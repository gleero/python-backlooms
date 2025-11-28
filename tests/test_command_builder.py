"""
Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import inspect
from typing import Annotated, Literal, get_args, get_origin

import pytest
from typer.models import ArgumentInfo, OptionInfo

from backlooms._utils.command_builder import (
    build_run_command,
    build_start_command,
)


class Recorder:
    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture()
def run_items():
    return [
        ("alpha", "Alpha worker"),
        ("beta", "Beta worker"),
    ]


@pytest.fixture()
def start_items():
    return [
        ("worker", "Run background workers"),
        ("scheduler", "Run scheduled jobs"),
    ]


@pytest.fixture()
def recorder():
    return Recorder()


def test_build_run_command_has_single_positional_cmd(run_items, recorder):
    cmd = build_run_command(
        recorder,
        run_items,
        description="Run the selected worker",
        help="Choose the worker to run",
    )
    sig = inspect.signature(cmd)
    assert list(sig.parameters) == ["cmd"]
    p = sig.parameters["cmd"]
    assert p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert p.default is inspect._empty


def test_build_run_command_literal_and_argument(run_items, recorder):
    help_text = "Choose the worker to run"
    cmd = build_run_command(recorder, run_items, description="", help=help_text)
    p = inspect.signature(cmd).parameters["cmd"]

    ann = p.annotation
    assert get_origin(ann) is Annotated
    annotated_args = get_args(ann)
    assert len(annotated_args) >= 2

    # First arg of Annotated is a Literal with a tuple of variants (current impl)
    lit = annotated_args[0]
    assert get_origin(lit) is Literal
    assert get_args(lit) == tuple([name for name, _ in run_items])

    # Second arg is Typer Argument metadata
    meta = annotated_args[1]
    assert isinstance(meta, ArgumentInfo)
    assert getattr(meta, "help") == help_text


def test_build_run_command_includes_description_and_items(run_items, recorder):
    description = "Run the selected worker"
    cmd = build_run_command(recorder, run_items, description=description, help="")
    assert cmd.__doc__ is not None
    assert description in cmd.__doc__
    for name, text in run_items:
        assert f"- {name}: {text}" in cmd.__doc__


def test_build_run_command_kwargs_to_target(run_items, recorder):
    cmd = build_run_command(recorder, run_items, description="", help="")
    cmd(cmd="alpha")
    assert recorder.calls == [{"cmd": "alpha"}]


def test_build_start_command_order_and_defaults(start_items, recorder):
    cmd = build_start_command(recorder, start_items)
    sig = inspect.signature(cmd)

    expected_params = [name for name, _ in start_items] + ["server_only"]
    assert list(sig.parameters.keys()) == expected_params

    for name, _ in start_items:
        p = sig.parameters[name]
        assert p.kind == inspect.Parameter.KEYWORD_ONLY
        assert p.default is True

    p = sig.parameters["server_only"]
    assert p.kind == inspect.Parameter.KEYWORD_ONLY
    assert p.default is False


def test_build_start_command_annotations_and_help(start_items, recorder):
    cmd = build_start_command(recorder, start_items)
    sig = inspect.signature(cmd)

    for name, descr in start_items:
        p = sig.parameters[name]
        ann = p.annotation
        assert get_origin(ann) is Annotated
        ann_args = get_args(ann)
        assert len(ann_args) >= 2
        assert ann_args[0] is bool
        meta = ann_args[1]
        assert isinstance(meta, OptionInfo)

        assert f"--with-{name}/--without-{name}" == meta.default
        assert meta.help == descr


def test_build_start_command_only_flags_and_help_text(start_items, recorder):
    cmd = build_start_command(recorder, start_items)
    p = inspect.signature(cmd).parameters["server_only"]

    ann = p.annotation
    assert get_origin(ann) is Annotated
    ann_args = get_args(ann)
    assert len(ann_args) >= 2
    assert ann_args[0] is bool
    meta = ann_args[1]
    assert isinstance(meta, OptionInfo)

    assert meta.param_decls is not None
    assert "--server-only" == meta.default
    assert "-s" == meta.param_decls[0]

    # Exact text check (ensures the join of named flags is executed)
    expected_help = (
        "Start the server only. Same as --without-worker --without-scheduler."
    )
    assert meta.help == expected_help


def test_build_start_command_kwargs_to_target(start_items, recorder):
    cmd = build_start_command(recorder, start_items)
    cmd(worker=True, scheduler=False, server_only=False)
    assert recorder.calls == [
        {"worker": True, "scheduler": False, "server_only": False}
    ]
