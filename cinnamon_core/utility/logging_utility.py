import logging
import os
import sys
import traceback
from logging import FileHandler
from pathlib import Path
from typing import AnyStr, Optional, Union

try:
    import absl.logging

    logging.root.removeHandler(absl.logging._absl_handler)
    absl.logging._warn_preinit_stderr = False
except Exception:
    pass


class NoBuiltLoggerException(Exception):

    def __init__(self):
        super(NoBuiltLoggerException, self).__init__(
            'Attempted to use logger prior to building it...Make sure you call build_logger(...) first.')


_logging_path: Optional[Path] = None
logger: Optional[logging.Logger] = None


def set_logging_path(
        logging_path: Union[AnyStr, Path]
):
    """
    Sets the logging path for the logger

    Args:
        logging_path: path where to log the logger's output
    """

    global _logging_path
    _logging_path = Path(logging_path) if type(logging_path) != Path else logging_path


def _handle_exception(
        exctype,
        value,
        tb
):
    global logger
    if logger is not None:
        logger.info(f"Type: {exctype}{os.linesep}"
                    f"Value: {value}{os.linesep}"
                    f"Traceback: {''.join(traceback.format_exception(exctype, value, tb))}{os.linesep}")


def build_logger(
        name: str
):
    """
    Builds the logger.

    Args:
        name: name of the logger
    """
    global logger
    global _logging_path

    if logger is not None:
        return

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)

    file_handler = FileHandler(_logging_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    sys.excepthook = _handle_exception


def update_logger(
        logging_path: Path
):
    global logger
    global _logging_path

    set_logging_path(logging_path=logging_path)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    if _logging_path.parent.exists():
        file_handler = FileHandler(_logging_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.handlers[1] = file_handler


__all__ = [
    'set_logging_path',
    'build_logger',
    'logger',
    'update_logger'
]
