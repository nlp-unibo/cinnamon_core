import shutil
from pathlib import Path
from typing import AnyStr, Union

from utility.logging_utility import logger


def clear_folder(
        folder: Union[AnyStr, Path]
):
    """
    Clears a folder recursively.

    Args:
        folder: path to folder to clear.
    """

    folder = Path(folder) if type(folder) != Path else folder

    if not folder.is_dir():
        raise RuntimeError(f'{folder} is not a directory.')

    for filename in folder.glob('**/**'):
        if not filename.is_file():
            continue

        file_path = folder.joinpath(filename)
        try:
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
        except Exception as e:
            logger.exception(f'Failed to delete {file_path}. Reason: {e}')
            raise e


__all__ = ['clear_folder']
