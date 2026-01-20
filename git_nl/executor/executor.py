"""Command executor with optional dry-run safety."""

import subprocess
from dataclasses import dataclass
from typing import List

from git_nl import config
from git_nl.planner import Plan


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str


class Executor:
    """Executes plan steps sequentially, stopping on first error."""

    def __init__(self, dry_run: bool = config.DRY_RUN_DEFAULT) -> None:
        self.dry_run = dry_run

    def run_plan(self, plan: Plan) -> List[CommandResult]:
        results: List[CommandResult] = []
        for step in plan.steps:
            results.append(self._run_command(step.command))
            if results[-1].returncode != 0:
                break
        return results

    def _run_command(self, command: str) -> CommandResult:
        if self.dry_run:
            return CommandResult(command=command, returncode=0, stdout="(dry-run)", stderr="")

        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )

