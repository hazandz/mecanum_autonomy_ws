from types import SimpleNamespace
import importlib
import inspect
import math

import pytest
import rclpy.node

from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

from mecanum_base_bridge.bridge_node import (HEARTBEAT_TOPIC, LIFECYCLE_TOPIC,
    ODOMETRY_TOPIC, RESET_SERVICE, UartBridgeNode, lifecycle_identity,
    lifecycle_qos_profile)
from mecanum_base_bridge import bridge_node as bridge_node_module
from mecanum_base_bridge.hardware_config import HardwareConfigError


def test_existing_lifecycle_fields_map_without_synthetic_ready():
    msg = SafetyLifecycleState()
    msg.reset_epoch=0; msg.runtime_generation=4; msg.sequence=7
    msg.primary_state=SafetyLifecycleState.PRIMARY_ACTIVE
    msg.barrier_state=SafetyLifecycleState.BARRIER_NON_READY
    msg.motion_permitted=False
    identity = lifecycle_identity(msg, 10.0, 10.1)
    assert identity.reset_epoch == 0 and identity.runtime_generation == 4
    assert identity.fresh and not identity.ready
    msg.barrier_state=SafetyLifecycleState.BARRIER_READY; msg.motion_permitted=True
    assert lifecycle_identity(msg, 10.0, 10.1).ready
    assert not lifecycle_identity(msg, 10.0, 10.7).fresh
    assert LIFECYCLE_TOPIC == "/mecanum/safety_lifecycle_state"
    assert RESET_SERVICE == "/mecanum/safety/request_reset"
    init = inspect.getsource(UartBridgeNode.__init__)
    assert 'serial_device' in init and 'hardware_manifest' in init
    assert 'use_sim_time' in init and 'Reliable' not in init  # QoS uses enum constants.
    assert 'create_subscription(Twist, "/cmd_vel"' in init
    assert 'create_publisher(Twist' not in init
    source = inspect.getsource(UartBridgeNode)
    assert 'create_publisher(Odometry, ODOMETRY_TOPIC' in source
    assert 'create_timer(0.1, self._heartbeat_tick)' in source
    assert '"/mecanum/safety/rearm"' not in source
    assert ODOMETRY_TOPIC == "/wheel/odometry_raw"
    assert HEARTBEAT_TOPIC == "/mcu/heartbeat"


def test_lifecycle_qos_matches_existing_owner_and_reset_is_async_coalesced():
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy
    qos = lifecycle_qos_profile()
    assert qos.history == HistoryPolicy.KEEP_LAST and qos.depth == 10
    assert qos.reliability == ReliabilityPolicy.RELIABLE
    assert qos.durability == DurabilityPolicy.VOLATILE

    class Session:
        pending=True
        def take_owner_reset_request(self):
            was_pending=self.pending; self.pending=False; return was_pending
    class Future:
        def done(self): return False
    class Client:
        calls=0
        def service_is_ready(self): return True
        def call_async(self, request):
            assert isinstance(request, Trigger.Request)
            self.calls += 1
            return Future()
    from std_srvs.srv import Trigger
    adapter=SimpleNamespace(_session=Session(),_reset_client=Client(),_reset_future=None)
    UartBridgeNode._request_owner_reset(adapter)
    UartBridgeNode._request_owner_reset(adapter)
    assert adapter._reset_client.calls == 1


def test_twist_callback_forwards_latest_values_and_shutdown_closes_without_zero():
    received=[]
    adapter=SimpleNamespace(_session=SimpleNamespace(receive_cmd_vel=lambda *v: received.append(v)),
                            _steady_clock=lambda: 12.5)
    twist=SimpleNamespace(linear=SimpleNamespace(x=0.1,y=-0.2),
                          angular=SimpleNamespace(z=0.3))
    UartBridgeNode._on_cmd_vel(adapter,twist)
    assert received == [(0.1,-0.2,0.3,12.5)]
    source=inspect.getsource(UartBridgeNode.destroy_node)
    assert '_session.shutdown()' in source
    shutdown=inspect.getsource(UartBridgeNode._heartbeat_tick)
    assert 'SOURCE_MCU' in shutdown


