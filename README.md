# mp-image-tool-esp32

Tool for manipulating MicroPython esp32 image files.

`mp-image-tool-esp32` copies an existing micropython esp32 firmware file, such
as those at <https://micropython.org/download?port=esp32>, to a new file with a
modified partition table. It has been tested to work with ESP32, ESP32-S2 and
ESP32-S3 firmware images.

`mp-image-tool-esp32` can:

- print a summary of the partition table of a micropython esp32 firmware file
  (`mp-image-tool-esp32 filename`)
- change the size of the flash storage for the firmware file (eg.
  `--resize-flash 8MB`)
- rewrite the partition table to support Over-The-Air (OTA) firmware updates
  (`--ota`)
- change the size of the partitions which hold the micropython app firmware
  (`--app-size 0x200000`)
- change the size of any partition (`--resize factory=0x2M,vfs=0x400K`)
- extract the micropython application image (`.app-bin`) from the firmware file

`mp-image-tool-esp32` will create a copy of the provided firmware file with the
partition table modified according to the options provided. The original
firmware file is not modified in any way. If no modification options are given,
it will print the partition table of `filename`.

**NOTE:** This tool is not yet packaged for installation, but it can be run from
the repo top folder with `mp-image-tool-esp32.py [-options]  filename`.

## Usage

```text
usage: mp-image-tool-esp32.py [-h] [-q] [-n] [-d] [-o] [-x] [-f FLASH_SIZE] [-a APP_SIZE]
                              [-r RESIZE]
                              filename
```

### options

```text
  -h, --help            show this help message and exit
  -q, --quiet           mute program output
  -n, --dummy           no output file
  -d, --debug           print additional diagnostics
  -o, --ota             build an OTA partition table
  -x, --extract-app     extract the micropython .app-bin
  -f FLASH_SIZE, --flash-size FLASH_SIZE
                        size of flash for new partition table
  -a APP_SIZE, --app-size APP_SIZE
                        size of factory and ota app partitions
  -r RESIZE, --resize RESIZE
                        resize specific partitions by name/label, eg. --resize
                        factory=0x2M,vfs=0x400K
```

## Examples

Display the partition table..

```bash
$ ./mp-image-tool-esp32.py ESP32_GENERIC-20230426-v1.20.0.bin
Opening image file: ESP32_GENERIC-20230426-v1.20.0.bin...
Chip type: esp32
Flash size: 4MB
App size: 0x16d740 bytes (1,461 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size  Flags
  nvs              data     nvs          0x9000     0x6000  0x0   (24.0 kB)
  phy_init         data     phy          0xf000     0x1000  0x0    (4.0 kB)
  factory          app      factory     0x10000   0x1f0000  0x0    (1.9 MB)
  vfs              data     fat        0x200000   0x200000  0x0    (2.0 MB)
Micropython app fills 73.7% of factory partition (522 kB unused)
Filesystem partition "vfs" is 2.0 MB.
```

Resize the flash size:

```bash
$ ./mp-image-tool-esp32.py ESP32_GENERIC-20230426-v1.20.0.bin -f 8M
Opening image file: ESP32_GENERIC-20230426-v1.20.0.bin...
Chip type: esp32
Flash size: 4MB
App size: 0x16d740 bytes (1,461 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size  Flags
  nvs              data     nvs          0x9000     0x6000  0x0   (24.0 kB)
  phy_init         data     phy          0xf000     0x1000  0x0    (4.0 kB)
  factory          app      factory     0x10000   0x1f0000  0x0    (1.9 MB)
  vfs              data     fat        0x200000   0x200000  0x0    (2.0 MB)
Micropython app fills 73.7% of factory partition (522 kB unused)
Filesystem partition "vfs" is 2.0 MB.
Writing output file: ESP32_GENERIC-20230426-v1.20.0-8MB.bin...
Partition table (flash size: 8MB):
# Name             Type     SubType      Offset       Size  Flags
  nvs              data     nvs          0x9000     0x6000  0x0   (24.0 kB)
  phy_init         data     phy          0xf000     0x1000  0x0    (4.0 kB)
  factory          app      factory     0x10000   0x1f0000  0x0    (1.9 MB)
  vfs              data     fat        0x200000   0x600000  0x0    (6.0 MB)
Micropython app fills 73.7% of factory partition (522 kB unused)
Filesystem partition "vfs" is 6.0 MB.
```

