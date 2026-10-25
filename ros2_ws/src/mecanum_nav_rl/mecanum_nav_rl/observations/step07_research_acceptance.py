"""Pure, deterministic Step 7 research acceptance core.

No ROS, file, repository, or wall-clock access is allowed here. Adapters pass
typed facts and both clock domains explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable, Iterable, Mapping

import numpy as np


@dataclass(frozen=True, slots=True)
class Context:
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str


@dataclass(frozen=True, slots=True)
class StampedFact:
    stamp_ns: int
    received_steady_ns: int
    frame_id: str
    value: Any
    context: Context
    identity: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class PathSnapshot:
    poses_xy: tuple[tuple[float, float], ...]
    request_id: str
    goal_xy: tuple[float, float]
    map_id: str
    map_content_hash: str
    context: Context
    received_steady_ns: int
    expires_steady_ns: int


@dataclass(frozen=True, slots=True)
class ObservationSample:
    vector: np.ndarray
    scan_stamp_ns: int
    odom_stamp_ns: int
    scan_receive_ns: int
    odom_receive_ns: int
    tf_stamp_ns: int
    reference_receive_ns: int
    receipt_stamp_ns: int
    receipt_sequence: int
    context: Context
    barrier_sequence: int

    def __post_init__(self) -> None:
        if (type(self.vector) is not np.ndarray or self.vector.dtype != np.float32
                or self.vector.shape != (81,) or self.vector.flags.writeable
                or not np.isfinite(self.vector).all()):
            raise ValueError("Observation sample requires immutable finite float32[81]")


class BoundedFacts:
    """Ordered, bounded, exact-identity input stream with duplicate rejection."""

    def __init__(self, capacity: int = 64) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive int")
        self.capacity = capacity
        self._facts: list[StampedFact] = []
        self._ids: set[tuple[Any, ...]] = set()

    def insert(self, fact: StampedFact) -> bool:
        if not isinstance(fact, StampedFact):
            raise TypeError("fact must be StampedFact")
        key = fact.identity or (fact.stamp_ns, fact.context)
        if key in self._ids:
            return False
        self._ids.add(key)
        index = 0
        while index < len(self._facts) and self._facts[index].stamp_ns <= fact.stamp_ns:
            index += 1
        self._facts.insert(index, fact)
        if len(self._facts) > self.capacity:
            removed = self._facts.pop(0)
            self._ids.discard(removed.identity or (removed.stamp_ns, removed.context))
        return True

    def clear(self) -> None:
        self._facts.clear()
        self._ids.clear()

    def eligible(self, *, cutoff_ns: int, now_steady_ns: int,
                 freshness_ns: int, after_barrier_ns: int,
                 context: Context) -> tuple[StampedFact, ...]:
        return tuple(f for f in self._facts
                     if f.context == context and after_barrier_ns < f.stamp_ns <= cutoff_ns
                     and 0 <= now_steady_ns - f.received_steady_ns <= freshness_ns)


class ClockRollbackGuard:
    """Once simulation time rolls back, invalidate buffers and fail this attempt."""

    def __init__(self, clearers: Iterable[Callable[[], None]] = ()) -> None:
        self._last_ns: int | None = None
        self._failed = False
        self._clearers = tuple(clearers)

    def observe(self, ros_time_ns: int) -> bool:
        if type(ros_time_ns) is not int or ros_time_ns <= 0:
            return False
        if self._failed:
            return False
        if self._last_ns is not None and ros_time_ns < self._last_ns:
            self._failed = True
            for clear in self._clearers:
                clear()
            return False
        self._last_ns = ros_time_ns
        return True

    @property
    def failed(self) -> bool:
        return self._failed


def select_actual_receipt(receipts: Iterable[StampedFact], *, cutoff_ns: int,
                          now_steady_ns: int, freshness_ns: int,
                          after_barrier_ns: int, context: Context,
                          accepted_sources: tuple[int, ...] = (1, 2, 3, 4)) -> StampedFact | None:
    """Admit a real final-publisher receipt after the barrier and capture cut."""
    eligible = []
    for receipt in receipts:
        if (receipt.context != context or not after_barrier_ns < receipt.stamp_ns <= cutoff_ns
                or not 0 <= now_steady_ns-receipt.received_steady_ns <= freshness_ns
                or not isinstance(receipt.value, Mapping)):
            continue
        command = receipt.value.get("command")
        sequence = receipt.value.get("sequence")
        source = receipt.value.get("source")
        if (type(sequence) is not int or sequence <= 0 or type(source) is not int
                or source not in accepted_sources or not isinstance(command, tuple)
                or len(command) != 3 or not all(math.isfinite(float(x)) for x in command)):
            continue
        eligible.append(receipt)
    return max(eligible, key=lambda fact: (fact.stamp_ns, fact.value["sequence"])) if eligible else None


def select_scan_odom_pair(
    scans: Iterable[StampedFact], odometry: Iterable[StampedFact], *,
    cutoff_ns: int, now_steady_ns: int, scan_freshness_ns: int,
    odom_freshness_ns: int, sync_tolerance_ns: int,
    scan_barrier_ns: int, odom_barrier_ns: int, context: Context,
    used_pairs: set[tuple[int, int]],
) -> tuple[StampedFact, StampedFact] | None:
    """Select the latest new, synchronized, post-barrier actual pair."""
    eligible_scan = [f for f in scans if f.context == context
                     and scan_barrier_ns < f.stamp_ns <= cutoff_ns
                     and 0 <= now_steady_ns - f.received_steady_ns <= scan_freshness_ns]
    eligible_odom = [f for f in odometry if f.context == context
                     and odom_barrier_ns < f.stamp_ns <= cutoff_ns
                     and 0 <= now_steady_ns - f.received_steady_ns <= odom_freshness_ns]
    candidates = []
    for scan in eligible_scan:
        for odom in eligible_odom:
            pair = (scan.stamp_ns, odom.stamp_ns)
            if abs(scan.stamp_ns - odom.stamp_ns) <= sync_tolerance_ns and pair not in used_pairs:
                candidates.append((max(pair), pair, scan, odom))
    if not candidates:
        return None
    _, pair, scan, odom = max(candidates, key=lambda item: (item[0], item[1]))
    used_pairs.add(pair)
    return scan, odom


def lidar_sectors(ranges: Iterable[float], *, angle_min: float, angle_increment: float,
                  range_min: float, range_max: float, frame_id: str,
                  expected_frame: str = "lidar_frame") -> tuple[float, ...]:
    """Produce 72 angular-sector minima normalized to [0, 1]."""
    values = tuple(float(v) for v in ranges)
    if (frame_id != expected_frame or not values or len(values) < 2
            or not all(math.isfinite(v) for v in (angle_min, angle_increment, range_min, range_max))
            or angle_increment <= 0 or range_min < 0 or range_max <= range_min):
        raise ValueError("invalid scan frame/geometry/range metadata")
    bins: list[list[float]] = [[] for _ in range(72)]
    for i, raw in enumerate(values):
        angle = (angle_min + i * angle_increment + math.pi) % (2 * math.pi)
        sector = min(71, int(angle / (2 * math.pi) * 72))
        if math.isnan(raw) or raw == -math.inf or raw <= 0 or (math.isfinite(raw) and raw < range_min):
            raise ValueError("scan contains invalid required range data")
        if raw == math.inf or raw > range_max:
            distance = range_max  # valid no-return under the LaserScan range contract
        else:
            distance = raw
        bins[sector].append(distance)
    if any(not bucket for bucket in bins):
        raise ValueError("scan does not provide at least one valid beam per angular sector")
    return tuple(min(bucket) / range_max for bucket in bins)


def normalized_twist(vx: float, vy: float, wz: float, *, scales: tuple[float, float, float]
                     ) -> tuple[float, float, float]:
    values = (float(vx), float(vy), float(wz))
    if not all(math.isfinite(v) for v in values) or len(scales) != 3:
        raise ValueError("measured twist must be finite")
    if any(abs(v) > s for v, s in zip(values, scales)):
        raise ValueError("measured twist is outside validity envelope")
    return tuple(v / s for v, s in zip(values, scales))


def project_lookahead(path: PathSnapshot, *, robot_xy: tuple[float, float],
                      previous_arc_m: float | None, now_steady_ns: int,
                      lookahead_m: float = 0.50, backtrack_m: float = 0.10,
                      forward_window_m: float = 1.0,
                      max_deviation_m: float = 0.50) -> tuple[float, float, float]:
    """Deterministic arc-length projection constrained to the prior branch."""
    if now_steady_ns > path.expires_steady_ns or len(path.poses_xy) < 2:
        raise ValueError("path expired or empty")
    pts = path.poses_xy
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        if not math.isfinite(d):
            raise ValueError("path contains non-finite pose")
        lengths.append(lengths[-1] + d)
    if lengths[-1] <= 0:
        raise ValueError("path has zero arc length")
    lo = 0.0 if previous_arc_m is None else max(0.0, previous_arc_m - backtrack_m)
    hi = lengths[-1] if previous_arc_m is None else min(lengths[-1], previous_arc_m + forward_window_m)
    projections = []
    rx, ry = robot_xy
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        seg = lengths[i + 1] - lengths[i]
        if seg == 0:
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0.0, min(1.0, ((rx-a[0])*dx + (ry-a[1])*dy) / (seg*seg)))
        arc = lengths[i] + t * seg
        if lo <= arc <= hi:
            xy = (a[0] + t*dx, a[1] + t*dy)
            projections.append((math.dist((rx, ry), xy), arc, i))
    if not projections:
        raise ValueError("path progress is outside bounded search window")
    deviation, progress, _ = min(projections, key=lambda x: (x[0], x[1], x[2]))
    if deviation > max_deviation_m:
        raise ValueError("robot deviated from path")
    target_arc = min(lengths[-1], progress + lookahead_m)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if lengths[i] <= target_arc <= lengths[i + 1] and lengths[i + 1] > lengths[i]:
            t = (target_arc - lengths[i]) / (lengths[i + 1] - lengths[i])
            x, y = a[0] + t*(b[0]-a[0]), a[1] + t*(b[1]-a[1])
            dx, dy = x-rx, y-ry
            distance = math.hypot(dx, dy)
            bearing = math.atan2(dy, dx)
            return progress, min(distance / 5.0, 1.0), bearing
    raise ValueError("lookahead projection could not be resolved")


def make_observation(scan_values: Iterable[float], *, scan_angle_min: float,
                     scan_angle_increment: float, scan_range_min: float,
                     scan_range_max: float, scan_frame: str,
                     reference_features: tuple[float, float, float],
                     measured_twist: tuple[float, float, float],
                     previous_final_command: tuple[float, float, float],
                     twist_scales: tuple[float, float, float],
                     context: Context) -> np.ndarray:
    sectors = lidar_sectors(scan_values, angle_min=scan_angle_min,
                            angle_increment=scan_angle_increment,
                            range_min=scan_range_min, range_max=scan_range_max,
                            frame_id=scan_frame)
    twist = normalized_twist(*measured_twist, scales=twist_scales)
    command = normalized_twist(*previous_final_command, scales=twist_scales)
    if len(reference_features) != 3 or not all(math.isfinite(v) for v in reference_features):
        raise ValueError("LocalReference must have three finite base_link features")
    if not all(0.0 <= v <= 1.0 for v in reference_features[:1]):
        raise ValueError("LocalReference distance feature is invalid")
    from .v3_observation_assembler import assemble_observation
    from .v3_snapshot_types import (
        BASE_FRAME, FRAME_TF_CONTRACT_ID, LIDAR_CONTRACT_ID, LIDAR_FRAME,
        LIFECYCLE_BARRIER_CONTRACT_ID, LOCAL_REFERENCE_CONTRACT_ID,
        MEASURED_TWIST_CONTRACT_ID, ActiveLifecycleConfigContext,
        FinalIssuedReceiptContext, LidarSnapshot, LocalReferenceSnapshot,
        MeasuredTwistSnapshot,
    )
    typed_context = ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID,
        context.episode_generation, context.reset_epoch, context.runtime_generation,
        context.config_hash)
    lidar = LidarSnapshot(LIDAR_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
        context.episode_generation, context.reset_epoch, context.runtime_generation,
        context.config_hash, LIDAR_FRAME, sectors)
    reference = LocalReferenceSnapshot(LOCAL_REFERENCE_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
        context.episode_generation, context.reset_epoch, context.runtime_generation,
        context.config_hash, BASE_FRAME, tuple(reference_features))
    measured = MeasuredTwistSnapshot(MEASURED_TWIST_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
        context.episode_generation, context.reset_epoch, context.runtime_generation,
        context.config_hash, BASE_FRAME, twist)
    receipt = FinalIssuedReceiptContext(LIFECYCLE_BARRIER_CONTRACT_ID, FRAME_TF_CONTRACT_ID,
        context.episode_generation, context.reset_epoch, context.runtime_generation,
        context.config_hash, BASE_FRAME, command)
    from .v3_snapshot_validation import validate_observation_inputs
    token = validate_observation_inputs(context=typed_context, lidar=lidar,
        local_reference=reference, measured_twist=measured, receipt=receipt)
    if token is None:
        raise ValueError("V3 Observation context/input validation failed")
    assembly = assemble_observation(token)
    if not assembly.ready or assembly.vector is None:
        raise ValueError("V3 Observation assembler rejected the snapshot")
    return assembly.vector


def localization_health(samples: Iterable[Mapping[str, Any]], *, now_ros_ns: int,
                        max_age_ns: int, now_steady_ns: int,
                        max_covariance: float = 0.25) -> tuple[bool, str | None]:
    """Validate map pose, covariance, freshness, and bounded inter-sample jumps."""
    values = tuple(samples)
    if not values:
        return False, "NO_LOCALIZATION_SAMPLE"
    current = values[-1]
    if current.get("frame_id") != "map":
        return False, "LOCALIZATION_FRAME_INVALID"
    stamp = current.get("stamp_ns")
    received = current.get("received_steady_ns")
    if (type(stamp) is not int or stamp <= 0 or now_ros_ns < stamp
            or now_ros_ns-stamp > max_age_ns or type(received) is not int
            or now_steady_ns < received or now_steady_ns-received > max_age_ns):
        return False, "LOCALIZATION_STALE_OR_FUTURE"
    pose = current.get("pose")
    covariance = current.get("covariance")
    if (not isinstance(pose, (tuple, list)) or len(pose) != 3
            or not all(math.isfinite(float(x)) for x in pose)
            or not isinstance(covariance, (tuple, list)) or len(covariance) != 3
            or any(not math.isfinite(float(x)) or x < 0 or x > max_covariance for x in covariance)):
        return False, "LOCALIZATION_VALUE_OR_COVARIANCE_INVALID"
    if len(values) > 1:
        previous = values[-2]
        dt = (stamp - previous["stamp_ns"]) / 1e9
        if dt <= 0:
            return False, "LOCALIZATION_TIMESTAMP_NOT_ADVANCING"
        distance = math.hypot(pose[0]-previous["pose"][0], pose[1]-previous["pose"][1])
        yaw = abs((pose[2]-previous["pose"][2]+math.pi) % (2*math.pi)-math.pi)
        if distance > 0.50 + 0.35*dt:
            return False, "LOCALIZATION_TRANSLATION_JUMP"
        if yaw > 0.50 + 1.0*dt:
            return False, "LOCALIZATION_YAW_JUMP"
    return True, None


def mission_settled(samples: Iterable[Mapping[str, Any]], *, now_ros_ns: int,
                    settle_ns: int = 1_000_000_000, xy_tolerance_m: float = 0.15,
                    linear_speed_mps: float = 0.03,
                    angular_speed_radps: float = 0.05) -> bool:
    """Require fresh valid pose/twist/localization throughout ROS-time settle."""
    values = tuple(samples)
    if len(values) < 2:
        return False
    end = values[-1]
    start = end.get("settle_start_ros_ns")
    if type(start) is not int or now_ros_ns-start < settle_ns:
        return False
    for sample in values:
        if sample.get("stamp_ns", now_ros_ns+1) < start:
            continue
        x, y = sample.get("position_xy", (math.inf, math.inf))
        vx, vy, wz = sample.get("twist", (math.inf, math.inf, math.inf))
        if (math.hypot(x+4.0, y) > xy_tolerance_m
                or math.hypot(vx, vy) > linear_speed_mps
                or abs(wz) > angular_speed_radps
                or sample.get("localization_valid") is not True
                or sample.get("fresh") is not True):
            return False
    return True


def evaluate_a1_a10(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Pure A1-A10 report; missing/unmeasured facts always evaluate FAIL."""
    required = tuple(f"A{i}" for i in range(1, 11))
    results = {}
    for key in required:
        item = facts.get(key)
        if not isinstance(item, Mapping):
            results[key] = {"status": "FAIL", "reason": "NOT_EVALUATED_DUE_TO_MISSING_FACT"}
        else:
            passed = item.get("pass") is True
            results[key] = {"status": "PASS" if passed else "FAIL",
                            "reason": str(item.get("reason") or ("ACCEPTED" if passed else "REJECTED")),
                            "measured": item.get("measured")}
    overall = "PASS" if all(v["status"] == "PASS" for v in results.values()) else "FAIL"
    return {"overall": overall, "acceptance": results,
            "primary_failure": facts.get("primary_failure"),
            "warnings": list(facts.get("warnings", ())),
            "valid_observations": list(facts.get("valid_observations", ()))[:5]}
