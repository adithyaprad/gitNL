"""CLI entrypoint wiring the rule-based intent pipeline end-to-end."""

import argparse
import json
import time
from typing import Any

from git_nl.executor import Executor
from git_nl.definitions.router import IntentRouter
from git_nl.planner import Planner
from git_nl.verifier import Verifier


def _print_result(title: str, payload: Any) -> None:
    print(f"\n{title}:")
    print(json.dumps(payload, indent=2))


def _format_command_results(results: list[Any]) -> list[dict[str, Any]]:
    formatted = []
    for r in results:
        formatted.append(
            {
                "command": r.command,
                "returncode": r.returncode,
                "stdout": r.stdout,
                "stderr": r.stderr,
                "latency_ms": float(f"{r.latency_sec * 1000:.3f}"),
            }
        )
    return formatted


def _print_latency_summary(title: str, results: list[Any]) -> None:
    if not results:
        return
    total_ms = sum(r.latency_sec for r in results) * 1000
    print(f"{title} total latency: {total_ms:.1f} ms")


def run(text: str, execute: bool) -> None:
    router = IntentRouter()
    intent_result = router.route(text)
    route_used = intent_result.source or "unknown"
    print(f"\nRoute used: {route_used}")
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

    executor = Executor(dry_run=not execute)
    verifier = Verifier(executor)

    exec_results = executor.run_plan(plan)
    _print_result(
        "Execution",
        _format_command_results(exec_results),
    )
    _print_latency_summary("Execution", exec_results)

    if exec_results and exec_results[-1].returncode != 0:
        print("\nExecution halted due to error; verification skipped.")
        return

    verify_results = verifier.verify(plan)
    _print_result(
        "Verification",
        _format_command_results(verify_results),
    )
    _print_latency_summary("Verification", verify_results)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Natural-language git CLI (Phase 1) - rule-based intent demo.")
    parser.add_argument("text", help="Natural-language request, e.g., 'undo last commit but keep my changes'")
    parser.add_argument("--execute", action="store_true", help="Actually run commands (unsafe if not intended).")
    return parser.parse_args()


def main() -> None:
    started_at = time.perf_counter()
    args = parse_args()
    run(text=args.text, execute=args.execute)
    total_ms = (time.perf_counter() - started_at) * 1000
    print(f"\nTotal latency (CLI invocation -> completion): {total_ms:.3f} ms")


if __name__ == "__main__":
    main()

