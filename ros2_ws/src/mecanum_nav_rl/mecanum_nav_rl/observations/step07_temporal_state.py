"""Pure Run005 temporal state machine; no ROS, filesystem, or action imports."""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any


@dataclass(frozen=True)
class AttemptContext:
    goal_intent: str
    config_hash: str
    map_id: str
    map_sha256: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    barrier_sequence: int

    def valid(self) -> bool:
        return (bool(self.goal_intent) and len(self.config_hash) == 64
                and bool(self.map_id) and len(self.map_sha256) == 64
                and min(self.episode_generation, self.reset_epoch,
                        self.runtime_generation, self.barrier_sequence) >= 0)


@dataclass(frozen=True)
class PathContext:
    request_uuid: str
    goal_intent: str
    path_sequence: int
    receipt_steady_ns: int
    expiry_steady_ns: int
    frame_id: str
    poses: tuple[Any, ...]
    context: AttemptContext


@dataclass(frozen=True)
class PendingSnapshot:
    t_vector_ns: int
    t_tf_ns: int
    steady_acquired_ns: int
    measurement_identity: tuple[Any, ...]
    context: AttemptContext
    input_stamps_ns: tuple[int, ...]
    input_age_limits_ns: tuple[int, ...]
    correlation_records: tuple[Any, ...]
    payload: Any


