from types import MethodType, SimpleNamespace

from builtin_interfaces.msg import Time
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist

from mecanum_base_bridge.slam_manual_joy import (
    JOY_RAW_TOPIC,
    SlamManualJoyNode,
    _reliable_volatile,
)
from mecanum_base_bridge.slam_manual_teleop import BodyCommand


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Teleop:
    def __init__(self):
        self.disconnects = 0

    def disconnected(self):
        self.disconnects += 1

    def update(self, _axes, _buttons):
        return BodyCommand()


def _adapter(now_ns=10_000_000_000, steady=1.0):
    adapter = SimpleNamespace(
        _last_joy_received=None,
        _last_timeout_stop=None,
        _steady=lambda: steady,
        _joy_timeout=0.25,
        _teleop=_Teleop(),
        _raw_pub=_Publisher(),
    )
    adapter.get_clock = lambda: SimpleNamespace(
        now=lambda: SimpleNamespace(
            nanoseconds=now_ns,
            to_msg=lambda: Time(sec=10, nanosec=0),
        ),
    )
    adapter._stamp_ns = SlamManualJoyNode._stamp_ns
    adapter._valid_joy = SlamManualJoyNode._valid_joy
    adapter._publish = MethodType(SlamManualJoyNode._publish, adapter)
    return adapter


def test_joy_node_publishes_raw_zero_without_motion_enable():
    adapter = _adapter()
    message = Joy()
    message.header.stamp = Time(sec=10)
    message.header.frame_id = "joy"
    message.axes = [0.0, -1.0]
    message.buttons = [0] * 6

    SlamManualJoyNode._on_joy(adapter, message)

    assert len(adapter._raw_pub.messages) == 1
    raw = adapter._raw_pub.messages[0]
    assert (raw.linear.x, raw.linear.y, raw.angular.z) == (0.0, 0.0, 0.0)
    assert JOY_RAW_TOPIC == "/cmd_vel_teleop_raw"


def test_invalid_or_stale_joy_resets_mapper_and_emits_raw_zero():
    adapter = _adapter()
    invalid = Joy()
    invalid.header.stamp = Time(sec=10)
    invalid.axes = [float("nan"), 0.0]
    invalid.buttons = [0] * 6

    SlamManualJoyNode._on_joy(adapter, invalid)

    assert adapter._teleop.disconnects == 1
    assert adapter._raw_pub.messages[-1] == Twist()

    stale = Joy()
    stale.header.stamp = Time(sec=9)
    stale.axes = [0.0, 0.0]
    stale.buttons = [0] * 6
    SlamManualJoyNode._on_joy(adapter, stale)
    assert adapter._teleop.disconnects == 2
    assert len(adapter._raw_pub.messages) == 2


def test_joy_timeout_emits_one_raw_zero_and_does_not_touch_session():
    adapter = _adapter(steady=2.0)
    adapter._last_joy_received = 1.0

    SlamManualJoyNode._watchdog_tick(adapter)
    SlamManualJoyNode._watchdog_tick(adapter)

    assert adapter._teleop.disconnects == 1
    assert len(adapter._raw_pub.messages) == 1
    assert adapter._raw_pub.messages[0] == Twist()


def test_raw_topic_qos_is_reliable_volatile_and_mapper_has_no_final_output():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy
    import inspect

    raw_qos = _reliable_volatile(1)
    assert raw_qos.history == HistoryPolicy.KEEP_LAST
    assert raw_qos.reliability == ReliabilityPolicy.RELIABLE
    assert raw_qos.durability == DurabilityPolicy.VOLATILE
    assert raw_qos.depth == 1
    from mecanum_base_bridge import slam_manual_joy
    source = inspect.getsource(slam_manual_joy)
    assert '"/cmd_vel"' not in source
    assert '"/cmd_vel_teleop_raw"' in source
    assert "SlamManualTeleop(profile, motion_enabled=False)" in source
