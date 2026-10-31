"""Injected reset service tests; never create ROS context or service client."""
from dataclasses import replace

from mecanum_nav_rl.simulation.local_training_reset import (
    AppliedZeroReceiptFact,
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
        'run-1', 'a' * 64, 7, 2, 0, 3, 4,
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


def _applied_zero_fact(**overrides):
    values = {
        'session_id': 'run-1',
        'config_hash': 'a' * 64,
        'backend_instance_id': 7,
        'episode_generation': 3,
        'reset_epoch': 2,
        'runtime_generation': 4,
        'final_publisher_instance_id': 11,
        'final_publish_sequence': 8,
        'source': 4,
        'source_instance_id': 12,
        'source_sequence': 2,
        'step_index': 0,
        'transition_id': '',
        'twist': (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        'barrier_stamp_ns': 100_000_000,
        'receipt_stamp_ns': 110_000_000,
        'applied_receipt_valid': True,
        'applied_final_publisher_instance_id': 11,
        'applied_final_publish_sequence': 8,
        'applied_physics_iteration': 12,
        'applied_sim_stamp_ns': 120_000_000,
        'local_zero_override': False,
        'receive_steady_ns': 0,
    }
    values.update(overrides)
    return AppliedZeroReceiptFact(**values)


def test_reset_requires_actual_zero_and_measured_3d_standstill():
    """Reset needs a selected zero receipt and measured 3D standstill."""
    services = Services()
    now = [0.0]
    adapter = LocalTrainingResetAdapter(
        services, lambda pause, timeout: True,
        lambda: [_measurement(i, i * 10_000_000) for i in range(30, 51)],
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: now[0],
    )
    with pytest.raises(ValueError, match='applied zero receipt'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
            applied_zero_receipt=True,
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
        lambda: [_measurement(i, i * 10_000_000) for i in range(30, 51)],
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: 0.0,
    )
    facts = adapter.execute(
        target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
        applied_zero_receipt=_applied_zero_fact(),
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
        lambda: [ResetMeasurement(
            i, i * 10_000_000, 0.1, 0, 0.1, 0, 0, 0,
            (0, 0, 0), (0, 0, 0), True, False, True,
            'run-1', 'a' * 64, 7, 2, 0, 3, 4,
        ) for i in range(30, 51)],
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: 0.0,
    )
    with pytest.raises(ValueError, match='XY'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0), measured_standstill=_samples(),
            applied_zero_receipt=_applied_zero_fact(),
            reset_emulator_and_buffers=lambda: None,
        )


@pytest.mark.parametrize(
    'sample, match',
    [
        (
            replace(_measurement(1, 0), runtime_generation=5),
            'identity mismatch',
        ),
        (
            replace(_measurement(1, 0), receive_steady_ns=-1),
            'receive steady',
        ),
        (
            replace(_measurement(1, 0), linear_xyz_mps=(0.02, 0, 0)),
            'linear standstill limit',
        ),
        (
            replace(_measurement(1, 0), angular_xyz_radps=(0, 0, 0.03)),
            'angular standstill limit',
        ),
        (
            replace(_measurement(1, 0), linear_xyz_mps=(0, 0, float('inf'))),
            'complete and finite',
        ),
    ],
)
def test_reset_rejects_stale_identity_or_invalid_standstill(sample, match):
    """Standstill facts must be fresh, identity-bound and within 3D limits."""
    samples = _samples()
    samples[0] = sample
    with pytest.raises(ValueError, match=match):
        if match in {'identity mismatch', 'receive steady'}:
            adapter = LocalTrainingResetAdapter(
                Services(), lambda pause, timeout: True,
                lambda: _samples(), expected_session_id='run-1',
                expected_config_hash='a' * 64,
                expected_backend_instance_id=7, expected_reset_epoch=2,
                expected_episode_generation=3,
                expected_runtime_generation=4,
                expected_final_publisher_instance_id=11,
                expected_safe_stop_source_instance_id=12,
                expected_barrier_stamp_ns=100_000_000,
                sleep=lambda _: None, monotonic=lambda: 0.0,
            )
            adapter._validate_identity_and_freshness(
                [sample], after_steady_s=-5.0,
            )
        else:
            LocalTrainingResetAdapter.validate_standstill_window(samples)


def test_reset_rejects_large_twist_after_successful_pose_ack():
    """Pose ACK cannot substitute for measured post-resume standstill."""
    post = [
        replace(
            _measurement(i, i * 10_000_000),
            linear_xyz_mps=(0.02, 0.0, 0.0),
        )
        for i in range(30, 51)
    ]
    adapter = LocalTrainingResetAdapter(
        Services(), lambda pause, timeout: True, lambda: post,
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: 0.0,
    )
    with pytest.raises(ValueError, match='linear standstill limit'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0),
            measured_standstill=_samples(),
            applied_zero_receipt=_applied_zero_fact(),
            reset_emulator_and_buffers=lambda: None,
        )


