import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from tests.utils import run_git_command


@pytest.fixture
def git_repo() -> Generator[Path, Any, None]:
    """
    A pytest fixture that creates a temporary Git repository for testing.

    This fixture creates a "remote" non-bare repository and configures
    the local test repo to use it as 'origin'. This allows for testing
    commands that involve fetching or pushing.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        original_dir = Path.cwd()
        os.chdir(repo_path)

        # Set GIT_EDITOR to prevent interactive prompts
        original_editor = os.environ.get("GIT_EDITOR")
        os.environ["GIT_EDITOR"] = "true"

        try:
            # 1. Create a non-bare repository to act as the remote "origin"
            remote_path = repo_path / "remote"
            remote_path.mkdir()
            run_git_command(["init"], cwd=str(remote_path))

            # Configure the remote repository to accept pushes
            run_git_command(
                ["config", "receive.denyCurrentBranch", "updateInstead"],
                cwd=str(remote_path),
            )
            run_git_command(["config", "user.name", "Remote User"], cwd=str(remote_path))
            run_git_command(
                ["config", "user.email", "remote@example.com"],
                cwd=str(remote_path),
            )

            # 2. Initialize the local repository
            run_git_command(["init", "-b", "main"])
            run_git_command(["config", "user.name", "Test User"])
            run_git_command(["config", "user.email", "test@example.com"])

            # 3. Add the non-bare repository as the 'origin' remote
            run_git_command(["remote", "add", "origin", str(remote_path)])
            # Add another remote for testing custom remote env vars
            run_git_command(["remote", "add", "another_remote", str(remote_path)])
            # Add upstream remote for sync tests
            run_git_command(["remote", "add", "upstream", str(remote_path)])

            # 4. Create an initial commit in the remote repository
            initial_file = remote_path / "initial.txt"
            initial_file.write_text("initial commit")
            run_git_command(["add", "initial.txt"], cwd=str(remote_path))
            run_git_command(
                ["commit", "-m", "Initial commit"],
                cwd=str(remote_path),
            )

            # 5. Pull the initial commit to establish the connection
            run_git_command(["pull", "origin", "main"])

            yield repo_path
        finally:
            # Teardown: Change back to the original directory and restore GIT_EDITOR
            os.chdir(original_dir)
            if original_editor is None:
                if "GIT_EDITOR" in os.environ:
                    del os.environ["GIT_EDITOR"]
            else:
                os.environ["GIT_EDITOR"] = original_editor
