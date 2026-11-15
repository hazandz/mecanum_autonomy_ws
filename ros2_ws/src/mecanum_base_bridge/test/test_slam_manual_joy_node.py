from types import MethodType, SimpleNamespace

from builtin_interfaces.msg import Time
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Joy

from mecanum_base_bridge.slam_manual_joy import (
    CMD_VEL_TOPIC, SlamManualJoyNode, _reliable_volatile,
)
from mecanum_base_bridge.slam_manual_teleop import (
    BodyCommand, SlamBenchMotionProfile, SlamManualTeleop,
)


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


def _profile():
    return SlamBenchMotionProfile(
        wheel_diameter_m=.097, wheelbase_m=.216, track_m=.190,
        ticks_per_wheel_revolution=937.2,
        motor_to_gearbox_output_ratio=21.3,
        wheel_rpm_per_gearbox_output_rpm=1.0,
        experimental_max_wheel_target_cps=1400.0,
    )


def _adapter(now_ns=10_000_000_000, steady=1.0):
    adapter = SimpleNamespace(
        _last_joy_received=None,
        _last_timeout_stop=object(),
        _steady=lambda: steady,
        _joy_timeout=0.25,
        _teleop=SlamManualTeleop(_profile(), motion_enabled=False),
        _cmd_pub=_Publisher(),
        _manual_valid=True,
        _publisher_conflict=False,
        _conflict_stop_published=False,
        get_logger=lambda: _Logger(),
        _has_unexpected_cmd_vel_publisher=lambda: False,
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


def _joy(axes, buttons=None, stamp=10):
    message = Joy()
    message.header.stamp = Time(sec=stamp)
    message.header.frame_id = "joy"
    message.axes = list(axes)
    message.buttons = [0] * 6 if buttons is None else list(buttons)
    return message


def test_manual_joy_publishes_only_zero_before_explicit_enable_and_neutral_sample():
    adapter = _adapter()
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 1.0]))
    assert adapter._cmd_pub.messages[-1] == Twist()

    request = SimpleNamespace()
    response = SimpleNamespace(success=False, message="")
    adapter._manual_valid = True
    adapter._has_unexpected_cmd_vel_publisher = lambda: False
    assert SlamManualJoyNode._on_enable(adapter, request, response).success
    assert response.message == "WAITING_FOR_FRESH_NEUTRAL_JOY"

    # A deflected stick cannot arm. Neutral acknowledges; next valid sample moves.
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 1.0]))
    assert adapter._cmd_pub.messages[-1] == Twist()
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 0.0]))
    assert adapter._cmd_pub.messages[-1] == Twist()
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 1.0]))
    assert adapter._cmd_pub.messages[-1].linear.x > 0.0
    assert CMD_VEL_TOPIC == "/cmd_vel"


def test_invalid_stale_joy_and_timeout_disarm_without_auto_resume():
    adapter = _adapter(steady=2.0)
    adapter._teleop.request_enable()
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 0.0]))
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 1.0]))
    assert adapter._cmd_pub.messages[-1].linear.x > 0.0

    invalid = _joy([float("nan"), 0.0])
    SlamManualJoyNode._on_joy(adapter, invalid)
    assert adapter._cmd_pub.messages[-1] == Twist()
    assert adapter._teleop.update([0.0, 1.0], [0] * 6) == BodyCommand()

    adapter._last_joy_received = 1.0
    adapter._steady = lambda: 2.0
    SlamManualJoyNode._watchdog_tick(adapter)
    assert adapter._cmd_pub.messages[-1] == Twist()
    # Fresh non-neutral Joy remains zero after timeout until explicit re-enable.
    adapter._steady = lambda: 2.01
    SlamManualJoyNode._on_joy(adapter, _joy([0.0, 1.0]))
    assert adapter._cmd_pub.messages[-1] == Twist()


def test_detected_extra_cmd_vel_publisher_disarms_and_reports_conflict():
    adapter = _adapter(steady=2.0)
    logger = _Logger()
    adapter.get_logger = lambda: logger
    adapter._has_unexpected_cmd_vel_publisher = lambda: True
    SlamManualJoyNode._watchdog_tick(adapter)
    assert adapter._publisher_conflict
    assert adapter._cmd_pub.messages[-1] == Twist()
    assert logger.errors


def test_manual_node_source_has_single_cmd_vel_route_and_no_session_owner():
    import inspect
    from mecanum_base_bridge import slam_manual_joy

    source = inspect.getsource(slam_manual_joy)
    assert '"/cmd_vel"' in source
    assert '"/cmd_vel_teleop_raw"' not in source
    assert "BridgeSession" not in source
    assert '"/manual_slam/enable"' in source
    assert '"/manual_slam/disarm"' in source


def test_cmd_vel_qos_is_reliable_volatile_and_depth_one():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy

    qos = _reliable_volatile(1)
    assert qos.history == HistoryPolicy.KEEP_LAST
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.durability == DurabilityPolicy.VOLATILE
    assert qos.depth == 1


def test_valid_joy_accepts_common_controllers_with_additional_buttons():
    assert SlamManualJoyNode._valid_joy(_joy([0.0, 0.0], [0] * 11))


def test_slam_manual_joy_node_constructs_with_real_jazzy_rclpy_and_builtin_clock_parameter():
    import rclpy
    from pathlib import Path

    manifest = Path(__file__).resolve().parents[4] / (
        "artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/"
        "hardware_manifest_slam_manual_bench.yaml"
    )
    rclpy.init(args=[
        "slam-manual-joy-test", "--ros-args",
        "-p", "control_mode:=MANUAL_SLAM",
        "-p", "manual_slam_selected:=true",
        "-p", f"hardware_manifest:={manifest}",
    ])
    node = None
    try:
        node = SlamManualJoyNode()
        assert node.get_name() == "slam_manual_joy"
        assert node.has_parameter("use_sim_time")
        assert node.get_parameter("use_sim_time").value is False
        assert node._manual_slam_selected
        assert node._profile_valid and node._manual_valid
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
