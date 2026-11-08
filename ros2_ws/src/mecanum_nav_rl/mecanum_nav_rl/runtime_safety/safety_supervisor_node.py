"""Selector Safety theo mode: NAV2_BASELINE và LOCAL_TRAINING tách đầu vào."""
from __future__ import annotations

from geometry_msgs.msg import Twist
import math
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState, SafetyState

from mecanum_nav_rl.runtime_safety.safety_contract import (
    BarrierState, SafetyInputs, SafetyLifecycleCore, SafetyPolicy, SafetySupervisorCore,
)


def scan_values_valid(msg: LaserScan) -> bool:
    """+Inf là no-return; metadata, NaN và -Inf vẫn fail closed."""
    metadata = (msg.range_min, msg.range_max, msg.angle_min, msg.angle_increment)
    return (bool(msg.ranges) and all(math.isfinite(value) for value in metadata)
            and 0.0 <= msg.range_min < msg.range_max and msg.angle_increment != 0.0
            and all((math.isfinite(value) and msg.range_min <= value <= msg.range_max)
                    or value == math.inf for value in msg.ranges))


class SafetySupervisorNode(Node):
    _POLICY_NAMES = (
        "freshness_ns.command_ttl", "freshness_ns.scan_max_age",
        "freshness_ns.filtered_odometry_max_age", "freshness_ns.lifecycle_barrier_max_age",
        "limits.velocity", "limits.acceleration", "limits.jerk",
    )

    def __init__(self, *, local_training_context=None, evidence_sink=None, **node_options) -> None:
        super().__init__("safety_supervisor", **node_options)
        if self.get_parameter("use_sim_time").value is not True:
            raise ValueError("SIM_EVAL_USE_SIM_TIME_MUST_BE_TRUE")
        self.declare_parameter('navigation_mode', 'NAV2_BASELINE')
        mode = self.get_parameter('navigation_mode').value
        if mode not in ('NAV2_BASELINE', 'LOCAL_TRAINING'):
            raise ValueError('unsupported SafetySupervisor mode')
        if mode == 'LOCAL_TRAINING':
            from mecanum_nav_rl_interfaces.msg import LocalTrainingSafetyInput, SimulationContactState
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self)
            reliable = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            sensor = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5,
                reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
            backend = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=50,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            self._accepted_pub = self.create_publisher(
                CommandEnvelope, "/mecanum/safety_accepted_cmd", reliable)
            self._state_pub = self.create_publisher(SafetyState, '/mecanum/safety_state', reliable)
            self.local_training = LocalTrainingSafetyAdapter(self, local_training_context, emit=evidence_sink)
            for message_type, topic, callback, qos in (
                (CommandEnvelope, '/mecanum/cmd_policy', self.local_training.on_command, reliable),
                (LaserScan, '/scan', self.local_training.on_scan, sensor),
                (SafetyLifecycleState, '/mecanum/safety_lifecycle_state', self.local_training.on_lifecycle, reliable),
                (LocalTrainingSafetyInput, '/mecanum/local_training/safety_input', self.local_training.on_safety_input, reliable),
                (SimulationContactState, '/mecanum/local_training/backend_state', self.local_training.on_backend, backend),
            ):
                self.create_subscription(message_type, topic, callback, qos)
            self.create_timer(local_training_context['profile']['safety_period_ms'] / 1000,
                              self.local_training.tick)
            return
        for name in self._POLICY_NAMES:
            self.declare_parameter(name)
        self.declare_parameter("sim_estop_release_authorized", False)
        self._policy = SafetyPolicy.from_mapping({
            "freshness_ns": {
                "command_ttl": self.get_parameter("freshness_ns.command_ttl").value,
                "scan_max_age": self.get_parameter("freshness_ns.scan_max_age").value,
                "filtered_odometry_max_age": self.get_parameter("freshness_ns.filtered_odometry_max_age").value,
                "lifecycle_barrier_max_age": self.get_parameter("freshness_ns.lifecycle_barrier_max_age").value,
            },
            "limits": {
                "velocity": self.get_parameter("limits.velocity").value,
                "acceleration": self.get_parameter("limits.acceleration").value,
                "jerk": self.get_parameter("limits.jerk").value,
            },
        })
        estop_parameter = self.get_parameter("sim_estop_release_authorized").value
        if type(estop_parameter) is not bool:
            raise ValueError("SIM_ESTOP_RELEASE_AUTHORIZATION_MUST_BE_BOOLEAN")
        self._sim_estop_release_authorized = estop_parameter
        self._core = SafetySupervisorCore(self._policy)
        self._command: Twist | None = None
        self._command_stamp_ns = 0
        self._scan_stamp_ns = 0
        self._scan_finite = False
        self._scan_frame_valid = False
        self._odom_stamp_ns = 0
        self._odom_finite = False
        self._odom_frame_valid = False
        self._barrier: SafetyLifecycleState | None = None
        self._source_sequence = 0
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)
        reliable_volatile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        sensor_data_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._accepted_pub = self.create_publisher(
            CommandEnvelope, "/mecanum/safety_accepted_cmd", reliable_volatile
        )
        self._state_pub = self.create_publisher(SafetyState, "/mecanum/safety_state", reliable_volatile)
        self.create_subscription(Twist, "/mecanum/nav2_candidate_cmd", self._on_command, reliable_volatile)
        self.create_subscription(LaserScan, "/scan", self._on_scan, sensor_data_qos)
        self.create_subscription(Odometry, "/odometry/filtered", self._on_odometry, reliable_volatile)
        self.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_barrier, reliable_volatile)
        self.create_timer(0.05, self._evaluate_and_publish)

    def _on_command(self, msg: Twist) -> None:
        self._command = msg
        self._command_stamp_ns = self.get_clock().now().nanoseconds

    def _on_scan(self, msg: LaserScan) -> None:
        self._scan_stamp_ns = self._stamp(msg.header.stamp)
        self._scan_frame_valid = msg.header.frame_id == "lidar_frame"
        self._scan_finite = scan_values_valid(msg)

    def _on_odometry(self, msg: Odometry) -> None:
        self._odom_stamp_ns = self._stamp(msg.header.stamp)
        self._odom_frame_valid = msg.header.frame_id == "odom" and msg.child_frame_id == "base_link"
        values = [msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.angular.z,
                  *msg.pose.covariance, *msg.twist.covariance]
        self._odom_finite = len(msg.pose.covariance) == 36 and len(msg.twist.covariance) == 36 and all(math.isfinite(value) for value in values)

    def _on_barrier(self, msg: SafetyLifecycleState) -> None:
        self._barrier = msg

    @staticmethod
    def _stamp(stamp: object) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    def _evaluate_and_publish(self) -> None:
        now = self.get_clock().now().nanoseconds
        command = self._command or Twist()
        barrier_msg = self._barrier
        barrier_ns = self._stamp(barrier_msg.barrier_stamp) if barrier_msg is not None else 0
        barrier = BarrierState.READY if barrier_msg is not None and (
            barrier_msg.barrier_state == SafetyLifecycleState.BARRIER_READY and barrier_msg.motion_permitted
        ) else BarrierState.NON_READY
        try:
            tf_valid = bool(self._tf_buffer.can_transform("odom", "base_link", rclpy.time.Time())) and self._odom_frame_valid
            localization_valid = bool(self._tf_buffer.can_transform("map", "odom", rclpy.time.Time()))
        except Exception:
            tf_valid = localization_valid = False
        result = self._core.evaluate(SafetyInputs(
            now, self._command_stamp_ns, self._scan_stamp_ns, self._odom_stamp_ns,
            barrier_ns, barrier, tf_valid, localization_valid,
            self._sim_estop_release_authorized,
            (command.linear.x, command.linear.y, command.angular.z),
            self._scan_finite, self._odom_finite,
            self._scan_frame_valid, self._odom_frame_valid,
        ))
        output = Twist()
        output.linear.x, output.linear.y, output.angular.z = result.command
        envelope = CommandEnvelope()
        envelope.header.stamp = self.get_clock().now().to_msg()
        envelope.header.frame_id = "base_link"
        envelope.source = CommandEnvelope.SOURCE_NAV2 if result.accepted else CommandEnvelope.SOURCE_SAFE_STOP
        self._source_sequence += 1
        envelope.sequence = self._source_sequence
        envelope.episode_generation = barrier_msg.episode_generation if barrier_msg is not None else 0
        envelope.reset_epoch = barrier_msg.reset_epoch if barrier_msg is not None else 0
        envelope.runtime_generation = barrier_msg.runtime_generation if barrier_msg is not None else 0
        import os
        envelope.source_instance_id = os.getpid()
        envelope.twist = output
        self._accepted_pub.publish(envelope)
        state = SafetyState()
        state.header = envelope.header
        state.state = SafetyState.STATE_NORMAL if result.accepted else SafetyState.STATE_STOPPED
        state.reset_epoch = envelope.reset_epoch
        state.runtime_generation = envelope.runtime_generation
        state.active_command_source = envelope.source
        state.command_valid = result.accepted
        state.scan_fresh = (self._scan_frame_valid and self._scan_stamp_ns > 0
                            and 0 <= now - self._scan_stamp_ns <= self._policy.scan_max_age_ns)
        state.odom_fresh = self._odom_frame_valid and self._odom_stamp_ns > 0
        state.tf_valid = tf_valid
        state.localization_valid = localization_valid
        state.motion_permitted = result.accepted
        state.estop_active = "SIM_ESTOP_ACTIVE" in result.reasons
        state.intervention_reasons = list(result.reasons)
        state.raw_command = command
        state.limited_command = output
        state.final_command = output
        self._state_pub.publish(state)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SafetySupervisorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


