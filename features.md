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
- Branch name: if none provided, defaults to `default_branch` (CLI will note this and you can specify one).
- Steps:
  - `git branch {branch}` — Create branch locally
- Verifications:
  - `git show-ref --verify refs/heads/{branch}` — Validate branch ref exists

## switch_branch
- Triggering words/sentences (must_include_any): `switch branch`, `checkout`, `change branch`, `go to branch`
- Regex patterns: `\b(switch|checkout|change|go)\b.*\bbranch\b`
- Description: User asked to switch branches.
- Branch name: if none provided, defaults to `default_branch` (CLI will note this and you can specify one).
- Steps:
  - `git switch {branch}` — Checkout the target branch
- Verifications:
  - `git rev-parse --abbrev-ref HEAD` — Confirm current branch matches target

## push_branch
- Triggering words/sentences (must_include_any): `push branch`, `publish branch`, `send branch`
- Regex patterns: `\b(push|publish|send)\b.*\bbranch\b`
- Description: User asked to push a branch to origin.
- Branch name: if none provided, defaults to `default_branch` (CLI will note this and you can specify one).
- Steps:
  - `git push -u origin {branch}` — Push branch to origin with upstream
- Verifications:
  - `git ls-remote --heads origin {branch}` — Confirm branch is present on origin

## stash_changes
- Triggering words/sentences (must_include_any): `stash`, `stash changes`, `stash my changes`, `stash work`, `stash current work`
- Regex patterns: `\bstash\b`, `\bstash\b.*\bchanges\b`
- Description: User asked to stash their uncommitted changes.
- Steps:
  - `git status --short` — Preview changes that will be stashed
  - `git stash push -m "{message}"` — Stash uncommitted changes with a message
- Verifications:
  - `git stash list` — Confirm stash entry was created

## rebase_branch
- Triggering words/sentences (must_include_any): `rebase`, `rebase branch`, `rebase onto main`, `rebase with main`
- Regex patterns: `\brebase\b.*\b(onto|on|with|against)\b`
- Description: User asked to rebase the current branch onto another branch.
- Branch name: if none provided, defaults to `default_branch`.
- Steps:
  - `git status --short` — Check working tree before rebase
  - `git fetch origin {branch}` — Ensure upstream branch is up to date
  - `git rebase origin/{branch}` — Rebase current branch onto target
- Verifications:
  - `git status --short` — Ensure working tree clean after rebase
  - `git log --oneline --decorate -5` — Review recent history after rebase

## Origin Commands

## Pull origin
- Triggering words/sentences (must_include_any): `pull origin`, `git pull`, `pull latest`, `sync with origin`, `update from origin`
- Regex patterns: `\b(pull|sync|update)\b.*\borigin\b`
- Description: User asked to pull the latest changes from origin.
- Branch name: if none provided, defaults to `default_branch`.
- Steps:
  - `git status --short` — Preview working tree before pulling
  - `git pull origin {branch}` — Pull latest changes from origin
- Verifications:
  - `git status --short` — Ensure working tree clean after pull
  - `git log -1 --oneline` — Inspect newest commit after pull

## Resets

## reset_soft
- Triggering words/sentences (must_include_any): `soft reset`, `reset soft`, `reset --soft`, `soft reset last commit`
- Regex patterns: `\b(reset|soft)\b.*\bsoft\b`
- Description: User asked to soft reset to a previous commit while keeping changes staged.
- Target: if none provided, defaults to `HEAD~1`.
- Steps:
  - `git reset --soft {target}` — Move HEAD while keeping index and working tree
- Verifications:
  - `git rev-parse HEAD` — Ensure HEAD moved to target
  - `git status --short` — Confirm changes remain staged

## reset_hard
- Triggering words/sentences (must_include_any): `hard reset`, `reset hard`, `reset --hard`, `discard my changes`
- Regex patterns: `\b(reset|hard)\b.*\bhard\b`, `\bdiscard\b.*\bchanges\b`
- Description: User asked to hard reset and discard local changes.
- Target: if none provided, defaults to `HEAD`.
- Steps:
  - `git reset --hard {target}` — Reset HEAD and working tree, discarding changes
- Verifications:
  - `git rev-parse HEAD` — Ensure HEAD moved to target
  - `git status --short` — Confirm working tree is clean