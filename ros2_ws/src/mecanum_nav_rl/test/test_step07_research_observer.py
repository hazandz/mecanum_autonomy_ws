"""Offline boundary and production method checks for the in-process adapter."""

import ast
import inspect
import math
import sys
import threading
from collections import deque
from types import SimpleNamespace

import pytest

from mecanum_nav_rl.observations import step07_research_observer as observer_module
from mecanum_nav_rl.observations.step07_research_acceptance import Context


def test_observer_import_does_not_import_or_initialize_ros_graph():
    assert "ros2cli" not in sys.modules
    assert hasattr(observer_module, "Step07ResearchObserver")
    tree = ast.parse(open(observer_module.__file__, encoding="utf-8").read())
    top_level_ros_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
        and ((isinstance(node, ast.Import) and any(alias.name.startswith("rclpy") for alias in node.names))
             or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rclpy")))]
    assert top_level_ros_imports == []


def test_observer_has_no_collector_process_or_file_ipc_protocol():
    source = open(observer_module.__file__, encoding="utf-8").read()
    assert "subprocess" not in source
    assert "ros2cli" not in source
    assert "ACK/RELEASE" not in source
    assert 'lookup_transform("base_link", "map", stamp' in source
    assert "ClockType.ROS_TIME" in source


def test_observer_admission_context_is_static_config_plus_real_lifecycle_identity():
    context = Context(5, 2, 3, "f" * 64)
    assert context == Context(5, 2, 3, "f" * 64)
    assert context != Context(5, 2, 4, "f" * 64)


def _install_strict_fake_ros(monkeypatch, *, fail_subscription_at=None):
    """Install fakes whose subscription API rejects unapproved keywords."""
    from types import ModuleType
    from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

    created = {}

    class FakeSubscription:
        def __init__(self, **values):
            self.__dict__.update(values)

    class FakeNode:
        def __init__(self, name, *, parameter_overrides):
            self.name = name
            self.destroyed = False
            self.subscriptions = []
            self.subscription_calls = 0
            created['node'] = self

        def set_parameters(self, parameters):
            return [SimpleNamespace(successful=True) for _ in parameters]

        def create_subscription(self, msg_type, topic, callback, qos_profile,
                                *, callback_group=None):
            self.subscription_calls += 1
            if self.subscription_calls == fail_subscription_at:
                raise RuntimeError('strict fake subscription failure')
            entity = FakeSubscription(
                msg_type=msg_type,
                topic=topic,
                callback=callback,
                qos_profile=qos_profile,
                callback_group=callback_group,
            )
            self.subscriptions.append(entity)
            return entity

        def create_client(self, srv_type, name):
            return SimpleNamespace(service_type=srv_type, name=name)

        def destroy_node(self):
            self.destroyed = True

    class FakeQoS:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def module(name, **attrs):
        value = ModuleType(name)
        value.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, value)
        return value

    module(
        'rclpy',
        parameter=SimpleNamespace(Parameter=lambda *a, **k: (a, k)),
        clock=SimpleNamespace(
            ClockType=SimpleNamespace(ROS_TIME=1, STEADY_TIME=2)
        ),
    )
    module('rclpy.callback_groups',
           MutuallyExclusiveCallbackGroup=MutuallyExclusiveCallbackGroup)
    module('rclpy.action', ActionClient=lambda *a, **k: SimpleNamespace())
    module(
        'rclpy.duration',
        Duration=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    module('rclpy.node', Node=FakeNode)
    module('rclpy.qos', QoSProfile=FakeQoS,
           DurabilityPolicy=SimpleNamespace(VOLATILE=1, TRANSIENT_LOCAL=2),
           HistoryPolicy=SimpleNamespace(KEEP_LAST=1),
           ReliabilityPolicy=SimpleNamespace(BEST_EFFORT=1, RELIABLE=2))
    for package, submodule, names in (
        ('sensor_msgs', 'msg', ('LaserScan', 'Imu')),
        ('nav_msgs', 'msg', ('Odometry', 'Path', 'OccupancyGrid')),
        ('tf2_msgs', 'msg', ('TFMessage',)),
        ('geometry_msgs', 'msg', ('PoseWithCovarianceStamped', 'Twist')),
        ('rosgraph_msgs', 'msg', ('Clock',)),
        ('nav2_msgs', 'action', ('ComputePathToPose', 'NavigateToPose')),
        (
            'mecanum_nav_rl_interfaces', 'msg',
            (
                'SafetyLifecycleState', 'FinalIssuedCommandReceipt',
                'CommandEnvelope', 'SafetyState',
            ),
        ),
        ('std_srvs', 'srv', ('Trigger',)),
        ('lifecycle_msgs', 'srv', ('GetState',)),
    ):
        parent = module(package)
        child = module(
            f'{package}.{submodule}',
            **{name: type(name, (), {}) for name in names},
        )
        setattr(parent, submodule, child)
    module('tf2_ros', Buffer=lambda **kwargs: SimpleNamespace(),
           TransformListener=lambda *a, **k: SimpleNamespace())
    return created


def test_observer_constructor_uses_jazzy_callback_and_cleans_node(monkeypatch):
    """Use strict fake subscriptions and verify constructor rollback."""
    from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

    created = _install_strict_fake_ros(monkeypatch)
    observer = observer_module.Step07ResearchObserver(config_hash='c' * 64)
    node = created['node']
    assert observer._amcl_yaw_covariance_roundoff_tolerance_rad2 is None
    by_topic = {item.topic: item.callback for item in node.subscriptions}
    by_subscription = {item.topic: item for item in node.subscriptions}
    assert (by_subscription['/odometry/filtered'].callback_group
            is observer._filtered_odometry_callback_group)
    assert isinstance(observer._filtered_odometry_callback_group,
                      MutuallyExclusiveCallbackGroup)
    assert all(item.callback_group is None for item in node.subscriptions
               if item.topic != '/odometry/filtered')
    assert len(inspect.signature(by_topic['/tf']).parameters) == 2
    assert len(inspect.signature(by_topic['/tf_static']).parameters) == 2

    failed = _install_strict_fake_ros(monkeypatch, fail_subscription_at=2)
    try:
        observer_module.Step07ResearchObserver(config_hash='c' * 64)
    except RuntimeError as error:
        assert str(error) == 'strict fake subscription failure'
    else:
        raise AssertionError(
            'strict create_subscription accepted an invalid API keyword'
        )
    assert failed['node'].destroyed is True


def test_filtered_odometry_group_isolated_and_mutually_exclusive(monkeypatch):
    """Exercise Jazzy group admission directly without initializing ROS."""
    from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

    created = _install_strict_fake_ros(monkeypatch)
    observer = observer_module.Step07ResearchObserver(config_hash='c' * 64)
    filtered = next(item for item in created['node'].subscriptions
                    if item.topic == '/odometry/filtered')
    default_group = MutuallyExclusiveCallbackGroup()

    class Entity:
        pass

    default_entity = Entity()
    odom_sibling = Entity()
    default_group.add_entity(default_entity)
    default_group.add_entity(filtered)

    # Baseline coupling: a busy default group excludes its other callback.
    assert default_group.beginning_execution(default_entity)
    assert not default_group.beginning_execution(filtered)
    default_group.ending_execution(default_entity)

    # The filtered callback has a distinct group and can be admitted while
    # the node's default group remains occupied.
    odom_group = filtered.callback_group
    assert odom_group is not default_group
    odom_group.add_entity(filtered)
    odom_group.add_entity(odom_sibling)
    assert default_group.beginning_execution(default_entity)
    assert odom_group.beginning_execution(filtered)

    # Mutually exclusive semantics still block concurrent work in this group.
    assert not odom_group.beginning_execution(odom_sibling)
    odom_group.ending_execution(filtered)
    assert odom_group.beginning_execution(odom_sibling)
    odom_group.ending_execution(odom_sibling)
    default_group.ending_execution(default_entity)
    assert observer._filtered_odometry_callback_group is odom_group


def _lifecycle_message(*, sec, barrier_sec, sequence=4, generation=3, epoch=2,
                       runtime=5, primary=2, barrier=2, permitted=False):
    return SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=sec, nanosec=0), frame_id="base_link"),
        barrier_stamp=SimpleNamespace(sec=barrier_sec, nanosec=0),
        sequence=sequence, episode_generation=generation, reset_epoch=epoch,
        runtime_generation=runtime, primary_state=primary, barrier_state=barrier,
        motion_permitted=permitted, reason="test",
    )


