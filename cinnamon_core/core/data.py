from __future__ import annotations

import os
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional, Callable, Dict, Type, Set, Union, Iterable, Tuple, Hashable, TypeVar, List

from typeguard import check_type

F = TypeVar('F', bound='Field')


class InconsistentTypeException(Exception):

    def __init__(self, expected_type, given_type):
        super().__init__(f'Expected parameter value with type {expected_type} but got {given_type}')


class OutOfRangeParameterValueException(Exception):

    def __init__(self, value):
        super().__init__(f'Parameter value {value} not in allowed range')


@dataclass
class ValidationResult:
    """
    Utility dataclass to store conditions evaluation result (see ``Configuration.validate()``).

    Args:
        passed: True if all conditions are True
        error_message: a string message reporting which condition failed during the evaluation process.
    """

    passed: bool
    error_message: Optional[str] = None


class ValidationFailureException(Exception):

    def __init__(
            self,
            validation_result: ValidationResult
    ):
        super().__init__(f'The validation process has failed!{os.linesep}'
                         f'Passed: {validation_result.passed}{os.linesep}'
                         f'Error message: {validation_result.error_message}')


class Field:
    """
    A generic field wrapper that allows
    - type annotation
    - textual description metadata
    - tags metadata for categorization and general-purpose retrieval
    """

    def __init__(
            self,
            name: Hashable,
            value: Any = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Optional[Set[str]] = None,
    ):
        """
        A ``Field`` constructor method.

        Args:
            name: unique identifier of the ``Field`` instance
            value: the wrapped value of the ``Field`` instance
            type_hint: type annotation concerning ``value``
            description: a string description of the ``Field`` for readability purposes
            tags: a set of string tags to mark the ``Field`` instance with metadata.
        """
        self.name = name
        self.value = value
        self.type_hint = type_hint
        self.description = description
        self.tags = tags if tags is not None else set()

    def short_repr(
            self
    ) -> str:
        return f'{self.value}'

    def long_repr(
            self
    ) -> str:
        return (f'name: {self.name} --{os.linesep}'
                f'value: {self.value} --{os.linesep}'
                f'type_hint: {self.type_hint} --{os.linesep}'
                f'description: {self.description} --{os.linesep}'
                f'tags: {self.tags}--{os.linesep}')

    def __str__(
            self
    ) -> str:
        return self.short_repr()

    def __repr__(
            self
    ) -> str:
        return self.short_repr()

    def __hash__(
            self
    ) -> int:
        return hash(str(self))

    def __eq__(
            self,
            other: type[F]
    ) -> bool:
        """
        Two ``Field`` instances are equal iff they have the same name and value.

        Args:
            other: another ``Field`` instance

        Returns:
            True if the two ``Field`` instances are equal.
        """
        name_condition = lambda other: self.name == other.name
        value_condition = lambda other: self.value == other.value
        return name_condition(other) and value_condition(other)


