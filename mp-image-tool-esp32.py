#!/usr/bin/env python3

# MIT License: Copyright (c) 2023 @glenn20

import sys
import mp_image_tool_esp32.main


def main() -> int:
    return mp_image_tool_esp32.main.main()


if __name__ == "__main__":
    sys.exit(main())
