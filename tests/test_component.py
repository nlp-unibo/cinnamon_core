import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.core.registry import Registry
from pathlib import Path


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
    assert 'x' not in delta_copy.config
    assert component.x == 5


def test_find():
    """
    Testing component.find() method (flat and nested search)
    """

    parent = Component(config=Configuration())
    parent.config.add(name='x', value=5)
    parent.config.add(name='child', value=Component(Configuration({'y': 10})))

    assert parent.x == 5
    assert parent.config.child.y == 10
    assert parent.find(name='x') == 5
    assert parent.find(name='y') == 10


def test_save_and_load():
    """
    Testing component.save() and component.load().
    The component has a flat configuration (i.e., no children)
    """

    config = Configuration()
    config.add(name='x', value=5)
    config.add(name='y', value='some string')

    component = Component(config=config)
    serialization_path = Path('.').resolve()
    component.save(serialization_path=serialization_path)

    component_path = serialization_path.joinpath(component.__class__.__name__)
    assert component_path.exists()

    component.x = 10
    assert component.x == 10

    component.load(serialization_path=serialization_path)
    assert component.x == 5
    assert component.y == 'some string'

    component_path.unlink()


def test_save_and_load_nested():
    """
    Testing component.save() and component.load().
    The component has a non-flat configuration (i.e., at least one child)
    """

    config = Configuration()
    config.add(name='x', value=5)

    child_config = Configuration()
    child_config.add(name='y', value='some string')
    child = Component(config=child_config)

    config.add(name='child', value=child, is_registration=True)
    component = Component(config=config, from_component=True)

    serialization_path = Path('.').resolve()
    component.save(serialization_path=serialization_path)

    component_path = serialization_path.joinpath(component.__class__.__name__)
    assert component_path.exists()

    child_path = component_path.with_name(f'{component_path.name}_child')
    assert child_path.exists()

    config.child.y = 'other string'
    assert config.child.y == 'other string'

    component.load(serialization_path=serialization_path)
    assert config.child.y == 'some string'

    component_path.unlink()
    child_path.unlink()
