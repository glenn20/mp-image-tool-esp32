from __future__ import annotations

import hashlib
import platform
import re
from pathlib import Path

import pytest
import yaml

from .conftest import assert_output, mpi_run, options

rootdir = Path(__file__).parent.parent
test_outputs = rootdir / "tests" / "test_outputs.yaml"

with open(test_outputs) as f:
    OUTPUTS: dict[str, str] = yaml.safe_load(f)


def mpi_check(firmware: Path, args: str) -> None:
    output = mpi_run(firmware, args)
    assert_output(OUTPUTS[args], output)


def mpi_check_output(firmware: Path, args: str) -> None:
    mpi_run(firmware, args)
    output = mpi_run(firmware)
    assert_output(OUTPUTS[args], output)


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


def mpi_check_output_flash_size(firmware: Path, args: str) -> bool:
    output = mpi_run(firmware, args)
    if "ValueError: Selected flash size is larger than device flash size" in output:
        return False
    output = mpi_run(firmware)
    assert_output(OUTPUTS[args], output)
    return True


def test_flash_size(firmware: Path):
    if not mpi_check_output_flash_size(firmware, "--flash-size 8M"):
        pytest.skip("Skipping test_flash_size because device flash size is too small")


def test_flash_size_vfs(firmware: Path):
    if not mpi_check_output_flash_size(firmware, "--flash-size 8M --resize vfs=0"):
        pytest.skip(
            "Skipping test_flash_size_vfs because device flash size is too small"
        )


def test_read(firmware: Path, bootloader: bytes):
    out = Path("out.bin")
    mpi_run(firmware, f"--read bootloader={out.name}")
    output = out.read_bytes().rstrip(b"\xFF")
    assert len(output) == len(bootloader)
    assert output == bootloader


def test_write(firmware: Path):
    input = bytes(range(32)) * 8  # 256 data bytes to write
    infile, outfile = Path("input.bin"), Path("out2.bin")
    infile.write_bytes(bytes(range(32)) * 8)
    mpi_run(firmware, f"--write phy_init={infile}")
    mpi_run(firmware, f"--read phy_init={outfile}")
    output = outfile.read_bytes()
    assert len(output) == 4096
    output = output.rstrip(b"\xFF")
    assert len(output) == len(input)
    assert output == input


def test_erase(firmware: Path):
    Path("input.bin").write_bytes(bytes(range(32)) * 8)
    mpi_run(firmware, "--write phy_init=input.bin")
    mpi_run(firmware, "--read phy_init=output1.bin")
    mpi_run(firmware, "--erase phy_init")
    mpi_run(firmware, "--read phy_init=output2.bin")
    input = Path("input.bin").read_bytes()
    output1 = Path("output1.bin").read_bytes()
    output2 = Path("output2.bin").read_bytes()
    assert output1.rstrip(b"\xFF") == input
    assert len(output2) == 4096
    assert output2.count(0xFF) == len(output2)


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


def test_file_integrity(firmware: Path):
    if options.port:
        pytest.skip("Skipping test_file_integrity because --port is set")
    sha1 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    mpi_run(firmware, "--flash-size 8M --resize vfs=0")
    sha2 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    mpi_run(firmware, "--flash-size 4M --resize vfs=0")
    sha3 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    assert sha1 != sha2
    assert sha1 == sha3


def test_read_write(firmware: Path):
    if options.port:
        pytest.skip("Skipping test_read_write because --port is set")
    sha1 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    mpi_run(firmware, "--read bootloader=bootloader.bin")
    sha2 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    mpi_run(firmware, "--write bootloader=bootloader.bin")
    sha3 = hashlib.sha256(firmware.read_bytes()).hexdigest()
    assert sha1 == sha2
    assert sha1 == sha3
