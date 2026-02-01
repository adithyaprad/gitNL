"""CLI entrypoint wiring the rule-based intent pipeline end-to-end."""

import argparse
import json
import time
from typing import Any

from git_nl import config
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


def _sum_latency_ms(results: list[Any]) -> float:
    return sum(r.latency_sec for r in results) * 1000


def _determine_outcome(intent_result: Any, exec_results: list[Any], verify_results: list[Any], dry_run: bool) -> str:
    if intent_result.intent == "unknown":
        return "no intent matched"
    if exec_results and exec_results[-1].returncode != 0:
        return f"failed during execution ({exec_results[-1].command})"
    if verify_results and verify_results[-1].returncode != 0:
        return f"failed during verification ({verify_results[-1].command})"
    status = "success"
    if dry_run:
        status += " (dry-run)"
    return status


def _print_summary(
    intent_result: Any,
    route_used: str,
    detect_ms: float,
    exec_ms: float,
    verify_ms: float,
    total_ms: float,
    exec_results: list[Any],
    verify_results: list[Any],
    dry_run: bool,
) -> None:
    entities = intent_result.entities or {}
    branch = (entities.get("branch") or "").strip() or config.DEFAULT_BRANCH
    message = (entities.get("message") or "").strip()
    outcome = _determine_outcome(intent_result, exec_results, verify_results, dry_run)

    def _success_line() -> str:
        intent = intent_result.intent
        suffix = " (dry-run)" if dry_run else ""
        if intent == "commit_changes":
            return f"Changes committed successfully{suffix}"
        if intent == "undo_commit_soft":
            return f"Last commit undone successfully{suffix}"
        if intent == "push_commit_to_origin":
            return f"Commit pushed to origin successfully{suffix}"
        if intent == "create_branch":
            label = branch or "branch"
            return f'Branch "{label}" created successfully{suffix}'
        if intent == "switch_branch":
            label = branch or "branch"
            return f'Switched to branch "{label}" successfully{suffix}'
        if intent == "push_branch":
            label = branch or "branch"
            return f'Branch "{label}" pushed to origin successfully{suffix}'
        return f"Request handled successfully{suffix}"

    def _failure_line() -> str:
        if intent_result.intent == "unknown":
            return "No action taken: could not determine the request."
        if exec_results and exec_results[-1].returncode != 0:
            last = exec_results[-1]
            err = last.stderr or f"returncode {last.returncode}"
            return f"Action failed during execution ({last.command}): {err}"
        if verify_results and verify_results[-1].returncode != 0:
            last = verify_results[-1]
            err = last.stderr or f"returncode {last.returncode}"
            return f"Action failed during verification ({last.command}): {err}"
        return "Action failed."

    print()
    if outcome.startswith("failed") or outcome.startswith("no intent"):
        print(_failure_line())
    else:
        print(_success_line())
        if message:
            print(f'  - Commit message: "{message}"')
        if branch and intent_result.intent in {"create_branch", "switch_branch", "push_branch"}:
            print(f'  - Branch: "{branch}"')


def run(text: str, execute: bool, explain: bool, debug: bool) -> None:
    router = IntentRouter()
    detect_started = time.perf_counter()
    intent_results = router.route_many(text)
    detect_ms = (time.perf_counter() - detect_started) * 1000
    total_intents = len(intent_results)
    for idx, intent_result in enumerate(intent_results):
        detect_ms_for_intent = detect_ms if idx == 0 else 0.0
        if total_intents > 1:
            print(f"\n--- Intent {idx + 1}/{total_intents} ---")

        route_used = intent_result.source or "unknown"
        exec_results: list[Any] = []
        verify_results: list[Any] = []
        exec_ms = 0.0
        verify_ms = 0.0

        if explain or debug:
            print(f"\nRoute used: {route_used}")
        if debug:
            _print_result("Intent", intent_result.__dict__)

        if intent_result.intent != "unknown":
            planner = Planner()
            plan = planner.build_plan(intent_result)

            if debug:
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
            exec_ms = _sum_latency_ms(exec_results)

            if debug:
                _print_result("Execution", _format_command_results(exec_results))
                _print_latency_summary("Execution", exec_results)

            if not exec_results or exec_results[-1].returncode == 0:
                verify_results = verifier.verify(plan)
                verify_ms = _sum_latency_ms(verify_results)

                if debug:
                    _print_result("Verification", _format_command_results(verify_results))
                    _print_latency_summary("Verification", verify_results)
            elif debug:
                print("\nExecution halted due to error; verification skipped.")

        total_ms = detect_ms_for_intent + exec_ms + verify_ms
        _print_summary(
            intent_result=intent_result,
            route_used=route_used,
            detect_ms=detect_ms_for_intent,
            exec_ms=exec_ms,
            verify_ms=verify_ms,
            total_ms=total_ms,
            exec_results=exec_results,
            verify_results=verify_results,
            dry_run=not execute,
        )

        if intent_result.intent == "unknown":
            break
        if exec_results and exec_results[-1].returncode != 0:
            break
        if verify_results and verify_results[-1].returncode != 0:
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Natural-language git CLI (Phase 1) - rule-based intent demo.")
    parser.add_argument("text", help="Natural-language request, e.g., 'undo last commit but keep my changes'")
    parser.add_argument("--execute", action="store_true", help="Actually run commands (unsafe if not intended).")
    parser.add_argument("--explain", action="store_true", help="Show human-readable extras (routes, etc.).")
    parser.add_argument("--debug", action="store_true", help="Show full JSON outputs for intent, plan, execution, verification.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(text=args.text, execute=args.execute, explain=args.explain, debug=args.debug)


if __name__ == "__main__":
    main()

