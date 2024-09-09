# Tests for mp_image_tool_esp32

## Usage

Run these tests with `pytest` from the tol-level directory. Eg. to run with `uv` (`pip install uv`) :

```bash
uv run pytest
```

or to test for all supported versions (3.8, 3.9, 3.10, 3.11, 3.12)

- `uv run tox` or `uvx tox` or `tox`

## Files

- `test_firmware.py`: Tests for basic commands:
  - `--table --delete --resize --flash-size --read --write --erase`

    `--extract-app --check-app`

- `test_fs.py`: Tests for operations on the littlefs filesystems on flash
  storage of ESP32 devices:
  - `--fs mkfs, --fs ls, --fs cat, --fs rename, --fs mkdir, --fs rm, --fs get,
    --fs put`

- `conftest.py`: Fixtures and initialisation for the tests.

- `test_output.yaml`: A yaml file containing the expected outputs for the tests
  in `test_firmware.py` and `test_fs.py`. These are indexed by the command line args provided to `mp_image_tool_esp32`.
