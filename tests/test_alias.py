from pathlib import Path

import pytest

from tests.utils import (
    run_sd_command,
)


def test_alias_set_list_rm(git_repo: Path, capsys):
    """Verify `sd alias set, list, rm` and running a user alias."""
    # Set an alias
    run_sd_command(["alias", "set", "my-echo", "--run", "echo hello from my-echo"])
    capsys.readouterr()  # Clear buffer

    # List aliases and check
    run_sd_command(["alias", "list"])
    captured = capsys.readouterr()
    assert "my-echo: User alias for: echo hello from my-echo" in captured.out

    # Run the alias
    run_sd_command(["my-echo"])
    captured = capsys.readouterr()
    assert "hello from my-echo" in captured.out

    # Remove the alias
    run_sd_command(["alias", "rm", "my-echo"])
    capsys.readouterr()  # Clear buffer

    # List again and check it's gone
    run_sd_command(["alias", "list"])
    captured = capsys.readouterr()
    assert "my-echo" not in captured.out

    # Verify trying to run removed alias fails (or is not found)
    with pytest.raises(SystemExit) as e:
        run_sd_command(["my-echo"])
    assert e.value.code != 0


def test_alias_set_overwrite_existing_user_alias(git_repo: Path, capsys):
    """Verify setting an alias overwrites an existing user alias with the same name."""
    run_sd_command(["alias", "set", "my-alias", "--run", "echo first version"])
    capsys.readouterr()

    run_sd_command(["alias", "set", "my-alias", "--run", "echo second version"])
    capsys.readouterr()

    run_sd_command(["alias", "list"])
    captured_list = capsys.readouterr()
    assert "my-alias: User alias for: echo second version" in captured_list.out
    assert "my-alias: User alias for: echo first version" not in captured_list.out

    run_sd_command(["my-alias"])
    captured_run = capsys.readouterr()
    assert "second version" in captured_run.out
    assert "first version" not in captured_run.out


def test_alias_set_missing_run_command(git_repo: Path, capsys):
    """Verify `sd alias set` fails if no --run command is provided."""
    with pytest.raises(SystemExit) as e:
        run_sd_command(["alias", "set", "bad-alias"])
    assert e.value.code == 2  # argparse error code
    captured = capsys.readouterr()
    assert "the following arguments are required: --run" in captured.err

    # Verify the bad alias was not set
    run_sd_command(["alias", "list"])
    captured_list = capsys.readouterr()
    assert "bad-alias" not in captured_list.out


def test_alias_rm_non_existent_alias(git_repo: Path, capsys):
    """Verify `sd alias rm` handles non-existent aliases gracefully."""
    with pytest.raises(SystemExit) as e:
        run_sd_command(["alias", "rm", "no-such-alias"])
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "User alias 'no-such-alias' not found." in captured.err


def test_alias_list_no_user_aliases(git_repo: Path, capsys):
    """Verify `sd alias list` shows only built-in aliases when no user aliases are set."""
    # Ensure no user aliases exist by trying to remove a dummy one (and clearing output)
    with pytest.raises(SystemExit):  # Or just ensure .sd_aliases.json is not there
        run_sd_command(["alias", "rm", "dummy-for-cleanup"])
    capsys.readouterr()

    # If .sd_aliases.json might exist and be empty, this test is fine.
    # If it's guaranteed not to exist, then the output is predictable.
    # For robustness, let's assume it might be empty or non-existent.

    run_sd_command(["alias", "list"])
    captured = capsys.readouterr()

    assert "--- Built-in Aliases ---" in captured.out
    assert "update:" in captured.out  # Check for a known built-in alias
    assert "sync:" in captured.out
    # Check that the "User-defined Aliases" section is not printed if no user aliases
    # The current implementation prints the header even if empty, then nothing under it.
    # If there are truly no user aliases, the .sd_aliases.json won't exist or will be empty.
    # The `handle_alias_list` prints "--- User-defined Aliases ---" if user_aliases is truthy.
    # If it's empty, it won't print that header.
    assert "--- User-defined Aliases (.sd_aliases.json) ---" not in captured.out


