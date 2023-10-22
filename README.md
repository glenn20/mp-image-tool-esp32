# mp-image-tool-esp32

Tool for manipulating partition tables in MicroPython esp32 firmware image files
and device flash storage.

`mp-image-tool-esp32` manipulates micropython esp32 firmware files and flash
storage on serial-attached ESP32 devices. It has been tested to work with ESP32,
ESP32-S2 and ESP32-S3 firmware images and devices.

**Contents: [Features](#features) | [Installation](#installation) |
[Examples](#examples) | [OTA Updates](#ota-firmware-updates) | [Usage](#usage)**

```console
$ mp-image-tool-esp32 ESP32_GENERIC-20231005-v1.21.0.bin
Opening image file: ESP32_GENERIC-20231005-v1.21.0.bin...
Chip type: esp32
Flash size: 4MB
Micropython App size: 0x186bb0 bytes (1,562 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000  0x0   (2.0 MB)
Micropython app fills 78.8% of factory partition (421 kB free)
```

## Features

`mp-image-tool-esp32` can operate on:

- micropython esp32 firmware files (including those downloaded from
  [micropython.org](https://micropython.org/download?port=esp32)) or
- flash storage in esp32 devices attached via serial port.

### Operations on files and esp32 devices

- Print a summary of the partition table of a micropython esp32 firmware file or
  device
  - `mp-image-tool-esp32 ESP32_GENERIC-20231005-v1.21.0.bin`
- Change the size of the flash storage for the firmware file:
  - `--resize-flash 8M` or `-f 8M`
- Rewrite or modify the partition table:
  - `--table ota` : install an OTA-enabled partition table
  - `--table default` : install the default micropython table (non-OTA)
  - `--table nvs=6B,phy_init=1B,factory=0x1f0B,vfs=0` : specify a table layout
  - `--resize factory=0x2M,vfs=0x400K` : resize any partition (adjust other
    parts to fit)
  - `--delete phy_init --resize nvs=0` : delete 'phy_init' and expand 'nvs' to
    use free space
  - `--add vfs2=fat:2M:1M` : add a new FS data partition at offset 0x200000 with
    size 0x100000
  - `--app-size 0x200000` : change the size of the `app` partitions (use this
    with `--table ota`)
- Extract the micropython application image (`.app-bin`) from the firmware
  or device
  - `--extract-app`: the `.app-bin` file saved can be used for OTA firmware
    updates.

### Operations on serial-attached esp32 devices

Use `mp-image-tool-esp32 u0` to operate on the esp32 device attached to
`/dev/ttyUSB0`. Additional features include:

- Modify the contents of partitions on the flash storage:
  - `--read factory=micropython.app-bin,nvs=nvs.bin` : read contents of
    partitions into files
  - `--write factory=micropython.app-bin` : write contents of files into
    partitions
  - `--write bootloader=bootloader.bin` : load a new bootloader from file
  - `--erase nvs,otadata` : erase partitions
  - `--erase-fs vfs` : erase 'vfs' filesystem (erases the first 4 blocks of the
      partition)
    - micropython will automatically build a fresh filesystem or 'nvs' partition
      on the next boot
- Use the `OTA` mechanism to perform a micropython firmware update over the
  serial interface to the device:
  - `--ota-update micropython.app-bin`

When operating on micropython firmware files, `mp-image-tool-esp32` will create
a copy of the firmware file with the partition table modified according to the
options provided. The original firmware file is not modified in any way. If no
modification options are given, it will print the partition table of `filename`.

When operating on serial-attached esp32 devices, `mp-image-tool-esp32` will
automatically erase any `data` partitions (eg. `nvs`, `otadata` or `vfs/fat`)
which have been moved or resized. Generally, micropython will re-initialise
these `data` partitions on next boot. This prevents micropython attempting to
mount what appears to be a corrupt filesystem or nvs partition.

`mp-image-tool-esp32` uses the
[`esptool.py`](https://github.com/espressif/esptool) program to perform the
operations on attached esp32 devices.

## Installation

First, copy this github repo into a folder somewhere:

```bash
git clone https://github.com/glenn20/mp-image-tool-esp32
cd mp-image-tool-esp32
```

If you use a python virtual environment, make sure it is active.

To use without installing:

- Prerequisites (`esptool` and `colorama`):

  ```bash
  pip install -r requirements.txt
  ```

- Usage:

  ```bash
  ./mp-image-tool-esp32 ~/Downloads/ESP32_GENERIC-20231005-v1.21.0.bin
  ```

To install in your python environment:

```bash
python -m build
pip install dist/mp_image_tool_esp32*.whl
```

## Examples

### Operating on ESP32 Firmware Files

#### Resize the flash size and expand the vfs partition to fill the space

```console
$ mp-image-tool-esp32 ESP32_GENERIC-20231005-v1.21.0.bin -f 8M --resize vfs=0
Opening image file: ESP32_GENERIC-20231005-v1.21.0.bin...
Chip type: esp32
Flash size: 4MB
Micropython App size: 0x186bb0 bytes (1,562 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000  0x0   (2.0 MB)
Micropython app fills 78.8% of factory partition (421 kB free)
Resizing vfs partition to 0x600000 bytes.
Writing output file: ESP32_GENERIC-20231005-v1.21.0-8MB-vfs=0.bin...
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x600000   0x800000  0x0   (6.0 MB)
Micropython app fills 78.8% of factory partition (421 kB free)
```

#### Convert a generic image to an OTA-capable firmware image

```console
$ mp-image-tool-esp32 ESP32_GENERIC-20231005-v1.21.0-8MB.bin --table ota
Opening image file: ESP32_GENERIC-20231005-v1.21.0-8MB.bin...
Warning: End of last partition (0x400000) < flash size (0x800000).
Chip type: esp32
Flash size: 8MB
Micropython App size: 0x186bb0 bytes (1,562 KB)
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000  0x0   (2.0 MB)
Warning: End of last partition (0x400000) < flash size (0x800000).
Micropython app fills 78.8% of factory partition (421 kB free)
Writing output file: ESP32_GENERIC-20231005-v1.21.0-8MB-OTA.bin...
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x5000     0xe000  0x0  (20.0 kB)
  otadata          data     ota          0xe000     0x2000    0x10000  0x0   (8.0 kB)
  ota_0            app      ota_0       0x10000   0x200000   0x210000  0x0   (2.0 MB)
  ota_1            app      ota_1      0x210000   0x200000   0x410000  0x0   (2.0 MB)
  vfs              data     fat        0x410000   0x3f0000   0x800000  0x0   (3.9 MB)
Micropython app fills 76.3% of ota_0 partition (485 kB free)
```

### Operating on ESP32 Devices

#### Resize the flash size and expand the vfs partition to fill available space

- will automatically erase the first 4 blocks of any data partition which is
  changed by the operation.
  - micropython will automatically create a new filesystem on 'vfs' at next
    boot.

```console
$ mp-image-tool-esp32 u0 -f 8M --resize vfs=0
Opening esp32 device at: /dev/ttyUSB0...
Warning: End of last partition (0x400000) < flash size (0x800000).
Chip type: esp32
Flash size: 8MB
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000  0x0   (2.0 MB)
Warning: End of last partition (0x400000) < flash size (0x800000).
Resizing vfs partition to 0x600000 bytes.
Writing new table to flash storage at /dev/ttyUSB0...
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x600000   0x800000  0x0   (6.0 MB)
Setting flash_size in bootloader to 8.0MB...
Erasing data partition: vfs...
```

#### Resize the flash storage and write an OTA partition table

```console
$ mp-image-tool-esp32 u0 -f 8M --table ota
Opening esp32 device at: /dev/ttyUSB0...
Warning: End of last partition (0x400000) < flash size (0x800000).
Chip type: esp32
Flash size: 8MB
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x6000     0xf000  0x0  (24.0 kB)
  phy_init         data     phy          0xf000     0x1000    0x10000  0x0   (4.0 kB)
  factory          app      factory     0x10000   0x1f0000   0x200000  0x0   (1.9 MB)
  vfs              data     fat        0x200000   0x200000   0x400000  0x0   (2.0 MB)
Warning: End of last partition (0x400000) < flash size (0x800000).
Writing new table to flash storage at /dev/ttyUSB0...
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x5000     0xe000  0x0  (20.0 kB)
  otadata          data     ota          0xe000     0x2000    0x10000  0x0   (8.0 kB)
  ota_0            app      ota_0       0x10000   0x200000   0x210000  0x0   (2.0 MB)
  ota_1            app      ota_1      0x210000   0x200000   0x410000  0x0   (2.0 MB)
  vfs              data     fat        0x410000   0x3f0000   0x800000  0x0   (3.9 MB)
Setting flash_size in bootloader to 8.0MB...
Erasing data partition: nvs...
Erasing data partition: otadata...
Warning: app partition 'ota_1' does not contain app image.
Erasing data partition: vfs...
```

#### Perform an OTA firmware update

```console
$ mp-image-tool-esp32 u0 --ota-update ESP32_GENERIC-20231005-v1.21.0.app-bin
Opening esp32 device: /dev/ttyUSB0...
Chip type: esp32
Flash size: 8MB
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x5000     0xe000  0x0  (20.0 kB)
  otadata          data     ota          0xe000     0x2000    0x10000  0x0   (8.0 kB)
  ota_0            app      ota_0       0x10000   0x200000   0x210000  0x0   (2.0 MB)
  ota_1            app      ota_1      0x210000   0x200000   0x410000  0x0   (2.0 MB)
  vfs              data     fat        0x410000   0x3f0000   0x800000  0x0   (3.9 MB)
Performing OTA firmware upgrade from 'ESP32_GENERIC-20231005-v1.21.0-8MB-OTA.app-bin'...
Writing firmware to OTA partition ota_1...
Updating otadata partition...
```

## OTA firmware updates

`mp-image-tool-esp32` can be used to perform an **OTA firmware update**
over the serial interface to an [OTA-enabled](
https://github.com/glenn20/micropython-esp32-ota#an-ota-enabled-partition-table)
esp32 device:

```sh
mp-image-tool-esp32 a1 --ota-update micropython.app-bin
```

ESP32 [Over-The-Air updates](
https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/ota.html)
are intended to support firmware updates over wifi or bluetooth, but sometimes
it is convenient to push a firmware update to an OTA-enabled, USB-attached
device. This is the purpose of the `--ota-update` option.

OTA updates must be performed using **micropython app image** firmware files.
You can :

- download a `.app-bin` firmware file from
  [micropython.org](https://micropython.org/download?port=esp32>) or
- use `--extract-app` to extract a `.app-bin` file from a micropython `.bin`
  firmware file. For more options, see [micropython app image](
  https://github.com/glenn20/micropython-esp32-ota#micropython-firmware-for-ota-updates).

OTA-enabled devices include those which:

- have been converted in place with `mp-image-tool-esp32 u0 --table ota` or
- have been flashed with `OTA` enabled firmware files (see [Firmware for OTA
  updates](
  https://github.com/glenn20/micropython-esp32-ota#micropython-firmware-for-ota-updates)):
  - produced by `mp-image-tool-esp32 filename --table ota` or
  - downloaded from
    [micropython.org](https://micropython.org/download?port=esp32).

### OTA Rollback

**CAUTION:** If you update the firmware with `--ota-update` and **OTA rollback**
is enabled, the device will automatically reset into the new firmware on
completion. If you then connect to the device over the serial port, the device
will usually reset again. If your startup files have **not** marked the firmware
as `valid`, your device will have **rolled back** to the previous firmware.

You can stop the **rollback** by marking the new firmware as **valid** with:

- `esp32.Partition.mark_app_valid_cancel_rollback()` ([docs](
  https://docs.micropython.org/en/latest/library/esp32.html#esp32.Partition.mark_app_valid_cancel_rollback)) or
- `ota.rollback.cancel()` if you use the
  [micropython-esp32-ota](https://github.com/glenn20/micropython-esp32-ota)
  tool.
- In practice, this means you should call
  `esp32.Partition.mark_app_valid_cancel_rollback()` after **every** restart.
  - Eg. in `main.py` -- or you might choose to wait till after your app has
    initialised wifi and any other devices you require so you know the new
    firmware is good for your app.
  - If it fails, just call `machine.hard_reset()` and
    the device will revert to the previous firmware on restart.

Alternatively, you can use `--no-rollback` to disable rollback for this update.

**OTA rollback** is enabled by default in the bootloader of:

- all micropython firmware files since `v1.21.0` and
- `-OTA` micropython firmware files for earlier versions downloaded from
  [micropython.org](https://micropython.org/download?port=esp32).

If you use `--table ota` to convert a non-OTA, pre-`v1.21.0` firmware, it will
**NOT** support OTA rollback. You **can** replace the bootloader with one from
an OTA-enabled firmware or device, but it is just easier to start with
rollback-enabled firmware.

See [micropython-esp32-ota](https://github.com/glenn20/micropython-esp32-ota)
for an example of a tool which can perform conventional OTA firmware updates
over the wifi interface.

**NOTE:** You can also update the app firmware of a non-OTA device with:

```shell
mp-image-tool-esp32 --write factory=ESP32_GENERIC-20231005-v1.21.0.app-bin
```

- This will upgrade the micropython firmware on the device **without** erasing
  the `nvs` partition (which is usually placed before the `factory` partition on
  the device), as would be the case for writing a full micropython firmware to
  the device with `esptool.py`.

## Usage

```text
usage: mp-image-tool-esp32 [-h] [-o OUTPUT] [-q] [-d] [-x] [-f SIZE] [-a SIZE]
                           [--no-rollback] [--ota-update FILE] [--from-csv FILE]
                           [--table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...]]
                           [--delete NAME1[,NAME2]]
                           [--add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]]
                           [--resize NAME1=SIZE1[,NAME2=SIZE2]] [--erase NAME1[,NAME2]]
                           [--erase-fs NAME1[,NAME2]]
                           [--read NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]]
                           [--write NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]]
                           filename

Tool for manipulating MicroPython esp32 firmware files and flash storage on esp32 devices.

positional arguments:
  filename              the esp32 firmware image filename or serial device

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        output filename
  -q, --quiet           mute program output
  -d, --debug           print additional info
  -x, --extract-app     extract .app-bin from firmware
  -f SIZE, --flash-size SIZE
                        size of flash for new partition table
  -a SIZE, --app-size SIZE
                        size of factory and ota app partitions
  --no-rollback         disable ota rollback on firmware update with --ota Use this if
                        bootloader or app don't support rollback.
  --ota-update FILE     perform an OTA firmware updgrade over the serial port
  --from-csv FILE       load new partition table from CSV file
  --table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...]
                        create new partition table, eg: "--table ota" (install an OTA-
                        enabled partition table), "--table default" (default (non-OTA)
                        partition table), "--table nvs=7B,factory=2M,vfs=0". SUBTYPE is
                        optional in most cases (inferred from name).
  --delete NAME1[,NAME2]
                        delete the named partitions
  --add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]
                        add new partitions to table
  --resize NAME1=SIZE1[,NAME2=SIZE2]
                        resize partitions eg. --resize factory=2M,nvs=5B,vfs=0. If SIZE is
                        0, expand partition to available space
  --erase NAME1[,NAME2]
                        erase the named partitions on device flash storage
  --erase-fs NAME1[,NAME2]
                        erase first 4 blocks of a partition on flash storage. Micropython
                        will initialise filesystem on next boot.
  --read NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]
                        copy partition contents to file(s)
  --write NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]
                        write file(s) contents into partitions on the device flash storage.

Where SIZE is a decimal or hex number with an optional suffix (M=megabytes, K=kilobytes,
B=blocks (0x1000=4096 bytes)). Options --erase, --erase-fs, --read, --write and --bootloader
can only be used when operating on serial-attached devices (not firmware files).
```
