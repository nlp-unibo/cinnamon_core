from pathlib import Path
from typing import AnyStr, Any, Union

import jsonpickle as json
import jsonpickle.ext.numpy as jsonpickle_numpy
jsonpickle_numpy.register_handlers()


def load_json(
        filepath: Union[AnyStr, Path]
):
    """
    Loads JSON data from file. Special python objects are
    handled by custom serializers.

    Args:
        filepath: path of .json file from which to load data

    Returns:
        JSON loaded data
    """
    filepath = Path(filepath) if type(filepath) != Path else filepath

    with filepath.open(mode='r') as f:
        data = f.read()
        data = json.decode(data)

    return data


def save_json(
        filepath: Union[AnyStr, Path],
        data: Any,
        **kwargs
):
    """
    Saves data in JSON format to file. Special python objects are
    handled by custom serializers.

    Args:
        filepath: path of .json file in which to save data
        data: data to save
    """
    filepath = Path(filepath) if type(filepath) != Path else filepath

    with filepath.open(mode='w') as f:
        data = json.encode(data, indent=4, **kwargs)
        f.write(data)


__all__ = ['load_json', 'save_json']