def test_alias_set_shadow_builtin_command_name_and_run_behavior(git_repo: Path, capsys):
    """
    Verify that a user can define an alias with the same name as a built-in command (e.g., 'tree'),
    that `alias list` shows the user's definition, but running `sd <command-name>`
    still executes the built-in command due to dispatch precedence.
    """
    # Set a user alias with the same name as the built-in 'tree' command
    run_sd_command(["alias", "set", "tree", "--run", "echo This is the user tree alias"])
    capsys.readouterr()

    # Verify `alias list` shows the user-defined alias
    run_sd_command(["alias", "list"])
    list_output = capsys.readouterr().out
    assert "tree: User alias for: echo This is the user tree alias" in list_output

    # Run `sd tree` and verify it executes the built-in command, not the user alias
    run_sd_command(["tree"])  # This should run the actual tree command
    run_output = capsys.readouterr().out
    assert "This is the user tree alias" not in run_output
    assert (
        "No stacks found to display." in run_output or "'main' (Trunk)" in run_output
    )  # Characteristic output of the real 'tree' command (empty or with stacks)


def test_alias_set_with_advanced_features(git_repo: Path, capsys):
    """Test setting an alias with advanced features like pre-flight, post-flight, env vars, etc."""
    run_sd_command(
        [
            "alias",
            "set",
            "advanced-alias",
            "--run",
            "echo main command",
            "--pre-flight",
            "echo pre-flight command",
            "--post-flight",
            "echo post-flight command",
            "--description",
            "An advanced alias for testing",
            "--continue-cmd",
            "echo continuing",
            "--abort-cmd",
            "echo aborting",
            "--env",
            "TEST_VAR=test_value",
            "--env",
            "ANOTHER_VAR=another_value",
            "--descendants-only",
        ]
    )
    capsys.readouterr()

    # Verify the alias was created with all features
    run_sd_command(["alias", "show", "advanced-alias"])
    captured = capsys.readouterr()
    assert "Alias: advanced-alias (user-defined)" in captured.out
    assert "Description: An advanced alias for testing" in captured.out
    assert "Run command: echo main command" in captured.out
    assert "Pre-flight command: echo pre-flight command" in captured.out
    assert "Post-flight command: echo post-flight command" in captured.out
    assert "Continue command: echo continuing" in captured.out
    assert "Abort command: echo aborting" in captured.out
    assert "Descendants only: Yes" in captured.out
    assert "Environment variables:" in captured.out
    assert "TEST_VAR=test_value" in captured.out
    assert "ANOTHER_VAR=another_value" in captured.out


def test_alias_show_builtin(git_repo: Path, capsys):
    """Test showing details of a built-in alias."""
    run_sd_command(["alias", "show", "update"])
    captured = capsys.readouterr()
    assert "Alias: update (built-in)" in captured.out
    assert "After amending a commit, rebase all descendant branches." in captured.out
    assert "Run command: git rebase $SD_PARENT_BRANCH" in captured.out
    assert "Continue command: git rebase --continue" in captured.out
    assert "Abort command: git rebase --abort" in captured.out


def test_alias_show_nonexistent(git_repo: Path, capsys):
    """Test showing a non-existent alias."""
    with pytest.raises(SystemExit) as e:
        run_sd_command(["alias", "show", "nonexistent"])
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Alias 'nonexistent' not found." in captured.err


def test_alias_list_verbose(git_repo: Path, capsys):
    """Test verbose listing of aliases."""
    # Create a test alias first
    run_sd_command(
        ["alias", "set", "test-verbose", "--run", "echo test", "--description", "Test alias for verbose output"]
    )
    capsys.readouterr()

    # Test verbose listing
    run_sd_command(["alias", "list", "--verbose"])
    captured = capsys.readouterr()
    assert "--- Built-in Aliases ---" in captured.out
    assert "update: After amending a commit, rebase all descendant branches." in captured.out
    assert "Run: git rebase $SD_PARENT_BRANCH" in captured.out
    assert "--- User-defined Aliases (.sd_aliases.json) ---" in captured.out
    assert "test-verbose: Test alias for verbose output" in captured.out
    assert "Run: echo test" in captured.out
