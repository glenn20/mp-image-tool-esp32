from __future__ import annotations

from pathlib import Path

import yaml

from .conftest import assert_output, mpi_run

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


def test_ls() -> None:
    mpi_check_output(rootdir / "firmware" / "ls", "ls")
