# mp-image-tool-esp32

Tool for manipulating MicroPython esp32 firmware image files.

`mp-image-tool-esp32` manipulates partition tables and contents of micropython
esp32 firmware files (such as those at
<https://micropython.org/download?port=esp32>) and flash storage on ESP32
devices. It has been tested to work with ESP32, ESP32-S2 and ESP32-S3 firmware
images and devices.

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

`mp-image-tool-esp32` can:

- print a summary of the partition table of a micropython esp32 firmware file or device
  - `mp-image-tool-esp32 ESP32_GENERIC-20230426-v1.20.0.bin`
- change the size of the flash storage for the firmware file:
  - `--resize-flash 8M` or `-f 8M`
- rewrite or modify the partition table:
  - `--table ota` : install an OTA-enabled partition table
  - `--table default` : install the default micropython table (non-OTA)
  - `--table nvs=6B,phy_init=1B,factory=0x1f0B,vfs=0` : specify a table layout
  - `--resize factory=0x2M,vfs=0x400K` : resize any partition (adjust other
    parts to fit)
  - `--delete phy_init --resize nvs=0` : delete 'phy_init' and expand 'nvs' to
    use free space.
  - `--add vfs2=fat:2M:1M` : add a new FS data partition at offset 0x200000 with
    size 0x100000
  - `--app-size 0x200000` : change the size of the partitions which hold the micropython app firmware
- extract the micropython application image (`.app-bin`) from the firmware file
  - `--extract-app`

`mp-image-tool-esp32` will create a copy of the provided firmware file with the
partition table modified according to the options provided. The original
firmware file is not modified in any way. If no modification options are given,
it will print the partition table of `filename`.

`mp-image-tool-esp32` also works with flash storage on esp32 devices:

- print a summary of the partition table on flash storage of an esp32 device
  - `mp-image-tool-esp32 u0` : (u0=/dev/ttyUSB0, c1=COM1, ...)
- update the partition table on the flash storage using:
  - `--resize-flash`, `--table`, `--delete`, `--add`, `--resize` and
    `--app-size` (as above)
- modify the contents of partitions on the flash storage:
  - `--read-part factory=micropython.app-bin,nvs=nvs.bin` : read contents of partitions
    into files
  - `--write-part factory=micropython.app-bin` : write contents of files into partitions
  - `--erase-part nvs,otadata` : erase partitions
    - micropython automatically re-inits 'nvs' and 'otadata' partitions after
      being erased
  - `--erase-fs vfs` : erase 'vfs' filesystem
    - erases the first 4 blocks of the partition - micropython will
      automatically build a fresh filesystem on the next boot

`mp-image-tool-esp32` uses the
[`esptool.py`](https://github.com/espressif/esptool) program to perform the
operations on attached esp32 devices.

## Install

To use without installing:

- Prerequisites:

  ```bash
  pip install esptool colorama
  ```

- Usage:

  ```bash
  ./mp-image-tool-esp32 ~/Downloads/ESP32_GENERIC-20230426-v1.20.0.bin
  ```

To install in your python environment:

```bash
python -m build
pip install dist/mp_image_tool_esp32*.whl
```

## Examples

### Operating on ESP32 Firmware Files

Resize the flash size and expand the vfs partition to fill the space:

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

Convert a generic image to an OTA-capable firmware image:

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

Resize the flash size and expand the vfs partition to fill the space

- will automatically erase the first 4 block of any data partition which is
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

Resize the flash storage and write an OTA partition table:

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

## Usage

```text
usage: mp-image-tool-esp32 [-h] [-q] [-n] [-d] [-x] [-f SIZE] [-a SIZE] [--from-csv FILE]
                           [--table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...]]
                           [--delete NAME1[,NAME2]]
                           [--add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]]
                           [--resize NAME1=SIZE1[,NAME2=SIZE2]] [--erase NAME1[,NAME2]]
                           [--erase-fs NAME1[,NAME2]] [--read NAME1=FILE1[,NAME2=FILE2]]
                           [--write NAME1=FILE1[,NAME2=FILE2]]
                           filename

Tool for manipulating MicroPython esp32 firmware image files and flash storage on esp32
devices.

positional arguments:
  filename              the esp32 firmware image filename or serial device

options:
  -h, --help            show this help message and exit
  -q, --quiet           mute program output
  -n, --dummy           no output file
  -d, --debug           print additional info
  -x, --extract-app     extract .app-bin from firmware
  -f SIZE, --flash-size SIZE
                        size of flash for new partition table
  -a SIZE, --app-size SIZE
                        size of factory and ota app partitions
  --from-csv FILE       load new partition table from CSV file
  --table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...]
                        create new partition table, eg: "--table ota" (install an OTA-enabled
                        partition table), "--table default" (default (non-OTA) partition
                        table), "--table nvs=7B,factory=2M,vfs=0". SUBTYPE is optional in most
                        cases (inferred from name).
  --delete NAME1[,NAME2]
                        delete the named partitions
  --add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...]
                        add new partitions to table
  --resize NAME1=SIZE1[,NAME2=SIZE2]
                        resize partitions eg. --resize factory=2M,nvs=5B,vfs=0. If SIZE is 0,
                        expand partition to available space
  --erase NAME1[,NAME2]
                        erase the named partitions on device flash storage
  --erase-fs NAME1[,NAME2]
                        erase first 4 blocks of a partition on flash storage. Micropython will
                        initialise filesystem on next boot.
  --read NAME1=FILE1[,NAME2=FILE2]
                        copy partition contents to file
  --write NAME1=FILE1[,NAME2=FILE2]
                        write file contents into partitions on the device flash storage.

Where SIZE is a decimal or hex number with an optional suffix (M=megabytes, K=kilobytes,
B=blocks (0x1000=4096 bytes)). Options --erase, --erase-fs, --read, --write and --bootloader
can only be used when operating on serial-attached devices (not firmware files).
```
