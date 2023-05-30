from __future__ import annotations

from pathlib import Path
from typing import AnyStr, Any, Iterable, Optional, Dict, Union, TypeVar, Type, cast

from dotmap import DotMap
from typeguard import check_type

from cinnamon_core import core
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.utility.pickle_utility import save_pickle, load_pickle

C = TypeVar('C', bound='Component')


class Component:
    """
    Generic component class.
    Components generally receive data and produce other data as output: i.e., a data transformation process.
    """

    def __init__(
            self,
            config: Configuration,
            post_build: bool = True,
            serialization_id: Optional[int] = None
    ):
        """
        ``Component`` constructor.

        Args:
            config: the ``Configuration`` instance bound to this ``Component``.
            post_build: if True, ``Configuration.post_build()`` method is invoked along with corresponding conditions
            evaluation.
        """

        self.config = config
        self.config.validate(stage='pre')

        self.serialization_id: int = serialization_id if serialization_id is not None else 0

        if post_build:
            self.config.post_build(serialization_id=self.serialization_id)
            self.config.validate(stage='post')

    def __getattr__(
            self,
            item
    ):
        if item == 'config':
            raise AttributeError()
        if item in self.__dict__:
            return super().__getattr__(item)
        if item in self.config:
            return self.config[item]
        else:
            raise AttributeError(f'{self.__class__.__name__} has no attribute {item}')

    def __dir__(
            self
    ) -> Iterable[str]:
        return list(super().__dir__()) + list(self.config.__dir__())

    def save(
            self,
            serialization_path: Optional[Union[AnyStr, Path]] = None,
            overwrite: bool = False
    ):
        """
        Saves ``Component`` internal state in Pickle format.
        The ``Component``'s state is its internal Python dictionary state, accessible via ``Component.state`` wrapper.

        Args:
            serialization_path: Path where to save the ``Component`` state.
            overwrite: if True, the existing serialized ``Component`` state is overwritten.
        """

        # Call save() for children as well
        for param_key, param in self.config.items():
            if isinstance(param.value, Component):
                param.value.save(serialization_path=serialization_path,
                                 overwrite=overwrite)

        if serialization_path is not None:
            component_path = serialization_path.joinpath(f'{self.__class__.__name__}_{self.serialization_id}')
            if component_path.exists() and not overwrite:
                raise RuntimeError(f'Cannot overwrite existing serialized state if overwrite={overwrite}')

            save_pickle(filepath=component_path,
                        data=self.state)

    def load(
            self,
            serialization_path: Optional[Union[AnyStr, Path]] = None
    ):
        """
        Loads ``Component``'s internal state from serialized Pickle file.

        Args:
            serialization_path: Path where to load the ``Component``'s state.
        """

        # Call load() for children as well
        for param_key, param in self.config.items():
            if isinstance(param.value, Component):
                param.value.load(serialization_path=serialization_path)

        if serialization_path is not None:
            component_path = serialization_path.joinpath(f'{self.__class__.__name__}_{self.serialization_id}')
            loaded_state = load_pickle(filepath=component_path)
            for key, value in loaded_state.items():
                if key == 'config':
                    for param_key, param in value.items():
                        self.config.add(param)
                elif hasattr(self, key):
                    setattr(self, key, value)

    @property
    def state(
            self
    ) -> DotMap:
        return DotMap(self.__dict__)

    def get_delta_copy(
            self: Type[C],
            params_dict: Optional[Dict[str, Any]] = None
    ) -> C:
        """
        Builds a ``Component`` deepcopy where its ``Configuration`` differs from the original one by the specified
        parameters' value.

        Args:
            params_dict: a dictionary where keys are the ``Configurations``'s parameters' name and values are the new
            values to update.

        Returns:
            A ``Component``'s delta copy based on specified new parameters' value.
        """

        config_copy = self.config.get_delta_copy(params_dict=params_dict)
        return type(self)(config=config_copy,
                          post_build=False)

    def run(
            self,
            *args,
            **kwargs
    ) -> Any:
        """
        General execution entry point of ``Component``.
        The recommended way of subclassing ``Component`` is to define the ``Component``'s logic in this method.
        This general interface allows general-purpose ``Component`` stacking.
        """
        pass

    @classmethod
    def build_component_from_key(
            cls: Type[C],
            config_registration_key: core.registry.Registration,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> C:
        component = core.registry.Registry.build_component_from_key(
            config_registration_key=config_registration_key,
            register_built_component=register_built_component,
            build_args=build_args)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component

    @classmethod
    def build_component(
            cls: Type[C],
            name: str,
            namespace: str = 'generic',
            tags: core.registry.Tag = None,
            register_built_component: bool = False,
            build_args: Optional[Dict] = None
    ) -> C:
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
    def retrieve_built_component_from_key(
            cls: Type[C],
            config_registration_key: core.registry.Registration
    ) -> C:
        component = core.registry.Registry.retrieve_built_component_from_key(
            config_registration_key=config_registration_key)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component

    @classmethod
    def retrieve_built_component(
            cls: Type[C],
            name: str,
            namespace: str = 'generic',
            tags: core.registry.Tag = None,
            is_default: bool = False
    ) -> C:
        component = core.registry.Registry.retrieve_built_component(name=name,
                                                                    tags=tags,
                                                                    namespace=namespace,
                                                                    is_default=is_default)
        check_type('component', component, cls)
        component = cast(type(cls), component)
        return component


__all__ = ['Component']
