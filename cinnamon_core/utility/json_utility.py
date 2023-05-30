from pathlib import Path
from typing import AnyStr, Any, Union

import simplejson


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
        data = simplejson.load(f)

    return data


def save_json(
        filepath: Union[AnyStr, Path],
        data: Any
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
        simplejson.dump(data, f, tuple_as_array=False, indent=4)


__all__ = ['load_json', 'save_json']
