from stacked_diffs.utils.classes import Alias, CommandConfig

# --- Built-in Default Aliases ---
DEFAULT_ALIASES: dict[str, Alias] = {
    "update": Alias(
        description="After amending a commit, rebase all descendant branches.",
        command=CommandConfig(
            run="git rebase $SD_PARENT_BRANCH",
            descendants_only=True,
        ),
        continue_cmd="git rebase --continue",
        abort_cmd="git rebase --abort",
    ),
    "sync": Alias(
        description="Update trunk and rebase the entire current stack on top.",
        command=CommandConfig(
            run="git rebase $SD_TRUNK_BRANCH",
            pre_flight="git stash push -u -m sd-sync-autostash || true ; git fetch $REMOTE ; git checkout $SD_TRUNK_BRANCH ; git reset --hard $REMOTE/$SD_TRUNK_BRANCH",
            post_flight="git checkout $SD_START_BRANCH ; git stash pop || true",
            start_from_root=True,
        ),
        env={"REMOTE": "upstream"},
        continue_cmd="git rebase --continue",
        abort_cmd="git rebase --abort",
    ),
}