@pytest.mark.parametrize(
    'case, match, services_called',
    [
        ('missing_pre', '21 measured 100 Hz samples', 0),
        ('wrong_backend', 'identity mismatch', 0),
        ('iteration_gap', 'missing physics iteration', 0),
        ('non_finite', 'complete and finite', 0),
        ('post_missing', '21 measured 100 Hz samples', 3),
        ('stale_steady', 'receive freshness', 3),
        ('future_steady', 'stale or future', 3),
        ('stale_ros', 'not newer than reset barrier', 3),
    ],
)
def test_execute_rejects_invalid_measurement_at_owned_boundary(
    case, match, services_called,
):
    """Reject bad measured facts through the full reset adapter entrypoint."""
    services = Services()
    now = [0.0]
    pre = _samples()
    post = [
        replace(
            _measurement(i, i * 10_000_000), receive_steady_ns=0,
        )
        for i in range(30, 51)
    ]
    if case == 'missing_pre':
        pre = []
    elif case == 'wrong_backend':
        pre[0] = replace(pre[0], backend_instance_id=8)
    elif case == 'iteration_gap':
        pre[10] = replace(pre[10], iteration=99)
    elif case == 'non_finite':
        pre[0] = replace(
            pre[0], angular_xyz_radps=(0.0, float('nan'), 0.0),
        )
    elif case in {'stale_steady', 'future_steady', 'stale_ros'}:
        if case == 'future_steady':
            post = [
                replace(sample, receive_steady_ns=600_000_000)
                for sample in post
            ]
        elif case == 'stale_ros':
            post = [
                replace(
                    sample,
                    stamp_ns=(sample.iteration - 30) * 10_000_000,
                    receive_steady_ns=500_000_000,
                )
                for sample in post
            ]
    elif case == 'post_missing':
        post = []

    def confirm_state(pause, timeout):
        if not pause:
            now[0] = 500_000_000 / 1_000_000_000
        return True

    adapter = LocalTrainingResetAdapter(
        services, confirm_state, lambda: post,
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: now[0],
    )
    with pytest.raises(ValueError, match=match):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0),
            measured_standstill=pre,
            applied_zero_receipt=_applied_zero_fact(),
            reset_emulator_and_buffers=lambda: None,
        )
    assert len(services.calls) == services_called
    assert not any(kind == 'pose' for kind, _ in services.calls) or (
        case in {
            'post_missing', 'stale_steady', 'future_steady', 'stale_ros',
        }
    )


def test_reset_total_deadline_is_checked_before_next_service_request():
    """An exhausted total deadline prevents issuing the next reset service."""
    services = Services()
    now = [0.0]

    def confirm_pause(pause, timeout):
        now[0] = 16.0
        return True

    adapter = LocalTrainingResetAdapter(
        services, confirm_pause, lambda: _samples(),
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: now[0],
    )
    with pytest.raises(TimeoutError, match='total reset deadline'):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0),
            measured_standstill=_samples(),
            applied_zero_receipt=_applied_zero_fact(),
            reset_emulator_and_buffers=lambda: None,
        )
    assert [kind for kind, _ in services.calls] == ['control']


def test_yaw_target_comparison_wraps_across_pi_boundary():
    """Yaw error uses shortest wrapped angular distance."""
    measurement = replace(_measurement(1, 0), yaw_rad=3.135)
    LocalTrainingResetAdapter.validate_target(
        measurement, ResetTarget(0, 0, 0.1, -3.135),
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
        ), monotonic=lambda: 0.0,
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


