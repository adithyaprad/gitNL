# Usage Guidelines
- Install: run `pip install -e .` from the `gitNL` directory.
- Run (dry-run default): `git-nl "undo last commit"` — prints intent, plan, and simulated execution.
- Execute for real: add `--execute`, e.g. `git-nl "push my commit" --execute`.
- Safety: review the printed Plan steps before running with `--execute`.

# Features - all executable commands

## Commit commands

## commit_changes
- Triggering words/sentences (must_include_any): `commit`, `save changes`, `record changes`
- Regex patterns: `\bcommit\b`, `\bsave\b.*\bchanges\b`
- Description: User asked to create a commit.
- Steps:
  - `git status --short` — Preview pending changes
  - `git add -A` — Stage all changes
  - `git commit -m "{message}"` — Create commit with provided message
- Verifications:
  - `git log -1 --oneline` — Verify commit was recorded

## undo_commit_soft
- Triggering words/sentences (must_include_any): `undo last commit`, `undo previous commit`, `soft reset`, `reset soft`, `uncommit`
- Regex patterns: `\bundo\b.*\bcommit\b`, `\breset\b.*\bsoft\b`
- Description: Explicit request to undo the last commit while keeping changes.
- Steps:
  - `git reset --soft HEAD~1` — Move HEAD back one commit, keep files
- Verifications:
  - `git rev-parse HEAD` — Ensure HEAD moved to previous commit
  - `git status --short` — Confirm working tree is preserved

#Origin Commands

## push_commit_to_origin
- Triggering words/sentences (must_include_any): `push commit`, `push the commit`, `push my commit`, `push this commit`, `push latest commit`, `push commit to origin`, `push commit to remote`, `push changes`, `send changes`
- Regex patterns: `\bpush\b.*\b(origin|remote|commit|changes)\b`
- Description: User asked to push commits to the remote origin.
- Steps:
  - `git status --short` — Preview working tree before push
  - `git push origin HEAD` — Push current HEAD to origin
- Verifications:
  - `git status --short` — Ensure working tree clean after push
  - `git ls-remote --heads origin` — Confirm branches present on origin

## Branch Commands

## create_branch
- Triggering words/sentences (must_include_any): `create branch`, `new branch`, `make branch`
- Regex patterns: `\b(create|make|new)\b.*\bbranch\b`
- Description: User asked to create a branch.
- Steps:
  - `git branch {branch}` — Create branch locally
- Verifications:
  - `git show-ref --verify refs/heads/{branch}` — Validate branch ref exists

## switch_branch
- Triggering words/sentences (must_include_any): `switch branch`, `checkout`, `change branch`, `go to branch`
- Regex patterns: `\b(switch|checkout|change|go)\b.*\bbranch\b`
- Description: User asked to switch branches.
- Steps:
  - `git switch {branch}` — Checkout the target branch
- Verifications:
  - `git rev-parse --abbrev-ref HEAD` — Confirm current branch matches target

## push_branch
- Triggering words/sentences (must_include_any): `push branch`, `publish branch`, `send branch`
- Regex patterns: `\b(push|publish|send)\b.*\bbranch\b`
- Description: User asked to push a branch to origin.
- Steps:
  - `git push -u origin {branch}` — Push branch to origin with upstream
- Verifications:
  - `git ls-remote --heads origin {branch}` — Confirm branch is present on origin
