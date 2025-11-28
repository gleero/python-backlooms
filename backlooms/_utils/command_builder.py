"""
CLI command builders used by the Backlooms framework.

This module provides small helpers to dynamically construct Typer commands
with precise type annotations and rich help text, while keeping the command
implementation functions themselves minimal. The builders create callables
and attach runtime `inspect.Signature` objects so that Typer can render
choices, options, and help automatically from the provided metadata.

Notes:
- Builders avoid side effects and do not bind application logic; they only
  prepare typed callables. Actual execution is delegated to the callable that
  you pass in (e.g., Application methods).
- The produced functions keep simple bodies to remain testable and easy to
  reason about; most of the dynamic behavior lives in the synthesized
  signatures and docstrings.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import inspect
from typing import Annotated, Callable, Literal

from typer import Argument, Option


def build_run_command(
    fn: Callable,
    items: list[tuple[str, str]],
    *,
    description: str = "",
    help: str = "",
) -> Callable:
    """
    Construct a Typer command that runs a specific worker (or named command).

    This helper synthesizes a callable and assigns a runtime `inspect.Signature`
    so that Typer renders a positional `cmd` argument with constrained choices
    and contextual help. The returned callable delegates execution to the
    provided `fn`, forwarding keyword arguments as-is.

    Parameters:
    - fn: A target callable that will be invoked when the command runs. It must
      accept keyword arguments compatible with the synthesized signature
      (e.g., `cmd`).
    - items: A list of pairs `(name, description)` describing allowed command
      names (usually worker names) and their human-readable descriptions. These
      names form the allowed `Literal` choices for the `cmd` argument and are
      also used to build the help text.
    - description: A short paragraph placed into the generated function
      docstring; Typer will render it as the command description.
    - help: Help text for the `cmd` argument (displayed by Typer).

    Returns:
    - Callable: A function object suitable for decorating with
      `@app.command(...)`. Its body only forwards arguments to `fn`; the
      behavior is primarily driven by the synthesized signature and docstring.

    Notes:
    - Type constraints are applied via `typing.Literal` over provided `items`.
    - The command function itself stays intentionally thin to keep logic testable
      and to separate execution from presentation (help/choices).
    """

    variants = []
    descriptions: list[str] = []

    for item in items:
        variants.append(item[0])
        descriptions.append(f"- {item[0]}: {item[1]}")

    def run_command(**kwargs):
        fn(**kwargs)

    run_command.__signature__ = inspect.Signature(  # type: ignore
        parameters=[
            inspect.Parameter(
                name="cmd",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect._empty,
                annotation=Annotated[
                    Literal[tuple(variants)],  # noqa
                    Argument(help=help),
                ],
            ),
        ],
        return_annotation=None,
    )
    run_command.__doc__ = f"{description}\n\n{'\n'.join(descriptions)}"

    return run_command


def build_start_command(
    fn: Callable,
    items: list[tuple[str, str]],
) -> Callable:
    """
    Construct a Typer command that starts multiple components with toggles.

    The builder creates a callable with a synthesized signature consisting of
    keyword-only boolean options for each `(name, description)` provided in
    `items`, exposing paired `--with-<name>/--without-<name>` flags. It also
    appends a global `--server-only` flag that disables all item-backed options
    for convenience.

    Parameters:
    - fn: A target callable invoked with the collected keyword arguments for
      each item (by its name) and the `server_only` boolean flag.
    - items: A list of pairs `(name, description)` that define switchable
      components. Each name becomes a keyword-only boolean with a descriptive
      help message derived from `description`.

    Returns:
    - Callable: A function object suitable for decorating with
      `@app.command(...)`. Its body simply forwards keyword args to `fn` while
      the dynamic signature drives Typer's CLI rendering.

    Notes:
    - All item flags default to `True` (with-<name>); users can negate them via
      the generated `--without-<name>` form.
    - The `server_only` option defaults to `False` and acts as a shorthand to
      disable all item-backed components.
    """

    def start_command(**kwargs):
        fn(**kwargs)

    parameters: list[inspect.Parameter] = []
    named = []

    for item in items:
        parameters.append(
            inspect.Parameter(
                name=item[0],
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=True,
                annotation=Annotated[
                    bool,
                    Option(f"--with-{item[0]}/--without-{item[0]}", help=item[1]),
                ],
            ),
        )
        named.append(f"--without-{item[0]}")

    parameters.append(
        inspect.Parameter(
            name="server_only",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=False,
            annotation=Annotated[
                bool,
                Option(
                    "--server-only",
                    "-s",
                    help=f"Start the server only. Same as {' '.join(named)}.",
                ),
            ],
        ),
    )

    start_command.__signature__ = inspect.Signature(  # type: ignore
        parameters=parameters,
        return_annotation=None,
    )

    return start_command
