"""Điều phối control B2.3: request bất biến, ACK thật và deadline chung.

Module này không tạo ROS context hoặc tự cấp runtime authority. Runner sở hữu
node/client, lifecycle, guard và sink; port nhận đúng generated interface.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import time
from typing import Callable

from rclpy.serialization import deserialize_message, serialize_message
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort


@dataclass(frozen=True)
class BackendSessionIdentity:
    session_id: str
    config_hash: str
    asset_manifest_sha256: str
    coordinator_ingress_instance_id: int
    backend_instance_id: int

    def __post_init__(self):
        if (not isinstance(self.session_id, str) or not self.session_id
                or self.session_id != self.session_id.strip() or len(self.session_id) > 64):
            raise ValueError('B23 session identity invalid')
        for digest in (self.config_hash, self.asset_manifest_sha256):
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('B23 config/asset digest invalid')
        for value in (self.coordinator_ingress_instance_id, self.backend_instance_id):
            if type(value) is not int or not 0 < value < 2**64:
                raise ValueError('B23 instance identity invalid')


@dataclass(frozen=True)
class BackendControlAck:
    request_bytes: bytes
    response_bytes: bytes
    observed_steady_ns: int

    @property
    def response(self):
        return deserialize_message(self.response_bytes, Control.Response)

    @property
    def request(self):
        return deserialize_message(self.request_bytes, Control.Request)


def lifecycle_request_fields(snapshot: SafetyLifecycleState) -> dict:
    """Sao chép facts nguồn, gồm motion_permitted; không đổi READY thành hold giả."""
    if not isinstance(snapshot, SafetyLifecycleState):
        raise TypeError('actual SafetyLifecycleState is required')
    return {
        'episode_generation': snapshot.episode_generation,
        'reset_epoch': snapshot.reset_epoch,
        'runtime_generation': snapshot.runtime_generation,
        'lifecycle_sequence': snapshot.sequence,
        'primary_state': snapshot.primary_state,
        'barrier_state': snapshot.barrier_state,
        'lifecycle_header_stamp': snapshot.header.stamp,
        'lifecycle_frame_id': snapshot.header.frame_id,
        'barrier_stamp': snapshot.barrier_stamp,
        'motion_permitted': snapshot.motion_permitted,
    }


class BackendControlError(RuntimeError):
    def __init__(self, message: str, ack: BackendControlAck | None = None):
        super().__init__(message)
        self.ack = ack


class BackendControlSession:
    """Một sequence/revision owner cho backend service trong đúng phiên."""

    MUTATION_NS = 1_000_000_000
    POLL_NS = 5_000_000
    _PINNED = frozenset((
        'schema_version', 'coordinator_ingress_instance_id', 'request_sequence',
        'expected_binding_revision', 'expected_backend_instance_id',
        'session_id', 'config_hash', 'asset_manifest_sha256',
    ))

    def __init__(self, port: LocalTrainingBackendControlPort,
                 identity: BackendSessionIdentity, *, emit: Callable[[str, dict], None],
                 now_ns: Callable[[], int] = time.monotonic_ns,
                 pause: Callable = asyncio.sleep):
        if (Control.Request.SCHEMA_VERSION != 2
                or Control.Response.RESPONSE_SCHEMA_VERSION != 2):
            raise ValueError('B23 requires schema 2 at both control endpoints')
        if not isinstance(identity, BackendSessionIdentity) or not callable(emit):
            raise TypeError('B23 identity/evidence sink required')
        self.identity = identity
        self._port, self._emit = port, emit
        self._now_ns, self._pause = now_ns, pause
        self._sequence = 0
        self._revision = 0
        self._last_clock_ns = -1
        self._faulted = False
        self._uncertain_mutation = False
        self._lock = asyncio.Lock()
        self._futures = []
        self._active_task = None
        self.evidence_errors = []
        self._completed_acks = OrderedDict()

    @property
    def revision(self):
        return self._revision

    @property
    def owned_calls(self):
        return tuple(self._futures)

    def _now(self):
        now = self._now_ns()
        if type(now) is not int or now < 0 or now < self._last_clock_ns:
            self._faulted = True
            raise BackendControlError('control monotonic clock invalid')
        self._last_clock_ns = now
        return now

    async def _bounded_pause(self, deadline):
        before = self._now()
        remaining = deadline - before
        if remaining <= 0:
            raise TimeoutError('backend control deadline expired')
        await self._pause(min(self.POLL_NS, remaining) / 1_000_000_000)
        if self._now() <= before:
            raise BackendControlError('control pause did not advance monotonic clock')

    def _request_bytes(self, operation, fields):
        if self._PINNED.intersection(fields):
            raise ValueError('cannot override pinned backend identity/revision')
        request = Control.Request()
        request.schema_version = request.SCHEMA_VERSION
        request.operation = operation
        request.coordinator_ingress_instance_id = self.identity.coordinator_ingress_instance_id
        request.expected_backend_instance_id = self.identity.backend_instance_id
        request.session_id = self.identity.session_id
        request.config_hash = self.identity.config_hash
        request.asset_manifest_sha256 = self.identity.asset_manifest_sha256
        request.request_sequence = self._sequence + 1
        request.expected_binding_revision = self._revision
        known = request.get_fields_and_field_types()
        for key, value in fields.items():
            if key not in known:
                raise ValueError('unknown backend request field: ' + key)
            setattr(request, key, value)
        raw = serialize_message(request)
        self._sequence += 1
        return raw

    async def transact(self, operation: int, *, deadline_ns: int, **fields) -> BackendControlAck:
        if type(deadline_ns) is not int:
            raise TypeError('backend control deadline must be monotonic integer nanoseconds')
        start = self._now()
        deadline = min(deadline_ns, start + self.MUTATION_NS)
        while self._lock.locked():
            await self._bounded_pause(deadline)
        async with self._lock:
            if self._faulted and operation != Control.Request.OP_INHIBIT:
                raise BackendControlError('backend session already uncertain/faulted')
            if deadline <= self._now():
                raise TimeoutError('backend control deadline expired before submit')
            raw = self._request_bytes(operation, fields)
            request = deserialize_message(raw, Control.Request)
            self._active_task = asyncio.current_task()
            try:
                self._emit('CONTROL_REQUEST', {'request_sequence': request.request_sequence,
                           'operation': operation, 'request_cdr_hex': raw.hex(),
                           'request_sha256': hashlib.sha256(raw).hexdigest(),
                           'started_ns': start, 'deadline_ns': deadline})
                while self._now() < deadline:
                    # Mỗi lần gửi lấy lại cùng bytes: QUEUED không tạo request/actor mới.
                    future = self._port.submit(deserialize_message(raw, Control.Request))
                    self._futures.append(future)
                    while not future.done():
                        await self._bounded_pause(deadline)
                    observed = self._now()
                    if observed >= deadline:
                        raise TimeoutError('backend ACK observed after deadline')
                    try:
                        response = future.result()
                    finally:
                        self._futures.remove(future)
                    if not isinstance(response, Control.Response):
                        raise BackendControlError('backend ACK missing/generated type mismatch')
                    ack = BackendControlAck(raw, serialize_message(response), observed)
                    self._emit('CONTROL_RESPONSE', {'request_sequence': request.request_sequence,
                               'observed_ns': observed, 'response_cdr_hex': ack.response_bytes.hex(),
                               'result': response.result, 'reason': response.reason_code})
                    if (response.schema_version != response.RESPONSE_SCHEMA_VERSION
                            or response.request_sequence != request.request_sequence
                            or response.backend_instance_id != self.identity.backend_instance_id):
                        raise BackendControlError('backend ACK identity/schema mismatch', ack)
                    if response.result == response.RESULT_QUEUED:
                        if response.reason_code != response.REASON_NONE or any(response.pending_admission_token):
                            raise BackendControlError('QUEUED ACK contains reason or admission token', ack)
                        await self._bounded_pause(deadline)
                        continue
                    if response.result != response.RESULT_APPLIED or response.reason_code != response.REASON_NONE:
                        raise BackendControlError('backend control rejected: ' + str(response.reason_code), ack)
                    mutates = operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
                    expected = request.expected_binding_revision + int(mutates)
                    allowed_revisions = {expected}
                    if operation == Control.Request.OP_INHIBIT and self._uncertain_mutation:
                        # Một mutation đã gửi có thể APPLIED dù client chưa nhận ACK.
                        allowed_revisions.add(expected + 1)
                    if (response.binding_revision not in allowed_revisions
                            or response.applied_binding_revision != response.binding_revision
                            or (response.applied_physics_iteration == 0 and operation != Control.Request.OP_INHIBIT)
                            or response.applied_sim_stamp.sec < 0
                            or not 0 <= response.applied_sim_stamp.nanosec < 1_000_000_000):
                        raise BackendControlError('backend APPLIED revision/application fact invalid', ack)
                    token = bytes(response.pending_admission_token)
                    if operation == Control.Request.OP_BIND_PENDING_STEP and not any(token):
                        raise BackendControlError('pending step APPLIED without admission token', ack)
                    if operation != Control.Request.OP_BIND_PENDING_STEP and any(token):
                        raise BackendControlError('non-pending ACK carries admission token', ack)
                    self._revision = response.applied_binding_revision
                    self._emit('ACK_OBSERVED', {'request_sequence': request.request_sequence,
                               'revision': self._revision, 'observed_ns': observed,
                               'admission_token_hex': token.hex()})
                    self._completed_acks[request.request_sequence] = ack
                    if len(self._completed_acks) > 128:
                        self._completed_acks.popitem(last=False)
                    return ack
                raise TimeoutError('backend control mutation did not apply within deadline')
            except BaseException as error:
                self._faulted = True
                if operation not in (Control.Request.OP_INHIBIT, Control.Request.OP_VERIFY_CONTACT_CAPABILITY):
                    self._uncertain_mutation = True
                try:
                    self._emit('CONTROL_UNCERTAIN', {'request_sequence': request.request_sequence,
                               'at_ns': self._now_ns(), 'error': type(error).__name__, 'detail': str(error)})
                except BaseException as sink_error:
                    self.evidence_errors.append(repr(sink_error))
                raise
            finally:
                self._active_task = None
                self._futures[:] = [call for call in self._futures if not call.done()]

    async def inhibit(self, *, deadline_ns: int) -> BackendControlAck:
        """Dừng transaction chờ ở client rồi gửi INHIBIT; không đợi hết 1 s mutation.

        Cancel client không chứng minh server đã hủy mutation: chỉ ACK INHIBIT
        từ native mới là fact đóng quyền. Call chưa xong vẫn thuộc session.
        """
        self._faulted = True
        active = self._active_task
        if active is not None and active is not asyncio.current_task():
            active.cancel()
            while not active.done():
                await self._bounded_pause(deadline_ns)
        return await self.transact(Control.Request.OP_INHIBIT, deadline_ns=deadline_ns)

    def cancel_pending_calls(self):
        """Thu hồi future local sau khi ingress đã đóng; không coi đây là backend ACK."""
        for future in tuple(self._futures):
            if not future.done():
                future.cancel()
        self._futures[:] = [future for future in self._futures if not future.done()]


    async def replay(self, original: BackendControlAck, *, deadline_ns: int) -> BackendControlAck:
        """Gửi lại bytes ACK đã thuộc session; không tăng sequence/revision/budget cũ."""
        if type(deadline_ns) is not int or not isinstance(original, BackendControlAck):
            raise TypeError('owned ACK and integer replay deadline required')
        request = original.request
        owned = self._completed_acks.get(request.request_sequence)
        if owned is None or owned.request_bytes != original.request_bytes or owned.response_bytes != original.response_bytes:
            raise BackendControlError('replay is not a retained owned APPLIED transaction')
        deadline = min(deadline_ns, self._now() + self.MUTATION_NS)
        while self._lock.locked():
            await self._bounded_pause(deadline)
        async with self._lock:
            if self._now() >= deadline:
                raise TimeoutError('replay deadline expired before submit')
            self._emit('CONTROL_EXACT_REPLAY', {'request_sequence': request.request_sequence,
                'request_sha256': hashlib.sha256(original.request_bytes).hexdigest(), 'deadline_ns': deadline})
            self._active_task = asyncio.current_task()
            future = None
            try:
                future = self._port.submit(deserialize_message(original.request_bytes, Control.Request))
                self._futures.append(future)
                while not future.done():
                    await self._bounded_pause(deadline)
                observed = self._now()
                if observed >= deadline:
                    raise TimeoutError('replay ACK observed after deadline')
                response = future.result()
                if (not isinstance(response, Control.Response) or response.schema_version != 2
                        or response.backend_instance_id != self.identity.backend_instance_id
                        or response.request_sequence != request.request_sequence):
                    raise BackendControlError('replay ACK identity/schema mismatch')
                ack = BackendControlAck(original.request_bytes, serialize_message(response), observed)
                self._emit('CONTROL_REPLAY_RESPONSE', {'request_sequence': request.request_sequence,
                    'response_cdr_hex': ack.response_bytes.hex(), 'observed_ns': observed})
                return ack
            except BaseException as error:
                self._faulted = True
                try:
                    self._emit('CONTROL_REPLAY_UNCERTAIN', {'request_sequence': request.request_sequence,
                        'error': repr(error), 'at_ns': self._now_ns()})
                except BaseException as sink_error:
                    self.evidence_errors.append(repr(sink_error))
                raise
            finally:
                self._active_task = None
                if future is not None and future.done():
                    self._futures.remove(future)


class B1SnapshotPending(ValueError):
    """Chưa đủ facts trong budget; caller không được tạo transition thay thế."""


class LocalTrainingB1Adapter:
    """Ghép facts runtime thật rồi gọi transaction owner B1 không sửa core.

    Adapter đặc quyền giữ ingress để đọc oracle/reset. Vector trả cho POLICY
    chỉ được lắp từ scan, reference noisy, measured twist noisy và receipt.
    """

    def __init__(self, ingress, artifact_result, asset_manifest, *, scan_transform,
                 emit, task_id='local_training', goal_id='scenario_goal'):
        from mecanum_nav_rl.core.episode_lifecycle import EpisodeLifecycle
        from mecanum_nav_rl.core.rl_transition import RLTransitionCommitter
        from mecanum_nav_rl.simulation.contact_latch import ContactLatch
        from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoadResult
        import copy
        if (not isinstance(artifact_result, ScenarioArtifactLoadResult)
                or not artifact_result.ready or artifact_result.artifact is None):
            raise ValueError('B1 requires validated scenario artifact')
        artifact = artifact_result.artifact
        if (artifact.identity.gazebo_world_name != asset_manifest['world_id']
                or artifact.identity.world_file_sha256 != asset_manifest['world_file_sha256']
                or artifact.identity.scenario_content_sha256 != asset_manifest['scenario_artifacts'][
                    artifact.identity.scenario_id]['scenario_content_sha256']):
            raise ValueError('B1 scenario/asset closure mismatch')
        if not all(callable(value) for value in (scan_transform, emit)):
            raise TypeError('B1 requires actual scan transform and evidence sink')
        self.ingress, self.artifact_result = ingress, artifact_result
        self.asset_manifest = copy.deepcopy(asset_manifest)
        self.scan_transform, self.emit = scan_transform, emit
        self.task_id, self.goal_id = task_id, goal_id
        self.lifecycle = EpisodeLifecycle()
        self.committer = RLTransitionCommitter(self.lifecycle)
        self.contact = ContactLatch()
        self.binding = None
        self.last_contact_iteration = 0
        self.issuance = None
        self.action_barrier_ns = None
        self._application_logged = set()
        p = ingress.profile
        self.scales = tuple(p[key] for key in ('max_vx_mps', 'max_vy_mps', 'max_wz_radps'))

    def begin_reset(self):
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity
        from mecanum_nav_rl.tasks.scenario_artifact import scenario_session_binding_from_ready_artifact
        if self.ingress.lifecycle is None or self.ingress.fault:
            raise ValueError('reset has no valid lifecycle source')
        identity = lifecycle_identity(self.ingress.lifecycle)
        self.binding = scenario_session_binding_from_ready_artifact(self.artifact_result, identity)
        result = self.lifecycle.begin_reset(identity, self.binding)
        self.lifecycle.wait_for_initial_observation(identity)
        self.contact.reset(identity)
        self.last_contact_iteration = 0
        self.issuance = self.action_barrier_ns = None
        self.emit('B1_RESET_STARTED', {'identity': list((identity.episode_generation,
            identity.reset_epoch, identity.runtime_generation)), 'steady_ns': self.ingress.now()})
        return result

    def _joined(self, cutoff_ns):
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns, lifecycle_identity, quaternion_rpy
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        source = self.ingress
        if source.fault or self.binding is None or source.lifecycle is None:
            raise ValueError('B1 source/context fault or missing binding')
        identity = lifecycle_identity(source.lifecycle)
        if identity != self.binding.lifecycle_identity:
            raise ValueError('B1 lifecycle changed before transaction')
        if cutoff_ns not in source.scans or cutoff_ns not in source.noisy_samples:
            raise B1SnapshotPending('exact scan/noisy pair is not available')
        scan, noisy = source.scans[cutoff_ns], source.noisy_samples[cutoff_ns]
        pairs = [pair for pair in source.physics_pairs if pair.stamp_ns == cutoff_ns]
        if len(pairs) != 1:
            raise B1SnapshotPending('exact oracle/backend iteration pair is not available')
        pair = pairs[0]
        ros_now, steady_now = source.ros_now(), source.now()
        for stamp, received, age_ms in (
                (cutoff_ns, scan.received_steady_ns, source.profile['scan_max_age_ms']),
                (cutoff_ns, noisy.received_steady_ns, source.profile['odometry_max_age_ms']),
                (cutoff_ns, pair.oracle_received_steady_ns, source.profile['oracle_max_age_ms']),
                (stamp_ns(source.lifecycle.header.stamp), source.lifecycle_received_ns,
                 source.profile['lifecycle_max_age_ms'])):
            validate_dual_clock_freshness(source_ros_ns=stamp, now_ros_ns=ros_now,
                receive_steady_ns=received, now_steady_ns=steady_now, max_age_ns=age_ms * 1_000_000)
        if not 0 <= steady_now - pair.backend_received_steady_ns <= source.profile['backend_status_receive_age_ms'] * 1_000_000:
            raise ValueError('joined backend state receive age expired')
        oracle = deserialize_message(pair.oracle_bytes, Odometry)
        status = deserialize_message(pair.backend_bytes, SimulationContactState)
        if (stamp_ns(oracle.header.stamp) != cutoff_ns or stamp_ns(status.header.stamp) != cutoff_ns
                or noisy.output.snapshot.timestamp_ns != cutoff_ns or noisy.lifecycle != identity
                or lifecycle_identity(status) != identity or status.physics_iteration != pair.iteration
                or stamp_ns(source.lifecycle.barrier_stamp) >= cutoff_ns):
            raise ValueError('exact source/context/barrier pairing failed')
        quaternion_rpy(oracle.pose.pose.orientation)
        return {'identity': identity, 'scan': deserialize_message(scan.message_bytes, LaserScan),
                'scan_record': scan, 'noisy': noisy, 'pair': pair, 'oracle': oracle, 'status': status,
                'cutoff': cutoff_ns, 'ros_now': ros_now, 'steady_now': steady_now}

    def _selection(self, facts, *, reset):
        from mecanum_nav_rl.core.issued_command_cutoff import (
            ReceiptStreamBinding, CutoffStatus, select_reset_zero_at_cutoff, select_final_issued_at_cutoff,
        )
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        source = self.ingress
        stream = ReceiptStreamBinding(source.final_publisher_id, source.identity.session_id,
            source.identity.config_hash, facts['identity'], 'base_link')
        barrier = stamp_ns(source.lifecycle.barrier_stamp)
        phase_start = barrier if reset else max(barrier, self.action_barrier_ns)
        # Ingress đã kiểm toàn chuỗi; core chỉ nhận cửa sổ pha sau barrier.
        # Lịch sử trước pha vẫn được giữ nguyên để audit, không dùng làm fallback.
        receipts = tuple(receipt for receipt in source.receipts if receipt.lifecycle == facts['identity']
                         and receipt.publish_stamp_ns > phase_start)
        kwargs = dict(binding=stream, cutoff_ros_ns=facts['cutoff'], evaluation_ros_now_ns=facts['ros_now'],
            evaluation_steady_now_ns=facts['steady_now'],
            reset_barrier_ros_ns=stamp_ns(source.lifecycle.barrier_stamp), physical_scales=self.scales)
        selection = (select_reset_zero_at_cutoff(receipts, **kwargs) if reset else
                     select_final_issued_at_cutoff(receipts, issuance=self.issuance,
                        action_barrier_ros_ns=self.action_barrier_ns, **kwargs))
        if selection.status is CutoffStatus.PENDING:
            raise B1SnapshotPending('B1 cutoff pending: ' + str(selection.reason))
        if selection.status is not CutoffStatus.READY:
            raise ValueError('B1 cutoff rejected: ' + str(selection.reason))
        return selection

    def _prove_application(self, receipt, cutoff_ns):
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        for pair in self.ingress.physics_pairs:
            if pair.stamp_ns > cutoff_ns:
                continue
            status = deserialize_message(pair.backend_bytes, SimulationContactState)
            if (status.applied_receipt_valid and not status.local_zero_override
                    and status.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
                    and status.applied_final_publish_sequence == receipt.final_publish_sequence
                    and status.applied_physics_iteration == pair.iteration
                    and receipt.publish_stamp_ns <= stamp_ns(status.applied_sim_stamp) <= cutoff_ns):
                return status
        raise B1SnapshotPending('selected receipt lacks native application at/before cutoff')

    def _goal_fact(self, facts, transition=None):
        from mecanum_nav_rl.core.goal_facts import GoalFactProvenance, GoalFactJoinMode
        from mecanum_nav_rl.core.lifecycle_types import ExactObservationProvenance
        from mecanum_nav_rl.tasks.training_task_oracle import TrainingTaskOracle, OraclePose2D
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import quaternion_rpy
        stamp = facts['cutoff']
        provenance = ExactObservationProvenance(facts['identity'], stamp, stamp, stamp)
        pose = facts['oracle'].pose.pose
        result = TrainingTaskOracle().derive_goal_fact(artifact_result=self.artifact_result,
            pose=OraclePose2D(pose.position.x, pose.position.y, quaternion_rpy(pose.orientation)[2], self.binding),
            provenance=GoalFactProvenance(GoalFactJoinMode.RESET_OBSERVATION0 if transition is None
                else GoalFactJoinMode.STEP_TRANSITION, self.binding, provenance, stamp, transition),
            expected_transition_identity=transition)
        if result.fact is None:
            raise ValueError('task oracle rejected actual source: ' + result.status.value)
        return provenance, result

    def _observation(self, facts, selection):
        import math
        import numpy as np
        from mecanum_nav_rl.config.models import ObservationConfig, MotionLimitsConfig
        from mecanum_nav_rl.observations.lidar import LidarAngularBinner, RawLidarScan
        from mecanum_nav_rl.observations.measured_twist import MeasuredTwistFeatureExtractor
        from mecanum_nav_rl.observations.local_training_reference import (
            NoisyOdometryContext, LocalTrainingGoal, build_local_training_reference,
        )
        from mecanum_nav_rl.observations.v3_snapshot_types import (
            ActiveLifecycleConfigContext, LidarSnapshot, LocalReferenceSnapshot,
            MeasuredTwistSnapshot, FinalIssuedReceiptContext, LIFECYCLE_BARRIER_CONTRACT_ID,
            FRAME_TF_CONTRACT_ID, LIDAR_CONTRACT_ID, LOCAL_REFERENCE_CONTRACT_ID, MEASURED_TWIST_CONTRACT_ID,
        )
        from mecanum_nav_rl.observations.v3_snapshot_validation import validate_observation_inputs
        from mecanum_nav_rl.observations.v3_observation_assembler import assemble_observation
        sample, scan, identity = facts['noisy'], facts['scan'], facts['identity']
        odom = NoisyOdometryContext(sample.output.snapshot, identity,
            self.binding.coordinate_reference_id, self.binding.scenario_id, sample.received_steady_ns)
        goal = self.artifact_result.artifact.task_definition.goal
        reference = build_local_training_reference(LocalTrainingGoal(goal.x_m, goal.y_m,
            self.binding.coordinate_reference_id, self.binding.scenario_id), odom,
            evaluation_ros_now_ns=facts['ros_now'], evaluation_steady_now_ns=facts['steady_now'],
            scan_timestamp_ns=facts['cutoff'], scan_lifecycle=identity, scan_scenario_identity=self.binding.scenario_id)
        if not reference.ready:
            raise ValueError('noisy reference rejected: ' + str(reference.reason))
        config = ObservationConfig()
        limits = MotionLimitsConfig(max_vx_mps=self.scales[0], max_vy_mps=self.scales[1], max_wz_radps=self.scales[2])
        twist = MeasuredTwistFeatureExtractor(config, limits).extract(sample.output.snapshot)
        if twist.features is None:
            raise ValueError('noisy twist not ready')
        sector = LidarAngularBinner(config).bin_scan(RawLidarScan(facts['cutoff'], scan.angle_min,
            scan.angle_increment, scan.range_min, scan.range_max, tuple(scan.ranges)))
        # Clearance dùng transform base_link thật, đối chiếu extrinsic asset.
        transform = self.scan_transform()
        translation, rotation = transform.transform.translation, transform.transform.rotation
        expected = self.asset_manifest['sensor']['extrinsic_xyz_m']
        if (any(abs(a - b) > 1e-9 for a, b in zip((translation.x, translation.y, translation.z), expected))
                or any(abs(v) > 1e-9 for v in (rotation.x, rotation.y, rotation.z))
                or abs(abs(rotation.w) - 1.) > 1e-9):
            raise ValueError('scan transform differs from verified asset')
        points = ((translation.x + (scan.range_max if value == math.inf else value) * math.cos(scan.angle_min + i * scan.angle_increment),
                   translation.y + (scan.range_max if value == math.inf else value) * math.sin(scan.angle_min + i * scan.angle_increment))
                  for i, value in enumerate(scan.ranges))
        clearance = max(0., min(math.hypot(x, y) for x, y in points) - self.ingress.profile['robot_bounding_radius_m'])
        common = (identity.episode_generation, identity.reset_epoch, identity.runtime_generation, self.ingress.identity.config_hash)
        normalized = tuple(float(value) for value in np.asarray(selection.normalized_command, dtype=np.float32))
        inputs = validate_observation_inputs(context=ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, *common),
            lidar=LidarSnapshot(LIDAR_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common, 'lidar_frame',
                tuple(float(value / scan.range_max) for value in sector.sector_ranges_m)),
            local_reference=LocalReferenceSnapshot(LOCAL_REFERENCE_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
                'base_link', tuple(float(value) for value in reference.features)),
            measured_twist=MeasuredTwistSnapshot(MEASURED_TWIST_CONTRACT_ID, FRAME_TF_CONTRACT_ID, *common,
                'base_link', twist.features),
            receipt=FinalIssuedReceiptContext(LIFECYCLE_BARRIER_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
                *common, 'base_link', normalized))
        assembled = assemble_observation(inputs)
        if not assembled.ready or assembled.vector is None:
            raise ValueError('81D observation assembly rejected')
        self.emit('OBSERVATION_81D_ASSEMBLED', {'cutoff_ns': facts['cutoff'],
            'dtype': str(assembled.vector.dtype), 'shape': list(assembled.vector.shape),
            'vector_sha256': hashlib.sha256(assembled.vector.tobytes()).hexdigest(),
            'vector': [float(value) for value in assembled.vector],
            'selected_receipt_key': selection.receipt.receipt_key,
            'adjacent_receipt_key': selection.adjacent_receipt.receipt_key,
            'noisy_sample_received_ns': sample.received_steady_ns,
            'scan_received_ns': facts['scan_record'].received_steady_ns,
            'evaluation_ros_ns': facts['ros_now'], 'evaluation_steady_ns': facts['steady_now']})
        return inputs, assembled.vector, reference, odom, twist, clearance

    def commit_observation0(self, cutoff_ns):
        from mecanum_nav_rl.core.episode_lifecycle import ResetCommitCandidate, ResetZeroReceipt, EpisodeOperationStatus
        from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        with self.ingress.lock:
            facts = self._joined(cutoff_ns)
            selection = self._selection(facts, reset=True)
            self._prove_application(selection.receipt, cutoff_ns)
            self._observe_contact(cutoff_ns)
            if self.contact.state.contact_active:
                raise ValueError('reset observation0 has active contact')
            provenance, goal_result = self._goal_fact(facts)
            observed = self._observation(facts, selection)
            observation, clearance = observed[1], observed[-1]
            if clearance < self.ingress.profile['reset_footprint_clearance_expansion_m']:
                raise ValueError('reset observation0 clearance is not proven')
            goal = self.artifact_result.artifact.task_definition.goal
            result = self.lifecycle.commit_reset(ResetCommitCandidate(facts['identity'], provenance, goal_result,
                PreviousNormalizedCommand(0., 0., 0.), self.task_id, self.ingress.identity.session_id,
                self.goal_id, (goal.x_m, goal.y_m), stamp_ns(self.ingress.lifecycle.barrier_stamp),
                ResetZeroReceipt(selection.receipt.receipt_key, facts['identity'], selection.receipt.publish_stamp_ns,
                    'SAFE_STOP', PreviousNormalizedCommand(0., 0., 0.), selection, selection.stream_binding)))
            if result.status is not EpisodeOperationStatus.RESET_COMMITTED:
                raise ValueError('B1 reset commit rejected: ' + str(result.reason))
            self.emit('B1_RESET_COMMITTED', {'cutoff_ns': cutoff_ns, 'receipt_key': selection.receipt.receipt_key,
                'steady_ns': self.ingress.now()})
            # Không giao observation0 cho POLICY trước ACK backend CONFIRM.
            return observation, selection

    def begin_step(self):
        from mecanum_nav_rl.core.lifecycle_types import policy_transition_identity
        snapshot = self.lifecycle.snapshot
        if snapshot.identity is None or snapshot.step_index is None:
            raise ValueError('step has no committed B1 baseline')
        token = policy_transition_identity(identity=snapshot.identity, session_id=self.ingress.identity.session_id,
            source_instance_id=self.ingress.policy_source_id, source_sequence=snapshot.step_index + 1,
            step_index=snapshot.step_index + 1)
        self.lifecycle.begin_step(token)
        self.issuance = self.action_barrier_ns = None
        return token

    def record_issuance(self, envelope, *, action_barrier_ns):
        """Chỉ gọi sau publisher adapter trả về; không suy Safety/backend đã chấp nhận."""
        from mecanum_nav_rl.core.issued_command_cutoff import PolicyActionIssuance
        from mecanum_nav_rl.core.lifecycle_types import policy_transition_identity
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import lifecycle_identity, stamp_ns
        token = self.lifecycle.snapshot.active_transition_identity
        if token is None or self.issuance is not None:
            raise ValueError('missing pending B1 step or duplicate issuance')
        expected = policy_transition_identity(identity=lifecycle_identity(envelope), session_id=self.ingress.identity.session_id,
            source_instance_id=envelope.source_instance_id, source_sequence=envelope.sequence, step_index=envelope.sequence)
        if (expected != token or envelope.source != envelope.SOURCE_POLICY
                or envelope.source_instance_id != self.ingress.policy_source_id or envelope.header.frame_id != 'base_link'
                or type(action_barrier_ns) is not int
                or not stamp_ns(self.ingress.lifecycle.barrier_stamp) < action_barrier_ns <= stamp_ns(envelope.header.stamp)
                or stamp_ns(envelope.header.stamp) > self.ingress.ros_now()
                or self.ingress.pending_ack is None
                or stamp_ns(self.ingress.pending_ack.request.action_barrier_stamp) != action_barrier_ns
                or self.ingress.pending_ack.request.pending_transition_id != token.transition_id):
            raise ValueError('actual issuance does not match bound B1 step/barrier')
        self.issuance = PolicyActionIssuance(envelope.source_instance_id, envelope.sequence,
            expected.identity, expected.step_index, expected.transition_id)
        self.action_barrier_ns = action_barrier_ns
        self.emit('policy_adapter_issued', {'step_index': expected.step_index, 'transition_id': expected.transition_id,
            'sequence': envelope.sequence, 'source_instance_id': envelope.source_instance_id,
            'identity': [expected.identity.episode_generation, expected.identity.reset_epoch, expected.identity.runtime_generation],
            'steady_ns': self.ingress.now(), 'envelope_cdr_hex': serialize_message(envelope).hex()})

    def _observe_contact(self, cutoff_ns):
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.simulation.contact_latch import ContactFact
        for pair in self.ingress.physics_pairs:
            if pair.stamp_ns > cutoff_ns or pair.iteration <= self.last_contact_iteration:
                continue
            if self.last_contact_iteration and pair.iteration != self.last_contact_iteration + 1:
                raise ValueError('contact coverage history has a physics gap')
            status = deserialize_message(pair.backend_bytes, SimulationContactState)
            healthy = (status.contact_source_healthy and status.coverage_complete
                and status.required_collision_mask != 0
                and status.required_collision_mask == status.observed_collision_mask)
            fact = ContactFact(self.binding.lifecycle_identity,
                f'{status.backend_instance_id}:{status.status_sequence}', status.status_sequence,
                status.contact_active, healthy)
            result = self.contact.observe(fact)
            self.last_contact_iteration = pair.iteration
            if not result.accepted:
                raise ValueError('contact source continuity invalid: ' + str(result.reason))

    def _goal_sample(self, facts, selection, reference, odometry, twist):
        from mecanum_nav_rl.tasks.local_training_goal import LocalTrainingHealth, OracleGoalSample
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns, lifecycle_identity
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        source, status, life = self.ingress, facts['status'], self.ingress.lifecycle
        safety = source.safety_state
        if safety is None:
            raise ValueError('actual Safety state/endpoint is missing')
        validate_dual_clock_freshness(source_ros_ns=stamp_ns(safety.header.stamp),
            now_ros_ns=facts['ros_now'], receive_steady_ns=source.safety_received_ns,
            now_steady_ns=facts['steady_now'], max_age_ns=source.profile['policy_ttl_ms'] * 1_000_000)
        identity = facts['identity']
        key = (identity.episode_generation, identity.reset_epoch, identity.runtime_generation)
        selected = selection.receipt
        receipt_key = (selected.lifecycle.episode_generation, selected.lifecycle.reset_epoch, selected.lifecycle.runtime_generation)
        artifact = self.artifact_result.artifact
        goal, pose, velocity = artifact.task_definition.goal, facts['oracle'].pose.pose, facts['oracle'].twist.twist
        clock_ok = facts['cutoff'] <= facts['ros_now'] and not status.paused and not (status.fault_flags & status.FAULT_CLOCK)
        safety_context = (safety.reset_epoch == identity.reset_epoch and safety.runtime_generation == identity.runtime_generation)
        safety_ready = (safety_context and safety.state in (safety.STATE_NORMAL, safety.STATE_LIMITED, safety.STATE_STOPPED)
                        and safety.fault_bits == 0)
        healthy_contact = (self.contact.state.source_healthy is True and status.contact_source_healthy
            and status.coverage_complete and status.required_collision_mask == status.observed_collision_mask)
        values = dict(simulator_valid=(status.backend_instance_id == source.identity.backend_instance_id
                             and not status.paused and status.fault_flags == 0),
            clock_valid=clock_ok,
            reset_complete=(self.lifecycle.snapshot.reset_commit_facts is not None and source.observation0_ack is not None),
            scenario_identity_valid=(artifact.identity.scenario_content_sha256 == self.binding.scenario_content_sha256),
            world_identity_valid=(status.header.frame_id == artifact.identity.gazebo_world_name),
            session_identity_valid=(status.session_id == source.identity.session_id and selected.session_id == source.identity.session_id),
            lifecycle_valid=(lifecycle_identity(life) == identity),
            barrier_valid=(life.barrier_state == life.BARRIER_READY and stamp_ns(life.barrier_stamp) < facts['cutoff']),
            safety_ready=safety_ready, safety_fault=(safety.state == safety.STATE_FAULT or safety.fault_bits != 0),
            estop_active=safety.estop_active,
            reset_pending=self.lifecycle.snapshot.reset_in_progress,
            scan_valid=(facts['scan'].header.frame_id == 'lidar_frame'),
            noisy_odometry_valid=(odometry.snapshot.measurement is not None and odometry.snapshot.status.value == 'valid'),
            reference_valid=reference.ready, measured_twist_valid=twist.ready,
            oracle_pose_valid=(facts['oracle'].header.frame_id == 'world'),
            oracle_twist_valid=(facts['oracle'].child_frame_id == 'base_link'),
            contact_source_healthy=healthy_contact,
            receipt_valid=selected.admission_valid,
            context_matches=(selected.lifecycle == identity and self.binding.lifecycle_identity == identity
                and selected.ingress_config_hash == source.identity.config_hash and status.config_hash == source.identity.config_hash),
            scenario_session_binding=self.binding, task_id=self.task_id, session_id=source.identity.session_id,
            lifecycle_key=key, goal_id=self.goal_id, goal_x_m=goal.x_m, goal_y_m=goal.y_m,
            receipt_session_id=selected.session_id, receipt_lifecycle_key=receipt_key,
            oracle_timestamp_ns=facts['cutoff'], oracle_twist_timestamp_ns=facts['cutoff'],
            scan_timestamp_ns=facts['cutoff'], noisy_odometry_timestamp_ns=odometry.snapshot.timestamp_ns,
            reference_timestamp_ns=reference.timestamp_ns, measured_twist_timestamp_ns=twist.timestamp_ns,
            lifecycle_timestamp_ns=stamp_ns(life.header.stamp), receipt_timestamp_ns=selected.publish_stamp_ns,
            cutoff_ros_ns=facts['cutoff'], evaluation_ros_now_ns=facts['ros_now'],
            oracle_received_steady_ns=facts['pair'].oracle_received_steady_ns,
            oracle_twist_received_steady_ns=facts['pair'].oracle_received_steady_ns,
            scan_received_steady_ns=facts['scan_record'].received_steady_ns,
            noisy_odometry_received_steady_ns=odometry.received_steady_ns,
            lifecycle_received_steady_ns=source.lifecycle_received_ns,
            receipt_received_steady_ns=selected.received_steady_ns,
            evaluation_steady_now_ns=facts['steady_now'])
        for name, stamp, received in (
                ('scan', facts['cutoff'], facts['scan_record'].received_steady_ns),
                ('noisy_odom', odometry.snapshot.timestamp_ns, odometry.received_steady_ns),
                ('oracle', facts['cutoff'], facts['pair'].oracle_received_steady_ns),
                ('oracle_twist', facts['cutoff'], facts['pair'].oracle_received_steady_ns),
                ('lifecycle', stamp_ns(life.header.stamp), source.lifecycle_received_ns),
                ('receipt', selected.publish_stamp_ns, selected.received_steady_ns)):
            values[name + '_ros_age_ns'] = facts['ros_now'] - stamp
            values[name + '_steady_age_ns'] = facts['steady_now'] - received
        health = LocalTrainingHealth(**values)
        if not health.healthy():
            raise ValueError('actual LOCAL_TRAINING source health is incomplete/invalid')
        return OracleGoalSample(facts['cutoff'], facts['pair'].oracle_received_steady_ns,
            key, self.binding, self.task_id, source.identity.session_id, self.goal_id,
            goal.x_m, goal.y_m, pose.position.x, pose.position.y,
            velocity.linear.x, velocity.linear.y, velocity.angular.z, health)

    def commit_step(self, cutoff_ns):
        import numpy as np
        from mecanum_nav_rl.core.episode_lifecycle import CommandReceiptSnapshot, StepCommitCandidate, EpisodeLifecycleState
        from mecanum_nav_rl.core.issued_command_cutoff import ReceiptSource
        from mecanum_nav_rl.core.rl_transition import RLTransitionContext
        from mecanum_nav_rl.observations.previous_command import PreviousNormalizedCommand
        from mecanum_nav_rl.tasks.local_training_goal import GoalSettleState, evaluate_local_training_goal
        from mecanum_nav_rl.termination.manager import EpisodeTaskSample, TerminationInput, TerminationManager, TerminationReason
        from mecanum_nav_rl.rewards.manager import RewardManager, TransitionRewardInput
        with self.ingress.lock:
            snapshot = self.lifecycle.snapshot
            token = snapshot.active_transition_identity
            if token is None or self.issuance is None or self.action_barrier_ns is None:
                raise ValueError('step has no actual issuance or pending B1 identity')
            facts = self._joined(cutoff_ns)
            selection = self._selection(facts, reset=False)
            self._prove_application(selection.receipt, cutoff_ns)
            policies = [receipt for receipt in self.ingress.receipts if receipt.source is ReceiptSource.POLICY
                and receipt.lifecycle == token.identity and receipt.transition_id == token.transition_id
                and receipt.source_instance_id == self.ingress.policy_source_id and receipt.source_sequence == token.step_index
                and receipt.publish_stamp_ns <= cutoff_ns]
            applied_policy = None
            for receipt in policies:
                try:
                    applied_policy = (receipt, self._prove_application(receipt, cutoff_ns)); break
                except B1SnapshotPending:
                    continue
            if applied_policy is None:
                raise B1SnapshotPending('issued POLICY has no native application before cutoff')
            self._observe_contact(cutoff_ns)
            provenance, fact = self._goal_fact(facts, token)
            inputs, observation, reference, odometry, twist, clearance = self._observation(facts, selection)
            goal_sample = self._goal_sample(facts, selection, reference, odometry, twist)
            old = snapshot.goal_settle_state
            continuous = (snapshot.task_health_epoch == snapshot.committed_task_health_epoch
                          and self.contact.state.health_epoch == snapshot.committed_contact_health_epoch)
            settle_state = GoalSettleState() if old is None or not continuous else GoalSettleState(
                goal_sample.lifecycle_key, old.settled_since_ros_ns, old.last_ros_ns, old.success,
                self.binding, old.task_id, old.session_id, old.goal_id, old.goal_xy_m)
            goal = self.artifact_result.artifact.task_definition.goal
            goal_result = evaluate_local_training_goal(goal_sample, settle_state,
                expected_scenario_session_binding=self.binding, expected_task_id=self.task_id,
                expected_session_id=self.ingress.identity.session_id, expected_goal_id=self.goal_id,
                expected_goal_xy_m=(goal.x_m, goal.y_m))
            if not goal_result.healthy:
                raise ValueError('goal settle source health rejected: ' + str(goal_result.reason))
            history = tuple(EpisodeTaskSample(sample.ros_time_ns, sample.x_m, sample.y_m,
                sample.true_goal_distance_m, sample.required_health_valid) for sample in snapshot.task_history
                if (continuous and sample.lifecycle == token.identity and sample.task_id == self.task_id
                    and sample.session_id == self.ingress.identity.session_id and sample.goal_id == self.goal_id
                    and sample.goal_xy_m == (goal.x_m, goal.y_m)))
            contact = self.contact.state
            termination = TerminationManager().evaluate(TerminationInput(
                cutoff_ns - snapshot.reset_commit_facts.observation_provenance.observation_timestamp_ns,
                EpisodeTaskSample(cutoff_ns, goal_sample.pose_x_m, goal_sample.pose_y_m,
                    goal_result.distance_m, goal_result.healthy), history,
                contact.contact_active or contact.collision_pulse_pending, goal_result.success))
            normalized = tuple(float(value) for value in np.asarray(selection.normalized_command, dtype=np.float32))
            candidate = StepCommitCandidate(token, provenance, fact,
                CommandReceiptSnapshot(token, selection.receipt.receipt_key, PreviousNormalizedCommand(*normalized)),
                EpisodeLifecycleState.TERMINATED if termination.terminated else
                EpisodeLifecycleState.TRUNCATED if termination.truncated else EpisodeLifecycleState.RUNNING)
            baseline, previous = snapshot.reward_baseline, snapshot.previous_issued_command
            reward = RewardManager().compute(TransitionRewardInput(baseline.previous_goal_distance_m,
                fact.fact.goal_distance_m, clearance, (cutoff_ns - baseline.previous_committed_sim_time_ns) / 1e9,
                normalized, tuple(float(value) for value in np.asarray((previous.vx, previous.vy, previous.wz), dtype=np.float32)),
                goal=termination.reason is TerminationReason.GOAL,
                collision=termination.reason is TerminationReason.COLLISION,
                stuck=termination.reason is TerminationReason.STUCK))
            context = RLTransitionContext(token, candidate, observation, reward, termination,
                (('step_index', token.step_index),), selection.receipt.receipt_key, selection, normalized,
                token.transition_id, self.contact, self.issuance, applied_policy[0], clearance, provenance,
                inputs, reference, odometry, twist, goal_sample, self.task_id, self.ingress.identity.session_id,
                self.goal_id, (goal.x_m, goal.y_m), None)
            application = applied_policy[1]
            if token.transition_id not in self._application_logged:
                self._application_logged.add(token.transition_id)
                self.emit('B1_POLICY_APPLICATION_BOUND', {'step_index': token.step_index, 'transition_id': token.transition_id,
                    'publisher_instance_id': application.applied_final_publisher_instance_id,
                    'publish_sequence': application.applied_final_publish_sequence,
                    'iteration': application.applied_physics_iteration,
                    'stamp_ns': application.applied_sim_stamp.sec * 10**9 + application.applied_sim_stamp.nanosec,
                    'steady_ns': self.ingress.now()})
            result = self.committer.commit(context)
            if not result.committed:
                raise ValueError('B1 transition commit rejected: ' + str(result.reason))
            self.emit('b1_transition_committed', {'step_index': token.step_index,
                'transition_id': token.transition_id, 'receipt_key': selection.receipt.receipt_key,
                'cutoff_ns': cutoff_ns, 'reward': result.transition.reward.total,
                'terminated': result.transition.termination.terminated, 'truncated': result.transition.termination.truncated,
                'steady_ns': self.ingress.now()})
            return result.transition
