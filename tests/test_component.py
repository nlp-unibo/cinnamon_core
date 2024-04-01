import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.core.registry import Registry


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_build_component(
        reset_registry
):
    """
    Testing if we can build component from its configuration key
    """

    key = Registry.register_and_bind(config_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(registration_key=key)
    assert type(component) == Component
    assert type(component.config) == Configuration


def test_delta_copy(
        reset_registry
):
    """
    Testing if we can get a component delta copy.
    We additionally check if setting attributes to copy does not alter the original component
    """

    key = Registry.register_and_bind(config_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(registration_key=key)

    delta_copy: Component = component.get_delta_copy()
    assert component != delta_copy
    assert type(delta_copy) == Component

    component.config.add(name='x',
                         value=5)
    assert 'x' not in delta_copy.config.fields
    assert component.x == 5


def test_find():
    """
    Testing component.find() method (flat and nested search)
    """

    parent = Component(config=Configuration())
    parent.config.add(name='x', value=5)
    parent.config.add(name='child', value=Component(Configuration(y=10)), is_child=True)

    assert parent.x == 5
    assert parent.config.child.y == 10
    assert parent.find(name='x') == 5
    assert parent.find(name='y') == 10
