from __future__ import annotations

import ast
import importlib.util
import pkgutil
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Type, AnyStr, List, Set, Dict, Any, Union, Optional, Callable

from typeguard import check_type

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.utility import logging_utility

Tag = Optional[Set[str]]
Constructor = Callable[[Any], Configuration]


class RegistrationKey:
    """
    Compound key used for registration.
    """

    KEY_VALUE_SEPARATOR: str = ':'
    ATTRIBUTE_SEPARATOR: str = '--'

    def __init__(
            self,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
    ):
        """

        Args:
            name: A general identifier of the type of ``Configuration`` being registered.
                For example, use ``name='data_loader'`` if you are registering a data loader ``Configuration``.
                Note that this is the recommended naming convention. There are no specific restrictions regarding
                name choice.
            namespace: The namespace is a high-level identifier used to distinguish macro groups
                of registered Configuration. For example, a group of models may be implemented in Tensorflow and
                another one in Torch. You can distinguish between these two groups by specifying two
                distinct namespaces. Additionally, the namespace can also used to distinguish among
                multiple users' registrations. In this case, the recommended naming convention is
                like the Huggingface's one: ``user/namespace``.
            tags: tags are metadata information that allows quick inspection of a registered ``Configuration`` details.
                In the case of ``Configuration`` with the same name and namespace (e.g., multiple models implemented by
                the same user), tags are used to distinguish among them.
        """
        self.name = name
        self.namespace = namespace if namespace is not None else 'default'
        self.tags = tags if tags is not None else set()

    def __hash__(
            self
    ) -> int:
        return hash(self.__str__())

    def __str__(
            self
    ) -> str:
        to_return = f'name{self.KEY_VALUE_SEPARATOR}{self.name}'

        if self.tags is not None:
            to_return += f'{self.ATTRIBUTE_SEPARATOR}tags{self.KEY_VALUE_SEPARATOR}{sorted(list(self.tags))}'

        to_return += f'{self.ATTRIBUTE_SEPARATOR}namespace{self.KEY_VALUE_SEPARATOR}{self.namespace}'
        return to_return

    def __repr__(
            self
    ) -> str:
        return self.__str__()

    def __eq__(
            self,
            other
    ) -> bool:
        default_condition = lambda other: self.name == other.name

        tags_condition = lambda other: (self.tags is not None and other.tags is not None and self.tags == other.tags) \
                                       or (self.tags is None and other.tags is None)

        namespace_condition = lambda other: (self.namespace is not None
                                             and other.namespace is not None
                                             and self.namespace == other.namespace) \
                                            or (self.namespace is None and other.namespace is None)

        return default_condition(other) \
            and tags_condition(other) \
            and namespace_condition(other)

    def partial_match(
            self,
            other: RegistrationKey
    ) -> bool:
        """
        Partial identifier matching between two ``RegistrationKey`` instances.
        The following conditions are evaluated:
        - name: the two instances must have the same name
        - namespace: the two instances must have the same namespace
        - tags: the two instances do not have any tag (``tags=None``) or one's tags are a subset of the other's tags.

        Args:
            other: a ``RegistrationKey`` instance for which a partial match is issued.

        Returns:
            True if all the above conditions are True.
        """

        name_condition = lambda other: self.name == other.name

        namespace_condition = lambda other: self.namespace == other.namespace

        tags_non_null_condition = lambda other: self.tags is not None and other.tags is not None
        tags_intersection_condition = lambda other: self.tags.intersection(other.tags) == other.tags \
                                                    or self.tags.intersection(other.tags) == self.tags
        tags_null_condition = lambda other: self.tags is None and other.tags is None
        tags_condition = lambda other: (tags_non_null_condition(other) and tags_intersection_condition(other)) \
                                       or tags_null_condition(other)

        return name_condition(other) and tags_condition(other) and namespace_condition(other)

    @classmethod
    def from_string(
            cls,
            string_format: str
    ) -> RegistrationKey:
        """
        Utility method to parse a ``RegistrationKey`` instance from its string format.

        Args:
            string_format: the string format of a ``RegistrationKey`` instance.

        Returns:
            The corresponding parsed ``RegistrationKey`` instance
        """

        registration_attributes = string_format.split(cls.ATTRIBUTE_SEPARATOR)
        registration_dict = {}
        for registration_attribute in registration_attributes:
            try:
                key, value = registration_attribute.split(cls.KEY_VALUE_SEPARATOR)
                if key == 'tags':
                    value = set(ast.literal_eval(value))

                registration_dict[key] = value
            except ValueError as e:
                logging_utility.logger.exception(f'Failed parsing registration key from string.. Got: {string_format}')
                raise e

        return RegistrationKey(**registration_dict)

    # TODO: overload with singledispatch?
    @classmethod
    def parse(
            cls,
            registration_key: Union[RegistrationKey, str]
    ) -> RegistrationKey:
        """
        Parses a given ``RegistrationKey`` instance.
        If the given ``registration_key`` is in its string format, it is converted to ``RegistrationKey`` instance

        Args:
            registration_key: a ``RegistrationKey`` instance in its class instance or string format

        Returns:
            The parsed ``RegistrationKey`` instance
        """

        check_type('registration_key', registration_key, Union[RegistrationKey, str])

        if type(registration_key) == str:
            registration_key = RegistrationKey.from_string(string_format=registration_key)

        return registration_key


