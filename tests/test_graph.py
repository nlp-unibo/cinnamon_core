from typing import Type

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, C
from cinnamon_core.core.registry import Registry, RegistrationKey, NotADAGException


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_add_configuration(
        reset_registry
):
    Registry.add_configuration(configuration_class=Configuration,
                               name='config',
                               namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 2
    assert len(Registry.DEPENDENCY_DAG.edges) == 1

    assert Registry.check_registration_graph()


def test_expand_and_resolve_single_configuration(
        reset_registry
):
    Registry.add_configuration(configuration_class=Configuration,
                               name='config',
                               namespace='testing')
    Registry.expand_and_resolve_registration()
    assert RegistrationKey(name='config', namespace='testing') in Registry.REGISTRY
    assert len(Registry.REGISTRY) == 1


def test_add_and_bind_configuration(
        reset_registry
):
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

        config.add_short(name='param',
                         value=5,
                         variants=[10, 15, 20])

        return config


def test_flat_add_variants(
        reset_registry
):
    Registry.add_and_bind_variants(config_class=ConfigA,
                                   component_class=Component,
                                   name='config',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 5
    assert len(Registry.DEPENDENCY_DAG.edges) == 4


class ConfigB(ConfigA):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add_short(name='child',
                         variants=[RegistrationKey(name='config_c', tags={'var1'}, namespace='testing'),
                                   RegistrationKey(name='config_c', tags={'var2'}, namespace='testing')],
                         is_registration=True)

        return config


def test_one_level_add_variants(
        reset_registry
):
    Registry.add_and_bind_variants(config_class=ConfigB,
                                   component_class=Component,
                                   name='config',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 10
    assert len(Registry.DEPENDENCY_DAG.edges) == 9
    assert Registry.check_registration_graph()
    Registry.expand_and_resolve_registration()
    assert len(Registry.REGISTRY) == 7


class ConfigC(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add_short(name='x',
                         value=1,
                         type_hint=int,
                         variants=[1, 2, 3, 4])
        config.add_short(name='child',
                         value=RegistrationKey(name='config_d', namespace='testing'),
                         is_registration=True)

        return config


class ConfigD(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add_short(name='y',
                         value=False,
                         type_hint=bool,
                         variants=[False, True])
        config.add_short(name='child',
                         value=RegistrationKey(name='config_e', namespace='testing'),
                         is_registration=True)

        return config


class ConfigE(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add_short(name='z',
                         value=5,
                         type_hint=int,
                         variants=[5, 25, 100])
        return config


def test_two_level_add_variants(
        reset_registry
):
    Registry.add_and_bind_variants(config_class=ConfigC,
                                   component_class=Component,
                                   name='config_c',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 7
    assert Registry.check_registration_graph()
    Registry.add_and_bind_variants(config_class=ConfigD,
                                   component_class=Component,
                                   name='config_d',
                                   namespace='testing')
    assert len(Registry.DEPENDENCY_DAG.nodes) == 10
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

        config.add_short(name='child',
                         value=RegistrationKey(name='config_g', namespace='testing'),
                         is_registration=True)

        return config


class ConfigG(Configuration):

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        config = super().get_default()

        config.add_short(name='child',
                         value=RegistrationKey(name='config_f', namespace='testing'),
                         is_registration=True)

        return config


def test_cycle(
        reset_registry
):
    Registry.add_configuration(configuration_class=ConfigF,
                               name='config_f',
                               namespace='testing')
    Registry.add_configuration(configuration_class=ConfigG,
                               name='config_g',
                               namespace='testing')
    with pytest.raises(NotADAGException):
        Registry.check_registration_graph()
