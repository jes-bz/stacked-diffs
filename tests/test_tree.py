from pathlib import Path

from tests.utils import (
    run_git_command,
    run_sd_command,
)


def test_tree_command(git_repo: Path, capsys):
    """Verify that `sd tree` prints the correct hierarchical structure."""
    run_sd_command(["add", "base"])
    run_sd_command(["add", "service"])  # Stays on service
    run_git_command(["checkout", "base"])
    run_sd_command(["add", "ui"])

    capsys.readouterr()
    run_sd_command(["tree"])

    captured = capsys.readouterr()
    stdout = captured.out

    expected_output = "'main' (Trunk)\n└── base\n    ├── service\n    └── ui\n"
    normalized_stdout = "\n".join(line.strip() for line in stdout.strip().splitlines())
    normalized_expected = "\n".join(
        line.strip() for line in expected_output.strip().splitlines()
    )
    assert normalized_stdout == normalized_expected


def test_tree_no_stacks(git_repo: Path, capsys):
    """Verify `sd tree` output when no branches are stacked."""
    capsys.readouterr()  # Clear buffer
    run_sd_command(["tree"])
    captured = capsys.readouterr()
    expected_output = "No stacks found to display. Your trunk branch is 'main'.\n"
    assert captured.out == expected_output
