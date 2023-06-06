from __future__ import annotations

from itertools import product

import pytest

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, add_variant, supports_variants
from cinnamon_core.core.registry import RegistrationKey, Registry


@supports_variants
class ParentConfig(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1',
                         value=True,
                         type_hint=bool,
                         variants=[False, True])
        config.add_short(name='param_2',
                         value=False,
                         type_hint=bool,
                         variants=[False, True])
        config.add_short(name='child_A',
                         value=RegistrationKey(name='config_a',
                                               namespace='testing'),
                         is_registration=True)
        config.add_short(name='child_B',
                         value=RegistrationKey(name='config_b',
                                               namespace='testing'),
                         is_registration=True)
        return config

    @classmethod
    @add_variant(name='variant1')
    def variant1(
            cls
    ) -> ParentConfig:
        default = cls.get_default()
        default.param_1 = False
        default.param_2 = False
        return default

    @classmethod
    @add_variant(name='variant2')
    def variant2(
            cls
    ) -> ParentConfig:
        default = cls.get_default()
        default.param_1 = False
        default.param_2 = True
        return default


class NestedChild(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='child_A', value=RegistrationKey(name='config_c',
                                                               namespace='testing'),
                         is_registration=True)

        return config


@pytest.fixture
def reset_registry():
    Registry.clear()


def test_flatten_parameter_variants(
        reset_registry
):
    Registry.register_and_bind(configuration_class=NestedChild,
                               configuration_constructor=NestedChild.get_default,
                               component_class=Component,
                               name='config_a',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=Configuration,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=Configuration,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(configuration_class=ParentConfig,
                                                       component_class=Component,
                                                       name='parent',
                                                       namespace='testing',
                                                       parameter_variants_only=True)
    assert len(variant_keys) == 4
    for (param1, param2) in product([False, True], [False, True]):
        assert RegistrationKey(name='parent',
                               tags={f'param_1={param1}', f'param_2={param2}'},
                               namespace='testing') in variant_keys


def test_flatten_configuration_variants(
        reset_registry
):
    Registry.register_and_bind(configuration_class=NestedChild,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_a',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=Configuration,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=Configuration,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(configuration_class=ParentConfig,
                                                       component_class=Component,
                                                       name='parent',
                                                       namespace='testing',
                                                       parameter_variants_only=False,
                                                       allow_parameter_variants=True)
    assert len(variant_keys) == 2
    assert RegistrationKey(name='parent', tags={'variant1'}, namespace='testing') in variant_keys
    assert RegistrationKey(name='parent', tags={'variant2'}, namespace='testing') in variant_keys


class ConfigA(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=True, type_hint=bool, variants=[False, True])
        config.add_short(name='child', value=RegistrationKey(name='config_b',
                                                             namespace='testing'), is_registration=True)
        return config


class ConfigB(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=1, type_hint=int, variants=[1, 2])
        config.add_short(name='child', value=RegistrationKey(name='config_c',
                                                             namespace='testing'), is_registration=True)

        return config


class ConfigC(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=False, type_hint=bool, variants=[False, True])

        return config


def test_nested_parameter_variants(
        reset_registry
):
    Registry.register_and_bind(configuration_class=ConfigB,
                               configuration_constructor=ConfigB.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=ConfigC,
                               configuration_constructor=ConfigC.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(configuration_class=ConfigA,
                                                       component_class=Component,
                                                       name='config_a',
                                                       namespace='testing',
                                                       parameter_variants_only=True)
    assert len(variant_keys) == 8


def test_nested_configuration_variants(
        reset_registry
):
    Registry.register_and_bind(configuration_class=ConfigB,
                               configuration_constructor=ConfigB.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=ConfigC,
                               configuration_constructor=ConfigC.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(configuration_class=ConfigA,
                                                       component_class=Component,
                                                       name='config_a',
                                                       namespace='testing',
                                                       parameter_variants_only=False,
                                                       allow_parameter_variants=False)
    assert len(variant_keys) == 0


def test_nested_configuration_variants_with_allow(
        reset_registry
):
    Registry.register_and_bind(configuration_class=ConfigB,
                               configuration_constructor=ConfigB.get_default,
                               component_class=Component,
                               name='config_b',
                               namespace='testing')
    Registry.register_and_bind(configuration_class=ConfigC,
                               configuration_constructor=ConfigC.get_default,
                               component_class=Component,
                               name='config_c',
                               namespace='testing')

    variant_keys = Registry.register_and_bind_variants(configuration_class=ConfigA,
                                                       component_class=Component,
                                                       name='config_a',
                                                       namespace='testing',
                                                       parameter_variants_only=False,
                                                       allow_parameter_variants=True)
    assert len(variant_keys) == 8


class ConfigD(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=True, type_hint=bool, variants=[False, True])
        config.add_short(name='child', value=RegistrationKey(name='config_e',
                                                             namespace='testing'), is_registration=True)
        return config


@supports_variants
class ConfigE(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=1, type_hint=int, variants=[1, 2])

        return config

    @classmethod
    @add_variant(name='variant1')
    def variant1(
            cls
    ):
        config = cls.get_default()
        config.param_1 = 3
        return config


def test_nested_configuration_variants_with_allow_2(
        reset_registry
):
    Registry.queue_register_and_bind_variants(configuration_class=ConfigD,
                                              component_class=Component,
                                              name='config_d',
                                              namespace='testing',
                                              parameter_variants_only=False,
                                              allow_parameter_variants=True)
    Registry.register_and_bind(configuration_class=ConfigE,
                               configuration_constructor=Configuration.get_default,
                               component_class=Component,
                               name='config_e',
                               namespace='testing')
    variant_keys = Registry.register_and_bind_queued_variants()

    assert len(variant_keys) == 2


class ConfigF(Configuration):

    @classmethod
    def get_default(
            cls
    ):
        config = super().get_default()

        config.add_short(name='param_1', value=True, type_hint=bool, variants=[False, True])
        config.add_short(name='param_2', value=True, type_hint=bool, variants=[False, True])

        config.add_condition(condition=lambda p: p.param_1 == p.param_2)

        return config


def test_variants_with_conditions(
        reset_registry
):
    variant_keys = Registry.register_and_bind_variants(configuration_class=ConfigF,
                                                       component_class=Component,
                                                       name='config_f',
                                                       namespace='testing',
                                                       parameter_variants_only=True)
    assert len(variant_keys) == 2
