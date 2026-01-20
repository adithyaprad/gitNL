"""CLI entrypoint wiring the rule-based intent pipeline end-to-end."""

import argparse
import json
from typing import Any, Dict

from git_nl.executor import Executor
from git_nl.intent.router import IntentRouter
from git_nl.planner import Planner
from git_nl.verifier import Verifier


def _print_result(title: str, payload: Any) -> None:
    print(f"\n{title}:")
    print(json.dumps(payload, indent=2))


def run(text: str, execute: bool, dry_run: bool) -> None:
    router = IntentRouter()
    intent_result = router.route(text)
    _print_result("Intent", intent_result.__dict__)

    if intent_result.intent == "unknown":
        return

    planner = Planner()
    plan = planner.build_plan(intent_result)
    _print_result(
        "Plan",
        {
            "intent": plan.intent,
            "steps": [s.command for s in plan.steps],
            "verification": [s.command for s in plan.verification],
        },
    )

    executor = Executor(dry_run=dry_run or not execute)
    verifier = Verifier(executor)

    exec_results = executor.run_plan(plan)
    _print_result(
        "Execution",
        [{"command": r.command, "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr} for r in exec_results],
    )

    if exec_results and exec_results[-1].returncode != 0:
        print("\nExecution halted due to error; verification skipped.")
        return

    verify_results = verifier.verify(plan)
    _print_result(
        "Verification",
        [{"command": r.command, "returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr} for r in verify_results],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Natural-language git CLI (Phase 1) - rule-based intent demo.")
    parser.add_argument("text", help="Natural-language request, e.g., 'undo last commit but keep my changes'")
    parser.add_argument("--execute", action="store_true", help="Actually run commands (unsafe if not intended).")
    parser.add_argument("--no-dry-run", action="store_true", help="Disable dry-run; applies only when --execute is set.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(text=args.text, execute=args.execute, dry_run=not args.no_dry_run)