class Run005TemporalAttempt:
    """Fail-closed temporal coordinator used by the production collector."""

    def __init__(self, *, steady_deadline_ns: int, max_odom_age_ns: int = 250_000_000):
        if type(steady_deadline_ns) is not int or steady_deadline_ns <= 0:
            raise ValueError("RUN005_STEADY_DEADLINE_INVALID")
        if type(max_odom_age_ns) is not int or max_odom_age_ns <= 0:
            raise ValueError("RUN005_ODOM_AGE_POLICY_INVALID")
        self.deadline_ns = steady_deadline_ns
        self.max_odom_age_ns = max_odom_age_ns
        self.t_a_ns: int | None = None
        self.context: AttemptContext | None = None
        self.planner_sent = False
        self.planner_uuid: str | None = None
        self.planner_send_ns: int | None = None
        self.path: PathContext | None = None
        self.pending: PendingSnapshot | None = None
        self.terminal_failure: str | None = None
        self._last_ros_ns: int | None = None
        self._measurement_ids: set[tuple[Any, ...]] = set()
        self._sample_stamps: list[int] = []

    def observe_time(self, ros_ns: int | None, steady_ns: int) -> bool:
        if self.terminal_failure:
            return False
        if type(steady_ns) is not int or steady_ns >= self.deadline_ns:
            self.invalidate("CAMPAIGN_STEADY_DEADLINE_EXPIRED")
            return False
        if ros_ns is not None:
            if type(ros_ns) is not int or ros_ns < 0:
                self.invalidate("ROS_CLOCK_INVALID")
                return False
            if self._last_ros_ns is not None and ros_ns < self._last_ros_ns:
                self.pending = None
                self.invalidate("ROS_CLOCK_ROLLBACK")
                return False
            self._last_ros_ns = ros_ns
        return True

    def consume_trigger(self, *, valid: bool, ros_ns: int | None, steady_ns: int,
                        context: AttemptContext | None) -> str:
        if not self.observe_time(ros_ns, steady_ns):
            return self.terminal_failure or "TERMINAL_FAILURE"
        if self.t_a_ns is not None:
            return "PINNED"
        if not valid:
            return "TRIGGER_NOT_VALID"
        if ros_ns is None or ros_ns <= 0:
            return "WAIT_VALID_ROS_CLOCK"
        if context is None or not context.valid():
            self.invalidate("ATTEMPT_CONTEXT_MISSING_OR_INVALID")
            return self.terminal_failure
        self.t_a_ns = ros_ns
        self.context = context
        return "PINNED"

    def poll_prerequisite_tf(self, *, available: bool, ros_ns: int | None,
                             steady_ns: int, context: AttemptContext | None,
                             query_error: str | None = None) -> str:
        if not self.observe_time(ros_ns, steady_ns):
            return self.terminal_failure or "TERMINAL_FAILURE"
        if self.t_a_ns is None or self.context is None:
            return "NOT_PINNED"
        if context != self.context:
            self.invalidate("ATTEMPT_CONTEXT_CHANGED_BEFORE_PLANNER")
            return self.terminal_failure
        if query_error:
            return "TF_QUERY_PENDING"
        if not available:
            return "TF_QUERY_PENDING"
        if self.planner_sent:
            return "PLANNER_ALREADY_SENT"
        return "SEND_PLANNER_ONCE"

    def mark_planner_sent(self, request_uuid: str, send_ros_ns: int) -> None:
        if self.terminal_failure or self.t_a_ns is None or self.planner_sent:
            raise ValueError("RUN005_PLANNER_ACTION_CARDINALITY_OR_STATE_INVALID")
        if not request_uuid or type(send_ros_ns) is not int or send_ros_ns <= 0:
            raise ValueError("RUN005_PLANNER_REQUEST_IDENTITY_INVALID")
        self.planner_sent = True
        self.planner_uuid = request_uuid
        self.planner_send_ns = send_ros_ns

    def admit_path(self, *, request_uuid: str, result_status: str, frame_id: str,
                   poses: tuple[Any, ...], receipt_steady_ns: int,
                   campaign_deadline_ns: int, context: AttemptContext | None) -> PathContext:
        if (self.terminal_failure or self.context is None or not self.planner_sent
                or request_uuid != self.planner_uuid or context != self.context
                or result_status != "SUCCEEDED" or frame_id != "map" or len(poses) < 2):
            raise ValueError("RUN005_PATH_RESULT_IDENTITY_OR_CONTENT_INVALID")
        if type(receipt_steady_ns) is not int or receipt_steady_ns >= self.deadline_ns:
            self.invalidate("RUN005_PATH_RECEIPT_AFTER_DEADLINE")
            raise ValueError(self.terminal_failure)
        sequence = 1 if self.path is None else self.path.path_sequence + 1
        path = PathContext(request_uuid, self.context.goal_intent, sequence,
                           receipt_steady_ns, min(campaign_deadline_ns, self.deadline_ns),
                           frame_id, deepcopy(tuple(poses)), self.context)
        self.path = path
        return path

    def acquire_snapshot(self, *, t_vector_ns: int, t_tf_ns: int, steady_ns: int,
                         measurement_identity: tuple[Any, ...],
                         context: AttemptContext, input_stamps_ns: tuple[int, ...],
                         correlation_records: tuple[Any, ...], payload: Any,
                         input_age_limits_ns: tuple[int, ...] | None = None) -> PendingSnapshot:
        if self.terminal_failure:
            raise ValueError(self.terminal_failure)
        if self.pending is not None:
            raise ValueError("RUN005_PENDING_SNAPSHOT_EXISTS")
        if self.context is None or context != self.context:
            raise ValueError("RUN005_SNAPSHOT_CONTEXT_MISMATCH")
        if not measurement_identity or measurement_identity in self._measurement_ids:
            raise ValueError("RUN005_MEASUREMENT_IDENTITY_DUPLICATE_OR_MISSING")
        if type(t_vector_ns) is not int or t_vector_ns <= 0 or type(t_tf_ns) is not int or t_tf_ns <= 0:
            raise ValueError("RUN005_SNAPSHOT_TIMESTAMP_INVALID")
        if t_tf_ns > t_vector_ns or any(type(s) is not int or s <= 0 or s > t_vector_ns for s in input_stamps_ns):
            raise ValueError("RUN005_SNAPSHOT_CUTOFF_ORDER_INVALID")
        if not input_stamps_ns or t_tf_ns != input_stamps_ns[0]:
            raise ValueError("RUN005_TF_ODOMETRY_STAMP_BINDING_INVALID")
        limits = input_age_limits_ns or tuple(self.max_odom_age_ns for _ in input_stamps_ns)
        if len(limits) != len(input_stamps_ns) or any(type(x) is not int or x <= 0 for x in limits):
            raise ValueError("RUN005_INPUT_FRESHNESS_POLICY_INVALID")
        if any(t_vector_ns - stamp > limit for stamp, limit in zip(input_stamps_ns, limits)):
            raise ValueError("RUN005_SNAPSHOT_STALE_AT_ACQUISITION")
        self.pending = PendingSnapshot(t_vector_ns, t_tf_ns, steady_ns,
            tuple(measurement_identity), context, tuple(input_stamps_ns),
            tuple(limits), tuple(correlation_records), payload)
        return self.pending

    def commit_snapshot(self, *, ros_ns: int, steady_ns: int,
                        context: AttemptContext | None,
                        lookup_succeeded: bool, lookup_exception: str | None = None) -> PendingSnapshot:
        pending = self.pending
        if pending is None:
            raise ValueError("RUN005_PENDING_SNAPSHOT_MISSING")
        if not self.observe_time(ros_ns, steady_ns):
            raise ValueError(self.terminal_failure)
        if lookup_exception:
            raise ValueError("RUN005_TF_LOOKUP_EXCEPTION:" + lookup_exception)
        if not lookup_succeeded:
            raise ValueError("RUN005_EXACT_TF_UNAVAILABLE")
        if context != pending.context:
            self.pending = None
            raise ValueError("RUN005_COMMIT_CONTEXT_CHANGED")
        if steady_ns >= self.deadline_ns:
            self.pending = None
            self.invalidate("CAMPAIGN_STEADY_DEADLINE_EXPIRED")
            raise ValueError(self.terminal_failure)
        if ros_ns < pending.t_tf_ns or ros_ns - pending.t_tf_ns > self.max_odom_age_ns:
            self.pending = None
            raise ValueError("RUN005_SNAPSHOT_STALE_AT_COMMIT")
        if any(stamp > pending.t_vector_ns or ros_ns < stamp
               or ros_ns - stamp > limit for stamp, limit in
               zip(pending.input_stamps_ns, pending.input_age_limits_ns)):
            self.pending = None
            raise ValueError("RUN005_INPUT_FRESHNESS_OR_CUTOFF_FAILED_AT_COMMIT")
        if self._sample_stamps and pending.t_vector_ns <= self._sample_stamps[-1]:
            self.pending = None
            raise ValueError("RUN005_VECTOR_TIMESTAMP_NOT_INCREASING")
        if pending.measurement_identity in self._measurement_ids:
            self.pending = None
            raise ValueError("RUN005_MEASUREMENT_IDENTITY_DUPLICATE")
        self._measurement_ids.add(pending.measurement_identity)
        self._sample_stamps.append(pending.t_vector_ns)
        self.pending = None
        return pending

    def invalidate(self, reason: str) -> None:
        if self.terminal_failure is None:
            self.terminal_failure = reason
        self.pending = None
        self.path = None
