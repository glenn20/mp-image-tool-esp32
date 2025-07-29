# Changelog

## What's Changed  ([unreleased])

- Add initial CHANGELOG.md file.- ([42b6915])
- Add the `py.typed` file to indicate that the package is typed.- ([519aec7])
- pyproject.toml: Add `tox-gh` config for github actions.- ([dfb811c])
- Update the CI workflow to use v2 of my python-ci workflows.- ([cd27bfd])
- ci: Update pre-commit config to optimise for post hooks.- ([95783aa])
- ci: README.md: Fix links to GitHub Actions workflow badges.- ([cbe52be])

[unreleased]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.1.1..HEAD
[42b6915]: https://github.com/glenn20/mp-image-tool-esp32/commit/42b6915b50d5a6b38e60aa182f01a1aba416101a
[519aec7]: https://github.com/glenn20/mp-image-tool-esp32/commit/519aec7f5e867c8349467ab42f5754520513adf2
[dfb811c]: https://github.com/glenn20/mp-image-tool-esp32/commit/dfb811c5951ad1ded566ad53ba3b2fb2f3d50544
[cd27bfd]: https://github.com/glenn20/mp-image-tool-esp32/commit/cd27bfd55be249426ef1e52f6c63ad8d274b86c1
[95783aa]: https://github.com/glenn20/mp-image-tool-esp32/commit/95783aadf5e54214d81a3125ccd39afb6352f540
[cbe52be]: https://github.com/glenn20/mp-image-tool-esp32/commit/cbe52bec8cc57c5303d828954b033b8c4c468cff

## What's Changed  in [v0.1.1]

- Drop support for python 3.8.- ([b42676f])
- Update README.md for the --rename option.- ([7444e5c])

[v0.1.1]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.1.0..v0.1.1
[b42676f]: https://github.com/glenn20/mp-image-tool-esp32/commit/b42676f2e5de3ca883a7e443a724808b96d5b765
[7444e5c]: https://github.com/glenn20/mp-image-tool-esp32/commit/7444e5cfa9ecdd1c632bb12bceea9938007999e8

## What's Changed  in [v0.1.0]

