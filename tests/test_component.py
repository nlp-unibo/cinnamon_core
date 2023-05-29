import pytest

from core.component import Component
from core.configuration import Configuration
from core.registry import Registry


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_build_component(
        reset_registry
):
    key = Registry.register_and_bind(configuration_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(config_registration_key=key)
    assert type(component) == Component
    assert type(component.config) == Configuration


def test_delta_copy(
        reset_registry
):
    key = Registry.register_and_bind(configuration_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(config_registration_key=key)

    delta_copy: Component = component.get_delta_copy()
    assert component != delta_copy
    assert type(delta_copy) == Component

    component.config.add_short(name='x',
                               value=5)
    assert 'x' not in delta_copy.config
    assert component.x == 5
