from __future__ import annotations

from typing import Any, Iterable, Optional, Dict, TypeVar, Type, cast

from typeguard import check_type

from cinnamon_core import core
from cinnamon_core.core.configuration import Configuration

C = TypeVar('C', bound='Component')

__all__ = ['Component', 'C']


class Component:
    """
    Generic component class.
    Components generally receive data and produce other data as output: i.e., a data transformation process.
    """

    def __init__(
            self,
            config: Configuration,
    ):
        """
        ``Component`` constructor.

        Args:
            config: the ``Configuration`` instance bound to this ``Component``.
        """
        self.config = config

    def __getattr__(
            self,
            item
    ):
        if item == 'config':
            raise AttributeError()
        if item in self.config.fields:
            return self.config.values[item]
        else:
            return object.__getattribute__(self, item)

    def __setattr__(
            self,
            key,
            value
    ):
        if hasattr(self, 'config') and key in self.config.fields:
            self.config.add(name=key, value=value)
        else:
            super().__setattr__(key, value)

    def __dir__(
            self
    ) -> Iterable[str]:
        return list(super().__dir__()) + list(self.config.__dir__())

    def get_delta_copy(
            self: Type[C],
            **kwargs
    ) -> C:
        """
        Builds a ``Component`` deepcopy where its ``Configuration`` differs from the original one by the specified
        parameters' value.

        Returns:
            A ``Component``'s delta copy based on specified new parameters' value.
        """

        config_copy = self.config.get_delta_copy(**kwargs)
        return type(self)(config=config_copy)

    def find(
            self,
            name: str,
            default: Any = None
    ) -> Optional[Any]:
        """
        Searches for the specified attribute within the Component's configuration.
        This operation is also extended to the Component's children.

        Args:
            name: attribute's name to find.
            default: default value if attribute is not found

        Returns:
            The attribute's value in case of success. None, otherwise.
        """

        if name in self.config.fields or hasattr(self, name):
            return getattr(self, name)
        else:
            for child_name, child in self.config.children.items():
                child_find = child.value.find(name=name, default=None)
                if child_find is not None:
                    return child_find

        return default

    def clear(
            self
    ):
        """
        Resets the Component's internal state.
        """
        for child_key, child in self.config.children.items():
            child.clear()

    @property
    def name(
            self
    ) -> Optional[str]:
        return ''

    @classmethod
    def build_component_from_key(
            cls: Type[C],
            registration_key: core.registry.Registration,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> C:
        """
        Syntactic sugar for building a ``Component`` from a ``RegistrationKey``.

        Args:
            registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.
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

        component = core.registry.Registry.build_component_from_key(
            registration_key=registration_key,
            register_component_instance=register_built_component,
            build_args=build_args)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component

    @classmethod
    def build_component(
            cls: Type[C],
            name: str,
            namespace: str = 'default',
            tags: core.registry.Tags = None,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> C:
        """
        Syntactic sugar for building a ``Component`` from a ``RegistrationKey`` in implicit format.

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

        component = core.registry.Registry.build_component(
            name=name,
            tags=tags,
            namespace=namespace,
            register_built_component=register_built_component,
            build_args=build_args
        )
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component

    @classmethod
    def retrieve_component_instance_from_key(
            cls: Type[C],
            registration_key: core.registry.Registration
    ) -> C:
        """
        Syntactic sugar for retrieving a built ``Component`` instance from its corresponding ``Configuration``
         ``RegistrationKey``.

        Args:
            registration_key: the ``RegistrationKey`` used to register the ``Configuration`` class.

        Returns:
            The built ``Component`` instance
        """

        component = core.registry.Registry.retrieve_component_instance_from_key(
            registration_key=registration_key)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component

    @classmethod
    def retrieve_component_instance(
            cls: Type[C],
            name: str,
            namespace: str = 'default',
            tags: core.registry.Tags = None,
            is_default: bool = False
    ) -> C:
        """
        Syntactic sugar for retrieving a built ``Component`` instance from its corresponding ``Configuration``
         ``RegistrationKey`` in implicit format.

        Args:
            name: the ``name`` field of ``RegistrationKey``
            tags: the ``tags`` field of ``RegistrationKey``
            namespace: the ``namespace`` field of ``RegistrationKey``
            is_default: if True, the tag ``default`` is added to ``tags``

        Returns:
            The built ``Component`` instance
        """

        component = core.registry.Registry.retrieve_component_instance(name=name,
                                                                       tags=tags,
                                                                       namespace=namespace,
                                                                       is_default=is_default)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component
