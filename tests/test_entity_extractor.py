import unittest

from git_nl.definitions.entity_extractor import extract_entities


class EntityExtractorTests(unittest.TestCase):
    def test_commit_message_from_flag(self) -> None:
        text = 'commit -m "fix login bug"'
        entities = extract_entities(text)
        self.assertEqual(entities.get("message"), "fix login bug")

    def test_branch_from_create_phrase(self) -> None:
        text = "please create branch feature/auth-rework"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "feature/auth-rework")

    def test_rebase_targets_branch(self) -> None:
        text = "rebase onto main"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "main")
        self.assertNotIn("target", entities)

    def test_reset_hard_target(self) -> None:
        text = "reset --hard HEAD~2"
        entities = extract_entities(text)
        self.assertEqual(entities.get("target"), "HEAD~2")

    def test_pull_origin_branch(self) -> None:
        text = "pull origin develop"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "develop")

    def test_commit_message_from_natural_phrase(self) -> None:
        text = "please commit everything with the message \"fix the login flow\""
        entities = extract_entities(text)
        self.assertEqual(entities.get("message"), "fix the login flow")

    def test_stash_message_from_natural_phrase(self) -> None:
        text = "stash my current work with the message 'wip onboarding'"
        entities = extract_entities(text)
        self.assertEqual(entities.get("message"), "wip onboarding")

    def test_create_branch_natural(self) -> None:
        text = "could you create a branch named hotfix/login-page"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "hotfix/login-page")

    def test_switch_branch_natural(self) -> None:
        text = "can you switch me over to the branch feature/checkout-flow"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "feature/checkout-flow")

    def test_pull_origin_natural(self) -> None:
        text = "please pull the latest changes from origin develop"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "develop")

    def test_rebase_target_natural(self) -> None:
        text = "please rebase this branch onto main so we're up to date"
        entities = extract_entities(text)
        self.assertEqual(entities.get("branch"), "main")
        self.assertNotIn("target", entities)

    def test_reset_hard_target_natural(self) -> None:
        text = "can you hard reset everything back to origin/main"
        entities = extract_entities(text)
        self.assertEqual(entities.get("target"), "origin/main")

    def test_reset_soft_target_natural(self) -> None:
        text = "undo the last commit softly to HEAD~1"
        entities = extract_entities(text)
        self.assertEqual(entities.get("target"), "HEAD~1")


if __name__ == "__main__":
    unittest.main()
