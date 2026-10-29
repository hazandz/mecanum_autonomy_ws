"""Policy-safe LOCAL_TRAINING reference from scenario goal and noisy odometry."""
from __future__ import annotations
from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, sin
from numbers import Real
import numpy as np
from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.simulation.simulated_odometry import SimulatedOdometrySnapshot, SimulatedOdometryStatus

@dataclass(frozen=True, slots=True)

class LocalTrainingGoal:
    x_m: float
    y_m: float
    scenario_frame_id: str
    scenario_identity: str

    def __post_init__(self) -> None:
        _finite('goal.x_m', self.x_m)
        _finite('goal.y_m', self.y_m)
        _identifier('scenario_frame_id', self.scenario_frame_id)
        _identifier('scenario_identity', self.scenario_identity)

@dataclass(frozen=True, slots=True)

class NoisyOdometryContext:
    """Copied measurement scalars; has no field capable of retaining raw GT."""
    snapshot: SimulatedOdometrySnapshot
    lifecycle: EpisodeLifecycleIdentity
    scenario_frame_id: str
    scenario_identity: str
    received_steady_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, SimulatedOdometrySnapshot):
            raise TypeError('snapshot must be a SimulatedOdometrySnapshot')
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        _identifier('scenario_frame_id', self.scenario_frame_id)
        _identifier('scenario_identity', self.scenario_identity)
        _uint('received_steady_ns', self.received_steady_ns)

@dataclass(frozen=True, slots=True)

class LocalReferenceResult:
    ready: bool
    reason: str | None = None
    features: tuple[np.float32, np.float32, np.float32] | None = None
    timestamp_ns: int | None = None
    sequence: int | None = None
    lifecycle: EpisodeLifecycleIdentity | None = None
    scenario_identity: str | None = None
    frame_id: str | None = None
    source: str = 'LOCAL_TASK_GOAL'

    def __post_init__(self) -> None:
        if type(self.ready) is not bool:
            raise TypeError('ready must be bool')
        if not self.ready:
            if any((v is not None for v in (self.features, self.timestamp_ns,
                self.sequence, self.lifecycle, self.scenario_identity, self.frame_id))):
                raise ValueError('non-ready reference cannot carry feature data')
            return
        if type(self.features) is not tuple or len(self.features) != 3:
            raise ValueError('ready reference requires three ordered features')
        if any((type(v) is not np.float32 or not np.isfinite(v) for v in self.features)):
            raise ValueError('reference features must be finite float32 values')
        _uint('timestamp_ns', self.timestamp_ns)
        _uint('sequence', self.sequence)
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise ValueError('ready reference requires lifecycle provenance')
        _identifier('scenario_identity', self.scenario_identity)
        if self.frame_id != 'base_link':
            raise ValueError('LOCAL_TRAINING reference features must be base_link-relative')
        if self.source != 'LOCAL_TASK_GOAL':
            raise ValueError('LOCAL_TRAINING reference source must be LOCAL_TASK_GOAL')

def build_local_training_reference(goal: LocalTrainingGoal,
    odometry: NoisyOdometryContext, *, evaluation_ros_now_ns: int, evaluation_steady_now_ns: int, scan_timestamp_ns: int, scan_sequence: int, max_ros_age_ns: int=250000000, max_steady_age_ns: int=250000000) -> LocalReferenceResult:
    """Compute normalized distance/sin/cos at one exact VALID noisy snapshot."""
    try:
        if not isinstance(goal, LocalTrainingGoal) or not isinstance(odometry,
            NoisyOdometryContext):
            raise TypeError('goal and odometry must be typed scalar context')
        for name, value in (('evaluation_ros_now_ns', evaluation_ros_now_ns),
            ('evaluation_steady_now_ns',
            evaluation_steady_now_ns), ('scan_timestamp_ns', scan_timestamp_ns), ('scan_sequence', scan_sequence), ('max_ros_age_ns', max_ros_age_ns), ('max_steady_age_ns', max_steady_age_ns)):
            _uint(name, value)
        sample = odometry.snapshot
        if sample.status is not SimulatedOdometryStatus.VALID or sample.measurement is None:
            raise ValueError('noisy odometry is not VALID')
        if odometry.scenario_frame_id != goal.scenario_frame_id:
            raise ValueError('goal and noisy odometry scenario frames differ')
        if odometry.scenario_identity != goal.scenario_identity:
            raise ValueError('goal and noisy odometry scenario identities differ')
        if sample.timestamp_ns != scan_timestamp_ns or sample.sequence != scan_sequence:
            raise ValueError('scan and noisy odometry must share exact timestamp and sequence')
        if sample.timestamp_ns > evaluation_ros_now_ns:
            raise ValueError('noisy odometry timestamp is future')
        if evaluation_ros_now_ns - sample.timestamp_ns > max_ros_age_ns:
            raise ValueError('noisy odometry is stale in ROS time')
        if evaluation_steady_now_ns < odometry.received_steady_ns:
            raise ValueError('noisy odometry steady receive time is future')
        if evaluation_steady_now_ns - odometry.received_steady_ns > max_steady_age_ns:
            raise ValueError('noisy odometry is stale in steady time')
        pose = sample.measurement
        dx, dy = (goal.x_m - pose.x_m, goal.y_m - pose.y_m)
        c, s = (cos(pose.yaw_rad), sin(pose.yaw_rad))
        bx, by = (c * dx + s * dy, -s * dx + c * dy)
        distance = hypot(bx, by)
        bearing = 0.0 if distance == 0.0 else atan2(by, bx)
        features = (np.float32(min(distance / 10.0, 1.0)),
            np.float32(sin(bearing)), np.float32(cos(bearing)))
        if any((not np.isfinite(value) for value in features)):
            raise ValueError('local reference calculation is non-finite')
        return LocalReferenceResult(True, features=features,
            timestamp_ns=sample.timestamp_ns, sequence=sample.sequence, lifecycle=odometry.lifecycle, scenario_identity=odometry.scenario_identity, frame_id='base_link')
    except (TypeError, ValueError, OverflowError) as error:
        return LocalReferenceResult(False, reason=str(error))

def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value,
        Real) or (not isfinite(float(value))):
        raise ValueError(f'{name} must be finite')
    return float(value)

def _uint(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a non-negative integer')
    return value

def _identifier(name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f'{name} must be a non-empty trimmed string')
__all__ = ('LocalReferenceResult', 'LocalTrainingGoal', 'NoisyOdometryContext',
    'build_local_training_reference')
