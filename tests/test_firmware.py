from __future__ import annotations

import platform
import re
from pathlib import Path

import yaml

from .conftest import mpi_run

rootdir = Path(__file__).parent.parent
test_outputs = rootdir / "tests" / "test_outputs.yaml"

with open(test_outputs) as f:
    OUTPUTS: dict[str, str] = yaml.safe_load(f)


def mpi_check(firmware: Path, args: str) -> None:
    output = mpi_run(firmware, args)
    for line in OUTPUTS[args].strip().splitlines():
        assert line in output


def mpi_check_output(firmware: Path, args: str) -> None:
    mpi_run(firmware, args)
    output = mpi_run(firmware)
    for line in OUTPUTS[args].strip():
        assert line in output


def test_python_version(firmware: Path):
    output = mpi_run(firmware, "")
    match = re.search(r"Running mp-image-tool-esp32 .*Python ([0-9.]+)", output)
    assert match is not None
    assert match.group(1) == platform.python_version()


def test_firmware_file_valid(firmware: Path):
    mpi_check(firmware, "")


def test_table_ota(firmware: Path):
    mpi_check_output(firmware, "--table ota --app-size 0x1f0B")


def test_table_default(firmware: Path):
    mpi_check_output(firmware, "--table default")


def test_table_custom(firmware: Path):
    mpi_check_output(firmware, "--table nvs=7B,factory=2M,vfs=1M,vfs2=fat:0")


def test_delete(firmware: Path):
    mpi_check_output(firmware, "--delete phy_init")


def test_resize(firmware: Path):
    mpi_check_output(firmware, "--resize vfs=1M")


def test_add(firmware: Path):
    mpi_check_output(firmware, "--resize vfs=1M --add data=fat:50B")


# def test_flash_size(firmware: Path):
#     mpi_check_output(firmware, "--flash-size 8M")


def test_read(firmware: Path, bootloader: bytes):
    out = Path("out.bin")
    mpi_run(firmware, f"--read bootloader={out.name}")
    output = out.read_bytes().rstrip(b"\xFF")
    assert len(output) == len(bootloader)
    assert output == bootloader


def test_write(firmware: Path):
    input = bytes(range(32)) * 8
    input_file = Path("input.bin")
    input_file.write_bytes(input)
    out = Path("out.bin")
    mpi_run(firmware, f"--write phy_init={input_file.name}")
    mpi_run(firmware, f"--read phy_init={out.name}")
    output = out.read_bytes()
    assert len(output) == 0x1000
    output = output.rstrip(b"\xFF")
    assert len(output) == len(input)
    assert output == input


def test_erase(firmware: Path):
    mpi_run(firmware, "--erase phy_init")
    mpi_run(firmware, "--read phy_init=output.bin")
    output = Path("output.bin").read_bytes()
    assert len(output) == 0x1000
    assert output.count(0xFF) == len(output)


def test_extract_app(firmware: Path, app_image: bytes):
    app = Path("app.bin")
    mpi_run(firmware, "--extract-app", output=app)
    output = app.read_bytes()
    assert len(output) == len(app_image)
    assert output == app_image


def test_check_app(firmware: Path, app_image: bytes, bootloader: bytes):
    output = mpi_run(firmware, "--check-app")
    for line in (
        "Partition 'bootloader': App image signature found.",
        f"Partition 'bootloader': Hash confirmed (size={len(bootloader)}).",
        "Partition 'factory': App image signature found.",
        f"Partition 'factory': Hash confirmed (size={len(app_image)}).",
    ):
        assert line in output
