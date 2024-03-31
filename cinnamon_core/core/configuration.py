from __future__ import annotations

import os
from copy import deepcopy
from functools import partial
from typing import Dict, Any, Callable, Optional, TypeVar, Type, Iterable, List, Set, Union

from cinnamon_core import core
from cinnamon_core.core.data import Data, Field, ValidationFailureException, ValidationResult, F, typing_condition, \
    allowed_range_condition
from cinnamon_core.utility import logging_utility
from cinnamon_core.utility.python_utility import get_dict_values_combinations
from pandas import json_normalize

C = TypeVar('C', bound='Configuration')
Constructor = Callable[[Any], C]


class Param(Field):
    """
    A ``Field`` extension that is ``Configuration`` specific.
    """

    def __init__(
            self,
            is_child: bool = False,
            build_type_hint: Optional[Type] = None,
            variants: Optional[Iterable] = None,
            **kwargs
    ):
        """
        The ``Parameter`` constructor

        Args:
            is_child: if True, ``value`` must be a ``RegistrationKey`` instance
            is_calibration: if True, ``value`` must be a ``RegistrationKey`` instance pointing to a calibration ``Configuration``
            build_type_hint: the type hint annotation of the built ``Component``
            variants: set of variant values of ``value`` of interest
        """

        super().__init__(**kwargs)
        self.is_child = is_child
        self.build_type_hint = build_type_hint
        self.variants = variants

        if is_child:
            self.tags.add('child')

    def long_repr(
            self
    ) -> str:
        long_repr = super().long_repr()
        return long_repr + (f'is_child: {self.is_child} {os.linesep}'
                            f'build_type_hint: {self.build_type_hint} {os.linesep}'
                            f'variants: {self.variants}')


