"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import copy
import importlib
import sys

import pytest
import types

from backlooms.server.adapter import ServerAdapter
from backlooms.workers.registry import WorkerRegistry
from backlooms.di import DIContainer


MODULE_NAME = "backlooms.server.adapters"


@pytest.fixture(scope="session")
def original_adapters_module():
    pkg = importlib.import_module(MODULE_NAME)
    original_dict = copy.copy(pkg.__dict__)
    return pkg, original_dict


@pytest.fixture(scope="function")
def adapters_pkg(original_adapters_module):
    original_module, original_dict = original_adapters_module

    sys.modules.pop(MODULE_NAME, None)
    test_module = importlib.import_module(MODULE_NAME)

    try:
        yield test_module
    finally:
        sys.modules[MODULE_NAME] = original_module
        original_module.__dict__.clear()
        original_module.__dict__.update(original_dict)


class ConcreteAdapter(ServerAdapter):
    def __init__(self):
        super().__init__()
        self.started_with: list[str] | None = None
        self.seen_project_name: str | None = None

    def start(self, workers_to_run: list[str]):  # type: ignore[override]
        assert self._config is not None
        assert self._workers is not None
        assert self._container is not None

        self.started_with = list(workers_to_run)
        self.seen_project_name = self._config.PROJECT_NAME


def test_server_adapter_is_abstract_and_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ServerAdapter()  # type: ignore[abstract] # noqa


def test_server_adapter_init_sets_none_before_setup():
    adapter = ConcreteAdapter()
    assert adapter._config is None
    assert adapter._workers is None
    assert adapter._container is None


def test_server_adapter_setup_injects_context_and_is_accessible_in_start(config):
    reg = WorkerRegistry()
    container = DIContainer()

    adapter = ConcreteAdapter()

    # Call setup and verify identities are stored
    adapter.setup(config=config, workers=reg, container=container)
    assert adapter._config is config
    assert adapter._workers is reg
    assert adapter._container is container

    # Now start with a selection of workers and verify they were received
    to_run = ["alpha", "beta", "gamma"]
    adapter.start(to_run)

    assert adapter.started_with == to_run
    assert adapter.seen_project_name == config.PROJECT_NAME


def test_adapters_lazy_load_success(monkeypatch, adapters_pkg):
    real_import_module = importlib.import_module
    calls = {"count": 0}

    dummy_mod = types.ModuleType("backlooms.server.adapters.fastapi")

    class DummyAdapter:  # sentinel object
        pass

    setattr(dummy_mod, "FastAPIServerAdapter", DummyAdapter)

    def fake_import_module(name, package=None):
        if name == ".fastapi" and package == adapters_pkg.__name__:
            calls["count"] += 1
            return dummy_mod
        return real_import_module(name, package)  # pragma: nocover

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    # First access triggers __getattr__ and lazy import
    obj1 = getattr(adapters_pkg, "FastAPIServerAdapter")
    assert obj1 is DummyAdapter
    assert calls["count"] == 1

    # Second access should be served from module globals cache without extra import
    obj2 = getattr(adapters_pkg, "FastAPIServerAdapter")
    assert obj2 is DummyAdapter
    assert calls["count"] == 1


def test_adapters_lazy_load_importerror(monkeypatch, adapters_pkg):

    def raising_import_module(name, package=None):
        if name == ".fastapi" and package == adapters_pkg.__name__:
            raise ImportError("fastapi missing for test")
        return importlib.import_module(name, package)  # pragma: nocover

    monkeypatch.setattr(importlib, "import_module", raising_import_module)

    with pytest.raises(ImportError) as exc:
        getattr(adapters_pkg, "FastAPIServerAdapter")

    msg = str(exc.value)
    assert "fastapi is not installed" in msg
    assert "pip install 'backlooms[fastapi]'" in msg
    assert exc.value.__cause__ is not None
    assert isinstance(exc.value.__cause__, ImportError)


def test_adapters_unknown_attribute_raises_attribute_error(adapters_pkg):
    with pytest.raises(AttributeError) as exc:
        getattr(adapters_pkg, "UnknownAdapter")

    assert adapters_pkg.__name__ in str(exc.value)
    assert "UnknownAdapter" in str(exc.value)
