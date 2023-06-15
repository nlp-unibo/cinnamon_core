from __future__ import annotations

import inspect
import os
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from typing import Dict, Any, Callable, Optional, Tuple, TypeVar, Hashable, Type, Iterable, List, Set

from typeguard import check_type

from cinnamon_core import core
from cinnamon_core.core.data import FieldDict, Parameter, ValidationResult, ValidationFailureException
from cinnamon_core.utility import logging_utility
from cinnamon_core.utility.python_utility import get_dict_values_combinations

C = TypeVar('C', bound='Configuration')
Constructor = Callable[[Any], C]


@dataclass
class VariantSpec:
    """
    Utility dataclass that stores the decorated method and its variant name.

    Args:
        name: the specified variant name in the ``@add_variant`` decorator
        method: a pointer to the decorated method
    """
    name: str
    tags: core.registry.Tag
    namespace: Optional[str]
    method: Constructor
    class_name: str


def add_variant(
        name: Optional[str] = None,
        tags: core.registry.Tag = None,
        namespace: Optional[str] = None
) -> Callable[[Constructor], Constructor]:
    """
    Marks a ``Configuration`` method as a ``Configuration`` variant.
    A ``Configuration`` variant is a method that returns a ``Configuration`` instance
    (e.g., ``Configuration.get_default()``).

    Args:
        name: unique identifier of the ``Configuration`` variant.
        tags: TODO
        namespace: TODO

    Returns:
        The decorated ``Configuration`` method.
    """

    def _add_variant(
            method: Constructor,

    ) -> Constructor:
        method.variant = True
        method.variant_name = name if name is not None else method.__name__
        method.tags = tags
        method.namespace = namespace
        method.class_name = method.__qualname__.split('.')[0]
        return method

    return _add_variant


# TODO: make it a metaclass to allow inheritance
def supports_variants(
        cls
):
    """
    Class-level decorator that makes a class sensitive to ``@add_variant`` decorated methods.
    This decorator checks for all ``@add_variant`` decorated methods and stores their list in a class-level attribute.

    Args:
        cls: the ``Configuration`` class

    Returns:
        The decorated ``Configuration`` class
    """
    variants = list(getattr(cls, 'variants', ()))
    for method in cls.__dict__.values():
        if isinstance(method, classmethod) or isinstance(method, staticmethod):
            method = method.__func__

        if getattr(method, "variant", False):
            variant_name = getattr(method, 'variant_name', None)
            tags = getattr(method, 'tags', None)
            namespace = getattr(method, 'namespace', None)
            class_name = getattr(method, 'class_name', None)
            variants.append(VariantSpec(name=variant_name,
                                        method=method,
                                        class_name=class_name,
                                        tags=tags,
                                        namespace=namespace))
    cls.variants = tuple(variants)
    return cls


