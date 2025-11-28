"""
Async-friendly Typer wrapper for building CLI actions.

This module defines `CLIAction`, a thin wrapper around `typer.Typer` that
allows declaring commands and callbacks as `async def` while keeping Typer's
native API and behavior. If a command or callback is asynchronous, it will be
run within an event loop automatically; synchronous functions remain unchanged.

Example:
    ```python
    from backlooms import CLIAction

    action = CLIAction(name="migration", help="Manage database migrations")

    @action.command("current", help="Display current revision")
    async def action_current():
        ...
    ```

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import asyncio
import inspect
from argparse import ArgumentParser
from functools import partial, wraps
from typing import Any, Callable, Dict, Optional, Type, Union

import typer
from typer.core import TyperCommand
from typer.models import CommandFunctionType, Default


CLIExtraType = Callable[[ArgumentParser], Any]


class CLIAction(typer.Typer):
    """
    Typer application with transparent support for async commands.

    Purpose:
        - Provide an interface identical to `typer.Typer` while enabling
          `async def` command and callback functions without additional glue.

    Behavior:
        - When a decorated function is asynchronous, the decorator runs it
          using `asyncio.run(...)`. Synchronous functions are passed through.
        - Command registration, help rendering, and other Typer features behave
          the same as with `typer.Typer`.

    Notes:
        - This class does not alter command semantics; it only adapts how
          functions are executed based on whether they are coroutine functions.
    """

    @staticmethod
    def maybe_run_async(decorator, f):
        """
        Adapt a Typer decorator to execute async functions transparently.

        Parameters:
            decorator: The Typer-provided decorator callable returned by
                `Typer.command(...)` or `Typer.callback(...)`.
            f: The function being decorated (sync or async).

        Returns:
            The original function `f` after it has been registered with Typer.

        Notes:
            - If `f` is asynchronous, a small wrapper is registered that runs
              the coroutine via `asyncio.run(...)`.
            - Intended for internal use by `CLIAction`; end users typically
              interact through `.command(...)` or `.callback(...)`.
        """
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            def runner(*args, **kwargs):
                return asyncio.run(f(*args, **kwargs))

            decorator(runner)
        else:
            decorator(f)
        return f

    def callback(self, *args, **kwargs):
        """
        Register an application-level callback with async support.

        Parameters:
            *args, **kwargs: Same parameters accepted by `typer.Typer.callback`.

        Returns:
            A decorator that can be applied to a function. If the function is
            asynchronous, it will be executed via `asyncio.run(...)` when
            invoked by Typer.
        """
        decorator = super().callback(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)

    def command(
        self,
        name: Optional[str] = None,
        *,
        cls: Optional[Type[TyperCommand]] = None,
        context_settings: Optional[Dict[Any, Any]] = None,
        help: Optional[str] = None,
        epilog: Optional[str] = None,
        short_help: Optional[str] = None,
        options_metavar: str = "[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
        rich_help_panel: Union[str, None] = Default(None),
    ) -> Callable[[CommandFunctionType], CommandFunctionType]:
        """
        Register a command that can be defined as sync or async.

        Parameters mirror `typer.Typer.command` and control how the command is
        exposed in the CLI (name, help, visibility, custom command class, etc.).

        Parameters:
            name: Optional explicit command name. Defaults to the function name.
            cls: Optional custom `TyperCommand` subclass.
            context_settings: Optional Click context settings mapping.
            help: Full help text for the command.
            epilog: Additional text shown after help.
            short_help: Short help used in listings.
            options_metavar: Placeholder name for options in help output.
            add_help_option: Whether to add the automatic help option.
            no_args_is_help: Show help if no arguments are provided.
            hidden: Hide the command from help output.
            deprecated: Mark the command as deprecated in help.
            rich_help_panel: Optional help panel label (Typer rich integration).

        Returns:
            A decorator for a function; if the function is async it will be
            executed via `asyncio.run(...)` at invocation time.
        """
        decorator = super().command(
            name=name,
            cls=cls,
            context_settings=context_settings,
            help=help,
            epilog=epilog,
            short_help=short_help,
            options_metavar=options_metavar,
            add_help_option=add_help_option,
            no_args_is_help=no_args_is_help,
            hidden=hidden,
            deprecated=deprecated,
            rich_help_panel=rich_help_panel,
        )
        return partial(self.maybe_run_async, decorator)
