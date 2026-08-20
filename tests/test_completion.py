"""Tests for generated Bash and Zsh command completion scripts."""

import pytest

from lunchmoney_mcp.completion import CompletionShell, render_completion


@pytest.mark.parametrize(
    ("shell", "expected_registration"),
    [
        ("bash", "complete -F _lunchmoney_mcp lunchmoney-mcp"),
        ("zsh", "compdef _lunchmoney_mcp lunchmoney-mcp"),
    ],
)
def test_completion_scripts_cover_every_runtime_command(
    shell: CompletionShell,
    expected_registration: str,
) -> None:
    """Emit installable scripts that expose the complete public CLI surface."""
    completion_script = render_completion(shell)

    assert expected_registration in completion_script
    for command in ("mcp", "serve", "schedule", "sync", "doctor", "version"):
        assert command in completion_script
    assert "--ephemeral" in completion_script
    assert "--access-token" not in completion_script
    assert "--print-completion" in completion_script
