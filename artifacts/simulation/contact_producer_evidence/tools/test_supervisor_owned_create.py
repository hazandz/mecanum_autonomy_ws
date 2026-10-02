#!/usr/bin/env python3
"""Offline tests for the injected supervisor-owned create phase."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_typed_scene_observer as supervisor
import typed_scene_final_run_guard as approval_guard

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
TEST_SPEC = approval_guard.TypedSceneApprovalSpec(
    'TEST_TYPED_SCENE_SUPERVISOR_APPROVAL', approval_guard.SUPPORTED_SCHEMA,
    'docs/test-supervisor-packet.md',
    'artifacts/simulation/contact_producer_evidence/approval_guards/TEST_TYPED_SCENE_SUPERVISOR_APPROVAL.json',
)

SHA_A = 'a' * 64
SHA_B = 'b' * 64


class FakeProcess:
    def __init__(self, outcomes, pid=701, sigint_error=None):
        self.outcomes = list(outcomes if isinstance(outcomes, tuple) else (outcomes,))
        self.pid = pid
        self.timeouts = []
        self.sigint_calls = 0
        self.sigint_error = sigint_error

    def wait(self, timeout_ms):
        self.timeouts.append(timeout_ms)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def send_sigint_group(self):
        self.sigint_calls += 1
        if self.sigint_error is not None:
            raise self.sigint_error


class FakeSpawner:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []
        self.processes = []

    def __call__(self, executable, argv):
        self.calls.append((executable, argv))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        process = FakeProcess(self.outcome)
        self.processes.append(process)
        return process


class FakePopenChild:
    def __init__(self, outcomes=(0,), pid=811):
        self.pid = pid
        self.outcomes = list(outcomes)
        self.wait_timeouts = []

    def wait(self, timeout):
        self.wait_timeouts.append(timeout)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakePopenFactory:
    def __init__(self, child):
        self.child = child
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.child


class RuntimeCreateAdapterTests(unittest.TestCase):
    def test_adapter_uses_exact_popen_command_and_new_session(self):
        child = FakePopenChild()
        factory = FakePopenFactory(child)
        signals = []
        adapter = supervisor.RuntimeCreateAdapter(
            popen_factory=factory,
            get_process_group=lambda pid: pid,
            kill_process_group=lambda pgid, sig: signals.append((pgid, sig)),
        )
        process = adapter.spawn(str(supervisor.CREATE_EXECUTABLE), supervisor.CREATE_ARGUMENTS)
        self.assertEqual(len(factory.calls), 1)
        args, kwargs = factory.calls[0]
        self.assertEqual(args, ([str(supervisor.CREATE_EXECUTABLE), *supervisor.CREATE_ARGUMENTS],))
        self.assertFalse(kwargs['shell'])
        self.assertTrue(kwargs['start_new_session'])
        self.assertTrue(kwargs['close_fds'])
        self.assertIs(kwargs['stdout'], subprocess.DEVNULL)
        self.assertIs(kwargs['stderr'], subprocess.DEVNULL)
        process.send_sigint_group()
        self.assertEqual(signals, [(child.pid, supervisor.signal.SIGINT)])

    def test_adapter_rejects_unallowlisted_command_without_popen(self):
        factory = FakePopenFactory(FakePopenChild())
        adapter = supervisor.RuntimeCreateAdapter(
            popen_factory=factory, get_process_group=lambda pid: pid,
            kill_process_group=lambda pgid, sig: None,
        )
        with self.assertRaises(ValueError):
            adapter.spawn('/tmp/other', supervisor.CREATE_ARGUMENTS)
        self.assertEqual(factory.calls, [])

    def test_adapter_timeout_flows_through_sigint_grace_only(self):
        child = FakePopenChild(
            outcomes=(subprocess.TimeoutExpired('create', 90), 0),
            pid=813,
        )
        factory = FakePopenFactory(child)
        signals = []
        adapter = supervisor.RuntimeCreateAdapter(
            popen_factory=factory,
            get_process_group=lambda pid: pid,
            kill_process_group=lambda pgid, sig: signals.append((pgid, sig)),
        )
        plan = supervisor.resolve_create_plan(
            digest_path=lambda _: SHA_A, is_regular_file=lambda _: True,
        )
        result = supervisor.create_phase(
            plan, adapter.spawn, iter((1, 2, 3, 4)).__next__,
            digest_path=lambda _: SHA_A, is_regular_file=lambda _: True,
        )
        self.assertEqual(result.status, 'SCENE_CREATE_OUTCOME_UNCONFIRMED')
        self.assertFalse(result.helper_permitted)
        self.assertTrue(result.shutdown_complete)
        self.assertEqual(child.wait_timeouts, [90.0, 5.0])
        self.assertEqual(signals, [(813, supervisor.signal.SIGINT)])
        self.assertEqual(len(factory.calls), 1)

    def test_execution_gate_requires_all_explicit_spec_fields_by_source_contract(self):
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        for required in ('--workspace-root', '--approval-id', '--packet-path', '--guard-path'):
            self.assertIn(required, source)
        self.assertIn('EXECUTION_GATE_ARGUMENTS_REQUIRED', source)
        self.assertNotIn('APPROVAL_ID', source)


class CreatePhaseTests(unittest.TestCase):
    def setUp(self):
        self.plan = supervisor.resolve_create_plan(
            digest_path=lambda _: SHA_A,
            is_regular_file=lambda _: True,
        )

    def run_phase(self, outcome, delay=lambda milliseconds: None, digest_path=lambda _: SHA_A,
                  is_regular_file=lambda _: True, plan=None):
        spawner = FakeSpawner(outcome)
        clock = iter((100, 200, 300, 400)).__next__
        result = supervisor.create_phase(
            self.plan if plan is None else plan,
            spawner,
            clock,
            delay,
            digest_path,
            is_regular_file,
        )
        return spawner, result

    def assert_pre_spawn_rejection(self, result, spawner):
        self.assertEqual(result.status, 'SCENE_CREATE_OUTCOME_UNCONFIRMED')
        self.assertEqual(result.bootstrap_status, 'SCENE_BOOTSTRAP_UNCONFIRMED')
        self.assertFalse(result.helper_permitted)
        self.assertEqual(result.create_invocations, 0)
        self.assertEqual(spawner.calls, [])

    def test_allowlisted_argv_and_single_create(self):
        spawner, result = self.run_phase(0)
        self.assertEqual(spawner.calls, [(str(supervisor.CREATE_EXECUTABLE), supervisor.CREATE_ARGUMENTS)])
        self.assertEqual(result.create_invocations, 1)
        self.assertTrue(result.helper_permitted)
        self.assertEqual(result.status, 'SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST')

    def test_exit_zero_runs_exact_delay_gate(self):
        delays = []
        spawner, result = self.run_phase(0, delays.append)
        self.assertEqual(delays, [2000])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(len(spawner.calls), 1)

    def test_nonzero_blocks_helper_without_retry(self):
        spawner, result = self.run_phase(7)
        self.assertFalse(result.helper_permitted)
        self.assertEqual(result.status, 'SCENE_CREATE_OUTCOME_UNCONFIRMED')
        self.assertEqual(result.create_invocations, 1)
        self.assertEqual(len(spawner.calls), 1)

    def test_timeout_interrupted_and_missing_exit_fail_closed(self):
        for outcome in (TimeoutError(), InterruptedError(), None):
            with self.subTest(outcome=type(outcome).__name__):
                spawner, result = self.run_phase(outcome)
                self.assertFalse(result.helper_permitted)
                self.assertEqual(result.bootstrap_status, 'SCENE_BOOTSTRAP_UNCONFIRMED')
                self.assertEqual(len(spawner.calls), 1)

    def test_spawn_error_blocks_helper(self):
        spawner, result = self.run_phase(OSError('no child'))
        self.assertFalse(result.helper_permitted)
        self.assertEqual(result.create_invocations, 1)

    def test_hash_changes_after_plan_resolution_fail_before_invocation(self):
        spawner, result = self.run_phase(0, digest_path=lambda _: SHA_B)
        self.assert_pre_spawn_rejection(result, spawner)
        self.assertIn('mismatch', result.reason)

    def test_direct_plan_sha_mismatch_fails_before_invocation(self):
        bad = supervisor.CreatePlan(
            str(supervisor.CREATE_EXECUTABLE), SHA_B, supervisor.CREATE_ARGUMENTS,
            90000, 2000, 5000, supervisor.OWNERSHIP_MODE,
        )
        spawner, result = self.run_phase(0, plan=bad)
        self.assert_pre_spawn_rejection(result, spawner)

    def test_invalid_hash_format_and_path_or_file_fail_before_invocation(self):
        invalid_hash = supervisor.CreatePlan(
            str(supervisor.CREATE_EXECUTABLE), 'not-a-sha', supervisor.CREATE_ARGUMENTS,
            90000, 2000, 5000, supervisor.OWNERSHIP_MODE,
        )
        spawner, result = self.run_phase(0, plan=invalid_hash)
        self.assert_pre_spawn_rejection(result, spawner)
        invalid_path = supervisor.CreatePlan(
            '/tmp/not-allowed', SHA_A, supervisor.CREATE_ARGUMENTS,
            90000, 2000, 5000, supervisor.OWNERSHIP_MODE,
        )
        spawner, result = self.run_phase(0, plan=invalid_path)
        self.assert_pre_spawn_rejection(result, spawner)
        spawner, result = self.run_phase(0, is_regular_file=lambda _: False)
        self.assert_pre_spawn_rejection(result, spawner)


    def test_timeout_child_exits_after_sigint_grace(self):
        spawner, result = self.run_phase((TimeoutError(), 0))
        self.assertEqual(result.status, 'SCENE_CREATE_OUTCOME_UNCONFIRMED')
        self.assertEqual(result.bootstrap_status, 'SCENE_BOOTSTRAP_UNCONFIRMED')
        self.assertFalse(result.helper_permitted)
        self.assertTrue(result.shutdown_signal_sent)
        self.assertTrue(result.shutdown_complete)
        self.assertEqual(result.shutdown_grace_ms, 5000)
        self.assertEqual(len(spawner.calls), 1)
        self.assertEqual(spawner.processes[0].timeouts, [90000, 5000])
        self.assertEqual(spawner.processes[0].sigint_calls, 1)

    def test_timeout_child_alive_after_sigint_grace_is_shutdown_incomplete(self):
        spawner, result = self.run_phase((TimeoutError(), TimeoutError()))
        self.assertEqual(result.status, 'SHUTDOWN_INCOMPLETE')
        self.assertEqual(result.bootstrap_status, 'SCENE_BOOTSTRAP_UNCONFIRMED')
        self.assertFalse(result.helper_permitted)
        self.assertTrue(result.shutdown_signal_sent)
        self.assertFalse(result.shutdown_complete)
        self.assertEqual(result.shutdown_grace_ms, 5000)
        self.assertEqual(len(spawner.calls), 1)
        self.assertEqual(spawner.processes[0].timeouts, [90000, 5000])
        self.assertEqual(spawner.processes[0].sigint_calls, 1)
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        self.assertNotIn('RequestRaw(', source)
        self.assertNotIn('.kill(', source)
        self.assertNotIn('SIGTERM', source)
        self.assertNotIn('SIGKILL', source)

    def test_no_legacy_guard_or_log_parsing_and_not_observed_taxonomy(self):
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        for prohibited in ('S3.3.31', 'typed_scene_approval_guard', 'communicate(', 'preflight_authority'):
            self.assertNotIn(prohibited, source)
        self.assertIn('SCENE_CREATE_OUTCOME_UNCONFIRMED', source)
        readiness = (WORKSPACE_ROOT / 'docs/S3_D3_Spawn_Completion_And_Scene_Readiness_Design_DRAFT.md').read_text(encoding='utf-8')
        self.assertIn('SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY', readiness)
        self.assertNotIn('SCENE_MODEL_ABSENT` | `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY', readiness)


class GuardedExecutionIntegrationTests(unittest.TestCase):
    def ready_phase(self):
        return supervisor.CreatePhaseResult(
            'SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST',
            'SCENE_BOOTSTRAP_READY_FOR_ONE_REQUEST', True, 1,
            str(supervisor.CREATE_EXECUTABLE), SHA_A, supervisor.CREATE_ARGUMENTS,
            701, 10, 20, 0, 'offline ready fixture',
        )

    def dependencies(self, events, launch_error=None, shutdown=True):
        def launch():
            events.append('launch')
            if launch_error is not None:
                raise launch_error

        def spawn(executable, argv):
            events.append(('create', executable, argv))
            return FakeProcess(0)

        def compile_helper(directory):
            events.append(('compile', directory.is_dir()))
            (directory / 'typed_scene_observer').write_bytes(b'temporary-only')

        def helper_once(directory):
            events.append(('helper_once', directory.is_dir()))
            return 'SCENE_SENSOR_PRESENT_IDENTITY_ONLY'

        def persist(directory, status):
            events.append(('persist', directory.is_dir(), status))

        def cleanup():
            events.append('sigint_cleanup')
            return shutdown

        return supervisor.GuardedExecutionDependencies(
            launch, spawn, compile_helper, helper_once, persist, cleanup,
            tempfile.TemporaryDirectory, lambda: '2026-09-27T00:00:00Z',
            lambda: 'run-s3347-fixture',
        )

    def patched_guard(self, events):
        lease = object()
        return (
            mock.patch.object(approval_guard, 'validate_spec', return_value=(None, Path('/tmp/guard.json'))),
            mock.patch.object(approval_guard, 'build_trusted_context', side_effect=lambda root, spec: events.append('context') or {}),
            mock.patch.object(approval_guard, 'acquire_trusted', side_effect=lambda spec, root: events.append('acquire') or (True, 'ready', lease)),
            mock.patch.object(approval_guard, 'consume_trusted', side_effect=lambda spec, got, root, run_id, status, when: events.append(('consume', got is lease, status)) or (True, 'ready')),
        )

    def test_valid_mocked_sequence_runs_once_and_consumes_once(self):
        events = []
        deps = self.dependencies(events)
        plan = object()
        def fake_phase(_plan, spawn, **_kwargs):
            self.assertIs(_plan, plan)
            spawn(str(supervisor.CREATE_EXECUTABLE), supervisor.CREATE_ARGUMENTS)
            return self.ready_phase()
        patches = self.patched_guard(events)
        with patches[0], patches[1], patches[2], patches[3], \
             mock.patch.object(supervisor, 'resolve_create_plan', return_value=plan), \
             mock.patch.object(supervisor, 'create_phase', side_effect=fake_phase), \
             mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            status = supervisor.execute_guarded(WORKSPACE_ROOT, TEST_SPEC, deps)
        self.assertEqual(status, 'SCENE_SENSOR_PRESENT_IDENTITY_ONLY')
        self.assertEqual(events[0:3], ['context', 'acquire', 'launch'])
        self.assertEqual(sum(1 for item in events if isinstance(item, tuple) and item[0] == 'create'), 1)
        self.assertEqual(sum(1 for item in events if isinstance(item, tuple) and item[0] == 'helper_once'), 1)
        self.assertEqual(events[-2], 'sigint_cleanup')
        self.assertEqual(events[-1], ('consume', True, 'SCENE_SENSOR_PRESENT_IDENTITY_ONLY'))
        popen.assert_not_called()

    def test_gate_rejections_make_zero_subprocess_or_guard_calls(self):
        events = []
        deps = self.dependencies(events)
        with mock.patch.object(approval_guard, 'build_trusted_context') as context, \
             mock.patch.object(approval_guard, 'acquire_trusted') as acquire, \
             mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            status = supervisor.execute_guarded(WORKSPACE_ROOT, 'wrong', deps)
        self.assertEqual(status, 'INVALID_GATE_APPROVAL_SPEC')
        context.assert_not_called(); acquire.assert_not_called(); popen.assert_not_called()
        with mock.patch.object(approval_guard, 'validate_spec', return_value=(None, Path('/tmp/guard.json'))), \
             mock.patch.object(approval_guard, 'build_trusted_context', side_effect=approval_guard.TrustedContextError('drift')) as context, \
             mock.patch.object(approval_guard, 'acquire_trusted') as acquire, \
             mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            status = supervisor.execute_guarded(WORKSPACE_ROOT, TEST_SPEC, deps)
        self.assertEqual(status, 'INVALID_GATE_TRUSTED_CONTEXT')
        context.assert_called_once(); acquire.assert_not_called(); popen.assert_not_called()

    def test_failure_and_shutdown_incomplete_consume_exactly_once(self):
        events = []
        deps = self.dependencies(events, launch_error=OSError('fixture launch failure'), shutdown=False)
        patches = self.patched_guard(events)
        with patches[0], patches[1], patches[2], patches[3], mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            status = supervisor.execute_guarded(WORKSPACE_ROOT, TEST_SPEC, deps)
        self.assertEqual(status, 'SHUTDOWN_INCOMPLETE')
        self.assertEqual(sum(1 for item in events if isinstance(item, tuple) and item[0] == 'consume'), 1)
        self.assertEqual(events[-1], ('consume', True, 'SHUTDOWN_INCOMPLETE'))
        self.assertNotIn('create', [item[0] if isinstance(item, tuple) else item for item in events])
        popen.assert_not_called()

    def test_invalid_cli_spec_is_rejected_before_factory_or_guard_activity(self):
        invalid = approval_guard.spec_from_cli(
            TEST_SPEC.approval_id, TEST_SPEC.packet_path, '/tmp/guard.json',
        )
        with mock.patch.object(supervisor, 'build_runtime_dependencies') as factory, \
             mock.patch.object(approval_guard, 'acquire_trusted') as acquire, \
             mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            with self.assertRaises(approval_guard.TrustedContextError):
                approval_guard.validate_spec(invalid, WORKSPACE_ROOT, True, False)
        factory.assert_not_called(); acquire.assert_not_called(); popen.assert_not_called()

    def test_no_retry_or_force_kill_in_guarded_source(self):
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        for forbidden in ('.kill(', 'SIGTERM', 'SIGKILL', 'bash -c', 'RequestRaw(', 'retry'):
            self.assertNotIn(forbidden, source)


class RuntimeDependencyFactoryTests(unittest.TestCase):
    def test_factory_construction_has_zero_subprocess_or_guard_activity(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with mock.patch.object(supervisor.subprocess, 'Popen') as popen, \
                 mock.patch.object(approval_guard, 'acquire_trusted') as acquire:
                dependencies = supervisor.build_runtime_dependencies(root, create_arguments=supervisor.CREATE_ARGUMENTS)
            self.assertIsInstance(dependencies, supervisor.GuardedExecutionDependencies)
            popen.assert_not_called(); acquire.assert_not_called()

    def test_launch_callback_uses_exact_allowlisted_argv_with_fake_popen(self):
        class FakeLaunch:
            pid = 991
            def wait(self, timeout): return 0
        calls = []
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            factory = supervisor.RuntimeDependencyFactory(
                root,
                popen_factory=lambda *args, **kwargs: calls.append((args, kwargs)) or FakeLaunch(),
                process_group=lambda pid, sig: None,
                create_arguments=supervisor.CREATE_ARGUMENTS,
            )
            factory.begin_run('run-typed-scene-fixture')
            with mock.patch.object(supervisor, 'regular_file', return_value=True):
                factory.launch_bootstrap()
            self.assertEqual(len(calls), 1)
            args, kwargs = calls[0]
            self.assertEqual(args[0], [str(supervisor.ROS2_EXECUTABLE), *supervisor.DEDICATED_LAUNCH_ARGUMENTS])
            self.assertFalse(kwargs['shell']); self.assertTrue(kwargs['start_new_session'])
            self.assertTrue(kwargs['close_fds'])
            self.assertTrue(factory.shutdown_sigint_only())

    def test_durable_run_identity_is_shared_with_guard_consumption(self):
        events = []
        identity = 'run-typed-scene-shared-fixture'
        base = GuardedExecutionIntegrationTests().dependencies(events)
        lease = object()
        with mock.patch.object(approval_guard, 'validate_spec', return_value=(None, Path('/tmp/guard.json'))), \
             mock.patch.object(approval_guard, 'build_trusted_context', side_effect=lambda _, __: events.append('context') or {}), \
             mock.patch.object(approval_guard, 'acquire_trusted', return_value=(True, 'ready', lease)), \
             mock.patch.object(approval_guard, 'consume_trusted', side_effect=lambda spec, got, root, run_id, status, when: events.append(('consume', run_id, status)) or (True, 'ready')), \
             mock.patch.object(supervisor, 'resolve_create_plan', return_value=object()), \
             mock.patch.object(supervisor, 'create_phase', return_value=GuardedExecutionIntegrationTests().ready_phase()):
            deps = supervisor.GuardedExecutionDependencies(
                base.launch_bootstrap, base.spawn_create, base.compile_helper, base.helper_once,
                base.persist_artifact, base.shutdown_sigint_only, base.temporary_directory,
                base.now_utc, lambda: identity, base.prepare,
                lambda value: events.append(('begin_run', value)),
            )
            supervisor.execute_guarded(WORKSPACE_ROOT, TEST_SPEC, deps)
        self.assertIn(('begin_run', identity), events)
        self.assertIn(('consume', identity, 'SCENE_SENSOR_PRESENT_IDENTITY_ONLY'), events)

    def test_factory_writes_mandatory_no_response_records_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            factory = supervisor.RuntimeDependencyFactory(root, create_arguments=supervisor.CREATE_ARGUMENTS)
            factory.begin_run('run-typed-scene-evidence-fixture')
            factory.finalize_evidence('SCENE_CREATE_OUTCOME_UNCONFIRMED', None, False, True)
            artifact = root / 'artifacts/simulation/contact_producer_evidence/run-typed-scene-evidence-fixture'
            expected = {'run_manifest.json', 'scene_summary.json', 'request_metadata.json',
                        'create_process.json', 'helper_process.json', 'shutdown_outcome.json'}
            self.assertEqual({item.name for item in artifact.iterdir()}, expected)
            parsed_json = __import__('json')
            summary = parsed_json.loads((artifact / 'scene_summary.json').read_text())
            shutdown = parsed_json.loads((artifact / 'shutdown_outcome.json').read_text())
            self.assertEqual(summary['schema_version'], 's3_d3_typed_scene_summary/v4')
            metadata = parsed_json.loads((artifact / 'request_metadata.json').read_text())
            self.assertEqual(metadata['schema_version'], 's3_d3_typed_scene_metadata/v3')
            self.assertEqual(metadata['outer_status'], 'INVALID_EVIDENCE_PERSISTENCE_FAILURE')
            self.assertEqual(metadata['service'], '/world/world_demo/scene/info')
            self.assertIsNone(summary['raw_response_sha256'])
            self.assertFalse((artifact / 'scene_response.pb').exists())
            self.assertTrue(shutdown['supervisor_sigint_attempted'])
            self.assertIsNone(shutdown['launcher_managed_escalation_observed'])
            self.assertEqual(shutdown['deadline_result'], 'COMPLETE')
            link = root / 'linked-artifact'
            link.symlink_to(artifact, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                supervisor.atomic_write_json_new(link / 'blocked.json', {'x': 1})

    def test_factory_policy_literals_and_deferred_helper_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            factory = supervisor.RuntimeDependencyFactory(root, create_arguments=supervisor.CREATE_ARGUMENTS)
            dependencies = factory.build()
            installed_model = WORKSPACE_ROOT / approval_guard.INSTALLED_NATIVE_MODEL_PATH
            self.assertEqual(supervisor.CREATE_ARGUMENTS, (
                '-world', 'world_demo', '-file', str(installed_model),
                '-name', 'ROBOT_URDF_final', '-allow_renaming', 'false',
                '-x', '0', '-y', '0', '-z', '0.1', '-Y', '0',
            ))
            self.assertEqual(supervisor.DEDICATED_LAUNCH_ARGUMENTS, (
                'launch', 'ROBOT_URDF_final_description', 'native_sdf_contact_diagnostic.launch.py',
            ))
            self.assertEqual(supervisor.MEASUREMENT_SHUTDOWN_GRACE_MS, 5000)
            with self.assertRaises(RuntimeError):
                dependencies.compile_helper(Path(raw))
            with self.assertRaises(RuntimeError):
                dependencies.helper_once(Path(raw))



class PkgConfigPreparationTests(unittest.TestCase):
    def test_exact_private_pkg_config_environment_and_global_environment_unchanged(self):
        calls = []
        baseline = dict(supervisor.os.environ)

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, stdout=b'13.5.0\n10.3.2\n')

        factory = supervisor.RuntimeDependencyFactory(WORKSPACE_ROOT, run_factory=fake_run, environ={'KEEP': 'value'})
        environment = factory._pkg_config_environment()
        self.assertEqual(environment['PKG_CONFIG_PATH'], supervisor.os.pathsep.join(approval_guard.PKG_CONFIG_DIRECTORIES))
        self.assertEqual(environment['KEEP'], 'value')
        self.assertEqual(dict(supervisor.os.environ), baseline)
        self.assertEqual(calls[0][0], [str(supervisor.PKG_CONFIG_EXECUTABLE), '--modversion', 'gz-transport13', 'gz-msgs10'])
        self.assertEqual(calls[0][1]['env']['PKG_CONFIG_PATH'], environment['PKG_CONFIG_PATH'])

    def test_missing_or_version_mismatch_blocks_before_gxx(self):
        with tempfile.TemporaryDirectory() as raw:
            calls = []
            factory = supervisor.RuntimeDependencyFactory(WORKSPACE_ROOT, run_factory=lambda *args, **kwargs: calls.append((args, kwargs)))
            with mock.patch.object(approval_guard, 'pkg_config_identity', side_effect=approval_guard.TrustedContextError('missing')):
                with self.assertRaises(supervisor.PrepareFailure) as error:
                    factory.compile_helper(Path(raw))
            self.assertEqual(error.exception.status, 'INVALID_PREPARE_PKG_CONFIG_ENV')
            self.assertEqual(calls, [])
            with mock.patch.object(approval_guard, 'pkg_config_identity', return_value=(approval_guard.PKG_CONFIG_DIRECTORIES, {'gz-transport13': 'bad', 'gz-msgs10': '10.3.2'})):
                with self.assertRaises(supervisor.PrepareFailure) as error:
                    factory.compile_helper(Path(raw))
            self.assertEqual(error.exception.status, 'INVALID_PREPARE_PKG_CONFIG_ENV')
            self.assertEqual(calls, [])

    def test_missing_packet_or_guard_rejects_before_factory_or_popen(self):
        missing = approval_guard.TypedSceneApprovalSpec(
            TEST_SPEC.approval_id, approval_guard.SUPPORTED_SCHEMA,
            'docs/missing-packet.md', TEST_SPEC.guard_path,
        )
        with mock.patch.object(supervisor, 'build_runtime_dependencies') as factory, \
             mock.patch.object(approval_guard, 'acquire_trusted') as acquire, \
             mock.patch.object(supervisor.subprocess, 'Popen') as popen:
            with self.assertRaises(approval_guard.TrustedContextError):
                approval_guard.build_trusted_context(WORKSPACE_ROOT, missing)
        factory.assert_not_called(); acquire.assert_not_called(); popen.assert_not_called()


class DurableEvidenceCompletionTests(unittest.TestCase):
    def test_prepare_failure_precedes_artifact_and_guard_operations(self):
        events = []
        base = GuardedExecutionIntegrationTests().dependencies(events)

        def fail_prepare():
            events.append('prepare')
            raise supervisor.PrepareFailure('INVALID_PREPARE_COMPILE')

        deps = supervisor.GuardedExecutionDependencies(
            base.launch_bootstrap, base.spawn_create, base.compile_helper, base.helper_once,
            base.persist_artifact, base.shutdown_sigint_only, base.temporary_directory,
            base.now_utc, lambda: 'run-typed-scene-prepare-failure', fail_prepare,
            lambda run_id: events.append(('begin_run', run_id)), None,
            lambda: events.append('discard_prepared'),
        )
        with mock.patch.object(approval_guard, 'validate_spec', return_value=(None, Path('/tmp/guard.json'))), \
             mock.patch.object(approval_guard, 'build_trusted_context') as context, \
             mock.patch.object(approval_guard, 'acquire_trusted') as acquire, \
             mock.patch.object(approval_guard, 'consume_trusted') as consume:
            status = supervisor.execute_guarded(WORKSPACE_ROOT, TEST_SPEC, deps)
        self.assertEqual(status, 'INVALID_PREPARE_COMPILE')
        self.assertEqual(events, ['prepare'])
        context.assert_not_called(); acquire.assert_not_called(); consume.assert_not_called()

    def test_helper_argv_carries_exact_shared_run_id_without_runtime_call(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw).resolve()
            argv = supervisor.helper_runtime_argv(
                Path('/tmp/typed_scene_observer'), 'run-typed-scene-shared-id', output,
            )
        self.assertEqual(argv[0:4], ['/tmp/typed_scene_observer', '--runtime-once', '--run-id', 'run-typed-scene-shared-id'])
        self.assertIn('--output-dir', argv)
        with self.assertRaises(RuntimeError):
            supervisor.helper_runtime_argv(Path('/tmp/typed_scene_observer'), '../bad', Path('/tmp'))

    def test_finalized_records_share_run_id_and_no_response_has_no_raw_pair(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            factory = supervisor.RuntimeDependencyFactory(root, create_arguments=supervisor.CREATE_ARGUMENTS)
            run_id = 'run-typed-scene-durable-records'
            factory.begin_run(run_id)
            factory.finalize_evidence('SCENE_REQUEST_INCOMPLETE', None, False, True)
            artifact = root / 'artifacts/simulation/contact_producer_evidence' / run_id
            import json
            for name in ('run_manifest.json', 'scene_summary.json', 'request_metadata.json',
                         'create_process.json', 'helper_process.json', 'shutdown_outcome.json'):
                self.assertEqual(json.loads((artifact / name).read_text())['run_id'], run_id)
            self.assertFalse((artifact / 'scene_response.pb').exists())
            self.assertFalse((artifact / 'scene_response.sha256').exists())

    def test_atomic_json_never_overwrites_existing_or_symlink_target(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / 'evidence.json'
            supervisor.atomic_write_json_new(target, {'first': 1})
            with self.assertRaises(RuntimeError):
                supervisor.atomic_write_json_new(target, {'second': 2})
            self.assertEqual(target.read_text(), '{"first":1}\n')
            link = root / 'link.json'
            link.symlink_to(target)
            with self.assertRaises(RuntimeError):
                supervisor.atomic_write_json_new(link, {'blocked': True})

    def test_source_contract_has_prepare_before_begin_and_no_second_compile(self):
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        execute = source[source.index('def execute_guarded('):source.index('\ndef result_json(', source.index('def execute_guarded('))]
        self.assertLess(execute.index('dependencies.prepare()'), execute.index('dependencies.begin_run(run_id)'))
        self.assertEqual(execute.count('dependencies.compile_helper('), 0)
        self.assertNotIn('RequestRaw(', source)


class HelperTerminalContractTests(unittest.TestCase):
    ALLOWED = (
        'SCENE_SERVICE_UNAVAILABLE', 'SCENE_REQUEST_INCOMPLETE',
        'SCENE_RESPONSE_UNDECODABLE', 'SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY',
        'SCENE_LINK_NOT_OBSERVED_AFTER_DELAY', 'SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY',
        'SCENE_SENSOR_PRESENT_IDENTITY_ONLY',
    )

    def _write_terminal(self, artifact, run_id, status):
        import json
        response_status = status not in {'SCENE_SERVICE_UNAVAILABLE', 'SCENE_REQUEST_INCOMPLETE'}
        raw = artifact / 'scene_response.pb'
        sha = None
        if response_status:
            raw.write_bytes(b'protobuf-fixture')
            sha = supervisor.digest(raw)
            (artifact / 'scene_response.sha256').write_text(sha + '\n', encoding='ascii')
        timestamps = {
            'preflight_start_steady_ns': 1, 'preflight_end_steady_ns': 2,
            'request_start_steady_ns': 3 if response_status else None,
            'request_end_steady_ns': 4 if response_status else None,
        }
        summary = {'status': status, 'reason': 'OFFLINE_FIXTURE', 'run_id': run_id,
                   'request_raw_called': response_status, 'raw_response_sha256': sha,
                   'schema_version': 's3_d3_typed_scene_summary/v4', **timestamps}
        metadata = {'scene_status': status if response_status else None, 'detail': 'OFFLINE_FIXTURE',
                    'run_id': run_id, 'request_raw_called': response_status,
                    'outer_status': 'SCENE_CLASSIFICATION_COMPLETE' if response_status else status,
                    'service': '/world/world_demo/scene/info',
                    'schema_version': 's3_d3_typed_scene_metadata/v3', **timestamps}
        supervisor.atomic_write_json_new(artifact / 'scene_summary.json', summary)
        supervisor.atomic_write_json_new(artifact / 'request_metadata.json', metadata)

    def test_each_allowlisted_terminal_status_is_preserved_without_stdout_evidence(self):
        for status in self.ALLOWED:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                factory = supervisor.RuntimeDependencyFactory(root, create_arguments=supervisor.CREATE_ARGUMENTS)
                run_id = 'run-typed-scene-terminal-' + status.lower()
                factory.begin_run(run_id)
                artifact = root / 'artifacts/simulation/contact_producer_evidence' / run_id
                binary_dir = root / 'compiled'; binary_dir.mkdir()
                binary = binary_dir / 'typed_scene_observer'; binary.write_bytes(b'helper')
                prepared = supervisor.PreparedHelper(None, binary, supervisor.digest(binary),
                    'a' * 64, 'compiler', 'pkg', ('offline',))
                factory._prepared_helper = prepared
                factory._helper_sha256 = prepared.binary_sha256
                self._write_terminal(artifact, run_id, status)
                with mock.patch.object(supervisor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                    self.assertEqual(factory.helper_once(binary_dir), status)
                self.assertTrue((artifact / 'helper_process.json').is_file())

    def test_malformed_run_id_or_raw_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); factory = supervisor.RuntimeDependencyFactory(root, create_arguments=supervisor.CREATE_ARGUMENTS)
            run_id = 'run-typed-scene-invalid-evidence'; factory.begin_run(run_id)
            artifact = root / 'artifacts/simulation/contact_producer_evidence' / run_id
            binary_dir = root / 'compiled'; binary_dir.mkdir(); binary = binary_dir / 'typed_scene_observer'
            binary.write_bytes(b'helper')
            prepared = supervisor.PreparedHelper(None, binary, supervisor.digest(binary),
                'a' * 64, 'compiler', 'pkg', ('offline',))
            factory._prepared_helper = prepared
            factory._helper_sha256 = prepared.binary_sha256
            self._write_terminal(artifact, run_id, 'SCENE_SENSOR_PRESENT_IDENTITY_ONLY')
            import json
            summary_path = artifact / 'scene_summary.json'
            summary = json.loads(summary_path.read_text()); summary['run_id'] = 'run-typed-scene-other'
            summary_path.unlink(); supervisor.atomic_write_json_new(summary_path, summary)
            with mock.patch.object(supervisor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                with self.assertRaisesRegex(RuntimeError, 'INVALID_EVIDENCE_PERSISTENCE_FAILURE'):
                    factory.helper_once(binary_dir)


class NativeBindingAndHelperReceiptTests(unittest.TestCase):
    def test_native_create_plan_has_only_native_file_route_literals(self):
        plan = supervisor.resolve_create_plan(
            digest_path=lambda _: SHA_A, is_regular_file=lambda _: True,
        )
        self.assertEqual(plan.argv, supervisor.CREATE_ARGUMENTS)
        self.assertEqual(plan.argv[0:5], ('-world', 'world_demo', '-file',
            str(WORKSPACE_ROOT / approval_guard.INSTALLED_NATIVE_MODEL_PATH), '-name'))
        source = Path(supervisor.__file__).read_text(encoding='utf-8')
        for legacy in ('typed_scene_observer.launch.py', "'-topic'", '/robot_description',
                       'robot_state_publisher', 'ros_gz_bridge', '/cmd_vel'):
            self.assertNotIn(legacy, source)

    def test_helper_binary_receipt_missing_mismatch_and_mutation_fail_before_callback(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            factory = supervisor.RuntimeDependencyFactory(
                root, create_arguments=supervisor.CREATE_ARGUMENTS,
            )
            factory.begin_run('run-typed-scene-receipt')
            artifact = root / 'artifacts/simulation/contact_producer_evidence/run-typed-scene-receipt'
            binary_dir = root / 'compile'; binary_dir.mkdir()
            binary = binary_dir / 'typed_scene_observer'; binary.write_bytes(b'first')
            # No prepared receipt rejects before subprocess.run.
            with mock.patch.object(supervisor.subprocess, 'run') as runtime:
                with self.assertRaisesRegex(RuntimeError, 'binary invalid'):
                    factory.helper_once(binary_dir)
            runtime.assert_not_called()
            prepared = supervisor.PreparedHelper(None, binary, supervisor.digest(binary),
                'a' * 64, 'compiler', 'pkg', ('offline',))
            factory._prepared_helper = prepared
            factory._helper_sha256 = prepared.binary_sha256
            binary.write_bytes(b'mutated')
            with mock.patch.object(supervisor.subprocess, 'run') as runtime:
                with self.assertRaisesRegex(RuntimeError, 'binary invalid'):
                    factory.helper_once(binary_dir)
            runtime.assert_not_called()
            self.assertFalse((artifact / 'helper_process.json').exists())


if __name__ == '__main__':
    unittest.main()
