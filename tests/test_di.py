"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import copy
import importlib
import sys

import pytest
from dependency_injector import containers

from backlooms import BaseConfig

MODULE_NAME = "backlooms.di"


@pytest.fixture(scope="session")
def original_di_module():
    pkg = importlib.import_module(MODULE_NAME)
    original_dict = copy.copy(pkg.__dict__)
    return pkg, original_dict


@pytest.fixture(scope="function")
def di_pkg(original_di_module):
    original_module, original_dict = original_di_module

    sys.modules.pop(MODULE_NAME, None)
    test_module = importlib.import_module(MODULE_NAME)

    try:
        yield test_module
    finally:
        sys.modules[MODULE_NAME] = original_module
        original_module.__dict__.clear()
        original_module.__dict__.update(original_dict)


def test_di_container_type():
    from backlooms.di import DIContainer

    class AppContainer(DIContainer):
        pass

    c = AppContainer()
    assert isinstance(c, containers.DynamicContainer)


def test_di_container_sets_wiring_config_reference(di_pkg):
    DIContainer = di_pkg.DIContainer

    class AppContainer(DIContainer):
        pass

    class MyContainer(DIContainer):
        pass

    # The class-level wiring_config must point to the shared `wiring` object
    assert AppContainer.wiring_config is di_pkg.wiring
    assert MyContainer.wiring_config is di_pkg.wiring


def test_di_container_subclass_keeps_wiring_config(di_pkg):
    DIContainer = di_pkg.DIContainer

    class SubContainer(DIContainer):
        pass

    sub = SubContainer()
    assert sub.wiring_config is di_pkg.wiring


def test_inject(di_pkg):
    assert len(di_pkg.wiring.modules) == 0

    @di_pkg.inject
    def my_test_fn():
        pass  # pragma: nocover

    assert len(di_pkg.wiring.modules) == 1
    assert my_test_fn.__module__ in di_pkg.wiring.modules


def test_use_container_not_initialized(di_pkg):
    DIContainer = di_pkg.DIContainer

    with pytest.raises(RuntimeError, match="Container is not initialized"):
        di_pkg.use_container(DIContainer)


def test_use_container_register(di_pkg):

    class Container(di_pkg.DIContainer):
        pass

    container = Container()

    ret = di_pkg.use_container(Container)
    assert ret is container
    assert isinstance(ret, containers.DynamicContainer)


def test_container_has_config(di_pkg, config):

    class Container(di_pkg.DIContainer):
        pass

    container = Container()
    assert hasattr(container, "config")

    # Not initialized in constructor
    c = getattr(container, "config")
    assert c() is None

    # With config
    container = Container(config=config)
    c = getattr(container, "config")
    assert isinstance(c(), BaseConfig)
