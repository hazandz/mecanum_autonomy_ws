"""Injected reset service tests; never create ROS context or service client."""
from mecanum_nav_rl.simulation.local_training_reset import (
    LocalTrainingResetAdapter,
    ResetMeasurement,
    ResetTarget,
    RosGazeboResetServices,
)

import pytest


def _measurement(iteration=1, stamp=0):
    return ResetMeasurement(
        iteration, stamp, 0, 0, 0.10, 0, 0, 0,
        (0, 0, 0), (0, 0, 0), True, False, True,
    )


class Services:
    """Capture reset service requests without ROS clients."""

    def __init__(self):
        """Initialize the call record."""
        self.calls = []

    def control_world(self, **kwargs):
        """Record a world control request and acknowledge it."""
        self.calls.append(('control', kwargs))
        return True

    def set_entity_pose(self, **kwargs):
        """Record a pose request and acknowledge it."""
        self.calls.append(('pose', kwargs))
        return True


def _samples():
    return [_measurement(i, (i - 1) * 10_000_000) for i in range(1, 22)]


def test_reset_requires_actual_zero_and_measured_3d_standstill():
    """Reset needs a selected zero receipt and measured 3D standstill."""
    services = Services()
    now = [0.0]
    adapter = LocalTrainingResetAdapter(
        services, lambda pause, timeout: True,
        lambda: _measurement(30, 300_000_000), sleep=lambda _: None,
        monotonic=lambda: now[0],
    )
    with pytest.raises(ValueError, match='applied zero receipt'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
            zero_receipt_applied=False,
            reset_emulator_and_buffers=lambda: None,
        )
    with pytest.raises(ValueError, match='21'):
        LocalTrainingResetAdapter.validate_standstill_window(_samples()[:20])


def test_set_pose_ack_is_followed_by_measurement_and_exact_model_name():
    """Pose acknowledgment is followed by measurement of the named model."""
    services = Services()
    reset = []
    adapter = LocalTrainingResetAdapter(
        services, lambda pause, timeout: True,
        lambda: _measurement(30, 300_000_000), sleep=lambda _: None,
        monotonic=lambda: 0.0,
    )
    facts = adapter.execute(
        target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
        zero_receipt_applied=True,
        reset_emulator_and_buffers=lambda: reset.append(True),
    )
    assert facts.set_pose_acknowledged and facts.measured_target_valid
    assert reset == [True]
    pose_call = next(
        kwargs for kind, kwargs in services.calls if kind == 'pose'
    )
    assert pose_call['world_name'] == 'b2_training_arena'
    assert pose_call['entity_name'] == 'mecanum_b2'


def test_invalid_post_ack_measurement_fails_closed():
    """Invalid post-ack pose measurements fail closed."""
    adapter = LocalTrainingResetAdapter(
        Services(), lambda pause, timeout: True,
        lambda: _measurement(30, 300_000_000).__class__(
            30, 300_000_000, 0.1, 0, 0.1, 0, 0, 0,
            (0, 0, 0), (0, 0, 0),
            True, False, True,
        ),
        sleep=lambda _: None, monotonic=lambda: 0.0,
    )
    with pytest.raises(ValueError, match='XY'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
            zero_receipt_applied=True,
            reset_emulator_and_buffers=lambda: None,
        )


def test_ros_service_adapter_uses_jazzy_endpoints_and_exact_model_name():
    """Gazebo service adapters use the bound endpoints and model name."""
    from ros_gz_interfaces.srv import ControlWorld, SetEntityPose

    class Future:
        """Return an immediately completed fake service response."""

        def __init__(self, response):
            """Store the fake service response."""
            self._response = response

        def done(self):
            """Report the fake operation as complete."""
            return True

        def result(self):
            """Return the stored response."""
            return self._response

    class Client:
        """Capture service client creation and request data."""

        def __init__(self, service_type, endpoint):
            """Store client identity and an empty request slot."""
            self.service_type = service_type
            self.endpoint = endpoint
            self.request = None

        def wait_for_service(self, timeout_sec):
            """Acknowledge only the test's one second timeout."""
            return timeout_sec == 1.0

        def call_async(self, request):
            """Capture a request and return an immediate fake future."""
            self.request = request
            return Future(self.service_type.Response(success=True))

    class Node:
        """Create and record fake service clients."""

        def __init__(self):
            """Initialize the client list."""
            self.clients = []

        def create_client(self, service_type, endpoint):
            """Create a fake client for the requested endpoint."""
            client = Client(service_type, endpoint)
            self.clients.append(client)
            return client

    node = Node()
    spin_calls = []
    services = RosGazeboResetServices(
        node, lambda passed_node, future, timeout_sec: spin_calls.append(
            (passed_node, timeout_sec),
        ),
    )
    assert services.control_world(
        world_name='b2_training_arena', pause=True, timeout_s=1.0,
    )
    assert services.set_entity_pose(
        world_name='b2_training_arena', entity_name='mecanum_b2',
        target=ResetTarget(0, 0, 0.1, 0.4), timeout_s=1.0,
    )
    assert [client.endpoint for client in node.clients] == [
        '/world/b2_training_arena/control',
        '/world/b2_training_arena/set_pose',
    ]
    assert node.clients[0].service_type is ControlWorld
    assert node.clients[0].request.world_control.pause is True
    assert node.clients[1].service_type is SetEntityPose
    assert node.clients[1].request.entity.name == 'mecanum_b2'
    assert node.clients[1].request.entity.id == 0
    assert node.clients[1].request.pose.orientation.z == pytest.approx(
        0.19866933079506122,
    )
    assert len(spin_calls) == 2 and all(
        item[0] is node and item[1] == 1.0 for item in spin_calls
    )
