from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Type, AnyStr, List, Set, Dict, Any, Union, Optional, Callable

import networkx as nx
from pyvis.network import Network
from typeguard import check_type

from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration, C
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
            tags = sorted(list(self.tags)) if self.tags else None
            if tags is not None:
                to_return += f'{self.ATTRIBUTE_SEPARATOR}tags{self.KEY_VALUE_SEPARATOR}{tags}'

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
        if other is None or not isinstance(other, RegistrationKey):
            return False

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


class DisconnectedGraphException(Exception):

    def __init__(
            self,
            nodes
    ):
        super().__init__(f'Disconnected graph! Nodes {nodes} are not connected!')


class NotADAGException(Exception):

    def __init__(
            self
    ):
        super().__init__(f'The built graph is not a DAG!')


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


# TODO: to be updated
_DEFAULT_PACKAGES = {
    'generic': 'cinnamon_generic',
    'tf': 'cinnamon_tf',
    'th': 'cinnamon_th'
}


def register(
        func: Callable
) -> Callable:
    # call the function to execute registrations
    if Registry.REGISTER_SCOPE is None:
        return func

    if func not in Registry.REGISTRATION_METHODS and func.__module__ == Registry.REGISTER_SCOPE.name:
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
    BUILT_REGISTRY: Dict = {}

    REGISTRATION_METHODS: List = []
    MODULE_SCOPE: AnyStr = None
    REGISTER_SCOPE: AnyStr = None
    REGISTERED_NAMESPACES: List[str] = []

    ROOT_KEY = RegistrationKey(name='root', namespace='root')
    DEPENDENCY_DAG = nx.DiGraph()
    DEPENDENCY_DAG.add_node(ROOT_KEY)
    REGISTRATION_REGISTRY = {}

    @staticmethod
    def load_registrations(
            directory_path: Union[AnyStr, Path],
    ):
        """
        Imports a Python's module for registration.
        In particular, the Registry looks for ``register()`` functions in each found ``__init__.py``.
        These functions are the entry points for registrations: that is, where the ``Registry`` APIs are invoked
        to issue registrations.

        Args:
            directory_path: path of the module
        """

        directory_path = Path(directory_path) if type(directory_path) != Path else directory_path

        if not directory_path.exists() or not directory_path.is_dir():
            return

        for config_folder in directory_path.rglob('configurations'):
            for python_script in config_folder.glob('*.py'):
                spec = importlib.util.spec_from_file_location(name=python_script.name,
                                                              location=python_script)
                if spec is not None:
                    Registry.REGISTER_SCOPE = python_script
                    Registry.import_and_load_registrations(spec=spec)
                    Registry.REGISTER_SCOPE = None

    @staticmethod
    def import_and_load_registrations(
            spec
    ):
        previous_methods_size = len(Registry.REGISTRATION_METHODS)
        module = importlib.util.module_from_spec(spec=spec)
        spec.loader.exec_module(module)
        new_methods_size = len(Registry.REGISTRATION_METHODS)
        if new_methods_size > previous_methods_size:
            for method in Registry.REGISTRATION_METHODS[previous_methods_size:]:
                method()

    @staticmethod
    def try_resolve_module_from_namespace(
            namespace: Optional[str] = None
    ):
        if namespace is None:
            return None

        if namespace in _DEFAULT_PACKAGES:
            module_name = _DEFAULT_PACKAGES[namespace]
            if Registry.MODULE_SCOPE is None and namespace not in Registry.REGISTERED_NAMESPACES:
                Registry.REGISTERED_NAMESPACES.append(namespace)

                Registry.MODULE_SCOPE = module_name
                module = importlib.import_module(module_name)
                Registry.load_registrations(directory_path=module.__path__[0])

                Registry.check_registration_graph()
                Registry.expand_and_resolve_registration(namespace=namespace)

                Registry.MODULE_SCOPE = None

    @staticmethod
    def is_in_registry(
            registration_key: RegistrationKey,
    ) -> bool:
        if registration_key in Registry.REGISTRY:
            return True

        if registration_key.namespace not in Registry.REGISTERED_NAMESPACES:
            Registry.try_resolve_module_from_namespace(namespace=registration_key.namespace)

        if registration_key not in Registry.REGISTRY:
            return False

        return True

    @staticmethod
    def clear(

    ):
        Registry.REGISTRY.clear()
        Registry.BINDINGS.clear()
        Registry.BUILT_REGISTRY.clear()

        Registry.REGISTRATION_METHODS.clear()
        Registry.MODULE_SCOPE = None
        Registry.REGISTER_SCOPE = None
        Registry.REGISTERED_NAMESPACES.clear()

        Registry.DEPENDENCY_DAG.clear()
        Registry.REGISTRATION_REGISTRY.clear()

    # Registration APIs

    # Component

    @staticmethod
    def build_component_from_key(
            registration_key: Registration,
            register_component_instance: bool = False,
            build_args: Optional[Dict] = None
    ) -> Component:
        """
        Builds a ``Component`` instance from its bounded ``Configuration`` via the given ``RegistrationKey``.

        Args:
            registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.
            register_component_instance: if True, it automatically registers the ``Component`` instance in the registry.
            build_args: additional optional build arguments

        Returns:
            The built ``Component`` instance

        Raises:
            ``InvalidConfigurationTypeException``: if there's a mismatch between the ``Configuration`` class used
            during registration and the type of the built ``Configuration`` instance using the registered
            ``constructor`` method (see ``ConfigurationInfo`` arguments).

            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """
        registration_key = RegistrationKey.parse(registration_key=registration_key)

        if not Registry.is_in_registry(registration_key=registration_key):
            raise NotRegisteredException(registration_key=registration_key)

        registered_config_info = Registry.REGISTRY[registration_key]
        built_config = registered_config_info.constructor(**registered_config_info.kwargs)

        if type(built_config) != registered_config_info.class_type:
            raise InvalidConfigurationTypeException(expected_type=built_config.class_type,
                                                    actual_type=type(built_config))
        if registration_key not in Registry.BINDINGS:
            raise NotBoundException(registration_key=registration_key)

        built_config.post_build()
        built_config.validate()

        registered_component = Registry.BINDINGS[registration_key]
        build_args = build_args if build_args else {}
        built_component = registered_component(config=built_config,
                                               **build_args)

        if register_component_instance:
            Registry.register_built_component_from_key(component=built_component,
                                                       registration_key=registration_key)
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
        return Registry.build_component_from_key(registration_key=config_regr_key,
                                                 register_component_instance=register_built_component,
                                                 build_args=build_args)

    @staticmethod
    def retrieve_component_from_key(
            registration_key: Registration,
    ) -> Type[Component]:
        """
        Retrieves the ``Component`` class bound to the given ``Configuration`` ``RegistrationKey``.

        Args:
            registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.

        Returns:
            The ``Component`` class bound to the given ``Configuration`` ``RegistrationKey``.

        Raises:
            ``NotBoundException``: if the ``Configuration`` is not bound to any ``Component``.
        """

        if type(registration_key) == str:
            registration_key = RegistrationKey.from_string(string_format=registration_key)

        if registration_key not in Registry.BINDINGS:
            raise NotBoundException(registration_key=registration_key)

        return Registry.BINDINGS[registration_key]

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

        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.retrieve_component_from_key(registration_key=registration_key)

    @staticmethod
    def register_built_component_from_key(
            component: Component,
            registration_key: RegistrationKey
    ):
        """
        Registers a built ``Component`` via its corresponding ``Configuration`` ``RegistrationKey``.

        Args:
            component: a ``Component`` instance
            registration_key: the ``Configuration`` ``RegistrationKey`` used to bind the ``Component``

        Raises:
            ``NotRegisteredException``: if the given ``registration_key`` is not found in the Registry.
        """
        if not Registry.is_in_registry(registration_key=registration_key):
            raise NotRegisteredException(registration_key=registration_key)
        Registry.BUILT_REGISTRY[registration_key] = component

    @staticmethod
    def register_component_instance(
            component: Component,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False
    ):
        """
        Registers a ``Component`` instance via its associated ``RegistrationKey`` in implicit format.

        Args:
            component: a ``Component`` instance
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            is_default: if True, the tag ``default`` is added to ``tags``

        Raises:
            ``NotRegisteredException``: if the given ``registration_key`` is not found in the Registry.
        """

        if is_default:
            tags = tags.union('default') if tags is not None else {'default'}
        built_regr_key = RegistrationKey(name=name,
                                         tags=tags,
                                         namespace=namespace)
        Registry.register_built_component_from_key(component=component,
                                                   registration_key=built_regr_key)

    @staticmethod
    def retrieve_component_instance_from_key(
            registration_key: Registration
    ) -> Component:
        """
        Retrieves a ``Component`` instance from its associated ``RegistrationKey`` in explicit format.

        Args:
            registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.

        Returns:
            The built ``Component`` instance
        """
        registration_key = RegistrationKey.parse(registration_key=registration_key)

        if not Registry.is_in_registry(registration_key=registration_key):
            raise NotRegisteredException(registration_key=registration_key)

        return Registry.BUILT_REGISTRY[registration_key]

    @staticmethod
    def retrieve_component_instance(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False
    ) -> Component:
        """
        Retrieves a ``Component`` instance from its associated ``RegistrationKey`` in implicit format.

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
        return Registry.retrieve_component_instance_from_key(registration_key=config_regr_key)

    # Configuration

    @staticmethod
    def is_in_graph(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
    ) -> bool:
        key = RegistrationKey(name=name,
                              tags=tags,
                              namespace=namespace)
        return Registry.is_in_graph_from_key(registration_key=key)

    @staticmethod
    def is_in_graph_from_key(
            registration_key: Registration
    ) -> bool:
        return registration_key in Registry.DEPENDENCY_DAG

    @staticmethod
    def check_registration_graph(

    ) -> bool:
        for node in Registry.DEPENDENCY_DAG.nodes():
            if node == Registry.ROOT_KEY:
                continue

            node_sources = [edge[0] for edge in Registry.DEPENDENCY_DAG.in_edges(node)]
            if len(node_sources) > 1 and Registry.ROOT_KEY in node_sources:
                Registry.DEPENDENCY_DAG.remove_edge(Registry.ROOT_KEY, node)

        isolated_nodes = list(nx.isolates(Registry.DEPENDENCY_DAG))
        if len(isolated_nodes) > 0 and len(Registry.DEPENDENCY_DAG.nodes) > 1:
            raise DisconnectedGraphException(nodes=isolated_nodes)

        if not nx.algorithms.dag.is_directed_acyclic_graph(Registry.DEPENDENCY_DAG):
            raise NotADAGException()

        return True

    @staticmethod
    def build_configuration_from_key(
            registration_key: Registration
    ) -> C:
        """
        Builds a configuration instance given its registration key.

        Args:
            registration_key: key used to register the configuration

        Returns:
            The built configuration
        """

        if not Registry.is_in_registry(registration_key=registration_key):
            raise NotRegisteredException(registration_key=registration_key)

        config_info = Registry.retrieve_configurations_from_key(registration_key=registration_key)
        return config_info.constructor(**config_info.kwargs)

    @staticmethod
    def build_configuration(
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
    ):
        """
                Builds a configuration instance given its implicit registration key.

        Args:
            name: the ``name`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``

        Returns:
            The built configuration
        """

        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.build_configuration_from_key(registration_key=registration_key)

    @staticmethod
    def register_configuration(
            config_class: Type[Configuration],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None,
    ) -> RegistrationKey:
        """
        Registers a ``Configuration`` in the ``Registry`` via implicit ``RegistrationKey``.
        In particular, a ``ConfigurationInfo`` wrapper is stored in the ``Registry``.

        Args:
            config_class: the class of the ``Configuration``
            name: the ``name`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            is_default: if True, the 'default' tag is automatically added to configuration tags
            config_constructor: the constructor method to build the ``Configuration`` instance from its class
            config_kwargs: potential arguments to the ``configuration_constructor`` method.

        Returns:
            The built ``RegistrationKey`` instance that can be used to retrieve the registered ``ConfigurationInfo``.

        Raises:
            ``AlreadyRegisteredException``: if the ``RegistrationKey`` is already used
        """

        tags = tags.union({'default'}) if tags is not None and is_default else tags
        if tags is None and is_default:
            tags = {'default'}
        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.register_configuration_from_key(config_class=config_class,
                                                        registration_key=registration_key,
                                                        config_constructor=config_constructor,
                                                        config_kwargs=config_kwargs)

    @staticmethod
    def register_configuration_from_key(
            config_class: Type[Configuration],
            registration_key: RegistrationKey,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None,
    ):
        """
        Registers a ``Configuration`` in the ``Registry`` via explicit ``RegistrationKey``.
        In particular, a ``ConfigurationInfo`` wrapper is stored in the ``Registry``.

        Args:
            config_class: the class of the ``Configuration``
            registration_key: the ``RegistrationKey`` instance to use to register the ``Configuration``
            config_constructor: the constructor method to build the ``Configuration`` instance from its class
            config_kwargs: potential arguments to the ``configuration_constructor`` method.

        Returns:
            The built ``RegistrationKey`` instance that can be used to retrieve the registered ``ConfigurationInfo``.

        Raises:
            ``AlreadyRegisteredException``: if the ``RegistrationKey`` is already used
        """

        # Check if already registered
        if Registry.is_in_registry(registration_key=registration_key):
            raise AlreadyRegisteredException(registration_key=registration_key)

        # Store configuration in registry
        config_constructor = config_constructor \
            if config_constructor is not None else config_class.get_default
        config_kwargs = config_kwargs if config_kwargs is not None else {}
        Registry.REGISTRY[registration_key] = ConfigurationInfo(class_type=config_class,
                                                                constructor=config_constructor,
                                                                kwargs=config_kwargs)
        return registration_key

    @staticmethod
    def add_configuration(
            config_class: Type[Configuration],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None,
    ):
        tags = tags.union({'default'}) if tags is not None and is_default else tags
        if tags is None and is_default:
            tags = {'default'}
        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        Registry.add_configuration_from_key(config_class=config_class,
                                            registration_key=registration_key,
                                            config_constructor=config_constructor,
                                            config_kwargs=config_kwargs)

    @staticmethod
    def add_configuration_from_key(
            config_class: Type[Configuration],
            registration_key: RegistrationKey,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None,
    ):
        if not Registry.is_in_graph_from_key(registration_key=registration_key):
            Registry.DEPENDENCY_DAG.add_node(registration_key)
            Registry.DEPENDENCY_DAG.add_edge(Registry.ROOT_KEY, registration_key)

        # Check children
        config_kwargs = config_kwargs if config_kwargs is not None else {}
        config_constructor = config_constructor if config_constructor is not None else config_class.get_default

        built_config = config_constructor(**config_kwargs)
        for child_name, child in built_config.children.items():
            child_key = child.value
            if child_key is not None:
                if not Registry.is_in_graph_from_key(child_key):
                    Registry.DEPENDENCY_DAG.add_node(child_key)

                Registry.DEPENDENCY_DAG.add_edge(registration_key, child_key)

            if child.variants is not None:
                for variant in child.variants:
                    if not Registry.is_in_graph_from_key(variant):
                        Registry.DEPENDENCY_DAG.add_node(variant)
                    Registry.DEPENDENCY_DAG.add_edge(registration_key, variant)

        # Memo registration method
        if registration_key not in Registry.REGISTRATION_REGISTRY:
            Registry.REGISTRATION_REGISTRY[registration_key] = partial(Registry.register_configuration_from_key,
                                                                       config_class=config_class,
                                                                       registration_key=registration_key,
                                                                       config_constructor=config_constructor,
                                                                       config_kwargs=config_kwargs)

    @staticmethod
    def retrieve_configurations_from_key(
            registration_key: Registration,
            exact_match: bool = True,
            strict: bool = True
    ) -> Union[ConfigurationInfo, List[ConfigurationInfo]]:
        """
        Retrieves one or multiple ``ConfigurationInfo`` from the ``Registry``.

        Args:
            registration_key: the ``RegistrationKey`` used to register a ``Configuration``.
            exact_match: if True, only the exact ``RegistrationKey`` is considered for looking up in the ``Registry`.
                Otherwise, a partial match is carried out (see ``RegistrationKey.partial_match``).
            strict: if True, the case of not retrieving any ``ConfigurationInfo`` from the ``Registry`` throws a
                ``NotRegisteredException``. Otherwise, ``None`` is returned without raising any exception.

        Returns:
            One or a list of ``ConfigurationInfo`` objects.

        Raises:
            ``NotRegisteredException``: if ``strict = True`` and no ``ConfigurationInfo`` is found in the ``Registry``
            using the specified ``registration_key``.
        """
        # Trigger potential latent registrations before attempting registry lookup
        Registry.is_in_registry(registration_key=registration_key)

        registration_key = RegistrationKey.parse(registration_key=registration_key)

        if exact_match:
            configurations = Registry.REGISTRY.get(registration_key, None)
        else:
            configurations = [Registry.REGISTRY.get(key, None)
                              for key in Registry.REGISTRY if key.partial_match(key)]

        if (configurations is None
            or (type(configurations) == List
                and any([item is None for item in configurations]))) \
                and strict:
            raise NotRegisteredException(registration_key=registration_key)

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
            using the specified ``registration_key``.
        """

        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        return Registry.retrieve_configurations_from_key(registration_key=registration_key,
                                                         exact_match=exact_match,
                                                         strict=strict)

    @staticmethod
    def bind_from_key(
            registration_key: RegistrationKey,
            component_class: Type
    ):
        """
        Binds a ``Configuration`` to a ``Component``.

        Args:
            registration_key: the ``RegistrationKey`` used to register a ``Configuration``.
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``

        Raises:
            ``NotRegisteredException``: if ``registration_key`` is not in the ``Registry``.

            ``AlreadyBoundException``: if ``registration_key`` has already been used to bind a ``Component``
        """

        if not Registry.is_in_registry(registration_key=registration_key):
            raise NotRegisteredException(registration_key=registration_key)

        if registration_key in Registry.BINDINGS:
            raise AlreadyBoundException(registration_key=registration_key)

        Registry.BINDINGS[registration_key] = component_class

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
            ``NotRegisteredException``: if ``registration_key`` is not in the ``Registry``.
        """
        Registry.bind_from_key(registration_key=RegistrationKey(namespace=namespace,
                                                                name=name,
                                                                tags=tags),
                               component_class=component_class)

    @staticmethod
    def register_and_bind(
            config_class: Type[Configuration],
            component_class: Type,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None
    ) -> RegistrationKey:
        """
        Registers a ``Configuration`` and binds it to a ``Component``.

        Args:
            config_class: the class of the ``Configuration``
            component_class: the class of the ``Component``.
            name: the ``name`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            config_constructor: the constructor method to build the ``Configuration`` instance from its class
            config_kwargs: potential arguments to the ``configuration_constructor`` method.
            is_default: if True, the tag ``default`` is added to ``tags``

        Returns:
            The ``RegistrationKey`` instance used to register the ``Configuration``.
        """

        tags = tags.union({'default'}) if tags is not None and is_default else tags
        if tags is None and is_default:
            tags = {'default'}

        key = Registry.register_configuration(config_class=config_class,
                                              config_constructor=config_constructor,
                                              config_kwargs=config_kwargs,
                                              name=name,
                                              tags=tags,
                                              namespace=namespace)

        Registry.bind_from_key(registration_key=key,
                               component_class=component_class)

        return key

    @staticmethod
    def add_and_bind(
            config_class: Type[Configuration],
            component_class: Type,
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            is_default: bool = False,
            config_constructor: Optional[Constructor] = None,
            config_kwargs: Optional[Dict] = None,
    ):
        tags = tags.union({'default'}) if tags is not None and is_default else tags
        if tags is None and is_default:
            tags = {'default'}
        registration_key = RegistrationKey(name=name,
                                           tags=tags,
                                           namespace=namespace)
        if not Registry.is_in_graph_from_key(registration_key=registration_key):
            Registry.DEPENDENCY_DAG.add_node(registration_key)
            Registry.DEPENDENCY_DAG.add_edge(Registry.ROOT_KEY, registration_key)

        config_kwargs = config_kwargs if config_kwargs is not None else {}
        config_constructor = config_constructor if config_constructor is not None else config_class.get_default

        built_config = config_constructor(**config_kwargs)
        for child_name, child in built_config.children.items():
            child_key = child.value
            if child_key is not None:
                if not Registry.is_in_graph_from_key(child_key):
                    Registry.DEPENDENCY_DAG.add_node(child_key)

                Registry.DEPENDENCY_DAG.add_edge(registration_key, child_key)

            if child.variants is not None:
                for variant in child.variants:
                    if not Registry.is_in_graph_from_key(variant):
                        Registry.DEPENDENCY_DAG.add_node(variant)
                    Registry.DEPENDENCY_DAG.add_edge(registration_key, variant)

        if registration_key not in Registry.REGISTRATION_REGISTRY:
            Registry.REGISTRATION_REGISTRY[registration_key] = partial(Registry.register_and_bind,
                                                                       config_class=config_class,
                                                                       component_class=component_class,
                                                                       name=name,
                                                                       tags=tags,
                                                                       namespace=namespace,
                                                                       config_constructor=config_constructor,
                                                                       config_kwargs=config_kwargs)

    @staticmethod
    def register_and_bind_variants(
            config_class: Type[Configuration],
            component_class: Type[Component],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            config_constructor: Callable[[Any], Configuration] = None,
            config_kwargs: Optional[Dict] = None,
    ) -> Optional[List[RegistrationKey]]:
        """
        Registers and binds all possible ``Configuration`` variants.
        A configuration variant is a variant of ``Configuration`` parameters.
        Given a ``Configuration`` class, all its variants are retrieved, registered in the ``Registry`` and bound
        to the given ``Component``.

        Args:
            config_class: the class of the ``Configuration``
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            config_constructor: callable that builds the configuration instance (just like ``get_default()``)
            config_kwargs: optional constructor arguments

        Returns:
            the list of ``RegistrationKey`` used to register each ``Configuration`` variant
        """

        config_constructor = config_constructor \
            if config_constructor is not None else config_class.get_default
        config_kwargs = config_kwargs \
            if config_kwargs is not None else {}

        new_registered_keys = []

        main_key = RegistrationKey(name=name,
                                   tags=tags,
                                   namespace=namespace)
        if not Registry.is_in_registry(registration_key=main_key):
            Registry.register_and_bind(config_class=config_class,
                                       component_class=component_class,
                                       config_constructor=config_constructor,
                                       config_kwargs=config_kwargs,
                                       name=name,
                                       tags=tags,
                                       namespace=namespace)
            new_registered_keys.append(main_key)

        if not Registry.is_in_graph_from_key(registration_key=main_key):
            Registry.DEPENDENCY_DAG.add_node(main_key)
            Registry.DEPENDENCY_DAG.add_edge(Registry.ROOT_KEY, main_key)

        built_config = config_constructor(**config_kwargs)

        # Add variants to each registration child
        for child_name, child in built_config.children.items():
            child_key = child.value
            child_variants = []

            if child.variants is not None:
                for variant in child.variants:
                    variant_config_info = Registry.retrieve_configurations_from_key(registration_key=variant,
                                                                                    exact_match=True)
                    if variant not in Registry.BINDINGS:
                        raise NotBoundException(registration_key=variant)
                    variant_component_class = Registry.BINDINGS[variant]
                    child_variants.extend(Registry.register_and_bind_variants(
                        config_class=variant_config_info.class_type,
                        component_class=variant_component_class,
                        name=variant.name,
                        tags=variant.tags,
                        namespace=variant.namespace,
                        config_constructor=variant_config_info.constructor,
                        config_kwargs=variant_config_info.kwargs))

            if child_key is not None:
                child_config_info = Registry.retrieve_configurations_from_key(registration_key=child_key,
                                                                              exact_match=True)
                if child_key not in Registry.BINDINGS:
                    raise NotBoundException(registration_key=child_key)

                child_component_class = Registry.BINDINGS[child_key]
                child_variants.extend(Registry.register_and_bind_variants(
                    config_class=child_config_info.class_type,
                    component_class=child_component_class,
                    name=child_key.name,
                    tags=child_key.tags if child_key.tags else None,
                    namespace=child_key.namespace,
                    config_constructor=child_config_info.constructor,
                    config_kwargs=child_config_info.kwargs))

                if Registry.is_in_graph_from_key(child_key):
                    Registry.DEPENDENCY_DAG.add_node(child_key)
                if (main_key, child_key) not in Registry.DEPENDENCY_DAG.edges:
                    Registry.DEPENDENCY_DAG.add_edge(main_key, child_key)

            if main_key.name == 'calibrator':
                print()

            child_variants = list(set(child_variants))
            child.variants = child.variants if child.variants is not None else []
            built_config.get(child_name).variants = child_variants + child.variants

            if built_config.get(child_name).variants is not None and child_key is not None:
                Registry.DEPENDENCY_DAG.nodes[child_key]['variants'] = [str(key)
                                                                        for key in built_config.get(child_name).variants]

        # Register each combination of parameter variants
        parameter_combinations = built_config.get_variants_combinations()

        # No combinations have been found -> check if already registered
        if not len(parameter_combinations):
            return new_registered_keys

        # Register each combination
        combination_keys = []
        for combination in parameter_combinations:
            combination_tags = set()
            for key, value in combination.items():
                if type(value) != RegistrationKey:
                    combination_tags.add(f'{key}={value}')
                else:
                    for tag in value.tags:
                        combination_tags.add(f'{key}.{tag}')
                    if value.namespace != namespace:
                        combination_tags.add(f'{key}.{value.namespace}')
            combination_tags = tags.union(combination_tags) if tags is not None else combination_tags
            combination_key = RegistrationKey(name=name,
                                              tags=combination_tags,
                                              namespace=namespace)
            combination_keys.append(str(combination_key))

            if not Registry.is_in_registry(registration_key=combination_key):
                combination_key = Registry.register_and_bind(config_class=config_class,
                                                             config_constructor=config_class.get_delta_class_copy,
                                                             config_kwargs={
                                                                 'params': combination,
                                                                 'constructor': config_constructor,
                                                                 'constructor_kwargs': config_kwargs
                                                             },
                                                             component_class=component_class,
                                                             name=name,
                                                             tags=combination_tags,
                                                             namespace=namespace)
            new_registered_keys.append(combination_key)

        Registry.DEPENDENCY_DAG.nodes[main_key]['variants'] = combination_keys

        return new_registered_keys

    @staticmethod
    def add_and_bind_variants(
            config_class: Type[Configuration],
            component_class: Type[Component],
            name: str,
            namespace: str = 'generic',
            tags: Tag = None,
            config_constructor: Callable[[Any], Configuration] = None,
            config_kwargs: Optional[Dict] = None,
    ):
        """
        Registers and binds all possible ``Configuration`` variants.
        A configuration variant is a variant of ``Configuration`` parameters.
        Given a ``Configuration`` class, all its variants are retrieved, registered in the ``Registry`` and bound
        to the given ``Component``.

        Args:
            config_class: the class of the ``Configuration``
            component_class: the ``Component`` class to bound to the ``Configuration`` via its ``RegistrationKey``
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            config_constructor: callable that builds the configuration instance (just like ``get_default()``)
            config_kwargs: optional constructor arguments

        Returns:
            the list of ``RegistrationKey`` used to register each ``Configuration`` variant
        """
        config_constructor = config_constructor if config_constructor is not None else config_class.get_default
        config_kwargs = config_kwargs if config_kwargs is not None else {}

        # Main key
        main_key = RegistrationKey(name=name, tags=tags, namespace=namespace)

        if main_key not in Registry.REGISTRATION_REGISTRY:
            Registry.REGISTRATION_REGISTRY[main_key] = partial(Registry.register_and_bind_variants,
                                                               config_class=config_class,
                                                               component_class=component_class,
                                                               name=name,
                                                               tags=tags,
                                                               namespace=namespace,
                                                               config_constructor=config_constructor,
                                                               config_kwargs=config_kwargs)

        if not Registry.is_in_graph(name=name, tags=tags, namespace=namespace):
            Registry.DEPENDENCY_DAG.add_node(main_key)
            Registry.DEPENDENCY_DAG.add_edge(Registry.ROOT_KEY, main_key)

        built_config = config_constructor(**config_kwargs)

        for child_name, child in built_config.children.items():
            child_key = child.value
            if child_key is not None:
                if not Registry.is_in_graph_from_key(child_key):
                    Registry.DEPENDENCY_DAG.add_node(child_key)

                Registry.DEPENDENCY_DAG.add_edge(main_key, child_key)

            if child.variants is not None:
                for variant in child.variants:
                    if not Registry.is_in_graph_from_key(variant):
                        Registry.DEPENDENCY_DAG.add_node(variant)
                    Registry.DEPENDENCY_DAG.add_edge(main_key, variant)

        # Register each combination of parameter variants
        parameter_combinations = built_config.get_variants_combinations(validate=False)

        # Register each combination
        combination_keys = []
        for combination in parameter_combinations:
            combination_tags = set()
            for key, value in combination.items():
                if type(value) != RegistrationKey:
                    combination_tags.add(f'{key}={value}')
                else:
                    for tag in value.tags:
                        combination_tags.add(f'{key}.{tag}')
                    if value.namespace != namespace:
                        combination_tags.add(f'{key}.{value.namespace}')
            combination_tags = tags.union(combination_tags) if tags is not None else combination_tags
            combination_key = RegistrationKey(name=name,
                                              tags=combination_tags,
                                              namespace=namespace)
            combination_keys.append(str(combination_key))

        Registry.DEPENDENCY_DAG.nodes[main_key]['variants'] = combination_keys

    @staticmethod
    def expand_and_resolve_registration(
            namespace: Optional[str] = None
    ):
        topological_sorted = list(reversed(list(nx.topological_sort(Registry.DEPENDENCY_DAG))))

        if namespace is not None:
            topological_sorted = [key for key in topological_sorted if key.namespace == namespace]

        for key in topological_sorted:
            if key in Registry.REGISTRATION_REGISTRY:
                registration_method = Registry.REGISTRATION_REGISTRY.pop(key)
                Registry.REGISTRATION_REGISTRY = {key: value for key, value in Registry.REGISTRATION_REGISTRY.items()
                                                  if value != registration_method}
                registration_method()

    @staticmethod
    def show_dependencies():
        g = Network(height="1000px",
                    width="100%",
                    notebook=True,
                    cdn_resources='remote',
                    select_menu=True,
                    filter_menu=True,
                    directed=True)
        g.toggle_hide_edges_on_drag(True)
        g.barnes_hut()
        dag_str = nx.DiGraph()
        dag_str.update(
            nodes=[(str(node), node_props) for (node, node_props) in Registry.DEPENDENCY_DAG.nodes(data=True)],
            edges=[(str(s), str(t)) for (s, t) in Registry.DEPENDENCY_DAG.edges()])

        for node in dag_str.nodes(data=True):
            node[1]['title'] = node[1]['variants'] if 'variants' in node[1] else 'No variants'

        g.from_nx(dag_str)
        g.set_options(options="""
            const options = {
              "configure": { "enabled": true },
              "nodes": {
                "borderWidth": null,
                "borderWidthSelected": null,
                "opacity": 1,
                "font": {"size": 9},
                "size": null
              },
              "edges": {
                "arrows": {
                  "to": {
                    "enabled": true
                  }
                },
                "color": {
                  "inherit": true
                },
                "selfReferenceSize": null,
                "selfReference": {
                  "angle": 0.7853981633974483
                },
                "smooth": {
                  "forceDirection": "none"
                }
              },
                "layout": {
                "hierarchical": {
                  "enabled": true,
                  "nodeSpacing": 260,
                  "treeSpacing": 260,
                  "sortMethod": "directed"
                }
              },
              "interaction": {
                "hideEdgesOnDrag": true,
                "hover": true
              },
              "physics": {
                "enabled": false,
                "repulsion": {
                  "nodeDistance": 200
                },
                "minVelocity": 0.75,
                "solver": "repulsion"
              }
            }
        """)
        g.show('dependencies.html')


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
    'DisconnectedGraphException',
    'NotADAGException'
]
