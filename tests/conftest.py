import argparse
import os
import shutil
from pathlib import Path

import pytest

test_dir = "test"
datadir = Path(__file__).parent / "data"
FIRMWARE = "ESP32_GENERIC-20240602-v1.23.0.bin"


def pytest_addoption(parser: argparse.Namespace):
    parser.addoption(
        "--port",
        dest="port",
        action="store",
        default="/dev/ttyUSB0",
        help="Serial port for micropython board: /dev/ttyUSB0",
    )
    parser.addoption(
        "--baud",
        dest="baud",
        type=int,
        action="store",
        default=115200,
        help="Baud rate for serial port: 115200",
    )


@pytest.fixture(scope="session")
def firmware(tmp_path_factory: Path) -> Path:
    path: Path = tmp_path_factory.mktemp("test_dir")  # type: ignore
    assert isinstance(path, Path)
    firmware = path / FIRMWARE
    shutil.copyfile(datadir / FIRMWARE, firmware)
    os.chdir(path)
    return firmware
