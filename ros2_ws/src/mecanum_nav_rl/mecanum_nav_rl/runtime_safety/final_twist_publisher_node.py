"""Single ROS /cmd_vel publisher with publish-before-receipt ordering."""
from __future__ import annotations

import os
import math
import secrets
import time
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, FinalIssuedCommandReceipt, SafetyLifecycleState


class FinalTwistPublisherNode(Node):
    def __init__(self, *, evidence_sink=None, **node_options) -> None:
        super().__init__("final_twist_publisher", **node_options)
        if self.get_parameter("use_sim_time").value is not True:
            raise ValueError("SIM_EVAL_USE_SIM_TIME_MUST_BE_TRUE")
        self.declare_parameter('navigation_mode', 'NAV2_BASELINE')
        self.declare_parameter('session_id', '')
        self.declare_parameter('policy_source_instance_id', 0)
        self.declare_parameter('safe_stop_source_instance_id', 0)
        mode = self.get_parameter('navigation_mode').value
        if mode not in ('NAV2_BASELINE', 'LOCAL_TRAINING'):
            raise ValueError('unsupported FinalTwistPublisher mode')
        self._local_training = mode == 'LOCAL_TRAINING'
        self._session_id = self.get_parameter('session_id').value
        self._policy_source = self.get_parameter('policy_source_instance_id').value
        self._safe_stop_source = self.get_parameter('safe_stop_source_instance_id').value
        if self._local_training and (not isinstance(self._session_id, str)
                or not self._session_id or self._session_id.strip() != self._session_id
                or len(self._session_id) > 64
                or any(type(v) is not int or not 0 <= v < 2**63
                       for v in (self._policy_source, self._safe_stop_source))
                or (bool(self._policy_source) != bool(self._safe_stop_source))
                or (self._policy_source != 0 and self._policy_source == self._safe_stop_source)):
            raise ValueError('LOCAL_TRAINING publisher requires bound session/source identities')
        if self._local_training:
            if not callable(evidence_sink):
                raise ValueError('LOCAL_TRAINING publisher requires evidence sink')
            self._emit = evidence_sink
        self._local_admitted = False
        self._binding_sha256 = None
        self._identity_received_ns = 0
        self._identity: SafetyLifecycleState | None = None
        self._final_publish_sequence = 0
        self._last_receipt_bytes = None
        self._publisher_instance_id = (secrets.randbelow(2**63 - 1) + 1) if self._local_training else os.getpid()
        command_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        receipt_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        reliable_volatile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", command_qos)
        self._receipt_pub = self.create_publisher(FinalIssuedCommandReceipt, "/mecanum/final_issued_command", receipt_qos)
        self.create_subscription(CommandEnvelope, "/mecanum/safety_accepted_cmd", self._on_accepted, reliable_volatile)
        self.create_subscription(SafetyLifecycleState, "/mecanum/safety_lifecycle_state", self._on_lifecycle, reliable_volatile)

    @property
    def publisher_instance_id(self):
        return self._publisher_instance_id

    @property
    def last_publication(self):
        """Bản sao receipt đã publish thành công; không suy application native."""
        if self._last_receipt_bytes is None:
            return None
        from rclpy.serialization import deserialize_message
        return deserialize_message(self._last_receipt_bytes, FinalIssuedCommandReceipt)

    def bind_backend_session(self, ack, expected_identity):
        """Nối sources sau ACK native thật; child restart mặc định chưa được bind.

        Đây là biên bootstrap riêng của runner, không tạo ROS interface thứ ba
        hoặc đường actuator mới. Replay cùng bytes không làm mới binding.
        """
        import hashlib
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, BackendSessionIdentity
        if not self._local_training or not isinstance(ack, BackendControlAck) or not isinstance(expected_identity, BackendSessionIdentity):
            raise TypeError('actual B23 backend binding ACK/identity required')
        digest = hashlib.sha256(ack.request_bytes + ack.response_bytes).hexdigest()
        req, res = ack.request, ack.response
        if (req.operation != req.OP_BIND_SESSION or req.schema_version != 2 or res.schema_version != 2
                or req.session_id != self._session_id or req.session_id != expected_identity.session_id
                or req.config_hash != expected_identity.config_hash
                or req.asset_manifest_sha256 != expected_identity.asset_manifest_sha256
                or req.coordinator_ingress_instance_id != expected_identity.coordinator_ingress_instance_id
                or req.expected_backend_instance_id != expected_identity.backend_instance_id
                or res.backend_instance_id != expected_identity.backend_instance_id
                or res.request_sequence != req.request_sequence or res.result != res.RESULT_APPLIED
                or res.reason_code != res.REASON_NONE or req.expected_binding_revision != 0
                or res.binding_revision != 1 or res.applied_binding_revision != 1
                or res.applied_physics_iteration == 0 or any(res.pending_admission_token)
                or res.applied_sim_stamp.sec < 0 or not 0 <= res.applied_sim_stamp.nanosec < 10**9
                or req.final_publisher_instance_id != self._publisher_instance_id
                or req.policy_source_instance_id == 0 or req.safe_stop_source_instance_id == 0
                or req.policy_source_instance_id == req.safe_stop_source_instance_id):
            raise ValueError('final publisher ACK session/source/application mismatch')
        if self._binding_sha256 is not None:
            if digest != self._binding_sha256:
                raise ValueError('final publisher binding cannot change within one boot')
            return
        now = self.get_clock().now().nanoseconds
        steady_now = time.monotonic_ns()
        applied = res.applied_sim_stamp.sec * 10**9 + res.applied_sim_stamp.nanosec
        life = self._identity
        if (type(ack.observed_steady_ns) is not int
                or not 0 <= steady_now - ack.observed_steady_ns <= 1_000_000_000
                or not 0 < applied <= now or life is None
                or (life.episode_generation, life.reset_epoch, life.runtime_generation)
                   != (req.episode_generation, req.reset_epoch, req.runtime_generation)
                or life.sequence != req.lifecycle_sequence or life.barrier_stamp != req.barrier_stamp
                or life.header.frame_id != req.lifecycle_frame_id):
            raise ValueError('final publisher lifecycle/clock is not ready for actual binding')
        self._policy_source, self._safe_stop_source = req.policy_source_instance_id, req.safe_stop_source_instance_id
        self._binding_sha256, self._local_admitted = digest, True
        self._emit('FINAL_SOURCE_BINDING_APPLIED', {'binding_sha256': digest,
            'publisher_instance_id': self._publisher_instance_id,
            'backend_instance_id': expected_identity.backend_instance_id, 'steady_ns': time.monotonic_ns()})

    def _on_lifecycle(self, msg: SafetyLifecycleState) -> None:
        self._identity = msg
        self._identity_received_ns = time.monotonic_ns()

    def _on_accepted(self, envelope: CommandEnvelope) -> None:
        identity = self._identity
        is_safe_stop = envelope.source == CommandEnvelope.SOURCE_SAFE_STOP
        local = getattr(self, '_local_training', False)
        allowed = CommandEnvelope.SOURCE_POLICY if local else CommandEnvelope.SOURCE_NAV2
        if not is_safe_stop and envelope.source != allowed:
            return
        if local:
            if not self._policy_source or not self._safe_stop_source:
                return
            if not is_safe_stop and not getattr(self, '_local_admitted', False):
                return
            expected = self._safe_stop_source if is_safe_stop else self._policy_source
            values = (envelope.twist.linear.x, envelope.twist.linear.y, envelope.twist.angular.z,
                      envelope.twist.linear.z, envelope.twist.angular.x, envelope.twist.angular.y)
            if (envelope.source_instance_id != expected or envelope.sequence == 0
                    or envelope.header.frame_id != 'base_link'
                    or not all(math.isfinite(v) for v in values)
                    or any(values[3:])):
                self.get_logger().error('LOCAL_COMMAND_IDENTITY_OR_VALUES_INVALID')
                return
            if is_safe_stop and any(values):
                self.get_logger().error('LOCAL_SAFE_STOP_MUST_BE_ZERO')
                return
        if not is_safe_stop:
            if identity is None:
                return
            envelope_identity = (
                envelope.episode_generation,
                envelope.reset_epoch,
                envelope.runtime_generation,
            )
            lifecycle_identity = (
                identity.episode_generation,
                identity.reset_epoch,
                identity.runtime_generation,
            )
            if envelope_identity != lifecycle_identity:
                self.get_logger().error("NAV2_COMMAND_LIFECYCLE_IDENTITY_MISMATCH")
                return
            now_ns = self.get_clock().now().nanoseconds
            identity_ns = identity.header.stamp.sec * 1_000_000_000 + identity.header.stamp.nanosec
            identity_fresh = identity_ns > 0 and 0 <= now_ns - identity_ns <= 500_000_000
            if local:
                source_ns = envelope.header.stamp.sec * 1_000_000_000 + envelope.header.stamp.nanosec
                identity_fresh = (identity_fresh
                    and identity.primary_state == identity.PRIMARY_ACTIVE
                    and identity.barrier_state == identity.BARRIER_READY
                    and 0 <= time.monotonic_ns() - self._identity_received_ns <= 500_000_000
                    and source_ns > 0 and 0 <= now_ns - source_ns <= 200_000_000)
            if not identity.motion_permitted or not identity_fresh:
                self.get_logger().error("NAV2_COMMAND_LIFECYCLE_BARRIER_NOT_READY_OR_STALE")
                return
        if local:
            from mecanum_nav_rl.core.lifecycle_types import (
                EpisodeLifecycleIdentity, policy_transition_identity,
            )
            step_index = 0 if is_safe_stop else envelope.sequence
            transition_id = '' if is_safe_stop else policy_transition_identity(
                identity=EpisodeLifecycleIdentity(envelope.episode_generation,
                    envelope.reset_epoch, envelope.runtime_generation),
                session_id=self._session_id, source_instance_id=envelope.source_instance_id,
                source_sequence=envelope.sequence, step_index=envelope.sequence,
            ).transition_id
        else:
            step_index = envelope.sequence
            transition_id = "sim_eval_nav2_baseline"
        final_command = Twist() if is_safe_stop else envelope.twist
        try:
            self._cmd_pub.publish(final_command)
        except Exception as error:
            self.get_logger().error(f"FINAL_CMD_PUBLISH_FAILED:{type(error).__name__}")
            return
        self._final_publish_sequence += 1
        receipt = FinalIssuedCommandReceipt()
        receipt.header.stamp = self.get_clock().now().to_msg()
        receipt.header.frame_id = "base_link"
        receipt.episode_generation = envelope.episode_generation
        receipt.reset_epoch = envelope.reset_epoch
        receipt.runtime_generation = envelope.runtime_generation
        receipt.step_index = step_index
        receipt.transition_id = transition_id
        receipt.source = envelope.source
        receipt.sequence = envelope.sequence
        receipt.source_instance_id = envelope.source_instance_id
        receipt.final_publisher_instance_id = self._publisher_instance_id
        receipt.final_publish_sequence = self._final_publish_sequence
        receipt.final_command = final_command
        try:
            self._receipt_pub.publish(receipt)
        except Exception:
            if local and hasattr(self, '_emit'):
                self._emit('FINAL_PUBLISHED_WITHOUT_RECEIPT', {
                    'publish_sequence': self._final_publish_sequence,
                    'source': envelope.source, 'sequence': envelope.sequence,
                })
            raise
        if local and hasattr(self, '_emit'):
            from rclpy.serialization import serialize_message
            self._last_receipt_bytes = serialize_message(receipt)
            record = {'receipt_cdr_hex': self._last_receipt_bytes.hex(),
                'steady_ns': time.monotonic_ns(), 'source_instance_id': receipt.source_instance_id,
                'source_sequence': receipt.sequence, 'step_index': receipt.step_index,
                'transition_id': receipt.transition_id, 'publisher_instance_id': self._publisher_instance_id,
                'publish_sequence': self._final_publish_sequence,
                'identity': [receipt.episode_generation, receipt.reset_epoch, receipt.runtime_generation]}
            self._emit('FINAL_PUBLISHED', record)
            if not is_safe_stop:
                self._emit('policy_final_published', record)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = FinalTwistPublisherNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
