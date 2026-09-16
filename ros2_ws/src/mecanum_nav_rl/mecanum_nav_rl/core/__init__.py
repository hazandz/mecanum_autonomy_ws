"""Core domain types and pure logic for the Mecanum DRL system.

This package must not import ROS 2, Gazebo, Gymnasium, or Stable-Baselines3.
"""

from mecanum_nav_rl.core.enums import (
    TerminationReason,
    TruncationReason,
)
from mecanum_nav_rl.core.exceptions import (
    AgentContractError,
    ConfigurationContractError,
    InfrastructureError,
    MecanumNavRLError,
    ResetFailedError,
    RuntimeGenerationChangedError,
    SensorSynchronizationError,
    StaleSensorDataError,
)
from mecanum_nav_rl.core.frozen_array import (
    FrozenFloat32Array,
    freeze_float32_array,
)
from mecanum_nav_rl.core.protocols import (
    CommandPublisher,
    NanosecondClock,
    SensorSnapshotProvider,
)
from mecanum_nav_rl.core.snapshots import SensorSnapshot
from mecanum_nav_rl.core.transition import TaskState, TransitionContext
from mecanum_nav_rl.core.types import Pose2D, VelocityCommand

__all__ = (
    "AgentContractError",
    "CommandPublisher",
    "ConfigurationContractError",
    "FrozenFloat32Array",
    "InfrastructureError",
    "MecanumNavRLError",
    "NanosecondClock",
    "Pose2D",
    "ResetFailedError",
    "RuntimeGenerationChangedError",
    "SensorSnapshot",
    "SensorSnapshotProvider",
    "SensorSynchronizationError",
    "StaleSensorDataError",
    "TaskState",
    "TerminationReason",
    "TransitionContext",
    "TruncationReason",
    "VelocityCommand",
    "freeze_float32_array",
)