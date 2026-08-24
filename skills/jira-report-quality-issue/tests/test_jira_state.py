from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_state import (
    StateError,
    cleanup_state,
    operation_lock,
    read_state,
    write_state,
)


class StateTests(unittest.TestCase):
    def test_state_is_atomic_private_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / ".state"
            path = write_state(
                state_dir,
                "batch-deadbeef",
                {"status": "verified", "operationId": "batch-deadbeef"},
            )
            self.assertEqual(
                read_state(state_dir, "batch-deadbeef")["status"], "verified"
            )
            self.assertEqual(os.stat(state_dir).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_lock_rejects_concurrent_same_operation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / ".state"
            with (
                operation_lock(state_dir, "batch-deadbeef"),
                self.assertRaisesRegex(StateError, "OperationAlreadyRunning"),
                operation_lock(state_dir, "batch-deadbeef"),
            ):
                self.fail("second lock should not be acquired")

    def test_cleanup_refuses_partial_and_removes_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / ".state"
            write_state(state_dir, "batch-deadbeef", {"status": "partial"})
            with self.assertRaisesRegex(StateError, "verified"):
                cleanup_state(state_dir, "batch-deadbeef")
            write_state(state_dir, "batch-deadbeef", {"status": "verified"})
            cleanup_state(state_dir, "batch-deadbeef")
            self.assertIsNone(read_state(state_dir, "batch-deadbeef"))


if __name__ == "__main__":
    unittest.main()