def _bare_observer():
    instance = object.__new__(observer_module.Step07ResearchObserver)
    instance._lock = threading.RLock()
    instance._config_hash = "c" * 64
    instance._steady_ns = lambda: 9_000_000_000
    instance.context = None
    instance.lifecycle = None
    instance.barrier_stamp_ns = 0
    instance.barrier_event_stamp_ns = 0
    instance.barrier_sequence = 0
    instance.action_events = []
    return instance


def test_lifecycle_callback_heartbeat_refreshes_freshness_without_new_barrier_event():
    observer = _bare_observer()
    first = _lifecycle_message(sec=10, barrier_sec=9)
    observer._lifecycle_cb(first)
    assert observer.lifecycle.value["sequence"] == 4
    assert observer.barrier_sequence == 1
    event_stamp = observer.barrier_event_stamp_ns
    for sec in (11, 12, 13):
        observer._lifecycle_cb(_lifecycle_message(sec=sec, barrier_sec=sec-1))
        assert observer.lifecycle.stamp_ns == sec * 1_000_000_000
        assert observer.barrier_event_stamp_ns == event_stamp
        assert observer.barrier_sequence == 1


def test_lifecycle_callback_tracks_rearm_generation_and_nonready_fault_events():
    observer = _bare_observer()
    observer._lifecycle_cb(_lifecycle_message(sec=10, barrier_sec=9))
    observer._lifecycle_cb(_lifecycle_message(sec=11, barrier_sec=11, sequence=5,
                                               runtime=6, barrier=1, permitted=True))
    assert observer.barrier_sequence == 2
    assert observer.lifecycle.context.runtime_generation == 6
    assert observer.lifecycle.value["barrier_state"] == 1
    observer._lifecycle_cb(_lifecycle_message(sec=12, barrier_sec=12, sequence=6,
                                               barrier=2, permitted=False))
    assert observer.barrier_sequence == 3
    observer._lifecycle_cb(_lifecycle_message(sec=13, barrier_sec=13, sequence=7,
                                               barrier=3, permitted=False))
    assert observer.barrier_sequence == 4


