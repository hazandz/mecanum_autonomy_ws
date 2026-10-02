#!/usr/bin/env python3
"""Offline tests for generic typed-Scene approval guard v1."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import typed_scene_final_run_guard as live_guard

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
MODULE_REL = 'artifacts/simulation/contact_producer_evidence/tools/typed_scene_final_run_guard.py'
STATIC_REL = (
    live_guard.SUPERVISOR_PATH, live_guard.SOURCE_LAUNCH_PATH,
    live_guard.INSTALLED_LAUNCH_PATH, live_guard.SOURCE_NATIVE_MODEL_PATH,
    live_guard.INSTALLED_NATIVE_MODEL_PATH, live_guard.HELPER_PATH, live_guard.WORLD_PATH,
)
HISTORICAL_GUARD = WORKSPACE_ROOT / 'artifacts/simulation/contact_producer_evidence/approval_guards/S3.3.54_TYPED_SCENE_OBSERVER_FINAL_EXECUTION_RUN.json'


def load_temp_guard(root: Path):
    target = root / MODULE_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(live_guard.__file__).read_bytes())
    spec = importlib.util.spec_from_file_location('temporary_generic_guard', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GenericGuardTests(unittest.TestCase):
    def build_workspace(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative in STATIC_REL:
            source = WORKSPACE_ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        (root / 'docs').mkdir(parents=True, exist_ok=True)
        (root / 'docs/packet-a.md').write_text('packet A\n', encoding='utf-8')
        (root / 'docs/packet-b.md').write_text('packet B\n', encoding='utf-8')
        return temporary, root

    @staticmethod
    def spec(guard, suffix: str):
        return guard.TypedSceneApprovalSpec(
            f'TEST_TYPED_SCENE_APPROVAL_{suffix}', guard.SUPPORTED_SCHEMA,
            f'docs/packet-{suffix.lower()}.md',
            f'artifacts/simulation/contact_producer_evidence/approval_guards/TEST_TYPED_SCENE_APPROVAL_{suffix}.json',
        )

    def authorize_fixture(self, guard, root, spec):
        self.assertEqual(guard.initialize(spec, root, '2026-09-28T00:00:00Z'), (True, 'ready'))
        _, path = guard.validate_spec(spec, root, True, True)
        ok, record, _ = guard.load(path); self.assertTrue(ok)
        record['state'] = guard.AUTHORIZED
        self.assertEqual(guard.atomic_replace(path, record), (True, 'ready'))
        return path

    def test_two_independent_specs_share_generic_tooling(self):
        temporary, root = self.build_workspace()
        with temporary:
            guard = load_temp_guard(root)
            for suffix in ('A', 'B'):
                spec = self.spec(guard, suffix)
                self.assertEqual(guard.initialize(spec, root, '2026-09-28T00:00:00Z'), (True, 'ready'))
                context = guard.build_trusted_context(root, spec)
                _, path = guard.validate_spec(spec, root, True, True)
                ok, record, _ = guard.load(path)
                self.assertTrue(ok); self.assertEqual(guard.validate(record, context, spec, False), (True, 'ready'))

    def test_spec_path_traversal_absolute_symlink_missing_and_record_mismatch_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            guard = load_temp_guard(root)
            valid = self.spec(guard, 'A')
            invalids = (
                guard.TypedSceneApprovalSpec(valid.approval_id, guard.SUPPORTED_SCHEMA, '../packet.md', valid.guard_path),
                guard.TypedSceneApprovalSpec(valid.approval_id, guard.SUPPORTED_SCHEMA, '/tmp/packet.md', valid.guard_path),
                guard.TypedSceneApprovalSpec(valid.approval_id, guard.SUPPORTED_SCHEMA, valid.packet_path, '../guard.json'),
                guard.TypedSceneApprovalSpec(valid.approval_id, 'wrong', valid.packet_path, valid.guard_path),
            )
            for spec in invalids:
                with self.assertRaises(guard.TrustedContextError): guard.build_trusted_context(root, spec)
            linked = root / 'docs/linked.md'; linked.symlink_to(root / 'docs/packet-a.md')
            with self.assertRaises(guard.TrustedContextError):
                guard.build_trusted_context(root, guard.TypedSceneApprovalSpec(valid.approval_id, guard.SUPPORTED_SCHEMA, 'docs/linked.md', valid.guard_path))
            self.authorize_fixture(guard, root, valid)
            context = guard.build_trusted_context(root, valid)
            _, path = guard.validate_spec(valid, root, True, True)
            ok, record, _ = guard.load(path); self.assertTrue(ok)
            record['literals']['world'] = 'drift'
            self.assertFalse(guard.validate(record, context, valid, True)[0])

    def test_lease_capacity_one_spec_binding_and_context_drift(self):
        temporary, root = self.build_workspace()
        with temporary:
            guard = load_temp_guard(root); spec = self.spec(guard, 'A')
            self.authorize_fixture(guard, root, spec)
            ok, _, lease = guard.acquire_trusted(spec, root)
            self.assertTrue(ok); self.assertIsNotNone(lease)
            ok, _, second = guard.acquire_trusted(spec, root)
            self.assertFalse(ok); self.assertIsNone(second)
            wrong = self.spec(guard, 'B')
            self.assertFalse(guard.consume_trusted(wrong, lease, root, 'run-fixture', 'INVALID', 'now')[0])
            self.assertEqual(guard.consume_trusted(spec, lease, root, 'run-fixture', 'INVALID', 'now'), (True, 'ready'))
            self.assertFalse(guard.acquire_trusted(spec, root)[0])

    def test_packet_source_hash_drift_and_atomic_failure_reject(self):
        temporary, root = self.build_workspace()
        with temporary:
            guard = load_temp_guard(root); spec = self.spec(guard, 'A')
            self.authorize_fixture(guard, root, spec)
            baseline = guard.build_trusted_context(root, spec)
            (root / spec.packet_path).write_text('changed\n', encoding='utf-8')
            self.assertFalse(guard.validate(json.loads((root / spec.guard_path).read_text()), guard.build_trusted_context(root, spec), spec, True)[0])
            # Restore packet, then drift a separately locked source hash.
            (root / spec.packet_path).write_text('packet A\n', encoding='utf-8')
            supervisor_path = root / guard.SUPERVISOR_PATH
            supervisor_path.write_bytes(supervisor_path.read_bytes() + b'\n# fixture source drift\n')
            self.assertFalse(guard.validate(json.loads((root / spec.guard_path).read_text()), guard.build_trusted_context(root, spec), spec, True)[0])
            target = root / spec.guard_path
            self.assertFalse(guard.atomic_replace(target, {'bad': True}, replace=lambda *_: (_ for _ in ()).throw(OSError('fixture')))[0])
            self.assertIn('supervisor_sha256', baseline)

    def test_historical_guard_is_read_only_and_production_has_no_historical_identity(self):
        before = hashlib.sha256(HISTORICAL_GUARD.read_bytes()).hexdigest()
        source = Path(live_guard.__file__).read_text(encoding='utf-8')
        self.assertNotIn('S3.3.54', source)
        self.assertEqual(before, hashlib.sha256(HISTORICAL_GUARD.read_bytes()).hexdigest())

    def test_native_assets_and_argv_are_bound_without_legacy_route_literals(self):
        temporary, root = self.build_workspace()
        with temporary:
            guard = load_temp_guard(root)
            spec = self.spec(guard, 'A')
            context = guard.build_trusted_context(root, spec)
            self.assertEqual(context['literals']['world'], 'world_demo')
            self.assertEqual(context['literals']['create_argv'], [
                '-world', 'world_demo', '-file',
                str(root / guard.INSTALLED_NATIVE_MODEL_PATH),
                '-name', 'ROBOT_URDF_final', '-allow_renaming', 'false',
                '-x', '0', '-y', '0', '-z', '0.1', '-Y', '0',
            ])
            self.assertIn('source_native_model_sha256', context)
            self.assertIn('installed_native_model_sha256', context)
        source = Path(live_guard.__file__).read_text(encoding='utf-8')
        for legacy in ('typed_scene_observer.launch.py', "'-topic'", '/robot_description'):
            self.assertNotIn(legacy, source)


if __name__ == '__main__':
    unittest.main()
