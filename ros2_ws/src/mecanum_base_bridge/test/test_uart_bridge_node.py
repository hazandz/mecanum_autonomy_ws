from types import SimpleNamespace
import inspect

from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState

from mecanum_base_bridge.bridge_node import (HEARTBEAT_TOPIC, LIFECYCLE_TOPIC,
    ODOMETRY_TOPIC, RESET_SERVICE, UartBridgeNode, lifecycle_identity,
    lifecycle_qos_profile)


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
                            _clock=lambda: 12.5)
    twist=SimpleNamespace(linear=SimpleNamespace(x=0.1,y=-0.2),
                          angular=SimpleNamespace(z=0.3))
    UartBridgeNode._on_cmd_vel(adapter,twist)
    assert received == [(0.1,-0.2,0.3,12.5)]
    source=inspect.getsource(UartBridgeNode.destroy_node)
    assert '_session.shutdown()' in source
    shutdown=inspect.getsource(UartBridgeNode._heartbeat_tick)
    assert 'SOURCE_MCU' in shutdown
