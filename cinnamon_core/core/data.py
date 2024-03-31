from __future__ import annotations

import os
from dataclasses import dataclass
from functools import partial
from typing import Any, Optional, Callable, Dict, Type, Set, Union, TypeVar, List

from typeguard import check_type

F = TypeVar('F', bound='Field')
Tags = Optional[Set[str]]


class OutOfRangeParameterValueException(Exception):

    def __init__(self, value):
        super().__init__(f'Parameter value {value} not in allowed range')


class InconsistentTypeException(Exception):

    def __init__(self, expected_type, given_type):
        super().__init__(f'Expected parameter value with type {expected_type} but got {given_type}')


@dataclass
class ValidationResult:
    """
    Utility dataclass to store conditions evaluation result (see ``Configuration.validate()``).

    Args:
        passed: True if all conditions are True
        error_message: a string message reporting which condition failed during the evaluation process.
    """

    passed: bool
    source: str
    error_message: Optional[str] = None


class ValidationFailureException(Exception):

    def __init__(
            self,
            validation_result: ValidationResult
    ):
        super().__init__(f'Source: {validation_result.source}{os.linesep}'
                         f'The validation process has failed!{os.linesep}'
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
            name: str,
            value: Any = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Tags = None,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            is_required: bool = False,
    ):
        """
        A ``Field`` constructor method.

        Args:
            name: unique identifier of the ``Field`` instance
            value: the wrapped value of the ``Field`` instance
            type_hint: type annotation concerning ``value``
            description: a string description of the ``Field`` for readability purposes
            tags: a set of string tags to mark the ``Field`` instance with metadata.
            allowed_range: allowed range of values for ``value``
            is_required: if True, ``value`` cannot be None
        """
        self.name = name
        self.value = value
        self.type_hint = type_hint
        self.description = description
        self.tags = set(tags) if tags is not None else set()
        self.allowed_range = allowed_range
        self.is_required = is_required

        if is_required:
            self.tags.add('required')

    def short_repr(
            self
    ) -> str:
        return f'{self.name}: {self.value}'

    def long_repr(
            self
    ) -> str:
        return (f'name: {self.name} {os.linesep}'
                f'value: {self.value} {os.linesep}'
                f'type_hint: {self.type_hint} {os.linesep}'
                f'description: {self.description} {os.linesep}'
                f'tags: {self.tags} {os.linesep}'
                f'is_required: {self.is_required} {os.linesep}')

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
        return self.name == other.name and self.value == other.value


def typing_condition(
        data: Data,
        field_name: str,
        type_hint: Type
) -> bool:
    try:
        found_param = data.get(field_name)
        check_type(argname=str(found_param.name),
                   value=found_param.value,
                   expected_type=type_hint)
    except TypeError:
        return False
    return True


def allowed_range_condition(
        data: Data,
        field_name: str,
):
    found_param = data.get(field_name)

    if found_param.value is not None and not found_param.allowed_range(found_param.value):
        return False
    return True


