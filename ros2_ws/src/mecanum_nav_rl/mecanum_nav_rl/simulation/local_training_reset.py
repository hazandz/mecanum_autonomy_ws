"""B2.2 reset-service adapter that returns measured facts only."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence


@dataclass(frozen=True)
class ResetTarget:
    """Provide the requested world-frame reset pose."""

    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float

    def __post_init__(self) -> None:
        """Reject reset targets with invalid numeric values."""
        values = (self.x_m, self.y_m, self.z_m, self.yaw_rad)
        if any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in values
        ):
            raise ValueError(
                'reset target must be finite and explicitly bound'
            )


@dataclass(frozen=True)
class ResetMeasurement:
    """Carry measured pose, 3D twist and health from one physics step."""

    iteration: int
    stamp_ns: int
    x_m: float
    y_m: float
    z_m: float
    roll_rad: float
    pitch_rad: float
    yaw_rad: float
    linear_xyz_mps: tuple[float, float, float]
    angular_xyz_radps: tuple[float, float, float]
    contact_healthy: bool
    contact_active: bool
    footprint_clear: bool


@dataclass(frozen=True)
class ResetFacts:
    """Report reset service acknowledgments and validated measurement."""

    pause_confirmed: bool
    set_pose_acknowledged: bool
    resume_confirmed: bool
    measured_target_valid: bool
    measurement: ResetMeasurement


class GazeboResetServices(Protocol):
    """Define the world-control and entity-pose service boundary."""

    def control_world(
        self, *, world_name: str, pause: bool, timeout_s: float,
    ) -> bool:
        """Request a world pause state with a bounded timeout."""
        ...

    def set_entity_pose(
        self, *, world_name: str, entity_name: str,
        target: ResetTarget, timeout_s: float,
    ) -> bool:
        """Request a named model pose with a bounded timeout."""
        ...


class RosGazeboResetServices:
    """Jazzy service client adapter using an externally owned ROS node."""

    CONTROL_ENDPOINT = '/world/b2_training_arena/control'
    SET_POSE_ENDPOINT = '/world/b2_training_arena/set_pose'

    def __init__(
        self, node: object, spin_until_future_complete: Callable,
    ) -> None:
        """Bind the two services to an externally owned ROS node."""
        from ros_gz_interfaces.srv import ControlWorld, SetEntityPose

        self._node = node
        self._spin_until = spin_until_future_complete
        self._control_type = ControlWorld
        self._set_pose_type = SetEntityPose
        self._control = node.create_client(
            ControlWorld, self.CONTROL_ENDPOINT,
        )
        self._set_pose = node.create_client(
            SetEntityPose, self.SET_POSE_ENDPOINT,
        )

    def control_world(
        self, *, world_name: str, pause: bool, timeout_s: float,
    ) -> bool:
        """Call the exact B2 world-control service."""
        if world_name != LocalTrainingResetAdapter.WORLD:
            raise ValueError('reset service world must be b2_training_arena')
        request = self._control_type.Request()
        request.world_control.pause = pause
        return self._call(self._control, request, timeout_s)

    def set_entity_pose(
        self, *, world_name: str, entity_name: str,
        target: ResetTarget, timeout_s: float,
    ) -> bool:
        """Call set-pose using the exact model name, not a cached ID."""
        if (
            world_name != LocalTrainingResetAdapter.WORLD
            or entity_name != LocalTrainingResetAdapter.ENTITY
        ):
            raise ValueError('SetEntityPose must bind exact MODEL mecanum_b2')
        from ros_gz_interfaces.msg import Entity

        request = self._set_pose_type.Request()
        request.entity.id = 0
        request.entity.name = LocalTrainingResetAdapter.ENTITY
        request.entity.type = Entity.MODEL
        request.pose.position.x = target.x_m
        request.pose.position.y = target.y_m
        request.pose.position.z = target.z_m
        request.pose.orientation.x = 0.0
        request.pose.orientation.y = 0.0
        request.pose.orientation.z = math.sin(target.yaw_rad / 2.0)
        request.pose.orientation.w = math.cos(target.yaw_rad / 2.0)
        return self._call(self._set_pose, request, timeout_s)

    def _call(self, client: object, request: object, timeout_s: float) -> bool:
        if (
            timeout_s <= 0
            or not client.wait_for_service(timeout_sec=timeout_s)
        ):
            return False
        future = client.call_async(request)
        self._spin_until(self._node, future, timeout_sec=timeout_s)
        if not future.done():
            return False
        response = future.result()
        return response is not None and bool(response.success)


class LocalTrainingResetAdapter:
    """Run bounded reset services and validate measured reset facts."""

    WORLD = 'b2_training_arena'
    ENTITY = 'mecanum_b2'
    TOTAL_DEADLINE_S = 15.0
    SERVICE_TIMEOUT_S = 1.0
    PAUSE_RESUME_TIMEOUT_S = 2.0

    def __init__(
        self, services: GazeboResetServices,
        confirmed_state: Callable[[bool, float], bool],
        measurement: Callable[[], ResetMeasurement],
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Inject reset services, confirmed state, measurement and clocks."""
        self._services = services
        self._confirmed_state = confirmed_state
        self._measurement = measurement
        self._sleep = sleep
        self._monotonic = monotonic

    @staticmethod
    def validate_standstill_window(
        samples: Sequence[ResetMeasurement],
    ) -> None:
        """Require a continuous measured 3D standstill window."""
        if len(samples) < 21:
            raise ValueError(
                'standstill requires at least 21 measured 100 Hz samples'
            )
        for previous, current in zip(samples, samples[1:]):
            if current.iteration != previous.iteration + 1:
                raise ValueError(
                    'standstill measurement has a missing physics iteration'
                )
            if current.stamp_ns - previous.stamp_ns != 10_000_000:
                raise ValueError(
                    'standstill samples must be consecutive 100 Hz ROS'
                    ' measurements'
                )
        if samples[-1].stamp_ns - samples[0].stamp_ns < 200_000_000:
            raise ValueError('standstill span must be at least 0.20 s ROS')
        for sample in samples:
            values = (
                sample.x_m, sample.y_m, sample.z_m, sample.roll_rad,
                sample.pitch_rad, sample.yaw_rad, *sample.linear_xyz_mps,
                *sample.angular_xyz_radps,
            )
            if (
                type(sample.iteration) is not int or sample.iteration < 0
                or type(sample.stamp_ns) is not int or sample.stamp_ns < 0
                or any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in values
                )
            ):
                raise ValueError(
                    'reset measurement must be complete and finite'
                )
            if any(
                type(value) is not bool
                for value in (
                    sample.contact_healthy, sample.contact_active,
                    sample.footprint_clear,
                )
            ):
                raise ValueError(
                    'reset measurement health flags must be bool'
                )
            if math.sqrt(sum(v * v for v in sample.linear_xyz_mps)) > 0.01:
                raise ValueError(
                    'measured 3D linear standstill limit exceeded'
                )
            if math.sqrt(sum(v * v for v in sample.angular_xyz_radps)) > 0.02:
                raise ValueError(
                    'measured 3D angular standstill limit exceeded'
                )

    @staticmethod
    def validate_target(
        measurement: ResetMeasurement, target: ResetTarget,
    ) -> None:
        """Check measured pose, 3D velocity, contact and clearance."""
        values = (
            measurement.x_m, measurement.y_m, measurement.z_m,
            measurement.roll_rad, measurement.pitch_rad, measurement.yaw_rad,
            *measurement.linear_xyz_mps, *measurement.angular_xyz_radps,
        )
        if any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                'post-reset measurement must be complete and finite'
            )
        if (
            abs(measurement.x_m - target.x_m) > 0.01
            or abs(measurement.y_m - target.y_m) > 0.01
        ):
            raise ValueError('measured XY reset error exceeds 0.01 m')
        if abs(measurement.yaw_rad - target.yaw_rad) > 0.02:
            raise ValueError('measured yaw reset error exceeds 0.02 rad')
        if (
            abs(measurement.roll_rad) > 0.05
            or abs(measurement.pitch_rad) > 0.05
        ):
            raise ValueError('measured roll/pitch exceeds 0.05 rad')
        if abs(measurement.z_m - target.z_m) > 0.02:
            raise ValueError('measured Z reset error exceeds 0.02 m')
        if not measurement.contact_healthy or measurement.contact_active:
            raise ValueError('contact must be healthy and clear after reset')
        if not measurement.footprint_clear:
            raise ValueError(
                'reset footprint clearance including 0.05 m is not proven'
            )

    def execute(
        self, *, target: ResetTarget,
        measured_standstill: Sequence[ResetMeasurement],
        zero_receipt_applied: bool,
        reset_emulator_and_buffers: Callable[[], None],
    ) -> ResetFacts:
        """Perform a reset and return only validated measured facts."""
        start = self._monotonic()
        deadline = start + self.TOTAL_DEADLINE_S
        if not zero_receipt_applied:
            raise ValueError('reset requires an actually applied zero receipt')
        self.validate_standstill_window(measured_standstill)
        if self._monotonic() - start > 5.0:
            raise TimeoutError('standstill phase exceeded 5 s steady')
        if not self._services.control_world(
            world_name=self.WORLD, pause=True,
            timeout_s=self.SERVICE_TIMEOUT_S,
        ):
            raise TimeoutError('Gazebo pause service failed or exceeded 1 s')
        if not self._confirmed_state(
            True, min(2.0, deadline - self._monotonic()),
        ):
            raise TimeoutError('world pause was not confirmed within 2 s')
        pose_ack = self._services.set_entity_pose(
            world_name=self.WORLD, entity_name=self.ENTITY, target=target,
            timeout_s=self.SERVICE_TIMEOUT_S,
        )
        if not pose_ack:
            raise TimeoutError('SetEntityPose did not acknowledge within 1 s')
        reset_emulator_and_buffers()
        if not self._services.control_world(
            world_name=self.WORLD, pause=False,
            timeout_s=self.SERVICE_TIMEOUT_S,
        ):
            raise TimeoutError('Gazebo resume service failed or exceeded 1 s')
        if not self._confirmed_state(
            False, min(2.0, deadline - self._monotonic()),
        ):
            raise TimeoutError('world resume was not confirmed within 2 s')
        measured = self._measurement()
        self.validate_target(measured, target)
        if self._monotonic() > deadline:
            raise TimeoutError('total reset deadline exceeded 15 s steady')
        return ResetFacts(True, pose_ack, True, True, measured)
