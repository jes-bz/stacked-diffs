import os
import subprocess
import sys


def run_command(
    command: list[str],
    env_vars: dict | None = None,
) -> str:
    """A helper to run a command and return its stdout, with an optional custom environment."""
    # Combine the custom environment with the existing environment
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            env=env,
        )
        return result.stdout.strip()
    except FileNotFoundError as e:
        print(f"Error: Command not found: {command[0]}", file=sys.stderr)
        if command[0] == os.environ.get("SD_GIT_EXECUTABLE", "git"):
            print(
                f"Git executable '{command[0]}' not found. Check SD_GIT_EXECUTABLE environment variable.",
                file=sys.stderr,
            )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}", file=sys.stderr)
        print(f"Exit Code: {e.returncode}", file=sys.stderr)
        print(f"\n--- STDOUT ---\n{e.stdout}", file=sys.stderr)
        print(f"\n--- STDERR ---\n{e.stderr}", file=sys.stderr)
        sys.exit(1)


def run_shell_command(
    command: str,
    env_vars: dict | None = None,
    fail_on_error: bool = False,
) -> bool:
    """
    Runs a user-provided shell command string.
    Returns True on success, False on failure.
    If fail_on_error is True, exits the program on command failure.
    """
    current_branch_for_prompt = env_vars.get("SD_CURRENT_BRANCH", "shell")
    print(f"[{current_branch_for_prompt}]> {command}")

    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        subprocess.run(
            command,
            text=True,
            check=True,
            encoding="utf-8",
            env=env,
            shell=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}", file=sys.stderr)
        print(f"Exit Code: {e.returncode}", file=sys.stderr)
        if fail_on_error:
            sys.exit(1)
        return False
