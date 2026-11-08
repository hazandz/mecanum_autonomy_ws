"""Ingress B2.3: GT chỉ ở oracle/emulator; POLICY nhận bản sao noisy.

Runner sở hữu node/executor và subscriptions. Adapter không tạo ROS context,
không publish /cmd_vel, không tự bind/rearm hoặc tạo application fact.
"""
from __future__ import annotations

from collections import OrderedDict, deque
import copy
from dataclasses import dataclass
import math
import threading
import time

from rclpy.serialization import serialize_message
from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput, SafetyLifecycleState, SimulationContactState, FinalIssuedCommandReceipt
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity, policy_transition_identity
from mecanum_nav_rl.core.issued_command_cutoff import IssuedCommandReceiptView, ReceiptSource
from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, BackendSessionIdentity
from mecanum_nav_rl.runtime_simulation.local_training_ports import GroundTruthPortSample, PolicySafeOdometryPort, SimulatedOdometryPort
from mecanum_nav_rl.simulation.simulated_odometry import SimulatedOdometryNoiseConfig, SimulatedOdometryStatus
from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness


@dataclass(frozen=True)
class ReceivedNoisySample:
    """Không giữ message GT hoặc pose oracle trong dữ liệu POLICY."""
    output: PolicySafeOdometryPort
    received_steady_ns: int
    lifecycle: EpisodeLifecycleIdentity


@dataclass(frozen=True)
class ReceivedScan:
    stamp_ns: int
    received_steady_ns: int
    message_bytes: bytes


@dataclass(frozen=True)
class TrustedPhysicsPair:
    """Chỉ dùng cho oracle/reset/contact, không thuộc observation POLICY."""
    stamp_ns: int
    iteration: int
    oracle_bytes: bytes
    backend_bytes: bytes
    oracle_received_steady_ns: int
    backend_received_steady_ns: int


def stamp_ns(value):
    if type(value.sec) is not int or value.sec < 0 or not 0 <= value.nanosec < 1_000_000_000:
        raise ValueError('invalid ROS source timestamp')
    return value.sec * 1_000_000_000 + value.nanosec


def lifecycle_identity(msg):
    return EpisodeLifecycleIdentity(msg.episode_generation, msg.reset_epoch, msg.runtime_generation)


def quaternion_rpy(q):
    values = (q.x, q.y, q.z, q.w)
    if not all(math.isfinite(v) for v in values) or abs(sum(v * v for v in values) - 1.) > 1e-5:
        raise ValueError('oracle quaternion is not normalized/finite')
    return (math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y)),
            math.asin(max(-1., min(1., 2 * (q.w * q.y - q.z * q.x)))),
            math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))


