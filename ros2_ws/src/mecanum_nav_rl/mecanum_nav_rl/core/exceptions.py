"""Project-specific exception hierarchy for the Mecanum DRL system."""

from __future__ import annotations


class MecanumNavRLError(Exception):
    """Base exception for expected project-specific failures."""


class ConfigurationContractError(MecanumNavRLError):
    """Raised when validated project configuration violates a contract."""


class AgentContractError(MecanumNavRLError):
    """Raised when a policy/checkpoint contract differs from runtime contract."""


class InfrastructureError(MecanumNavRLError):
    """Base error for ROS, Gazebo, sensor, or runtime infrastructure failures."""


class SensorSynchronizationError(InfrastructureError):
    """Raised when required sensor messages cannot form a valid snapshot."""


class StaleSensorDataError(InfrastructureError):
    """Raised when required sensor data is too old for the active runtime."""


class ResetFailedError(InfrastructureError):
    """Raised when a simulator or environment reset cannot complete safely."""


class RuntimeGenerationChangedError(InfrastructureError):
    """Raised when runtime state changes during one required operation."""
