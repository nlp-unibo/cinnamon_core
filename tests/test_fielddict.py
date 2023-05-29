from typing import List

import pytest

from core.data import FieldDict, Field, ValidationFailureException


def test_adding_field():
    field_dict = FieldDict()
    field_dict.add_short(name='x',
                         value=50,
                         type_hint=int,
                         description="test description")
    assert field_dict.x == 50
    assert field_dict.get_field('x').value == 50
    assert type(field_dict.get_field('x')) == Field
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
