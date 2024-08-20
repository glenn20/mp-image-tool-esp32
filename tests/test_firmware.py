from __future__ import annotations

import platform
import re
import shlex
import subprocess
from pathlib import Path

import yaml

rootdir = Path(__file__).parent.parent
test_outputs = rootdir / "tests" / "test-outputs.yaml"

# Use the top level script entry point to run the tests
# ... so we can test without installing the package
prog = rootdir / "mp-image-tool-esp32"

output_file = Path("test-output.bin")

with open(test_outputs) as f:
    OUTPUTS: dict[str, str] = yaml.safe_load(f)

BOOTLOADER_SIZE = 0x07_000
FACTORY_OFFSET = 0x0F_000
FACTORY_SIZE = 0x1F_0000


# Run the mp-image-tool-esp32 command and return the output
def mpitool(firmware: Path, *args: str) -> str:
    cmd = [str(prog), str(firmware), *args]
    cmd = shlex.split(" ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    output = "\n".join(line.rstrip() for line in res.stdout.splitlines())
    return output


def mpi_check(input: Path, args: str) -> None:
    output = mpitool(input, args)
    assert OUTPUTS[args].strip() in output


def mpi_check_output(input: Path, args: str) -> None:
    mpitool(input, "-o", output_file.name, args)
    output = mpitool(output_file)
    assert OUTPUTS[args].strip() in output


def test_python_version(firmware: Path):
    output = mpitool(firmware, "")
    match = re.search(r"Running mp-image-tool-esp32 .*Python ([0-9.]+)", output)
    assert match is not None
    assert match.group(1) == platform.python_version()


def test_firmware_file_exists(firmware: Path):
    assert Path(firmware).is_file()
    assert Path(firmware).stat().st_size > 0


def test_firmware_file_valid(firmware: Path):
    mpi_check(firmware, "")


def test_check_app(firmware: Path):
    mpi_check(firmware, "--check-app")


def test_flash_size(firmware: Path):
    mpi_check_output(firmware, "--flash-size 8M")


def test_table_ota_8M(firmware: Path):
    mpi_check_output(firmware, "--flash-size 8M --table ota")


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


def test_extract_app(firmware: Path):
    mpitool(firmware, "-o", output_file.name, "--extract-app")
    factory_part = firmware.read_bytes()[FACTORY_OFFSET:]
    app = output_file.read_bytes()
    assert factory_part == app


def test_erase(firmware: Path):
    mpitool(firmware, "-o", output_file.name, "--erase factory")
    factory_part = output_file.read_bytes()[FACTORY_OFFSET:]
    assert factory_part == b"\xFF" * len(factory_part)


def test_read(firmware: Path):
    bootloader = Path("bootloader.bin")
    mpitool(firmware, f"--read bootloader={bootloader.name}")
    output = bootloader.read_bytes()
    bootloader = firmware.read_bytes()[:BOOTLOADER_SIZE]
    assert len(output) == len(bootloader)
    assert output == bootloader


def test_write(firmware: Path):
    bootloader = Path("bootloader.bin")
    bootloader.write_bytes(firmware.read_bytes()[:BOOTLOADER_SIZE])
    mpitool(firmware, "-o", output_file.name, "--write factory=bootloader.bin")
    output = output_file.read_bytes()[FACTORY_OFFSET:]
    assert output == bootloader.read_bytes() + b"\xFF" * (
        FACTORY_SIZE - BOOTLOADER_SIZE
    )
