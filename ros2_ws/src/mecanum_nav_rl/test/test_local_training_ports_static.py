"""Ground Truth is on trusted ports and absent from policy-safe output.

The test inspects port types without constructing a ROS graph.
"""
from dataclasses import fields

from mecanum_nav_rl.runtime_simulation.local_training_ports import (
    BACKEND_CONTROL_ENDPOINT,
    GroundTruthPortSample,
    LocalTrainingBackendControlPort,
    PolicySafeOdometryPort,
    SimulatedOdometryPort,
)
from mecanum_nav_rl.simulation.simulated_odometry import (
    SimulatedOdometryNoiseConfig,
)

from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl


def test_emulator_wrapper_keeps_ground_truth_out_of_policy_safe_type():
    """The policy-safe port type does not contain Ground Truth."""
    assert 'GroundTruthPortSample' not in {
        field.type for field in fields(PolicySafeOdometryPort)
    }
    port = SimulatedOdometryPort()
    port.reset(
        20261029, SimulatedOdometryNoiseConfig(0, 0, 0, 0, 0, 0, 0, 0),
    )
    result = port.accept_ground_truth(
        GroundTruthPortSample(1, 0, 0, 0, 0.1, 0.2, 0.3),
    )
    assert result.snapshot.measurement is not None
    assert not hasattr(result, 'ground_truth')
    assert result.snapshot.timestamp_ns == 1


def test_negative_profiles_keep_no_vector_and_original_stamp():
    """Delayed data retains its source stamp and has no measurement vector."""
    port = SimulatedOdometryPort()
    port.reset(
        20261030, SimulatedOdometryNoiseConfig(0, 0, 0, 0, 0, 0, 30, 0),
    )
    for stamp in range(1, 31):
        last = port.accept_ground_truth(
            GroundTruthPortSample(stamp, 0, 0, 0, 0, 0, 0),
        )
    assert last.snapshot.status.value == 'delayed'
    assert last.snapshot.measurement is None
    assert last.snapshot.timestamp_ns == 30


def test_backend_control_adapter_uses_canonical_endpoint_and_injected_client():
    """The client adapter uses an injected client at the fixed endpoint."""
    class Future:
        pass

    class Client:
        def __init__(self):
            self.request = None
            self.future = Future()

        def call_async(self, request):
            self.request = request
            return self.future

    class Node:
        def __init__(self):
            self.created = None

        def create_client(self, service_type, endpoint):
            self.created = (service_type, endpoint)
            return client

    client = Client()
    node = Node()
    port = LocalTrainingBackendControlPort.from_node(node)
    request = LocalTrainingBackendControl.Request()
    request.schema_version = request.SCHEMA_VERSION
    request.coordinator_ingress_instance_id = 17
    request.request_sequence = 1
    assert node.created == (
        LocalTrainingBackendControl, BACKEND_CONTROL_ENDPOINT,
    )
    assert port.submit(request) is client.future
    assert client.request is request
