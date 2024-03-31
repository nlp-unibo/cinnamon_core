from copy import deepcopy
from typing import List

import pytest

from cinnamon_core.core.data import Data, Field, ValidationFailureException


def test_adding_field():
    """
    Testing data.add() function
    """

    data = Data()
    data.add(name='x',
             value=50,
             type_hint=int,
             description="test description")
    assert data.x == 50
    assert data.get('x').value == 50
    assert type(data.get('x')) == Field


def test_init_from_kwargs():
    """
    Testing that a data can be initialized from a python dictionary
    """

    data = Data(x=50)
    assert data.x == 50
    assert data.get('x').value == 50
    assert type(data.get('x')) == Field


def test_typecheck():
    """
    Testing that typecheck condition fails when setting a field to a new value with different type
    """

    data = Data()
    data.add(name='x',
             value=50,
             type_hint=int,
             description="test description")
    data.x = 'invalid_integer'
    with pytest.raises(ValidationFailureException):
        data.validate()


def test_add_condition():
    """
    Testing fielddict.add_condition() function
    """

    data = Data()
    data.add(name='x',
             value=[1, 2, 3],
             type_hint=List[int],
             description="test description")
    data.add(name='y',
             value=[2, 2, 2],
             type_hint=List[int],
             description="test description")
    data.add_condition(condition=lambda fields: len(fields.x) == len(fields.y),
                       name='x_y_pairing')
    data.validate()

    with pytest.raises(ValidationFailureException):
        data.x.append(5)
        data.validate()


def test_copy():
    """
    Testing that a data can be deepcopied
    """

    data = Data()
    data.add(name='x',
             value=[1, 2, 3])
    data.add(name='y',
             value=Data(z=5))
    copy = deepcopy(data)
    copy.x.append(5)

    assert data.x == [1, 2, 3]
    assert copy.x == [1, 2, 3, 5]

    copy.y.z = 10
    assert data.y.z == 5
    assert copy.y.z == 10


def test_search_by_tag():
    data = Data()
    data.add(name='x',
             value=5,
             tags={'number'})
    data.add(name='y',
             value=10,
             tags={'number'})
    data.add(name='z',
             value='z',
             tags={'letter'})

    result = data.search_field_by_tag(tags={'number'})
    assert 'x' in result
    assert 'y' in result
    assert type(result['x'] == int)
    assert type(result['y'] == int)


def test_search():
    data = Data()
    data.add(name='x',
             value=5,
             tags={'number'})
    data.add(name='y',
             value=10,
             tags={'number'})
    data.add(name='z',
             value='z',
             tags={'letter'})

    result = data.search_field(conditions=[
        lambda field: 'number' in field.tags
    ])
    assert 'y' in result
    assert type(result['x'] == int)
    assert type(result['y'] == int)
