"""Structural interfaces shared by pure core and runtime adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mecanum_nav_rl.core.snapshots import SensorSnapshot
from mecanum_nav_rl.core.types import VelocityCommand


@runtime_checkable
class NanosecondClock(Protocol):
    """A clock that returns a non-negative timestamp in nanoseconds.

    The implementation must document its time domain, for example simulation
    time or monotonic steady time.
    """

    def now_ns(self) -> int:
        """Return the current timestamp in nanoseconds."""
        ...


@runtime_checkable
class CommandPublisher(Protocol):
    """A component that publishes a physical velocity command.

    Publishing only sends the command to the next runtime layer. It does not
    claim that an actuator or Gazebo has already applied the command.
    """

    def publish_velocity_command(self, command: VelocityCommand) -> None:
        """Publish one physical Mecanum velocity command."""
        ...


@runtime_checkable
class SensorSnapshotProvider(Protocol):
    """A component that returns the current valid sensor snapshot.

    The implementation must return a snapshot selected by its synchronizer or
    raise an InfrastructureError subclass when no valid snapshot is available.
    """

    def get_sensor_snapshot(self) -> SensorSnapshot:
        """Return one valid immutable sensor snapshot."""
        ...