class Configuration(Data):
    """
    Generic Configuration class.
    A Configuration specifies the parameters of a Component.
    Configurations store parameters and allow flow control via conditions.

    A ``Configuration`` is a ``Data`` extension specific to ``Component``.
    """

    def __init__(
            self,
            **kwargs
    ):
        super().__init__(**kwargs)
        self.add(name='built',
                 value=False,
                 type_hint=bool,
                 is_required=True,
                 description="Internal status field that is True when post_build() is invoked, False otherwise.")

    @property
    def children(
            self
    ) -> Dict[str, F]:
        return {param_key: param for param_key, param in self.__dict__.items() if param.is_child}

    def add(
            self,
            name: str,
            value: Optional[Any] = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Optional[Set[str]] = None,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            is_required: bool = False,
            is_child: bool = False,
            build_type_hint: Optional[Type] = None,
            variants: Optional[Iterable] = None,
    ):
        """
        Adds a Parameter to the Configuration via its implicit format.
        By default, Parameter's default conditions are added as well.

        Args:
            name: unique identifier of the Parameter
            value: value of the Parameter
            type_hint: the type hint annotation of ``value``
            description: a string description of the ``Parameter`` for readability purposes
            tags: a set of string tags to mark the ``Parameter`` instance with metadata.
            allowed_range: allowed range of values for ``value``
            is_required: if True, ``value`` cannot be None
            is_child: if True, ``value`` must be a ``RegistrationKey`` instance
            build_type_hint: the type hint annotation of the built ``Component``
            variants: set of variant values of ``value`` of interest
        """
        if is_child:
            type_hint = core.registry.RegistrationKey

        if name in self.__dict__:
            param = self.get(name)
            param.value = param.value if value is None else value
            param.type_hint = param.type_hint if type_hint is None else type_hint
            param.description = param.description if description is None else description
            param.tags = param.tags if tags is None else tags
            param.allowed_range = param.allowed_range if allowed_range is None else allowed_range
            param.build_type_hint = param.build_type_hint if build_type_hint is None else build_type_hint
            param.variants = param.variants if variants is None else variants
        else:
            self.__dict__[name] = Param(name=name,
                                        value=value,
                                        type_hint=type_hint,
                                        description=description,
                                        tags=tags,
                                        allowed_range=allowed_range,
                                        is_required=is_required,
                                        is_child=is_child,
                                        build_type_hint=build_type_hint,
                                        variants=variants)

        if is_required:
            self.add_condition(name=f'{name}_is_required',
                               condition=lambda config: config.get(name) is not None)

        if type_hint is not None:
            self.add_condition(name=f'{name}_typecheck',
                               condition=lambda config: partial(typing_condition,
                                                                field_name=name,
                                                                type_hint=type_hint)(config),
                               description=f'Checks if {name} if of type {type_hint}.',
                               tags={'typechecking', 'pre-built'})

        if is_child and build_type_hint is not None:
            self.add_condition(name=f'post_{name}_build_typecheck',
                               condition=lambda config: partial(typing_condition,
                                                                param_name=name,
                                                                type_hint=build_type_hint)(config),
                               description=f'Checks if {name} is of type {build_type_hint}',
                               tags={'typechecking', 'post-built'})

        if allowed_range is not None:
            self.add_condition(name=f'{name}_allowed_range',
                               condition=lambda config: partial(allowed_range_condition,
                                                                field_name=name)(config),
                               description=f'Checks if {name} is in allowed range.',
                               tags={'allowed_range'})

        if variants is not None:
            self.add_condition(name=f'{name}_valid_variants',
                               condition=lambda p: len(p.get(name).variants) > 0,
                               description='Check if variants is not an empty set',
                               tags={'variants'})

    def validate(
            self,
            strict: bool = True
    ) -> ValidationResult:
        """
        Calls all stage-related conditions to assess the correctness of the current ``Configuration``.

        Args:
            strict: if True, a failed validation process will raise ``InvalidConfigurationException``

        Returns:
            A ``ValidationResult`` object that stores the boolean result of the validation process along with
            an error message if the result is ``False``.

        Raises:
            ``ValidationFailureException``: if ``strict = True`` and the validation process failed
        """

        if self.built:
            for child_name, child in self.children.items():
                child_validation = child.value.config.validate(strict=strict)
                if not child_validation.passed:
                    return child_validation

        for condition_name, condition in self.search_condition(conditions=[
            lambda field: 'condition' in field.tags,
            lambda field: f'{"pre" if self.built else "post"}' not in field.tags
        ]).items():
            if not condition(self):
                validation_result = ValidationResult(passed=False,
                                                     error_message=f'Condition {condition_name} failed!',
                                                     source=self.__class__.__name__)
                if strict:
                    raise ValidationFailureException(validation_result=validation_result)

                return validation_result

        return ValidationResult(passed=True,
                                source=self.__class__.__name__)

    def fully_validate(
            self,
            strict: bool = True
    ):
        """
        Validates a ``Configuration`` in all stages.
        If the ``Configuration`` has yet to run post_build(), the method is then invoked.
        Note that this method alters the internal status of the ``Configuration``.
        It is recommended to be executed on a copy.

        Args:
            strict: if True, a failed validation process will raise ``InvalidConfigurationException``

        Returns:
            A ``ValidationResult`` object that stores the boolean result of the validation process along with
            an error message if the result is ``False``.

        Raises:
            ``ValidationFailureException``: if ``strict = True`` and the validation process failed
        """

        if not self.built:
            self.validate(strict=strict)
            try:
                self.post_build()
            except Exception as e:
                if strict:
                    raise e
                else:
                    return ValidationResult(passed=False,
                                            error_message=str(e),
                                            source=self.__class__.__name__)
        return self.validate(strict=strict)

    def post_build(
            self
    ):
        """
        Checks for parameters that are a ``RegistrationKey`` and calls the ``Registry`` to build the
        bounded ``Component`` instance.

        """
        if self.built:
            return

        for child_name, child in self.children.items():
            if child.value is not None:
                child.value = core.registry.Registry.build_component_from_key(registration_key=child.value)

        self.built = True

    @classmethod
    def get_delta_class_copy(
            cls: type[C],
            constructor: Optional[Callable[[Any], Configuration]] = None,
            constructor_kwargs: Optional[Dict] = None,
            **kwargs
    ) -> C:
        """
        Gets a delta copy of the default ``Configuration``.

        Args:
            constructor: callable that builds the configuration instance (just like ``get_default()``)
            constructor_kwargs: optional constructor arguments

        Returns:
            A delta copy of the default ``Configuration`` as specified by ``Configuration.get_default()`` method.
        """
        constructor = constructor if constructor is not None else cls.get_default
        constructor_kwargs = constructor_kwargs if constructor_kwargs is not None else {}

        config = constructor(**constructor_kwargs)
        return config.get_delta_copy(**kwargs)

    def get_delta_copy(
            self: type[C],
            **kwargs
    ) -> C:
        """
        Gets a delta copy of current ``Configuration``.

        Returns:
            A delta copy of current ``Configuration``.
        """
        copy = deepcopy(self)

        found_keys = []
        for key, value in kwargs.items():
            if key in self.fields:
                copy.get(key).value = deepcopy(value)
                found_keys.append(key)

        # Remove found keys
        for key in found_keys:
            kwargs.pop(key)

        if not len(kwargs):
            return copy

        for child_key, child in copy.children.items():
            if isinstance(child.value, core.component.Component):
                copy.get(child_key).value.config = child.value.config.get_delta_copy(**kwargs)

        if len(kwargs):
            raise RuntimeError(f'Expected to not have remaining delta parameters, but got {kwargs}.')

        return copy

    @classmethod
    def get_default(
            cls: Type[C]
    ) -> C:
        """
        Returns the default Configuration instance.

        Returns:
            Configuration instance.
        """
        return cls()

    def to_value_dict(
            self
    ):
        value_dict = {}
        for child_name, child in self.children.items():
            if isinstance(child, core.component.Component):
                value_dict.update(child.config.to_value_dict())

        return json_normalize(value_dict)

    def get_variants_combinations(
            self,
            validate: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Gets all possible ``Configuration`` variant combinations of current ``Configuration``
        instance based on specified variants.
        There exist two different methods to specify variants
        - ``Parameter``-based: via ``variants`` field of ``Parameter``
        - ``Configuration``-based: via ``@supports_variants`` and ``@add_variant`` decorators

        Args:
            validate: if True, only valid configuration variants are returned.

        Returns:
            List of variant combinations.
            Each variant combination is a dictionary with ``Parameter.name`` as keys and ``Parameter.value`` as values
        """

        parameters = {}
        for param_key, param in self.items():
            if param.variants is not None and len(param.variants):
                parameters[param_key] = param.variants
        combinations = get_dict_values_combinations(params_dict=parameters)
        if validate:
            return [comb for comb in combinations
                    if self.get_delta_copy(params=comb).fully_validate(strict=False).passed]
        else:
            return combinations

    def show(
            self,
    ):
        """
        Displays ``Configuration`` parameters.
        """
        logging_utility.logger.info(f'Displaying {self.__class__.__name__} parameters...')
        parameters_repr = os.linesep.join(
            [f'{key}: {value}' for key, value in self.to_value_dict().items()])
        logging_utility.logger.info(parameters_repr)


__all__ = ['Configuration', 'ValidationFailureException', 'C']
