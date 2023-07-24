from __future__ import annotations

from itertools import product

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.core.registry import RegistrationKey, Registry


class ParentConfig(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1',
                   value=True,
                   type_hint=bool,
                   variants=[False, True])
        config.add(name='param_2',
                   value=False,
                   type_hint=bool,
                   variants=[False, True])
        config.add(name='child_A',
                   value=RegistrationKey(name='config_a',
                                         namespace='testing'),
                   is_registration=True)
        config.add(name='child_B',
                   value=RegistrationKey(name='config_b',
                                         namespace='testing'),
                   is_registration=True)
        return config


class NestedChild(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='child',
                   value=RegistrationKey(name='config_c',
                                         namespace='testing'),
                   is_registration=True)

        return config


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_flatten_parameter_variants(
        reset_registry
):
    """
    Testing registering and binding nested configuration and its variants.
    In this case, the variants are just at the parent configuration level.
    """

    Registry.register_and_bind(config_class=NestedChild,
                               component_class=Component,
                               name='config_a',
                               namespace='testing')
    Registry.register_and_bind(config_class=Configuration,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(config_class=Configuration,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(config_class=ParentConfig,
                                                       component_class=Component,
                                                       name='parent',
                                                       namespace='testing')
    assert len(variant_keys) == 5
    for (param1, param2) in product([False, True], [False, True]):
        assert RegistrationKey(name='parent',
                               tags={f'param_1={param1}', f'param_2={param2}'},
                               namespace='testing') in variant_keys


class ConfigA(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1', value=True, type_hint=bool, variants=[False, True])
        config.add(name='child', value=RegistrationKey(name='config_b',
                                                       namespace='testing'), is_registration=True)
        return config


class ConfigB(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1', value=1, type_hint=int, variants=[1, 2])
        config.add(name='child', value=RegistrationKey(name='config_c',
                                                       namespace='testing'), is_registration=True)

        return config


class ConfigC(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1', value=False, type_hint=bool, variants=[False, True])

        return config


def test_nested_parameter_variants(
        reset_registry
):
    """
    Testing registering and binding nested configuration and its variants.
    """

    Registry.register_and_bind(config_class=ConfigB,
                               config_constructor=ConfigB.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(config_class=ConfigC,
                               config_constructor=ConfigC.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(config_class=ConfigA,
                                                       component_class=Component,
                                                       name='config_a',
                                                       namespace='testing')
    assert len(variant_keys) == 9


class ConfigD(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1',
                   value=True,
                   type_hint=bool,
                   variants=[False, True])
        config.add(name='child',
                   value=RegistrationKey(name='config_e',
                                         namespace='testing'),
                   is_registration=True)
        return config


class ConfigE(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1',
                   value=1,
                   type_hint=int,
                   variants=[1, 2])

        return config


class ConfigF(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add(name='param_1', value=True, type_hint=bool, variants=[False, True])
        config.add(name='param_2', value=True, type_hint=bool, variants=[False, True])

        config.add_condition(condition=lambda p: p.param_1 == p.param_2)

        return config


def test_variants_with_conditions(
        reset_registry
):
    """
    Testing registering configuration and its valid variants
    """

    variant_keys = Registry.register_and_bind_variants(config_class=ConfigF,
                                                       component_class=Component,
                                                       name='config_f',
                                                       namespace='testing')
    assert len(variant_keys) == 3
