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

from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl

BACKEND_CONTROL_ENDPOINT = '/mecanum/local_training/backend_control'


class LocalTrainingBackendControlPort:
    """Adapt an injected ROS service client without owning a ROS context.

    B2.2 exposes this client seam for the future B2.3 coordinator. The adapter
    never creates session, lifecycle, step, receipt, or observation identities.
    """

    def __init__(self, client: object) -> None:
        """Bind a caller-owned service client."""
        self._client = client

    @classmethod
    def from_node(cls, node: object) -> 'LocalTrainingBackendControlPort':
        """Bind the canonical service to a caller-owned node."""
        client = node.create_client(
            LocalTrainingBackendControl, BACKEND_CONTROL_ENDPOINT,
        )
        return cls(client)

    def submit(
        self, request: LocalTrainingBackendControl.Request,
    ) -> object:
        """Submit one caller-constructed request and return its future."""
        if not isinstance(request, LocalTrainingBackendControl.Request):
            raise TypeError(
                'request must be LocalTrainingBackendControl.Request'
            )
        if (
            request.schema_version
            != LocalTrainingBackendControl.Request.SCHEMA_VERSION
        ):
            raise ValueError('backend_control_request_schema_invalid')
        if (
            request.coordinator_ingress_instance_id == 0
            or request.request_sequence == 0
        ):
            raise ValueError('backend_control_request_identity_missing')
        return self._client.call_async(request)


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
