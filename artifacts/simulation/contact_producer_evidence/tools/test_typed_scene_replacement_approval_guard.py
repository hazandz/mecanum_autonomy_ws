#!/usr/bin/env python3
"""Offline tests for the S3.3.47 trusted-context capacity-one guard."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import run_typed_scene_observer as supervisor
import typed_scene_replacement_approval_guard as guard

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
OLD_GUARD = WORKSPACE_ROOT / "artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.31_TYPED_SCENE_OBSERVER_RUN.json"
S345_GUARD = WORKSPACE_ROOT / "artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.45_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN.json"
S346_GUARD = WORKSPACE_ROOT / "artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.46_TYPED_SCENE_OBSERVER_REPLACEMENT_RUNTIME_RUN.json"


class TrustedGuardTests(unittest.TestCase):
    def build_workspace(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative, content in (
            (guard.PACKET_PATH, b"packet"),
            (guard.SUPERVISOR_PATH, b"supervisor"),
            (guard.LAUNCH_PATH, b"launch"),
            (guard.HELPER_PATH, b"helper"),
            (guard.GUARD_HELPER_PATH, b"guard-helper"),
            (guard.WORLD_PATH, b"world"),
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return temporary, root

    def initialize(self, root):
        path = root / "approval.json"
        self.assertTrue(guard.initialize(path, root, "2026-09-27T00:00:00Z")[0])
        return path

    def test_canonical_context_matches_record(self):
        temporary, root = self.build_workspace()
        with temporary:
            path = self.initialize(root)
            context = guard.build_trusted_context(root)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(guard.validate(record, context, True)[0])
            self.assertEqual(guard.context_digest(context), guard.context_digest(guard.build_trusted_context(root)))

    def test_each_hash_locked_file_change_rejects(self):
        for relative in (guard.PACKET_PATH, guard.SUPERVISOR_PATH, guard.LAUNCH_PATH, guard.HELPER_PATH, guard.GUARD_HELPER_PATH, guard.WORLD_PATH):
            with self.subTest(relative=relative):
                temporary, root = self.build_workspace()
                with temporary:
                    path = self.initialize(root)
                    (root / relative).write_bytes(b"changed")
                    self.assertFalse(guard.acquire_trusted(path, root)[0])

    def test_missing_symlink_and_path_traversal_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            (root / guard.WORLD_PATH).unlink()
            with self.assertRaises(guard.TrustedContextError):
                guard.build_trusted_context(root)
        temporary, root = self.build_workspace()
        with temporary:
            target = root / guard.HELPER_PATH
            target.unlink(); target.symlink_to(root / guard.WORLD_PATH)
            with self.assertRaises(guard.TrustedContextError):
                guard.build_trusted_context(root)
            with self.assertRaises(guard.TrustedContextError):
                guard.resolve_workspace_regular(root, "../outside")
        temporary, root = self.build_workspace()
        with temporary:
            simulation = root / "artifacts/simulation"
            renamed = root / "artifacts/simulation_real"
            simulation.rename(renamed)
            simulation.symlink_to(renamed, target_is_directory=True)
            with self.assertRaises(guard.TrustedContextError):
                guard.build_trusted_context(root)

    def test_packet_and_literal_tamper_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            path = self.initialize(root)
            record = json.loads(path.read_text(encoding="utf-8"))
            record["packet_sha256"] = "0" * 64
            path.write_bytes(guard.canonical(record))
            self.assertFalse(guard.acquire_trusted(path, root)[0])
            path = root / "literal-tamper.json"
            self.assertTrue(guard.initialize(path, root, "2026-09-27T00:00:00Z")[0])
            record = json.loads(path.read_text(encoding="utf-8"))
            record["literals"]["world"] = "other"
            path.write_bytes(guard.canonical(record))
            self.assertFalse(guard.acquire_trusted(path, root)[0])
            path = root / "executable-tamper.json"
            self.assertTrue(guard.initialize(path, root, "2026-09-27T00:00:00Z")[0])
            record = json.loads(path.read_text(encoding="utf-8"))
            record["create_executable_sha256"] = "0" * 64
            path.write_bytes(guard.canonical(record))
            self.assertFalse(guard.acquire_trusted(path, root)[0])

    def test_lease_owns_correct_context_token_and_metadata(self):
        temporary, root = self.build_workspace()
        with temporary:
            path = self.initialize(root)
            ok, _, lease = guard.acquire_trusted(path, root); self.assertTrue(ok)
            bad_token = replace(lease, nonce="wrong")
            self.assertFalse(guard.consume_trusted(path, bad_token, root, "run", "INVALID", "2026-09-27T00:00:01Z")[0])
            bad_context = replace(lease, context_digest="0" * 64)
            self.assertFalse(guard.consume_trusted(path, bad_context, root, "run", "INVALID", "2026-09-27T00:00:01Z")[0])
            metadata = lease.lock_path / guard.LOCK_METADATA
            metadata.write_bytes(guard.canonical({"approval_id": lease.approval_id, "context_digest": lease.context_digest, "nonce": "tampered"}))
            self.assertFalse(guard.consume_trusted(path, lease, root, "run", "INVALID", "2026-09-27T00:00:01Z")[0])

    def test_acquire_once_consume_and_consumed_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            path = self.initialize(root)
            ok, _, lease = guard.acquire_trusted(path, root); self.assertTrue(ok)
            self.assertFalse(guard.acquire_trusted(path, root)[0])
            self.assertTrue(guard.consume_trusted(path, lease, root, "run", "INVALID", "2026-09-27T00:00:01Z")[0])
            self.assertFalse(guard.acquire_trusted(path, root)[0])

    def test_leftover_lock_blocks_new_run(self):
        temporary, root = self.build_workspace()
        with temporary:
            path = self.initialize(root)
            lock = path.with_name(path.name + ".lock"); lock.mkdir()
            self.assertFalse(guard.acquire_trusted(path, root)[0])

    def test_malformed_and_atomic_write_failure_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            malformed = root / "bad.json"; malformed.write_text("not-json", encoding="utf-8")
            self.assertFalse(guard.acquire_trusted(malformed, root)[0])
            self.assertFalse(guard.atomic_replace(root / "failed.json", {"x": 1}, replace=lambda _a, _b: (_ for _ in ()).throw(OSError("fixture")))[0])

    def test_historical_and_s345_guards_read_only(self):
        old_before = OLD_GUARD.read_bytes()
        s345_before = S345_GUARD.read_bytes()
        s346_before = S346_GUARD.read_bytes()
        self.assertEqual(OLD_GUARD.read_bytes(), old_before)
        self.assertEqual(S345_GUARD.read_bytes(), s345_before)
        self.assertEqual(S346_GUARD.read_bytes(), s346_before)

    def test_execute_fails_before_trusted_context_acquire_or_popen(self):
        with mock.patch.object(supervisor.subprocess, "Popen") as popen, mock.patch.object(guard, "build_trusted_context") as context:
            with self.assertRaises(SystemExit):
                supervisor.main(["--execute"])
        popen.assert_not_called(); context.assert_not_called()


if __name__ == "__main__":
    unittest.main()