class Data:
    """
    TODO: write documentation
    """

    def __init__(
            self,
            **kwargs
    ):
        if kwargs:
            for k, v in kwargs.items():
                self.add(name=k,
                         value=v)

    def __setattr__(
            self,
            key,
            value
    ):
        self.add(name=key, value=value)

    def __getattribute__(
            self,
            name
    ):
        attr = object.__getattribute__(self, name)
        if isinstance(attr, Field):
            return attr.value
        return attr

    def __str__(
            self
    ) -> str:
        return str(self.to_value_dict())

    @property
    def conditions(
            self
    ) -> Dict[str, Field]:
        return {key: field for key, field in self.__dict__.items() if
                isinstance(field, Field) and 'condition' in field.tags}

    @property
    def fields(
            self
    ) -> Dict[str, Field]:
        return {key: field for key, field in self.__dict__.items()
                if isinstance(field, Field) and 'condition' not in field.tags}

    @property
    def values(
            self
    ) -> Dict[str, Any]:
        return {key: field.value for key, field in self.__dict__.items()
                if isinstance(field, Field) and 'condition' not in field.tags}

    @property
    def children(
            self
    ) -> Dict[str, Data]:
        return {key: field.value for key, field in self.__dict__.items() if isinstance(field, Field)
                and isinstance(field.value, Data)}

    def get(
            self,
            name: str,
            default: Any = None
    ) -> Optional[Field]:
        try:
            return self.__dict__[name]
        except AttributeError:
            return default

    def add(
            self,
            name: str,
            value: Any = None,
            type_hint: Optional[Type] = None,
            description: Optional[str] = None,
            tags: Tags = None,
            allowed_range: Optional[Callable[[Any], bool]] = None,
            is_required: bool = False,
    ):
        """
        Adds a ``Field`` to the ``Data`` via its implicit format.

        Args:
            name: unique identifier of the ``Field`` instance
            value: the wrapped value of the ``Field`` instance
            type_hint: type annotation concerning ``value``
            description: a string description of the ``Field`` for readability purposes
            tags: a set of string tags to mark the ``Field`` instance with metadata.
            allowed_range: allowed range of values for ``value``
            is_required: if True, ``value`` cannot be None
        """

        if name in self.__dict__:
            field = self.get(name)
            field.value = field.value if value is None else value
            field.type_hint = field.type_hint if type_hint is None else type_hint
            field.description = field.description if description is None else description
            field.tags = field.tags if tags is None else tags
            field.allowed_range = field.allowed_range if allowed_range is None else allowed_range
        else:
            self.__dict__[name] = Field(name=name,
                                        value=value,
                                        type_hint=type_hint,
                                        description=description,
                                        tags=tags,
                                        allowed_range=allowed_range,
                                        is_required=is_required)

        if is_required:
            self.add_condition(name=f'{name}_is_required',
                               condition=lambda data: data.get(name) is not None)

        if type_hint is not None:
            self.add_condition(name=f'{name}_typecheck',
                               condition=lambda data: partial(typing_condition,
                                                              field_name=name,
                                                              type_hint=type_hint)(data),
                               description=f'Checks if {name} if of type {type_hint}.',
                               tags={'typechecking'})

        if allowed_range is not None:
            self.add_condition(name=f'{name}_allowed_range',
                               condition=lambda data: partial(allowed_range_condition,
                                                              field_name=name)(data),
                               description=f'Checks if {name} is in allowed range.',
                               tags={'allowed_range'})

    def add_condition(
            self,
            condition: Callable[[Data], bool],
            name: str,
            description: Optional[str] = None,
            tags: Tags = None,
    ):
        """
        Adds a condition to be validated.

        Args:
            condition: a function that receives as input the current ``Data`` instance and returns a boolean.
            name: unique identifier.
            description: a string description for readability purposes.
            tags: a set of string tags to mark the condition with metadata.
        """

        tags = set() if tags is None else tags
        tags.add('condition')
        self.add(name=name,
                 value=condition,
                 description=description,
                 tags=tags)

    def validate(
            self,
            strict: bool = True
    ) -> ValidationResult:
        """
        Calls all stage-related conditions to assess the correctness of the current ``Data``.

        Args:
            strict: if True, a failed validation process will raise ``InvalidConfigurationException``

        Returns:
            A ``ValidationResult`` object that stores the boolean result of the validation process along with
            an error message if the result is ``False``.

        Raises:
            ``ValidationFailureException``: if ``strict = True`` and the validation process failed
        """

        for child_name, child in self.children.items():
            child_validation = child.validate(strict=strict)
            if not child_validation.passed:
                return child_validation

        for condition_name, condition in self.conditions.items():
            if not condition.value(self):
                validation_result = ValidationResult(passed=False,
                                                     error_message=f'Condition {condition_name} failed!',
                                                     source=self.__class__.__name__)
                if strict:
                    raise ValidationFailureException(validation_result=validation_result)

                return validation_result

        return ValidationResult(passed=True,
                                source=self.__class__.__name__)

    def search_field_by_tag(
            self,
            tags: Union[Tags, str],
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

        return {key: field.value for key, field in self.fields.items()
                if (exact_match and field.tags == tags) or (not exact_match and field.tags.intersection(tags) == tags)}

    def search_field(
            self,
            conditions: List[Callable[[Field], bool]]
    ) -> Dict[str, Any]:
        """
        Performs a custom ``Field`` search by given conditions.

        Args:
            conditions: list of callable filter functions

        Returns:
            A dictionary with ``Field.name`` as keys and ``Field`` as values
        """
        return {key: field.value for key, field in self.fields.items()
                if all([condition(field) for condition in conditions])}

    def search_condition_by_tag(
            self,
            tags: Union[Tags, str],
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

        return {key: field.value for key, field in self.conditions.items()
                if (exact_match and field.tags == tags) or (not exact_match and field.tags.intersection(tags) == tags)}

    def search_condition(
            self,
            conditions: List[Callable[[Field], bool]]
    ) -> Dict[str, Any]:
        """
        Performs a custom search on available ``Field`` conditions by given conditions.

        Args:
            conditions: list of callable filter functions

        Returns:
            A dictionary with ``Field.name`` as keys and ``Field`` as values
        """
        return {key: field.value for key, field in self.conditions.items()
                if all([condition(field) for condition in conditions])}
