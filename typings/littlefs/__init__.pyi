import io
from typing import (
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    overload,
)

from _typeshed import (
    OpenBinaryMode,
    OpenBinaryModeReading,
    OpenBinaryModeUpdating,
    OpenBinaryModeWriting,
    OpenTextMode,
)
from littlefs.context import UserContext as UserContext
from littlefs.errors import LittleFSError as LittleFSError
from littlefs.lfs import LFSConfig as LFSConfig
from littlefs.lfs import LFSFileFlag as LFSFileFlag
from littlefs.lfs import LFSFSStat as LFSFSStat
from littlefs.lfs import LFSStat as LFSStat

class LittleFS:
    cfg: LFSConfig

    @property
    def block_count(self) -> int: ...
    @property
    def used_block_count(self) -> int: ...
    def __init__(
        self, context: Optional["UserContext"] = None, mount: bool = True, **kwargs: int
    ) -> None: ...
    @overload
    def open(
        self,
        fname: str,
        mode: OpenTextMode = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> io.TextIOWrapper: ...
    @overload
    def open(
        self,
        fname: str,
        mode: OpenBinaryMode,
        buffering: Literal[0],
        encoding: None = None,
        errors: None = None,
        newline: None = None,
    ) -> io.RawIOBase: ...
    @overload
    def open(
        self,
        fname: str,
        mode: OpenBinaryModeUpdating,
        buffering: Literal[-1, 1] = -1,
        encoding: None = None,
        errors: None = None,
        newline: None = None,
    ) -> io.BufferedRandom: ...
    @overload
    def open(
        self,
        fname: str,
        mode: OpenBinaryModeWriting,
        buffering: Literal[-1, 1] = -1,
        encoding: None = None,
        errors: None = None,
        newline: None = None,
    ) -> io.BufferedWriter: ...
    @overload
    def open(
        self,
        fname: str,
        mode: OpenBinaryModeReading,
        buffering: Literal[-1, 1] = -1,
        encoding: None = None,
        errors: None = None,
        newline: None = None,
    ) -> io.BufferedReader: ...
    @overload
    def open(
        self,
        fname: str,
        mode: str = "r",
        buffering: int = -1,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        newline: Optional[str] = None,
    ) -> Union[io.BufferedIOBase, io.TextIOWrapper, io.RawIOBase]: ...
    def stat(self, path: str) -> LFSStat: ...
    def remove(self, path: str, recursive: bool = False) -> None: ...
    def rename(self, oldpath: str, newpath: str) -> int: ...
    def mount(self) -> int: ...
    def unmount(self) -> int: ...
    def fs_stat(self) -> LFSFSStat: ...
    def fs_grow(self, block_count: int) -> int: ...
    def walk(self, top: str) -> Iterator[Tuple[str, List[str], List[str]]]: ...
    def makedirs(self, name: str, exist_ok: bool = False) -> None: ...
    def format(self) -> int: ...
