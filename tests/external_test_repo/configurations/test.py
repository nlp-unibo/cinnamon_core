from cinnamon_core.core.component import Component
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.core.registry import Registry, register


@register
def register_configurations():
    Registry.add_and_bind(config_class=Configuration,
                          component_class=Component,
                          name='test',
                          namespace='external')
