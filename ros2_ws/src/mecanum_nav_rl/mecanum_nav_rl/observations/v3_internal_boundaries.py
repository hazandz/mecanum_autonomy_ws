"""Dependency-injected internal seams; deliberately independent of ROS/runtime."""

from typing import Protocol


class LidarSnapshotSource(Protocol):
    def read_snapshot(self) -> object: ...


class LocalReferenceSnapshotSource(Protocol):
    def read_snapshot(self) -> object: ...


class MeasuredTwistSnapshotSource(Protocol):
    def read_snapshot(self) -> object: ...


class ReceiptLifecycleContextSource(Protocol):
    def read_context(self) -> object: ...
