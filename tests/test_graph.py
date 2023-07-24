from pathlib import Path
from typing import Type

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, C
from cinnamon_core.core.registry import Registry, RegistrationKey, DisconnectedGraphException


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_add_configuration(
        reset_registry
):
    """
    Testing that the registration DAG has new nodes and edges when adding a configuration to the registry
    """

    Registry.add_configuration(config_class=Configuration,
                               name='config',
                               namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 2
    assert len(Registry.DEPENDENCY_DAG.edges) == 1

    assert Registry.check_registration_graph()


def test_expand_and_resolve_single_configuration(
        reset_registry
):
    """
    Testing registry.expand_and_resolve_registration() function
    """

    Registry.add_configuration(config_class=Configuration,
                               name='config',
                               namespace='testing')
    Registry.expand_and_resolve_registration()
    assert RegistrationKey(name='config', namespace='testing') in Registry.REGISTRY
    assert len(Registry.REGISTRY) == 1


def test_add_and_bind_configuration(
        reset_registry
):
    """
    Testing that the registration DAG gets new nodes and edges when using registry.add_and_bind()
    """

    Registry.add_and_bind(config_class=Configuration,
                          component_class=Component,
                          name='config',
                          namespace='testing')
    assert len(Registry.REGISTRY) == 0

    assert Registry.check_registration_graph()
    Registry.expand_and_resolve_registration()
    component = Registry.build_component(name='config', namespace='testing')
    assert type(component) == Component
    assert len(Registry.REGISTRY) == 1


class ConfigA(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='param',
                   value=5,
                   variants=[10, 15, 20])

        return config


def test_flat_add_variants(
        reset_registry
):
    """
    Testing that the registration DAG has new nodes and edges when adding a configuration
    and its variants to the registry
    """

    Registry.add_and_bind_variants(config_class=ConfigA,
                                   component_class=Component,
                                   name='config',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 2
    assert len(Registry.DEPENDENCY_DAG.edges) == 1


class ConfigB(ConfigA):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='child',
                   variants=[RegistrationKey(name='config_c', tags={'var1'}, namespace='testing'),
                             RegistrationKey(name='config_c', tags={'var2'}, namespace='testing')])

        return config


def test_one_level_add_variants(
        reset_registry
):
    """
    Testing adding a flat configuration and its variants to the registration DAG
    """

    Registry.add_and_bind_variants(config_class=ConfigB,
                                   component_class=Component,
                                   name='config',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 2
    assert len(Registry.DEPENDENCY_DAG.edges) == 1
    assert Registry.check_registration_graph()
    Registry.expand_and_resolve_registration()
    assert len(Registry.REGISTRY) == 7


class ConfigC(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='x',
                   value=1,
                   type_hint=int,
                   variants=[1, 2, 3, 4])
        config.add(name='child',
                   value=RegistrationKey(name='config_d', namespace='testing'),
                   is_registration=True)

        return config


class ConfigD(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='y',
                   value=False,
                   type_hint=bool,
                   variants=[False, True])
        config.add(name='child',
                   value=RegistrationKey(name='config_e', namespace='testing'),
                   is_registration=True)

        return config


class ConfigE(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='z',
                   value=5,
                   type_hint=int,
                   variants=[5, 25, 100])
        return config


def test_two_level_add_variants(
        reset_registry
):
    """
    Testing adding a nested configuration and its variants to the registration DAG
    """

    Registry.add_and_bind_variants(config_class=ConfigC,
                                   component_class=Component,
                                   name='config_c',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 3
    assert Registry.check_registration_graph()
    Registry.add_and_bind_variants(config_class=ConfigD,
                                   component_class=Component,
                                   name='config_d',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 4
    assert Registry.check_registration_graph()
    Registry.add_and_bind(config_class=ConfigE,
                          component_class=Component,
                          name='config_e',
                          namespace='testing')
    assert Registry.check_registration_graph()
    Registry.expand_and_resolve_registration()
    assert len(Registry.REGISTRY) == 36


class ConfigF(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='child',
                   value=RegistrationKey(name='config_g', namespace='testing'),
                   is_registration=True)

        return config


class ConfigG(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='child',
                   value=RegistrationKey(name='config_f', namespace='testing'),
                   is_registration=True)

        return config


def test_cycle(
        reset_registry
):
    """
    Testing that an exception occurs when the registration DAG contains a cycle (i.e., it is not a DAG)
    """

    Registry.add_configuration(config_class=ConfigF,
                               name='config_f',
                               namespace='testing')
    Registry.add_configuration(config_class=ConfigG,
                               name='config_g',
                               namespace='testing')
    with pytest.raises(DisconnectedGraphException):
        Registry.check_registration_graph()


class ConfigH(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='child',
                   value=RegistrationKey(name='test', namespace='external'),
                   is_registration=True)

        return config


def test_external_dependency(
        reset_registry
):
    """
    Testing that an external registration can be added to the registration DAG without errors.
    In particular, expanding the external registration triggers module import of the external package
    """

    external_path = Path().absolute().parent.joinpath('tests', 'external_test_repo')
    Registry.load_registrations(directory_path=external_path)

    Registry.add_configuration(config_class=ConfigH,
                               name='config',
                               namespace='testing')

    Registry.check_registration_graph()
    assert len(Registry.DEPENDENCY_DAG.nodes) == 3
    Registry.expand_and_resolve_registration()


class ConfigI(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='x',
                   value=5)

        return config


class ConfigJ(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add(name='child',
                   value=RegistrationKey(name='config_i', tags={'var1'}, namespace='testing'),
                   is_registration=True)

        return config


def test_nested_configuration_variant(
        reset_registry
):
    """
    Testing adding a nested configuration and its variants to the registration DAG
    """

    Registry.add_and_bind_variants(config_class=ConfigI,
                                   component_class=Component,
                                   name='config_i',
                                   namespace='testing')
    Registry.add_and_bind(config_class=ConfigJ,
                          component_class=Component,
                          name='config_j',
                          namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 4
    Registry.check_registration_graph()
    Registry.expand_and_resolve_registration()
