"""
Integration tests for main.py entry point and argument parsing.
Tests complex argument parsing scenarios and dynamic alias dispatch.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.utils import run_git_command, run_sd_command


def test_no_arguments_shows_help(git_repo: Path, capsys):
    """Test that running 'sd' with no arguments shows help and exits."""
    with pytest.raises(SystemExit) as exc_info:
        # Simulate running 'sd' with no arguments
        with patch.object(sys, "argv", ["sd"]):
            from stacked_diffs.main import main

            main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "usage:" in captured.err.lower()


def test_invalid_command_error(git_repo: Path, capsys):
    """Test error handling for invalid commands."""
    with pytest.raises(SystemExit) as exc_info:
        run_sd_command(["invalid-command-name"])

    # Should exit with error code
    assert exc_info.value.code != 0


def test_alias_with_continue_and_abort_flags(git_repo: Path):
    """Test alias execution with both --continue and --abort flags."""
    run_sd_command(["alias", "set", "test-conflict", "--run", "echo test"])

    # Test that providing both flags causes an error
    with pytest.raises(SystemExit):
        run_sd_command(["test-conflict", "--continue", "--abort"])


def test_alias_key_value_parsing_edge_cases(git_repo: Path):
    """Test edge cases in KEY=VALUE parsing for aliases."""
    run_sd_command(["alias", "set", "test-parsing", "--run", "echo $TEST_VAR"])

    # Test KEY=VALUE with spaces around equals
    with pytest.raises(SystemExit):
        run_sd_command(["test-parsing", "KEY = VALUE"])  # Spaces around =

    # Test multiple equals signs (should take first split)
    run_sd_command(["test-parsing", "URL=http://example.com/path?param=value"])

    # Test KEY=VALUE mixed with flags - should fail with env var error
    with pytest.raises(SystemExit):
        run_sd_command(["test-parsing", "TEST_VAR=hello", "--continue"])


def test_alias_precedence_over_builtin_commands(git_repo: Path, capsys):
    """Test that built-in commands take precedence over user aliases with same name."""
    # Create user alias with same name as built-in command
    run_sd_command(["alias", "set", "add", "--run", "echo This is user alias add"])

    # Clear the captured output from alias creation
    capsys.readouterr()

    # Running 'sd add' should still execute built-in add command
    with pytest.raises(SystemExit):  # Will fail because no branch name provided
        run_sd_command(["add"])

    captured = capsys.readouterr()
    # Should show built-in add command error, not execute user alias
    assert "This is user alias add" not in captured.out
    assert "This is user alias add" not in captured.err


def test_help_flag_with_alias_name(git_repo: Path, capsys):
    """Test help flag behavior with alias names."""
    run_sd_command(["alias", "set", "test-help", "--run", "echo test"])

    # Clear output from alias creation
    capsys.readouterr()

    # Test that -h and --help work with main command and show aliases
    # The help is printed but may not cause SystemExit in our test harness
    run_sd_command(["-h"])

    captured = capsys.readouterr()
    assert "test-help" in captured.out  # Should show the alias in help
    assert "usage:" in captured.out.lower()  # Should show help text


def test_run_command_validation(git_repo: Path):
    """Test validation of run command arguments."""
    # Test --continue with command string (should fail)
    with pytest.raises(SystemExit):
        run_sd_command(["run", "echo test", "--continue"])

    # Test --abort with command string (should fail)
    with pytest.raises(SystemExit):
        run_sd_command(["run", "echo test", "--abort"])

    # Test run without command and without --continue/--abort (should fail)
    with pytest.raises(SystemExit):
        run_sd_command(["run"])


def test_alias_dispatch_with_complex_arguments(git_repo: Path):
    """Test alias dispatch with complex argument combinations."""
    run_sd_command(["add", "test-branch"])

    # Create alias with pre-flight and post-flight
    run_sd_command(
        [
            "alias",
            "set",
            "complex-alias",
            "--run",
            "echo main: $TEST_VAR",
            "--pre-flight",
            "echo pre: $TEST_VAR",
            "--post-flight",
            "echo post: $TEST_VAR",
            "--env",
            "TEST_VAR=default",
        ]
    )

    # Test with CLI override and continue flag
    run_sd_command(["complex-alias", "TEST_VAR=override"])


def test_non_git_repository_handling(git_repo: Path, capsys):
    """Test behavior when not in a git repository."""
    # Create non-git directory
    non_git_dir = git_repo.parent / "non-git"
    non_git_dir.mkdir(exist_ok=True)

    # Change to non-git directory
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(non_git_dir)

        with pytest.raises(SystemExit) as exc_info:
            run_sd_command(["tree"])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Please run sd from a git repository" in captured.out

    finally:
        os.chdir(original_cwd)


def test_alias_environment_inheritance(git_repo: Path):
    """Test that aliases properly inherit and override environment variables."""
    run_sd_command(["add", "env-test"])

    # Create alias with environment variable
    run_sd_command(
        [
            "alias",
            "set",
            "env-inherit",
            "--run",
            "echo CUSTOM=$CUSTOM_VAR PATH_EXISTS=$PATH",
            "--env",
            "CUSTOM_VAR=from_alias",
        ]
    )

    # Test that system PATH is still available and custom var is set
    run_sd_command(["env-inherit"])


def test_alias_with_descendants_only_flag(git_repo: Path):
    """Test alias with descendants_only configuration."""
    # Create stack
    run_sd_command(["add", "parent"])
    run_sd_command(["add", "child1"])
    run_git_command(["checkout", "parent"])
    run_sd_command(["add", "child2"])

    # Create alias that only runs on descendants
    run_sd_command(
        ["alias", "set", "descendants-test", "--run", "touch file-$SD_CURRENT_BRANCH.txt", "--descendants-only"]
    )

    # Run from parent - should only affect children
    run_git_command(["checkout", "parent"])
    run_sd_command(["descendants-test"])

    # Verify files were created for children but not parent
    assert not (git_repo / "file-parent.txt").exists()
    assert (git_repo / "file-child1.txt").exists()
    assert (git_repo / "file-child2.txt").exists()


def test_alias_with_start_from_root_flag(git_repo: Path):
    """Test alias with start_from_root configuration."""
    # Create deep stack
    run_sd_command(["add", "root"])
    run_sd_command(["add", "middle"])
    run_sd_command(["add", "leaf"])

    # Create alias that starts from root
    run_sd_command(
        ["alias", "set", "root-test", "--run", "touch processed-$SD_CURRENT_BRANCH.txt", "--start-from-root"]
    )

    # Run from leaf - should process entire stack from root
    run_git_command(["checkout", "leaf"])
    run_sd_command(["root-test"])

    # Verify all branches in stack were processed
    assert (git_repo / "processed-root.txt").exists()
    assert (git_repo / "processed-middle.txt").exists()
    assert (git_repo / "processed-leaf.txt").exists()
