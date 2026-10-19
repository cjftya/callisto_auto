import json
import subprocess
import unittest
from unittest.mock import patch

from tools.probe_cli import classify, probe


class ProbeTests(unittest.TestCase):
    def test_requires_completed_turn_and_exact_answer(self):
        message = json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "CALLISTO_OK"}})
        self.assertEqual(classify(0, message, ""), "invalid_output")
        completed = message + '\n' + json.dumps({"type": "turn.completed"})
        self.assertEqual(classify(0, completed, ""), "passed")
        self.assertEqual(classify(1, completed, ""), "cli_failed")

    def test_auth_failure_overrides_output(self):
        self.assertEqual(classify(1, "", "401 Unauthorized"), "authentication_failed")

    def test_malformed_output_fails_closed(self):
        for output in ("CALLISTO_OK", "[]", "null"):
            self.assertEqual(classify(0, output, ""), "invalid_output")

    @patch("tools.probe_cli.shutil.which", return_value=None)
    def test_missing_executable(self, _):
        self.assertEqual(probe()["text"], "not_installed")

    @patch("tools.probe_cli.shutil.which", return_value="/fake/codex")
    @patch("tools.probe_cli.subprocess.run")
    def test_timeout_and_no_stdin_hang(self, run, _):
        run.side_effect = subprocess.TimeoutExpired("codex", 1)
        report = probe(timeout=1)
        self.assertEqual(report["text"], "timeout")
        self.assertFalse(report["p0_passed"])
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    @patch("tools.probe_cli.shutil.which", return_value="/fake/codex")
    @patch("tools.probe_cli.subprocess.run")
    def test_timeout_preserves_sanitized_auth_diagnosis(self, run, _):
        run.side_effect = subprocess.TimeoutExpired("codex", 1, stderr=b"401 Unauthorized secret")
        report = probe(timeout=1)
        self.assertEqual(report["text"], "authentication_failed")
        self.assertNotIn("secret", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