def _valid_odom_message():
    vector3 = lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0)
    pose = SimpleNamespace(position=vector3(), orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0))
    twist = SimpleNamespace(linear=vector3(), angular=vector3())
    return SimpleNamespace(header=SimpleNamespace(frame_id="odom"), child_frame_id="base_link",
        pose=SimpleNamespace(pose=pose, covariance=[0.0]*36),
        twist=SimpleNamespace(twist=twist, covariance=[0.0]*36))


def test_production_odometry_admission_rejects_wrong_frame_nonfinite_and_invalid_covariance():
    valid = _valid_odom_message()
    assert observer_module.Step07ResearchObserver._valid_odom(valid)
    wrong_frame = _valid_odom_message(); wrong_frame.child_frame_id = "base_footprint"
    assert not observer_module.Step07ResearchObserver._valid_odom(wrong_frame)
    invalid_value = _valid_odom_message(); invalid_value.twist.twist.linear.y = math.nan
    assert not observer_module.Step07ResearchObserver._valid_odom(invalid_value)
    invalid_covariance = _valid_odom_message(); invalid_covariance.pose.covariance[0] = -1.0
    assert not observer_module.Step07ResearchObserver._valid_odom(invalid_covariance)


def test_odom_fact_and_lifecycle_context_are_serialized_with_snapshot():
    """Pin odometry identity while lifecycle waits on the insertion lock."""
    observer = _bare_observer()
    observer.context = Context(5, 2, 3, 'c' * 64)
    observer.odometry = deque(maxlen=64)
    observer.scans = deque(maxlen=64)
    observer.wheel = deque(maxlen=64)
    observer.imu = deque(maxlen=64)
    observer.receipts = deque(maxlen=64)
    observer.localization = deque(maxlen=64)
    observer.clock_rollback = False
    observer.clock_ns = 10_000_000_000
    observer.clock_advance_count = 1
    fact_started = threading.Event()
    release_fact = threading.Event()
    lifecycle_started = threading.Event()
    lifecycle_finished = threading.Event()

    def steady_time_inside_fact():
        fact_started.set()
        assert release_fact.wait(timeout=2)
        return 9_000_000_000

    observer._steady_ns = steady_time_inside_fact
    odom_message = _valid_odom_message()
    odom_message.header.stamp = SimpleNamespace(sec=10, nanosec=0)
    odom_thread = threading.Thread(
        target=observer._odom, args=(odom_message,)
    )
    lifecycle_errors = []

    def update_lifecycle():
        lifecycle_started.set()
        try:
            observer._lifecycle_cb(_lifecycle_message(
                sec=11, barrier_sec=10, runtime=6, sequence=5,
                generation=5, permitted=True,
            ))
        except BaseException as error:
            lifecycle_errors.append(error)
        finally:
            lifecycle_finished.set()

    lifecycle_thread = threading.Thread(target=update_lifecycle)

    odom_thread.start()
    assert fact_started.wait(timeout=2)
    # _odom has captured its context and is still in _lock while constructing
    # the StampedFact; the lifecycle callback cannot mutate that identity yet.
    assert not observer._lock.acquire(blocking=False)
    lifecycle_thread.start()
    assert lifecycle_started.wait(timeout=2)
    release_fact.set()
    odom_thread.join(timeout=2)
    lifecycle_thread.join(timeout=2)

    assert not odom_thread.is_alive()
    assert not lifecycle_thread.is_alive()
    assert lifecycle_finished.is_set()
    assert lifecycle_errors == []
    snapshot = observer.sensor_health_snapshot()
    assert len(snapshot['odometry']) == 1
    assert (snapshot['odometry'][0].context
            == Context(5, 2, 3, 'c' * 64))
    assert snapshot['context'] == Context(5, 2, 6, 'c' * 64)
    assert snapshot['lifecycle'].context == snapshot['context']


