from copy import deepcopy
from typing import List

import pytest

from cinnamon_core.core.data import FieldDict, Field, ValidationFailureException


def test_adding_field():
    field_dict = FieldDict()
    field_dict.add_short(name='x',
                         value=50,
                         type_hint=int,
                         description="test description")
    assert field_dict.x == 50
    assert field_dict.get('x').value == 50
    assert type(field_dict.get('x')) == Field
    assert field_dict['x'] == 50


def test_init_from_dict():
    field_dict = FieldDict({'x': 50})
    assert field_dict.x == 50
    assert field_dict.get('x').value == 50
    assert type(field_dict.get('x')) == Field
    assert field_dict['x'] == 50


def test_typecheck():
    field_dict = FieldDict()
    field_dict.add_short(name='x',
                         value=50,
                         type_hint=int,
                         description="test description")
    field_dict.x = 'invalid_integer'
    with pytest.raises(ValidationFailureException):
        field_dict.validate()


def test_add_condition():
    field_dict = FieldDict()
    field_dict.add_short(name='x',
                         value=[1, 2, 3],
                         type_hint=List[int],
                         description="test description")
    field_dict.add_short(name='y',
                         value=[2, 2, 2],
                         type_hint=List[int],
                         description="test description")
    field_dict.add_condition(condition=lambda fields: len(fields.x) == len(fields.y),
                             name='x_y_pairing')
    field_dict.validate()

    with pytest.raises(ValidationFailureException):
        field_dict.x.append(5)
        field_dict.validate()


def test_deepcopy():
    field_dict = FieldDict()
    field_dict.add_short(name='x',
                         value=[1, 2, 3])
    field_dict.add_short(name='y',
                         value=FieldDict({'z': 5}))
    copy = deepcopy(field_dict)
    copy.x.append(5)

    assert field_dict.x == [1, 2, 3]
    assert copy.x == [1, 2, 3, 5]

    copy.y.z = 10
    assert field_dict.y.z == 5
    assert copy.y.z == 10
