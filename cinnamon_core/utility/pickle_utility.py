from pathlib import Path
from typing import AnyStr, Any, Union

import cloudpickle as pickle


def load_pickle(
        filepath: Union[AnyStr, Path]
) -> Any:
    """
    Loads serialized data from pickle file.

    Args:
        filepath: path to serialized data in pickle format

    Returns:
        Loaded data
    """

    filepath = Path(filepath) if type(filepath) != Path else filepath
    with filepath.open('rb') as f:
        data = pickle.load(f)
    return data


def save_pickle(
        filepath: Union[AnyStr, Path],
        data: Any
):
    """
    Serializes input data to filesystem in pickle format.

    Args:
        filepath: path where to save serialized data
        data: data to serialize
    """

    filepath = Path(filepath) if type(filepath) != Path else filepath
    with filepath.open('wb') as f:
        pickle.dump(data, f)


__all__ = ['load_pickle', 'save_pickle']
