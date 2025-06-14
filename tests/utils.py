import subprocess
import sys
from pathlib import Path

from stacked_diffs import main as sd_main
from stacked_diffs.utils import git


def run_sd_command(args: list[str]):
    """Helper to run the 'sd' tool with a given list of arguments."""
    sys.argv = ["sd", *args]
    try:
        sd_main.main()
    except SystemExit as e:
        if e.code != 0:
            raise


def run_git_command(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """
    Helper to run a Git command using subprocess.

    Parameters:
    - args: A list of strings representing the command and its arguments (e.g., ["commit", "-m", "Initial commit"]).
    - cwd: The working directory to run the command in. Defaults to None (current directory).
    - check: If True, raises CalledProcessError if the command returns a non-zero exit code. Defaults to True.
    - capture_output: If True, captures stdout and stderr. Defaults to True.

    Returns:
    - A subprocess.CompletedProcess instance.
    """
    command = ["git", *args]
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def get_commit_hash(branch: str) -> str:
    """Helper to get the current commit hash of a branch."""
    return run_git_command(["rev-parse", branch]).stdout.strip()


def get_parent_hash(branch: str) -> str:
    """Helper to get the parent commit hash of a branch's HEAD."""
    return run_git_command(["rev-parse", f"{branch}^"]).stdout.strip()
