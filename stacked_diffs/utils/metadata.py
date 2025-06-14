import json
import sys
from dataclasses import asdict
from pathlib import Path

from stacked_diffs.utils import git
from stacked_diffs.utils.classes import Alias, Graph, ResumeState
from stacked_diffs.utils.default_aliases import DEFAULT_ALIASES


class MetadataManager:
    """Manages all file-based state for the tool."""

    def __init__(self):
        self.git_root: Path = git.get_git_root()
        self.graph_path: Path = self.git_root / ".git" / "stacked_diffs_graph.json"
        self.user_alias_path: Path = self.git_root / ".sd_aliases.json"

    # --- Graph Management ---
    def load_graph(self) -> Graph:
        """Loads the metadata from the file, returning a default if it doesn't exist."""
        if not self.graph_path.exists():
            return Graph(
                version=3,
                trunk="main",
                branches={},
                resume_state=None,
                aliases={},
            )
        try:
            with open(self.graph_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert alias dicts to Alias dataclass instances
                if "aliases" in data:
                    data["aliases"] = {k: Alias(**v) for k, v in data["aliases"].items()}
                return Graph.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error: Corrupted metadata file '{self.graph_path}': {e}", file=sys.stderr)
            print("The metadata file will be backed up and recreated.", file=sys.stderr)
            # Backup corrupted file
            backup_path = self.graph_path.with_suffix(".json.backup")
            self.graph_path.rename(backup_path)
            print(f"Corrupted file backed up to: {backup_path}", file=sys.stderr)
            sys.exit(1)

    def save_graph(self, data: Graph) -> None:
        """Saves the metadata to the file."""
        # Convert dataclass to dict for JSON serialization
        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(asdict(data), f, indent=2)

    def get_resume_state(self) -> ResumeState | None:
        graph = self.load_graph()
        return graph.resume_state

    def save_resume_state(self, state: ResumeState) -> None:
        graph = self.load_graph()
        graph.resume_state = state
        self.save_graph(graph)

    def clear_resume_state(self) -> None:
        graph = self.load_graph()
        if graph.resume_state:
            graph.resume_state = None
            self.save_graph(graph)

    # --- Alias Management ---
    def load_user_aliases(self) -> dict[str, Alias]:
        """Loads aliases from the user-facing .sd_aliases.json file."""
        if not self.user_alias_path.exists():
            return {}
        try:
            with open(self.user_alias_path, "r", encoding="utf-8") as f:
                return {k: Alias.from_dict(v) for k, v in json.load(f).items()}
        except (json.JSONDecodeError, IOError) as e:
            print(
                f"Warning: Could not read or parse .sd_aliases.json: {e}",
                file=sys.stderr,
            )
            return {}

    def save_user_aliases(self, aliases: dict[str, Alias]) -> None:
        """Saves aliases to the user-facing .sd_aliases.json file."""
        with open(self.user_alias_path, "w", encoding="utf-8") as f:
            json.dump(aliases, f, indent=2, sort_keys=True)

    def get_all_aliases(self) -> dict[str, Alias]:
        """Returns a merged dictionary of default and user aliases."""
        user_aliases = self.load_user_aliases()
        # User aliases take precedence over defaults
        return {**DEFAULT_ALIASES, **user_aliases}