- feature: Add --rename option to rename partitions.- ([f2fd5f1]) - Closes [#5]

[v0.1.0]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.15..v0.1.0
[f2fd5f1]: https://github.com/glenn20/mp-image-tool-esp32/commit/f2fd5f18a33f1530fb29200529bba10746e4aba7
[#5]: https://github.com/glenn20/mp-image-tool-esp32/issues/5

## What's Changed  in [v0.0.15]

- Bugfix: firmware.py: Trap exceptions when calling `check_image_hash()`.- ([993f5bb])
- Tests: Bugfix test_fs.py to sort file lists before comparison.- ([1ac1ac9])
- pyproject.toml: Updates to improve clarity and maintainability.- ([6d616c0])
- Fix: Updates for type checking in tests/.- ([c7e6e93])
- README.md: Minor update clarifying use of `fs` command.- ([5ffeb30])
- Refactor: Minor refactor and fixups for typos.- ([42e6c22])
- Add pre-commit configuration file and update dependencies.- ([f7e97e5])
- docs: Add note about --fs swallowing non-option arguments.- ([b7aa945]) - Closes [#6]

[v0.0.15]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.14..v0.0.15
[993f5bb]: https://github.com/glenn20/mp-image-tool-esp32/commit/993f5bb5cec775743df7b121608f5c05fa8a4f5d
[1ac1ac9]: https://github.com/glenn20/mp-image-tool-esp32/commit/1ac1ac97474159e5999ed64831a263b02b7fe3fa
[6d616c0]: https://github.com/glenn20/mp-image-tool-esp32/commit/6d616c0742c3a0fcdf4d344a0a84f7c228f885ea
[c7e6e93]: https://github.com/glenn20/mp-image-tool-esp32/commit/c7e6e938bc8898c952a639b9dbaae54d0a41b5b3
[5ffeb30]: https://github.com/glenn20/mp-image-tool-esp32/commit/5ffeb300c65d781d09ae7b5a5387e2d929f4da1b
[42e6c22]: https://github.com/glenn20/mp-image-tool-esp32/commit/42e6c229e469e27348f7399d8aae4b34240dc937
[f7e97e5]: https://github.com/glenn20/mp-image-tool-esp32/commit/f7e97e5da8bce8e80136786b9ed5bc98f73edf8b
[b7aa945]: https://github.com/glenn20/mp-image-tool-esp32/commit/b7aa94500383846a799aafcb9d4173aa4270c023
[#6]: https://github.com/glenn20/mp-image-tool-esp32/issues/6

## What's Changed  in [v0.0.14]

- README.md: Add CI status badge.- ([9234997])
- README.md: Update the Examples to version 0.0.13- ([6dfc8ca])
- publish.yaml: Update comments.- ([ec1bab2])
- README.md: More update for newest version- ([cf18cdd])
- Minor formatting updates for ruff v0.9.- ([478d9ec])
- Make littlefs an optional dependency.- ([a955707])

[v0.0.14]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.13.dev2..v0.0.14
[9234997]: https://github.com/glenn20/mp-image-tool-esp32/commit/9234997acd745f4868a4359e6da8de7e5adc288f
[6dfc8ca]: https://github.com/glenn20/mp-image-tool-esp32/commit/6dfc8ca97fc6ee94d805c06c28abbb6e77e54ac9
[ec1bab2]: https://github.com/glenn20/mp-image-tool-esp32/commit/ec1bab29e79b92d44ba26f9346a9ef019c0bfd6c
[cf18cdd]: https://github.com/glenn20/mp-image-tool-esp32/commit/cf18cdd518accf0b2ffd924eed4bde2ce157ae30
[478d9ec]: https://github.com/glenn20/mp-image-tool-esp32/commit/478d9ec1fc42b26ded7bf946a25a3d563c0c1bc4
[a955707]: https://github.com/glenn20/mp-image-tool-esp32/commit/a9557079a639a00d7aabfc15c228f42ca06d5139

## What's Changed  in [v0.0.13.dev2]

- README.md: Update installation instructions.- ([bdc5571])
- Updates to github CI workflows. Use `python-ci` v1.- ([4512f65])

[v0.0.13.dev2]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.12..v0.0.13.dev2
[bdc5571]: https://github.com/glenn20/mp-image-tool-esp32/commit/bdc55710c4e6ea308a0fbb47f146ba10058e1d66
[4512f65]: https://github.com/glenn20/mp-image-tool-esp32/commit/4512f6567af782d34ea858bfba4250420e50d111

## What's Changed  in [v0.0.12]

- ci-release: fix for broken pypi upload.- ([6ef1ba9])

[v0.0.12]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.11..v0.0.12
[6ef1ba9]: https://github.com/glenn20/mp-image-tool-esp32/commit/6ef1ba9ae53b84581a977f65d40271ed3f0352ab

## What's Changed  in [v0.0.11]

- Move the build job out of the publish job into the ci-release job.- ([e36c86b])
- Make the ci-release workflow depend on the tests workflow.- ([7a0929c])

[v0.0.11]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.10..v0.0.11
[e36c86b]: https://github.com/glenn20/mp-image-tool-esp32/commit/e36c86bfc13cf382d2383b3625f1124e656ef4ee
[7a0929c]: https://github.com/glenn20/mp-image-tool-esp32/commit/7a0929cfeb48b336d163832a2935a03feba37b26

## What's Changed  in [v0.0.10]

- Enable publishing to pypi on tag.- ([9b1a6b3])

[v0.0.10]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.9..v0.0.10
[9b1a6b3]: https://github.com/glenn20/mp-image-tool-esp32/commit/9b1a6b36e0876dab231ca588618c26d8537ec2e1

## What's Changed  in [v0.0.9]

- Dummy push to trigger build- ([c958461])
- Move tox configuration to pyproject.toml.- ([a3d4722])
- Replace github action workflows from glenn20/python-ci.- ([0bfebc7])
- Add typing stubs for littlefs module.- ([c0c751b])
- Remove littlefs-python source folder from uv.lock and pyproject.toml.- ([6eaf2c1])
- pyproject.toml: Format comments.- ([7348864])

[v0.0.9]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.8..v0.0.9
[c958461]: https://github.com/glenn20/mp-image-tool-esp32/commit/c95846174d75d8ca883a653a94a71d187058a673
[a3d4722]: https://github.com/glenn20/mp-image-tool-esp32/commit/a3d47227f6588116124baeaf871e8272e4d45929
[0bfebc7]: https://github.com/glenn20/mp-image-tool-esp32/commit/0bfebc7e9fa4db4cecf04957405028ebad9efd67
[c0c751b]: https://github.com/glenn20/mp-image-tool-esp32/commit/c0c751be6d000ff55f2c27e01c1ef96b18e82a12
[6eaf2c1]: https://github.com/glenn20/mp-image-tool-esp32/commit/6eaf2c1ed2580cb39e623e4a0c6f4b54401db0b3
[7348864]: https://github.com/glenn20/mp-image-tool-esp32/commit/73488640b8502b0183e59ab4371644170fd0c18c

## What's Changed  in [v0.0.8]

- Overhaul logging to use the rich module.- ([e72e301])
- mypy: Fixes for mypy type checking.- ([887feda])
- Print partition tables using `Tables` from the `rich` module.- ([b6666e8])
- esptool_io: Replace tqdm with rich progress bar.- ([16d6d85])
- argtypes: Fix IntArg to handle float values, eg: --baud 1.5M- ([7306f90])
- esptool_io: Refactor progress bar handling to a separate module.- ([e39b471])
- Update project configuration: pyproject.toml and tox.ini.- ([a5a3887])
- Add build and publish CI workflows.- ([4180f04])
- Fixing issues on Windows.- ([6053e33])
- tests: Fixes for Windows.- ([312c417])
- CI: Try to build on tag pushes.- ([b96ff51])

[v0.0.8]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.7..v0.0.8
[e72e301]: https://github.com/glenn20/mp-image-tool-esp32/commit/e72e301cc036456debf0a796d0008263615b95d9
[887feda]: https://github.com/glenn20/mp-image-tool-esp32/commit/887fedaa334ff056ff11017f3a96680d61c8da20
[b6666e8]: https://github.com/glenn20/mp-image-tool-esp32/commit/b6666e8f06e054d1095726fe85b0dcb72fe4db8c
[16d6d85]: https://github.com/glenn20/mp-image-tool-esp32/commit/16d6d853f1b066b2fe2a9db3e0cbff31e7753a08
[7306f90]: https://github.com/glenn20/mp-image-tool-esp32/commit/7306f90deb5c87635cb0ee5d594cbf45001ca4e4
[e39b471]: https://github.com/glenn20/mp-image-tool-esp32/commit/e39b471c5d715dd06012b2d61a15d3307c8cdec8
[a5a3887]: https://github.com/glenn20/mp-image-tool-esp32/commit/a5a388795f59a186e21b27c0cac66eb3d051ca28
[4180f04]: https://github.com/glenn20/mp-image-tool-esp32/commit/4180f04e4f2b931f62f4f98bfc2d6de004621720
[6053e33]: https://github.com/glenn20/mp-image-tool-esp32/commit/6053e33d47f26ce538eaeacb4d9cd7332cbfdd21
[312c417]: https://github.com/glenn20/mp-image-tool-esp32/commit/312c417f2893d7a6695a3617d05c3de0d8593b71
[b96ff51]: https://github.com/glenn20/mp-image-tool-esp32/commit/b96ff51a8041af8c13ec8b9e32f319187b14d2e5

## What's Changed  in [v0.0.7]

- typings: Rename esptool.__init__.py to esptool.__init__.pyi.- ([386f378])
- tests: Add simple tests for the --fs filesystem operations.- ([32aae01])
- main: --fs commands can be repeated on the cli.- ([63fd491])
- lfs.py: Add BlockCache class for caching block reads and writes.- ([3eb4128])
- pyproject.toml: Add more-itertools dependency.- ([b85fa1e])
- main.py, lfs.py: Make type hints compatible with python 3.8.- ([4cba1a5])
- tox.ini: remove uv run from pytest command.- ([c07c75c])
- main.py: Give -q priority over -d.- ([67e6256])
- tests: Add README.md for the tests directory.- ([eddbbb6])
- partition_table: Rename make_table() to format_table().- ([6c070c8])
- firmware.py: Don't erase fs partitions if resizing to larger.- ([8e5a92c])
- lfs: Add the "--fs grow" to resize littlefs filesystems.- ([8de0f3f])
- README.md: Add note about filesystem partition resizing.- ([d6e9627])
- tests: Run mp_image_tool_esp32 as a module rather than a script.- ([7de5564])

[v0.0.7]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.6..v0.0.7
[386f378]: https://github.com/glenn20/mp-image-tool-esp32/commit/386f378c9a5be05392323dd60c45cb5a3ad4b51e
[32aae01]: https://github.com/glenn20/mp-image-tool-esp32/commit/32aae012df436a6290f8b81ee90c97b01d1d3d00
[63fd491]: https://github.com/glenn20/mp-image-tool-esp32/commit/63fd491ce6599f2865e5b430df68a7425d470876
[3eb4128]: https://github.com/glenn20/mp-image-tool-esp32/commit/3eb41283ba36d2498c2b7bd518aff64cbf865cf1
[b85fa1e]: https://github.com/glenn20/mp-image-tool-esp32/commit/b85fa1e690a306e4d721b1690a0d8423fe70d860
[4cba1a5]: https://github.com/glenn20/mp-image-tool-esp32/commit/4cba1a50325dc5546fb167a75b6a005fb879c3fd
[c07c75c]: https://github.com/glenn20/mp-image-tool-esp32/commit/c07c75c6d5ecc79fcbfc9f77951dccfd8e6ae044
[67e6256]: https://github.com/glenn20/mp-image-tool-esp32/commit/67e6256f843f1922bfaf0c10da306c1d52dc075d
[eddbbb6]: https://github.com/glenn20/mp-image-tool-esp32/commit/eddbbb6dc590bca577a3eb91d93d56144de2d705
[6c070c8]: https://github.com/glenn20/mp-image-tool-esp32/commit/6c070c8e6a504fd272356255f32ec058cbcf6814
[8e5a92c]: https://github.com/glenn20/mp-image-tool-esp32/commit/8e5a92cf8a71b1020d8699452113b8b310bb3042
[8de0f3f]: https://github.com/glenn20/mp-image-tool-esp32/commit/8de0f3ffc7331098630473bebc2245ac129e7361
[d6e9627]: https://github.com/glenn20/mp-image-tool-esp32/commit/d6e96276ee2db99eebbbf6d3752330e1a4e9e5fa
[7de5564]: https://github.com/glenn20/mp-image-tool-esp32/commit/7de5564d5ea611290f3f2df6ff5b1456221fa96b

## What's Changed  in [v0.0.6]

- layouts.py: Add the 'original' partition table layout.- ([f09935f])
- Bugfix: Fix esptool method selection.- ([2882e73])
- Add optional 'check' parameter to FirmwareFile and FirmwareDevice constructors.- ([5dedec4])
- tests: Update test scripts and fixtures- ([b5e5511])
- tests: Remove ESP32 firmware files from repo.- ([09ebec5])
- gitignore: Ignore /tests/data directory.- ([be7e21b])
- tests: Refactor and clean up of fixtures and- ([7d6019f])
- tests: Bugfix for run-tests.sh script.- ([5dae320])
- esptool_io: Minor refactor.- ([6f8e296])
- Refactor: Rename image_file.py->firmware.py, firmware_file.py->firmware_fileio.py.- ([e250c72])
- esptool_io: Use the Buffer protocol for write_flash().- ([d2af347])
- tests: Add flash_size tests.- ([e150ef0])
- argparse_typed: Add support for capturing types from the global namespace.- ([0364dfc])
- firmware-fileio: Add Partition class to read/write partition contents.- ([689f6bd])
- Use the new Partition class for reading/writing partitions.- ([bf483f2])
- image-header: Add sanity check when calculating image size.- ([db9cc25])
- partition_table: Catch PartitionErrors when loading an existing partition.- ([3803517])
- tests: Add tests for file integrity and read/write operations.- ([0957c3a])
- firmware_fileio: Add Partition.truncate() method.- ([a3cc794])
- main: --flash-size raise an error if size is larger than device flash size.- ([451caf8])
- .gitignore: Ignore .python_version files.- ([d1c3eb4])
- ota_update: Use new `Partition` context manager to write to partitions.- ([291f168])
- argtypes: Make ArgList and PartList concrete classes.- ([3c8eec6])
- pyproject.toml: Use uv for env and dependencies management.- ([c462d22])
- Add tox support for running tests.- ([413695a])
- run-tests.sh: Use 'uv' to run tests for multiple Python versions.- ([58844a2])
- tests: Change --device option to --port in conftest.py.- ([19acaf9])
- pyproject.toml: Add tox to dev-dependencies.- ([70e8d28])
- pyproject.toml: Use hatch-vcs to set __version__ from git tags.- ([e8c395c])
- .gitignore: Ignore requirements.txt file.- ([d630118])
- README.md: Update installation instructions (use `uv`).- ([afdecd8])
- FirmwareDeviceIO: Remove chip_name and flash_size attributes.- ([ffd78ec])
- argtypes: Remove unsplit(), add __str__() to ArgList and PartList.- ([2fe9762])
- Replace OSError with ValueError in firmware_fileio.py.- ([26b2fe7])
- Add --trim and --trimblocks options to mp_image_tool_esp32.- ([2e814f4])
- firmware.py: Add "partition_table" as a fake partition name.- ([2049e45])
- ImageHeader: Rename check() method to validate().- ([9897380])
- Firmware: Make `table` an attribute instead of a cached property.- ([0627a58])
- Tiny refactoring in the _get_part method of the Firmware class.- ([c491c41])
- argparse_typed: Add support for variable number of arguments.- ([9310887])
- Firmware: Make `size` an attribute instead of a cached_property.- ([49942cc])
- logger: Don't use the root logger.- ([8760de8])
- Add --fs option to manipulate files on littlefs filesystems.- ([11bb984])
- pyproject.toml: Add littlefs-python to dependencies.- ([3b50e6e])

[v0.0.6]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.5..v0.0.6
[f09935f]: https://github.com/glenn20/mp-image-tool-esp32/commit/f09935f0c989c653fe0d75ad900b81132a476c47
[2882e73]: https://github.com/glenn20/mp-image-tool-esp32/commit/2882e73f60cafc3aca8359ab6e342f2e48424f58
[5dedec4]: https://github.com/glenn20/mp-image-tool-esp32/commit/5dedec4d813b11d1ec9c0f43d2901140e7968666
[b5e5511]: https://github.com/glenn20/mp-image-tool-esp32/commit/b5e5511eb9dd8af8f664e6a068f198ed67a8c230
[09ebec5]: https://github.com/glenn20/mp-image-tool-esp32/commit/09ebec5e59cf1c451950173dcd3b76da4487291e
[be7e21b]: https://github.com/glenn20/mp-image-tool-esp32/commit/be7e21b6bba2796f7d681379a9440059d6f2605a
[7d6019f]: https://github.com/glenn20/mp-image-tool-esp32/commit/7d6019f179276abe32b44359c92d1b6f35ea6f1c
[5dae320]: https://github.com/glenn20/mp-image-tool-esp32/commit/5dae3205e131e840801da6c92ef825fdd069dae3
[6f8e296]: https://github.com/glenn20/mp-image-tool-esp32/commit/6f8e296a19ac72b2992fa8ea6e9d3e31a53a144c
[e250c72]: https://github.com/glenn20/mp-image-tool-esp32/commit/e250c7251da49dd085759faf6dc1320d9220e5c2
[d2af347]: https://github.com/glenn20/mp-image-tool-esp32/commit/d2af347af61b772d7f49397abf4b113601c87e2c
[e150ef0]: https://github.com/glenn20/mp-image-tool-esp32/commit/e150ef05fc845f1cc2b99927b2ef143f288116e7
[0364dfc]: https://github.com/glenn20/mp-image-tool-esp32/commit/0364dfc31e655be162de71b6cb71be25d7f1c48c
[689f6bd]: https://github.com/glenn20/mp-image-tool-esp32/commit/689f6bd1965ded90fc5cf8abde3fc4263431ab4c
[bf483f2]: https://github.com/glenn20/mp-image-tool-esp32/commit/bf483f2abbb35bea286232a629e90a9ee51cccd6
[db9cc25]: https://github.com/glenn20/mp-image-tool-esp32/commit/db9cc25f38db53fb7e96e6de4bae2406dbf0f5e8
[3803517]: https://github.com/glenn20/mp-image-tool-esp32/commit/38035170a44a8f55cda90d9d4335be023b1ab745
[0957c3a]: https://github.com/glenn20/mp-image-tool-esp32/commit/0957c3a13d2136d4ee9a2e6413b4b7e587136e46
[a3cc794]: https://github.com/glenn20/mp-image-tool-esp32/commit/a3cc794bdf071fdac51f97a1f0ca342d6a4912a5
[451caf8]: https://github.com/glenn20/mp-image-tool-esp32/commit/451caf8f238438a1a96223155004947127e7d38e
[d1c3eb4]: https://github.com/glenn20/mp-image-tool-esp32/commit/d1c3eb465ece398840a5350990bad1f2ef7daa5f
[291f168]: https://github.com/glenn20/mp-image-tool-esp32/commit/291f16808f0350378c9c44170ed2d172a042e88b
[3c8eec6]: https://github.com/glenn20/mp-image-tool-esp32/commit/3c8eec6a5c64e869dea5292020a4cd29df10c774
[c462d22]: https://github.com/glenn20/mp-image-tool-esp32/commit/c462d2236bfe1b6e2af153deaf7628fa2aa81460
[413695a]: https://github.com/glenn20/mp-image-tool-esp32/commit/413695ac65fd03930fb5bb7364c1184006fe4db6
[58844a2]: https://github.com/glenn20/mp-image-tool-esp32/commit/58844a26ac4f6461301ed5fa49f7d8d36fd415b1
[19acaf9]: https://github.com/glenn20/mp-image-tool-esp32/commit/19acaf9b5de3a35bc2666821c9cc3ed82a83d645
[70e8d28]: https://github.com/glenn20/mp-image-tool-esp32/commit/70e8d28ba3bae739418975bd0b5ba4f507546d42
[e8c395c]: https://github.com/glenn20/mp-image-tool-esp32/commit/e8c395cdf575266ed8e584ce0594e5c526d79577
[d630118]: https://github.com/glenn20/mp-image-tool-esp32/commit/d6301184a7001a17552add55373316df1ac380ef
[afdecd8]: https://github.com/glenn20/mp-image-tool-esp32/commit/afdecd837aaa666c10dc596cde822982adb91b9c
[ffd78ec]: https://github.com/glenn20/mp-image-tool-esp32/commit/ffd78ec5b5ac50b1c851faa14e7f23b7baeebd81
[2fe9762]: https://github.com/glenn20/mp-image-tool-esp32/commit/2fe97621567ca63b70d416dcc53ed5f0e8c7ef0e
[26b2fe7]: https://github.com/glenn20/mp-image-tool-esp32/commit/26b2fe78a1bf28066c871eec6b69aa3f9471038e
[2e814f4]: https://github.com/glenn20/mp-image-tool-esp32/commit/2e814f4b1541cd8c505f586b8f02796c441611b5
[2049e45]: https://github.com/glenn20/mp-image-tool-esp32/commit/2049e459db2c9350b8c2dfd5c12008a1f9980982
[9897380]: https://github.com/glenn20/mp-image-tool-esp32/commit/9897380d6a039d44380448e18239073fa34c280a
[0627a58]: https://github.com/glenn20/mp-image-tool-esp32/commit/0627a58b39eca86c9b58008407d372abb5c0696f
[c491c41]: https://github.com/glenn20/mp-image-tool-esp32/commit/c491c41e0161cbe3d8261321a96696da783a9f56
[9310887]: https://github.com/glenn20/mp-image-tool-esp32/commit/931088755ed6279ae9a597f9e305aa99d66efc29
[49942cc]: https://github.com/glenn20/mp-image-tool-esp32/commit/49942cc1b4ec101e3755357721531e0f121190f4
[8760de8]: https://github.com/glenn20/mp-image-tool-esp32/commit/8760de8eacf1bd44370ad3ebaf1240c5df547eae
[11bb984]: https://github.com/glenn20/mp-image-tool-esp32/commit/11bb984098ad04e969512a4e3cb7b53901f2d743
[3b50e6e]: https://github.com/glenn20/mp-image-tool-esp32/commit/3b50e6eced48f22b79bccf5583835d96b9c35cdc

## What's Changed  in [v0.0.5]

- Be more explicit about what is happening when leaving bootloader mode.- ([c3b81b3])
- Use EspToolWrapper class to handle esptool.py commands.- ([2ab4d8c])
- Bugfix: handle ValueError when parsing image header.- ([b2a0ac0])
- Avoid opening and initialising the device for each operation.- ([a04f4e1])
- Add typings stubs for the esptool modules.- ([8916a03])
- Remove "-" from the delimiter list in argtypes.py.- ([6c9210c])
- Remove write_part_from_file() and read_part_to_file() methods.- ([72ffae1])
- Major refactor of the ESP32 device I/O modules and classes.- ([9d8e441])
- Rename ImageFormat class to ImageHeader.- ([3be5ac7])
- Add typing-extensions to requirements.txt (for `Buffer`).- ([f5135ee])
- More refactoring of the ESP32 device IO modules.- ([0ee9fd1])
- image_header.py: Use ctypes for ImageHeader structure.- ([7b76834])
- esptool_io: Show esptool.py output for longer writes.- ([698859f])
- Bugfix: firmware_file: Correct logic for reset_on_close.- ([3585215])
- image_header: Add `check_image_hash` function to verify image hash.- ([59caa02])
- Support flashing the output firmware to a serial-attached device.- ([c9c5777])
- esptool_io: Rename esptool_wrapper() to get_esptool().- ([8ea03b6])
- partition_table: Rename `flash_size` to `max_size` in PartitionTable.- ([0be9ec7])
- Add README.md to typings/esptool.- ([5ba73b7])
- Rename --check to --check-app options to clarify the purpose.- ([c62fedc])
- Update README.md with new options and examples.- ([a9ae3d4])
- Remove the `app_size` attribute from the `Esp32Image` and `PartitionTable`- ([0e6fbe9])
- Add --flash command to flash firmware to a device.- ([fb8ab6f])
- esptool_io: Add --flash_frequency=keep to esptool args.- ([8a56583])
- More helpful error msg when OTA app part is too small.- ([73cdbc1])
- Use `print (table)` insted of `table.print()`.- ([7ce7549])
- Logging: add new logging messages and refine existing.- ([324d16f])
- main.py: Tweaks to the top-level exception catching.- ([0de9039])
- image_header.py: Tweaks to the printing of ctypes structures.- ([c896418])
- firmware_file: Use the detected flash size if it is different to the flash size in the bootloader header.- ([3592387])
- esptool_io.py: Add ESPToolProgressBar class for monitoring esptool.py progress.- ([ffd126a])
- Minor update to README.md.- ([3403549])
- logger.py: Log messages to stdout not stderr.- ([d0fc27e])
- main.py: Exit after --extract-app option.- ([0d5a0bd])
- main.py: Force an output file when --erase or --write options are used.- ([9d0a1a5])
- layouts.py: Raise PartitionError if app is to large for partition.- ([1400335])
- image-file.py: --check-app logs to INFO, not ACTION.- ([bccff34])
- tests: Add tests for operations on firmware files.- ([954ccc0])
- esptool_io.py: Minor renaming.- ([13abb4f])
- Increment version number to 0.0.5.- ([0619fcb])

[v0.0.5]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.4..v0.0.5
[c3b81b3]: https://github.com/glenn20/mp-image-tool-esp32/commit/c3b81b3c3d03e0a5f55f89068adf9cef39faa9d2
[2ab4d8c]: https://github.com/glenn20/mp-image-tool-esp32/commit/2ab4d8c613f42d6f7c3edc28ca0c9a55d39b48f4
[b2a0ac0]: https://github.com/glenn20/mp-image-tool-esp32/commit/b2a0ac08556fd28518f4b3a890fb0a4cd8cda316
[a04f4e1]: https://github.com/glenn20/mp-image-tool-esp32/commit/a04f4e1e3c4a58c60d6686cab3603eae85ae07aa
[8916a03]: https://github.com/glenn20/mp-image-tool-esp32/commit/8916a03937057b08e5f91706ae64eb11d9fe6980
[6c9210c]: https://github.com/glenn20/mp-image-tool-esp32/commit/6c9210ccd50c729df3afda7c891623265a2e6b28
[72ffae1]: https://github.com/glenn20/mp-image-tool-esp32/commit/72ffae1937463bab22657fc9068ce824fce91d76
[9d8e441]: https://github.com/glenn20/mp-image-tool-esp32/commit/9d8e441d08eb1dd649d020fb1b2540240b0d1562
[3be5ac7]: https://github.com/glenn20/mp-image-tool-esp32/commit/3be5ac75b8e681c81f4e6b653738ab46a7fbc981
[f5135ee]: https://github.com/glenn20/mp-image-tool-esp32/commit/f5135ee661a3b9a6b02da7b5637bc6f2c91e496b
[0ee9fd1]: https://github.com/glenn20/mp-image-tool-esp32/commit/0ee9fd1dcc1c73a0545ff6addaac75e383c568c7
[7b76834]: https://github.com/glenn20/mp-image-tool-esp32/commit/7b768348d2369fb2113e154b89b84aa73809b84a
[698859f]: https://github.com/glenn20/mp-image-tool-esp32/commit/698859fa9af638e15b7bbf89aa93c4fc8916f933
[3585215]: https://github.com/glenn20/mp-image-tool-esp32/commit/358521503b3e17f7c33ff0e88e6ede546622d15e
[59caa02]: https://github.com/glenn20/mp-image-tool-esp32/commit/59caa02098175d79630caed2a5317438c6068d59
[c9c5777]: https://github.com/glenn20/mp-image-tool-esp32/commit/c9c5777c5311b07e293153c3d4297e54afbed651
[8ea03b6]: https://github.com/glenn20/mp-image-tool-esp32/commit/8ea03b6476ca418b84a9ece56dcf2f4209748b07
[0be9ec7]: https://github.com/glenn20/mp-image-tool-esp32/commit/0be9ec78d494ca6d98742d3a932b0f3b94dad5e1
[5ba73b7]: https://github.com/glenn20/mp-image-tool-esp32/commit/5ba73b7999a5c205ed81331b3bd7b40de5c3cb6d
[c62fedc]: https://github.com/glenn20/mp-image-tool-esp32/commit/c62fedc4fc8b1487cd1b4009fa8d973b99d3d2dd
[a9ae3d4]: https://github.com/glenn20/mp-image-tool-esp32/commit/a9ae3d4ed43315b8ee33109513e02abf56a1fc58
[0e6fbe9]: https://github.com/glenn20/mp-image-tool-esp32/commit/0e6fbe91b5a89e6aabc1311e0eaea3b8c6a3bde0
[fb8ab6f]: https://github.com/glenn20/mp-image-tool-esp32/commit/fb8ab6f810a34cc7da6b9b2e02b876865e2712ef
[8a56583]: https://github.com/glenn20/mp-image-tool-esp32/commit/8a565830a64914392e29b0b65487739453317331
[73cdbc1]: https://github.com/glenn20/mp-image-tool-esp32/commit/73cdbc172efaf538361dc39aef86ae24e27414f1
[7ce7549]: https://github.com/glenn20/mp-image-tool-esp32/commit/7ce7549146bed96a09cf8e6082a58cc5e54530be
[324d16f]: https://github.com/glenn20/mp-image-tool-esp32/commit/324d16fa70bc5991567cf0d33912a17a05ef6008
[0de9039]: https://github.com/glenn20/mp-image-tool-esp32/commit/0de90390838c9345408f104bf8fd5f9d584b669e
[c896418]: https://github.com/glenn20/mp-image-tool-esp32/commit/c896418334f9c905efc51dd58f083513d56b1866
[3592387]: https://github.com/glenn20/mp-image-tool-esp32/commit/3592387ff5e7b5332345738c6cab4056239d5cc8
[ffd126a]: https://github.com/glenn20/mp-image-tool-esp32/commit/ffd126abe9e3c9c96394034cc1460365c24db9f1
[3403549]: https://github.com/glenn20/mp-image-tool-esp32/commit/3403549d3aee2217d9ace4a89894fa8371cf58af
[d0fc27e]: https://github.com/glenn20/mp-image-tool-esp32/commit/d0fc27e6fda6b76bd2bced28529192772b1f4d7a
[0d5a0bd]: https://github.com/glenn20/mp-image-tool-esp32/commit/0d5a0bdf3842d2134a5c44f6ef9ff32f71b1b15c
[9d0a1a5]: https://github.com/glenn20/mp-image-tool-esp32/commit/9d0a1a587964ccda0323b86efbdc22f9751bbfc4
[1400335]: https://github.com/glenn20/mp-image-tool-esp32/commit/1400335f934d35ae1c1776af386b5035c4f723cd
[bccff34]: https://github.com/glenn20/mp-image-tool-esp32/commit/bccff34ee1b27c631496fa40a9b7a27368537325
[954ccc0]: https://github.com/glenn20/mp-image-tool-esp32/commit/954ccc0291af8829e6d5b9f994c0dfacadfce123
[13abb4f]: https://github.com/glenn20/mp-image-tool-esp32/commit/13abb4fe467792f8c2caab753738d0bf01f7bd4d
[0619fcb]: https://github.com/glenn20/mp-image-tool-esp32/commit/0619fcb01333888dbb1cb5bbdf76ad795e1f3dee

## What's Changed  in [v0.0.4]

- Update README.md for new option --no-reset (version 0.0.3).- ([bf4dda8])
- pares-args.py: Fix comparison with bool and str- ([a5539f4])
- Refactor of the `parse_args` module to `argparse_typed` and `argtypes` modules.- ([0a948b1])
- Refactor to use a logger module for all output messages.- ([09ab35f])
- logger.py: Remove dependence on colorlog.- ([eef119a])
- Minor refactor of the table.print() method.- ([1dab45e])
- PartitionTable: Refactor from_bytes method.- ([717779d])
- Minor logging updates.- ([48e8b78])
- Improve robustness of esptool subprocess handling.- ([c071e6e])
- Bump version number to 0.0.4.- ([9403b02])

[v0.0.4]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.3..v0.0.4
[bf4dda8]: https://github.com/glenn20/mp-image-tool-esp32/commit/bf4dda847e5c61eabc5c228a38117b49bf96bf69
[a5539f4]: https://github.com/glenn20/mp-image-tool-esp32/commit/a5539f47846fd43ad26b82ef6cb9aa677a18d8ae
[0a948b1]: https://github.com/glenn20/mp-image-tool-esp32/commit/0a948b12470f2b6b27e03da16126672ea10d942c
[09ab35f]: https://github.com/glenn20/mp-image-tool-esp32/commit/09ab35fb83369872afffb82ba4a8049bc9cd47dc
[eef119a]: https://github.com/glenn20/mp-image-tool-esp32/commit/eef119a8d694891e23ef99dab17b6515d3181741
[1dab45e]: https://github.com/glenn20/mp-image-tool-esp32/commit/1dab45eb96a9607e2d6d6d6fd6bf0a78bc4b9648
[717779d]: https://github.com/glenn20/mp-image-tool-esp32/commit/717779dd41492ed9e03eebdfb753c7e8cf328957
[48e8b78]: https://github.com/glenn20/mp-image-tool-esp32/commit/48e8b78fc5d935dc40c22e95859e2a4ad4841fb7
[c071e6e]: https://github.com/glenn20/mp-image-tool-esp32/commit/c071e6e9410f4ba0768770aa03f6d4e56c90f901
[9403b02]: https://github.com/glenn20/mp-image-tool-esp32/commit/9403b02c57e7443898c6108a50b578fa834019e4

## What's Changed  in [v0.0.3]

- ota_update.py: Minor refactoring.- ([8003c7e])
- image_device.py: Increase the minimum size for displaying the progress bar.- ([8d1ea4b])
- Bugfix: Recalculate bootloader hash when flash-size is changed.- ([33ac3bb])
- Add -n option to leave device in bootloader after exit.- ([3ca246b])
- Bump version to 0.0.3.- ([0db8a6f])

[v0.0.3]: https://github.com/glenn20/mp-image-tool-esp32/compare/v0.0.2..v0.0.3
[8003c7e]: https://github.com/glenn20/mp-image-tool-esp32/commit/8003c7ea29c45cac5e9050b6961dda09589c3313
[8d1ea4b]: https://github.com/glenn20/mp-image-tool-esp32/commit/8d1ea4bf632c32602178d9309c34c1376354d935
[33ac3bb]: https://github.com/glenn20/mp-image-tool-esp32/commit/33ac3bb60d094c8aaee66413eafb97652b12b690
[3ca246b]: https://github.com/glenn20/mp-image-tool-esp32/commit/3ca246b751321c382f479c8a4af636424ad69295
[0db8a6f]: https://github.com/glenn20/mp-image-tool-esp32/commit/0db8a6fafe2b293a312f87b0ae3e0586429d1410

## What's Changed  in [v0.0.2]

- Initial commit- ([7b772dc])
- Update README.md- ([fdd8adb])
- First checkin: working code.- ([d8a5f30])
- Minor ruff fixes.- ([a42bcb6])
- README.md: add --ota to feature list.- ([04dc8d6])
- Add pyproject.toml (uses hatchling).- ([0040916])
- README.md: Add installation instructions.- ([97132c1])
- Add support for esp32 device flash storage.- ([a1f1097])
- Drop "-o" alias for "--ota".- ([2be2466])
- Introduce ESP32Image class to represent an image file or device.- ([840227a])
- Add PartitionTable.by_name(name) method.- ([908e7a4])
- Add erase_flash_region() function.- ([53aff5c])
- main.py: Add the --erase-part and --erase-first-block arguments.- ([c214269])
- image_device.py: Add support for providing chip_name.- ([e3d3b98])
- Rename --erase-first-blocks to --erase-fs option.- ([e76575d])
- Update README.md.- ([834280b])
- Add --write-part and --read-part options.- ([f819953])
- Use @cached_propery for Part() properties.- ([bc98e7c])
- Add --from-csv option.- ([1825d12])
- Part: rename label_name property to name.- ([be6b823])
- Simplify PartTuple class.- ([5f85260])
- Use local parse_args module to simplify args processing.- ([600486d])
- Change rules for read_part and write_part arguments.- ([ff4e827])
- Add del_part and expand_part methods.- ([fb87086])
- Move mp_image_tool_esp32 folder into src/.- ([05c4688])
- Fixup for expand_part().- ([3b7534c])
- image_device.py: Handle reconnection problems on esp32s2.- ([d3c955a])
- image_file.py: Fix when input file is less than expected length.- ([7f08372])
- Add support for parsing progname and description.- ([ce6e84a])
- Allow table["name"] to return Part with label = "name".- ([5ada1b7])
- PartitionTable: Simplify .resize_part() and remove.by_name().- ([91a0719])
- Partitiontable: Remove .del_part(), .expand_part(), .resize_flash().- ([f1a27a3])
- Bugfix: Handle default offset in .add_part().- ([ed96377])
- Add support for printing table on PartError.- ([4bc1054])
- Add support for epilog in arguments string.- ([54613a3])
- add_part(): Don't check after adding each part.- ([d8fdb38])
- Add --table option.- ([ca8bcc7])
- image_device.py: Drop use of pathlib.- ([e9bbef8])
- Erase data partitions when changed.- ([a547888])
- print_table(): Don't print out vfs size.- ([3b52135])
- Add esptool to package requirements.txt.- ([c2ac35b])
- Allow multiple paragraphs in the epilog.- ([5f219bd])
- Streamline command argument processing.- ([a7eeba3])
- Correct flash_size in bootloader if it has changed.- ([7847a3a])
- API change: Replace --ota with "--table ota".- ([3cc36b8])
- Move "Resizing part" message to main.py.- ([24d1208])
- Add "--bootloader FILE" option.- ([428ff85])
- Refactor: Reorganise code.- ([b50543e])
- Cleanup open_image().- ([74335e6])
- Refactor: Argparse, strict type checking, minor re-org.- ([f0a45c4])
- Add docstrings everywhere...- ([8ec7d13])
- More refactoring and module docstrings.- ([b726946])
- Add support for OTA update over the serial/USB interface.- ([1b04a23])
- Minor Readme update.- ([4645671])
- README.md: Add instruction on cloning repo.- ([d40ada6])
- Print chip type and flash size sooner.- ([6379c83])
- Add progress bar when read/write from flash storage on esp32 devices.- ([558f90c])
- Replace --bootloader option with --read/write bootloader=FILE.- ([8597cda])
- Update README.md for removal of --bootloader option.- ([1f18477])
- Squashed commit from dev: Add --check option.- ([13f1bba])
- Allow --read, --write and --erase options to be used on firmware files.- ([608de82])
- Add support for python versions 3.8 and 3.9.- ([d357de7])
- Refactor of parse_args.py for clarity.- ([47a2b32])
- Require at least python 3 8.- ([75682ab])
- Use the newer type notation for python >= 3 10.- ([db5d77d])
- Fix PartitionErrors raised when changing the flash size.- ([268318e])
- Increment version number.- ([fc86ff2])

[v0.0.2]: https://github.com/glenn20/mp-image-tool-esp32/tree/v0.0.2
[7b772dc]: https://github.com/glenn20/mp-image-tool-esp32/commit/7b772dc29b5ba747391865c7331a0db8ba060f02
[fdd8adb]: https://github.com/glenn20/mp-image-tool-esp32/commit/fdd8adb50f6f9336bd5cc8def4aae347e364bf1e
[d8a5f30]: https://github.com/glenn20/mp-image-tool-esp32/commit/d8a5f3072352576f0b0bc227fac374a3e1453064
[a42bcb6]: https://github.com/glenn20/mp-image-tool-esp32/commit/a42bcb6ab63f2054cc32c2cc76b8c7ec3acef2d7
[04dc8d6]: https://github.com/glenn20/mp-image-tool-esp32/commit/04dc8d6d08e0d0eb35a2eae732919122c948313d
[0040916]: https://github.com/glenn20/mp-image-tool-esp32/commit/00409162bbbd46b86fe7eed59771bd8aaf33d0d4
[97132c1]: https://github.com/glenn20/mp-image-tool-esp32/commit/97132c188f9c90ef437c85695a4dc52440cac7d2
[a1f1097]: https://github.com/glenn20/mp-image-tool-esp32/commit/a1f1097bbe4c138211a4becc205f86460737a9ea
[2be2466]: https://github.com/glenn20/mp-image-tool-esp32/commit/2be2466521e0244b026d3b004f51429e99664dcf
[840227a]: https://github.com/glenn20/mp-image-tool-esp32/commit/840227a0c4d2974e1c8a56d3cdc4228007993e42
[908e7a4]: https://github.com/glenn20/mp-image-tool-esp32/commit/908e7a486a2b7d3f35a699b5b222287eeecef343
[53aff5c]: https://github.com/glenn20/mp-image-tool-esp32/commit/53aff5c34ccedd1a01fbfbd74aaa658c8456b068
[c214269]: https://github.com/glenn20/mp-image-tool-esp32/commit/c2142694b44f89b7014fd850c62524dd4272bc47
[e3d3b98]: https://github.com/glenn20/mp-image-tool-esp32/commit/e3d3b98796bb614da7571d6b099f975df21df601
[e76575d]: https://github.com/glenn20/mp-image-tool-esp32/commit/e76575de75f7ad655e6bac0968d7d16eb985d194
[834280b]: https://github.com/glenn20/mp-image-tool-esp32/commit/834280b531480823ade45d34da66a5dab35ae561
[f819953]: https://github.com/glenn20/mp-image-tool-esp32/commit/f819953c3714bc3ea220c00027e576da30701f81
[bc98e7c]: https://github.com/glenn20/mp-image-tool-esp32/commit/bc98e7cb7a9ea6662073491080b9bd7685288deb
[1825d12]: https://github.com/glenn20/mp-image-tool-esp32/commit/1825d12d75098ca535854d50b3449d48a520177f
[be6b823]: https://github.com/glenn20/mp-image-tool-esp32/commit/be6b8231614bf1389d848a36e17679e6d1be02ff
[5f85260]: https://github.com/glenn20/mp-image-tool-esp32/commit/5f85260887f73aa4b396d52ad630caa3fe47db1f
[600486d]: https://github.com/glenn20/mp-image-tool-esp32/commit/600486d2155a8cea801e2dc1541f93a7b71cd8a8
[ff4e827]: https://github.com/glenn20/mp-image-tool-esp32/commit/ff4e8276cd20535e304d1f545cae772183c3d4ee
[fb87086]: https://github.com/glenn20/mp-image-tool-esp32/commit/fb87086750c7243a3846b0d80f572ac20c4adbad
[05c4688]: https://github.com/glenn20/mp-image-tool-esp32/commit/05c468827b979bf8ce868829aaf6900c2ffa5963
[3b7534c]: https://github.com/glenn20/mp-image-tool-esp32/commit/3b7534c56f7bddf5c1aa620bda273363801134e0
[d3c955a]: https://github.com/glenn20/mp-image-tool-esp32/commit/d3c955af6f8c3eca8d794cf1c9989dbc04777f5c
[7f08372]: https://github.com/glenn20/mp-image-tool-esp32/commit/7f08372bcc02b745971c1614cb9900a3a4df5bc0
[ce6e84a]: https://github.com/glenn20/mp-image-tool-esp32/commit/ce6e84a9b081d70393503a6fc81b9e688a0cbe62
[5ada1b7]: https://github.com/glenn20/mp-image-tool-esp32/commit/5ada1b73e5a83e2031477d479a17ff986802d8ab
[91a0719]: https://github.com/glenn20/mp-image-tool-esp32/commit/91a0719e20ee2a8c41abbdccc9d1b14a79b8ab9d
[f1a27a3]: https://github.com/glenn20/mp-image-tool-esp32/commit/f1a27a333e867ce0b680874f2b8785dbc4a6b6b6
[ed96377]: https://github.com/glenn20/mp-image-tool-esp32/commit/ed96377d92e222e0c2d2c7e9c999d835c382e12f
[4bc1054]: https://github.com/glenn20/mp-image-tool-esp32/commit/4bc1054427aa172f1ec76ba79722b062a978e753
[54613a3]: https://github.com/glenn20/mp-image-tool-esp32/commit/54613a310c38195735bc9976789817a814e63bea
[d8fdb38]: https://github.com/glenn20/mp-image-tool-esp32/commit/d8fdb38a7a07368d062d6bc900c1bdd0632ebeee
[ca8bcc7]: https://github.com/glenn20/mp-image-tool-esp32/commit/ca8bcc78e179edf3ecd2ecca094fc74afc8448a1
[e9bbef8]: https://github.com/glenn20/mp-image-tool-esp32/commit/e9bbef849901e41c39bc30dc092ca5e8b398b7b3
[a547888]: https://github.com/glenn20/mp-image-tool-esp32/commit/a547888bc43b9240a6c826984bfeb8689910ad7b
[3b52135]: https://github.com/glenn20/mp-image-tool-esp32/commit/3b521358696229142eb9d069a0a603d4719b6b7f
[c2ac35b]: https://github.com/glenn20/mp-image-tool-esp32/commit/c2ac35bb9745eb6a7d995f521cf0b0454f192981
[5f219bd]: https://github.com/glenn20/mp-image-tool-esp32/commit/5f219bd1a3fb920ee1a516f3eefa59a9a5eabf98
[a7eeba3]: https://github.com/glenn20/mp-image-tool-esp32/commit/a7eeba366474f227acb269031e0a6c80ba0af126
[7847a3a]: https://github.com/glenn20/mp-image-tool-esp32/commit/7847a3afd1c7c6125bce20ddb0ea6c22d1cc8c62
[3cc36b8]: https://github.com/glenn20/mp-image-tool-esp32/commit/3cc36b8bfbd670d20b22d6a38eaacee15d4d54e4
[24d1208]: https://github.com/glenn20/mp-image-tool-esp32/commit/24d120829bd646641b08021b5cf8b1aa14f36ad8
[428ff85]: https://github.com/glenn20/mp-image-tool-esp32/commit/428ff8537f4b4ebb1c62b24531bf5c3336153710
[b50543e]: https://github.com/glenn20/mp-image-tool-esp32/commit/b50543e372dfadec321d8dceb9a8d65c85eb4845
[74335e6]: https://github.com/glenn20/mp-image-tool-esp32/commit/74335e67122d057078e3e85e3b9696d75a65657b
[f0a45c4]: https://github.com/glenn20/mp-image-tool-esp32/commit/f0a45c4704ae0b27aeb535723185ffd25fb914cb
[8ec7d13]: https://github.com/glenn20/mp-image-tool-esp32/commit/8ec7d13d32a865abb5ea4cf10e74fc254de2a603
[b726946]: https://github.com/glenn20/mp-image-tool-esp32/commit/b72694602fb51a80174f0ca7e8e811c44abceb78
[1b04a23]: https://github.com/glenn20/mp-image-tool-esp32/commit/1b04a2323088593e6a6bbf8e0b23bb41df0f482e
[4645671]: https://github.com/glenn20/mp-image-tool-esp32/commit/4645671999708d982cb4f6d0ae007dbab41caadb
[d40ada6]: https://github.com/glenn20/mp-image-tool-esp32/commit/d40ada677df9acbfc31d1e2f87170012e59e38a6
[6379c83]: https://github.com/glenn20/mp-image-tool-esp32/commit/6379c83d368f3666f1254dd43df5aaa99fbcb54f
[558f90c]: https://github.com/glenn20/mp-image-tool-esp32/commit/558f90cfeec8a7548dee7cf6eda0d96eee71db47
[8597cda]: https://github.com/glenn20/mp-image-tool-esp32/commit/8597cdaf5a0ff15339c7258483e0c3c8fab234d4
[1f18477]: https://github.com/glenn20/mp-image-tool-esp32/commit/1f18477ce5bb17b3c78d9bf95448db0809c255ea
[13f1bba]: https://github.com/glenn20/mp-image-tool-esp32/commit/13f1bba7f4ba5dca665e1b89cb8db0c13feed89c
[608de82]: https://github.com/glenn20/mp-image-tool-esp32/commit/608de82574a10d03ae8dc38a9097cf1f93decf0a
[d357de7]: https://github.com/glenn20/mp-image-tool-esp32/commit/d357de7c794e761d4d41d2d5bcca892e8d44adce
[47a2b32]: https://github.com/glenn20/mp-image-tool-esp32/commit/47a2b32356aa15eb7ef0a95de158da7b6576b639
[75682ab]: https://github.com/glenn20/mp-image-tool-esp32/commit/75682abf262071dd7c8546b28e7fd069f18f5e1d
[db5d77d]: https://github.com/glenn20/mp-image-tool-esp32/commit/db5d77df1a58a1137c30b133670d1d4ff1263d42
[268318e]: https://github.com/glenn20/mp-image-tool-esp32/commit/268318ea8e27456674ae18f3ec2a020e8103abd2
[fc86ff2]: https://github.com/glenn20/mp-image-tool-esp32/commit/fc86ff299e41083357037cd93ec534d944b85c69

<!-- generated by git-cliff -->
