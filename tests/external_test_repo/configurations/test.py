from cinnamon_core.core.registry import Registry, register
from cinnamon_core.core.configuration import Configuration
from cinnamon_core.core.component import Component


@register
def register_configurations():
	Registry.register_and_bind(configuration_class=Configuration,
		component_class=Component,
		name='test',
		namespace='external')