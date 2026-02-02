# git-nl
Deterministic natural-language Git CLI.

## Install
- Python 3.9+
- Git installed and available on PATH

```
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install git-nl
```

## Quick start
Run from inside a Git repository:
```
git-nl "commit my changes with message add README"
git-nl "create a branch feature/login"
git-nl "switch to main and then pull origin"
git-nl "switch to branch feature/login and commit with message test scripts added"
```

By default, `git-nl` dry-runs and prints a summary of execution. To actually execute:
```
git-nl "push my commit" --execute
```

## Flags
- `--execute`: run the Git commands instead of simulating them (unsafe if you
  did not review the plan).
- `--explain`: show routing details like which route matched (rule, semantic and llm).
- `--debug`: verbose JSON output for intent, plan, execution, and verification.

## Optional LLM fallback (API key)
LLM fallback is enabled in config, but only runs when an API key is present.
Without a key, the router stays deterministic (rules + semantic match).

Environment variables:
- `OPENROUTER_API_KEY` (required to enable LLM fallback)
- `OPENROUTER_MODEL` (optional, default: `google/gemini-2.5-flash-lite`)

Example (PowerShell):
```
$env:OPENROUTER_API_KEY="your_key_here"
```

Example (bash/zsh):
```
export OPENROUTER_API_KEY="your_key_here"
```

## Supported intents (Phase 1)
- Commit changes: "commit my changes", "save changes with message"
- Undo last commit (soft): "undo last commit", "soft reset"
- Push commit: "push my commit", "push changes"
- Create/switch/push branch: "create branch foo", "switch to foo", "push branch foo"
- Pull from origin: "pull origin", "sync with origin"
- Stash changes: "stash my changes"
- Rebase: "rebase onto main"
- Reset soft/hard: "reset --soft HEAD~1", "reset --hard"

## How it works (three layers)
1. Intent routing: try rules first; if no confident match, fall back to semantic
   matching, then optional LLM fallback as the last resort.
2. Planning: map the chosen intent to a predefined, templated plan of Git
   commands and verification steps.
3. Execution + verification: run the plan (or simulate it), then run verification
   commands to confirm the expected outcome.

## Configuration defaults (config.py)
- Semantic confidence threshold: `0.80`
- Per-intent semantic thresholds:
  - `commit_changes`: `0.70`
  - `undo_commit_soft`: `0.80`
  - `push_commit_to_origin`: `0.80`
  - `create_branch`: `0.70`
  - `switch_branch`: `0.70`
  - `push_branch`: `0.80`
  - `pull_origin`: `0.70`
  - `stash_changes`: `0.70`
  - `rebase_branch`: `0.75`
  - `reset_soft`: `0.80`
  - `reset_hard`: `0.80`
- LLM fallback enabled: `True`
- LLM confidence threshold: `0.60`
- LLM timeout: `6.0` seconds
- Dry-run default: `True`
- Defaults when user omits values:
  - Commit message: `"default_message"`
  - Branch: `"default_branch"`
  - Stash message: `"work in progress"`
  - Reset target: `"HEAD"`
  - Reset target (soft): `"HEAD~1"`
  - Reset target (hard): `"HEAD"`

