from __future__ import annotations

import importlib
import logging
import os
import re
import shlex
import shutil
import subprocess
import warnings
from argparse import Namespace
from pathlib import Path
from typing import Any

import mp_image_tool_esp32
import pytest
from _pytest.config import Config
from mp_image_tool_esp32 import data_table

rootdir: Path = Path(__file__).parent.parent  # The root directory of the project
datadir: Path = Path(__file__).parent / "data"  # Location for firmware files

mpi_prog: Path = rootdir / "mp-image-tool-esp32"  # Location of the tool to test

BOOTLOADER_OFFSET = 0x1_000  # Size of the bootloader in the firmware file
BOOTLOADER_SIZE = 0x7_000  # Size of the bootloader in the firmware file
FACTORY_OFFSET = 0x10_000  # Offset of the factory partition in the firmware file
FACTORY_SIZE = 0x1F0_000  # Size of the factory partition in the firmware file

KB = 1024  # 1KB in bytes
MB = 1024 * 1024  # 1MB in bytes

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

mockfs_dir = datadir / "mock-fs"
assert mockfs_dir.exists(), f"Mock filesystem directory not found: {mockfs_dir}"

capsys_: pytest.CaptureFixture[str] | None = None
caplog_: pytest.LogCaptureFixture | None = None


# Class to add type annotations for command line options
class Options(Namespace):
    port: str = ""
    firmware: str = ""
    args: str = ""
    flash: bool = False
    show: bool = False


# The command line options provided to pytest.
options: Options = Options()


def pytest_addoption(parser: Namespace):
    parser.addoption(
        "--port",
        dest="port",
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


@pytest.fixture(autouse=True)
def my_setup(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
):
    global capsys_, caplog_
    capsys_ = capsys
    caplog_ = caplog
    caplog.set_level(logging.INFO, logger="mp_image_tool_esp32")


def do_mpi_run(firmware: Path, *args: str, output: Path | None = None) -> None:
    """Execute the mp-image-tool-esp32 command with the given arguments.
    Returns the output of the command as a string."""
    outputfile = output or Path("_test_output.bin")
    if args:
        args = ("--output", outputfile.name) + args
    cmd = [str(mpi_prog), str(firmware), options.args, *args]
    cmd = shlex.split(" ".join(cmd))
    importlib.reload(mp_image_tool_esp32)  # Reload the module to reset global variables
    data_table.use_rich_table = False  # Use plain text tables for testing
    assert mp_image_tool_esp32.main(cmd[1:]) == 0
    # subprocess.run(cmd)
    if not output and outputfile.exists() and firmware.parent == Path("."):
        # Replace the firmware file with the output file
        os.rename(outputfile, firmware)


def mpi_run(firmware: Path, *args: str, output: Path | None = None) -> str:
    assert capsys_ is not None
    _ = capsys_.readouterr().out  # Flush any captured output
    do_mpi_run(firmware, *args, output=output)
    return capsys_.readouterr().out  # Return captured output from command


def log_messages() -> str:
    assert caplog_ is not None
    return "\n".join([record[2] for record in caplog_.record_tuples])


# Strip whitespace from front and end of each line
def striplines(output: str) -> str:
    with warnings.catch_warnings():
        # Suppress the warning about possible nested sets in the regex
        warnings.simplefilter("ignore")
        return re.sub(
            r"\s*\n\s*",
            r"\n",
            re.sub(
                "\x1b[[0-9;]*m",
                "",
                output.strip(),
            ),
        )


def check_output(expected: str, output: str) -> bool:
    return striplines(expected) in striplines(output)


def assert_output(expected: str, output: str) -> None:
    expected = striplines(expected)
    output = striplines(output)
    assert expected in output, f"Expected:\n{expected}\nOutput:\n{output}"


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
def mock_device_session(testdir: Path) -> Path:
    """A fixture to create a mock device firmware for testing (session scope).
    Returns the path to the mock device as a Path object. The mock device
    firmware is a 4MB firmware file with a 2MB littlefsv2 filesystem at the end.
    """
    shutil.copyfile(firmware_file, firmware_file.name)
    device = Path("mock_esp32_device_session.bin")
    vfs = Path("vfs.bin")
    subprocess.run(
        f"littlefs-python create --fs-size 2mb --block-size 4096 {mockfs_dir} {vfs}".split(),
        check=True,
    )
    assert vfs.stat().st_size == 2 * MB, "Mock filesystem size is not 2MB"
    with device.open("w+b") as f:
        f.truncate()
        f.write(firmware_file.read_bytes())
        f.write(b"\xff" * (2 * MB - BOOTLOADER_OFFSET - f.tell()))  # Pad to 2MB - 4KB
        f.write(vfs.read_bytes())
        assert f.tell() == 4 * MB - BOOTLOADER_OFFSET, "Mock device size is not 4MB"
    return device


@pytest.fixture()
def mock_device(mock_device_session: Path) -> Path:
    """A fixture to create a fresh copy of the mock device firmware for testing."""
    device = Path("mock_esp32_device.bin")
    shutil.copyfile(mock_device_session, device)
    return device


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

    if not options.port:
        return None
    device = Path(expand_device_short_names(options.port))
    if options.flash:
        # Flash default firmware to the device
        do_mpi_run(firmware_file, "--flash", str(device))

    return device


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


@pytest.fixture()
def app_image(firmwarefile: Path) -> bytes:
    """A fixture to extract the application image from a firmware file.
    The application image is returned as a bytes object."""
    output = mpi_run(firmwarefile)
    match = re.search(r"Found (esp32\w*) firmware file", log_messages())
    if not match:
        pytest.exit("Could not find firmware type in output:\n" + output)
    chip_name = match.group(1)
    offset = FACTORY_OFFSET  # Start of app image within firmware file
    if chip_name in ("esp32", "esp32s2"):
        offset -= 0x1000  # ESP32 and ESP32S2 firmwares start at offset 0x1000
    return firmwarefile.read_bytes()[offset:].rstrip(b"\xFF")
