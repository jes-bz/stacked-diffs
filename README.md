# Stacked Diffs CLI Tool (`sd`)

`sd` is a command-line tool for managing complex chains and trees of Git branches locally.
It automates the tedious and error-prone parts of a stacked-diff workflow, such as rebasing stacks, propagating changes, and keeping work in sync with a trunk branch.

It is built around a `run` command that can execute any shell command across your entire dependency tree, with built-in, resumable workflows for common operations like `update` and `sync`.

## Core Philosophy

* **Git is the Source of Truth:** The tool does not maintain its own hidden state. Its context is always derived from your current checked-out branch (`HEAD`). You "switch stacks" by using `git checkout`.
* **Metadata is for Relationships:** The tool only stores metadata that Git doesn't natively track: the forward-linking parent-child relationships between your branches. This data is stored in `.git/stacked_diffs_graph.json`.
* **Alias-Driven Workflows:** Workflows like `sync` are not hardcoded; they are composed as built-in aliases of the core `run` command, demonstrating the tool's flexibility.

## Installation

This tool is designed to be installed with `uv`.

### Recommended Method (for Users)

The `uv tool install` command installs packages in isolated, persistent environments and makes their command-line scripts available on your `PATH`.

1.  **Ensure `uv` is installed.** If you don't have it, follow the [official installation instructions](https://github.com/astral-sh/uv#installation).

2.  **Install `sd` directly from GitHub:**
    ```bash
    uv tool install git+https://github.com/jes-bz/stacked-diffs.git
    ```

3.  **Verify the Installation:**
    ```bash
    sd --help
    ```

### Development Method (for Contributors)

If you want to contribute to the development of `sd`, clone the repository and install it in editable mode.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/jes-bz/stacked-diffs.git
    cd stacked-diffs
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    uv venv
    source .venv/bin/activate
    # On Windows: .venv\Scripts\activate
    ```

3.  **Install in Editable Mode:**
    This command links the `sd` executable to your source code, so any changes you make are immediately reflected.
    ```bash
    uv pip install -e ".[dev]"
    ```

## Command Reference

### `sd run`

This is the central command of the tool. It executes a shell command on the current branch and all of its descendants, traversing the dependency tree.

**Usage:**
`sd run "[command]" [options]`

**Options:**
* `--pre-flight "[command]"`: A command to run once *before* the traversal begins.
* `--post-flight "[command]"`: A command to run once *after* the traversal completes successfully.
* `--continue "[remediation_cmd]"`: Resumes a paused operation. Optionally runs a remediation command first (e.g., `git rebase --continue`).
* `--abort "[remediation_cmd]"`: Aborts a paused operation. Optionally runs a remediation command first (e.g., `git rebase --abort`).

**Environment Variables:**
The following variables are available to the executed `[command]`:
* `$SD_CURRENT_BRANCH`: The branch the command is currently running on.
* `$SD_PARENT_BRANCH`: The parent of the current branch in the stack.
* `$SD_TRUNK_BRANCH`: The configured trunk branch (e.g., `main`).
* `$SD_START_BRANCH`: The branch where the `run` command was initiated.

---

### Built-in Workflows (Aliases)

These are built-in aliases that use `sd run`.

#### `sd update`

After amending a commit, this command rebases all descendant branches onto the current branch.

* **Usage:** `sd update [--continue | --abort]`
* **Underlying Command:** `sd run "git rebase $SD_PARENT_BRANCH" --continue "git rebase --continue" --abort "git rebase --abort"`

#### `sd sync`

Updates the entire stack against the latest version of the remote trunk branch. It safely stashes uncommitted changes, fetches and resets the trunk, rebases the entire tree, and restores your working state.

* **Usage:** `sd sync [--continue | --abort]`
* **Underlying Command:** `sd run "git rebase $SD_TRUNK_BRANCH" --pre-flight "..." --post-flight "..."` (See `sd alias list` for the full definition).

---

### Branch & Metadata Management

#### `sd add <branch-name>`

Creates a new branch and stacks it on top of your current branch.

* **Example:** `git checkout main && sd add feature-base`

#### `sd tree`

Displays all tracked branches and their relationships in a clear, hierarchical tree structure.

* **Example:** `sd tree`

#### `sd prune`

Cleans up your workspace. It finds all tracked branches that have been merged into the trunk, removes their metadata, and deletes the local Git branches.

* **Example:** `sd prune`

#### `sd alias [list|set|rm|show]`

Manage project-specific aliases in a `.sd_aliases.json` file.

* `sd alias list [--verbose]`: Show all built-in and user-defined aliases. Use `--verbose` for detailed information.

The default built-in aliases are equivalent to the following JSON configuration:

```json
{
    "update": {
        "description": "After amending a commit, rebase all descendant branches.",
        "command": {
            "run": "git rebase $SD_PARENT_BRANCH",
            "descendants_only": true
        },
        "continue_cmd": "git rebase --continue",
        "abort_cmd": "git rebase --abort"
    },
    "sync": {
        "description": "Update trunk and rebase the entire current stack on top.",
        "command": {
            "run": "git rebase $SD_TRUNK_BRANCH",
            "pre_flight": "git stash push -u -m sd-sync-autostash ; git fetch $REMOTE ; git checkout $SD_TRUNK_BRANCH ; git reset --hard $REMOTE/$SD_TRUNK_BRANCH",
            "post_flight": "git checkout $SD_START_BRANCH ; git stash pop",
            "start_from_root": true
        },
        "env": {
            "REMOTE": "upstream"
        },
        "continue_cmd": "git rebase --continue",
        "abort_cmd": "git rebase --abort"
    }
}
```

When running an alias like `sync`, you can pass custom arguments to the underlying `sd run` command. For example, to sync against a different remote than the default `upstream`, you can override the `REMOTE` environment variable:

```bash
sd sync REMOTE=origin
```

* `sd alias set <name> --run '<command>' [options]`: Create a new alias with advanced configuration options.
    * `--run '<command>'`: The main command to execute (required)
    * `--description '<text>'`: Description of what the alias does
    * `--pre-flight '<command>'`: Command to run before the main execution
    * `--post-flight '<command>'`: Command to run after successful completion
    * `--continue-cmd '<command>'`: Command for resuming paused operations
    * `--abort-cmd '<command>'`: Command for aborting paused operations
    * `--descendants-only`: Only run on descendant branches, not the current branch
    * `--start-from-root`: Start execution from the root of the dependency tree
    * `--env KEY=VALUE`: Set environment variables (can be used multiple times)
    * **Example:** `sd alias set test --run "pytest -k TestMyFeature" --description "Run specific test suite"`
* `sd alias show <name>`: Display detailed information about a specific alias.
* `sd alias rm <name>`: Remove a user-defined alias.

## Configuration

### Git Executable Path

You can specify a custom path for the `git` executable by setting the `SD_GIT_EXECUTABLE` environment variable. If this variable is not set, `stacked-diffs` will default to using `git` from your system's PATH.

Example:
```bash
export SD_GIT_EXECUTABLE=/usr/local/bin/git
sd --help
```

## License

This project is licensed under the MIT License.
