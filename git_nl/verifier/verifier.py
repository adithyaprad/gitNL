"""Verification layer stub for Phase-1."""

from typing import List

from git_nl.executor import CommandResult, Executor
from git_nl.planner import Plan


class Verifier:
    """Runs verification commands after execution."""

    def __init__(self, executor: Executor) -> None:
        self.executor = executor

    def verify(self, plan: Plan) -> List[CommandResult]:
        results: List[CommandResult] = []
        for step in plan.verification:
            results.append(self.executor._run_command(step.command))  # reuse executor behavior
            if results[-1].returncode != 0:
                break
        return results

