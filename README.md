# gitNL
Deterministic natural-language Git CLI.

## What it does
`git-nl` turns a short natural-language request into a deterministic Git workflow.
It is safety-first: dry-run by default, explicit `--execute` to run commands, and
verification steps to confirm outcomes.

## Repository structure
```
    gitNL
    ├── git_nl
    │   ├── definitions
    │   │   ├── __init__.py
    │   │   ├── entity_extractor.py
    │   │   ├── llm.py
    │   │   ├── router.py
    │   │   ├── rule_definitions.py
    │   │   ├── semantic.py
    │   │   └── types.py
    │   ├── executor
    │   │   ├── __init__.py
    │   │   └── executor.py
    │   ├── planner
    │   │   ├── __init__.py
    │   │   └── rule_plans.py
    │   ├── verifier
    │   │   ├── __init__.py
    │   │   └── verifier.py
    │   ├── __init__.py
    │   ├── __main__.py
    │   ├── cli.py
    │   └── config.py
    ├── git_nl.egg-info
    │   ├── PKG-INFO
    │   ├── SOURCES.txt
    │   ├── dependency_links.txt
    │   ├── entry_points.txt
    │   └── top_level.txt
    ├── tests
    │   ├── test_entity_extractor.py
    │   └── test_router_multi_intent.py
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── features.md
    ├── main.py
    └── pyproject.toml
```

## How it works (three layers)
1. Intent routing: try rules first; if no confident match, fall back to semantic
   matching, then optional LLM fallback as the last resort.
2. Planning: map the chosen intent to a predefined, templated plan of Git
   commands and verification steps.
3. Execution + verification: run the plan (or simulate it), then run verification
   commands to confirm the expected outcome.

## Install
- Python 3.9+
- Git installed and available on PATH

From the repo root:
```
cd gitNL
pip install -e .
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

## How you should use it
- Use short, direct prompts that map to a single Git action.
- Chain multiple actions with "and then" or "after that" for multi-intent input.
- Review the dry-run summary before using `--execute`.
- Keep a clean working tree when performing destructive actions like reset.

## Supported intents (Phase 1)
- Commit changes: "commit my changes", "save changes with message"
- Undo last commit (soft): "undo last commit", "soft reset"
- Push commit: "push my commit", "push changes"
- Create/switch/push branch: "create branch foo", "switch to foo", "push branch foo"
- Pull from origin: "pull origin", "sync with origin"
- Stash changes: "stash my changes"
- Rebase: "rebase onto main"
- Reset soft/hard: "reset --soft HEAD~1", "reset --hard"

See `features.md` for the full rule definitions and command plans.

## Optional LLM fallback
LLM fallback is enabled in config, but only runs when an API key is present.
Without a key, the router stays deterministic (rules + semantic match).

Environment variables:
- `OPENROUTER_API_KEY` (required to enable LLM fallback)
- `OPENROUTER_MODEL` (optional, default: `google/gemini-2.5-flash-lite`)

## Configuration defaults (config.py)
These are the built-in defaults used by the router and planner:
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


## Project layout (high level)
- `git_nl/definitions`: intent routing and entity extraction
- `git_nl/planner`: deterministic plans for each intent
- `git_nl/executor`: dry-run or real execution of the plan
- `git_nl/verifier`: post-execution verification steps
