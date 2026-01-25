"""Configuration values for the natural-language git CLI pipeline."""

SEMANTIC_CONFIDENCE_THRESHOLD = 0.80
SEMANTIC_CONFIDENCE_BY_INTENT = {
    "commit_changes": 0.70,
    "undo_commit_soft": 0.80,
    "push_commit_to_origin": 0.80,
    "create_branch": 0.70,
    "switch_branch": 0.70,
    "push_branch": 0.80,
}

ENABLE_LLM_FALLBACK = True
LLM_CONFIDENCE_THRESHOLD = 0.60
LLM_TIMEOUT = 6.0

DRY_RUN_DEFAULT = True

# Defaults inserted when user omits values.
DEFAULT_COMMIT_MESSAGE = "default_message"
DEFAULT_BRANCH = "default_branch"