from __future__ import annotations

import inspect
import os
from copy import deepcopy
from functools import partial
from typing import Dict, Any, Callable, Optional, TypeVar, Hashable, Type, Iterable, List, Set

from typeguard import check_type

from cinnamon_core import core
from cinnamon_core.core.data import FieldDict, Parameter, ValidationFailureException, ValidationResult, F
from cinnamon_core.utility import logging_utility
from cinnamon_core.utility.python_utility import get_dict_values_combinations

C = TypeVar('C', bound='Configuration')
Constructor = Callable[[Any], C]


class Configuration(FieldDict):
    """
    Generic Configuration class.
    A Configuration specifies the parameters of a Component.
    Configurations store parameters and allow flow control via conditions.

    Differently from a ``FieldDict`` a ``Configuration`` is a extended dictionary that is specific to ``Component``.
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

    def __setitem__(
            self,
            key: Hashable,
            item: Any
    ):
        if isinstance(item, Parameter):
            super().__setitem__(key, item)
        else:
            if key not in self:
                raise KeyError(f'Cannot update the value of a non-existing parameter! Key = {key}')
            self.get(key).value = item
        self.get(key).in_allowed_range()

    @property
    def children(
            self
    ) -> Dict[str, F]:
        return {param_key: param
                for param_key, param in self.items()
                if param.is_child and not param.is_calibration}

    def add(
            self,
            name: str,
            value: Optional[Any] = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Optional[Set[str]] = None,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            affects_serialization: bool = False,
            is_required: bool = False,
            is_child: bool = False,
            is_calibration: bool = False,
            build_from_registration: bool = True,
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
            affects_serialization: if True, the Parameter leads to different serialization processes
            is_required: if True, ``value`` cannot be None
            is_child: if True, ``value`` must be a ``RegistrationKey`` instance
            is_calibration: if True, ``value`` must be a ``RegistrationKey`` instance pointing to a calibration ``Configuration``
            build_from_registration: if True, the ``RegistrationKey`` ``value`` is replaced by its bounded ``Component``
            build_type_hint: the type hint annotation of the built ``Component``
            variants: set of variant values of ``value`` of interest
        """
        self[name] = Parameter(name=name,
                               value=value,
                               type_hint=type_hint,
                               description=description,
                               tags=tags,
                               allowed_range=allowed_range,
                               affects_serialization=affects_serialization,
                               is_required=is_required,
                               is_child=is_child,
                               is_calibration=is_calibration,
                               build_from_registration=build_from_registration,
                               build_type_hint=build_type_hint,
                               variants=variants)

        # is_required condition
        if is_required:
            self.add_condition(name=f'{name}_is_required',
                               condition=lambda p: p[name] is not None)

        def typing_condition(
                parameters: Configuration,
                param_name: Hashable,
                type_hint: Type
        ) -> bool:
            found_param = parameters.get(param_name)
            try:
                if inspect.isclass(found_param.value):
                    return issubclass(found_param.value, type_hint)
                else:
                    check_type(argname=str(found_param.name),
                               value=found_param.value,
                               expected_type=type_hint)
            except TypeError:
                return False
            return True

        # add type_hint condition
        if type_hint is not None and not is_calibration:
            self.add_condition(name=f'{name}_typecheck' if not is_child else f'pre_{name}_typecheck',
                               condition=lambda parameters: partial(typing_condition,
                                                                    param_name=name,
                                                                    type_hint=type_hint)(parameters))

        # add post-build condition if the parameter is registration and should be built
        if is_child and build_from_registration and build_type_hint is not None:
            self.add_condition(name=f'post_{name}_build_typecheck',
                               condition=lambda parameters: partial(typing_condition,
                                                                    param_name=name,
                                                                    type_hint=build_type_hint)(parameters))

        # add variants condition
        # we do not consider allowed_range for variants since we have a lazy condition in __setitem__
        # However, variants space is usually small -> we might consider adding a pre-condition here
        if variants is not None:
            self.add_condition(name=f'{name}_valid_variants',
                               condition=lambda p: len(p.get(name).variants) > 0)

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

    def get_serialization_parameters(
            self
    ) -> Dict[str, Parameter]:
        """
        Returns the current ``Configuration`` instance parameters that can change the data serialization pipeline
        (i.e., those ``Parameter`` that have ``affects_serialization = True``).

        Returns:
            A dictionary with ``Parameter.name`` as keys and ``Parameter.value`` as values
        """
        return {key: param for key, param in self.items() if param.affects_serialization}

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

        for key, value in self.items():
            if isinstance(key, FieldDict):
                key_validation = key.validate(strict=strict)
                if not key_validation.passed:
                    return key_validation

        if 'conditions' not in self:
            return ValidationResult(passed=True)

        for condition_name, condition in self.conditions.items():
            if condition_name.startswith('pre') and self.built:
                continue
            if condition_name.startswith('post') and not self.built:
                continue

            if not condition(self):
                validation_result = ValidationResult(passed=False,
                                                     error_message=f'Condition {condition_name} failed!')
                if strict:
                    raise ValidationFailureException(validation_result=validation_result)

                return validation_result

        return ValidationResult(passed=True)

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
            self.post_build()
        return self.validate(strict=strict)

    def post_build(
            self
    ):
        """
        Checks for parameters that are a ``RegistrationKey`` and calls the ``Registry`` to build the
        bounded ``Component`` instance.

        """
        if not self.built:
            self.built = True
        else:
            return

        for param_key, param in self.items():
            if param.is_child and param.build_from_registration and param.value is not None:
                if 'conditions' in self and f'{param_key}_typecheck' in self.conditions:
                    del self.conditions[f'{param_key}_typecheck']

                if type(param.value) == core.registry.RegistrationKey:
                    param.value = core.registry.Registry.build_component_from_key(registration_key=param.value)
                else:
                    try:
                        components = []
                        for key in param.value:
                            component = core.registry.Registry.build_component_from_key(registration_key=key)
                            components.append(component)
                        param.value = components
                    except TypeError as e:
                        logging_utility.logger.error(e)
                        raise e

    @classmethod
    def get_delta_class_copy(
            cls: type[C],
            params: Dict[str, Any],
            constructor: Optional[Callable[[Any], C]] = None,
            constructor_kwargs: Optional[Dict] = None
    ) -> C:
        """
        Gets a delta copy of the default ``Configuration``.

        Args:
            params: a dictionary with ``Parameter.name`` as keys and new ``Parameter.value`` as values.
            constructor: callable that builds the configuration instance (just like ``get_default()``)
            constructor_kwargs: optional constructor arguments

        Returns:
            A delta copy of the default ``Configuration`` as specified by ``Configuration.get_default()`` method.
        """
        constructor = constructor if constructor is not None else cls.get_default
        constructor_kwargs = constructor_kwargs if constructor_kwargs is not None else {}

        config = constructor(**constructor_kwargs)
        return config.get_delta_copy(params=params)

    def get_delta_copy(
            self: type[C],
            params: Optional[Dict[str, Any]] = None
    ) -> C:
        """
        Gets a delta copy of current ``Configuration``.

        Args:
            params: a dictionary with ``Parameter.name`` as keys and new ``Parameter.value`` as values.

        Returns:
            A delta copy of current ``Configuration``.
        """
        params = params if params is not None else {}

        copy_dict = deepcopy(params)
        copy = deepcopy(self)

        found_keys = []
        for key, value in params.items():
            if key in copy:
                copy.get(key).value = deepcopy(value)
                found_keys.append(key)

        # Remove found keys
        for key in found_keys:
            copy_dict.pop(key)

        if not len(copy_dict):
            return copy

        for child_key, child in copy.children.items():
            copy_dict = {key.replace(f'{child_key}.', '')
                         if key.startswith(child_key) else key: value
                         for key, value in copy_dict.items()}

            # No valid case if child is a RegistrationKey -> we avoid an unnecessary registration
            if copy_dict and isinstance(child.value, core.component.Component):
                copy.get(child_key).value.config = child.value.config.get_delta_copy(params=copy_dict)

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
        value_dict = super().to_value_dict()

        return {key: value.config.to_value_dict() if isinstance(value, core.component.Component) else value
                for key, value in value_dict.items()}

    def show(
            self
    ):
        """
        Displays ``Configuration`` parameters.
        """
        logging_utility.logger.info(f'Displaying {self.__class__.__name__} parameters...')
        parameters_repr = os.linesep.join([param.long_repr() for param_key, param in self.items()])
        logging_utility.logger.info(parameters_repr)


__all__ = ['Configuration', 'ValidationFailureException', 'C']