def test_amcl_callback_does_not_admit_nonfinite_pose_or_invalid_quaternion():
    observer = object.__new__(observer_module.Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer._steady_ns = lambda: 100
    observer.localization = deque(maxlen=64)
    observer.context = Context(5, 2, 3, 'c' * 64)
    message = SimpleNamespace(header=SimpleNamespace(frame_id="map",
        stamp=SimpleNamespace(sec=1, nanosec=0)), pose=SimpleNamespace(
        pose=SimpleNamespace(position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
            orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)),
        covariance=[0.0]*36))
    observer._amcl(message)
    assert len(observer.localization) == 1
    message.pose.pose.orientation.w = 0.0
    observer._amcl(message)
    assert len(observer.localization) == 1
    message.pose.pose.position.x = math.inf
    observer._amcl(message)
    assert len(observer.localization) == 1


def _amcl_test_observer(*, tolerance=None):
    observer = object.__new__(observer_module.Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer._steady_ns = lambda: 100
    observer.localization = deque(maxlen=64)
    observer.context = Context(5, 2, 3, 'c' * 64)
    observer._amcl_yaw_covariance_roundoff_tolerance_rad2 = tolerance
    return observer


def _amcl_covariance_message(yaw_variance):
    covariance = [0.0] * 36
    covariance[35] = yaw_variance
    return SimpleNamespace(
        header=SimpleNamespace(frame_id='map',
                               stamp=SimpleNamespace(sec=1, nanosec=0)),
        pose=SimpleNamespace(
            pose=SimpleNamespace(
                position=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                orientation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
            ),
            covariance=covariance,
        ),
    )


@pytest.mark.parametrize('raw_yaw_variance', [
    -1e-12, math.nextafter(-1e-12, 0.0),
])
def test_amcl_yaw_roundoff_policy_is_opt_in_and_preserves_raw_message(
        raw_yaw_variance):
    """Normalize only bounded yaw roundoff without mutating the message."""
    epsilon = 1e-12
    message = _amcl_covariance_message(raw_yaw_variance)
    original = list(message.pose.covariance)
    strict = _amcl_test_observer()
    strict._amcl(message)
    assert strict.localization == deque()

    normalized = _amcl_test_observer(tolerance=epsilon)
    normalized._amcl(message)
    fact = normalized.localization[0]
    assert fact['covariance'] == (0.0, 0.0, 0.0)
    assert fact['raw_covariance'] == (0.0, 0.0, raw_yaw_variance)
    assert fact['covariance_roundoff_corrected'] is True
    assert message.pose.covariance == original


@pytest.mark.parametrize('yaw_variance', [
    math.nextafter(-1e-12, -math.inf), -1e-6, -0.01,
    math.nan, math.inf, -math.inf,
])
def test_amcl_yaw_roundoff_policy_rejects_out_of_boundary_and_nonfinite(
        yaw_variance):
    """Reject yaw variance below the bound and all nonfinite values."""
    observer = _amcl_test_observer(tolerance=1e-12)
    observer._amcl(_amcl_covariance_message(yaw_variance))
    assert len(observer.localization) == 0


@pytest.mark.parametrize('index', [0, 7])
def test_amcl_yaw_roundoff_policy_keeps_xy_covariance_strictly_nonnegative(
        index):
    """Keep X/Y covariance diagonals strict even with yaw tolerance."""
    message = _amcl_covariance_message(-1e-15)
    message.pose.covariance[index] = -1e-15
    observer = _amcl_test_observer(tolerance=1e-12)
    observer._amcl(message)
    assert len(observer.localization) == 0


@pytest.mark.parametrize('yaw_variance', [0.0, 1e-15, 0.25])
def test_amcl_yaw_roundoff_policy_preserves_nonnegative_covariance(
        yaw_variance):
    """Preserve nonnegative yaw variance without marking correction."""
    observer = _amcl_test_observer(tolerance=1e-12)
    message = _amcl_covariance_message(yaw_variance)
    observer._amcl(message)
    fact = observer.localization[0]
    assert fact['covariance'] == (0.0, 0.0, yaw_variance)
    assert fact['raw_covariance'] == (0.0, 0.0, yaw_variance)
    assert fact['covariance_roundoff_corrected'] is False


def test_amcl_roundoff_policy_still_rejects_invalid_frame_and_quaternion():
    """Keep frame and quaternion admission checks unchanged."""
    observer = _amcl_test_observer(tolerance=1e-12)
    wrong_frame = _amcl_covariance_message(-1e-15)
    wrong_frame.header.frame_id = 'odom'
    observer._amcl(wrong_frame)
    bad_quaternion = _amcl_covariance_message(-1e-15)
    bad_quaternion.pose.pose.orientation.w = 0.0
    observer._amcl(bad_quaternion)
    assert len(observer.localization) == 0


def test_constructor_rejects_unapproved_amcl_tolerance():
    """Reject arbitrary caller tolerances before constructing a ROS node."""
    with pytest.raises(
            ValueError,
            match='AMCL_YAW_COVARIANCE_ROUNDOFF_POLICY_INVALID'):
        observer_module.Step07ResearchObserver(
            config_hash='c' * 64,
            amcl_yaw_covariance_roundoff_tolerance_rad2=1e-6,
        )


def test_amcl_snapshot_pins_context_across_callback_interleaving():
    """Keep captured localization context fixed across the next callback."""
    observer = object.__new__(observer_module.Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer._steady_ns = lambda: 9_000_000_000
    observer.localization = deque(maxlen=64)
    observer.context = Context(5, 2, 3, 'c' * 64)
    observer.scans = deque()
    observer.wheel = deque()
    observer.imu = deque()
    observer.odometry = deque()
    observer.receipts = deque()
    observer.lifecycle = None
    observer.barrier_sequence = 2
    observer.barrier_stamp_ns = 10_000_000_000
    observer.clock_rollback = False
    observer.clock_ns = 12_000_000_000
    observer.clock_advance_count = 2

    def amcl_message(sec):
        return SimpleNamespace(
            header=SimpleNamespace(
                frame_id='map',
                stamp=SimpleNamespace(sec=sec, nanosec=0),
            ),
            pose=SimpleNamespace(
                pose=SimpleNamespace(
                    position=SimpleNamespace(x=1.0, y=2.0, z=0.0),
                    orientation=SimpleNamespace(
                        x=0.0, y=0.0, z=0.0, w=1.0,
                    ),
                ),
                covariance=[0.0] * 36,
            ),
        )

    observer._amcl(amcl_message(10))
    captured = observer.sensor_health_snapshot()
    observer.context = Context(6, 2, 3, 'c' * 64)
    observer._amcl(amcl_message(11))

    assert captured['localization'][0]['context'] == Context(5, 2, 3, 'c' * 64)
    assert captured['localization'][0]['stamp_ns'] == 10_000_000_000
    assert observer.localization[-1]['context'] == observer.context


def _tf_edge_observer():
    observer = object.__new__(observer_module.Step07ResearchObserver)
    observer._lock = threading.RLock()
    observer.tf_observed_edges = set()
    return observer


def _send_tf_metadata(observer, edge, *, static=False):
    transform = SimpleNamespace(
        header=SimpleNamespace(frame_id=edge[0]), child_frame_id=edge[1]
    )
    callback = observer._tf_static if static else observer._tf
    callback(SimpleNamespace(transforms=[transform]), {
        'source_timestamp': 10, 'received_timestamp': 11,
        'publication_sequence_number': 1, 'reception_sequence_number': 1,
    })


def test_tf_callback_accepts_jazzy_dictionary_metadata_without_gid():
    """Verify tf callback accepts jazzy dictionary metadata without gid."""
    observer = _tf_edge_observer()
    _send_tf_metadata(observer, ('map', 'odom'))
    assert observer.tf_observed_edges == {('map', 'odom')}


def test_tf_edge_observations_are_bounded_to_the_three_required_edges():
    """Verify tf edge observations are bounded to the three required edges."""
    observer = _tf_edge_observer()
    for edge in (('map', 'odom'), ('odom', 'base_link'),
                 ('base_link', 'lidar_frame'), ('map', 'base_link')):
        _send_tf_metadata(observer, edge)
    assert observer.tf_observed_edges == {
        ('map', 'odom'), ('odom', 'base_link'), ('base_link', 'lidar_frame')}


def test_tf_static_edge_observation_does_not_depend_on_callback_gid():
    """Verify tf static edge observation does not depend on callback gid."""
    observer = _tf_edge_observer()
    _send_tf_metadata(observer, ('base_link', 'lidar_frame'), static=True)
    assert observer.tf_observed_edges == {('base_link', 'lidar_frame')}


def test_tf_static_observation_survives_later_live_graph_discovery():
    """Verify tf static observation survives later live graph discovery."""
    observer = _tf_edge_observer()
    endpoints = {'/tf': [], '/tf_static': []}
    observer.node = SimpleNamespace(
        get_publishers_info_by_topic=lambda topic: endpoints[topic])
    _send_tf_metadata(observer, ('base_link', 'lidar_frame'), static=True)
    assert observer.tf_publisher_graph()['/tf_static'] == ()
    endpoints['/tf_static'] = [SimpleNamespace(
        node_name='robot_state_publisher', node_namespace='/',
        topic_type='tf2_msgs/msg/TFMessage')]
    assert observer.tf_publisher_graph()['/tf_static'] == ({
        'node_name': 'robot_state_publisher', 'node_namespace': '/',
        'topic_type': 'tf2_msgs/msg/TFMessage'},)
    assert observer.tf_observed_edges == {('base_link', 'lidar_frame')}