class _FaithfulNodeBase:
    """Offline double for Jazzy Node's already-declared use_sim_time."""
    instances = []
    def __init__(self, name):
        type(self).instances.append(self)
        self.name = name
        self._clock = _RosClock(ros_sec=400, ros_nanosec=123)
        self.parameters = {
            "use_sim_time": SimpleNamespace(value=False),
        }
        self.overrides = {
            "serial_device": "/dev/fake-uart",
            "hardware_manifest": "/tmp/manifest.yaml",
            "heartbeat_topic": HEARTBEAT_TOPIC,
            "lifecycle_timeout_s": 0.6,
        }
        self.destroyed = False
        self.timer_count = 0
        self.timers = []
    def has_parameter(self, name):
        return name in self.parameters
    def declare_parameter(self, name, value):
        if name in self.parameters:
            raise RuntimeError(f"parameter {name} already declared by Node")
        self.parameters[name] = SimpleNamespace(value=self.overrides.get(name, value))
    def get_parameter(self, name):
        return self.parameters[name]
    def get_logger(self):
        return SimpleNamespace(error=lambda message: None)
    def create_publisher(self, *args):
        publisher = SimpleNamespace(messages=[])
        publisher.publish = publisher.messages.append
        return publisher
    def create_subscription(self, *args):
        return object()
    def create_client(self, *args):
        return SimpleNamespace(service_is_ready=lambda: True,
                               call_async=lambda request: None)
    def get_clock(self):
        return self._clock
    def create_timer(self, timer_period_sec, callback, callback_group=None, clock=None):
        self.timer_count += 1
        selected_clock = self._clock if clock is None else clock
        if selected_clock is not self._clock:
            raise AssertionError("timer must use the Node-owned ROS clock")
        self.timers.append((timer_period_sec, callback, selected_clock))
        if getattr(type(self), "fail_timer", False):
            raise RuntimeError("offline timer initialization failure")
        return object()
    def destroy_node(self):
        self.destroyed = True
        return True


class _RosClock:
    """Offline ROS-clock double; deliberately differs from steady time."""
    def __init__(self, ros_sec, ros_nanosec):
        self.ros_sec = ros_sec
        self.ros_nanosec = ros_nanosec
    def now(self):
        from builtin_interfaces.msg import Time
        stamp = Time(sec=self.ros_sec, nanosec=self.ros_nanosec)
        return SimpleNamespace(to_msg=lambda: stamp)


class _SteadyClock:
    def __init__(self, value): self.value = value
    def __call__(self): return self.value


def _patch_constructor_dependencies(monkeypatch):
    made = {"transports": [], "sessions": []}
    class Transport:
        def __init__(self, port):
            self.port = port
            self.open_calls = 0
            made["transports"].append(self)
        def open(self):
            self.open_calls += 1
            return True
        def close(self):
            pass
    class Session:
        def __init__(self, transport, digest, monotonic):
            self.transport = transport
            self.monotonic = monotonic
            self.shutdown_calls = 0
            from mecanum_base_bridge.bridge_session import LifecycleIdentity, SessionState
            self.state = SessionState.ACTIVE
            self._identity = LifecycleIdentity(7, 0, True, 3, True)
            self.transport_healthy = False
            self.received_commands = []
            self.observed_identities = []
            self.reports = []
            self.continuity_reset = False
            made["sessions"].append(self)
        def shutdown(self):
            self.shutdown_calls += 1
        def receive_cmd_vel(self, *values): self.received_commands.append(values)
        def observe_lifecycle_snapshot(self, identity): self.observed_identities.append(identity)
        def take_owner_reset_request(self): return False
        def io_once(self): pass
        def take_accepted_telemetry(self):
            return self.reports.pop(0) if self.reports else None
    monkeypatch.setattr(rclpy.node, "Node", _FaithfulNodeBase)
    module = importlib.reload(bridge_node_module)
    monkeypatch.setattr(module, "SerialTransport", Transport)
    monkeypatch.setattr(module, "BridgeSession", Session)
    monkeypatch.setattr(module, "load_manifest", lambda path: {"fixture": True})
    monkeypatch.setattr(module, "communication_config_valid", lambda manifest: True)
    monkeypatch.setattr(module, "manifest_digest", lambda manifest: bytes(32))
    monkeypatch.setattr(module, "wheel_geometry", lambda manifest: {
        "wheel_diameter_m": 0.097, "wheelbase_m": 0.216, "track_m": 0.190,
        "ticks_per_wheel_revolution": 937.2, "encoder_tick_signs": (1, 1, 1, 1)})
    steady = _SteadyClock(100.0)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=steady))
    return made, module, steady


def test_constructor_initializes_with_existing_sim_time_and_no_serial_open(monkeypatch):
    made, module, steady = _patch_constructor_dependencies(monkeypatch)
    # Node đã sở hữu use_sim_time; override của adapter được nhận khi khai báo.
    node = module.UartBridgeNode()
    assert node.get_parameter("use_sim_time").value is False
    assert node.get_clock() is node._clock
    assert node._clock is not steady
    assert node._steady_clock is steady
    assert made["transports"][0].port == "/dev/fake-uart"
    assert made["transports"][0].open_calls == 0
    assert made["sessions"][0].monotonic is steady
    assert [timer[0] for timer in node.timers] == [0.005, 0.1]
    assert all(timer[2] is node.get_clock() for timer in node.timers)
    node.destroy_node()