Registration = Union[RegistrationKey, str]


class AlreadyRegisteredException(Exception):

    def __init__(
            self,
            registration_key: RegistrationKey
    ):
        super(AlreadyRegisteredException, self).__init__(
            f'A configuration has already been registered with the same key!'
            f'Got: {registration_key}')


class NotRegisteredException(Exception):

    def __init__(
            self,
            registration_key: RegistrationKey
    ):
        super(NotRegisteredException, self).__init__(f"Could not find registered configuration {registration_key}."
                                                     f" Did you register it?")


class NotBoundException(Exception):

    def __init__(
            self,
            registration_key: RegistrationKey
    ):
        super(NotBoundException, self).__init__(
            f'Registered configuration {registration_key} is not bound to any component.'
            f' Did you bind it?')


class AlreadyBoundException(Exception):

    def __init__(
            self,
            registration_key: RegistrationKey
    ):
        super(AlreadyBoundException, self).__init__(
            f'The given RegistrationKey was already used to bind to a Component!'
            f'Got: {registration_key}')


class InvalidConfigurationTypeException(Exception):

    def __init__(
            self,
            expected_type: Type,
            actual_type: Type
    ):
        super(InvalidConfigurationTypeException, self).__init__(
            f"Expected to build configuration of type {expected_type} but got {actual_type}")


@dataclass
class ConfigurationInfo:
    """
    Utility dataclass used for registration.
    Behind the curtains, the ``Configuration`` class is stored in the Registry via its corresponding
    ``ConfigurationInfo`` wrapper.

    This wrapper containsL
        - class_type: the ``Configuration`` class type
        - constructor: the method for creating an instance from the specified ``class_type``.
            By default, the constructor is set to ``Configuration.get_default()`` method.
        - kwargs: any potential constructor's function arguments.
    """

    class_type: Type[Configuration]
    constructor: Constructor
    kwargs: Any


_DEFAULT_REGISTRY_PACKAGES = {
    'generic': 'deasy_learning_generic',
    'tf': 'deasy_learning_tf',
    'torch': 'deasy_learning_torch',
}


def register(
        func: Callable
) -> Callable:
    # call the function to execute registrations
    if func not in Registry.REGISTRATION_METHODS:
        Registry.REGISTRATION_METHODS.append(func)
    return func