class FieldDict(dict):
    """
    A Python dictionary extension whose values are ``Field`` instances.
    The ``Field.name`` attribute is used as key.
    """

    def __init__(
            self,
            *args,
            **kwargs
    ):
        super(FieldDict, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self.add(name=k, value=v, type_hint=type(v))

        if kwargs:
            for k, v in kwargs.items():
                self.add(name=k, value=v, type_hint=type(v))

    def __getattr__(
            self,
            item
    ):
        field = self.get(item)
        if field is None:
            raise AttributeError(f'Could not find attribute {item}')
        return field.value

    def __setattr__(
            self,
            key,
            value
    ):
        self.__setitem__(key, value)

    def __delattr__(
            self,
            item
    ):
        self.__delitem__(item)

    def __delitem__(
            self,
            key
    ):
        super().__delitem__(key)
        del self.__dict__[key]

    def __setitem__(
            self,
            key: Hashable,
            item: Union[Field, Any]
    ):
        if isinstance(item, Field):
            super().__setitem__(key, item)
        else:
            assert key in self, f'Cannot find or update a non-existing field! Key = {key}'
            self.get(key).value = item

    def __getitem__(
            self,
            item: Union[Hashable, Tuple[Hashable, bool]]
    ) -> F:
        return_value = True
        if type(item) == tuple:
            item, return_value = item

        if not len(self.search_by_name(name=item)):
            return super().__getitem__(item)

        return super().__getitem__(item).value if return_value else super().__getitem__(item)

    def __str__(
            self
    ) -> str:
        return str(self.to_value_dict())

    def to_value_dict(
            self
    ):
        def convert_field(field: F):
            try:
                check_type('field.value', field.value, Union[type(self), List[type(self)]])
            except TypeError:
                return field.value

            if type(field.value) == type(self):
                return field.value.to_value_dict()
            else:
                return [item.to_value_dict() for item in field.value]

        return {key: convert_field(field) for key, field in self.items() if key != 'conditions'}

    def add(
            self,
            name: Hashable,
            value: Any = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Optional[Set[str]] = None
    ):
        """
        Adds a ``Field`` to the ``FieldDict`` via its implicit format.

        Args:
            name: unique identifier of the ``Field`` instance
            value: the wrapped value of the ``Field`` instance
            type_hint: type annotation concerning ``value``
            description: a string description of the ``Field`` for readability purposes
            tags: a set of string tags to mark the ``Field`` instance with metadata.
        """

        self[name] = Field(name=name,
                           value=value,
                           type_hint=type_hint,
                           description=description,
                           tags=tags)

        def typing_condition(
                fields: FieldDict,
                field_name: Hashable,
                type_hint: Type
        ) -> bool:
            try:
                found_param = fields.get(field_name)
                check_type(argname=str(found_param.name),
                           value=found_param.value,
                           expected_type=type_hint)
            except TypeError:
                return False
            return True

        # add type_hint condition
        if type_hint is not None:
            self.add_condition(name=f'{name}_typecheck',
                               condition=lambda fields: partial(typing_condition,
                                                                field_name=name,
                                                                type_hint=type_hint)(fields))

    def add_condition(
            self,
            condition: Callable[[FieldDict], bool],
            name: Optional[str] = None,
    ):
        """
        Adds a condition to current ``FieldDict``.

        Args:
            condition: a function that receives as input the current ``FieldDict`` and returns a boolean
            name: a unique identifier of the condition (mainly for readability and debugging purposes)

        Raises:
            ``AttributeError``: if the specified ``stage`` argument is not supported.
        """
        # Add conditions if first time
        if 'conditions' not in self:
            self.add(name='conditions',
                     value={},
                     type_hint=Dict[str, Callable[[FieldDict], bool]],
                     description='Stores conditions (callable boolean evaluators) '
                                 'that are used to assess the validity and correctness of this ParameterDict')

        if name is None:
            name = f'condition_{len(self.conditions) + 1}'
        self.conditions.setdefault(name, condition)

    def validate(
            self,
            strict: bool = True
    ) -> ValidationResult:
        """
        Calls all stage-related conditions to assess the correctness of the current ``FieldDict``.

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
            if not condition(self):
                validation_result = ValidationResult(passed=False,
                                                     error_message=f'Condition {condition_name} failed!')
                if strict:
                    raise ValidationFailureException(validation_result=validation_result)

                return validation_result

        return ValidationResult(passed=True)

    def search_by_tag(
            self,
            tags: Optional[Union[Set[str], str]] = None,
            exact_match: bool = True
    ) -> Dict[str, Any]:
        """
        Searches for all ``Field`` that match specified tags set.

        Args:
            tags: a set of string tags to look for
            exact_match: if True, only the ``Field`` with ``Field.tags`` that exactly match ``tags`` will be returned

        Returns:
            A dictionary with ``Field.name`` as keys and ``Field`` as values
        """
        if not type(tags) == set:
            tags = {tags}

        exatch_match_condition = lambda field: exact_match and field.tags == tags
        partial_match_condition = lambda field: not exact_match and field.tags.intersection(tags) == tags
        return {key: field.value for key, field in self.items()
                if exatch_match_condition(field) or partial_match_condition(field) or tags is None}

    def search_by_name(
            self,
            name: Optional[Hashable] = None
    ) -> Dict[str, Any]:
        """
        Searches for all ``Field`` that match the specified name.

        Args:
            name: unique identifier of the ``Field`` instance.

        Returns:
            A dictionary with ``Field.name`` as keys and ``Field`` as values
        """
        return {key: field.value for key, field in self.items() if key == name or name is None}


class Parameter(Field):
    """
    A ``Field`` extension that is ``Configuration`` specific.
    """

    def __init__(
            self,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            affects_serialization: bool = False,
            is_required: bool = False,
            is_child: bool = False,
            is_calibration: bool = False,
            build_from_registration: bool = True,
            build_type_hint: Optional[Type] = None,
            variants: Optional[Iterable] = None,
            **kwargs
    ):
        """
        The ``Parameter`` constructor

        Args:
            allowed_range: allowed range of values for ``value``
            affects_serialization: if True, the Parameter leads to different serialization processes
            is_required: if True, ``value`` cannot be None
            is_child: if True, ``value`` must be a ``RegistrationKey`` instance
            is_calibration: if True, ``value`` must be a ``RegistrationKey`` instance pointing to a calibration ``Configuration``
            build_from_registration: if True, the ``RegistrationKey`` ``value`` is replaced by its bounded ``Component``
            build_type_hint: the type hint annotation of the built ``Component``
            variants: set of variant values of ``value`` of interest
        """

        super().__init__(**kwargs)
        self.allowed_range = allowed_range
        self.affects_serialization = affects_serialization
        self.is_required = is_required
        self.is_child = is_child
        self.is_calibration = is_calibration
        self.build_from_registration = build_from_registration
        self.build_type_hint = build_type_hint
        self.variants = variants

    def in_allowed_range(
            self
    ):
        """
        Checks if ``Parameter.value`` is in ``Parameter.allowed_range``.

        Raises:
            ``OutOfRangeParameterValueException``: if ``Parameter.value`` is not in the specified value range.
        """

        if self.value is not None and self.allowed_range is not None and not self.allowed_range(self.value):
            raise OutOfRangeParameterValueException(value=self.value)

    def long_repr(
            self
    ) -> str:
        long_repr = super().long_repr()
        return long_repr + (f'affects_serialization: {self.affects_serialization} -- {os.linesep}'
                            f'is_required: {self.is_required} --{os.linesep}'
                            f'is_child: {self.is_child} --{os.linesep}'
                            f'is_calibration: {self.is_calibration} --{os.linesep}'
                            f'build_from_registration: {self.build_from_registration} --{os.linesep}'
                            f'build_type_hint: {self.build_type_hint} --{os.linesep}'
                            f'variants: {self.variants}')