# TODO: re-integrate search APIs?
@supports_variants
class Configuration(FieldDict):
    """
    Generic Configuration class.
    A Configuration specifies the parameters of a Component.
    Configurations store parameters and allow flow control via conditions.

    Differently from a ``FieldDict`` a ``Configuration`` is a extended dictionary that is specific to ``Component``.
    """

    variants: Tuple[VariantSpec] = tuple()

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

    def add(
            self,
            param: Parameter
    ):
        """
        Adds a ``Parameter`` to the ``Configuration``.
        By default, ``Parameter``'s default conditions are added as well.

        Args:
            param: the ``Parameter`` instance to add
        """
        self[param.name] = param

        # is_required condition
        if param.is_required:
            self.add_condition(name=f'{param.name}_is_required',
                               condition=lambda p: p[param.name] is not None)

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
        if param.type_hint is not None and not param.is_calibration:
            self.add_condition(name=f'{param.name}_typecheck',
                               condition=lambda parameters: partial(typing_condition,
                                                                    param_name=param.name,
                                                                    type_hint=param.type_hint)(parameters))

        # add post-build condition if the parameter is registration and should be built
        if param.is_registration and param.build_from_registration and param.build_type_hint is not None:
            self.add_condition(name=f'{param.name}_build_typecheck',
                               condition=lambda parameters: partial(typing_condition,
                                                                    param_name=param.name,
                                                                    type_hint=param.build_type_hint)(parameters),
                               stage='post')

        # add variants condition
        # we do not consider allowed_range for variants since we have a lazy condition in __setitem__
        # However, variants space is usually small -> we might consider adding a pre-condition here
        if param.variants is not None:
            self.add_condition(name=f'{param.name}_valid_variants',
                               condition=lambda p: len(p.get(param.name).variants) > 0)

    def add_short(
            self,
            name: str,
            value: Optional[Any] = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Optional[Set[str]] = None,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            affects_serialization: bool = False,
            is_required: bool = False,
            is_registration: bool = False,
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
            is_registration: if True, ``value`` must be a ``RegistrationKey`` instance
            is_calibration: if True, ``value`` must be a ``RegistrationKey`` instance pointing to a calibration ``Configuration``
            build_from_registration: if True, the ``RegistrationKey`` ``value`` is replaced by its bounded ``Component``
            build_type_hint: the type hint annotation of the built ``Component``
            variants: set of variant values of ``value`` of interest
        """
        param = Parameter(name=name,
                          value=value,
                          type_hint=type_hint,
                          description=description,
                          tags=tags,
                          allowed_range=allowed_range,
                          affects_serialization=affects_serialization,
                          is_required=is_required,
                          is_registration=is_registration,
                          is_calibration=is_calibration,
                          build_from_registration=build_from_registration,
                          build_type_hint=build_type_hint,
                          variants=variants)
        return self.add(param=param)

    def get_variants_combinations(
            self,
            registrations_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Gets all possible ``Configuration`` variant combinations of current ``Configuration``
        instance based on specified variants.
        There exist two different methods to specify variants
        - ``Parameter``-based: via ``variants`` field of ``Parameter``
        - ``Configuration``-based: via ``@supports_variants`` and ``@add_variant`` decorators

        Args:
            registrations_only: TODO

        Returns:
            List of variant combinations.
            Each variant combination is a dictionary with ``Parameter.name`` as keys and ``Parameter.value`` as values
        """

        parameters = {}
        for param_key, param in self.items():
            if param.variants is not None and len(param.variants):
                if (registrations_only and param.is_registration) or not registrations_only:
                    parameters[param_key] = param.variants
        combinations = get_dict_values_combinations(params_dict=parameters)
        return [comb for comb in combinations if self.get_delta_copy(params=comb).validate(strict=False).passed]

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

    def add_condition(
            self,
            condition: Callable[[Configuration], bool],
            name: Optional[str] = None,
            stage: str = 'pre'
    ):
        """
        Adds a condition to current ``Configuration``.
        Since a ``Configuration`` can have parameters pointing to other ``Configuration``, we distinguish between
        two stages for conditions evaluation.
        - Pre-build conditions: all conditions that do not concern the ``Configuration`` build phase
        - Post-build conditions all conditions that must be verified after the ``Configuration`` build phase

        The build phase is issued at ``Component`` initialization and concerns the retrieval of ``Component`` instances
        bounded to the specified ``RegistrationKey`` parameters.

        Args:
            condition: a function that receives as input the current ``Configuration`` and returns a boolean
            name: a unique identifier of the condition (mainly for readability and debugging purposes)
            stage: 'pre' for pre-build conditions and 'post' for post-build conditions

        Raises:
            ``AttributeError``: if the specified ``stage`` argument is not supported.
        """

        if stage not in ['pre', 'post']:
            raise AttributeError(f'Invalid stage passed! Got {stage} but allowed values are ["pre", "post"]')

        # Add conditions if first time
        if 'conditions' not in self:
            self.add_short(name='conditions',
                           value={},
                           type_hint=Dict[str, Dict[str, Callable[[Configuration], bool]]],
                           description='Stores conditions (callable boolean evaluators) '
                                       'that are used to assess the validity and correctness of this ParameterDict')

        if name is None:
            name = f'condition_{len(self.conditions) + 1}'
        self.conditions.setdefault(stage, {}).setdefault(name, condition)

    def validate(
            self,
            stage: str = 'pre',
            strict: bool = True
    ) -> ValidationResult:
        """
        Calls all stage-related conditions to assess the correctness of the current ``Configuration``.

        Args:
            stage: 'pre' for pre-build conditions and 'post' for post-build conditions
            strict: if True, a failed validation process will raise ``InvalidConfigurationException``

        Returns:
            A ``ValidationResult`` object that stores the boolean result of the validation process along with
            an error message if the result is ``False``.

        Raises:
            ``InvalidConfigurationException``: if ``strict = True`` and the validation process failed
        """

        if stage not in ['pre', 'post']:
            raise AttributeError(f'Invalid stage passed! Got {stage} but allowed values are ["pre", "post"]')

        if 'conditions' not in self:
            return ValidationResult(passed=True)

        if 'conditions' not in self and stage not in self.conditions:
            return ValidationResult(passed=True)

        if stage not in self.conditions:
            return ValidationResult(passed=True)

        for condition_name, condition in self.conditions[stage].items():
            if not condition(self):
                validation_result = ValidationResult(passed=False,
                                                     error_message=f'[Stage = {stage}] '
                                                                   f'Condition {condition_name} failed!')
                if strict:
                    raise ValidationFailureException(validation_result=validation_result)

                return validation_result

        return ValidationResult(passed=True)

    def post_build(
            self,
            serialization_id: Optional[int] = None
    ):
        """
        Checks for parameters that are a ``RegistrationKey`` and calls the ``Registry`` to build the
        bounded ``Component`` instance.

        Args:
            serialization_id: The ``Component`` unique identifier for serialization.
        """
        serialization_id = serialization_id if serialization_id is not None else 0

        for index in self.keys():
            param = self.get(index)
            if param.is_registration and param.build_from_registration and param.value is not None:
                serialization_id += 1
                if type(param.value) == core.registry.RegistrationKey:
                    param.value = core.registry.Registry.build_component_from_key(
                        registration_key=param.value,
                        build_args={'serialization_id': serialization_id})
                else:
                    try:
                        components = []
                        for key in param.value:
                            component = core.registry.Registry.build_component_from_key(
                                registration_key=key,
                                build_args={'serialization_id': serialization_id})
                            components.append(component)
                            serialization_id += 1
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
            constructor: TODO
            constructor_kwargs: TODO

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
        # copy = self.get_default()
        # for param_key, param in self.items():
        #     copy.add(deepcopy(param))

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

        children = {param_key: param for param_key, param in copy.items()
                    if param.is_registration and not param.is_calibration}
        for child_key, child in children.items():
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


__all__ = ['add_variant', 'supports_variants', 'Configuration', 'ValidationFailureException', 'C']
