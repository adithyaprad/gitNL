"""Configuration values for the natural-language git CLI pipeline."""

SEMANTIC_CONFIDENCE_THRESHOLD = 0.80
SEMANTIC_CONFIDENCE_BY_INTENT = {
    "commit_changes": 0.70,
    "undo_commit_soft": 0.80,
    "push_commit_to_origin": 0.80,
    "create_branch": 0.70,
    "switch_branch": 0.70,
    "push_branch": 0.80,
    "pull_origin": 0.70,
    "stash_changes": 0.70,
    "rebase_branch": 0.75,
    "reset_soft": 0.80,
    "reset_hard": 0.80,
}

ENABLE_LLM_FALLBACK = True
LLM_CONFIDENCE_THRESHOLD = 0.60
LLM_TIMEOUT = 6.0

DRY_RUN_DEFAULT = True

# Defaults inserted when user omits values.
DEFAULT_COMMIT_MESSAGE = "default_message"
DEFAULT_BRANCH = "default_branch"
DEFAULT_STASH_MESSAGE = "work in progress"
DEFAULT_RESET_TARGET = "HEAD"
DEFAULT_RESET_TARGET_SOFT = "HEAD~1"
DEFAULT_RESET_TARGET_HARD = "HEAD"