def test_late_service_future_cannot_turn_timed_out_reset_into_success():
    """A late response cannot change the adapter's bounded failure result."""
    from ros_gz_interfaces.srv import ControlWorld, SetEntityPose

    class Future:
        """Represent an incomplete future that completes after timeout."""

        def __init__(self):
            """Start without a response."""
            self.response = None

        def done(self):
            """Expose completion only after the test explicitly delivers it."""
            return self.response is not None

        def result(self):
            """Return the late response after delivery."""
            return self.response

    class Client:
        """Return one pending future from the production adapter call."""

        def __init__(self):
            """Create the pending future slot."""
            self.future = Future()

        def wait_for_service(self, timeout_sec):
            """Report discovery within the injected deadline."""
            return timeout_sec == 1.0

        def call_async(self, request):
            """Capture the request and return the pending future."""
            self.request = request
            return self.future

    class Node:
        """Provide fake clients at the ROS node boundary."""

        def __init__(self):
            """Create fake service clients and record their endpoints."""
            self.client = Client()
            self.endpoints = []

        def create_client(self, service_type, endpoint):
            """Return the client and validate the Jazzy service mapping."""
            expected = {
                ControlWorld: '/world/b2_training_arena/control',
                SetEntityPose: '/world/b2_training_arena/set_pose',
            }
            assert endpoint == expected[service_type]
            self.endpoints.append(endpoint)
            return self.client

    node = Node()
    adapter = RosGazeboResetServices(
        node, lambda passed_node, future, timeout_sec: None,
        monotonic=lambda: 0.0,
    )
    assert node.endpoints == [
        '/world/b2_training_arena/control',
        '/world/b2_training_arena/set_pose',
    ]
    result = adapter.control_world(
        world_name='b2_training_arena', pause=True, timeout_s=1.0,
    )
    assert result is False
    assert not node.client.future.done()

    node.client.future.response = ControlWorld.Response(success=True)

    assert node.client.future.done()
    assert node.client.future.result().success is True
    assert result is False


@pytest.mark.parametrize(
    'override, match',
    [
        ({'session_id': 'wrong'}, 'identity mismatch'),
        ({'backend_instance_id': 8}, 'identity mismatch'),
        ({'episode_generation': 9}, 'identity mismatch'),
        ({'runtime_generation': 9}, 'identity mismatch'),
        ({'source_instance_id': 13}, 'bound SAFE_STOP'),
        ({'final_publish_sequence': 9}, 'selected zero receipt key'),
        (
            {'applied_final_publisher_instance_id': 13},
            'selected zero receipt key',
        ),
        ({'local_zero_override': True}, 'selected zero receipt key'),
        ({'applied_receipt_valid': False}, 'selected zero receipt key'),
        ({'source': 1}, 'bound SAFE_STOP'),
        ({'step_index': 1}, 'bound SAFE_STOP'),
        ({'twist': (0.0, 0.0, float('nan'), 0.0, 0.0, 0.0)}, 'finite zero'),
        ({'barrier_stamp_ns': 110_000_000}, 'timing/barrier'),
        ({'receive_steady_ns': -1}, 'stale or future'),
    ],
)
def test_reset_rejects_unbound_or_invalid_selected_zero_facts(override, match):
    """Reject zero receipt facts missing the required bindings."""
    adapter = LocalTrainingResetAdapter(
        Services(), lambda pause, timeout: True, lambda: _samples(),
        expected_session_id='run-1', expected_config_hash='a' * 64,
        expected_backend_instance_id=7, expected_reset_epoch=2,
        expected_episode_generation=3, expected_runtime_generation=4,
        expected_final_publisher_instance_id=11,
        expected_safe_stop_source_instance_id=12,
        expected_barrier_stamp_ns=100_000_000,
        sleep=lambda _: None, monotonic=lambda: 0.0,
    )
    fact = _applied_zero_fact(**override)
    with pytest.raises(ValueError, match=match):
        adapter.execute(
            target=ResetTarget(0, 0, 0.1, 0),
            measured_standstill=_samples(),
            applied_zero_receipt=fact,
            reset_emulator_and_buffers=lambda: None,
        )
