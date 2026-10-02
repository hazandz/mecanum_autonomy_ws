"""Shared immutable scalar-only scenario session binding."""

from __future__ import annotations

from dataclasses import dataclass

from mecanum_nav_rl.core.lifecycle_types import (
    EpisodeLifecycleIdentity,
    require_sha256,
)


def _require_identifier(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed string")
    return value


@dataclass(frozen=True, slots=True)
class ScenarioSessionBinding:
    """Trusted scalar identity for one scenario selected before episode reset.

    It deliberately copies no ScenarioArtifact, Ground Truth pose, ROS/Gazebo
    object, task geometry, or runtime handle.
    """

    lifecycle_identity: EpisodeLifecycleIdentity
    scenario_id: str
    scenario_version: str
    scenario_content_sha256: str
    gazebo_world_name: str
    world_file_sha256: str
    coordinate_reference_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle_identity, EpisodeLifecycleIdentity):
            raise TypeError("lifecycle_identity must be an EpisodeLifecycleIdentity")
        for field_name in (
            "scenario_id",
            "scenario_version",
            "gazebo_world_name",
            "coordinate_reference_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_identifier(field_name, getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "scenario_content_sha256",
            require_sha256(
                "scenario_content_sha256", self.scenario_content_sha256
            ),
        )
        object.__setattr__(
            self,
            "world_file_sha256",
            require_sha256("world_file_sha256", self.world_file_sha256),
        )

