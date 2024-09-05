"""LittleFS filesystem support for the ESP32 firmware image tool.

Uses the `littlefs-python` package to interact with the LittleFS filesystem in
the ESP32 firmware image.

Provides low-level functions to perform common file operations on a LittleFS
partition.

Also provides a command line processor, `lfs_cmd()` to perform these operations
on a firmware image file.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator

from littlefs import LFSConfig, LFSStat, LittleFS, UserContext

from . import logger as log
from .argtypes import B
from .firmware import Firmware

BLOCK_SIZE: int = B  # The default block size (4096) for the LittleFS filesystem.

# Contents of the boot.py file to be written after making a new filesystem
BOOT_PY = """\
# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
"""


# This is the UserContext implementation for the LittleFS filesystem
# that uses a Python file object for IO operations.
#
# Use this to access filesystems on firmware partitions.
class UserContextFile(UserContext):
    """Python IO file context for LittleFSv2"""

    file: BinaryIO

    def __init__(self, file: BinaryIO) -> None:
        self.file = file

    def read(self, cfg: LFSConfig, block: int, off: int, size: int) -> bytearray:
        logging.getLogger(__name__).debug(
            "LFS Read : Block: %d, Offset: %d, Size=%d" % (block, off, size)
        )
        self.file.seek(block * cfg.block_size + off)
        data = self.file.read(size)
        return bytearray(data)

    def prog(self, cfg: "LFSConfig", block: int, off: int, data: bytes) -> int:
        logging.getLogger(__name__).debug(
            "LFS Prog : Block: %d, Offset: %d, Data=%r" % (block, off, data[:40])
        )
        self.file.seek(block * cfg.block_size + off)
        self.file.write(data)
        return 0

    def erase(self, cfg: "LFSConfig", block: int) -> int:
        logging.getLogger(__name__).debug("LFS Erase: Block: %d" % block)
        self.file.seek(block * cfg.block_size)
        self.file.write(b"\xff" * cfg.block_size)
        return 0

    def sync(self, cfg: "LFSConfig") -> int:
        self.file.flush()
        return 0

    def __del__(self):
        if not self.file.closed:
            self.file.flush()
            self.file.close()


def _is_file(fs: LittleFS, src: str | Path) -> bool:
    """Check if the path is a file."""
    src = Path(src)
    return (fs.stat(src.as_posix()).type & LFSStat.TYPE_REG) != 0


def _is_dir(fs: LittleFS, src: Path) -> bool:
    """Check if the path is a directory."""
    return (fs.stat(src.as_posix()).type & LFSStat.TYPE_DIR) != 0


def _get_file(fs: LittleFS, src: Path, dst: Path) -> None:
    """Copy a file from the LittleFS filesystem to the local filesystem."""
    with fs.open(src.as_posix(), "rb") as f:
        dst.write_bytes(f.read())


def _put_file(fs: LittleFS, src: Path, dst: Path) -> None:
    """Copy a file from the local filesystem to the LittleFS filesystem."""
    with fs.open(dst.as_posix(), "wb") as f:
        f.write(src.read_bytes())


def _mkdir(fs: LittleFS, dst: Path) -> None:
    """Create a directory on the LittleFS filesystem."""
    try:
        fs.mkdir(dst.as_posix())
    except FileExistsError:
        if not _is_dir(fs, dst):
            raise FileExistsError(f"{dst} exists and is not a directory.")


def littlefs(part: BinaryIO, block_count: int = 0) -> LittleFS:
    """Create a LittleFS filesystem object for a partition."""
    return LittleFS(
        context=UserContextFile(part),
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

    def vfs_files(self, names: Iterable[str]) -> Iterator[tuple[LittleFS, str, str]]:
        """A generator to yield LittleFS filesystems for a list of partition names.
        Yields a tuple of the filesystem, the file name, and the partition name."""
        partname: str = "vfs"
        for *parts, name in (arg.rsplit(":", 1) for arg in names):
            partname = parts[0] if parts else partname
            with self.firmware.partition(partname) as part:
                with lfs_mounted(part) as fs:
                    yield fs, name, partname

    def do_info(self) -> None:
        """Print information about the LittleFS filesystem."""
        for fs, _name, _part in self.vfs_files(self.args or ["/"]):
            fs_size = fs.cfg.block_size * fs.block_count
            fstat = fs.fs_stat()
            v = fstat.disk_version
            version = f"{v >> 16}.{v & 0xFFFF}"
            print("LittleFS Configuration:")
            print(f"  Block Size:  {fs.cfg.block_size:9d}  /  0x{fs.cfg.block_size:X}")
            print(f"  Image Size:  {fs_size:9d}  /  0x{fs_size:X}")
            print(f"  Block Count: {fs.block_count:9d}")
            print(f"  Name Max:    {fs.cfg.name_max:9d}")
            print(f"  Disk Version:{version:>9s}")

    def do_ls(self) -> None:
        """Recursively list the contents of a directory on the LittleFS filesystem."""
        for fs, name, part in self.vfs_files(self.args or ["/"]):
            log.action(f"ls '{part}:{name}':")
            src = Path(name)
            for root, dirs, files in fs.walk(str(src)):
                root = Path(root).relative_to(src)
                for f in (root / f for f in files):
                    print(f"{f}")
                for f in (root / f for f in dirs):
                    print(f"{f}/")

    def do_cat(self) -> None:
        """Print out the contents of a file on the LittleFS filesystem."""
        for fs, name, part in self.vfs_files(self.args):
            log.action(f"cat '{part}:{name}':")
            if not _is_file(fs, Path(name)):
                raise FileNotFoundError(f"{name} is not a file.")
            with fs.open(name, "r") as f:
                print(f.read(), end="")

    def do_mkdir(self) -> None:
        """Create a directory on the LittleFS filesystem."""
        for fs, name, part in self.vfs_files(self.args):
            log.action(f"mkdir '{part}:{name}':")
            _mkdir(fs, Path(name))

    def do_rm(self) -> None:
        """Remove a file or directory from the LittleFS filesystem."""
        for fs, name, part in self.vfs_files(self.args):
            log.action(f"rm '{part}:{name}':")
            fs.remove(name, True)

    def do_rename(self) -> None:
        """Rename a file or directory on the LittleFS filesystem."""
        if len(self.args) != 2:
            raise ValueError("'--fs rename' requires two arguments")
        names = self.vfs_files(self.args)
        fs, name1, part1 = next(names)
        fs, name2, part2 = next(names)
        if part1 != part2:
            raise ValueError("'--fs rename' Both partitions must be the same")
        log.action(f"rename '{part1}:{name1}' -> '{name2}:")
        fs.rename(name1, name2)
        for _ in names:  # Finish the generator
            pass

    def do_get(self) -> None:
        """Copy a file or directory from the LittleFS filesystem to the local filesystem."""
        dest = self.args.pop(-1) if len(self.args) > 1 else "."
        for fs, name, part in self.vfs_files(self.args):
            log.action(f"get '{part}:{name}' -> '{dest}:")

            source, dest = Path(name), Path(dest)
            if _is_file(fs, source):  # Copy a single file
                # If the destination is a directory, copy the file into it
                if dest.is_dir():
                    dest /= source.name
                _get_file(fs, source, dest)
                continue

            print(f"{source} -> {dest}")
            dest.mkdir(exist_ok=True)
            for srcdir, dirs, files in fs.walk(str(source)):
                srcdir = Path(srcdir)
                dstdir = dest / srcdir.relative_to(source)
                for src, dst in ((srcdir / f, dstdir / f) for f in files):
                    print(f"{src} -> {dst}")
                    _get_file(fs, src, dst)
                for src, dst in ((srcdir / f, dstdir / f) for f in dirs):
                    print(f"{src}/ -> {dst}/")
                    dst.mkdir(exist_ok=True)

    def do_put(self) -> None:
        """Copy a file or directory from the local filesystem to the LittleFS filesystem."""
        destname = self.args.pop(-1) if len(self.args) > 1 else "."
        for fs, destname, part in self.vfs_files([destname]):
            log.action(f"put '{' '.join(self.args)}' -> '{part}:{destname}':")

            for name in self.args:
                source, dest = Path(name), Path(destname)
                if source.is_file():  # Copy a single file
                    # If the destination is a directory, copy the file into it
                    if _is_dir(fs, dest):
                        dest /= source.name
                    print(f"{source} -> {dest}")
                    _put_file(fs, source, dest)
                    continue

                dest /= source.name
                print(f"{source} -> {dest}")
                _mkdir(fs, dest)
                for srcdir, dirs, files in os.walk(str(source)):
                    srcdir = Path(srcdir)
                    dstdir = dest / srcdir.relative_to(source)
                    for src, dst in ((srcdir / f, dstdir / f) for f in files):
                        print(f"{src} -> {dst}")
                        _put_file(fs, src, dst)
                    for src, dst in ((srcdir / f, dstdir / f) for f in dirs):
                        print(f"{src}/ -> {dst}/")
                        _mkdir(fs, dst)

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


def lfs_cmd(firmware: Firmware, command: str, args: list[str]) -> None:
    """A command line processor for LittleFS filesystem operations."""
    cmd_processor = LFSCmd(firmware)
    cmd_processor.run_command(command, args)
