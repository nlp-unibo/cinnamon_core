from copy import deepcopy
from typing import List

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, ValidationFailureException
from cinnamon_core.core.data import OutOfRangeParameterValueException
from cinnamon_core.core.registry import RegistrationKey, Registry


@pytest.fixture
def define_configuration():
    config = Configuration()
    config.add(name='x',
               value=10,
               type_hint=int,
               description='a parameter')
    return config


def test_define_configuration(define_configuration):
    """
    Testing configuration definition and get/set attribute APIs
    """

    config = define_configuration
    assert config.x == 10
    assert config.get('x').value == 10
    assert config.get('x').name == 'x'

    config.x = 5
    assert config.x == 5
    assert config.get('x').value == 5


def test_validate_empty(define_configuration):
    """
    Testing that an empty configuration (i.e., no parameters and no conditions) is always valid
    """

    config = define_configuration
    result = config.validate()
    assert result.passed is True


def test_type_hint_validation_nonstrict(define_configuration):
    """
    Testing that typecheck condition triggers when setting a parameter to a new value with different type
    """

    config = define_configuration
    result = config.validate(strict=False)
    assert result.passed is True

    config.x = '10'

    result = config.validate(strict=False)
    assert result.passed is False
    assert result.error_message == 'Condition x_typecheck failed!'


def test_type_hint_validation_strict(define_configuration):
    """
    Testing that configuration.validate() raises an exception when running in strict mode (default)
    """

    config = define_configuration
    config.validate()

    config.x = '10'
    with pytest.raises(ValidationFailureException):
        config.validate()


def test_required_validation():
    """
    Testing that 'is_required' parameter attribute triggers an exception when parameter.value is None
    """

    config = Configuration()
    config.add(name='x',
               is_required=True,
               type_hint=int,
               description='a parameter')
    with pytest.raises(ValidationFailureException):
        config.validate()


def test_allowed_range_validation():
    """
    Testing that configuration triggers an exception when parameter.value is not in parameter.allowed_range
    """

    config = Configuration()
    config.add(name='x',
               value=5,
               is_required=True,
               type_hint=int,
               allowed_range=lambda value: value in [1, 2, 3, 4, 5],
               description='a parameter')
    config.validate()

    with pytest.raises(OutOfRangeParameterValueException):
        config.x = 10


def test_variants_validation_exception():
    """
    Testing that an empty parameter.variants field is not allowed
    """

    config = Configuration()
    config.add(name='x',
               value=5,
               is_required=True,
               type_hint=int,
               variants=[],
               description='a parameter')
    with pytest.raises(ValidationFailureException):
        config.validate()


@pytest.fixture
def register_component():
    Registry.clear()
    Registry.register_and_bind(config_class=Configuration,
                               component_class=Component,
                               name='component',
                               namespace='testing')


def test_registration(
        register_component
):
    """
    Testing configuration.validate() of a nested configuration
    """

    config = Configuration()
    config.add(name='child',
               value=RegistrationKey(name='component',
                                     namespace='testing'),
               is_registration=True)
    config.validate()


def test_registration_post_build(
        register_component
):
    """
    Testing that config.post_build() builds all configuration children (from registration key to component)
    """

    config = Configuration()
    config.add(name='child',
               value=RegistrationKey(name='component',
                                     namespace='testing'),
               build_type_hint=Component,
               is_registration=True)
    config.post_build()
    config.validate(strict=False)
    assert type(config.child) == Component


def test_registration_post_build_mismatch(
        register_component
):
    """
    Testing that configuration raises an exception when a wrong 'build_type_hint' is specified
    """

    config = Configuration()
    config.add(name='child',
               value=RegistrationKey(name='component',
                                     namespace='testing'),
               build_type_hint=str,
               is_registration=True)
    config.post_build()
    with pytest.raises(ValidationFailureException):
        config.validate()


class ConfigA(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        copy = super().get_default()
        copy.add(name='param1',
                 value=False,
                 type_hint=bool)
        copy.add(name='param2',
                 value=[1, 2, 3],
                 type_hint=List[int])
        return copy


@pytest.fixture
def get_default_config():
    config = ConfigA.get_default()
    copy = config.get_delta_copy()
    return config, copy


@pytest.fixture
def get_deepcopy_config():
    config = ConfigA.get_default()
    copy = deepcopy(config)
    return config, copy


def test_copy(get_default_config):
    """
    Testing that a configuration can be deepcopied
    """

    config, copy = get_default_config
    copy.param2.append(5)
    assert config.param2 == [1, 2, 3]
    assert copy.param2 == [1, 2, 3, 5]


def test_get_delta_copy():
    """
    Testing configuration.get_delta_copy()
    """

    config = Configuration()
    config.add(name='x',
               value=10,
               type_hint=int,
               description='a parameter')
    delta_copy: Configuration = config.get_delta_copy()
    config.x = 5
    assert delta_copy.x == 10
    assert config.x == 5
    assert type(delta_copy) == Configuration

    other_copy: Configuration = delta_copy.get_delta_copy(params={'x': 15})
    assert other_copy.x == 15
    assert delta_copy.x == 10
    assert config.x == 5
    assert type(other_copy) == Configuration

    other_copy.add(name='y',
                   value=0)
    assert 'y' not in config
    assert 'y' not in delta_copy
    assert other_copy.y == 0