Convert a generic image to an OTA-capable firmware image:

```bash
$ ./mp-image-tool-esp32.py ESP32_GENERIC-20230426-v1.20.0.bin --ota
Opening image file: ESP32_GENERIC-20230426-v1.20.0.bin...
Chip type: esp32
Flash size: 4MB
App size: 0x16d740 bytes (1,461 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size  Flags
  nvs              data     nvs          0x9000     0x6000  0x0   (24.0 kB)
  phy_init         data     phy          0xf000     0x1000  0x0    (4.0 kB)
  factory          app      factory     0x10000   0x1f0000  0x0    (1.9 MB)
  vfs              data     fat        0x200000   0x200000  0x0    (2.0 MB)
Micropython app fills 73.7% of factory partition (522 kB unused)
Filesystem partition "vfs" is 2.0 MB.
Writing output file: ESP32_GENERIC-20230426-v1.20.0-OTA.bin...
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size  Flags
  nvs              data     nvs          0x9000     0x5000  0x0   (20.0 kB)
  otadata          data     ota          0xe000     0x2000  0x0    (8.0 kB)
  ota_0            app      ota_0       0x10000   0x180000  0x0    (1.5 MB)
  ota_1            app      ota_1      0x190000   0x180000  0x0    (1.5 MB)
  vfs              data     fat        0x310000    0xf0000  0x0    (0.9 MB)
Micropython app fills 95.2% of ota_0 partition (74 kB unused)
Filesystem partition "vfs" is 0.9 MB.
```

Resize all the **app** partitions (*factory* or *ota_?*):

```bash
$ ./mp-image-tool-esp32.py ESP32_GENERIC-20230426-v1.20.0-OTA.bin --app_size 0x170B
Opening image file: ESP32_GENERIC-20230426-v1.20.0-OTA.bin...
Chip type: esp32
Flash size: 4MB
Micropython App size: 0x16d740 bytes (1,461 KB)
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x5000     0xe000  0x0  (20.0 kB)
  otadata          data     ota          0xe000     0x2000    0x10000  0x0   (8.0 kB)
  ota_0            app      ota_0       0x10000   0x180000   0x190000  0x0   (1.5 MB)
  ota_1            app      ota_1      0x190000   0x180000   0x310000  0x0   (1.5 MB)
  vfs              data     fat        0x310000    0xf0000   0x400000  0x0   (0.9 MB)
Micropython app fills 95.2% of ota_0 partition (74 kB unused)
Filesystem partition "vfs" is 0.9 MB.
Writing output file: ESP32_GENERIC-20230426-v1.20.0-OTA-APP=0x170B.bin...
Partition table (flash size: 4MB):
# Name             Type     SubType      Offset       Size      (End)  Flags
  nvs              data     nvs          0x9000     0x5000     0xe000  0x0  (20.0 kB)
  otadata          data     ota          0xe000     0x2000    0x10000  0x0   (8.0 kB)
  ota_0            app      ota_0       0x10000   0x170000   0x180000  0x0   (1.4 MB)
  ota_1            app      ota_1      0x180000   0x170000   0x2f0000  0x0   (1.4 MB)
  vfs              data     fat        0x2f0000   0x110000   0x400000  0x0   (1.1 MB)
Micropython app fills 99.3% of ota_0 partition (10 kB unused)
Filesystem partition "vfs" is 1.1 MB.
```
