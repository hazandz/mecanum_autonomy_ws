from types import MethodType, SimpleNamespace

from geometry_msgs.msg import Twist
from mecanum_nav_rl_interfaces.msg import CommandEnvelope, SafetyLifecycleState

from mecanum_nav_rl.runtime_safety.teleop_command_adapter_node import (
    CANDIDATE_TOPIC,
    RAW_TOPIC,
    TeleopCommandAdapterNode,
    _qos,
)


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


def _adapter(mode="", steady=5.0):
    value = SimpleNamespace(
        _navigation_mode=mode,
        _source_instance_id=123,
        _sequence=0,
        _steady=lambda: steady,
        _lifecycle=None,
        _lifecycle_received_s=None,
        _publisher=_Publisher(),
    )
    value.get_clock = lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(to_msg=lambda: SimpleNamespace(sec=10, nanosec=0)))
    value._ready_identity = MethodType(TeleopCommandAdapterNode._ready_identity, value)
    value._publish = MethodType(TeleopCommandAdapterNode._publish, value)
    return value


def test_missing_lifecycle_never_mints_teleop_envelope_or_ready_identity():
    adapter = _adapter(mode="MAPPING")
    raw = Twist()
    raw.linear.x = 0.1

    TeleopCommandAdapterNode._on_raw(adapter, raw)

    envelope = adapter._publisher.messages[-1]
    assert envelope.source == CommandEnvelope.SOURCE_SAFE_STOP
    assert envelope.header.frame_id == "base_link"
    assert envelope.source_instance_id == 123 and envelope.sequence == 1
    assert (envelope.episode_generation, envelope.reset_epoch,
            envelope.runtime_generation) == (0, 0, 0)
    assert (envelope.twist.linear.x, envelope.twist.linear.y,
            envelope.twist.angular.z) == (0.0, 0.0, 0.0)


def test_nonfinite_input_and_wrong_mode_fail_to_safe_stop():
    adapter = _adapter(mode="NAV2")
    raw = Twist()
    raw.linear.x = float("nan")

    TeleopCommandAdapterNode._on_raw(adapter, raw)

    assert adapter._publisher.messages[-1].source == CommandEnvelope.SOURCE_SAFE_STOP
    assert adapter._publisher.messages[-1].twist == Twist()


def test_raw_candidate_topic_and_qos_are_explicit_and_no_final_publisher_exists():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy
    import inspect

    raw_qos, envelope_qos = _qos(1), _qos(10)
    for qos in (raw_qos, envelope_qos):
        assert qos.history == HistoryPolicy.KEEP_LAST
        assert qos.reliability == ReliabilityPolicy.RELIABLE
        assert qos.durability == DurabilityPolicy.VOLATILE
    assert raw_qos.depth == 1 and envelope_qos.depth == 10
    import mecanum_nav_rl.runtime_safety.teleop_command_adapter_node as module
    source = inspect.getsource(module)
    assert RAW_TOPIC == "/cmd_vel_teleop_raw"
    assert CANDIDATE_TOPIC == "/mecanum/cmd_teleop"
    assert '"/cmd_vel"' not in source
    assert '"/mecanum/safety_accepted_cmd"' not in source
