from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .conftest import assert_output, mockfs_dir, mpi_run

rootdir = Path(__file__).parent.parent
test_outputs = rootdir / "tests" / "test_outputs.yaml"

with open(test_outputs) as f:
    OUTPUTS: dict[str, str] = yaml.safe_load(f)


def mpi_check_ls(firmware: Path, args: str) -> None:
    mpi_run(firmware, args)
    output = mpi_run(firmware, "-q --fs ls")
    assert_output(OUTPUTS[args], output)


def mpi_check(firmware: Path, args: str) -> None:
    output = mpi_run(firmware, args)
    assert_output(OUTPUTS[args], output)


# The mock device firmware is a 4MB firmware file with a 2MB littlefsv2
# filesystem at the end. This can be used to test filesystem operations.


def test_ls(mock_device: Path) -> None:
    mpi_check(mock_device, "-q --fs ls")


def test_cat(mock_device: Path) -> None:
    mpi_check(mock_device, "-q --fs cat boot.py")


def test_rename(mock_device: Path) -> None:
    mpi_check_ls(mock_device, "-q --fs rename boot.py boot.bak")


def test_mkdir(mock_device: Path) -> None:
    mpi_check_ls(mock_device, "-q --fs mkdir data")


def test_rm_file(mock_device: Path) -> None:
    mpi_check_ls(mock_device, "-q --fs rm lib/ota/blockdev_writer.mpy")


def test_rm_directory(mock_device: Path) -> None:
    mpi_check_ls(mock_device, "-q --fs rm /lib")


def test_mkfs(mock_device: Path) -> None:
    mpi_check_ls(mock_device, "-q --fs mkfs vfs")


def test_df(mock_device: Path) -> None:
    mpi_check(mock_device, "-q --fs df vfs")


def test_grow(mock_device: Path) -> None:
    with mock_device.open("r+b") as f:
        f.seek(0, 2)
        f.write(b"\xff" * (2 * 1024 * 1024))
    mpi_check(mock_device, "-q -f 6M --resize vfs=0 --fs grow --fs df")


def test_get(mock_device: Path) -> None:
    """Download a file and compare to the original."""
    mpi_run(mock_device, "-q --fs get /boot.py")
    assert Path("boot.py").exists()
    assert Path("boot.py").read_text() == (mockfs_dir / "boot.py").read_text()


def test_put(mock_device: Path) -> None:
    """Upload a file and compare to the original."""
    input, output = Path("input.data"), Path("output.data")
    data = bytes(range(256)) * 16
    input.write_bytes(data)
    assert input.stat().st_size == 256 * 16
    mpi_run(mock_device, f"-q --fs put {input}")
    mpi_run(mock_device, f"-q --fs get /{input} {output}")
    assert output.exists()
    assert output.read_bytes() == input.read_bytes()


def test_get_directory(mock_device: Path) -> None:
    """Download the entire filesystem to a directory and compare to the
    original."""
    rootfs = Path("rootfs")
    assert not rootfs.exists()
    mpi_run(mock_device, "-q --fs get / rootfs")
    assert rootfs.is_dir()
    new_files = list(rootfs.rglob("*"))
    orig_files = list(mockfs_dir.rglob("*"))
    assert len(new_files) == len(orig_files)
    for new, orig in zip(new_files, orig_files):
        assert new.relative_to(rootfs) == orig.relative_to(mockfs_dir)
        assert new.is_file() == orig.is_file()
        if new.is_file():
            assert new.read_bytes() == orig.read_bytes()
    shutil.rmtree(rootfs)


# The test of "put" assumes that "get" works correctly. If "get" is broken,
# this test will also be broken.
def test_put_directory(mock_device: Path) -> None:
    """Upload the entire filesystem to a directory and compare to the
    original."""
    rootfs = Path("rootfs")
    assert not rootfs.exists()
    mpi_run(mock_device, "-q --fs mkdir /rootfs")
    mpi_run(mock_device, f"-q --fs put {mockfs_dir} /rootfs")
    mpi_run(mock_device, f"-q --fs get /rootfs {rootfs}")
    assert rootfs.is_dir()
    new_dir = rootfs / mockfs_dir.name
    new_files = list(new_dir.rglob("*"))
    orig_files = list(mockfs_dir.rglob("*"))
    assert len(new_files) == len(orig_files)
    for new, orig in zip(new_files, orig_files):
        assert new.relative_to(new_dir) == orig.relative_to(mockfs_dir)
        assert new.is_file() == orig.is_file()
        if new.is_file():
            assert new.read_bytes() == orig.read_bytes()
    shutil.rmtree(rootfs)
