from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
from _pytest.config import Config

rootdir: Path = Path(__file__).parent.parent  # The root directory of the project
datadir: Path = Path(__file__).parent / "data"  # Location for firmware files

mpi_prog: Path = rootdir / "mp-image-tool-esp32"  # Location of the tool to test

BOOTLOADER_SIZE = 0x7_000  # Size of the bootloader in the firmware file
FACTORY_OFFSET = 0x10_000  # Offset of the factory partition in the firmware file
FACTORY_SIZE = 0x1F0_000  # Size of the factory partition in the firmware file


# After initialising an ESP32 device the partition table should be as follows:
# If the table does not match this, the test will exit
expected_partition_table: str = """
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size        End Flags
  nvs              data     nvs          0x9000     0x6000     0xf000   0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000   0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000   0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000   0x0   (2.0 MB)
"""
# Firmware files to download and use for testing
firmware_version = "20240602-v1.23.0"
firmware_baseurl = "https://micropython.org/resources/firmware/"
firmware_files = [
    f"ESP32_GENERIC-{firmware_version}.bin",
    f"ESP32_GENERIC_S2-{firmware_version}.bin",
    f"ESP32_GENERIC_S3-FLASH_4M-{firmware_version}.bin",
    f"ESP32_GENERIC_C3-{firmware_version}.bin",
]
firmware_file: Path = datadir / firmware_files[0]
mpi_last_output: str = ""


# Class to add type annotations for command line options
class Options(Namespace):
    device: str = ""
    firmware: str = ""
    args: str = ""
    flash: bool = False
    show: bool = False


# The command line options provided to pytest.
options: Options = Options()


def pytest_addoption(parser: Namespace):
    parser.addoption(
        "--device",
        dest="device",
        action="store",
        default="",
        help="Serial port for micropython board: u0, a0, c0",
    )
    parser.addoption(
        "--firmware",
        dest="firmware",
        action="store",
        default="",
        help="Nmae of the firmware file to use",
    )
    parser.addoption(
        "--args",
        dest="args",
        action="store",
        default="",
        help="Additional arguments to pass to the mp-image-tool-esp32 command",
    )
    parser.addoption(
        "--flash",
        dest="flash",
        action="store_true",
        default=False,
        help="Flash a firmware image to the device",
    )
    parser.addoption(
        "--show",
        dest="show",
        action="store_true",
        default=False,
        help="Show output from the mp-image-tool-esp32 command",
    )


def download_firmware_files():
    """Download the firmware files if they are not present in 'datadir'."""
    if not datadir.exists():
        datadir.mkdir()
    for f in firmware_files:
        if not (datadir / f).exists():
            print(f"Downloading firmware file: {f}")
            subprocess.run(
                ["wget", f"{firmware_baseurl}{f}", "-O", f"{datadir / f}"],
                check=True,
            )


## pytest_configure is called after command line options have been parsed
def pytest_configure(config: Config):
    global options
    global firmware_file
    download_firmware_files()  # Download firmware files if needed
    options = Options(**config.option.__dict__)
    if options.firmware:
        files = sorted(datadir.glob(f"*{options.firmware}*"))
        if not files:
            pytest.exit(
                f"Matching firmware file not found: *{options.firmware}*\n"
                f"Available firmware files are: {firmware_files}"
            )
        firmware_file = files[0]
    print("Using firmware file:", firmware_file.name)


