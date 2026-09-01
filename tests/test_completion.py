"""Tests for generated Bash and Zsh command completion scripts."""

import pytest

from lunchmoney_app.completion import CompletionShell, render_completion


@pytest.mark.parametrize(
    ("shell", "expected_registration"),
    [
        ("bash", "complete -o nosort"),
        ("zsh", "compdef _lunchmoney_app_completion lunchmoney-app"),
    ],
)
def test_completion_scripts_use_click_native_activation(
    shell: CompletionShell,
    expected_registration: str,
) -> None:
    """Emit Click's installable shell-native activation scripts."""
    completion_script = render_completion(shell)

    assert expected_registration in completion_script
    assert "LUNCHMONEY_APP_COMPLETE" in completion_script
