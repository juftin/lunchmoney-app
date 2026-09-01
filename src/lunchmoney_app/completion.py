"""Compatibility wrapper for Click's native shell-completion scripts."""

from __future__ import annotations

from typing import Literal

CompletionShell = Literal["bash", "zsh", "fish"]
"""Shells supported by Click's built-in completion system."""


def render_completion(shell: CompletionShell) -> str:
    """Render native completion for the installed ``lunchmoney-app`` command.

    Parameters
    ----------
    shell : CompletionShell
        Shell whose activation script should be generated.

    Returns
    -------
    str
        Shell-native completion activation source.
    """
    from lunchmoney_app.cli import _render_click_completion

    return _render_click_completion(shell)


__all__ = ["CompletionShell", "render_completion"]
