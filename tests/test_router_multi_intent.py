import unittest

from git_nl.definitions.llm import LLMClauseIntent
from git_nl.definitions.router import IntentRouter, split_clauses
from git_nl import config


class StubLLMDetector:
    def __init__(self) -> None:
        self.calls = 0

    def detect_many(self, clauses, allowed_intents):
        self.calls += 1
        return (
            [
                LLMClauseIntent(clause_index=0, intent="create_branch", confidence=0.95, reason="stub"),
                LLMClauseIntent(clause_index=1, intent="push_branch", confidence=0.92, reason="stub"),
            ],
            "stub",
        )


class ConfigurableLLMDetector:
    def __init__(self, intents) -> None:
        self.intents = intents
        self.calls = 0

    def detect_many(self, clauses, allowed_intents):
        self.calls += 1
        results = [
            LLMClauseIntent(clause_index=idx, intent=intent, confidence=0.9, reason="stub")
            for idx, intent in enumerate(self.intents)
        ]
        return results, "stub"


class RouterMultiIntentTests(unittest.TestCase):
    def test_split_clauses_respects_quotes(self) -> None:
        text = "commit with message 'fix and test' and push commit"
        clauses = split_clauses(text)
        self.assertEqual(clauses, ["commit with message 'fix and test'", "push commit"])

    def test_split_clauses_handles_then_and_semicolon(self) -> None:
        text = "create branch feature/foo; then switch branch feature/foo"
        clauses = split_clauses(text)
        self.assertEqual(clauses, ["create branch feature/foo", "switch branch feature/foo"])

    def test_split_clauses_handles_next_and_after_that(self) -> None:
        text = "commit changes next push commit after that pull origin main"
        clauses = split_clauses(text)
        self.assertEqual(clauses, ["commit changes", "push commit", "pull origin main"])

    def test_route_many_rule_based(self) -> None:
        router = IntentRouter()
        results = router.route_many("commit changes and push commit")
        self.assertEqual([r.intent for r in results], ["commit_changes", "push_commit_to_origin"])
        self.assertEqual([r.source for r in results], ["rule", "rule"])

    def test_route_many_entities_per_clause(self) -> None:
        router = IntentRouter()
        text = "commit with message 'fix login' and push branch feature/foo"
        results = router.route_many(text)
        self.assertEqual([r.intent for r in results], ["commit_changes", "push_branch"])
        self.assertEqual(results[0].entities.get("message"), "fix login")
        self.assertEqual(results[1].entities.get("branch"), "feature/foo")

    def test_route_many_mixed_branch_intents(self) -> None:
        router = IntentRouter()
        text = "create branch feature/foo then switch to branch feature/foo"
        results = router.route_many(text)
        self.assertEqual([r.intent for r in results], ["create_branch", "switch_branch"])
        self.assertEqual(results[0].entities.get("branch"), "feature/foo")
        self.assertEqual(results[1].entities.get("branch"), "feature/foo")

    def test_route_many_pull_and_rebase(self) -> None:
        router = IntentRouter()
        text = "pull origin develop and rebase onto main"
        results = router.route_many(text)
        self.assertEqual([r.intent for r in results], ["pull_origin", "rebase_branch"])
        self.assertEqual(results[0].entities.get("branch"), "develop")
        self.assertEqual(results[1].entities.get("branch"), "main")

    def test_route_many_stash_and_switch(self) -> None:
        router = IntentRouter()
        text = "stash changes and switch branch feature/foo"
        results = router.route_many(text)
        self.assertEqual([r.intent for r in results], ["stash_changes", "switch_branch"])
        self.assertEqual(results[1].entities.get("branch"), "feature/foo")

    def test_route_many_single_clause(self) -> None:
        router = IntentRouter()
        results = router.route_many("create branch feature/foo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].intent, "create_branch")

    def test_route_many_combinations_bulk(self) -> None:
        cases = [
            {
                "text": "commit changes with message 'fix login' and push commit",
                "expected_intents": ["commit_changes", "push_commit_to_origin"],
                "expected_entities": [{"message": "fix login"}, {}],
                "use_llm": True,
            },
            {
                "text": "create branch feature/foo and switch branch feature/foo",
                "expected_intents": ["create_branch", "switch_branch"],
                "expected_entities": [{"branch": "feature/foo"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "create branch feature/foo then push branch feature/foo",
                "expected_intents": ["create_branch", "push_branch"],
                "expected_entities": [{"branch": "feature/foo"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "switch branch develop and pull origin develop",
                "expected_intents": ["switch_branch", "pull_origin"],
                "expected_entities": [{"branch": "develop"}, {"branch": "develop"}],
                "use_llm": False,
            },
            {
                "text": "pull origin main and rebase onto main",
                "expected_intents": ["pull_origin", "rebase_branch"],
                "expected_entities": [{"branch": "main"}, {"branch": "main"}],
                "use_llm": True,
            },
            {
                "text": "stash changes with message 'wip' and switch branch feature/foo",
                "expected_intents": ["stash_changes", "switch_branch"],
                "expected_entities": [{"message": "wip"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "undo last commit and commit changes with message 'redo'",
                "expected_intents": ["undo_commit_soft", "commit_changes"],
                "expected_entities": [{}, {"message": "redo"}],
                "use_llm": False,
            },
            {
                "text": "soft reset to HEAD~2 and commit changes with message 'fix'",
                "expected_intents": ["reset_soft", "commit_changes"],
                "expected_entities": [{"target": "HEAD~2"}, {"message": "fix"}],
                "use_llm": False,
            },
            {
                "text": "hard reset to origin/main and pull origin main",
                "expected_intents": ["reset_hard", "pull_origin"],
                "expected_entities": [{"target": "origin/main"}, {"branch": "main"}],
                "use_llm": True,
            },
            {
                "text": "commit changes; push commit",
                "expected_intents": ["commit_changes", "push_commit_to_origin"],
                "expected_entities": [{}, {}],
                "use_llm": False,
            },
            {
                "text": "create branch feature/foo; then switch branch feature/foo",
                "expected_intents": ["create_branch", "switch_branch"],
                "expected_entities": [{"branch": "feature/foo"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "push branch feature/foo and pull origin feature/foo",
                "expected_intents": ["push_branch", "pull_origin"],
                "expected_entities": [{"branch": "feature/foo"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "commit changes with message 'prep' and create branch feature/foo",
                "expected_intents": ["commit_changes", "create_branch"],
                "expected_entities": [{"message": "prep"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "switch branch develop then push branch develop",
                "expected_intents": ["switch_branch", "push_branch"],
                "expected_entities": [{"branch": "develop"}, {"branch": "develop"}],
                "use_llm": False,
            },
            {
                "text": "rebase onto main and push branch feature/foo",
                "expected_intents": ["rebase_branch", "push_branch"],
                "expected_entities": [{"branch": "main"}, {"branch": "feature/foo"}],
                "use_llm": False,
            },
            {
                "text": "stash changes and pull origin main",
                "expected_intents": ["stash_changes", "pull_origin"],
                "expected_entities": [{}, {"branch": "main"}],
                "use_llm": False,
            },
            {
                "text": "commit changes with message 'done' and stash changes with message 'backup'",
                "expected_intents": ["commit_changes", "stash_changes"],
                "expected_entities": [{"message": "done"}, {"message": "backup"}],
                "use_llm": True,
            },
            {
                "text": "pull origin develop then push commit",
                "expected_intents": ["pull_origin", "push_commit_to_origin"],
                "expected_entities": [{"branch": "develop"}, {}],
                "use_llm": False,
            },
            {
                "text": "reset --hard HEAD~1 and reset --soft HEAD~2",
                "expected_intents": ["reset_hard", "reset_soft"],
                "expected_entities": [{"target": "HEAD~1"}, {"target": "HEAD~2"}],
                "use_llm": False,
            },
            {
                "text": "save changes and push commit",
                "expected_intents": ["commit_changes", "push_commit_to_origin"],
                "expected_entities": [{}, {}],
                "use_llm": False,
            },
        ]

        for case in cases:
            text = case["text"]
            expected_intents = case["expected_intents"]
            expected_entities = case["expected_entities"]
            use_llm = case["use_llm"]

            with self.subTest(text=text):
                if use_llm:
                    stub = ConfigurableLLMDetector(expected_intents)
                    router = IntentRouter(llm_detector=stub)
                    router.rule_detector.detect = lambda _: None
                    router.semantic_detector.score = lambda _: None
                else:
                    stub = None
                    router = IntentRouter()

                results = router.route_many(text)
                self.assertEqual([r.intent for r in results], expected_intents)
                self.assertEqual(len(results), len(expected_entities))
                for result, expected in zip(results, expected_entities):
                    for key, value in expected.items():
                        self.assertEqual(result.entities.get(key), value)
                if use_llm:
                    self.assertEqual(stub.calls, 1)
                    self.assertTrue(all(r.source == "llm" for r in results))
                else:
                    self.assertTrue(all(r.source in {"rule", "semantic"} for r in results))

    def test_route_many_llm_fallback_uses_clause_index(self) -> None:
        stub = StubLLMDetector()
        router = IntentRouter(llm_detector=stub)
        router.rule_detector.detect = lambda _: None
        router.semantic_detector.score = lambda _: None

        text = "create branch feature/foo and push branch feature/foo"
        results = router.route_many(text)

        self.assertEqual(stub.calls, 1)
        self.assertEqual([r.intent for r in results], ["create_branch", "push_branch"])
        self.assertEqual([r.source for r in results], ["llm", "llm"])
        self.assertEqual(results[0].entities.get("branch"), "feature/foo")
        self.assertEqual(results[1].entities.get("branch"), "feature/foo")

    def test_route_many_llm_disabled(self) -> None:
        original = config.ENABLE_LLM_FALLBACK
        config.ENABLE_LLM_FALLBACK = False
        try:
            router = IntentRouter()
            router.rule_detector.detect = lambda _: None
            router.semantic_detector.score = lambda _: None
            results = router.route_many("commit changes and push commit")
            self.assertEqual([r.intent for r in results], ["unknown", "unknown"])
            self.assertTrue(all("LLM fallback: disabled." in r.reason for r in results))
        finally:
            config.ENABLE_LLM_FALLBACK = original


if __name__ == "__main__":
    unittest.main()
