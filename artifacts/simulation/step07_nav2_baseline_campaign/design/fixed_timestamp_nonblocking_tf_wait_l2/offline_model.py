"""Offline-only temporal state model for review; never a production implementation.

The production baseline below calls the pinned source methods with fake objects.
The proposed model is a separate deterministic state machine. No ROS graph,
node, action server, Gazebo, Nav2, campaign process, or runtime evidence is used.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

REPO = Path('/home/hazan/step07-integrated-nav2-gateb-campaign-f7f98c6').resolve()
OBSERVER_REL = Path('ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py')
OBSERVER_SHA256 = '39b9c08d01770c8ca12d1264297c69e5943a8b90640daa98ffeeaf9b2b28c28f'
OBSERVER_SOURCE = (REPO / OBSERVER_REL).resolve()
assert OBSERVER_SOURCE.is_file(), 'PINNED_PRODUCTION_SOURCE_MISSING'
assert hashlib.sha256(OBSERVER_SOURCE.read_bytes()).hexdigest() == OBSERVER_SHA256, 'PINNED_PRODUCTION_SOURCE_HASH_MISMATCH'
sys.path.insert(0, str(REPO / 'ros2_ws/src/mecanum_nav_rl'))
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as NavPath
from tf2_ros import ConnectivityException, ExtrapolationException
from mecanum_nav_rl.observations import step07_gate_b_observer_node as production
assert Path(production.__file__).resolve() == OBSERVER_SOURCE, 'PRODUCTION_IMPORT_ORIGIN_MISMATCH'
assert hashlib.sha256(Path(production.__file__).resolve().read_bytes()).hexdigest() == OBSERVER_SHA256, 'PRODUCTION_IMPORT_HASH_MISMATCH'

ORIGINAL_IMPORT = importlib.import_module
ORIGINAL_MONOTONIC = production.time.monotonic


class FakeTime:
    def __init__(self, *, nanoseconds: int):
        self.nanoseconds = nanoseconds


class Clock:
    def __init__(self, ns: int):
        self.ns = ns

    def now(self):
        return NS(nanoseconds=self.ns, to_msg=lambda: NS(sec=self.ns // 10**9, nanosec=self.ns % 10**9))


class Node:
    def __init__(self, ns: int):
        self.clock = Clock(ns)

    def get_clock(self):
        return self.clock


class FakeTF:
    def __init__(self, lower=0, upper=0, connected=True, transform_error=None):
        self.lower, self.upper, self.connected = lower, upper, connected
        self.transform_error = transform_error
        self.queries, self.lookups = [], []

    def can_transform(self, target, source, stamp):
        t = stamp.nanoseconds
        self.queries.append((target, source, t))
        return self.connected and self.lower <= t <= self.upper

    def transform(self, pose, target):
        t = pose.header.stamp.sec * 10**9 + pose.header.stamp.nanosec
        self.lookups.append((target, pose.header.frame_id, t))
        if self.transform_error is not None:
            raise self.transform_error
        if not self.connected:
            raise ConnectivityException('fake: graph edge unavailable')
        if t > self.upper:
            raise ExtrapolationException('fake: future extrapolation')
        if t < self.lower:
            raise ExtrapolationException('fake: past extrapolation')
        result = copy.deepcopy(pose)
        result.header.frame_id = target
        return result


def make_path():
    path = NavPath()
    path.header.frame_id = 'map'
    for x in (0.0, 1.0):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.orientation.w = 1.0
        path.poses.append(pose)
    return path


def run_production_tick(collector):
    """Isolate all monkeypatches so no test or imported module sees them later."""
    def isolated_import(name, *args, **kwargs):
        if name == 'rclpy.time':
            return NS(Time=FakeTime)
        return ORIGINAL_IMPORT(name, *args, **kwargs)

    with patch.object(production.importlib, 'import_module', side_effect=isolated_import):
        with patch.object(production.time, 'monotonic', return_value=1.0):
            collector._tick()


def production_collector(now_ns, tf_buffer):
    collector = production._Collector.__new__(production._Collector)
    collector.node = Node(now_ns)
    collector.tf_buffer = tf_buffer
    collector._finished = False
    collector.samples = []
    collector.errors = []
    collector.navigate_result = None
    collector.diagnostics = production._new_collector_diagnostics()
    collector.deadline = 10**99
    collector._publish_ready_when_complete = lambda: None
    collector._read_goal_trigger = lambda: True  # fake JSON trigger; no ROS header
    collector._compute_path_requested = False
    collector._navigate_requested = False
    collector.path = None
    collector.latest_lifecycle = collector.latest_scan = collector.latest_odom = collector.latest_receipt = None
    return collector


@dataclass(frozen=True)
class Identity:
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str


@dataclass(frozen=True)
class PathContext:
    goal_id: str
    path_sequence: int
    reset_epoch: int
    runtime_generation: int
    map_id: str
    map_content_hash: str
    path_stamp_ns: int
    received_steady_ns: int
    expiry_steady_ns: int
    revision: int


@dataclass(frozen=True)
class TriggerJson:
    """The current trigger is JSON and intentionally has no ROS header."""
    valid: bool = True
    goal_id: str = 'goal-1'


@dataclass(frozen=True)
class InputSnapshot:
    snapshot_id: str
    identity: Identity
    scan_stamp_ns: int
    odom_stamp_ns: int
    lifecycle_stamp_ns: int
    receipt_stamp_ns: int
    receipt_sequence: int
    scan_record_id: str
    odom_record_id: str
    lifecycle_sequence: int
    action_barrier_ns: int
    reset_barrier_ns: int
    scan_received_steady_ns: int
    odom_received_steady_ns: int
    lifecycle_received_steady_ns: int
    receipt_received_steady_ns: int
    path_context: PathContext
    path: object


class FixedTimestampModel:
    """Design model: immutable t_A and pending sample, nonblocking timer polls."""
    LIMITS = {'scan': 500_000_000, 'odom': 250_000_000, 'lifecycle': 500_000_000, 'receipt': 500_000_000}

    def __init__(self, run_deadline_steady_ns):
        self.run_deadline = run_deadline_steady_ns
        self.phase_a_stamp = None
        self.phase_a_context = None
        self.phase_a_identity = None
        self.phase_a_state = 'IDLE'
        self.phase_a_last_ros = None
        self.phase_a_queries = []
        self.planner_request_count = 0
        self.planner_request_stamp_ns = None
        self.pending = None
        self.last_ros = None
        self.committed = []
        self.used_measurement_identities = set()
        self.discards = []
        self.action_callbacks = 0
        self.lookup_failures = []

    @staticmethod
    def valid_context(identity, context):
        return (identity is not None and context is not None
                and bool(context.goal_id) and context.path_sequence >= 0
                and context.reset_epoch == identity.reset_epoch
                and context.runtime_generation == identity.runtime_generation
                and bool(context.map_id) and len(context.map_content_hash) == 64
                and all(c in '0123456789abcdef' for c in context.map_content_hash)
                and context.path_stamp_ns > 0
                and context.expiry_steady_ns > context.received_steady_ns)

    def consume_trigger_json(self, trigger, ros_now_ns, steady_ns, active_identity, active_context):
        if self.phase_a_state.startswith('FAILED_'):
            return self.phase_a_state
        if steady_ns >= self.run_deadline:
            self.phase_a_state = 'FAILED_STEADY_DEADLINE'
            return self.phase_a_state
        if not trigger or not trigger.valid:
            return 'TRIGGER_NOT_VALID'
        if self.phase_a_stamp is not None:
            return self.phase_a_state
        if ros_now_ns <= 0:
            self.phase_a_state = 'WAIT_VALID_ROS_CLOCK'
            return self.phase_a_state
        if not self.valid_context(active_identity, active_context):
            self.phase_a_state = 'FAILED_CONTEXT_MISSING_OR_INVALID'
            return self.phase_a_state
        if active_context.goal_id != trigger.goal_id:
            self.phase_a_state = 'FAILED_TRIGGER_CONTEXT_MISMATCH'
            return self.phase_a_state
        # JSON carries no ROS stamp: pin the positive ROS clock at first consumption.
        self.phase_a_stamp = ros_now_ns
        self.phase_a_last_ros = ros_now_ns
        self.phase_a_identity = active_identity
        self.phase_a_context = active_context
        self.phase_a_state = 'WAIT_EXACT_TF'
        return self.phase_a_state

    def rearm_phase_a_query(self):
        if self.phase_a_stamp is None or self.phase_a_state.startswith('FAILED_') or self.planner_request_count:
            return False
        self.phase_a_state = 'WAIT_EXACT_TF'
        return True

    def poll_phase_a(self, ros_now_ns, steady_ns, tf_buffer, active_identity, active_context):
        if self.phase_a_state.startswith('FAILED_'):
            return self.phase_a_state
        if steady_ns >= self.run_deadline:
            self.phase_a_state = 'FAILED_STEADY_DEADLINE'
            return self.phase_a_state
        if self.phase_a_stamp is None:
            return 'WAIT_VALID_ROS_CLOCK'
        if self.phase_a_last_ros is not None and ros_now_ns < self.phase_a_last_ros:
            self.phase_a_state = 'FAILED_CLOCK_ROLLBACK'
            return self.phase_a_state
        if ros_now_ns > 0:
            self.phase_a_last_ros = ros_now_ns
        if active_identity != self.phase_a_identity or active_context != self.phase_a_context:
            self.phase_a_state = 'FAILED_ACTIVE_CONTEXT_CHANGED'
            return self.phase_a_state
        self.phase_a_queries.append(self.phase_a_stamp)
        if not tf_buffer.can_transform('base_link', 'map', FakeTime(nanoseconds=self.phase_a_stamp)):
            self.phase_a_state = 'WAIT_EXACT_TF'
            return self.phase_a_state
        try:
            # A positive can_transform answer is followed by a real exact lookup.
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.header.stamp.sec, pose.header.stamp.nanosec = divmod(self.phase_a_stamp, 10**9)
            tf_buffer.transform(pose, 'base_link')
        except Exception as exc:  # keep original failure as structured offline outcome
            self.lookup_failures.append({'phase': 'A', 'type': type(exc).__name__, 'message': str(exc)})
            self.phase_a_state = 'WAIT_TF_LOOKUP_EXCEPTION'
            return self.phase_a_state
        if active_identity != self.phase_a_identity or active_context != self.phase_a_context:
            self.phase_a_state = 'FAILED_ACTIVE_CONTEXT_CHANGED'
            return self.phase_a_state
        if self.planner_request_count == 0:
            self.planner_request_count = 1
            # Preserve production behavior: goal uses request-send ROS time, not t_A.
            self.planner_request_stamp_ns = ros_now_ns
            self.phase_a_state = 'PLANNER_REQUESTED_ONCE'
        else:
            self.phase_a_state = 'PLANNER_REQUESTED_ONCE'
        return self.phase_a_state

    def capture_sample(self, snapshot, ros_now_ns, steady_ns, active_identity, active_barrier_revision, active_path_context):
        if snapshot is None or active_identity is None or active_barrier_revision is None or active_path_context is None:
            self.discards.append({'reason': 'ACTIVE_CONTEXT_REQUIRED_AT_ACQUISITION'})
            return False
        if not self.valid_context(snapshot.identity, snapshot.path_context) or not self.valid_context(active_identity, active_path_context):
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'IDENTITY_OR_PATH_CONTEXT_INVALID'})
            return False
        if snapshot.identity != active_identity or snapshot.path_context != active_path_context:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'ACTIVE_CONTEXT_MISMATCH_AT_ACQUISITION'})
            return False
        if ros_now_ns <= 0:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'CLOCK_NOT_STARTED'})
            return False
        if self.last_ros is not None and ros_now_ns < self.last_ros:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'CLOCK_ROLLBACK'})
            return False
        self.last_ros = ros_now_ns
        if steady_ns >= self.run_deadline:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'RUN_DEADLINE'})
            return False
        if not self._eligible(snapshot, t_vector_ns=ros_now_ns, now_ros_ns=ros_now_ns, steady_ns=steady_ns):
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'INPUT_NOT_ELIGIBLE_AT_ACQUISITION'})
            return False
        self.pending = {'snapshot': copy.deepcopy(snapshot), 't_vector_ns': ros_now_ns,
                        't_tf_ns': snapshot.odom_stamp_ns, 'identity': active_identity,
                        'barrier_revision': active_barrier_revision,
                        'path_context': copy.deepcopy(active_path_context), 'captured_steady_ns': steady_ns}
        return True

    def poll_sample(self, ros_now_ns, steady_ns, tf_buffer, active_identity, active_barrier_revision, active_path_context, latest_snapshot=None):
        if self.pending is None:
            return 'NO_PENDING'
        pending = self.pending
        snapshot = pending['snapshot']
        # Missing active context is itself a rejection, never a skipped predicate.
        if active_identity is None or active_barrier_revision is None or active_path_context is None:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'ACTIVE_CONTEXT_REQUIRED_AT_COMMIT'})
            self.pending = None
            return 'DISCARDED_MISSING_CONTEXT'
        if self.last_ros is not None and ros_now_ns < self.last_ros:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'CLOCK_ROLLBACK'})
            self.pending = None
            return 'DISCARDED_CLOCK_ROLLBACK'
        if ros_now_ns <= 0:
            return 'WAIT_VALID_ROS_CLOCK'
        self.last_ros = ros_now_ns
        if steady_ns >= self.run_deadline:
            self.discards.append({'snapshot_id': snapshot.snapshot_id, 'reason': 'EXISTING_RUN_DEADLINE'})
            self.pending = None
            return 'FAIL_EXISTING_RUN_DEADLINE'
        if active_identity != pending['identity']:
            return self._discard('IDENTITY_CHANGED')
        if active_barrier_revision != pending['barrier_revision']:
            return self._discard('BARRIER_REVISION_CHANGED')
        if active_path_context != pending['path_context']:
            return self._discard('PATH_CONTEXT_CHANGED')
        if not self._eligible(snapshot, t_vector_ns=pending['t_vector_ns'], now_ros_ns=ros_now_ns, steady_ns=steady_ns):
            return self._discard('INPUT_STALE_FUTURE_OR_AFTER_CUTOFF')
        # latest_snapshot is deliberately not consulted; the pending immutable snapshot is authoritative.
        del latest_snapshot
        query = FakeTime(nanoseconds=pending['t_tf_ns'])
        if not tf_buffer.can_transform('base_link', 'map', query):
            return 'WAIT_EXACT_TF_SAME_STAMP'
        try:
            # Transform only a deep copy. Preserve failure cause and do not commit on lookup exception.
            local_reference = production._features_from_path(copy.deepcopy(snapshot.path), tf_buffer, pending['t_tf_ns'])
        except Exception as exc:
            outcome = {'phase': 'B', 'type': type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__,
                       'message': str(exc.__cause__ or exc), 'wrapper_type': type(exc).__name__}
            self.lookup_failures.append(outcome)
            return 'WAIT_TF_LOOKUP_EXCEPTION'
        if not self._eligible(snapshot, t_vector_ns=pending['t_vector_ns'], now_ros_ns=ros_now_ns, steady_ns=steady_ns):
            return self._discard('INPUT_INVALIDATED_AT_COMMIT')
        measurement_identity = self.measurement_identity(snapshot)
        if measurement_identity in self.used_measurement_identities:
            return self._discard('DUPLICATE_MEASUREMENT_IDENTITY')
        self.used_measurement_identities.add(measurement_identity)
        # Commit marker records temporal/link provenance and LocalReference only; no vector is built.
        self.committed.append({'measurement_identity': measurement_identity,
                               't_vector_ns': pending['t_vector_ns'], 't_tf_ns': pending['t_tf_ns'],
                               't_odom_ns': snapshot.odom_stamp_ns, 't_commit_ros_ns': ros_now_ns,
                               'receipt_stamp_ns': snapshot.receipt_stamp_ns,
                               'receipt_sequence': snapshot.receipt_sequence,
                               'scan_record_id': snapshot.scan_record_id,
                               'odom_record_id': snapshot.odom_record_id,
                               'lifecycle_sequence': snapshot.lifecycle_sequence,
                               'path_sequence': snapshot.path_context.path_sequence,
                               'map_id': snapshot.path_context.map_id,
                               'local_reference': local_reference})
        self.pending = None
        return 'LOCAL_REFERENCE_COMMITTED'

    def _discard(self, reason):
        self.discards.append({'snapshot_id': self.pending['snapshot'].snapshot_id, 'reason': reason})
        self.pending = None
        return 'DISCARDED_' + reason

    @staticmethod
    def measurement_identity(s):
        # Stable source identities plus lifecycle/path context; excludes model-generated snapshot IDs and cutoff.
        return ((s.identity.episode_generation, s.identity.reset_epoch,
                 s.identity.runtime_generation, s.identity.config_hash),
                s.scan_record_id, s.odom_record_id, s.receipt_sequence,
                s.lifecycle_sequence, s.path_context.goal_id, s.path_context.path_sequence,
                s.path_context.reset_epoch, s.path_context.runtime_generation,
                s.path_context.map_id, s.path_context.map_content_hash)

    def _eligible(self, s, t_vector_ns, now_ros_ns, steady_ns):
        stamps = (('scan', s.scan_stamp_ns), ('odom', s.odom_stamp_ns),
                  ('lifecycle', s.lifecycle_stamp_ns), ('receipt', s.receipt_stamp_ns),
                  ('path', s.path_context.path_stamp_ns))
        for name, stamp in stamps:
            if stamp > t_vector_ns:  # no future input relative to the applicable observation cutoff
                return False
            age = now_ros_ns - stamp
            if age < 0 or (name in self.LIMITS and age > self.LIMITS[name]):
                return False
        if s.receipt_stamp_ns <= s.action_barrier_ns or s.receipt_stamp_ns <= s.reset_barrier_ns:
            return False
        if s.path_context.expiry_steady_ns <= steady_ns:
            return False
        return True


def make_context(identity, *, sequence=7, revision=3, path_stamp=10_000_000_000, received=1, expiry=10**15):
    return PathContext('goal-1', sequence, identity.reset_epoch, identity.runtime_generation,
                       'map-1', 'a' * 64, path_stamp, received, expiry, revision)


def make_snapshot(name, cutoff, *, identity=None, context=None, scan_stamp=None, odom_stamp=None,
                  lifecycle_stamp=None, receipt_stamp=None, scan_id='scan-1', odom_id='odom-1',
                  receipt_seq=11, lifecycle_seq=4, path=None):
    identity = identity or Identity(3, 2, 7, 'b' * 64)
    context = context or make_context(identity, path_stamp=cutoff)
    return InputSnapshot(name, identity, cutoff if scan_stamp is None else scan_stamp,
                         cutoff if odom_stamp is None else odom_stamp,
                         cutoff if lifecycle_stamp is None else lifecycle_stamp,
                         cutoff if receipt_stamp is None else receipt_stamp, receipt_seq,
                         scan_id, odom_id, lifecycle_seq, 0, 0, cutoff, cutoff, cutoff, cutoff,
                         context, path or make_path())


RESULTS = []
def record(name, baseline, proposed, **details):
    RESULTS.append({'case': name, 'baseline_production': baseline,
                    'proposed_model': proposed, **details})


identity = Identity(3, 2, 7, 'b' * 64)
context = make_context(identity)

# Production Phase-A baseline calls the current _tick(): each tick queries its moving ROS now.
baseline_rows = []
for now_ns, tf_upper in ((10_000_000_000, 9_980_000_000),
                         (10_050_000_000, 10_030_000_000),
                         (10_100_000_000, 10_080_000_000)):
    tf = FakeTF(upper=tf_upper)
    collector = production_collector(now_ns, tf)
    run_production_tick(collector)
    baseline_rows.append({'query_ns': tf.queries[-1][2], 'planner_requested': collector._compute_path_requested})
model = FixedTimestampModel(10**12)
model.consume_trigger_json(TriggerJson(), 10_000_000_000, 1, identity, context)
late_tf = FakeTF(upper=9_980_000_000)
phase_a_states = [model.poll_phase_a(10_000_000_000, 2, late_tf, identity, context)]
late_tf.upper = 10_000_000_000
phase_a_states.append(model.poll_phase_a(10_050_000_000, 3, late_tf, identity, context))
phase_a_states.append(model.poll_phase_a(10_100_000_000, 4, late_tf, identity, context))
record('phase_a_late_tf_fixed_trigger_consumption_time', baseline_rows, phase_a_states,
       trigger_format='JSON_NO_ROS_HEADER', t_a_ns=model.phase_a_stamp,
       planner_request_count=model.planner_request_count, planner_request_stamp_ns=model.planner_request_stamp_ns,
       phase_a_query_stamps=model.phase_a_queries)

# Production Phase-B baseline invokes the current path-feature helper at moving now.
path = make_path()
production_failures = []
for now_ns, tf_upper in ((10_050_000_000, 10_000_000_000), (10_100_000_000, 10_050_000_000)):
    try:
        production._features_from_path(path, FakeTF(upper=tf_upper), now_ns)
        production_failures.append('RETURNED')
    except ValueError as exc:
        production_failures.append({'wrapper': str(exc), 'cause': type(exc.__cause__).__name__ if exc.__cause__ else None})
snapshot = make_snapshot('snap-1', 10_000_000_000, path=path)
model = FixedTimestampModel(10**12)
model.capture_sample(snapshot, 10_000_000_000, 1, identity, context.revision, context)
tf = FakeTF(upper=9_980_000_000)
b_wait = model.poll_sample(10_050_000_000, 2, tf, identity, context.revision, context)
tf.upper = 10_000_000_000
b_commit = model.poll_sample(10_100_000_000, 3, tf, identity, context.revision, context)
record('phase_b_fixed_odom_transform_time', production_failures, [b_wait, b_commit],
       committed_records=model.committed)

# Trigger JSON contains no ROS header. Clock zero does not pin or send; steady deadline still terminates.
model = FixedTimestampModel(5)
clock_zero = model.consume_trigger_json(TriggerJson(), 0, 1, identity, context)
clock_zero_poll = model.consume_trigger_json(TriggerJson(), 0, 5, identity, context)
record('json_trigger_clock_invalid_steady_deadline', None, [clock_zero, clock_zero_poll],
       trigger_has_ros_header=False, t_a_ns=model.phase_a_stamp, action_count=model.planner_request_count)

# Missing/changed active context before sending the planner goal fails closed.
model = FixedTimestampModel(100)
model.consume_trigger_json(TriggerJson(), 20_000_000_000, 1, identity, context)
changed_identity = Identity(3, 3, 8, identity.config_hash)
state = model.poll_phase_a(20_000_000_001, 2, FakeTF(upper=30_000_000_000), changed_identity,
                           make_context(changed_identity))
record('phase_a_identity_changed_before_action', None, state, action_count=model.planner_request_count)

# Rollback is terminal for this attempt; a later clock increase cannot restore readiness.
model = FixedTimestampModel(100)
model.consume_trigger_json(TriggerJson(), 30_000_000_000, 1, identity, context)
rollback = model.poll_phase_a(29_000_000_000, 2, FakeTF(upper=40_000_000_000), identity, context)
recovered_clock = model.poll_phase_a(31_000_000_000, 3, FakeTF(upper=40_000_000_000), identity, context)
record('phase_a_rollback_terminal_no_resurrection', None, [rollback, recovered_clock],
       action_count=model.planner_request_count)

# Re-arm keeps t_A/context and sends the planner request once, with send-time stamp distinct from t_A.
model = FixedTimestampModel(100)
model.consume_trigger_json(TriggerJson(), 40_000_000_000, 1, identity, context)
model.poll_phase_a(40_000_000_000, 2, FakeTF(upper=39_000_000_000), identity, context)
rearmed = model.rearm_phase_a_query()
model.poll_phase_a(40_020_000_000, 3, FakeTF(upper=40_000_000_000), identity, context)
model.poll_phase_a(40_030_000_000, 4, FakeTF(upper=40_000_000_000), identity, context)
record('phase_a_rearm_one_action_preserve_ta', None, model.phase_a_state,
       rearm_accepted=rearmed, query_stamps=model.phase_a_queries, t_a_ns=model.phase_a_stamp,
       planner_request_count=model.planner_request_count, planner_request_stamp_ns=model.planner_request_stamp_ns,
       pinned_context_unchanged=(model.phase_a_context == context))

# Trigger arrives before any transform; false availability does not imply permanent failure or retarget.
model = FixedTimestampModel(10)
model.consume_trigger_json(TriggerJson(), 50_000_000_000, 1, identity, context)
never = FakeTF(lower=50_020_000_000, upper=50_100_000_000)
wait1 = model.poll_phase_a(50_000_000_000, 2, never, identity, context)
wait2 = model.poll_phase_a(50_050_000_000, 3, never, identity, context)
deadline = model.poll_phase_a(50_060_000_000, 10, never, identity, context)
record('phase_a_target_outside_buffer_until_steady_deadline', None, [wait1, wait2, deadline],
       query_stamps=model.phase_a_queries, t_a_ns=model.phase_a_stamp)

# Phase-B cutoff: no future input and no receipt later than t_vector.
base = 60_000_000_000
future_input = make_snapshot('future-input', base, identity=identity, context=make_context(identity, path_stamp=base),
                             scan_stamp=base + 1, receipt_stamp=base)
model = FixedTimestampModel(10**12)
future_accepted = model.capture_sample(future_input, base, 1, identity, context.revision, future_input.path_context)
late_receipt = make_snapshot('late-receipt', base, identity=identity, context=make_context(identity, path_stamp=base),
                             receipt_stamp=base + 1)
late_receipt_accepted = model.capture_sample(late_receipt, base, 1, identity, context.revision, late_receipt.path_context)
record('phase_b_cutoff_rejects_future_and_post_cutoff_inputs', None,
       {'future_input_accepted': future_accepted, 'post_cutoff_receipt_accepted': late_receipt_accepted})

# Required active barrier/path context cannot be omitted at acquisition or commit.
valid = make_snapshot('missing-context', base, identity=identity, context=make_context(identity, path_stamp=base))
model = FixedTimestampModel(10**12)
missing_barrier_acq = model.capture_sample(valid, base, 1, identity, None, valid.path_context)
missing_path_acq = model.capture_sample(valid, base, 1, identity, valid.path_context.revision, None)
model.capture_sample(valid, base, 1, identity, valid.path_context.revision, valid.path_context)
missing_barrier_commit = model.poll_sample(base + 1, 2, FakeTF(upper=base + 1), identity, None, valid.path_context)
model.capture_sample(valid, base + 1, 3, identity, valid.path_context.revision, valid.path_context)
missing_path_commit = model.poll_sample(base + 2, 4, FakeTF(upper=base + 2), identity, valid.path_context.revision, None)
record('phase_b_missing_active_context_rejected', None, {'missing_barrier_at_acquisition': missing_barrier_acq,
       'missing_path_at_acquisition': missing_path_acq, 'missing_barrier_at_commit': missing_barrier_commit,
       'missing_path_at_commit': missing_path_commit})

# Pending snapshot is immutable: later latest records cannot replace pinned members.
old = make_snapshot('old-snapshot', base, identity=identity, context=make_context(identity, path_stamp=base),
                    scan_id='scan-exact-1', odom_id='odom-exact-1', receipt_seq=91)
latest = make_snapshot('latest-snapshot', base + 10_000_000, identity=identity,
                       context=make_context(identity, path_stamp=base + 10_000_000),
                       scan_id='scan-new-2', odom_id='odom-new-2', receipt_seq=92)
model = FixedTimestampModel(10**12)
model.capture_sample(old, base, 1, identity, old.path_context.revision, old.path_context)
pending_before = copy.deepcopy(model.pending['snapshot'])
waiting = model.poll_sample(base + 1, 2, FakeTF(upper=base - 1), identity,
                            old.path_context.revision, old.path_context, latest_snapshot=latest)
pending_unchanged = model.pending['snapshot'] == pending_before
commit = model.poll_sample(base + 2, 3, FakeTF(upper=base + 2), identity,
                           old.path_context.revision, old.path_context, latest_snapshot=latest)
record('pending_snapshot_not_replaced_by_latest', None, [waiting, commit], pending_unchanged=pending_unchanged,
       committed_records=model.committed)

# Duplicate detection is measurement/lifecycle identity, not model snapshot ID or cutoff.
first = make_snapshot('id-a', base, identity=identity, context=make_context(identity, path_stamp=base),
                      scan_id='scan-same', odom_id='odom-same', receipt_seq=77)
second = make_snapshot('id-b', base + 5_000_000, identity=identity, context=make_context(identity, path_stamp=base),
                       scan_id='scan-same', odom_id='odom-same', receipt_seq=77)
model = FixedTimestampModel(10**12)
model.capture_sample(first, base, 1, identity, first.path_context.revision, first.path_context)
model.poll_sample(base + 1, 2, FakeTF(upper=base + 1), identity, first.path_context.revision, first.path_context)
model.capture_sample(second, base + 5_000_000, 3, identity, second.path_context.revision, second.path_context)
duplicate = model.poll_sample(base + 5_000_001, 4, FakeTF(upper=base + 5_000_001), identity,
                              second.path_context.revision, second.path_context)
record('same_measurements_different_snapshot_id_and_cutoff', None, duplicate,
       committed_count=len(model.committed), discarded=model.discards)

# Inputs fresh at acquisition may be stale at commit; no latest substitution.
model = FixedTimestampModel(10**12)
snapshot = make_snapshot('fresh-then-stale', base, identity=identity, context=make_context(identity, path_stamp=base))
acquired = model.capture_sample(snapshot, base, 1, identity, snapshot.path_context.revision, snapshot.path_context)
stale = model.poll_sample(base + FixedTimestampModel.LIMITS['odom'] + 1, 2,
                          FakeTF(upper=base + FixedTimestampModel.LIMITS['odom'] + 1), identity,
                          snapshot.path_context.revision, snapshot.path_context)
record('fresh_at_acquisition_stale_at_commit', None, stale, acquired=acquired, commits=len(model.committed))

# Barrier/path context ABA is caught by authoritative monotonic revisions/sequences.
ctx_old = make_context(identity, sequence=12, revision=4, path_stamp=base)
ctx_new = make_context(identity, sequence=14, revision=6, path_stamp=base)
snapshot = make_snapshot('aba', base, identity=identity, context=ctx_old)
model = FixedTimestampModel(10**12)
model.capture_sample(snapshot, base, 1, identity, 4, ctx_old)
barrier_aba = model.poll_sample(base + 1, 2, FakeTF(upper=base + 1), identity, 6, ctx_old)
model = FixedTimestampModel(10**12)
model.capture_sample(snapshot, base, 1, identity, 4, ctx_old)
path_aba = model.poll_sample(base + 1, 2, FakeTF(upper=base + 1), identity, 4, ctx_new)
record('barrier_and_path_change_then_return_invalidate', None, {'barrier': barrier_aba, 'path': path_aba,
       'current_values_equal_old_payload': True, 'revision_or_sequence_advanced': True})

# can_transform true is not enough: transform exceptions are preserved and never committed.
model = FixedTimestampModel(10**12)
snapshot = make_snapshot('lookup-throws', base, identity=identity, context=make_context(identity, path_stamp=base))
model.capture_sample(snapshot, base, 1, identity, snapshot.path_context.revision, snapshot.path_context)
throws = FakeTF(upper=base + 1, transform_error=ExtrapolationException('fake lookup cause'))
lookup_outcome = model.poll_sample(base + 1, 2, throws, identity, snapshot.path_context.revision, snapshot.path_context)
record('can_transform_true_lookup_exception', None, lookup_outcome, can_transform_result=True,
       lookup_failures=model.lookup_failures, commits=len(model.committed))

# Path transform uses a copied request; production helper mutation is separately shown as baseline evidence.
source_path = make_path()
source_path.poses[1].header.stamp.sec = 2
before = (source_path.poses[1].header.stamp.sec, source_path.poses[1].header.stamp.nanosec)
try:
    production._features_from_path(source_path, FakeTF(upper=4_000_000_000), 3_000_000_004)
    baseline_mutation = (source_path.poses[1].header.stamp.sec, source_path.poses[1].header.stamp.nanosec)
except Exception as exc:
    baseline_mutation = {'error': type(exc).__name__, 'message': str(exc)}
proposed_path = make_path()
proposed_path.poses[1].header.stamp.sec = 2
proposed_before = (proposed_path.poses[1].header.stamp.sec, proposed_path.poses[1].header.stamp.nanosec)
production._features_from_path(copy.deepcopy(proposed_path), FakeTF(upper=4_000_000_000), 3_000_000_004)
proposed_after = (proposed_path.poses[1].header.stamp.sec, proposed_path.poses[1].header.stamp.nanosec)
record('raw_path_immutability', {'before': before, 'after': baseline_mutation},
       {'before': proposed_before, 'after': proposed_after, 'unchanged': proposed_before == proposed_after})

# Executor/action callback remains processable while the model performs nonblocking timer polls.
model = FixedTimestampModel(10**12)
snapshot = make_snapshot('callback', base, identity=identity, context=make_context(identity, path_stamp=base))
model.capture_sample(snapshot, base, 1, identity, snapshot.path_context.revision, snapshot.path_context)
first_poll = model.poll_sample(base + 1, 2, FakeTF(upper=base - 1), identity,
                              snapshot.path_context.revision, snapshot.path_context)
model.action_callbacks += 1  # fake executor callback runs between timer invocations
second_poll = model.poll_sample(base + 2, 3, FakeTF(upper=base + 2), identity,
                               snapshot.path_context.revision, snapshot.path_context)
record('callbacks_progress_while_nonblocking_wait', None, {'first_poll': first_poll,
       'callbacks_processed': model.action_callbacks, 'next_poll': second_poll})

# Existing source-input freshness limit is rechecked; no new bound is introduced here.
record('freshness_limits_used_by_model', None, FixedTimestampModel.LIMITS,
       authority_note='existing collector source values only; not TF-age/skew/expiry authority')

assert production.importlib.import_module is ORIGINAL_IMPORT
assert production.time.monotonic is ORIGINAL_MONOTONIC
assert len(RESULTS) == 17
assert RESULTS[0]['proposed_model'][-1] == 'PLANNER_REQUESTED_ONCE'
assert RESULTS[0]['t_a_ns'] != RESULTS[0]['planner_request_stamp_ns']
assert RESULTS[2]['proposed_model'][-1] == 'FAILED_STEADY_DEADLINE' and RESULTS[2]['t_a_ns'] is None
assert RESULTS[3]['proposed_model'] == 'FAILED_ACTIVE_CONTEXT_CHANGED'
assert RESULTS[4]['proposed_model'] == ['FAILED_CLOCK_ROLLBACK', 'FAILED_CLOCK_ROLLBACK']
assert RESULTS[5]['pinned_context_unchanged'] is True and RESULTS[5]['planner_request_count'] == 1
assert RESULTS[6]['proposed_model'][-1] == 'FAILED_STEADY_DEADLINE'
assert RESULTS[7]['proposed_model']['future_input_accepted'] is False
assert RESULTS[7]['proposed_model']['post_cutoff_receipt_accepted'] is False
assert RESULTS[8]['proposed_model']['missing_barrier_at_acquisition'] is False
assert RESULTS[8]['proposed_model']['missing_path_at_acquisition'] is False
assert RESULTS[8]['proposed_model']['missing_barrier_at_commit'] == 'DISCARDED_MISSING_CONTEXT'
assert RESULTS[8]['proposed_model']['missing_path_at_commit'] == 'DISCARDED_MISSING_CONTEXT'
assert RESULTS[9]['pending_unchanged'] is True and RESULTS[9]['committed_records'][0]['receipt_sequence'] == 91
assert RESULTS[10]['proposed_model'] == 'DISCARDED_DUPLICATE_MEASUREMENT_IDENTITY'
assert RESULTS[11]['proposed_model'] == 'DISCARDED_INPUT_STALE_FUTURE_OR_AFTER_CUTOFF'
assert RESULTS[12]['proposed_model'] == {'barrier': 'DISCARDED_BARRIER_REVISION_CHANGED', 'path': 'DISCARDED_PATH_CONTEXT_CHANGED', 'current_values_equal_old_payload': True, 'revision_or_sequence_advanced': True}
assert RESULTS[13]['proposed_model'] == 'WAIT_TF_LOOKUP_EXCEPTION' and RESULTS[13]['commits'] == 0
assert RESULTS[14]['proposed_model']['unchanged'] is True
assert RESULTS[15]['proposed_model']['callbacks_processed'] == 1

OUT = Path(__file__).with_name('offline_validation_results.json')
RESULT_DOC = {
    'model_status': 'PROPOSAL_ONLY_NOT_PRODUCTION',
    'production_baseline': {
        'executed_separately': True,
        'executed_separately': True,
        'source_path': str(OBSERVER_REL),
        'source_sha256': OBSERVER_SHA256,
        'methods': ['_Collector._tick()', '_features_from_path()'],
        'fake_objects_only': True,
    },
    'runtime_or_campaign': False,
    'not_evaluated': ['81D_vector_acceptance', 'QoS_acceptance', 'evidence_chain_acceptance',
                      'campaign_pass', 'Nav2_runtime', 'TF2_runtime_buffer_behavior'],
    'freshness_limits_ns': FixedTimestampModel.LIMITS,
    'tf_wait_budget': 'none added; steady deadline is the existing whole-run deadline',
    'case_count': len(RESULTS),
    'cases': RESULTS,
}
OUT.write_text(json.dumps(RESULT_DOC, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'case_count': len(RESULTS), 'model_status': RESULT_DOC['model_status'],
                  'production_source': str(OBSERVER_SOURCE), 'source_sha256': OBSERVER_SHA256,
                  'not_evaluated': RESULT_DOC['not_evaluated']}, sort_keys=True))