class LocalTrainingIngress:
    CAPACITY = 64

    def __init__(self, identity: BackendSessionIdentity, profile: dict, *, final_publisher_id: int,
                 policy_source_id: int, safe_stop_source_id: int, safety_publish, emit,
                 now_ns=time.monotonic_ns, now_ros_ns):
        if not isinstance(identity, BackendSessionIdentity):
            raise TypeError('verified backend session identity required')
        if any(type(v) is not int or not 0 < v < 2**64 for v in
               (final_publisher_id, policy_source_id, safe_stop_source_id)):
            raise ValueError('publisher/source identity missing')
        if LocalTrainingSafetyInput.SCHEMA_VERSION != 2:
            raise ValueError('B23 ingress requires generated Safety schema 2')
        self.identity, self.profile = identity, copy.deepcopy(profile)
        self.final_publisher_id, self.policy_source_id, self.safe_stop_source_id = (
            final_publisher_id, policy_source_id, safe_stop_source_id)
        self.publish, self.emit, self.now, self.ros_now = safety_publish, emit, now_ns, now_ros_ns
        self.lock = threading.RLock()
        self.lifecycle = None
        self.lifecycle_received_ns = -1
        self.noise_port = SimulatedOdometryPort()
        self._noise_ready = False
        self.noisy_samples = OrderedDict()
        self.scans = OrderedDict()
        self._oracles, self._states = OrderedDict(), OrderedDict()
        self.physics_pairs = deque(maxlen=self.CAPACITY)
        self.receipts = deque(maxlen=128)
        self.backend_state = None
        self.backend_received_ns = -1
        self._last_status_bytes = None
        self._last_gt_stamp = -1
        self._last_gt_bytes = None
        self._last_join_iteration = 0
        self._sample_sequence = 0
        self._last_receipt_sequence = 0
        self._receipt_bytes = OrderedDict()
        self.pending_ack = self.observation0_ack = None
        self.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
        self.admission_publication_enabled = False
        self.fault = None

    def _fail(self, reason):
        self.fault = reason
        self.pending_ack = None
        self.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
        self.emit('INGRESS_FAULT', {'reason': reason, 'steady_ns': self.now()})
        raise ValueError(reason)

    def _put(self, mapping, key, value, name):
        if key in mapping:
            self._fail('duplicate ' + name + ' source key')
        if len(mapping) >= self.CAPACITY:
            old, _ = mapping.popitem(last=False)
            self.emit('INGRESS_BUFFER_EVICTED', {'buffer': name, 'stamp_ns': old, 'steady_ns': self.now()})
        mapping[key] = value

    def bind_lifecycle(self, msg: SafetyLifecycleState):
        if not isinstance(msg, SafetyLifecycleState) or msg.header.frame_id != 'b2_training_arena':
            self._fail('invalid actual lifecycle message')
        with self.lock:
            raw = copy.deepcopy(msg)
            if self.lifecycle is not None:
                if raw.sequence < self.lifecycle.sequence:
                    self._fail('lifecycle source sequence regressed')
                if raw.sequence == self.lifecycle.sequence and (
                        lifecycle_identity(raw) != lifecycle_identity(self.lifecycle)
                        or raw.barrier_stamp != self.lifecycle.barrier_stamp
                        or raw.motion_permitted != self.lifecycle.motion_permitted
                        or raw.barrier_state != self.lifecycle.barrier_state):
                    self._fail('lifecycle same-sequence conflict')
                if lifecycle_identity(raw) != lifecycle_identity(self.lifecycle):
                    self.noisy_samples.clear(); self.scans.clear()
                    self._oracles.clear(); self._states.clear(); self.physics_pairs.clear()
                    self.pending_ack = self.observation0_ack = None
                    self.admission_state = LocalTrainingSafetyInput.ADMISSION_INHIBITED
                    self.admission_publication_enabled = False
                    self._last_join_iteration = 0
            self.lifecycle, self.lifecycle_received_ns = raw, self.now()

    def reset_noise(self, seed: int):
        """Gọi sau set-pose ACK; không sửa seed hoặc dữ liệu mẫu cũ."""
        p = self.profile
        noise = SimulatedOdometryNoiseConfig(p['position_bias_sigma_m'], p['yaw_bias_sigma_rad'],
            p['position_drift_sigma_m_per_tick'], p['yaw_drift_sigma_rad_per_tick'],
            p['linear_velocity_noise_sigma_mps'], p['yaw_rate_noise_sigma_radps'],
            p['noise_delay_samples'], p['noise_dropout_probability'])
        with self.lock:
            self.noise_port.reset(seed, noise)
            self._noise_ready = True
            self.noisy_samples.clear(); self.scans.clear()
            self._oracles.clear(); self._states.clear(); self.physics_pairs.clear()
            self._last_join_iteration = 0
            self.emit('EMULATOR_RESET', {'seed': seed, 'steady_ns': self.now()})

    def _check_ack(self, ack, operation):
        if not isinstance(ack, BackendControlAck):
            raise TypeError('actual validated control ACK required')
        req, res = ack.request, ack.response
        if (type(ack.observed_steady_ns) is not int
                or not 0 <= ack.observed_steady_ns <= self.now()):
            self._fail('ACK receive timestamp invalid')
        if (req.operation != operation or req.schema_version != req.SCHEMA_VERSION
                or res.schema_version != res.RESPONSE_SCHEMA_VERSION
                or res.result != res.RESULT_APPLIED or res.reason_code != res.REASON_NONE
                or req.request_sequence != res.request_sequence
                or req.session_id != self.identity.session_id or req.config_hash != self.identity.config_hash
                or req.asset_manifest_sha256 != self.identity.asset_manifest_sha256
                or req.coordinator_ingress_instance_id != self.identity.coordinator_ingress_instance_id
                or req.expected_backend_instance_id != self.identity.backend_instance_id
                or res.backend_instance_id != self.identity.backend_instance_id
                or res.applied_binding_revision != res.binding_revision
                or res.binding_revision != req.expected_binding_revision + 1
                or stamp_ns(res.applied_sim_stamp) > self.ros_now()
                or res.applied_physics_iteration == 0 or self.lifecycle is None):
            self._fail('ACK identity/schema/application fact mismatch')
        if lifecycle_identity(req) != lifecycle_identity(self.lifecycle) and operation != req.OP_BIND_PENDING_STEP:
            self._fail('ACK lifecycle differs from current source')
        return req, res

    def confirm_observation0(self, ack):
        with self.lock:
            req, _ = self._check_ack(ack, Control.Request.OP_CONFIRM_OBSERVATION0)
            if (req.selected_zero_final_publisher_instance_id != self.final_publisher_id
                    or req.selected_zero_final_publish_sequence == 0
                    or req.adjacent_boundary_final_publish_sequence <= req.selected_zero_final_publish_sequence):
                self._fail('observation0 publication proof identity missing')
            self.observation0_ack = ack

    def arm_pending(self, ack):
        with self.lock:
            req, res = self._check_ack(ack, Control.Request.OP_BIND_PENDING_STEP)
            if self.observation0_ack is None or not any(res.pending_admission_token):
                self._fail('pending admission lacks observation0/token')
            expected = policy_transition_identity(identity=lifecycle_identity(self.lifecycle),
                session_id=self.identity.session_id, source_instance_id=self.policy_source_id,
                source_sequence=req.pending_source_sequence, step_index=req.pending_step_index)
            if (req.pending_source_sequence != req.pending_step_index
                    or req.pending_transition_id != expected.transition_id
                    or stamp_ns(req.action_barrier_stamp) <= stamp_ns(self.lifecycle.barrier_stamp)):
                self._fail('pending step binding differs from B1 identity/barrier')
            self.pending_ack = ack
            self.admission_state = LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            self.admission_publication_enabled = True

    def inhibit(self, *, zero_only=False):
        with self.lock:
            self.pending_ack = None
            self.admission_state = (LocalTrainingSafetyInput.ADMISSION_ZERO_ONLY if zero_only
                                    else LocalTrainingSafetyInput.ADMISSION_INHIBITED)
            self.admission_publication_enabled = True

    def pause_admission_publication(self):
        with self.lock:
            self.admission_publication_enabled = False

    def on_ground_truth(self, msg):
        from nav_msgs.msg import Odometry
        if not isinstance(msg, Odometry):
            self._fail('oracle type mismatch')
        with self.lock:
            stamp, received, raw = stamp_ns(msg.header.stamp), self.now(), serialize_message(msg)
            if msg.header.frame_id != 'world' or msg.child_frame_id != 'base_link':
                self._fail('oracle frame mismatch')
            if stamp < self._last_gt_stamp:
                self._fail('oracle clock rollback')
            if stamp == self._last_gt_stamp:
                if raw != self._last_gt_bytes:
                    self._fail('oracle same stamp changed bytes')
                return None  # Paused replay không tiến emulator hoặc refresh receive age.
            pose, twist = msg.pose.pose, msg.twist.twist
            roll, pitch, yaw = quaternion_rpy(pose.orientation)
            values = (pose.position.x, pose.position.y, pose.position.z, roll, pitch, yaw,
                      twist.linear.x, twist.linear.y, twist.linear.z,
                      twist.angular.x, twist.angular.y, twist.angular.z)
            if not all(math.isfinite(v) for v in values):
                self._fail('oracle non-finite pose/twist')
            self._last_gt_stamp, self._last_gt_bytes = stamp, raw
            self._put(self._oracles, stamp, (raw, received), 'oracle')
            self._join_physics(stamp)
            if not self._noise_ready or self.lifecycle is None:
                return None
            output = self.noise_port.accept_ground_truth(GroundTruthPortSample(
                stamp, pose.position.x, pose.position.y, yaw,
                twist.linear.x, twist.linear.y, twist.angular.z))
            sample = ReceivedNoisySample(output, received, lifecycle_identity(self.lifecycle))
            self._put(self.noisy_samples, stamp, sample, 'noisy')
            self.emit('SAMPLE_RECEIVED', {'stamp_ns': stamp, 'steady_ns': received,
                'sample_sequence': output.source_sequence, 'status': output.snapshot.status.value})
            if self.admission_publication_enabled:
                self._publish_safety(sample)
            return sample

    def _publish_safety(self, sample):
        if self.fault or self.lifecycle is None:
            return
        pending = self.pending_ack
        source_ns = sample.output.snapshot.timestamp_ns
        if self.admission_state == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN:
            if pending is None or (sample.received_steady_ns <= pending.observed_steady_ns
                    or source_ns <= stamp_ns(pending.response.applied_sim_stamp)):
                self.emit('ADMISSION_SAMPLE_REJECTED', {'reason': 'sample not received/generated after ACK',
                    'stamp_ns': source_ns, 'received_ns': sample.received_steady_ns})
                return
        validate_dual_clock_freshness(source_ros_ns=source_ns, now_ros_ns=self.ros_now(),
            receive_steady_ns=sample.received_steady_ns, now_steady_ns=self.now(),
            max_age_ns=self.profile['odometry_max_age_ms'] * 1_000_000)
        msg = LocalTrainingSafetyInput()
        msg.schema_version = msg.SCHEMA_VERSION
        msg.header.frame_id = 'base_link'
        msg.header.stamp.sec, msg.header.stamp.nanosec = divmod(source_ns, 10**9)
        msg.session_id, msg.config_hash = self.identity.session_id, self.identity.config_hash
        msg.ingress_instance_id = self.identity.coordinator_ingress_instance_id
        self._sample_sequence += 1; msg.sample_sequence = self._sample_sequence
        (msg.episode_generation, msg.reset_epoch, msg.runtime_generation) = (
            sample.lifecycle.episode_generation, sample.lifecycle.reset_epoch, sample.lifecycle.runtime_generation)
        status = sample.output.snapshot.status
        msg.odometry_status = {SimulatedOdometryStatus.VALID: msg.ODOM_VALID,
            SimulatedOdometryStatus.DELAYED: msg.ODOM_DELAYED, SimulatedOdometryStatus.DROPPED: msg.ODOM_DROPPED}[status]
        measurement = sample.output.snapshot.measurement
        msg.measured_twist = [] if measurement is None else [measurement.vx_mps, measurement.vy_mps, measurement.wz_radps]
        msg.admission_state = self.admission_state
        if pending is not None:
            proof = self.observation0_ack.request
            msg.admission_token = pending.response.pending_admission_token
            msg.observation0_cutoff = proof.observation0_cutoff
            msg.observation0_final_publisher_instance_id = proof.selected_zero_final_publisher_instance_id
            msg.observation0_final_publish_sequence = proof.selected_zero_final_publish_sequence
        self.emit('ADMISSION_BUILT', {'sample_sequence': msg.sample_sequence, 'source_ros_ns': source_ns,
            'sample_received_ns': sample.received_steady_ns,
            'ack_observed_ns': pending.observed_steady_ns if pending else None,
            'steady_ns': self.now(), 'message_cdr_hex': serialize_message(msg).hex()})
        self.publish(msg)
        self.emit('ADMISSION_PUBLISHED', {'sample_sequence': msg.sample_sequence, 'steady_ns': self.now()})

    def on_backend(self, msg):
        if not isinstance(msg, SimulationContactState):
            self._fail('backend state type mismatch')
        with self.lock:
            raw, received = serialize_message(msg), self.now()
            if (msg.schema_version != msg.SCHEMA_VERSION or msg.session_id != self.identity.session_id
                    or msg.config_hash != self.identity.config_hash
                    or msg.backend_instance_id != self.identity.backend_instance_id
                    or msg.header.frame_id != 'b2_training_arena' or msg.status_sequence == 0):
                self._fail('backend source identity/schema mismatch')
            if self.backend_state is not None and msg.status_sequence <= self.backend_state.status_sequence:
                if raw != self._last_status_bytes or msg.status_sequence != self.backend_state.status_sequence:
                    self._fail('backend status sequence conflict/replay')
                return
            self.backend_state, self.backend_received_ns, self._last_status_bytes = copy.deepcopy(msg), received, raw
            stamp = stamp_ns(msg.header.stamp)
            if msg.paused:
                return
            if self.lifecycle is not None and lifecycle_identity(msg) != lifecycle_identity(self.lifecycle):
                self.emit('BACKEND_OLD_CONTEXT', {'status_sequence': msg.status_sequence, 'steady_ns': received})
                return
            if stamp in self._states:
                self._fail('unpaused status duplicate physics stamp')
            self._put(self._states, stamp, (raw, received), 'backend')
            self._join_physics(stamp)

    def _join_physics(self, stamp):
        from rclpy.serialization import deserialize_message
        if stamp not in self._oracles or stamp not in self._states:
            return
        oracle, oracle_received = self._oracles.pop(stamp)
        backend, backend_received = self._states.pop(stamp)
        status = deserialize_message(backend, SimulationContactState)
        if status.physics_iteration == 0 or (self._last_join_iteration
                and status.physics_iteration != self._last_join_iteration + 1):
            self._fail('physics iteration missing or gap at exact oracle/status join')
        self._last_join_iteration = status.physics_iteration
        pair = TrustedPhysicsPair(stamp, status.physics_iteration, oracle, backend,
                                  oracle_received, backend_received)
        self.physics_pairs.append(pair)
        self.emit('PHYSICS_PAIR', {'iteration': pair.iteration, 'stamp_ns': stamp,
            'oracle_received_ns': oracle_received, 'backend_received_ns': backend_received})

    def on_scan(self, msg):
        from sensor_msgs.msg import LaserScan
        from mecanum_nav_rl.runtime_safety.safety_supervisor_node import scan_values_valid
        if not isinstance(msg, LaserScan) or not scan_values_valid(msg) or msg.header.frame_id != 'lidar_frame':
            self._fail('scan invalid values/frame/type')
        p = self.profile
        if (len(msg.ranges) != p['lidar_beam_count']
                or abs(msg.range_min - p['lidar_min_range_m']) > 1e-6
                or abs(msg.range_max - p['lidar_max_range_m']) > 1e-6
                or abs(msg.angle_min - p['scan_angle_min_rad']) > 1e-6
                or abs(msg.angle_max - p['scan_angle_max_rad']) > 1e-6):
            self._fail('scan metadata differs from pinned source profile')
        with self.lock:
            stamp = stamp_ns(msg.header.stamp)
            raw = serialize_message(msg)
            if stamp in self.scans:
                if raw != self.scans[stamp].message_bytes:
                    self._fail('scan same stamp changed bytes')
                return  # Exact replay không làm mới receive age.
            self._put(self.scans, stamp, ReceivedScan(stamp, self.now(), raw), 'scan')

    def on_receipt(self, msg):
        if not isinstance(msg, FinalIssuedCommandReceipt):
            self._fail('receipt generated type mismatch')
        with self.lock:
            raw = serialize_message(msg)
            if msg.final_publish_sequence in self._receipt_bytes:
                if self._receipt_bytes[msg.final_publish_sequence] != raw:
                    self._fail('receipt same publication key changed bytes')
                return
            if (msg.final_publisher_instance_id != self.final_publisher_id or msg.header.frame_id != 'base_link'
                    or msg.final_publish_sequence != self._last_receipt_sequence + 1
                    or self.lifecycle is None or lifecycle_identity(msg) != lifecycle_identity(self.lifecycle)):
                self._fail('receipt publication source/gap/context mismatch')
            is_policy = msg.source == msg.SOURCE_POLICY
            if msg.source not in (msg.SOURCE_POLICY, msg.SOURCE_SAFE_STOP):
                self._fail('receipt source not allowed in LOCAL_TRAINING')
            source = self.policy_source_id if is_policy else self.safe_stop_source_id
            values = (msg.final_command.linear.x, msg.final_command.linear.y, msg.final_command.angular.z)
            if (msg.source_instance_id != source or msg.sequence == 0
                    or not all(math.isfinite(v) for v in values)
                    or any((msg.final_command.linear.z, msg.final_command.angular.x, msg.final_command.angular.y))):
                self._fail('receipt source identity/twist invalid')
            expected = (policy_transition_identity(identity=lifecycle_identity(self.lifecycle),
                session_id=self.identity.session_id, source_instance_id=source,
                source_sequence=msg.sequence, step_index=msg.sequence).transition_id if is_policy else '')
            if (msg.transition_id != expected or msg.step_index != (msg.sequence if is_policy else 0)
                    or (not is_policy and any(values))):
                self._fail('receipt B1 transition identity or SAFE_STOP values mismatch')
            receipt = IssuedCommandReceiptView(stamp_ns(msg.header.stamp), msg.final_publisher_instance_id,
                msg.final_publish_sequence, ReceiptSource.POLICY if is_policy else ReceiptSource.SAFE_STOP,
                source, msg.sequence, msg.step_index, msg.transition_id, lifecycle_identity(self.lifecycle),
                self.identity.session_id, self.identity.config_hash, values, self.now(), 'base_link', True)
            self._last_receipt_sequence = msg.final_publish_sequence
            self._receipt_bytes[msg.final_publish_sequence] = raw
            if len(self._receipt_bytes) > 128:
                self._receipt_bytes.popitem(last=False)
            self.receipts.append(receipt)
            self.emit('RECEIPT_RECEIVED', {'receipt_key': receipt.receipt_key,
                'received_ns': receipt.received_steady_ns, 'message_cdr_hex': raw.hex()})
            return receipt
