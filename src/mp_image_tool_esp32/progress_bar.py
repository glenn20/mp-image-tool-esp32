"""A module for showing progress bars and capturing output from esptool.py."""

from __future__ import annotations

import io
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Lock
from typing import IO, Any, Callable, Generator

import rich.progress

from . import logger

log = logger.getLogger(__name__)


# A StringIO buffer is used for redirecting/capturing stdout and stderr
class StringIO_RW(io.StringIO):
    """A thread-safe StringIO buffer which supports read() and write().
    Writes are to the end of the buffer and reads are from the current position.
    All data written to the buffer is available in the `output` attribute.
    """

    def __init__(self, s: str = ""):
        super().__init__()
        self.output = s
        self.read_pos = 0
        self.lock = Lock()

    def read(self, size: int | None = None) -> str:
        end = self.read_pos + (size or 1)
        while not self.closed and len(self.output) < end:
            time.sleep(0.1)
        with self.lock:
            s = self.output[self.read_pos : end]
            self.read_pos = end
            return s

    def write(self, s: str) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        with self.lock:
            self.output += s
            return len(s)


# A context manager to redirect stdout and stderr to a buffer
# Will print stderr to stdout if an error occurs
# This is used to wrap calls to esptool module functions directly
class CaptureOutput:
    def __init__(self, name: str = "esptool"):
        self.name = name
        pipe = StringIO_RW()
        self.reader = pipe
        self.writer = pipe
        # r, w = os.pipe()
        # return os.fdopen(r, "r"), os.fdopen(w, "w")

    @property
    def output(self) -> str:
        return self.writer.output

    def __enter__(self) -> CaptureOutput:
        self.backupio = sys.stdout
        sys.stdout = self.writer  # Redirect stdout
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        sys.stdout = self.backupio  # Restore stdout
        if exc_type:
            log.error(f"Error: {self.name} raises {exc_type.__name__}")
        if not self.writer.closed:
            self.writer.close()
        if not self.reader.closed:
            self.reader.close()
        if exc_type:
            raise exc_val


class ProgressBar:
    """A progress bar as a context manager which can be updated with the number
    of bytes read or written. The progress bar is shown if the total size is
    greater than `MIN_SIZE` bytes."""

    MIN_SIZE: int = 64 * 1024  # Show progress bar for sizes above 64 KB
    columns = (
        rich.progress.SpinnerColumn(),
        *rich.progress.Progress.get_default_columns(),
        rich.progress.DownloadColumn(),
        rich.progress.TransferSpeedColumn(),
    )

    def __init__(self, total: int = 0, name: str = "Progress", **kwargs: Any):
        self.total = total
        self.name = name
        # Ensure progress bar output goes to stdout and is not redirected.
        logger.console.file = sys.stdout
        self.progress = rich.progress.Progress(
            *self.columns,
            console=logger.console,
            disable=self.total < self.MIN_SIZE,
            **kwargs,
        )
        self.task: rich.progress.TaskID | None = None

    def __enter__(self) -> ProgressBar:
        p = self.progress.__enter__()
        self.task = p.add_task(f"[cyan]{self.name}", total=self.total)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.progress.__exit__(exc_type, exc_val, exc_tb)
        logger.console.file = None  # type: ignore

    def update(self, completed: int, total: int = 0) -> None:
        if self.task is not None:
            self.progress.update(self.task, completed=completed, size=total or None)


# Regexp to match progress messages printed out by esptool.py
# match[1] is "" for reads and "Writing at " for writes
# match[2] is the number of bytes read/written,
# Matches: "Writing at 0x0002030... (2 %)\x08" and "1375 (1 %)\x08" at end of output
PROGRESS_BAR_MESSAGE_REGEXP = re.compile(
    r"(Writing at |Wrote )?([0-9][0-9a-fx]+)[^0-9a-f]"
)


def monitor_esptool_progress_messages(
    esptool_stdout: IO[str], update: Callable[[int, int], None]
) -> None:
    """Monitor the output stream of `esptool.py` for progress messages and
    update the progress bar accordingly. Returns the output as a string."""
    offset, line = 0, ""
    # Can't use readline() as progress messages dont end in "\n"
    while s := esptool_stdout.read(1):
        if s not in ("\n", "\r", "\x08"):
            line += s
        elif line:
            log.debug(line)
            if match := re.match(PROGRESS_BAR_MESSAGE_REGEXP, line):
                current = int(match[2], 0)
                # On writes, the first number is a starting value - need to subtract
                offset = offset or (current if match[1] else 0)
                update(current - offset, 0)  # Update the progress bar
            line = ""


@contextmanager
def EsptoolMonitor(
    size: int = 0, *, name: str = ""
) -> Generator[CaptureOutput, None, None]:
    """Show a progress bar for `esptool.py` reads and writes.
    A context manager that captures sys.stdout while executing the body of the
    `with` block and shows a progress bar for `esptool.py` transfers above 64
    KB. The captured `stdout` output is saved in the `output` attribute.

    - `size` is the expected size of the read/write operation.
    - `name` is the name shown in the progress bar and in error messages.

    The progress bar is run in a separate thread while executing the body of the
    `with` block.
    """
    # Do progress bar first so it outputs to sys.stdout before it is redirected
    with ProgressBar(total=size, name=name) as pbar:
        with CaptureOutput(name) as capture:  # Redirect stdout to a buffer
            with ThreadPoolExecutor() as executor:
                # Run the monitor in a separate thread
                monitor = executor.submit(
                    monitor_esptool_progress_messages, capture.reader, pbar.update
                )
                yield capture
                capture.writer.close()  # Monitor thread will exit after processing reader
                monitor.result()  # Wait for monitor thread to finish