def test_adapter_keeps_ros_clock_for_messages_and_steady_clock_for_freshness(monkeypatch):
    made, module, steady = _patch_constructor_dependencies(monkeypatch)
    node = module.UartBridgeNode()
    session = made["sessions"][0]
    session.transport_healthy = True
    session.reports = [
        SimpleNamespace(packet=SimpleNamespace(
            mcu_boot_id=44, reset_epoch=7, telemetry_sequence=4,
            mcu_monotonic_time_us=1_000_000, ticks_fl=0, ticks_fr=0,
            ticks_rl=0, ticks_rr=0, mcu_fault_bits=0, estop_aux_active=0),
            pi_receive_time=99.95),
        SimpleNamespace(packet=SimpleNamespace(
            mcu_boot_id=44, reset_epoch=7, telemetry_sequence=5,
            mcu_monotonic_time_us=1_020_000, ticks_fl=10, ticks_fr=10,
            ticks_rl=10, ticks_rr=10, mcu_fault_bits=0, estop_aux_active=0),
            pi_receive_time=99.95),
    ]

    from geometry_msgs.msg import Twist
    twist = Twist()
    twist.linear.x = 0.1
    twist.linear.y = -0.2
    twist.angular.z = 0.3
    node._on_cmd_vel(twist)
    assert session.received_commands[-1] == (0.1, -0.2, 0.3, 100.0)

    owner = SafetyLifecycleState()
    owner.reset_epoch = 7
    owner.runtime_generation = 0
    owner.sequence = 9
    owner.primary_state = SafetyLifecycleState.PRIMARY_ACTIVE
    owner.barrier_state = SafetyLifecycleState.BARRIER_READY
    owner.motion_permitted = True
    node._on_lifecycle(owner)
    assert node._owner_received_at == steady()
    node._io_tick()

    odometry = node._odom_pub.messages[-1]
    assert (odometry.header.stamp.sec, odometry.header.stamp.nanosec) == (400, 123)
    assert session.observed_identities[-1].fresh
    assert node._latest_report.pi_receive_time == 99.95

    node._heartbeat_tick()
    heartbeat = node._heartbeat_pub.messages[-1]
    assert (heartbeat.header.stamp.sec, heartbeat.header.stamp.nanosec) == (400, 123)
    assert heartbeat.healthy
    node.destroy_node()


def test_constructor_rejects_sim_time_true_and_cleans_node(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    original = _FaithfulNodeBase.__init__
    def init_with_sim_time(self, name):
        original(self, name)
        self.parameters["use_sim_time"] = SimpleNamespace(value=True)
    monkeypatch.setattr(_FaithfulNodeBase, "__init__", init_with_sim_time)
    before = len(_FaithfulNodeBase.instances)
    with pytest.raises(ValueError, match="use_sim_time=false"):
        module.UartBridgeNode()
    assert made["transports"] == []
    assert _FaithfulNodeBase.instances[before].destroyed


def test_constructor_fails_closed_before_transport_when_signs_missing(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    monkeypatch.setattr(module, "wheel_geometry",
                        lambda manifest: (_ for _ in ()).throw(
                            HardwareConfigError("encoder signs are unresolved")))
    with pytest.raises(HardwareConfigError, match="signs"):
        module.UartBridgeNode()
    assert made["transports"] == [] and made["sessions"] == []


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0.0, -0.1])
def test_constructor_rejects_nonpositive_or_nonfinite_lifecycle_timeout(monkeypatch, timeout):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    original = _FaithfulNodeBase.__init__
    def init_with_timeout(self, name):
        original(self, name)
        self.overrides["lifecycle_timeout_s"] = timeout
    monkeypatch.setattr(_FaithfulNodeBase, "__init__", init_with_timeout)
    with pytest.raises(ValueError, match="lifecycle_timeout_s"):
        module.UartBridgeNode()
    assert made["transports"] == [] and made["sessions"] == []


def test_constructor_failure_cleans_session_and_node(monkeypatch):
    made, module, _ = _patch_constructor_dependencies(monkeypatch)
    monkeypatch.setattr(_FaithfulNodeBase, "fail_timer", True, raising=False)
    before = len(_FaithfulNodeBase.instances)
    with pytest.raises(RuntimeError, match="timer initialization"):
        module.UartBridgeNode()
    assert made["sessions"][0].shutdown_calls == 1
    assert made["transports"][0].open_calls == 0
    assert _FaithfulNodeBase.instances[before].destroyed
