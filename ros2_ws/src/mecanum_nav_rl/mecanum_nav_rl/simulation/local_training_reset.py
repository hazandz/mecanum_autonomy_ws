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
    session_id: str = ''
    config_hash: str = ''
    backend_instance_id: int = 0
    reset_epoch: int = 0
    receive_steady_ns: int = -1
    episode_generation: int = 0
    runtime_generation: int = 0


@dataclass(frozen=True)
class AppliedZeroReceiptFact:
    """Bind the selected SAFE_STOP receipt to backend application facts."""

    session_id: str
    config_hash: str
    backend_instance_id: int
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    final_publisher_instance_id: int
    final_publish_sequence: int
    source: int
    source_instance_id: int
    source_sequence: int
    step_index: int
    transition_id: str
    twist: tuple[float, float, float, float, float, float]
    barrier_stamp_ns: int
    receipt_stamp_ns: int
    applied_receipt_valid: bool
    applied_final_publisher_instance_id: int
    applied_final_publish_sequence: int
    applied_physics_iteration: int
    applied_sim_stamp_ns: int
    local_zero_override: bool
    receive_steady_ns: int


@dataclass(frozen=True)
class ResetFacts:
    """Report reset service acknowledgments and validated measurement."""

    pause_confirmed: bool
    set_pose_acknowledged: bool
    resume_confirmed: bool
    measured_target_valid: bool
    measurement: ResetMeasurement
    applied_zero_receipt: AppliedZeroReceiptFact


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
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Bind the two services to an externally owned ROS node."""
        from ros_gz_interfaces.srv import ControlWorld, SetEntityPose

        self._node = node
        self._spin_until = spin_until_future_complete
        self._monotonic = monotonic
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
        if timeout_s <= 0:
            return False
        deadline = self._monotonic() + timeout_s
        if not client.wait_for_service(
            timeout_sec=max(0.0, deadline - self._monotonic()),
        ):
            return False
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            return False
        future = client.call_async(request)
        self._spin_until(self._node, future, timeout_sec=remaining)
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
    MEASUREMENT_MAX_RECEIVE_AGE_S = 0.2

    def __init__(
        self, services: GazeboResetServices,
        confirmed_state: Callable[[bool, float], bool],
        measurement: Callable[[], Sequence[ResetMeasurement]],
        *, expected_session_id: str, expected_config_hash: str,
        expected_backend_instance_id: int, expected_reset_epoch: int,
        expected_episode_generation: int, expected_runtime_generation: int,
        expected_final_publisher_instance_id: int,
        expected_safe_stop_source_instance_id: int,
        expected_barrier_stamp_ns: int,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Inject reset services, confirmed state, measurement and clocks."""
        self._services = services
        self._confirmed_state = confirmed_state
        self._measurement = measurement
        self._expected_session_id = expected_session_id
        self._expected_config_hash = expected_config_hash
        self._expected_backend_instance_id = expected_backend_instance_id
        self._expected_reset_epoch = expected_reset_epoch
        self._expected_episode_generation = expected_episode_generation
        self._expected_runtime_generation = expected_runtime_generation
        self._expected_final_publisher_instance_id = (
            expected_final_publisher_instance_id
        )
        self._expected_safe_stop_source_instance_id = (
            expected_safe_stop_source_instance_id
        )
        self._expected_barrier_stamp_ns = expected_barrier_stamp_ns
        if (
            not expected_session_id
            or len(expected_config_hash) != 64
            or any(c not in '0123456789abcdef' for c in expected_config_hash)
            or type(expected_backend_instance_id) is not int
            or expected_backend_instance_id <= 0
            or type(expected_reset_epoch) is not int
            or expected_reset_epoch < 0
            or type(expected_episode_generation) is not int
            or expected_episode_generation < 0
            or type(expected_runtime_generation) is not int
            or expected_runtime_generation < 0
            or type(expected_final_publisher_instance_id) is not int
            or expected_final_publisher_instance_id <= 0
            or type(expected_safe_stop_source_instance_id) is not int
            or expected_safe_stop_source_instance_id <= 0
            or type(expected_barrier_stamp_ns) is not int
            or expected_barrier_stamp_ns < 0
        ):
            raise ValueError('reset identity binding must be complete')
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
        for sample in samples:
            if (
                type(sample.iteration) is not int or sample.iteration < 0
                or type(sample.stamp_ns) is not int or sample.stamp_ns < 0
                or not isinstance(sample.linear_xyz_mps, tuple)
                or len(sample.linear_xyz_mps) != 3
                or not isinstance(sample.angular_xyz_radps, tuple)
                or len(sample.angular_xyz_radps) != 3
            ):
                raise ValueError(
                    'reset twist vectors must each have three values'
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
        yaw_error = math.atan2(
            math.sin(measurement.yaw_rad - target.yaw_rad),
            math.cos(measurement.yaw_rad - target.yaw_rad),
        )
        if abs(yaw_error) > 0.02:
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

    def _remaining(
        self, deadline: float, phase_limit: float, phase: str,
    ) -> float:
        remaining = min(phase_limit, deadline - self._monotonic())
        if remaining <= 0:
            raise TimeoutError(
                f'total reset deadline exhausted during {phase}'
            )
        return remaining

    def _validate_identity_and_freshness(
        self, samples: Sequence[ResetMeasurement], *, after_steady_s: float,
        after_stamp_ns: int | None = None,
    ) -> None:
        if not samples:
            raise ValueError('reset requires fresh measured samples')
        for sample in samples:
            if (
                sample.session_id != self._expected_session_id
                or sample.config_hash != self._expected_config_hash
                or sample.backend_instance_id
                != self._expected_backend_instance_id
                or sample.reset_epoch != self._expected_reset_epoch
                or sample.episode_generation
                != self._expected_episode_generation
                or sample.runtime_generation
                != self._expected_runtime_generation
            ):
                raise ValueError('reset measurement identity mismatch')
            if (
                type(sample.receive_steady_ns) is not int
                or sample.receive_steady_ns < 0
            ):
                raise ValueError(
                    'reset measurement lacks receive steady timestamp'
                )
            receive_s = sample.receive_steady_ns / 1_000_000_000
            if receive_s < after_steady_s or receive_s > self._monotonic():
                raise ValueError(
                    'reset measurement receive timestamp is stale or future'
                )
            if (
                self._monotonic() - receive_s
                > self.MEASUREMENT_MAX_RECEIVE_AGE_S
            ):
                raise ValueError(
                    'reset measurement exceeds receive freshness'
                )
            if (
                after_stamp_ns is not None
                and sample.stamp_ns <= after_stamp_ns
            ):
                raise ValueError(
                    'reset measurement is not newer than reset barrier'
                )

    def _validate_applied_zero_receipt(
        self, fact: AppliedZeroReceiptFact,
    ) -> None:
        """Require an identity-bound zero receipt selected by the backend."""
        if not isinstance(fact, AppliedZeroReceiptFact):
            raise ValueError(
                'reset requires a typed applied zero receipt fact'
            )
        if (
            fact.session_id != self._expected_session_id
            or fact.config_hash != self._expected_config_hash
            or fact.backend_instance_id != self._expected_backend_instance_id
            or fact.episode_generation != self._expected_episode_generation
            or fact.reset_epoch != self._expected_reset_epoch
            or fact.runtime_generation != self._expected_runtime_generation
        ):
            raise ValueError('applied zero receipt identity mismatch')
        if (
            type(fact.source) is not int or fact.source != 4
            or fact.source_instance_id
            != self._expected_safe_stop_source_instance_id
            or type(fact.source_instance_id) is not int
            or type(fact.source_sequence) is not int
            or fact.source_sequence <= 0
            or type(fact.step_index) is not int
            or fact.step_index != 0
            or fact.transition_id != ''
            or fact.final_publisher_instance_id
            != self._expected_final_publisher_instance_id
            or type(fact.final_publish_sequence) is not int
            or fact.final_publish_sequence <= 0
        ):
            raise ValueError(
                'applied zero receipt is not a bound SAFE_STOP'
            )
        if (
            not isinstance(fact.twist, tuple) or len(fact.twist) != 6
            or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in fact.twist
            )
            or any(value != 0.0 for value in fact.twist)
        ):
            raise ValueError(
                'selected SAFE_STOP receipt payload must be finite zero'
            )
        if (
            type(fact.applied_receipt_valid) is not bool
            or not fact.applied_receipt_valid
            or type(fact.local_zero_override) is not bool
            or fact.local_zero_override
            or fact.applied_final_publisher_instance_id
            != fact.final_publisher_instance_id
            or fact.applied_final_publish_sequence
            != fact.final_publish_sequence
        ):
            raise ValueError(
                'backend did not apply the selected zero receipt key'
            )
        if (
            type(fact.barrier_stamp_ns) is not int
            or type(fact.receipt_stamp_ns) is not int
            or type(fact.applied_sim_stamp_ns) is not int
            or type(fact.applied_physics_iteration) is not int
            or fact.barrier_stamp_ns < 0
            or fact.barrier_stamp_ns != self._expected_barrier_stamp_ns
            or fact.receipt_stamp_ns <= fact.barrier_stamp_ns
            or fact.applied_sim_stamp_ns < fact.receipt_stamp_ns
            or fact.applied_physics_iteration <= 0
        ):
            raise ValueError(
                'applied zero receipt timing/barrier proof is invalid'
            )
        now_ns = int(self._monotonic() * 1_000_000_000)
        if (
            type(fact.receive_steady_ns) is not int
            or fact.receive_steady_ns < 0
            or fact.receive_steady_ns > now_ns
            or now_ns - fact.receive_steady_ns > 100_000_000
        ):
            raise ValueError(
                'applied zero receipt proof is stale or future'
            )

    def execute(
        self, *, target: ResetTarget,
        measured_standstill: Sequence[ResetMeasurement],
        applied_zero_receipt: AppliedZeroReceiptFact,
        reset_emulator_and_buffers: Callable[[], None],
    ) -> ResetFacts:
        """Perform bounded reset actions and return fresh measured facts."""
        start = self._monotonic()
        deadline = start + self.TOTAL_DEADLINE_S
        self._validate_applied_zero_receipt(applied_zero_receipt)
        self.validate_standstill_window(measured_standstill)
        self._validate_identity_and_freshness(
            measured_standstill, after_steady_s=start - 5.0,
        )
        if self._monotonic() - start > 5.0:
            raise TimeoutError('standstill phase exceeded 5 s steady')
        pre_reset_stamp = measured_standstill[-1].stamp_ns
        self._remaining(deadline, self.SERVICE_TIMEOUT_S, 'pause service')
        pause_ack = self._services.control_world(
            world_name=self.WORLD, pause=True,
            timeout_s=self._remaining(
                deadline, self.SERVICE_TIMEOUT_S, 'pause service',
            ),
        )
        if type(pause_ack) is not bool or not pause_ack:
            raise TimeoutError(
                'Gazebo pause service failed or exceeded its shared 1 s '
                'deadline'
            )
        pause_confirmed = self._confirmed_state(
            True, self._remaining(
                deadline, self.PAUSE_RESUME_TIMEOUT_S,
                'pause confirmation',
            ),
        )
        if type(pause_confirmed) is not bool or not pause_confirmed:
            raise TimeoutError('world pause was not confirmed within 2 s')
        pose_ack = self._services.set_entity_pose(
            world_name=self.WORLD, entity_name=self.ENTITY, target=target,
            timeout_s=self._remaining(
                deadline, self.SERVICE_TIMEOUT_S, 'set pose service',
            ),
        )
        if type(pose_ack) is not bool or not pose_ack:
            raise TimeoutError(
                'SetEntityPose did not acknowledge within its shared 1 s '
                'deadline'
            )
        self._remaining(deadline, self.SERVICE_TIMEOUT_S, 'emulator reset')
        reset_emulator_and_buffers()
        resume_ack = self._services.control_world(
            world_name=self.WORLD, pause=False,
            timeout_s=self._remaining(
                deadline, self.SERVICE_TIMEOUT_S, 'resume service',
            ),
        )
        if type(resume_ack) is not bool or not resume_ack:
            raise TimeoutError(
                'Gazebo resume service failed or exceeded its shared 1 s '
                'deadline'
            )
        resumed_at = self._monotonic()
        resume_confirmed = self._confirmed_state(
            False, self._remaining(
                deadline, self.PAUSE_RESUME_TIMEOUT_S,
                'resume confirmation',
            ),
        )
        if type(resume_confirmed) is not bool or not resume_confirmed:
            raise TimeoutError('world resume was not confirmed within 2 s')
        self._remaining(
            deadline, self.PAUSE_RESUME_TIMEOUT_S, 'post-resume settling',
        )
        settled = self._measurement()
        if (
            not isinstance(settled, Sequence)
            or isinstance(settled, (str, bytes))
        ):
            raise ValueError(
                'post-resume measurement must be a sample sequence'
            )
        self.validate_standstill_window(settled)
        self._validate_identity_and_freshness(
            settled, after_steady_s=resumed_at, after_stamp_ns=pre_reset_stamp,
        )
        for sample in settled:
            self.validate_target(sample, target)
        self._remaining(deadline, self.TOTAL_DEADLINE_S, 'completion')
        measured = settled[-1]
        return ResetFacts(
            True, pose_ack, True, True, measured, applied_zero_receipt,
        )
