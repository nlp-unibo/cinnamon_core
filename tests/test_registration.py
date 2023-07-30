from pathlib import Path
from typing import Type

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, C
from cinnamon_core.core.registry import Registry, RegistrationKey, NotRegisteredException, \
    AlreadyRegisteredException, AlreadyBoundException


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_registration(
        reset_registry
):
    """
    Testing if a ``Configuration`` is registered correctly.
    """

    key = Registry.register_configuration(config_class=Configuration,
                                          name='test',
                                          tags={'tag1'},
                                          namespace='testing')
    assert key in Registry.REGISTRY

    config_info = Registry.retrieve_configurations_from_key(registration_key=key,
                                                            exact_match=True)
    assert config_info.class_type == Configuration
    assert config_info.constructor == Configuration.get_default


def test_repeated_registration(
        reset_registry
):
    """
    Testing if an exception is raised when using the same ``RegistrationKey`` for registering two ``Configuration``.
    """

    key = RegistrationKey(name='test',
                          tags={'tag1'},
                          namespace='testing')
    Registry.register_configuration_from_key(config_class=Configuration,
                                             registration_key=key)
    with pytest.raises(AlreadyRegisteredException):
        Registry.register_configuration_from_key(config_class=Configuration,
                                                 registration_key=key)


def test_invalid_configuration_retrieval(
        reset_registry
):
    """
    Testing that an exception occurs when trying to retrieve an unregistered configuration
    """

    registration_key = RegistrationKey(name='test_config',
                                       tags={'tag1', 'tag2'},
                                       namespace='testing')
    config_info = Registry.retrieve_configurations_from_key(registration_key=registration_key,
                                                            exact_match=True,
                                                            strict=False)
    assert config_info is None

    with pytest.raises(NotRegisteredException):
        Registry.retrieve_configurations_from_key(registration_key=registration_key,
                                                  exact_match=True)


def test_retrieve_multiple_configurations(
        reset_registry
):
    """
    Testing registry partial match search for configurations.
    Partial match search looks for all registration keys that are equal or subsets of the specified search key.
    In this example, key1 is retrieved as well since its tags are a subset of key2 tags (all other fields are equal)
    """

    key1 = RegistrationKey(name='test_config',
                           tags={'tag1'},
                           namespace='testing')
    Registry.register_configuration_from_key(config_class=Configuration,
                                             registration_key=key1)

    key2 = RegistrationKey(name='test_config',
                           tags={'tag2', 'tag1'},
                           namespace='testing')
    Registry.register_configuration_from_key(config_class=Configuration,
                                             registration_key=key2)

    retrieved_configs = Registry.retrieve_configurations_from_key(registration_key=key2,
                                                                  exact_match=False)
    assert len(retrieved_configs) == 2


def test_register_and_then_binding(
        reset_registry
):
    """
    Test configuration registration and bind APIs
    """

    key = Registry.register_configuration(config_class=Configuration,
                                          name='test',
                                          tags={'tag1'},
                                          namespace='testing')
    Registry.bind_from_key(registration_key=key,
                           component_class=Component)


def test_register_and_then_binding_exception(
        reset_registry
):
    """
    Testing that an exception occurs when trying to re-bind a configuration
    """

    key = Registry.register_configuration(config_class=Configuration,
                                          name='test',
                                          tags={'tag1'},
                                          namespace='testing')
    Registry.bind_from_key(registration_key=key,
                           component_class=Component)
    with pytest.raises(AlreadyBoundException):
        Registry.bind_from_key(registration_key=key,
                               component_class=Component)


def test_register_and_binding(
        reset_registry
):
    """
    Testing registry.register_and_bind() function
    """

    Registry.register_and_bind(config_class=Configuration,
                               component_class=Component,
                               name='test',
                               tags={'tag'},
                               namespace='testing')


def test_register_and_binding_exception(
        reset_registry
):
    """
    Testing that an exception occurs when re-running registry.register_and_bind() for an already registered (and bound)
    configuration
    """

    Registry.register_and_bind(config_class=Configuration,
                               component_class=Component,
                               name='test',
                               tags={'tag'},
                               namespace='testing')
    with pytest.raises(AlreadyRegisteredException):
        Registry.register_and_bind(config_class=Configuration,
                                   component_class=Component,
                                   name='test',
                                   tags={'tag'},
                                   namespace='testing')


def test_build_component(
        reset_registry
):
    """
    Testing Component building from a registered (and bound) configuration
    """

    key = Registry.register_and_bind(config_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(registration_key=key)
    assert type(component) == Component


def test_register_built_component(
        reset_registry
):
    """
    Testing built component live registration API
    """

    key = Registry.register_and_bind(config_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(registration_key=key)
    Registry.register_built_component_from_key(registration_key=key,
                                               component=component)


def test_retrieve_built_component(
        reset_registry
):
    """
    Testing built component live registration and retrieval APIs
    """

    key = Registry.register_and_bind(config_class=Configuration,
                                     component_class=Component,
                                     name='component',
                                     namespace='testing')
    component = Registry.build_component_from_key(registration_key=key)
    Registry.register_built_component_from_key(registration_key=key,
                                               component=component)
    retrieved = Registry.retrieve_component_instance_from_key(registration_key=key)
    assert component == retrieved


def test_register_built_component_exception(
        reset_registry
):
    """
    Testing that an exception occurs when trying to retrieve an unregistered built component
    """

    component = Component(config=Configuration())
    key = RegistrationKey(name='component',
                          namespace='testing')
    with pytest.raises(NotRegisteredException):
        Registry.register_built_component_from_key(registration_key=key,
                                                   component=component)


def test_retrieve_external_configurations(
        reset_registry
):
    """
    Testing Component building API for an external registration.
    """

    external_path = Path().absolute().parent.joinpath('tests', 'external_test_repo')
    Registry.load_registrations(directory_path=external_path)
    Registry.expand_and_resolve_registration()
    component = Registry.build_component(name='test',
                                         namespace='external')
    assert isinstance(component, Component)


class ConfigA(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='x',
                   value=5,
                   type_hint=int)
        config.add(name='y',
                   value=10,
                   type_hint=int)
        return config


def test_register_delta_copy(
        reset_registry
):
    """
    Testing registering a configuration delta copy (and building it)
    """

    Registry.register_and_bind(config_class=ConfigA,
                               component_class=Component,
                               config_constructor=ConfigA.get_delta_class_copy,
                               config_kwargs={
                                   'params': {
                                       'x': 10,
                                       'y': 15
                                   }
                               },
                               name='config',
                               namespace='testing')
    component = Registry.build_component_from_key(registration_key=RegistrationKey(name='config',
                                                                                   namespace='testing'))
    assert component.x == 10
    assert component.y == 15
