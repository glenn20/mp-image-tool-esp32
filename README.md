# mp-image-tool-esp32
Tool for manipulating MicroPython esp32 image files.


`mp-image-tool-esp32` will create a copy of the provided firmware file with the partition table modified according to the options provided. 
If no options are given, it will print the partition table of `filename`.

## Usage
```
usage: mp-image-tool-esp32.py [-h] [-q] [-n] [-d] [-o] [-x] [-f FLASH_SIZE] [-a APP_SIZE]
                              [-r RESIZE]
                              filename
```
### positional arguments:
```
  filename              the esp32 image file name
```
### options:
```
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
