"""Defines the plan for each intent, includes steps and verification commands. rename to rule_plans.py"""

from dataclasses import dataclass, field
from typing import Dict, List

from git_nl.definitions.types import IntentResult


@dataclass
class PlanStep:
    command: str
    description: str = ""


@dataclass
class Plan:
    intent: str
    steps: List[PlanStep] = field(default_factory=list)
    verification: List[PlanStep] = field(default_factory=list)


class Planner:
    """Maps intents to predefined workflows."""

    def __init__(self) -> None:
        self.intent_plans = self._build_plans()

    def build_plan(self, intent_result: IntentResult) -> Plan:
        if intent_result.intent not in self.intent_plans:
            raise ValueError(f"No plan defined for intent '{intent_result.intent}'.")

        template = self.intent_plans[intent_result.intent]
        steps = [self._fill(step.command, intent_result.entities, step.description) for step in template.steps]
        verification = [
            self._fill(step.command, intent_result.entities, step.description) for step in template.verification
        ]
        return Plan(intent=intent_result.intent, steps=steps, verification=verification)

    def _fill(self, command: str, entities: Dict[str, str], description: str) -> PlanStep:
        enriched = dict(entities or {})
        msg = enriched.get("message", "").strip()
        if not msg:
            enriched["message"] = "test commit"
        filled = command.format(**enriched) if enriched else command
        return PlanStep(command=filled, description=description)

    def _build_plans(self) -> Dict[str, Plan]:
        return {
            "undo_commit_soft": Plan(
                intent="undo_commit_soft",
                steps=[PlanStep(command="git reset --soft HEAD~1", description="Move HEAD back one commit, keep files")],
                verification=[
                    PlanStep(
                        command="git rev-parse HEAD",
                        description="Ensure HEAD moved to previous commit",
                    ),
                    PlanStep(
                        command="git status --short",
                        description="Confirm working tree is preserved",
                    ),
                ],
            ),
            "commit_changes": Plan(
                intent="commit_changes",
                steps=[
                    PlanStep(command="git status --short", description="Preview pending changes"),
                    PlanStep(command="git add -A", description="Stage all changes"),
                    PlanStep(command='git commit -m "{message}"', description="Create commit with provided message"),
                ],
                verification=[
                    PlanStep(command="git log -1 --oneline", description="Verify commit was recorded"),
                ],
            ),
            "create_branch": Plan(
                intent="create_branch",
                steps=[
                    PlanStep(command="git branch {branch}", description="Create branch locally"),
                ],
                verification=[
                    PlanStep(
                        command="git show-ref --verify refs/heads/{branch}",
                        description="Validate branch ref exists",
                    ),
                ],
            ),
            "switch_branch": Plan(
                intent="switch_branch",
                steps=[
                    PlanStep(command="git switch {branch}", description="Checkout the target branch"),
                ],
                verification=[
                    PlanStep(
                        command="git rev-parse --abbrev-ref HEAD",
                        description="Confirm current branch matches target",
                    ),
                ],
            ),
            "push_branch": Plan(
                intent="push_branch",
                steps=[
                    PlanStep(command="git push -u origin {branch}", description="Push branch to origin with upstream"),
                ],
                verification=[
                    PlanStep(
                        command="git ls-remote --heads origin {branch}",
                        description="Confirm branch is present on origin",
                    ),
                ],
            ),
            "push_commit_to_origin": Plan(
                intent="push_commit_to_origin",
                steps=[
                    PlanStep(command="git status --short", description="Preview working tree before push"),
                    PlanStep(command="git push origin HEAD", description="Push current HEAD to origin"),
                ],
                verification=[
                    PlanStep(command="git status --short", description="Ensure working tree clean after push"),
                    PlanStep(command="git ls-remote --heads origin", description="Confirm branches present on origin"),
                ],
            ),
        }

