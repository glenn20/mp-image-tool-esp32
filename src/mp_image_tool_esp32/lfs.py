"""LittleFS filesystem support for the ESP32 firmware image tool.

Uses the `littlefs-python` package to interact with the LittleFS filesystem in
the ESP32 firmware image.

Provides low-level functions to perform common file operations on a LittleFS
partition.

Also provides a command line processor, `lfs_cmd()` to perform these operations
on a firmware image file.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, DefaultDict, Iterable, Iterator

import more_itertools
from littlefs import LFSConfig, LFSStat, LittleFS, LittleFSError, UserContext
from rich import box

from . import logger
from .argtypes import KB, B, IntArg
from .data_table import TableTuple, print_table
from .firmware import Firmware

log = logger.getLogger(__name__)

BLOCK_SIZE: int = B  # The default block size (4096) for the LittleFS filesystem.

# Contents of the boot.py file to be written after making a new filesystem
BOOT_PY = """\
# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
"""


@dataclass
class CacheStats:
    """A dataclass to hold cache statistics for a BlockCache."""

    reads: int = 0
    misses: int = 0
    writes: int = 0

    @property
    def hits(self) -> int:
        return self.reads - self.misses

    def summary(self) -> str:
        return (
            f"cache hits: {self.hits} cache misses: "
            f"{self.misses} writes: {self.writes}"
        )


class BlockCache(DefaultDict[int, bytes]):
    """A caching interface to reading and writing blocks of data to a file.

    Writes are cached and flushed to the file when the `flush()` or `close()`
    methods are called. Writing blocks from the write cache is optimized by
    joining contiguous blocks together into a single write operation.

    The caching strategy provides significant performance improvements for
    reading and writing to the flash storage of a serial-attached esp32
    device."""

    file: BinaryIO
    block_size: int
    write_cache: dict[int, bytes] | None
    stats: CacheStats

    def __init__(
        self,
        file: BinaryIO,
        block_size: int = BLOCK_SIZE,
        write_cache: bool = True,
    ) -> None:
        super().__init__()
        self.file = file
        self.block_size = block_size
        self.write_cache = {} if write_cache else None
        self.stats = CacheStats()

    def __getitem__(self, key: int) -> bytes:
        self.stats.reads += 1
        return super().__getitem__(key)

    def __missing__(self, block: int) -> bytes:
        """Reading from the cache failed, read the block from the file."""
        self.stats.misses += 1
        log.debug(f"Read block {block} from file")
        self.file.seek(block * self.block_size)
        data = self.file.read(self.block_size)
        super().__setitem__(block, data)  # Save in the read cache
        return data

    def __setitem__(self, block: int, data: bytes) -> None:
        """Save the block data to the cache and write cache."""
        assert len(data) == self.block_size, "Data must be a block size"
        self.stats.writes += 1
        if self.write_cache is not None:
            log.debug(f"Write block {block} to cache")
            self.write_cache[block] = data  # Cache the write
        else:
            log.debug(f"Write block {block} to file {self.file.name}")
            self.file.seek(block * self.block_size)
            self.file.write(data)
        super().__setitem__(block, data)  # Save in the read cache

    def flush(self) -> None:
        """Flush cached writes to the file."""
        if not self.write_cache:
            self.file.flush()
            return

        # Join contiguous blocks together into larger blocks for writing
        def group_blocks(
            items: Iterable[tuple[int, bytes]],
        ) -> Iterable[tuple[int, bytes]]:
            return (
                # (start_block_number, concatenated_block_data)
                (blocks.peek()[0], b"".join(data for _block_num, data in blocks))
                for blocks in (
                    more_itertools.peekable(group)
                    for group in more_itertools.consecutive_groups(
                        sorted(items),  # Sort by block number
                        ordering=lambda item: item[0],  # key = block number
                    )
                )
            )

        for start_block, data in group_blocks(self.write_cache.items()):
            nblocks = len(data) / self.block_size
            log.debug(f"Writing {nblocks} blocks at {start_block}...")
            self.file.seek(start_block * self.block_size)
            self.file.write(data)
        self.file.flush()
        self.write_cache.clear()

    def close(self) -> None:
        """Flush the write cache to the file."""
        if self.file.closed:
            return
        self.flush()
        log.debug(f"Closing: {self.stats.summary()}")
        self.clear()
        self.file.flush()
        self.file.close()


# This is the UserContext implementation for the LittleFS filesystem
# that uses a Python file object for IO operations.
#
# Use this to access filesystems on firmware partitions.
class UserContextFile(UserContext):
    """Python IO file context for LittleFSv2"""

    block_cache: BlockCache

    def __init__(self, file: BinaryIO, block_size: int = BLOCK_SIZE) -> None:
        self.block_cache = BlockCache(file, block_size)

    def read_block(self, block: int) -> bytes:
        return self.block_cache[block]

    def write_block(self, block: int, data: bytes) -> None:
        self.block_cache[block] = data

    def read(self, cfg: LFSConfig, block: int, off: int, size: int) -> bytearray:
        log.debug("LFS Read : Block: %d, Offset: %d, Size=%d" % (block, off, size))
        assert off == 0, "Read offset must be 0"
        assert (
            size == cfg.block_size == self.block_cache.block_size
        ), "Read size must be block size"
        start, end = block, block + (off + size) // cfg.block_size
        data = b"".join(self.read_block(i) for i in range(start, end + 1))
        return bytearray(data[off : off + size])

    def prog(self, cfg: "LFSConfig", block: int, off: int, data: bytes) -> int:
        log.debug("LFS Prog : Block: %d, Offset: %d, Size=%d" % (block, off, len(data)))
        block_size = cfg.block_size
        assert off == 0, "Write offset must be 0"
        assert (
            len(data) == block_size == self.block_cache.block_size
        ), "Write size must be block size"
        for i in range(len(data) // block_size):
            self.write_block(
                block + i,
                data[i * block_size : (i + 1) * block_size],
            )
        return 0

    def erase_block(self, block: int) -> int:
        log.debug("LFS Erase: Block: %d" % block)
        self.write_block(block, b"\xff" * self.block_cache.block_size)
        return 0

    def erase(self, cfg: "LFSConfig", block: int) -> int:
        self.erase_block(block)
        return 0  # We dont need to erase blocks before writing blocks.

    def sync(self, cfg: "LFSConfig") -> int:
        # sync is a no-op for the BlockCache
        log.debug("LFS Sync:")
        return 0

    def __del__(self) -> None:
        self.block_cache.close()


def _is_file(fs: LittleFS, path: Path) -> bool:
    """Check if the path is a file."""
    return (fs.stat(path.as_posix()).type & LFSStat.TYPE_REG) != 0


def _is_dir(fs: LittleFS, path: Path) -> bool:
    """Check if the path is a directory."""
    return (fs.stat(path.as_posix()).type & LFSStat.TYPE_DIR) != 0


def _get_file(fs: LittleFS, src: Path, dst: Path) -> None:
    """Copy a file from the LittleFS filesystem to the local filesystem."""
    with fs.open(src.as_posix(), "rb") as f:
        dst.write_bytes(f.read())
    assert fs.stat(src.as_posix()).size == dst.stat().st_size


def _put_file(fs: LittleFS, src: Path, dst: Path) -> None:
    """Copy a file from the local filesystem to the LittleFS filesystem."""
    # Remove the destination file if it exists to make room before copying
    # in case we are over-copying a very large file.
    try:
        fs.remove(dst.as_posix())
    except FileNotFoundError:
        pass
    with fs.open(dst.as_posix(), "wb") as f:
        f.write(src.read_bytes())
    assert fs.stat(dst.as_posix()).size == src.stat().st_size


def littlefs(part: BinaryIO, block_count: int = 0) -> LittleFS:
    """Create a LittleFS filesystem object for a partition."""
    return LittleFS(
        context=UserContextFile(part, BLOCK_SIZE),
        block_size=BLOCK_SIZE,
        block_count=block_count,
        mount=False,
    )


@contextmanager
def lfs_mounted(part: BinaryIO) -> Iterator[LittleFS]:
    """A context manager to mount and unmount a LittleFS filesystem."""
    fs = littlefs(part)
    fs.mount()
    try:
        yield fs
    finally:
        fs.unmount()
        del fs


class LFSCmd:
    """A command processor for LittleFS filesystem operations."""

    def __init__(self, firmware: Firmware) -> None:
        self.firmware = firmware

    def run_command(self, command: str, args: list[str]) -> None:
        """Run a command with arguments."""
        self.command = command
        self.args = args
        funcname = f"do_{command}"
        if hasattr(self, funcname):
            func = getattr(self, funcname)
            if callable(func):
                func()
        else:
            raise ValueError(f"Unknown --fs command '{self.command}'")

    def vfs_files(self, names: Iterable[str]) -> Iterator[tuple[LittleFS, Path, str]]:
        """A generator to yield LittleFS filesystems for a list of partition names.
        Yields a tuple of the filesystem, the file name, and the partition name."""
        partname: str = "vfs"
        for *parts, name in (arg.rsplit(":", 1) for arg in names):
            partname = parts[0] if parts else partname
            try:
                with self.firmware.partition(partname) as part:
                    with lfs_mounted(part) as fs:
                        yield fs, Path(name), partname
            except (ValueError, LittleFSError):
                # Skip partition if not present in firmware file or if no lfs
                pass

    def vfs_partitions(self, names: Iterable[str]) -> Iterator[tuple[LittleFS, str]]:
        """A generator to yield LittleFS filesystems for a list of partition names.
        Yields a tuple of the filesystem, the file name, and the partition
        name."""
        vfs_parts = list(names) or (
            p for p in self.firmware.table if p.subtype_name == "fat"
        )
        for part in vfs_parts:
            try:
                with self.firmware.partition(part) as p:
                    with lfs_mounted(p) as fs:
                        yield fs, p.part.name
            except (ValueError, LittleFSError):
                # Skip partition if not present in firmware file or if no lfs
                pass

    def do_info(self) -> None:
        """Print information about the LittleFS filesystem."""
        for fs, part in self.vfs_partitions(self.args):
            fs_size = fs.cfg.block_size * fs.block_count
            fstat = fs.fs_stat()
            v = fstat.disk_version
            version = f"{v >> 16}.{v & 0xFFFF}"
            print(f"Filesystem '{part}': LittleFS")
            print(f"  Disk Version:{version:>9s}")
            print(f"  Name Max:    {fs.cfg.name_max:9d}")
            print(f"  Image Size:  {fs_size:9d}  /  0x{fs_size:X}")
            print(f"  Block Size:  {fs.cfg.block_size:9d}  /  0x{fs.cfg.block_size:X}")
            print(f"  Blocks Total:{fs.block_count:9d}")
            print(f"  Blocks Used: {fs.used_block_count:>9d}")
            print(f"  Blocks Free: {fs.block_count-fs.used_block_count:>9d}")

    def do_df(self) -> None:
        """Print size and usage information about the LittleFS filesystem."""
        table = TableTuple(
            "LittleFS Filesystems",
            "  {:14s} {:>9d} {:>8d} {:>9d} {:>5.0f}%",
            "Partition 'Total kB' 'Used kB' 'Free kB' Used",
            [
                (
                    name,
                    fs.block_count * BLOCK_SIZE // KB,
                    fs.used_block_count * BLOCK_SIZE // KB,
                    (fs.block_count - fs.used_block_count) * BLOCK_SIZE // KB,
                    100 * fs.used_block_count / fs.block_count,
                )
                for fs, name in self.vfs_partitions(self.args)
            ],
        )
        print_table(table, box=box.ROUNDED, style="cyan")

    def do_grow(self) -> None:
        """Resize/grow the LittleFS filesystem."""
        name: str = (self.args or ["vfs"])[0]
        size: int = int(IntArg(self.args[1])) if len(self.args) > 1 else 0
        with self.firmware.partition(name) as p:
            with lfs_mounted(p) as fs:
                old, new = fs.block_count, size or p.part.size // BLOCK_SIZE
                log.action(f"fs: grow '{name}' from {old} to {new} blocks")
                if err := fs.fs_grow(new):
                    raise LittleFSError(err)

    def do_ls(self) -> None:
        """Recursively list the contents of a directory on the LittleFS filesystem."""
        for fs, path, part in self.vfs_files(self.args or [""]):
            log.action(f"ls '{part}:{path.as_posix()}'")
            for root, subdirs, files in fs.walk(path.as_posix()):
                d = Path(root).relative_to(path)
                for f in (d / f for f in files):
                    print(f.as_posix())
                for f in (d / f for f in subdirs):
                    print(f.as_posix() + "/")

    def do_cat(self) -> None:
        """Print out the contents of a file on the LittleFS filesystem."""
        for fs, path, part in self.vfs_files(self.args):
            log.action(f"cat '{part}:{path.as_posix()}'")
            if not _is_file(fs, path):
                raise FileNotFoundError(f"{path.as_posix()} is not a file.")
            with fs.open(path.as_posix(), "r") as f:
                print(f.read(), end="")

    def do_mkdir(self) -> None:
        """Create a directory on the LittleFS filesystem."""
        for fs, path, part in self.vfs_files(self.args):
            log.action(f"mkdir '{part}:{path.as_posix()}'")
            fs.makedirs(path.as_posix(), exist_ok=True)
            assert _is_dir(fs, path)

    def do_rm(self) -> None:
        """Remove a file or directory from the LittleFS filesystem."""
        for fs, path, part in self.vfs_files(self.args):
            log.action(f"rm '{part}:{path}'")
            fs.remove(path.as_posix(), recursive=True)

    def do_rename(self) -> None:
        """Rename a file or directory on the LittleFS filesystem."""
        if len(self.args) != 2:
            raise ValueError("'--fs rename' requires two arguments")
        names = self.vfs_files(self.args)
        fs, path1, part1 = next(names)
        fs, path2, part2 = next(names)
        if part1 != part2:
            raise ValueError("'--fs rename' Both partitions must be the same")
        log.action(f"rename '{part1}:{path1.as_posix()}' -> '{path2.as_posix()}")
        fs.rename(path1.as_posix(), path2.as_posix())
        for _ in names:  # Finish the generator
            pass

    def do_get(self) -> None:
        """Copy a file or directory from the LittleFS filesystem to the local filesystem."""
        destname = self.args.pop(-1) if len(self.args) > 1 else "."
        for fs, path, part in self.vfs_files(self.args):
            log.action(f"get '{part}:{path.as_posix()}' -> '{destname}")

            source, dest = Path(path), Path(destname)
            if _is_file(fs, source):  # Copy a single file
                # If the destination is a directory, copy the file into it
                if dest.is_dir():
                    dest /= source.name
                _get_file(fs, source, dest)
                continue

            print(f"{source.as_posix()} -> {dest}")
            dest.mkdir(exist_ok=True)
            for root, subdirs, files in fs.walk(source.as_posix()):
                srcdir = Path(root)
                dstdir = dest / srcdir.relative_to(source)
                for src, dst in ((srcdir / f, dstdir / f) for f in files):
                    print(f"{src.as_posix()} -> {dst}")
                    _get_file(fs, src, dst)
                for src, dst in ((srcdir / f, dstdir / f) for f in subdirs):
                    print(f"{src.as_posix()}/ -> {dst}{os.sep}")
                    dst.mkdir(exist_ok=True)

    def do_put(self) -> None:
        """Copy a file or directory from the local filesystem to the LittleFS filesystem."""
        destname = self.args.pop(-1) if len(self.args) > 1 else "."
        for fs, destpath, part in self.vfs_files([destname]):
            for name in self.args:
                log.action(f"put '{name}' -> '{part}:{destpath.as_posix()}':")
                source, dest = Path(name), destpath
                if source.is_file():  # Copy a single file
                    # If the destination is a directory, copy the file into it
                    if _is_dir(fs, dest):
                        dest /= source.name
                    print(f"{source} -> {dest.as_posix()}")
                    _put_file(fs, source, dest)
                    continue

                dest /= source.name
                print(f"{source} -> {dest.as_posix()}")
                fs.makedirs(dest.as_posix(), exist_ok=True)
                for root, dirs, files in os.walk(source):
                    srcdir = Path(root)
                    dstdir = dest / srcdir.relative_to(source)
                    for src, dst in ((srcdir / f, dstdir / f) for f in files):
                        print(f"{src} -> {dst.as_posix()}")
                        _put_file(fs, src, dst)
                    for src, dst in ((srcdir / f, dstdir / f) for f in dirs):
                        print(f"{src}{os.sep} -> {dst.as_posix()}/")
                        fs.makedirs(dst.as_posix(), exist_ok=True)

    def do_mkfs(self) -> None:
        """Create a new LittleFS filesystem on a partition.
        Will erase the partition and write a `boot.py` file to the root directory."""
        for name in self.args or ["vfs"]:
            with self.firmware.partition(name) as part:
                part.truncate()
                log.action(f"mkfs on partition '{name}'...")
                size = part.seek(0, os.SEEK_END)
                block_count = size // BLOCK_SIZE
                fs = littlefs(part, block_count=block_count)
                fs.format()
                fs.mount()
                try:
                    with fs.open("boot.py", "w") as f:
                        f.write(BOOT_PY)
                finally:
                    fs.unmount()
                    del fs


def lfs_cmd(firmware: Firmware, command: str, args: list[str] = []) -> None:
    """A command line processor for LittleFS filesystem operations."""
    LFSCmd(firmware).run_command(command, args)
