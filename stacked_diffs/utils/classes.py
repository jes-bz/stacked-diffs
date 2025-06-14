from dataclasses import dataclass, field
from typing import Any


@dataclass
class BranchMeta:
    children: list[str] = field(default_factory=list)


# Dataclasses for command arguments
@dataclass
class AddArgs:
    branch_name: str


@dataclass
class RunArgs:
    command_string: str | None = None
    pre_flight_cmd: str | None = None
    post_flight_cmd: str | None = None
    continue_run: bool | str | None = None
    abort_run: bool | str | None = None
    cli_env_vars: dict[str, str] | None = None  # Added dynamically in main.py
    command_name: str = "run"


@dataclass
class TreeArgs:
    pass  # No specific arguments


@dataclass
class PruneArgs:
    pass  # No specific arguments


@dataclass
class AliasArgs:
    # Base class for alias command arguments
    alias_command: str  # To distinguish subcommands


@dataclass
class AliasSetArgs(AliasArgs):
    alias_name: str
    run: str
    pre_flight: str | None = None
    post_flight: str | None = None
    descendants_only: bool = False
    start_from_root: bool = False
    description: str | None = None
    continue_cmd: str | None = None
    abort_cmd: str | None = None
    env: list[str] | None = None  # Raw KEY=VALUE strings


@dataclass
class AliasListArgs(AliasArgs):
    verbose: bool = False


@dataclass
class AliasShowArgs(AliasArgs):
    alias_name: str


@dataclass
class AliasRmArgs(AliasArgs):
    alias_name: str


@dataclass(frozen=True)
class CommandConfig:
    run: str | None = None
    descendants_only: bool = False
    pre_flight: str | None = None
    post_flight: str | None = None
    start_from_root: bool = False


@dataclass(frozen=True)
class Alias:
    description: str
    command: CommandConfig = field(default_factory=CommandConfig)
    continue_cmd: str | None = None
    abort_cmd: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, alias_dict: dict[str, Any]) -> "Alias":
        return cls(
            description=alias_dict.get("description", ""),
            command=CommandConfig(**alias_dict.get("command", {})),
            continue_cmd=alias_dict.get("continue_cmd"),
            abort_cmd=alias_dict.get("abort_cmd"),
            env=alias_dict.get("env", {}),
        )


@dataclass
class PlanAction:
    branch: str
    parent: str


@dataclass
class ResumeState:
    operation: str
    start_branch: str
    user_command: str
    plan: list[PlanAction]
    alias_name: str
    env_vars: dict[str, str]
    post_flight_cmd: str | None = None

    @classmethod
    def from_dict(cls, resume_state_dict: dict[str, Any]) -> "ResumeState":
        return cls(
            operation=resume_state_dict.get("operation", ""),
            start_branch=resume_state_dict.get("start_branch", ""),
            user_command=resume_state_dict.get("user_command", ""),
            plan=[PlanAction(**action) for action in resume_state_dict.get("plan", [])],
            alias_name=resume_state_dict.get("alias_name", ""),
            env_vars=resume_state_dict.get("env_vars", {}),
            post_flight_cmd=resume_state_dict.get("post_flight_cmd"),
        )


@dataclass
class Graph:
    version: int
    trunk: str
    branches: dict[str, BranchMeta] = field(default_factory=dict)
    resume_state: ResumeState | None = None
    aliases: dict[str, Alias] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, graph_dict: dict[str, Any]) -> "Graph":
        resume_state_data = graph_dict.get("resume_state")
        resume_state_obj = ResumeState.from_dict(resume_state_data) if resume_state_data else None
        return cls(
            version=graph_dict.get("version", 0),
            trunk=graph_dict.get("trunk", ""),
            branches={k: BranchMeta(**v) for k, v in graph_dict.get("branches", {}).items()},
            resume_state=resume_state_obj,
            aliases=graph_dict.get("aliases", {}),
        )