# Run the mp-image-tool-esp32 command and return the output
def mpi_run(firmware: Path, *args: str, output: Path | None = None) -> str:
    """Execute the mp-image-tool-esp32 command with the given arguments.
    Returns the output of the command as a string."""
    outputfile = output or Path("_test_output.bin")
    if args:
        args = ("--output", outputfile.name) + args
    cmd = [str(mpi_prog), str(firmware), options.args, *args]
    cmd = shlex.split(" ".join(cmd))
    if options.show:
        print("Command:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if options.show or res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        if res.returncode != 0:
            raise subprocess.CalledProcessError(res.returncode, cmd)
    if not output and outputfile.exists() and firmware.parent == Path("."):
        # Replace the firmware file with the output file
        os.rename(outputfile, firmware)
    global mpi_last_output
    mpi_last_output = res.stdout
    return res.stdout


@pytest.fixture(scope="session")
def testdir(tmp_path_factory: Any) -> Path:
    """A fixture to create a temporary directory for testing (session scope).
    Will set the current working directory to the temporary directory
    and return the directory as a Path object."""
    path: Path = tmp_path_factory.mktemp("test_dir")  # type: ignore
    assert isinstance(path, Path)
    os.chdir(path)
    return path


@pytest.fixture(scope="session")
def firmwarefile(testdir: Path) -> Path:
    """Copy a firmware file to a testing directory (session scope).
    Returns the path to the copied file."""
    shutil.copyfile(firmware_file, firmware_file.name)
    return Path(firmware_file.name)


@pytest.fixture(scope="session")
def device() -> Path | None:
    """Fixture to produce an initialised ESP32 device (session scope).
    If the --flash option is given, a firmware is flashed to the device.
    The device is returned as a Path instance."""

    def expand_device_short_names(name: str) -> str:
        """Expand short device names to full device names."""
        name = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", name)
        name = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", name)
        name = re.sub(r"^c([0-9]+)$", r"COM\1", name)
        return name

    if not options.device:
        return None
    device = Path(expand_device_short_names(options.device))
    if options.flash:
        # Flash default firmware to the device
        mpi_run(firmware_file, "--flash", str(device))

    return device


# Strip whitespace from front and end of each line
def striplines(output: str) -> str:
    return re.sub(r"\s*\n\s*", r"\n", output.strip())


def check_output(expected: str, output: str) -> bool:
    return striplines(expected) in striplines(output)


def assert_output(expected: str, output: str) -> bool:
    return striplines(expected) in striplines(output)


@pytest.fixture
def firmware(device: Path | None, firmwarefile: Path) -> Path:
    """Returns a firmware file to use for testing as a Path instance.
    If the --device option is given, the returned Path will be a serial
    port connected to the ESP32 device.
    Otherwise, a default firmware file is returned."""
    if device:
        # Write a default partition table on the device if necessary
        if check_output(expected_partition_table, mpi_last_output):
            return device
        elif check_output(
            expected_partition_table,
            mpi_run(device, "--flash-size 4M --table original"),
        ):
            return device
        else:
            pytest.exit(
                f"Device {device} Partition table:\n"
                f"{mpi_last_output}\n"
                f"  does not match expected partition table:\n"
                f"{expected_partition_table}"
            )
    else:
        local = Path("firmware.bin")
        shutil.copyfile(firmwarefile, local)
        return local


@pytest.fixture(scope="session")
def bootloader(firmwarefile: Path) -> bytes:
    """A fixture to extract the bootloader from a firmware file.
    The bootloader image is returned as a bytes object."""
    return firmwarefile.read_bytes()[:BOOTLOADER_SIZE].rstrip(b"\xFF")


@pytest.fixture(scope="session")
def app_image(firmwarefile: Path) -> bytes:
    """A fixture to extract the application image from a firmware file.
    The application image is returned as a bytes object."""
    output = mpi_run(firmwarefile)
    match = re.search(r"Found (esp32\w*) firmware file", output)
    if not match:
        pytest.exit("Could not find firmware type in output:\n" + output)
    chip_name = match.group(1)
    offset = FACTORY_OFFSET  # Start of app image within firmware file
    if chip_name in ("esp32", "esp32s2"):
        offset -= 0x1000  # ESP32 and ESP32S2 firmwares start at offset 0x1000
    return firmwarefile.read_bytes()[offset:].rstrip(b"\xFF")