class Registry:
    """
    The registration registry.
    The registry has three main functionalities:
    - Storing/Retrieving registered ``Configuration``: via the ``ConfigurationInfo`` internal wrapper.
    - Storing/Retrieving ``Configuration`` to ``Component`` bindings: the binding operation allows to build
    a ``Component`` instance from its registered ``Configuration``.
    - Storing/Retrieving registered built ``Component`` instances: a ``Component`` instance can be registered
    as well to mimic Singleton behaviours. This functionality is useful is a single ``Component`` instance
    is used multiple times in a program.

    All the above functionalities require to specify a ``RegistrationKey`` (either directly or indirectly).
    """

    REGISTRY: Dict = {}
    BINDINGS: Dict = {}
    BUILT_MAPPINGS: Dict = {}
    REGISTRATION_METHODS: List = []

    @staticmethod
    def load_custom_module(
            module_path: Union[AnyStr, Path],
    ):
        """
        Imports a Python's module for registration.
        In particular, the Registry looks for ``register()`` functions in each found ``__init__.py``.
        These functions are the entry points for registrations: that is, where the ``Registry`` APIs are invoked
        to issue registrations.

        Args:
            module_path: path of the module
        """

        module_path = Path(module_path) if type(module_path) != Path else module_path
        module_name = module_path.name
        module_path = module_path.joinpath('__init__.py')

        if not module_path.is_file():
            return

        spec = importlib.util.spec_from_file_location(name=module_name,
                                                      location=module_path)
        module = importlib.util.module_from_spec(spec=spec)
        Registry.import_and_load_regitrations(package=module)

    @staticmethod
    def is_custom_module(
            module_path: Union[AnyStr, Path]
    ) -> bool:
        return module_path not in _DEFAULT_REGISTRY_PACKAGES

    @staticmethod
    def import_submodules(
            package: Union[str, ModuleType],
            recursive: bool = True
    ):
        """
        Import all submodules of a module, recursively, including subpackages

        Args:
            package: package (name or actual module)
            recursive: if True, the ``import_submodules`` function is invoked for found submodules
        """
        if isinstance(package, str):
            package = importlib.import_module(package)
        # TODO: low maintainability
        for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
            if name not in ['setup']:
                full_name = package.__name__ + '.' + name
                try:
                    importlib.import_module(full_name)
                except ModuleNotFoundError:
                    continue
                if recursive and is_pkg:
                    Registry.import_submodules(full_name)

    @staticmethod
    def try_resolve_module_from_namespace(
            namespace: Optional[str] = None
    ):
        if namespace is None:
            return None

        if namespace in _DEFAULT_REGISTRY_PACKAGES:
            module_name = _DEFAULT_REGISTRY_PACKAGES[namespace]
            Registry.import_and_load_regitrations(package=module_name)

    @staticmethod
    def import_and_load_regitrations(
            package: Union[str, ModuleType]
    ):
        # TODO: a bit of a hack -> should we mark registered methods to avoid re-executions?
        previous_methods_size = len(Registry.REGISTRATION_METHODS)
        Registry.import_submodules(package=package)
        new_methods_size = len(Registry.REGISTRATION_METHODS)
        if new_methods_size > previous_methods_size:
            for method in Registry.REGISTRATION_METHODS[previous_methods_size:]:
                method()

    @staticmethod
    def is_in_registry(
            registration_key: RegistrationKey,
    ) -> bool:
        if registration_key in Registry.REGISTRY:
            return True

        Registry.try_resolve_module_from_namespace(namespace=registration_key.namespace)

        if registration_key not in Registry.REGISTRY:
            return False

        return True

    @staticmethod
    def clear(

    ):
        Registry.REGISTRY.clear()
        Registry.BINDINGS.clear()
        Registry.BUILT_MAPPINGS.clear()
        Registry.REGISTRATION_METHODS.clear()

    # Registration APIs

    # Component

    @staticmethod
    def build_component_from_key(
            config_registration_key: Registration,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> Component:
        """
        Builds a ``Component`` instance from its bounded ``Configuration`` via the given ``RegistrationKey``.

        Args:
            config_registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.
            register_built_component: if True, it automatically registers the built ``Component`` in the registry.
            build_args

        Returns:
            The built ``Component`` instance

        Raises:
            ``InvalidConfigurationTypeException``: if there's a mismatch between the ``Configuration`` class used
            during registration and the type of the built ``Configuration`` instance using the registered
            ``constructor`` method (see ``ConfigurationInfo`` arguments).

            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """
        config_registration_key = RegistrationKey.parse(registration_key=config_registration_key)

        if not Registry.is_in_registry(registration_key=config_registration_key):
            raise NotRegisteredException(registration_key=config_registration_key)

        registered_config_info = Registry.REGISTRY[config_registration_key]
        built_config = registered_config_info.constructor(**registered_config_info.kwargs)

        if type(built_config) != registered_config_info.class_type:
            raise InvalidConfigurationTypeException(expected_type=built_config.class_type,
                                                    actual_type=type(built_config))
        if config_registration_key not in Registry.BINDINGS:
            raise NotBoundException(registration_key=config_registration_key)

        registered_component = Registry.BINDINGS[config_registration_key]
        build_args = build_args if build_args else {}
        built_component = registered_component(config=built_config,
                                               **build_args)

        if register_built_component:
            Registry.register_built_component_from_key(component=built_component,
                                                       config_registration_key=config_registration_key)
        return built_component

    @staticmethod
    def build_component(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> Component:
        """
        Builds a ``Component`` instance from its bounded ``Configuration`` via the implicit ``RegistrationKey``.

        Args:
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            register_built_component: if True, it automatically registers the built ``Component`` in the registry.
            build_args

        Returns:
            The built ``Component`` instance

        Raises:
            ``InvalidConfigurationTypeException``: if there's a mismatch between the ``Configuration`` class used
            during registration and the type of the built ``Configuration`` instance using the registered
            ``constructor`` method (see ``ConfigurationInfo`` arguments).

            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """

        config_regr_key = RegistrationKey(name=name,
                                          tags=tags,
                                          namespace=namespace)
        return Registry.build_component_from_key(config_registration_key=config_regr_key,
                                                 register_built_component=register_built_component,
                                                 build_args=build_args)

    @staticmethod
    def retrieve_component_from_key(
            config_registration_key: Registration,
    ) -> Type[Component]:
        """
        Retrieves the ``Component`` class bound to the given ``Configuration`` ``RegistrationKey``.

        Args:
            config_registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.

        Returns:
            The ``Component`` class bound to the given ``Configuration`` ``RegistrationKey``.

        Raises:
            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """

        if type(config_registration_key) == str:
            config_registration_key = RegistrationKey.from_string(string_format=config_registration_key)

        if config_registration_key not in Registry.BINDINGS:
            raise NotBoundException(registration_key=config_registration_key)

        return Registry.BINDINGS[config_registration_key]

    @staticmethod
    def retrieve_component(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
    ) -> Type[Component]:
        """
        Retrieves the ``Component`` class bound to the given ``Configuration`` ``RegistrationKey`` (implicit).

        Args:
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``s.

        Returns:
            The ``Component`` class bound to the given ``Configuration`` ``RegistrationKey``.

        Raises:
            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """

        config_regr_key = RegistrationKey(name=name,
                                          tags=tags,
                                          namespace=namespace)
        return Registry.retrieve_component_from_key(config_registration_key=config_regr_key)

    @staticmethod
    def register_built_component_from_key(
            component: Component,
            config_registration_key: RegistrationKey
    ):
        """
        Registers a built ``Component`` via its corresponding ``Configuration`` ``RegistrationKey``.

        Args:
            component: a ``Component`` instance
            config_registration_key: the ``Configuration`` ``RegistrationKey`` used to bind the ``Component``

        Raises:
            ``NotRegisteredException``: if the given ``config_registration_key`` is not found in the Registry.
        """
        if not Registry.is_in_registry(registration_key=config_registration_key):
            raise NotRegisteredException(registration_key=config_registration_key)
        Registry.BUILT_MAPPINGS[config_registration_key] = component

    @staticmethod
    def register_built_component(
            component: Component,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False
    ):
        """
        Registers a built ``Component`` via its corresponding ``Configuration`` ``RegistrationKey`` (implicitly).

        Args:
            component: a ``Component`` instance
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            is_default: if True, the tag ``default`` is added to ``tags``

        Raises:
            ``NotRegisteredException``: if the given ``config_registration_key`` is not found in the Registry.
        """

        if is_default:
            tags = tags.union('default') if tags is not None else {'default'}
        built_regr_key = RegistrationKey(name=name,
                                         tags=tags,
                                         namespace=namespace)
        Registry.register_built_component_from_key(component=component,
                                                   config_registration_key=built_regr_key)

    @staticmethod
    def retrieve_built_component_from_key(
            config_registration_key: Registration
    ) -> Component:
        """
        Retrieves a built ``Component`` instance from its corresponding ``Configuration`` ``RegistrationKey``.

        Args:
            config_registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.

        Returns:
            The built ``Component`` instance
        """
        config_registration_key = RegistrationKey.parse(registration_key=config_registration_key)

        if not Registry.is_in_registry(registration_key=config_registration_key):
            raise NotRegisteredException(registration_key=config_registration_key)

        return Registry.BUILT_MAPPINGS[config_registration_key]

    @staticmethod
    def retrieve_built_component(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False
    ) -> Component:
        """
        Retrieves a built ``Component`` instance from its corresponding ``Configuration``
        ``RegistrationKey`` (implicitly).

        Args:
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            is_default: if True, the tag ``default`` is added to ``tags``

        Returns:
            The built ``Component`` instance
        """

        if is_default:
            tags = tags.union('default') if tags is not None else {'default'}
        config_regr_key = RegistrationKey(name=name,
                                          tags=tags,
                                          namespace=namespace)
        return Registry.retrieve_built_component_from_key(config_registration_key=config_regr_key)

    # Configuration

    @staticmethod
    def register_configuration(
            configuration_class: Type[Configuration],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            configuration_constructor: Optional[Constructor] = None,
            configuration_kwargs: Optional[Dict] = None,
    ) -> RegistrationKey:
        """
        Registers a ``Configuration`` in the ``Registry`` via implicit ``RegistrationKey``.
        In particular, a ``ConfigurationInfo`` wrapper is stored in the ``Registry``.

        Args:
            configuration_class: the class of the ``Configuration``
            name: the ``name`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            configuration_constructor: the constructor method to build the ``Configuration`` instance from its class
            configuration_kwargs: potential arguments to the ``configuration_constructor`` method.

        Returns:
            The built ``RegistrationKey`` instance that can be used to retrieve the registered ``ConfigurationInfo``.

        Raises:
            ``AlreadyRegisteredException``: if the ``RegistrationKey`` is already used
        """

        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.register_configuration_from_key(configuration_class=configuration_class,
                                                        registration_key=registration_key,
                                                        configuration_constructor=configuration_constructor,
                                                        configuration_kwargs=configuration_kwargs)

    @staticmethod
    def register_configuration_from_key(
            configuration_class: Type[Configuration],
            registration_key: RegistrationKey,
            configuration_constructor: Optional[Constructor] = None,
            configuration_kwargs: Optional[Dict] = None,
    ):
        """
        Registers a ``Configuration`` in the ``Registry`` via explicit ``RegistrationKey``.
        In particular, a ``ConfigurationInfo`` wrapper is stored in the ``Registry``.

        Args:
            configuration_class: the class of the ``Configuration``
            registration_key: the ``RegistrationKey`` instance to use to register the ``Configuration``
            configuration_constructor: the constructor method to build the ``Configuration`` instance from its class
            configuration_kwargs: potential arguments to the ``configuration_constructor`` method.

        Returns:
            The built ``RegistrationKey`` instance that can be used to retrieve the registered ``ConfigurationInfo``.

        Raises:
            ``AlreadyRegisteredException``: if the ``RegistrationKey`` is already used
        """

        # Check if already registered
        if Registry.is_in_registry(registration_key=registration_key):
            raise AlreadyRegisteredException(registration_key=registration_key)

        # Store configuration in registry
        configuration_constructor = configuration_constructor \
            if configuration_constructor is not None else configuration_class.get_default
        configuration_kwargs = configuration_kwargs if configuration_kwargs is not None else {}
        Registry.REGISTRY[registration_key] = ConfigurationInfo(class_type=configuration_class,
                                                                constructor=configuration_constructor,
                                                                kwargs=configuration_kwargs)
        return registration_key

    @staticmethod
    def retrieve_configurations_from_key(
            config_registration_key: Registration,
            exact_match: bool = True,
            strict: bool = True
    ) -> Union[ConfigurationInfo, List[ConfigurationInfo]]:
        """
        Retrieves one or multiple ``ConfigurationInfo`` from the ``Registry``.

        Args:
            config_registration_key: the ``RegistrationKey`` used to register a ``Configuration``.
            exact_match: if True, only the exact ``RegistrationKey`` is considered for looking up in the ``Registry`.
                Otherwise, a partial match is carried out (see ``RegistrationKey.partial_match``).
            strict: if True, the case of not retrieving any ``ConfigurationInfo`` from the ``Registry`` throws a
                ``NotRegisteredException``. Otherwise, ``None`` is returned without raising any exception.

        Returns:
            One or a list of ``ConfigurationInfo`` objects.

        Raises:
            ``NotRegisteredException``: if ``strict = True`` and no ``ConfigurationInfo`` is found in the ``Registry``
            using the specified ``config_registration_key``.
        """

        config_registration_key = RegistrationKey.parse(registration_key=config_registration_key)

        if exact_match:
            configurations = Registry.REGISTRY.get(config_registration_key, None)
        else:
            configurations = [Registry.REGISTRY.get(config_registration_key, None)
                              for key in Registry.REGISTRY if key.partial_match(config_registration_key)]

        if (configurations is None
            or (type(configurations) == List
                and any([item is None for item in configurations]))) \
                and strict:
            raise NotRegisteredException(registration_key=config_registration_key)

        return configurations

    @staticmethod
    def retrieve_configurations(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            exact_match: bool = True,
            strict: bool = True
    ) -> Union[ConfigurationInfo, List[ConfigurationInfo]]:
        """
        Retrieves one or multiple ``ConfigurationInfo`` from the ``Registry``.

        Args:
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            exact_match: if True, only the exact ``RegistrationKey`` is considered for looking up in the ``Registry`.
                Otherwise, a partial match is carried out (see ``RegistrationKey.partial_match``).
            strict: if True, the even of not retrieving any ``ConfigurationInfo`` from the ``Registry`` throws a
                ``NotRegisteredException``. Otherwise, ``None`` is returned without raising any exception.

        Returns:
            One or a list of ``ConfigurationInfo`` objects.

        Raises:
            ``NotRegisteredException``: if ``strict = True`` and no ``ConfigurationInfo`` is found in the ``Registry``
            using the specified ``config_registration_key``.
        """

        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.retrieve_configurations_from_key(config_registration_key=registration_key,
                                                         exact_match=exact_match,
                                                         strict=strict)

    @staticmethod
    def bind_from_key(
            config_registration_key: RegistrationKey,
            component_class: Type
    ):
        """
        Binds a ``Configuration`` to a ``Component``.

        Args:
            config_registration_key: the ``RegistrationKey`` used to register a ``Configuration``.
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``

        Raises:
            ``NotRegisteredException``: if ``config_registration_key`` is not in the ``Registry``.

            ``AlreadyBoundException``: if ``config_registration_key`` has already been used to bind a ``Component``
        """

        if not Registry.is_in_registry(registration_key=config_registration_key):
            raise NotRegisteredException(registration_key=config_registration_key)

        if config_registration_key in Registry.BINDINGS:
            raise AlreadyBoundException(registration_key=config_registration_key)

        Registry.BINDINGS[config_registration_key] = component_class

    @staticmethod
    def bind(
            component_class: Type,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None
    ):
        """
        Binds a ``Configuration`` to a ``Component``.

        Args:
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``

        Raises:
            ``NotRegisteredException``: if ``config_registration_key`` is not in the ``Registry``.
        """
        Registry.bind_from_key(config_registration_key=RegistrationKey(namespace=namespace,
                                                                       name=name,
                                                                       tags=tags),
                               component_class=component_class)

    @staticmethod
    def register_and_bind(
            configuration_class: Type[Configuration],
            component_class: Type,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            configuration_constructor: Optional[Constructor] = None,
            configuration_kwargs: Optional[Dict] = None,
            is_default: bool = False
    ) -> RegistrationKey:
        """
        Registers a ``Configuration`` and binds it to a ``Component``.

        Args:
            configuration_class: the class of the ``Configuration``
            component_class: the class of the ``Component``.
            name: the ``name`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            configuration_constructor: the constructor method to build the ``Configuration`` instance from its class
            configuration_kwargs: potential arguments to the ``configuration_constructor`` method.
            is_default: if True, the tag ``default`` is added to ``tags``

        Returns:
            The ``RegistrationKey`` instance used to register the ``Configuration``.
        """

        tags = tags.union({'default'}) if tags is not None and is_default else tags
        if tags is None and is_default:
            tags = {'default'}

        config_regr_key = Registry.register_configuration(configuration_class=configuration_class,
                                                          configuration_constructor=configuration_constructor,
                                                          configuration_kwargs=configuration_kwargs,
                                                          name=name,
                                                          tags=tags,
                                                          namespace=namespace)

        Registry.BINDINGS[config_regr_key] = component_class

        return config_regr_key

    @staticmethod
    def register_and_bind_configuration_variants(
            configuration_class: Type[Configuration],
            component_class: Type[Component],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            parameter_variants_only: bool = False,
            allow_parameter_variants: bool = True
    ) -> Optional[List[RegistrationKey]]:
        """
        Registers and binds all possible ``Configuration`` variants.
        A configuration variant is a variant of ``Configuration`` parameters.
        Given a ``Configuration`` class, all its variants are retrieved, registered in the ``Registry`` and bound
        to the given ``Component``.

        Args:
            configuration_class: the class of the ``Configuration``
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            parameter_variants_only: if True, only parameter variants are considered.
            allow_parameter_variants: if True, the Registry looks for parameter variants iff
            no configuration variants have been detected. This functionality allows mixed nested configuration variants.

        Returns:
            the list of ``RegistrationKey`` used to register each ``Configuration`` variant
        """

        variants = configuration_class.variants

        if not parameter_variants_only:
            new_registered_conf_keys = []
            for variant in variants:
                variant_tags = tags.union({variant.name}) if tags is not None else {variant.name}
                variant_constructor = getattr(configuration_class, variant.method.__name__)
                new_registered_conf_keys.append(Registry.register_and_bind(configuration_class=configuration_class,
                                                                           configuration_constructor=variant_constructor,
                                                                           component_class=component_class,
                                                                           name=name,
                                                                           tags=variant_tags,
                                                                           namespace=namespace))

            if len(variants) or not allow_parameter_variants:
                return new_registered_conf_keys

        default_config = configuration_class.get_default()

        # Make sure we can work with a valid configuration
        default_config.validate()

        children = {param_key: param
                    for param_key, param in default_config.items()
                    if param.is_registration and not param.is_calibration}

        # Add variants to each registration child iff no variants have been specified
        for child_key, child in children.items():
            if child.variants is None:
                child_regr_key = child.value
                child_config_class = Registry.retrieve_configurations_from_key(config_registration_key=child_regr_key,
                                                                               exact_match=True).class_type
                if not child_regr_key in Registry.BINDINGS:
                    raise NotBoundException(registration_key=child_regr_key)
                child_component_class = Registry.BINDINGS[child_regr_key]
                child_variants = Registry.register_and_bind_configuration_variants(
                    configuration_class=child_config_class,
                    component_class=child_component_class,
                    name=child_regr_key.name,
                    tags=child_regr_key.tags,
                    namespace=child_regr_key.namespace,
                    parameter_variants_only=parameter_variants_only,
                    allow_parameter_variants=allow_parameter_variants)
                default_config.get_param(child_key).variants = child_variants

        # Register each combination of parameter variants
        parameter_combinations = default_config.get_variants_combinations()

        # No combinations have been found -> check if already registered
        if not len(parameter_combinations):
            retrieved_config = Registry.retrieve_configurations(name=name,
                                                                tags=tags,
                                                                namespace=namespace,
                                                                exact_match=True)
            if retrieved_config is not None:
                return None
            else:
                # Register configuration
                Registry.register_and_bind(configuration_class=configuration_class,
                                           configuration_constructor=configuration_class.get_default,
                                           component_class=component_class,
                                           name=name,
                                           tags=tags,
                                           namespace=namespace)
                return None

        # Register each combination
        new_registered_conf_keys = []
        for combination in parameter_combinations:
            combination_tags = set()
            for key, value in combination.items():
                if type(value) != RegistrationKey:
                    combination_tags.add(f'{key}={value}')
                else:
                    for tag in value.tags:
                        combination_tags.add(f'{key}.{tag}')
            combination_tags = tags.union(combination_tags) if tags is not None else combination_tags
            new_registered_conf_keys.append(Registry.register_and_bind(configuration_class=configuration_class,
                                                                       configuration_constructor=configuration_class.get_delta_copy,
                                                                       configuration_kwargs={
                                                                           'params': combination},
                                                                       component_class=component_class,
                                                                       name=name,
                                                                       tags=combination_tags,
                                                                       namespace=namespace))
        return new_registered_conf_keys


__all__ = [
    'RegistrationKey',
    'register',
    'Registry',
    'Tag',
    'Registration',
    'ConfigurationInfo',
    'NotRegisteredException',
    'NotBoundException',
    'AlreadyRegisteredException',
    'InvalidConfigurationTypeException',
    'AlreadyBoundException',
]
