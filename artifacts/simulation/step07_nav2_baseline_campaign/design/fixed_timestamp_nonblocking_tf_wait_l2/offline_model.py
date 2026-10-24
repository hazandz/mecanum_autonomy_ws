"""Review-only temporal model; proposed state machine is not production code."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

BASELINE_COMMIT = '4e83ce6cffdd9910c288f90454ab747497d7a4a6'
OBSERVER_REL = Path('ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py')
OBSERVER_SHA256 = '39b9c08d01770c8ca12d1264297c69e5943a8b90640daa98ffeeaf9b2b28c28f'


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True,
                        help='exact source checkout to verify; no overlay/source auto-discovery')
    return parser.parse_args()


ARGS = parse_args()
REPO = ARGS.repo_root.expanduser().resolve(strict=True)
OBSERVER_SOURCE = (REPO / OBSERVER_REL).resolve(strict=True)
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
    def __init__(self, *, nanoseconds): self.nanoseconds = nanoseconds


class Clock:
    def __init__(self, ns): self.ns = ns
    def now(self): return NS(nanoseconds=self.ns, to_msg=lambda: NS(sec=self.ns // 10**9, nanosec=self.ns % 10**9))


class Node:
    def __init__(self, ns): self.clock = Clock(ns)
    def get_clock(self): return self.clock


class FakeTF:
    def __init__(self, lower=0, upper=0, connected=True, transform_error=None, on_transform=None):
        self.lower, self.upper, self.connected = lower, upper, connected
        self.transform_error, self.on_transform = transform_error, on_transform
        self.queries, self.lookups = [], []
    def can_transform(self, target, source, stamp):
        self.queries.append((target, source, stamp.nanoseconds))
        return self.connected and self.lower <= stamp.nanoseconds <= self.upper
    def transform(self, pose, target):
        stamp = pose.header.stamp.sec * 10**9 + pose.header.stamp.nanosec
        self.lookups.append((target, pose.header.frame_id, stamp))
        if self.on_transform: self.on_transform()
        if self.transform_error: raise self.transform_error
        if not self.connected: raise ConnectivityException('fake connectivity failure')
        if stamp < self.lower or stamp > self.upper: raise ExtrapolationException('fake extrapolation')
        result = copy.deepcopy(pose)
        result.header.frame_id = target
        return result


def make_path():
    result = NavPath()
    result.header.frame_id = 'map'
    for x in (0.0, 1.0):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.orientation.w = 1.0
        result.poses.append(pose)
    return result


def run_production_tick(collector):
    """Patch import/steady clock only for this call; restore on every exit."""
    def isolated_import(name, *args, **kwargs):
        if name == 'rclpy.time': return NS(Time=FakeTime)
        return ORIGINAL_IMPORT(name, *args, **kwargs)
    with patch.object(production.importlib, 'import_module', side_effect=isolated_import):
        with patch.object(production.time, 'monotonic', return_value=1.0):
            collector._tick()


def production_collector(now_ns, tf):
    collector = production._Collector.__new__(production._Collector)
    collector.node = Node(now_ns)
    collector.tf_buffer = tf
    collector._finished = False
    collector.samples, collector.errors, collector.navigate_result = [], [], None
    collector.diagnostics = production._new_collector_diagnostics()
    collector.deadline = 10**99
    collector._publish_ready_when_complete = lambda: None
    collector._read_goal_trigger = lambda: True  # fake JSON trigger, intentionally no ROS header
    collector._compute_path_requested = collector._navigate_requested = False
    collector.path = None  # startup has no returned path
    collector.latest_lifecycle = collector.latest_scan = collector.latest_odom = collector.latest_receipt = None
    return collector


@dataclass(frozen=True)
class Identity:
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str


@dataclass(frozen=True)
class MapIdentity:
    map_id: str
    map_content_hash: str


@dataclass(frozen=True)
class AttemptContext:
    goal_intent_id: str
    goal_id: str
    identity: Identity
    map_identity: MapIdentity
    barrier_revision: int
    barrier_event_id: str


@dataclass(frozen=True)
class TriggerJson:
    valid: bool = True
    goal_intent_id: str = 'intent-1'
    goal_id: str = 'goal-1'


@dataclass(frozen=True)
class PlannerResult:
    request_id: str
    goal_id: str
    identity: Identity
    map_identity: MapIdentity
    status: str
    path_sequence: int
    path_stamp_ns: int
    received_steady_ns: int
    expiry_steady_ns: int
    path: object


@dataclass(frozen=True)
class PathContext:
    request_id: str
    goal_id: str
    path_sequence: int
    reset_epoch: int
    runtime_generation: int
    map_id: str
    map_content_hash: str
    path_stamp_ns: int
    received_steady_ns: int
    expiry_steady_ns: int


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


@dataclass(frozen=True)
class LiveState:
    ros_ns: int
    steady_ns: int
    identity: Identity | None
    attempt_context: AttemptContext | None
    barrier_revision: int | None
    path_context: PathContext | None


class FakeStateSupplier:
    """Explicit fake clock/context supplier; transform callback may advance/change it."""
    def __init__(self, state): self.state = state; self.read_count = 0
    def read(self):
        self.read_count += 1
        return self.state


class FixedTimestampModel:
    LIMITS = {'scan': 500_000_000, 'odom': 250_000_000,
              'lifecycle': 500_000_000, 'receipt': 500_000_000}
    def __init__(self, deadline_steady_ns):
        self.deadline = deadline_steady_ns
        self.last_ros_ns = None
        self.terminal_failure = None
        self.t_a_ns = None
        self.attempt_context = None
        self.phase_a_state = 'IDLE'
        self.phase_a_queries = []
        self.action_request_count = 0
        self.request_id = None
        self.planner_request_stamp_ns = None
        self.path_context = None
        self.bound_path = None
        self.pending = None
        self.committed = []
        self.used_measurements = set()
        self.outcomes = []
        self.callback_count = 0

    @staticmethod
    def _valid_identity(identity):
        return (identity is not None and identity.episode_generation >= 0 and identity.reset_epoch >= 0
                and identity.runtime_generation >= 0 and len(identity.config_hash) == 64
                and all(c in '0123456789abcdef' for c in identity.config_hash))

    @classmethod
    def _valid_attempt_context(cls, context):
        return (context is not None and bool(context.goal_intent_id) and bool(context.goal_id)
                and cls._valid_identity(context.identity) and context.map_identity is not None
                and bool(context.map_identity.map_id) and len(context.map_identity.map_content_hash) == 64
                and all(c in '0123456789abcdef' for c in context.map_identity.map_content_hash)
                and context.barrier_revision >= 0 and bool(context.barrier_event_id))

    @classmethod
    def _valid_path_context(cls, path):
        return (path is not None and bool(path.request_id) and bool(path.goal_id)
                and path.path_sequence >= 0 and path.reset_epoch >= 0 and path.runtime_generation >= 0
                and bool(path.map_id) and len(path.map_content_hash) == 64
                and all(c in '0123456789abcdef' for c in path.map_content_hash)
                and path.path_stamp_ns is not None and path.expiry_steady_ns > path.received_steady_ns)

    def process_action_callback(self):
        self.callback_count += 1

    def _clock_entry(self, state, entrypoint):
        if self.terminal_failure:
            return False
        if state.steady_ns >= self.deadline:
            self._terminal('STEADY_DEADLINE', entrypoint)
            return False
        if self.last_ros_ns is not None and state.ros_ns < self.last_ros_ns:
            self._terminal('ROS_CLOCK_ROLLBACK', entrypoint)
            return False
        if state.ros_ns > 0:
            self.last_ros_ns = state.ros_ns
        return True

    def _terminal(self, reason, entrypoint):
        self.terminal_failure = {'reason': reason, 'entrypoint': entrypoint}
        self.phase_a_state = 'FAILED_' + reason
        self.pending = None
        self.path_context = None
        self.bound_path = None
        self.outcomes.append(copy.deepcopy(self.terminal_failure))

    def consume_trigger_json(self, trigger, state):
        if not self._clock_entry(state, 'consume_trigger_json'):
            return self.phase_a_state if self.t_a_ns is not None else 'FAILED_' + self.terminal_failure['reason']
        if not trigger or not trigger.valid:
            return 'TRIGGER_INVALID'
        if self.t_a_ns is not None:
            return self.phase_a_state
        if state.ros_ns <= 0:
            self.phase_a_state = 'WAIT_VALID_ROS_CLOCK'
            return self.phase_a_state
        context = state.attempt_context
        if not self._valid_attempt_context(context) or context != state.attempt_context:
            return 'REJECTED_ATTEMPT_CONTEXT'
        if (trigger.goal_id != context.goal_id or trigger.goal_intent_id != context.goal_intent_id
                or context.identity != state.identity or context.barrier_revision != state.barrier_revision):
            return 'REJECTED_TRIGGER_CONTEXT_MISMATCH'
        # Phase A context intentionally contains no path sequence/stamp/expiry.
        self.t_a_ns = state.ros_ns
        self.attempt_context = context
        self.phase_a_state = 'WAIT_EXACT_TF'
        return self.phase_a_state

    def rearm_phase_a_query(self, state):
        if not self._clock_entry(state, 'rearm_phase_a_query'):
            return False
        if self.t_a_ns is None or self.action_request_count or state.attempt_context != self.attempt_context:
            return False
        self.phase_a_state = 'WAIT_EXACT_TF'
        return True

    def poll_phase_a(self, state, tf):
        if not self._clock_entry(state, 'poll_phase_a'):
            return self.phase_a_state
        if self.t_a_ns is None:
            self.phase_a_state = 'WAIT_VALID_ROS_CLOCK'
            return self.phase_a_state
        if (state.identity != self.attempt_context.identity
                or state.attempt_context != self.attempt_context
                or state.barrier_revision != self.attempt_context.barrier_revision):
            self._terminal('ACTIVE_ATTEMPT_CONTEXT_CHANGED', 'poll_phase_a')
            return self.phase_a_state
        self.phase_a_queries.append(self.t_a_ns)
        if not tf.can_transform('base_link', 'map', FakeTime(nanoseconds=self.t_a_ns)):
            self.phase_a_state = 'WAIT_EXACT_TF'
            return self.phase_a_state
        # No path exists or is required before planner success.
        if self.action_request_count == 0:
            self.action_request_count = 1
            self.request_id = 'request-1'
            self.planner_request_stamp_ns = state.ros_ns
        self.phase_a_state = 'PLANNER_REQUESTED_ONCE'
        return self.phase_a_state

    def accept_planner_result(self, result, state):
        if not self._clock_entry(state, 'accept_planner_result'):
            return 'REJECTED_TERMINAL_ATTEMPT'
        if self.action_request_count != 1 or self.path_context is not None:
            return 'REJECTED_NO_PENDING_PLANNER_REQUEST'
        ctx = self.attempt_context
        if (result is None or result.status != 'SUCCEEDED' or result.request_id != self.request_id
                or result.goal_id != ctx.goal_id or result.identity != ctx.identity
                or result.map_identity != ctx.map_identity
                or state.attempt_context != ctx or state.identity != ctx.identity
                or state.barrier_revision != ctx.barrier_revision):
            return 'REJECTED_WRONG_OR_STALE_PLANNER_RESULT'
        if not self._valid_path_context(PathContext(result.request_id, result.goal_id,
                result.path_sequence, result.identity.reset_epoch, result.identity.runtime_generation,
                result.map_identity.map_id, result.map_identity.map_content_hash,
                result.path_stamp_ns, result.received_steady_ns, result.expiry_steady_ns)) or result.path is None:
            return 'REJECTED_INVALID_RETURNED_PATH'
        self.path_context = PathContext(result.request_id, result.goal_id, result.path_sequence,
            result.identity.reset_epoch, result.identity.runtime_generation,
            result.map_identity.map_id, result.map_identity.map_content_hash,
            result.path_stamp_ns, result.received_steady_ns, result.expiry_steady_ns)
        self.bound_path = copy.deepcopy(result.path)
        return 'BOUND_RETURNED_PATH_AFTER_MATCHED_SUCCESS'

    def capture_sample(self, snapshot, supplier):
        state = supplier.read()
        if not self._clock_entry(state, 'capture_sample'):
            return 'REJECTED_TERMINAL_ATTEMPT'
        if self.pending is not None:
            return 'REJECTED_PENDING_SNAPSHOT_EXISTS'
        if self.terminal_failure or self.path_context is None or self.bound_path is None:
            return 'REJECTED_NO_ELIGIBLE_RETURNED_PATH'
        if (state.identity != self.attempt_context.identity or state.attempt_context != self.attempt_context
                or state.barrier_revision != self.attempt_context.barrier_revision
                or state.path_context != self.path_context):
            return 'REJECTED_ACTIVE_CONTEXT_MISMATCH'
        if snapshot is None or snapshot.identity != state.identity or snapshot.path_context != self.path_context:
            return 'REJECTED_SNAPSHOT_CONTEXT_MISMATCH'
        t_vector = state.ros_ns
        if t_vector <= 0 or not self._eligible(snapshot, t_vector, state):
            return 'REJECTED_INPUT_AT_ACQUISITION'
        self.pending = {'snapshot': copy.deepcopy(snapshot), 't_vector_ns': t_vector,
                        't_tf_ns': snapshot.odom_stamp_ns, 'identity': state.identity,
                        'attempt_context': state.attempt_context,
                        'barrier_revision': state.barrier_revision,
                        'path_context': state.path_context,
                        'path': copy.deepcopy(self.bound_path)}
        return 'PENDING_EXACT_TIME_TF'

    def poll_sample(self, supplier, tf):
        state = supplier.read()
        if not self._clock_entry(state, 'poll_sample_pre_lookup'):
            return 'REJECTED_TERMINAL_ATTEMPT'
        if self.pending is None:
            return 'NO_PENDING_SNAPSHOT'
        if not self._pending_context_valid(state):
            self._discard('PRE_LOOKUP_CONTEXT_INVALID')
            return 'DISCARDED_PRE_LOOKUP_CONTEXT'
        if not self._eligible(self.pending['snapshot'], self.pending['t_vector_ns'], state):
            self._discard('PRE_LOOKUP_INPUT_INVALID')
            return 'DISCARDED_PRE_LOOKUP_INPUT'
        target = FakeTime(nanoseconds=self.pending['t_tf_ns'])
        if not tf.can_transform('base_link', 'map', target):
            return 'WAIT_EXACT_TF_SAME_STAMP'
        transform_error = None
        try:
            local_reference = production._features_from_path(copy.deepcopy(self.pending['path']), tf,
                                                               self.pending['t_tf_ns'])
        except Exception as exc:
            cause = exc.__cause__
            transform_error = {'type': type(cause).__name__ if cause else type(exc).__name__,
                               'message': str(cause or exc),
                               'wrapper_type': type(exc).__name__}
        # Final supplier read is deliberately after lookup/transform, immediately before commit decision.
        final_state = supplier.read()
        if not self._clock_entry(final_state, 'poll_sample_final_check'):
            return 'REJECTED_TERMINAL_ATTEMPT'
        if not self._pending_context_valid(final_state):
            self._discard('FINAL_CONTEXT_INVALID')
            return 'DISCARDED_FINAL_CONTEXT'
        if not self._eligible(self.pending['snapshot'], self.pending['t_vector_ns'], final_state):
            self._discard('FINAL_INPUT_STALE_FUTURE_OR_AFTER_CUTOFF')
            return 'DISCARDED_FINAL_INPUT'
        if transform_error is not None:
            self.outcomes.append({'reason': 'TF_LOOKUP_EXCEPTION', **transform_error})
            return 'WAIT_TF_LOOKUP_EXCEPTION'
        measurement = self._measurement_identity(self.pending['snapshot'])
        if measurement in self.used_measurements:
            self._discard('DUPLICATE_MEASUREMENT_IDENTITY')
            return 'DISCARDED_DUPLICATE_MEASUREMENT_IDENTITY'
        pending = self.pending
        self.used_measurements.add(measurement)
        self.committed.append({'measurement_identity': measurement,
            't_vector_ns': pending['t_vector_ns'], 't_tf_ns': pending['t_tf_ns'],
            't_odom_ns': pending['snapshot'].odom_stamp_ns, 't_commit_ros_ns': final_state.ros_ns,
            'receipt_sequence': pending['snapshot'].receipt_sequence,
            'scan_record_id': pending['snapshot'].scan_record_id,
            'odom_record_id': pending['snapshot'].odom_record_id,
            'path_sequence': pending['path_context'].path_sequence,
            'map_id': pending['path_context'].map_id, 'local_reference': local_reference})
        self.pending = None
        return 'LOCAL_REFERENCE_COMMITTED'

    def _pending_context_valid(self, state):
        p = self.pending
        return (p is not None and state.identity == p['identity']
                and state.attempt_context == p['attempt_context']
                and state.barrier_revision == p['barrier_revision']
                and state.path_context == p['path_context']
                and state.steady_ns < self.deadline
                and state.steady_ns < p['path_context'].expiry_steady_ns)

    def _eligible(self, s, t_vector, state):
        stamps = (('scan', s.scan_stamp_ns), ('odom', s.odom_stamp_ns),
                  ('lifecycle', s.lifecycle_stamp_ns), ('receipt', s.receipt_stamp_ns),
                  ('path', s.path_context.path_stamp_ns))
        for name, stamp in stamps:
            if stamp > t_vector: return False
            age = state.ros_ns - stamp
            if age < 0 or (name in self.LIMITS and age > self.LIMITS[name]): return False
        if s.receipt_stamp_ns <= s.action_barrier_ns or s.receipt_stamp_ns <= s.reset_barrier_ns:
            return False
        if state.steady_ns >= s.path_context.expiry_steady_ns: return False
        return True

    def _discard(self, reason):
        self.outcomes.append({'reason': reason, 'snapshot_id': self.pending['snapshot'].snapshot_id})
        self.pending = None

    @staticmethod
    def _measurement_identity(s):
        c = s.path_context
        i = s.identity
        return ((i.episode_generation, i.reset_epoch, i.runtime_generation, i.config_hash),
                s.scan_record_id, s.odom_record_id, s.receipt_sequence, s.lifecycle_sequence,
                c.goal_id, c.path_sequence, c.reset_epoch, c.runtime_generation,
                c.map_id, c.map_content_hash)


def state_at(ros_ns, steady_ns, identity, attempt, barrier, path):
    return LiveState(ros_ns, steady_ns, identity, attempt, barrier, path)


def make_attempt(identity, map_identity, barrier=3):
    return AttemptContext('intent-1', 'goal-1', identity, map_identity, barrier, 'barrier-event-3')


def planner_result(model, attempt, status='SUCCEEDED', request_id=None, identity=None,
                   map_identity=None, path_sequence=7, path_stamp=10_000_000_000,
                   received=1, expiry=10**15, path=None):
    return PlannerResult(request_id or model.request_id, attempt.goal_id,
        identity or attempt.identity, map_identity or attempt.map_identity, status,
        path_sequence, path_stamp, received, expiry, path or make_path())


def sample_for(path_context, identity, stamp, *, name='sample-1', scan_id='scan-1', odom_id='odom-1', receipt_seq=11):
    return InputSnapshot(name, identity, stamp, stamp, stamp, stamp, receipt_seq,
        scan_id, odom_id, 4, 0, 0, stamp, stamp, stamp, stamp, path_context, make_path())


def establish_planner_ready(now=10_000_000_000, steady=10, deadline=10**15, tf_upper=None):
    ident = Identity(3, 2, 7, 'b' * 64)
    map_id = MapIdentity('map-1', 'a' * 64)
    attempt = make_attempt(ident, map_id)
    live = state_at(now, steady, ident, attempt, attempt.barrier_revision, None)
    model = FixedTimestampModel(deadline)
    assert model.consume_trigger_json(TriggerJson(), live) == 'WAIT_EXACT_TF'
    tf = FakeTF(upper=now if tf_upper is None else tf_upper)
    model.poll_phase_a(live, tf)
    assert model.path_context is None  # no path is required before the planner call
    assert model.action_request_count == 1
    result = planner_result(model, attempt, path_stamp=now)
    assert model.accept_planner_result(result, live) == 'BOUND_RETURNED_PATH_AFTER_MATCHED_SUCCESS'
    path = model.path_context
    return model, ident, attempt, path, state_at(now, steady, ident, attempt, attempt.barrier_revision, path)


CASES = {}
def case(name, expected, observed, **details):
    assert name not in CASES, 'DUPLICATE_CASE_NAME:' + name
    assert observed == expected, f'{name}: expected {expected!r}, got {observed!r}'
    CASES[name] = {'case': name, 'expected': expected, 'observed': observed, **details}


# Pinned production baseline is executed independently and uses no proposed-model methods.
BASE_IDENTITY = Identity(3, 2, 7, 'b' * 64)
BASELINE_PHASE_A = []
for now, upper in ((10_000_000_000, 9_980_000_000),
                   (10_050_000_000, 10_030_000_000),
                   (10_100_000_000, 10_080_000_000)):
    tf = FakeTF(upper=upper)
    collector = production_collector(now, tf)
    run_production_tick(collector)
    BASELINE_PHASE_A.append({'query_ns': tf.queries[-1][2], 'planner_requested': collector._compute_path_requested})
base_path = make_path()
BASELINE_PHASE_B = []
for now, upper in ((10_050_000_000, 10_000_000_000), (10_100_000_000, 10_050_000_000)):
    try:
        production._features_from_path(base_path, FakeTF(upper=upper), now)
        BASELINE_PHASE_B.append('RETURNED')
    except ValueError as exc:
        BASELINE_PHASE_B.append({'wrapper': str(exc), 'cause': type(exc.__cause__).__name__ if exc.__cause__ else None})
assert production.importlib.import_module is ORIGINAL_IMPORT
assert production.time.monotonic is ORIGINAL_MONOTONIC

# F1: startup has attempt context but no completed path; exact TF still sends once.
ident = Identity(3, 2, 7, 'b' * 64); map_ident = MapIdentity('map-1', 'a' * 64); attempt = make_attempt(ident, map_ident)
model = FixedTimestampModel(10**15); live = state_at(20_000_000_000, 10, ident, attempt, 3, None)
model.consume_trigger_json(TriggerJson(), live)
path_context_before_planner = model.path_context
assert path_context_before_planner is None
startup = model.poll_phase_a(live, FakeTF(upper=20_000_000_000))
assert model.path_context is None
case('startup_without_path_sends_planner_once', 'PLANNER_REQUESTED_ONCE', startup,
     path_context_before_planner=path_context_before_planner, path_context_after_request=model.path_context, action_count=model.action_request_count,
     t_a_ns=model.t_a_ns, planner_stamp_ns=model.planner_request_stamp_ns)

# Active attempt context is checked immediately before any planner action.
model = FixedTimestampModel(10**15); model.consume_trigger_json(TriggerJson(), live)
changed_map = MapIdentity('other-map', 'c' * 64)
changed_attempt = make_attempt(ident, changed_map)
changed_state = state_at(20_000_000_001, 11, ident, changed_attempt, 3, None)
blocked = model.poll_phase_a(changed_state, FakeTF(upper=20_000_000_001))
case('phase_a_attempt_context_change_before_action', 'FAILED_ACTIVE_ATTEMPT_CONTEXT_CHANGED', blocked,
     action_count=model.action_request_count, t_a_ns=model.t_a_ns)

# Trigger JSON has no header; clock zero waits, steady deadline still fails.
model = FixedTimestampModel(5); zero = state_at(0, 1, ident, attempt, 3, None)
first = model.consume_trigger_json(TriggerJson(), zero)
end = model.consume_trigger_json(TriggerJson(), state_at(0, 5, ident, attempt, 3, None))
case('json_trigger_no_header_clock_zero_steady_deadline', ['WAIT_VALID_ROS_CLOCK', 'FAILED_STEADY_DEADLINE'], [first, end],
     trigger_has_ros_header=False, action_count=model.action_request_count)

# Late TF uses one t_A; planner goal remains send-time stamped; re-arm cannot retry.
model = FixedTimestampModel(10**15); live = state_at(30_000_000_000, 1, ident, attempt, 3, None)
model.consume_trigger_json(TriggerJson(), live)
wait = model.poll_phase_a(live, FakeTF(upper=29_000_000_000))
rearm = model.rearm_phase_a_query(live)
sent = model.poll_phase_a(state_at(30_020_000_000, 2, ident, attempt, 3, None), FakeTF(upper=30_000_000_000))
model.poll_phase_a(state_at(30_030_000_000, 3, ident, attempt, 3, None), FakeTF(upper=30_000_000_000))
case('fixed_ta_late_tf_send_once', {'wait': 'WAIT_EXACT_TF', 'rearm': True, 'sent': 'PLANNER_REQUESTED_ONCE', 'count': 1,
     't_a': 30_000_000_000, 'request_stamp': 30_020_000_000},
     {'wait': wait, 'rearm': rearm, 'sent': sent, 'count': model.action_request_count,
      't_a': model.t_a_ns, 'request_stamp': model.planner_request_stamp_ns},
     production_baseline=BASELINE_PHASE_A, query_stamps=model.phase_a_queries)

# Wrong request / old generation never creates eligible returned path context.
wrong = planner_result(model, attempt, request_id='old-request')
wrong_state = state_at(30_040_000_000, 4, ident, attempt, 3, None)
wrong_outcome = model.accept_planner_result(wrong, wrong_state)
case('wrong_request_result_rejected', 'REJECTED_WRONG_OR_STALE_PLANNER_RESULT', wrong_outcome,
     path_context_created=model.path_context is not None)
model2 = FixedTimestampModel(10**15); model2.consume_trigger_json(TriggerJson(), live); model2.poll_phase_a(live, FakeTF(upper=30_000_000_000))
stale = planner_result(model2, attempt, identity=Identity(2, 1, 6, 'c' * 64))
stale_outcome = model2.accept_planner_result(stale, live)
case('stale_generation_result_rejected', 'REJECTED_WRONG_OR_STALE_PLANNER_RESULT', stale_outcome,
     path_context_created=model2.path_context is not None)
failed_result = planner_result(model2, attempt, status='FAILED')
failed_outcome = model2.accept_planner_result(failed_result, live)
case('planner_non_success_result_does_not_bind_path', 'REJECTED_WRONG_OR_STALE_PLANNER_RESULT', failed_outcome,
     path_context_created=model2.path_context is not None)

# Correct successful result binds returned path only after request/goal/identity correlation.
model3 = FixedTimestampModel(10**15); live3 = state_at(35_000_000_000, 5, ident, attempt, 3, None)
model3.consume_trigger_json(TriggerJson(), live3); model3.poll_phase_a(live3, FakeTF(upper=35_000_000_000))
path_absent_before_result = model3.path_context is None
accepted = model3.accept_planner_result(planner_result(model3, attempt, path_sequence=22, path_stamp=35_000_000_000), live3)
case('planner_success_correct_request_binds_path_after_result', 'BOUND_RETURNED_PATH_AFTER_MATCHED_SUCCESS', accepted,
     path_absent_before_result=path_absent_before_result, request_id=model3.path_context.request_id,
     goal_id=model3.path_context.goal_id, path_sequence=model3.path_context.path_sequence)

# F2: second capture is an explicit rejection and leaves the first pending value untouched.
model, ident, attempt, path, live = establish_planner_ready(now=40_000_000_000)
s1 = sample_for(path, ident, 40_000_000_000, name='pending-A')
s2 = sample_for(path, ident, 40_010_000_000, name='pending-B', scan_id='scan-B', odom_id='odom-B')
supplier = FakeStateSupplier(live)
first_capture = model.capture_sample(s1, supplier)
pending_before = copy.deepcopy(model.pending)
second_capture = model.capture_sample(s2, supplier)
case('capture_second_snapshot_rejected_without_overwrite', 'REJECTED_PENDING_SNAPSHOT_EXISTS', second_capture,
     first_capture=first_capture, pending_value_identical=(model.pending == pending_before),
     pending_snapshot_id=model.pending['snapshot'].snapshot_id,
     pending_t_vector=model.pending['t_vector_ns'], pending_t_tf=model.pending['t_tf_ns'])

# F3: rollback detected by another entry point invalidates pending and latches terminal failure.
model, ident, attempt, path, live = establish_planner_ready(now=50_000_000_000)
snap = sample_for(path, ident, 50_000_000_000)
supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
rollback_supplier = FakeStateSupplier(state_at(49_000_000_000, 12, ident, attempt, 3, path))
rollback_capture = model.capture_sample(sample_for(path, ident, 49_000_000_000, name='after-rollback'), rollback_supplier)
recovered = state_at(51_000_000_000, 13, ident, attempt, 3, path)
recovered_poll = model.poll_sample(FakeStateSupplier(recovered), FakeTF(upper=51_000_000_000))
case('rollback_entrypoint_invalidates_and_latches_attempt', {'capture': 'REJECTED_TERMINAL_ATTEMPT',
     'pending_cleared': True, 'recovered_poll': 'REJECTED_TERMINAL_ATTEMPT'},
     {'capture': rollback_capture, 'pending_cleared': model.pending is None, 'recovered_poll': recovered_poll},
     failure=model.terminal_failure)

# F4: supplier is read again after lookup; freshness crossing prevents commit.
model, ident, attempt, path, live = establish_planner_ready(now=60_000_000_000)
snap = sample_for(path, ident, 60_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
def age_inputs(): supplier.state = state_at(60_000_000_000 + model.LIMITS['odom'] + 1, 12, ident, attempt, 3, path)
tf = FakeTF(upper=60_000_000_000, on_transform=age_inputs)
outcome = model.poll_sample(supplier, tf)
assert supplier.read_count == 3  # capture, pre-lookup, and post-transform final check
case('lookup_advances_ros_past_freshness_final_check_rejects', 'DISCARDED_FINAL_INPUT', outcome,
     commit_count=len(model.committed), final_ros_ns=supplier.state.ros_ns,
     supplier_reads=supplier.read_count)

# Lookup advances steady time to overall deadline: no commit.
model, ident, attempt, path, live = establish_planner_ready(now=70_000_000_000, steady=1, deadline=100)
snap = sample_for(path, ident, 70_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
def expire_deadline(): supplier.state = state_at(70_000_000_000, 100, ident, attempt, 3, path)
tf = FakeTF(upper=70_000_000_000, on_transform=expire_deadline)
outcome = model.poll_sample(supplier, tf)
case('lookup_advances_steady_to_deadline_no_commit', 'REJECTED_TERMINAL_ATTEMPT', outcome,
     commit_count=len(model.committed), terminal_failure=model.terminal_failure)

# Context/barrier/path change during lookup is observed by final supplier read.
for label, mutate in (
    ('context', lambda m, i, a, p: state_at(80_000_000_001, 12, i, make_attempt(i, a.map_identity, 4), 4, p)),
    ('barrier', lambda m, i, a, p: state_at(80_000_000_001, 12, i, a, 4, p)),
    ('path', lambda m, i, a, p: state_at(80_000_000_001, 12, i, a, 3, PathContext(p.request_id,p.goal_id,p.path_sequence+1,p.reset_epoch,p.runtime_generation,p.map_id,p.map_content_hash,p.path_stamp_ns,p.received_steady_ns,p.expiry_steady_ns)))):
    model, ident, attempt, path, live = establish_planner_ready(now=80_000_000_000)
    snap = sample_for(path, ident, 80_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
    tf = FakeTF(upper=80_000_000_000, on_transform=lambda m=model,i=ident,a=attempt,p=path,fn=mutate: setattr(supplier,'state',fn(m,i,a,p)))
    outcome = model.poll_sample(supplier, tf)
    case('lookup_context_change_' + label, 'DISCARDED_FINAL_CONTEXT', outcome,
         commit_count=len(model.committed), final_ros_ns=supplier.state.ros_ns,
     final_barrier_revision=supplier.state.barrier_revision,
     final_path_sequence=supplier.state.path_context.path_sequence if supplier.state.path_context else None)

# ABA changes must carry a monotonic event barrier revision/path sequence; returned payload cannot restore old event identity.
model, ident, attempt, path, live = establish_planner_ready(now=90_000_000_000)
snap = sample_for(path, ident, 90_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
barrier_trace = []
def barrier_aba():
    supplier.state = state_at(90_000_000_001, 12, ident, attempt, 4, path); barrier_trace.append(4)
    supplier.state = state_at(90_000_000_001, 12, ident, attempt, 5, path); barrier_trace.append(5)
tf = FakeTF(upper=90_000_000_000, on_transform=barrier_aba)
outcome = model.poll_sample(supplier, tf)
case('barrier_changed_then_values_return_revision_invalidates', 'DISCARDED_FINAL_CONTEXT', outcome,
     pinned_revision=3, final_revision=supplier.state.barrier_revision, event_trace=barrier_trace, commit_count=len(model.committed))

# can_transform=true followed by transform exception preserves cause and never commits.
model, ident, attempt, path, live = establish_planner_ready(now=100_000_000_000)
snap = sample_for(path, ident, 100_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
tf = FakeTF(upper=100_000_000_000, transform_error=ExtrapolationException('fake lookup cause'))
outcome = model.poll_sample(supplier, tf)
case('can_transform_true_lookup_exception_no_commit', 'WAIT_TF_LOOKUP_EXCEPTION', outcome,
     can_transform=True, commit_count=len(model.committed), original_cause=model.outcomes[-1])

# Future/post-cutoff input is rejected at acquisition.
model, ident, attempt, path, live = establish_planner_ready(now=110_000_000_000)
supplier = FakeStateSupplier(live)
future = sample_for(path, ident, 110_000_000_001, name='future')
out_future = model.capture_sample(future, supplier)
late_receipt = sample_for(path, ident, 110_000_000_000, name='late-receipt')
late_receipt = InputSnapshot(**{**late_receipt.__dict__, 'receipt_stamp_ns': 110_000_000_001})
out_receipt = model.capture_sample(late_receipt, supplier)
case('phase_b_cutoff_rejects_future_and_post_cutoff_receipt',
     ['REJECTED_INPUT_AT_ACQUISITION', 'REJECTED_INPUT_AT_ACQUISITION'], [out_future, out_receipt])

# Dedup is measurement/lifecycle identity, not snapshot ID or vector cutoff.
model, ident, attempt, path, live = establish_planner_ready(now=120_000_000_000)
supplier = FakeStateSupplier(live)
s1 = sample_for(path, ident, 120_000_000_000, name='id-A', scan_id='same-scan', odom_id='same-odom', receipt_seq=77)
model.capture_sample(s1, supplier); model.poll_sample(supplier, FakeTF(upper=120_000_000_000))
live2 = state_at(120_010_000_000, 20, ident, attempt, 3, path); supplier.state = live2
s2 = sample_for(path, ident, 120_010_000_000, name='id-B', scan_id='same-scan', odom_id='same-odom', receipt_seq=77)
model.capture_sample(s2, supplier); duplicate = model.poll_sample(supplier, FakeTF(upper=120_010_000_000))
case('same_measurements_new_snapshot_id_cutoff_duplicate', 'DISCARDED_DUPLICATE_MEASUREMENT_IDENTITY', duplicate,
     committed_count=len(model.committed))

# Path replacement and path ABA invalidate by authoritative sequence/revision.
model, ident, attempt, path, live = establish_planner_ready(now=130_000_000_000)
snap = sample_for(path, ident, 130_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
path2 = PathContext(path.request_id,path.goal_id,path.path_sequence+2,path.reset_epoch,path.runtime_generation,path.map_id,path.map_content_hash,path.path_stamp_ns,path.received_steady_ns,path.expiry_steady_ns)
def change_path_during_lookup():
    transient = PathContext(path.request_id,path.goal_id,path.path_sequence+1,path.reset_epoch,path.runtime_generation,path.map_id,path.map_content_hash,path.path_stamp_ns,path.received_steady_ns,path.expiry_steady_ns)
    supplier.state = state_at(130_000_000_001, 12, ident, attempt, 3, transient)
    supplier.state = state_at(130_000_000_001, 12, ident, attempt, 3, path2)
outcome = model.poll_sample(supplier, FakeTF(upper=130_000_000_001, on_transform=change_path_during_lookup))
case('path_sequence_changed_then_restored_payload_not_resurrected', 'DISCARDED_FINAL_CONTEXT', outcome,
     commit_count=len(model.committed), sequence_revision=path2.path_sequence)

# Transform request is copied; raw path's original pose stamp survives.
model, ident, attempt, path, live = establish_planner_ready(now=140_000_000_000)
raw = make_path(); raw.poses[1].header.stamp.sec = 2
before = (raw.poses[1].header.stamp.sec, raw.poses[1].header.stamp.nanosec)
production._features_from_path(copy.deepcopy(raw), FakeTF(upper=4_000_000_000), 3_000_000_004)
after = (raw.poses[1].header.stamp.sec, raw.poses[1].header.stamp.nanosec)
case('transform_request_does_not_mutate_raw_path', before, after)

# A returned nonblocking poll permits another executor/action callback before the next poll.
model, ident, attempt, path, live = establish_planner_ready(now=150_000_000_000)
snap = sample_for(path, ident, 150_000_000_000); supplier = FakeStateSupplier(live); model.capture_sample(snap, supplier)
waiting = model.poll_sample(supplier, FakeTF(upper=149_999_999_999))
model.process_action_callback()
completed = model.poll_sample(supplier, FakeTF(upper=150_000_000_000))
case('callbacks_progress_between_nonblocking_polls', {'first':'WAIT_EXACT_TF_SAME_STAMP','callbacks':1,'second':'LOCAL_REFERENCE_COMMITTED'},
     {'first':waiting,'callbacks':model.callback_count,'second':completed})

# Model metadata is declarations, not a behavioral test/case.
DECLARATIONS = {'existing_source_freshness_values_ns': FixedTimestampModel.LIMITS,
                'new_tf_age_skew_expiry_limits': 'NONE_SELECTED',
                'model_not_evaluated': ['81D_acceptance','QoS','evidence_chain','campaign_acceptance','Nav2_runtime','tf2_runtime']}
COVERAGE = {
    'F1_no_path_before_planner_and_match_result': ['startup_without_path_sends_planner_once','phase_a_attempt_context_change_before_action','wrong_request_result_rejected','stale_generation_result_rejected','planner_non_success_result_does_not_bind_path','planner_success_correct_request_binds_path_after_result'],
    'F2_single_pending_snapshot': ['capture_second_snapshot_rejected_without_overwrite'],
    'F3_rollback_terminal_invalidation': ['rollback_entrypoint_invalidates_and_latches_attempt'],
    'F4_final_supplier_recheck': ['lookup_advances_ros_past_freshness_final_check_rejects','lookup_advances_steady_to_deadline_no_commit','lookup_context_change_context','lookup_context_change_barrier','lookup_context_change_path'],
    'clock_trigger_TA_action_once': ['json_trigger_no_header_clock_zero_steady_deadline','fixed_ta_late_tf_send_once','rollback_entrypoint_invalidates_and_latches_attempt'],
    'cutoff_dedup_immutability': ['phase_b_cutoff_rejects_future_and_post_cutoff_receipt','same_measurements_new_snapshot_id_cutoff_duplicate','path_sequence_changed_then_restored_payload_not_resurrected','transform_request_does_not_mutate_raw_path','callbacks_progress_between_nonblocking_polls'],
    'lookup_exception': ['can_transform_true_lookup_exception_no_commit'],
}
assert set(COVERAGE) == {'F1_no_path_before_planner_and_match_result','F2_single_pending_snapshot','F3_rollback_terminal_invalidation','F4_final_supplier_recheck','clock_trigger_TA_action_once','cutoff_dedup_immutability','lookup_exception'}
for req, names in COVERAGE.items():
    assert all(name in CASES for name in names), (req, names)
RESULT = {
    'model_status': 'PROPOSAL_ONLY_NOT_PRODUCTION',
    'baseline_source': {'commit': BASELINE_COMMIT, 'path': str(OBSERVER_REL),
        'resolved_import': str(OBSERVER_SOURCE), 'sha256': OBSERVER_SHA256,
        'methods': ['_Collector._tick()', '_features_from_path()'], 'executed_separately': True},
    'proposed_model': 'temporal state and LocalReference fake cases only',
    'runtime_or_campaign': False,
    'not_evaluated': DECLARATIONS['model_not_evaluated'],
    'declarations': DECLARATIONS,
    'coverage': COVERAGE,
    'behavioral_case_count': len(CASES),
    'cases': list(CASES.values()),
}
OUT = Path(__file__).with_name('offline_validation_results.json')
OUT.write_text(json.dumps(RESULT, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'behavioral_case_count': len(CASES), 'baseline_commit': BASELINE_COMMIT,
                  'source_sha256': OBSERVER_SHA256, 'result': 'PASS'}, sort_keys=True))
