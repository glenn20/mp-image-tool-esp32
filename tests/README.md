# Tests for mp_image_tool_esp32

## Usage

Run these tests with `pytest` from the top-level directory. Eg. to run with `uv`
(`pip install uv`) :

- `uv run pytest` or `pytest`

or to test for all supported versions (3.8, 3.9, 3.10, 3.11, 3.12)

- `uv run tox` or `uvx tox` or `tox`

By default, `pytest` will run the tests against original and modified firmware
files downloaded from <https://micropython.org/download/>.

### Run tests against a real ESP32 device

Use `pytest --port u0` to run the tests against an ESP32 device attached to
serial port `/dev/ttyUSB0`.

- **WARNING:** pytest will erase and write new firmware to the device during the
tests.

## Files

- `tests/test_firmware.py`: Tests for basic commands:
  - `--table --delete --resize --flash-size --read --write --erase`
    `--extract-app --check-app`

- `tests/test_fs.py`: Tests for operations on the littlefs filesystems on flash
  storage of ESP32 devices:
  - `--fs mkfs, --fs ls, --fs cat, --fs rename, --fs mkdir, --fs rm, --fs get,
    --fs put`

- `tests/conftest.py`: Fixtures and initialisation for the tests.

- `tests/test_output.yaml`: A yaml file containing the expected outputs for the tests
  in `test_firmware.py` and `test_fs.py`. These are indexed by the command line
  args provided to `mp_image_tool_esp32`.

- `tests/data/*`: Directory for micropython firmware files downloaded from
  <https://micropython.org/download/> and a sample filesystem used for test_fs.py
  tests.
