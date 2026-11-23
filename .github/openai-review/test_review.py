"""Offline tests. No secrets, runners, package installs, or network calls."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import review


def pr():
    return {
        "state": "open",
        "base": {"repo": {"full_name": "example/repo"}, "ref": "main", "sha": "b" * 40},
        "head": {"sha": "a" * 40},
        "changed_files": 1,
    }


def item(**overrides):
    out = {
        "filename": "src/file.cpp",
        "additions": 1,
        "deletions": 1,
        "patch": "@@ -1 +1 @@\n-old\n+new",
    }
    return dict(out, **overrides)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.summary = Path(self.directory.name) / "summary"
        self.env = {
            "GITHUB_REPOSITORY": "example/repo",
            "DEFAULT_BRANCH": "main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "PR_NUMBER": "5",
            "ALLOW_PRIVATE_DIFF": "true",
            "REVIEW_API_KEY": "synthetic-api-key-for-tests",
            "GITHUB_TOKEN": "synthetic-gh-token-for-tests",
            "GITHUB_STEP_SUMMARY": str(self.summary),
        }

    def test_sends_patches_only_and_escapes_summary(self):
        output = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "<img src=x> Fix the boundary."}
                    ],
                }
            ],
        }
        send = Mock(side_effect=[pr(), [item()], pr(), output])
        review.run(self.env, send)
        self.assertEqual(send.call_count, 4)
        endpoint, secret = send.call_args.args
        self.assertEqual(endpoint, "https://api.openai.com/v1/responses")
        self.assertEqual(secret, self.env["REVIEW_API_KEY"])
        body = send.call_args.kwargs["body"]
        self.assertEqual(json.loads(body["input"])[0]["path"], "src/file.cpp")
        self.assertFalse(body["store"])
        self.assertNotIn("tools", body)
        self.assertNotIn(self.env["GITHUB_TOKEN"], json.dumps(body))
        summary = self.summary.read_text()
        self.assertIn("&lt;img src=x&gt;", summary)
        self.assertIn("a" * 40, summary)

    def test_ref_and_number_checks_before_network(self):
        for overrides in (
            {"GITHUB_REF": "refs/heads/not-main"},
            {"PR_NUMBER": "1; bad"},
            {"REVIEW_API_KEY": ""},
        ):
            with self.subTest(overrides=overrides):
                send = Mock()
                with self.assertRaises(review.ReviewError):
                    review.run(dict(self.env, **overrides), send)
                send.assert_not_called()

    def test_blocks_sensitive_binary_incomplete_and_large_patches(self):
        for bad in (
            item(filename=".env"),
            item(previous_filename="tls.key"),
            item(patch=None),
            item(additions=2),
            item(patch="@@ -1 +1 @@\n-old\n+password = 'syntheticValue1234'"),
            item(patch="@@ -1 +1 @@\n-old\n+" + "z" * review.MAX_PATCH_BYTES),
        ):
            with self.subTest(path=bad["filename"]):
                send = Mock(side_effect=[pr(), [bad]])
                with self.assertRaises(review.ReviewError):
                    review.run(self.env, send)
                self.assertEqual(send.call_count, 2)

    def test_updated_pr_never_reaches_openai(self):
        moved = pr()
        moved["head"]["sha"] = "c" * 40
        send = Mock(side_effect=[pr(), [item()], moved])
        with self.assertRaises(review.ReviewError):
            review.run(self.env, send)
        self.assertEqual(send.call_count, 3)
        self.assertFalse(self.summary.exists())

    def test_private_defaults_to_no_transfer(self):
        if review.PRIVATE:
            send = Mock()
            with self.assertRaises(review.ReviewError):
                review.run(dict(self.env, ALLOW_PRIVATE_DIFF="false"), send)
            send.assert_not_called()

    def test_incomplete_or_empty_review_is_not_success(self):
        for output in ({"status": "incomplete"}, {"status": "completed", "output": []}):
            with self.assertRaises(review.ReviewError):
                review.response_text(output)
