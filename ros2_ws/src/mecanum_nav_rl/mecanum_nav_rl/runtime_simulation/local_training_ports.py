"""Trusted bridge between simulator Ground Truth and policy-safe data."""
from __future__ import annotations

from dataclasses import dataclass

from mecanum_nav_rl.core.types import Pose2D, VelocityCommand
from mecanum_nav_rl.simulation.simulated_odometry import (
    GroundTruthSample,
    SimulatedOdometryEmulator,
    SimulatedOdometryNoiseConfig,
    SimulatedOdometrySnapshot,
)


@dataclass(frozen=True)
class GroundTruthPortSample:
    """Internal trusted port: world pose and measured base twist only."""

    stamp_ns: int
    world_x_m: float
    world_y_m: float
    world_yaw_rad: float
    body_vx_mps: float
    body_vy_mps: float
    body_wz_radps: float


@dataclass(frozen=True)
class PolicySafeOdometryPort:
    """No field retains a GroundTruthPortSample reference."""

    snapshot: SimulatedOdometrySnapshot
    source_sequence: int


class SimulatedOdometryPort:
    """Pass trusted samples through the B1 noisy emulator."""

    def __init__(
        self, emulator: SimulatedOdometryEmulator | None = None,
    ) -> None:
        """Bind an emulator, creating the standard emulator if omitted."""
        self._emulator = emulator or SimulatedOdometryEmulator()
        self._last_output: PolicySafeOdometryPort | None = None

    def reset(self, seed: int, config: SimulatedOdometryNoiseConfig) -> None:
        """Reset emulator state with the requested seed and profile."""
        self._emulator.reset(seed, config)
        self._last_output = None

    def accept_ground_truth(
        self, sample: GroundTruthPortSample,
    ) -> PolicySafeOdometryPort:
        """Convert one trusted sample into a policy-safe output snapshot."""
        internal = GroundTruthSample(
            sample.stamp_ns,
            Pose2D(
                sample.world_x_m, sample.world_y_m, sample.world_yaw_rad,
            ),
            VelocityCommand(
                sample.body_vx_mps, sample.body_vy_mps, sample.body_wz_radps,
            ),
        )
        snapshot = self._emulator.step(internal)
        result = PolicySafeOdometryPort(
            snapshot=snapshot, source_sequence=snapshot.sequence,
        )
        self._last_output = result
        return result

    @property
    def last_policy_safe_output(self) -> PolicySafeOdometryPort | None:
        """Return the latest policy-safe output, if one exists."""
        return self._last_output
