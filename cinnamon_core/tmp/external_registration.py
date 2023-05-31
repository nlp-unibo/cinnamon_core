from pathlib import Path

from cinnamon_core.core.registry import Registry


def retrieve_external_configurations():
    external_path = Path().absolute().parent.parent.joinpath('tests', 'external_test_repo')
    Registry.load_registrations(directory_path=external_path)
    component = Registry.build_component(name='test',
                                         namespace='external')


if __name__ == '__main__':
    retrieve_external_configurations()