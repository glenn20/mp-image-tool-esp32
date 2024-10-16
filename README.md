# mp-image-tool-esp32: Working with esp32 firmware files and devices

![CI Tests](https://github.com/glenn20/mp-image-tool-esp32/actions/workflows/ci-tests.yaml/badge.svg)

Tool for manipulating partition tables and files in MicroPython esp32 firmware
image files and device flash storage.

`mp-image-tool-esp32` manipulates micropython esp32 firmware files and flash
storage on serial-attached ESP32 devices. It has been tested to work with ESP32,
ESP32-S2 and ESP32-S3 firmware images and devices.

**Contents: [Features](#features) | [Installation](#installation) |
[Examples](#examples) | [Filesystem Operations](#filesystem-operations) | [OTA Updates](#ota-firmware-updates) | [Usage](#usage)**

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
  - `mp-image-tool-esp32 ESP32_GENERIC-20231005-v1.21.0.bin` or
  - `mp-image-tool-esp32 /dev/ttyUSB0` (Linux) or
  - `mp-image-tool-esp32 COM1` (Windows)
- Change the size of the flash storage programmed into the firmware header:
  - `--resize-flash 8M` or `-f 8M`
- Rewrite or modify the partition table:
  - `--table ota` : install an OTA-enabled partition table
  - `--table default` : install a default micropython table (non-OTA, without 'phy_init')
  - `--table original` : install the original default micropython table (non-OTA, with 'phy_init')
  - `--table nvs=6B,phy_init=1B,factory=0x1f0B,vfs=0` : specify a table layout
  - `--resize factory=2M,vfs=0x400K` : resize any partition (adjust other
    parts to fit)
  - `--delete phy_init --resize nvs=0` : delete 'phy_init' and expand 'nvs' to
    use free space
  - `--add vfs2=fat:2M:1M` : add a new FS data partition at offset 0x200000 with
    size 0x100000
  - `--app-size 0x200000` : change the size of the `app` partitions (use this
    with `--table ota`)
- Extract the micropython application image (`.app-bin`) from the firmware
  or device
  - `--extract-app`: the extracted `.app-bin` file can be used for OTA firmware
    updates.
- Modify the contents of partitions in the firmware:
  - `--read factory=micropython.app-bin,nvs=nvs.bin` : read contents of
    partitions into files
  - `--write factory=micropython.app-bin` : write contents of files into
    partitions
  - `--write bootloader=bootloader.bin` : load a new bootloader from file
  - `--erase nvs,otadata` : erase partitions

When operating on micropython firmware files, `mp-image-tool-esp32` will create
a copy of the firmware file with the partition table and partition contents
modified according to the options provided. The original firmware file is not
modified in any way. If no modification options are given, it will print the
partition table of `filename`.

### Operations on serial-attached esp32 devices

Use `mp-image-tool-esp32 u0` to operate on the esp32 device attached to
`/dev/ttyUSB0`. When operating on esp32 devices over a serial interface, the
following additional commands are available:

- Perform operations on the files installed on the `vfs` or other filesystem
  partition:
  - `--fs ls` will list all the files on the device filesystem
  - `--fs get . backup` will copy all the files on the device filesystem to
    `backup` on the local computer
  - `--fs put backup/* /` will copy all the files from `backup` onto the
    device filesystem .
    - See [below](#filesystem-operations) for more filesystem operations
- Erase 'vfs' filesystem partitions:
  - `--erase vfs` : erases the `vfs` partition
    - micropython will automatically build a fresh filesystem on the next boot
- Use the `OTA` mechanism to perform a micropython firmware update over the
  serial interface to the device:
  - `--ota-update micropython.app-bin`
- Flash a firmware (including any changes) to an esp32 device, eg:
  - `mp-image-tool-esp32 firmware.bin --flash u0` or
  - `mp-image-tool-esp32 firmware.bin -f 8M --table ota --flash /dev/ttyACM1`

  `mp-image-tool-esp32` will automatically use the right `esptool` options to
  flash the firmware for your device (you don't need to remember if you should
  write to offset `0x0` or `0x1000`)

When operating on serial-attached esp32 devices, `mp-image-tool-esp32` will
automatically erase any `data` partitions (eg. `nvs`, `otadata` or `vfs/fat`)
which have been moved or resized. Generally, micropython will re-initialise
these `data` partitions on next boot. This prevents micropython attempting to
mount what appears to be a corrupt filesystem or nvs partition.

- Note: Since version 0.0.7, `mp-image-tool-esp32` will not automatically erase
  filesytem partitions that have been **increased** in size. Micropython will
  complain that the filesystem is corrupt on reboot because the filesystem does
  not match the partition size, but this can be repaired with `--fs grow vfs` or
  use `--erase vfs` to forcibly erase the partition.

`mp-image-tool-esp32` uses the
[`esptool.py`](https://github.com/espressif/esptool) program to perform the
operations on attached esp32 devices:

- Select the specific method used to perform operations on the device:
  - `--method direct/command/subprocess`
    - `subprocess`: Run the "esptool.py" command in a subprocess to interact
      with the device.
    - `command`: Run the esptool commands in this process using the
      **esptool.main()** function from the esptool module.
    - `direct`: (default): Use lower level functions from the **esptool** module to
      perform operations on the device. This is more efficient as it skips
      repeated initialisation and querying of the device.

    Versions prior to 0.0.5, always used the `subprocess` method.

## Installation

### Install from PYPI

- Using pip: `pip install mp-image-tool-esp32`, or
- Using uv: `uv tool install mp-image-tool-esp32`.

### Install from github source

I recommend using [`uv`](https://docs.astral.sh/uv/) to install and manage
dependencies and dev environments.

```bash
git clone https://github.com/glenn20/mp-image-tool-esp32
cd mp-image-tool-esp32
uv build  # To build an installable .whl file
uv tool install dist/mp_image_tool_esp32-0.0.12-py3-none-any.whl
```

To run the tests: `uv run pytest` or `uv run tox`.

## Examples

#### Change the flash size of a firmware file and expand the vfs partition

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

#### Change the flash size of firmware on a device and write an OTA partition table

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

## Filesystem Operations

`mp_image_tool_esp32` can be used to access and manipulate files installed on
the `littlefsv2` filesystems, the default filesystem used by micropython on the
device flash storage (FAT filesystems are not supported). `mp_image_tool_esp32`
uses the [`littlefs-python`](https://github.com/jrast/littlefs-python) package
to operate on these filesystems.

The available fs comands are:

- `--fs df`: List current usage of filesystems.
- `--fs ls /lib /data`: Recursively list the files in the `/lib` and `/data`
  directories of the `vfs` partition.
- `--fs get /lib /data backup`: Recursively copy `/lib` and `/data`
  from the device to `./backup` on the local host.
- `--fs put backup/* /`: Recursively copy all files and dirs in `backup/` to the
  device.
- `--fs cat boot.py`: Print out the contents of `/boot.py` on the device.
- `--fs mkdir /data`: Create a new directory on the device.
- `--fs rm /boot.py /main.py`: Recursively delete files and directories on the device.
- `--fs rename app.py main.py`: Rename files on the device.
- `--fs mkfs vfs`: Create a new littlefsv2 filesystem on the `vfs` partition
  (will erase the partition first).
- `--fs grow [vfs [blocks]]`: Grow the filesystem to fill the partition or to the
  requested number of 4K-blocks.
  - Note: micropython will not mount a filesystem unless it uses all the space
    in the partition. Use this after you have used `--resize` to increase the
    size of a filesystem partition.

Filenames on the device can be prefixed with a partition name to operate on a
filesystem partition other than `vfs`, eg. `--fs ls vfs2:/recordings`.

The `--fs` commands operate directly on the filesystem on the flash storage, and
not through the micropython repl. Some operations may be much faster using
this method, though the current implementation does not yet support block
caching which should provide further performance improvements.

Eg. `mp-image-tool-esp32 a0 --fs mkfs vfs --fs put ./rootfs/* /` will create
a new littlefs filesystem on the 'vfs' partition and initialise it with the
files from `./rootfs/` on the local computer.

You can also use [`littlefs-python`](https://github.com/jrast/littlefs-python)
to build filesystem partitions on your computer and flash them to the device,
eg:

```bash
littlefs-python create --compact --no-pad --block-size 4096 --fs-size=2mb ./root-fs vfs.bin
mp-image-tool-esp32 u0 --write vfs=vfs.bin
```

will create a new littlefs filesystem image, fill it with files from the
root-fs directory and flash it to the `vfs` partition on the device attached to
serial port `/dev/ttyUSB0`.

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
  - downloaded from
    [micropython.org](https://micropython.org/download?port=esp32) or
  - produced by `mp-image-tool-esp32 filename --table ota`.

### OTA Rollback

**CAUTION:** If you update the firmware with `--ota-update` and **OTA rollback**
is enabled, the device will automatically reset into the new firmware on
completion. If you then connect to the device over the serial port, your IDE or
terminal software may reset the device again. If your startup files have **not**
marked the firmware as `valid`, your device will have **rolled back to the
previous firmware** before you get to work with it.

You *can* stop the **rollback** by marking the new firmware as **valid** with:

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
usage: mp-image-tool-esp32 [-h] [-o FILE] [-q] [-n] [-x] [-f SIZE] [-a SIZE]
                           [-m METHOD] [-d]
                           [--log NAME=LEVEL[,NAME=LEVEL,...]] [--check-app]
                           [--no-rollback] [--baud RATE] [--ota-update FILE]
                           [--from-csv FILE]
                           [--table ota/default/original/NAME1=SUBTYPE:SIZE[,NAME2,...]]
                           [--delete NAME1[,NAME2]]
                           [--add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]]
                           [--resize NAME1=SIZE1[,NAME2=SIZE2]]
                           [--erase NAME1[,NAME2]] [--erase-fs NAME1[,NAME2]]
                           [--read NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]]
                           [--write NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]]
                           [--flash DEVICE] [--trimblocks] [--trim]
                           [--fs CMD [CMD ...]]
                           filename

Tool for manipulating MicroPython esp32 firmware files and flash storage on
esp32 devices.

positional arguments:
  filename              the esp32 firmware filename or serial device

options:
  -h, --help            show this help message and exit
  -o FILE, --output FILE
                        output firmware filename (auto-generated if not given)
  -q, --quiet           set debug level to ERROR (default: INFO)
  -n, --no-reset        leave device in bootloader mode afterward
  -x, --extract-app     extract .app-bin from firmware
  -f SIZE, --flash-size SIZE
                        size of flash for new partition table
  -a SIZE, --app-size SIZE
                        size of factory and ota app partitions
  -m METHOD, --method METHOD
                        esptool method: subprocess, command or direct
                        (default)
  -d, --debug           set debug level to DEBUG (default: INFO)
  --log NAME=LEVEL[,NAME=LEVEL,...]
                        set the log level for the named loggers.
  --check-app           check app partitions and OTA config are valid
  --no-rollback         disable app rollback after OTA update
  --baud RATE           baud rate for serial port (default: 921600)
  --ota-update FILE     perform an OTA firmware upgrade over the serial port
  --from-csv FILE       load new partition table from CSV file
  --table ota/default/original/NAME1=SUBTYPE:SIZE[,NAME2,...]
                        create new partition table, eg: "--table ota" (install
                        an OTA-enabled partition table), "--table default"
                        (default (non-OTA) partition table), "--table
                        nvs=7B,factory=2M,vfs=0". SUBTYPE is optional in most
                        cases (inferred from name).
  --delete NAME1[,NAME2]
                        delete the named partitions
  --add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]
                        add new partitions to table
  --resize NAME1=SIZE1[,NAME2=SIZE2]
                        resize partitions eg. --resize
                        factory=2M,nvs=5B,vfs=0. If SIZE is 0, expand
                        partition to available space
  --erase NAME1[,NAME2]
                        erase the named partitions
  --erase-fs NAME1[,NAME2]
                        erase first 4 blocks of a partition on flash storage.
                        Micropython will initialise filesystem on next boot.
  --read NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]
                        copy partition contents (or bootloader) to file. Use
                        --trimblocks or --trim to remove trailing blank
                        blocks.
  --write NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...]
                        write file(s) contents into partitions (or bootloader)
                        in the firmware.
  --flash DEVICE        flash new firmware to the serial-attached device.
  --trimblocks          Remove trailing blank blocks from data returned by
                        --read and --extract-app. This is useful for reading
                        app images and filesystems from flash storage.
  --trim                Like --trimblocks, but trims to 16-byte boundary. This
                        is appropriate for reading app images from flash
                        storage.
  --fs CMD [CMD ...]    Operate on files in the `vfs` or other filesystem
                        partitions.

Where SIZE is a decimal or hex number with an optional suffix (M=megabytes,
K=kilobytes, B=blocks (0x1000=4096 bytes)). --fs commands include: ls, get,
put, mkdir, rm, rename, cat, info, mkfs, df and grow. Options --erase-fs and
--ota-update can only be used when operating on serial-attached devices (not
firmware files). If the --flash option is provided, the firmware (including
any changes made) will be flashed to the device, eg: `mp-image-tool-esp32
firmware.bin --flash u0` is a convenient way to flash firmware to a device.

```