class LocalTrainingSafetyAdapter:
    """Selector LOCAL_TRAINING không dùng GT, map/odom TF hoặc Nav2 giả.

    Context đến từ runner đã pin config/asset. Callback giữ bytes và receive
    time gốc; tick không tạo POLICY issuance mới và không làm mới TTL.
    """

    def __init__(self, node, context, *, now_steady_ns=None, emit=None):
        import copy
        import threading
        import time
        from mecanum_nav_rl.safety.command_safety_core import MotionLimits, VelocityCommand
        if not isinstance(context, dict):
            raise ValueError('LOCAL_TRAINING requires verified runner context')
        self.node, self.context = node, copy.deepcopy(context)
        self.now = now_steady_ns or time.monotonic_ns
        if not callable(emit):
            raise ValueError('LOCAL_TRAINING Safety requires evidence sink')
        self.emit = emit
        for key in ('session_id', 'config_hash', 'ingress_instance_id', 'backend_instance_id',
                    'policy_source_instance_id', 'safe_stop_source_instance_id', 'profile', 'sensor',
                    'sim_estop_release_authorized'):
            if key not in self.context:
                raise ValueError('missing LOCAL_TRAINING Safety context: ' + key)
        digest = self.context['config_hash']
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in '0123456789abcdef' for c in digest)
                or not isinstance(context['session_id'], str) or not context['session_id']
                or any(type(context[k]) is not int or not 0 < context[k] < 2**64 for k in
                       ('ingress_instance_id', 'backend_instance_id',
                        'policy_source_instance_id', 'safe_stop_source_instance_id'))
                or context['policy_source_instance_id'] == context['safe_stop_source_instance_id']):
            raise ValueError('invalid LOCAL_TRAINING Safety context')
        p = self.context['profile']
        self.limits = MotionLimits(p['max_vx_mps'], p['max_vy_mps'], p['max_wz_radps'],
            p['max_accel_xy_mps2'], p['max_accel_xy_mps2'], p['max_accel_yaw_radps2'],
            p['max_jerk_xy_mps3'], p['max_jerk_xy_mps3'], p['max_jerk_yaw_radps3'])
        self.lock = threading.RLock()
        self.command = self.scan = self.noisy = self.life = self.status = None
        self.command_bytes = None
        self.command_received = self.scan_received = self.noisy_received = 0
        self.life_received = self.status_received = 0
        self.noisy_bytes = self.status_bytes = None
        self.previous_velocity = self.previous_acceleration = VelocityCommand(0., 0., 0.)
        self.last_tick_ns = None
        self.fault = None
        self.stream_enabled = True
        self.policy_hold = True
        self.safe_stop_sequence = 0
        self.state_observer = None
        self.last_output = None
        self.expected_extrinsic = (tuple(self.context['sensor']['extrinsic_xyz_m']),
                                   tuple(self.context['sensor']['extrinsic_rpy_rad']))
        if self.expected_extrinsic[1] != (0., 0., 0.):
            raise ValueError('LOCAL_TRAINING sensor rotation not supported by pinned profile')

    @staticmethod
    def identity(msg):
        return msg.episode_generation, msg.reset_epoch, msg.runtime_generation

    @staticmethod
    def stamp(value):
        if not 0 <= value.nanosec < 1_000_000_000:
            raise ValueError('invalid ROS stamp')
        return value.sec * 1_000_000_000 + value.nanosec

    def fail(self, reason):
        self.fault = reason
        self.emit('SAFETY_INPUT_REJECTED', {'reason': reason, 'steady_ns': self.now()})

    def on_lifecycle(self, msg):
        import copy
        with self.lock:
            if msg.header.frame_id != 'b2_training_arena':
                self.fail('LIFECYCLE_FRAME'); return
            if self.life is not None:
                if msg.sequence < self.life.sequence:
                    self.fail('LIFECYCLE_SEQUENCE_REGRESSION'); return
                if msg.sequence == self.life.sequence and (
                        self.identity(msg) != self.identity(self.life)
                        or msg.barrier_stamp != self.life.barrier_stamp
                        or msg.barrier_state != self.life.barrier_state
                        or msg.motion_permitted != self.life.motion_permitted):
                    self.fail('LIFECYCLE_SAME_SEQUENCE_CONFLICT'); return
                if self.identity(msg) != self.identity(self.life):
                    self.command = self.noisy = None
                    self.command_bytes = self.noisy_bytes = None
            self.life = copy.deepcopy(msg)
            self.life_received = self.now()

    def on_command(self, msg):
        import copy
        from rclpy.serialization import serialize_message
        with self.lock:
            values = (msg.twist.linear.x, msg.twist.linear.y, msg.twist.angular.z)
            if (msg.source != msg.SOURCE_POLICY
                    or msg.source_instance_id != self.context['policy_source_instance_id']
                    or msg.sequence == 0 or msg.header.frame_id != 'base_link'
                    or self.life is None or self.identity(msg) != self.identity(self.life)
                    or any((msg.twist.linear.z, msg.twist.angular.x, msg.twist.angular.y))
                    or not all(math.isfinite(v) for v in values)
                    or self.stamp(msg.header.stamp) <= self.stamp(self.life.barrier_stamp)):
                self.fail('POLICY_IDENTITY_OR_VALUES'); return
            raw = serialize_message(msg)
            if self.command is not None:
                if msg.sequence == self.command.sequence:
                    if raw != self.command_bytes:
                        self.fail('POLICY_SAME_KEY_CONFLICT')
                    return
                if msg.sequence != self.command.sequence + 1:
                    self.fail('POLICY_SEQUENCE_GAP_OR_REPLAY'); return
            elif msg.sequence != 1:
                self.fail('POLICY_FIRST_SEQUENCE_NOT_ONE'); return
            self.command, self.command_bytes = copy.deepcopy(msg), raw
            self.command_received = self.now()

    def on_scan(self, msg):
        import copy
        with self.lock:
            # Giữ invalid sample để tick đóng motion; không tái dùng scan cũ.
            self.scan, self.scan_received = copy.deepcopy(msg), self.now()

    def on_safety_input(self, msg):
        import copy
        from rclpy.serialization import serialize_message
        with self.lock:
            if (msg.schema_version != msg.SCHEMA_VERSION or msg.SCHEMA_VERSION != 2
                    or msg.session_id != self.context['session_id']
                    or msg.config_hash != self.context['config_hash']
                    or msg.ingress_instance_id != self.context['ingress_instance_id']
                    or msg.header.frame_id != 'base_link' or msg.sample_sequence == 0
                    or self.life is None or self.identity(msg) != self.identity(self.life)):
                self.fail('SAFETY_INPUT_IDENTITY'); return
            raw = serialize_message(msg)
            if self.noisy is not None and msg.sample_sequence <= self.noisy.sample_sequence:
                if msg.sample_sequence != self.noisy.sample_sequence or raw != self.noisy_bytes:
                    self.fail('SAFETY_INPUT_REPLAY_OR_CONFLICT')
                return
            self.noisy, self.noisy_bytes = copy.deepcopy(msg), raw
            self.noisy_received = self.now()

    def on_backend(self, msg):
        import copy
        from rclpy.serialization import serialize_message
        with self.lock:
            if (msg.schema_version != msg.SCHEMA_VERSION
                    or msg.session_id != self.context['session_id']
                    or msg.config_hash != self.context['config_hash']
                    or msg.backend_instance_id != self.context['backend_instance_id']
                    or msg.header.frame_id != 'b2_training_arena' or msg.status_sequence == 0):
                self.fail('BACKEND_IDENTITY'); return
            raw = serialize_message(msg)
            if self.status is not None and msg.status_sequence <= self.status.status_sequence:
                if msg.status_sequence != self.status.status_sequence or raw != self.status_bytes:
                    self.fail('BACKEND_REPLAY_OR_CONFLICT')
                return
            self.status, self.status_bytes = copy.deepcopy(msg), raw
            self.status_received = self.now()

    def set_stream_enabled(self, enabled):
        if type(enabled) is not bool:
            raise TypeError('stream state must be boolean')
        with self.lock:
            self.stream_enabled = enabled
            if not enabled:
                self.policy_hold = True

    def set_policy_hold(self, hold):
        if type(hold) is not bool:
            raise TypeError('policy hold must be boolean')
        with self.lock:
            self.policy_hold = hold

    def _reasons(self, ros_ns, steady_ns):
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        p = self.context['profile']
        reasons = []
        for name, msg, received, budget in (
                ('COMMAND', self.command, self.command_received, p['policy_ttl_ms']),
                ('SCAN', self.scan, self.scan_received, p['scan_max_age_ms']),
                ('NOISY', self.noisy, self.noisy_received, p['odometry_max_age_ms']),
                ('LIFECYCLE', self.life, self.life_received, p['lifecycle_max_age_ms'])):
            if msg is None:
                reasons.append(name + '_MISSING'); continue
            try:
                validate_dual_clock_freshness(source_ros_ns=self.stamp(msg.header.stamp),
                    now_ros_ns=ros_ns, receive_steady_ns=received, now_steady_ns=steady_ns,
                    max_age_ns=budget * 1_000_000)
            except ValueError:
                reasons.append(name + '_STALE_OR_FUTURE')
        if self.fault:
            reasons.append(self.fault)
        if self.policy_hold:
            reasons.append('POLICY_HELD')
        if self.context['sim_estop_release_authorized'] is not True:
            reasons.append('SIM_ESTOP_ACTIVE')
        life = self.life
        if (life is None or life.primary_state != life.PRIMARY_ACTIVE
                or life.barrier_state != life.BARRIER_READY or not life.motion_permitted):
            reasons.append('LIFECYCLE_NOT_READY')
        noisy = self.noisy
        if (noisy is None or noisy.odometry_status != noisy.ODOM_VALID
                or len(noisy.measured_twist) != 3 or not all(math.isfinite(v) for v in noisy.measured_twist)
                or noisy.admission_state != noisy.ADMISSION_POLICY_OPEN
                or not any(noisy.admission_token)
                or self.stamp(noisy.observation0_cutoff) <= 0
                or noisy.observation0_final_publisher_instance_id == 0
                or noisy.observation0_final_publish_sequence == 0):
            reasons.append('NOISY_OR_ADMISSION_NOT_VALID')
        status = self.status
        if (status is None or not 0 <= steady_ns - self.status_received <= p['backend_status_receive_age_ms'] * 1_000_000
                or life is None or self.identity(status) != self.identity(life)
                or not status.coverage_complete or not status.contact_source_healthy
                or status.required_collision_mask == 0
                or status.required_collision_mask != status.observed_collision_mask
                or status.contact_active or status.fault_flags or status.paused):
            reasons.append('BACKEND_CONTACT_UNHEALTHY')
        scan = self.scan
        sensor = self.context['sensor']
        if (scan is None or scan.header.frame_id != 'lidar_frame' or not scan_values_valid(scan)
                or len(scan.ranges) != sensor['beams']
                or abs(scan.range_min - sensor['range_m'][0]) > 1e-6
                or abs(scan.range_max - sensor['range_m'][1]) > 1e-6
                or abs(scan.angle_min - sensor['angle_rad'][0]) > 1e-6
                or abs(scan.angle_max - sensor['angle_rad'][1]) > 1e-6):
            reasons.append('SCAN_VALUES_OR_FRAME_INVALID')
        else:
            # Chỉ dùng extrinsic tĩnh đã pin; xác minh TF thật trùng asset trước đo khoảng cách.
            try:
                transform = self.node._tf_buffer.lookup_transform('base_link', 'lidar_frame', rclpy.time.Time())
                t, q = transform.transform.translation, transform.transform.rotation
                xyz, rpy = self.expected_extrinsic
                if (any(abs(a - b) > 1e-9 for a, b in zip((t.x, t.y, t.z), xyz))
                        or any(abs(v) > 1e-9 for v in (q.x, q.y, q.z)) or abs(abs(q.w) - 1.) > 1e-9):
                    raise ValueError('TF differs from pinned asset')
                points = ((xyz[0] + v * math.cos(scan.angle_min + i * scan.angle_increment),
                           xyz[1] + v * math.sin(scan.angle_min + i * scan.angle_increment))
                          for i, v in enumerate(scan.ranges) if math.isfinite(v))
                if any(math.hypot(x, y) <= p['stopping_distance_limit_m'] for x, y in points):
                    reasons.append('STOPPING_ENVELOPE_OCCUPIED')
            except Exception:
                reasons.append('SCAN_EXTRINSIC_UNVERIFIED')
        return tuple(reasons)

    def tick(self):
        import copy
        from mecanum_nav_rl.safety.command_safety_core import VelocityCommand, limit_motion_command
        with self.lock:
            if not self.stream_enabled:
                return
            ros_ns = self.node.get_clock().now().nanoseconds
            now = self.now()
            reasons = self._reasons(ros_ns, now)
            previous = self.last_tick_ns
            self.last_tick_ns = now
            if previous is not None and now <= previous:
                reasons += ('SAFETY_CLOCK_NOT_INCREASING',)
            if previous is None:
                reasons += ('LIMITER_PRIMED',)
            if not reasons:
                try:
                    candidate = VelocityCommand(self.command.twist.linear.x,
                        self.command.twist.linear.y, self.command.twist.angular.z)
                    velocity, acceleration = limit_motion_command(candidate, self.previous_velocity,
                        self.previous_acceleration, (now - previous) / 1e9, self.limits)
                except ValueError as error:
                    reasons += (str(error),)
            accepted = not reasons
            if accepted:
                self.previous_velocity, self.previous_acceleration = velocity, acceleration
                envelope = copy.deepcopy(self.command)
                envelope.twist.linear.x, envelope.twist.linear.y, envelope.twist.angular.z = (
                    velocity.linear_x, velocity.linear_y, velocity.angular_z)
            else:
                self.previous_velocity = self.previous_acceleration = VelocityCommand(0., 0., 0.)
                envelope = CommandEnvelope()
                envelope.header.stamp = self.node.get_clock().now().to_msg()
                envelope.header.frame_id = 'base_link'
                envelope.source = envelope.SOURCE_SAFE_STOP
                self.safe_stop_sequence += 1
                envelope.sequence = self.safe_stop_sequence
                envelope.source_instance_id = self.context['safe_stop_source_instance_id']
                if self.life is not None:
                    (envelope.episode_generation, envelope.reset_epoch,
                     envelope.runtime_generation) = self.identity(self.life)
            self.node._accepted_pub.publish(envelope)
            self.last_output = copy.deepcopy(envelope)
            state = SafetyState()
            state.header.stamp = self.node.get_clock().now().to_msg()
            state.header.frame_id = 'base_link'
            state.state = state.STATE_NORMAL if accepted else state.STATE_STOPPED
            state.active_command_source, state.command_valid = envelope.source, accepted
            state.motion_permitted = accepted
            state.reset_epoch, state.runtime_generation = envelope.reset_epoch, envelope.runtime_generation
            state.intervention_reasons = list(reasons)
            state.raw_command = self.command.twist if self.command is not None else Twist()
            state.limited_command = state.final_command = envelope.twist
            self.node._state_pub.publish(state)
            if self.state_observer is not None:
                self.state_observer(copy.deepcopy(state))
            self.emit('SAFETY_ACCEPTED' if accepted else 'SAFETY_REJECTED', {
                'steady_ns': now, 'ros_ns': ros_ns, 'sequence': envelope.sequence,
                'source': envelope.source, 'reasons': list(reasons)})
            return envelope
