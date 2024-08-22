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

test_dir = "test"
datadir = Path(__file__).parent / "data"
FIRMWARE = "ESP32_GENERIC-20240602-v1.23.0.bin"
rootdir = Path(__file__).parent.parent

# Use the top level script entry point to run the tests
# ... so we can test without installing the package
prog = rootdir / "mp-image-tool-esp32"

output_file = Path("test-output.bin")
firmware_local = Path("firmware.bin")


BOOTLOADER_SIZE = 0x7_000
FACTORY_OFFSET = 0x10_000
FACTORY_SIZE = 0x1F0_000


class Options(Namespace):
    device: str = ""
    firmware: str = ""
    flash: bool = False
    show: bool = False


test_options: Options = Options()


# Run the mp-image-tool-esp32 command and return the output
def mpi_run(firmware: Path, *args: str, output: Path | None = None) -> str:
    output_file.unlink(missing_ok=True)
    if args:
        args = ("--output", output_file.name) + args
    cmd = [str(prog), str(firmware), *args]
    cmd = shlex.split(" ".join(cmd))
    if test_options.show:
        print("Command:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise subprocess.CalledProcessError(res.returncode, cmd)
    if output_file.exists():
        os.rename(output_file, output or firmware_local)
    stdout = "\n".join(line.rstrip() for line in res.stdout.splitlines())
    if test_options.show:
        print(stdout)
        print(res.stderr)
    return stdout


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


def expand_device_short_names(name: str) -> str:
    """Expand short device names to full device names."""
    name = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", name)
    name = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", name)
    name = re.sub(r"^c([0-9]+)$", r"COM\1", name)
    return name


@pytest.fixture(scope="session")
def options(pytestconfig: Config) -> Options:
    global test_options
    test_options = Options(**pytestconfig.option.__dict__)
    return test_options


@pytest.fixture(scope="session")
def testdir(tmp_path_factory: Any) -> Path:
    path: Path = tmp_path_factory.mktemp("test_dir")  # type: ignore
    assert isinstance(path, Path)
    os.chdir(path)
    return path


@pytest.fixture(scope="session")
def firmwarefile(testdir: Path, options: Options) -> Path:
    if options.firmware:
        files = sorted(datadir.glob(f"*{options.firmware}*"))
        if not files:
            raise FileNotFoundError(f"Matching file not found: *{options.firmware}*")
        firmware = files[0]
        print(f"Using firmware file: {firmware.name}")
    else:
        firmware = datadir / Path(FIRMWARE)
    shutil.copyfile(firmware, firmware.name)
    return Path(firmware.name)


@pytest.fixture(scope="session")
def device_init(firmwarefile: Path, options: Options) -> Path | None:
    if not options.device:
        return None
    device = Path(expand_device_short_names(options.device))
    if options.flash:
        # Flash default firmware to the device
        mpi_run(firmwarefile, "--flash", str(device))
    return device


@pytest.fixture
def firmware(device_init: Path | None, firmwarefile: Path) -> Path:
    if device_init:
        # Set a default partition table on the device
        mpi_run(device_init, "--flash-size 4M --table original")
        return device_init
    else:
        shutil.copyfile(firmwarefile, firmware_local)
        return firmware_local


@pytest.fixture(scope="session")
def rawdevice(options: Options) -> Path:
    path = Path(options.device)
    return path


@pytest.fixture(scope="session")
def flashdevice(options: Options, rawdevice: Path, firmware: Path) -> Path:
    if options.flash and options.device:
        mpi_run(firmware, "--flash", str(rawdevice))
    return rawdevice


@pytest.fixture
def device(flashdevice: Path, firmware: Path) -> Path:
    """Write a default partition table to the device."""
    mpi_run(flashdevice, "--flash-size 4M --table original")
    return flashdevice


@pytest.fixture(scope="session")
def bootloader(firmwarefile: Path) -> bytes:
    return firmwarefile.read_bytes()[:BOOTLOADER_SIZE].rstrip(b"\xFF")


@pytest.fixture(scope="session")
def app_image(firmwarefile: Path) -> bytes:
    output = mpi_run(firmwarefile)
    match = re.search(r"Found esp32(\w*) firmware file", output)
    offset = FACTORY_OFFSET
    if match and match.group(1) in ("", "s2"):
        offset -= 0x1000
        print(offset, match, match.group(1))
    return firmwarefile.read_bytes()[offset:].rstrip(b"\xFF")
