"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import pytest
from typer.testing import CliRunner

from backlooms.action import CLIAction


@pytest.fixture
def runner():
    yield CliRunner()


@pytest.fixture
def app():
    yield CLIAction(name="app")


@pytest.mark.parametrize(
    "is_async",
    [False, True],
)
def test_command_decorator_returns_original_function(is_async: bool, app):
    if is_async:

        async def fn():  # type: ignore
            pass  # pragma: nocover

    else:

        def fn():  # type: ignore
            pass  # pragma: nocover

    assert app.command("cmd")(fn) is fn


def test_sync_command(runner, app):
    @app.command("sync")
    def sync_cmd(item: str):
        print("SYNC OK", item)

    result = runner.invoke(app, ["test"])
    assert result.exit_code == 0
    assert "SYNC OK test" in result.stdout


def test_async_command(runner, app):
    @app.command("sync")
    async def async_cmd(item: str):
        print("ASYNC OK", item)

    result = runner.invoke(app, ["test"])
    assert result.exit_code == 0
    assert "ASYNC OK test" in result.stdout


def test_sync_and_async_commands(app, runner):
    @app.command("sync")
    def sync_cmd():
        print("SYNC")

    @app.command("async")
    async def async_cmd():
        print("ASYNC")

    res1 = runner.invoke(app, ["sync"])
    res2 = runner.invoke(app, ["async"])

    assert res1.exit_code == 0 and "SYNC" in res1.stdout
    assert res2.exit_code == 0 and "ASYNC" in res2.stdout


@pytest.mark.parametrize("is_async", [False, True])
def test_callback_runs_for_command(is_async: bool, app, runner):
    if is_async:

        @app.callback()
        async def cb():  # type: ignore
            print("CALLBACK")

    else:

        @app.callback()
        def cb():  # type: ignore
            print("CALLBACK")

    @app.command("do")
    def cmd():
        print("CMD")

    result = runner.invoke(app, ["do"])

    assert result.exit_code == 0
    assert "CALLBACK" in result.stdout
    assert "CMD" in result.stdout
    assert result.stdout.index("CALLBACK") < result.stdout.index("CMD")


def test_callback_decorator_returns_original():
    app = CLIAction(name="app")

    def sync():
        pass  # pragma: nocover

    async def async_():
        pass  # pragma: nocover

    ret_sync = app.callback()(sync)
    ret_async = app.callback()(async_)

    assert ret_sync is sync
    assert ret_async is async_
