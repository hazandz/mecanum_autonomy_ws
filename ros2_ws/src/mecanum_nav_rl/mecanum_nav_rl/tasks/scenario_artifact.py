"""Pure-core parser and validator for immutable scenario artifacts.

This module accepts caller-supplied mappings or JSON text only.  It never
opens a file, reads an environment variable, creates a runtime endpoint, or
imports policy-observation, ROS, Gazebo, or Ground Truth types.  A successful
load validates data-only candidate task metadata; it does not authorize a
runtime scenario, reset, clearance, collision policy, or task oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from math import isfinite
from numbers import Real
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from mecanum_nav_rl.core.lifecycle_types import EpisodeLifecycleIdentity
from mecanum_nav_rl.core.scenario_session import ScenarioSessionBinding


SCENARIO_ARTIFACT_SCHEMA_VERSION = "s3_scenario_artifact/v1"
SCENARIO_ARTIFACT_HASH_VERSION = "s3_scenario_artifact_hash/v1"
GT_ODOM_2D_REFERENCE_ID = "GT_ODOM_2D"
SHA256_HEX_LENGTH = 64
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class _ScenarioModel(BaseModel):
    """Pydantic convention shared by immutable scenario data models."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


def _require_nonempty_identifier(value: object, field_name: str) -> str:
    """Validate one exact, non-empty identifier without coercion."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty trimmed string")
    return value


def _require_finite_real(value: object, field_name: str) -> float:
    """Validate a finite numeric field while rejecting bool and strings."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a real number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _require_sha256(value: object, field_name: str) -> str:
    """Validate a lowercase full SHA-256 digest."""

    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase 64-hex SHA-256")
    return value


class GoalDefinition(_ScenarioModel):
    """Finite 2D goal metadata; no world/model pose or z coordinate exists."""

    x_m: float
    y_m: float
    goal_radius_m: float
    goal_rule_id: str

    @field_validator("x_m", "y_m", "goal_radius_m", mode="before")
    @classmethod
    def validate_finite_values(cls, value: object, info: Any) -> float:
        return _require_finite_real(value, info.field_name)

    @field_validator("goal_rule_id", mode="before")
    @classmethod
    def validate_goal_rule_id(cls, value: object) -> str:
        value = _require_nonempty_identifier(value, "goal_rule_id")
        if value != "distance_to_goal_lte_radius_2d":
            raise ValueError(
                "only goal_rule_id distance_to_goal_lte_radius_2d is supported"
            )
        return value

    @model_validator(mode="after")
    def validate_goal_radius(self) -> "GoalDefinition":
        if self.goal_radius_m <= 0.0:
            raise ValueError("goal_radius_m must be positive")
        return self


class StartPoseDefinition(_ScenarioModel):
    """One immutable 2D candidate start-pose catalog member."""

    start_id: str
    x_m: float
    y_m: float
    yaw_rad: float

    @field_validator("start_id", mode="before")
    @classmethod
    def validate_start_id(cls, value: object) -> str:
        return _require_nonempty_identifier(value, "start_id")

    @field_validator("x_m", "y_m", "yaw_rad", mode="before")
    @classmethod
    def validate_finite_values(cls, value: object, info: Any) -> float:
        return _require_finite_real(value, info.field_name)


class CandidateTaskBounds(_ScenarioModel):
    """Candidate-only rectangle metadata; this is deliberately not valid_area."""

    shape_type: Literal["axis_aligned_rectangle"]
    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float
    boundary_semantics: Literal["boundary_invalid"]

    @field_validator("min_x_m", "max_x_m", "min_y_m", "max_y_m", mode="before")
    @classmethod
    def validate_finite_values(cls, value: object, info: Any) -> float:
        return _require_finite_real(value, info.field_name)

    @model_validator(mode="after")
    def validate_extent_order(self) -> "CandidateTaskBounds":
        if self.min_x_m >= self.max_x_m or self.min_y_m >= self.max_y_m:
            raise ValueError("candidate_task_bounds minimum must be less than maximum")
        return self


class ScenarioTaskDefinition(_ScenarioModel):
    """Validated task metadata without runtime validity or collision claims."""

    goal: GoalDefinition
    start_pose_catalog: tuple[StartPoseDefinition, ...] = Field(min_length=1)
    candidate_task_bounds: CandidateTaskBounds
    forbidden_zone_policy: str
    forbidden_zones: tuple[dict[str, object], ...]
    randomization: str

    @field_validator("forbidden_zone_policy", mode="before")
    @classmethod
    def validate_forbidden_zone_policy(cls, value: object) -> str:
        value = _require_nonempty_identifier(value, "forbidden_zone_policy")
        if value != "none_provisional":
            raise ValueError("only forbidden_zone_policy 'none_provisional' is supported")
        return value

    @field_validator("forbidden_zones", mode="before")
    @classmethod
    def validate_forbidden_zones(cls, value: object) -> tuple[dict[str, object], ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("forbidden_zones must be a list or tuple")
        if value:
            raise ValueError("forbidden_zones must be empty for none_provisional")
        return tuple(value)

    @field_validator("randomization", mode="before")
    @classmethod
    def validate_randomization(cls, value: object) -> str:
        value = _require_nonempty_identifier(value, "randomization")
        if value != "disabled":
            raise ValueError("only randomization 'disabled' is supported")
        return value

    @model_validator(mode="after")
    def validate_start_ids(self) -> "ScenarioTaskDefinition":
        start_ids = tuple(start.start_id for start in self.start_pose_catalog)
        if len(start_ids) != len(set(start_ids)):
            raise ValueError("start_pose_catalog start_id values must be unique")
        return self


class ScenarioArtifactIdentity(_ScenarioModel):
    """Fully verified public scenario identity including its content digest."""

    artifact_schema_version: Literal[SCENARIO_ARTIFACT_SCHEMA_VERSION]
    scenario_id: str
    scenario_version: str
    scenario_content_sha256: str
    gazebo_world_name: str
    world_file_sha256: str
    coordinate_reference_id: str

    @field_validator("scenario_id", "scenario_version", "gazebo_world_name", "coordinate_reference_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info: Any) -> str:
        return _require_nonempty_identifier(value, info.field_name)

    @field_validator("scenario_content_sha256", "world_file_sha256", mode="before")
    @classmethod
    def validate_hashes(cls, value: object, info: Any) -> str:
        return _require_sha256(value, info.field_name)


class ScenarioArtifact(_ScenarioModel):
    """Public immutable artifact returned only after complete verification."""

    artifact_hash_version: Literal[SCENARIO_ARTIFACT_HASH_VERSION]
    identity: ScenarioArtifactIdentity
    task_definition: ScenarioTaskDefinition


class _ScenarioArtifactIdentityWithoutContentHash(_ScenarioModel):
    """Internal identity body used to validate canonical hash payload data."""

    artifact_schema_version: Literal[SCENARIO_ARTIFACT_SCHEMA_VERSION]
    scenario_id: str
    scenario_version: str
    gazebo_world_name: str
    world_file_sha256: str
    coordinate_reference_id: str

    @field_validator("scenario_id", "scenario_version", "gazebo_world_name", "coordinate_reference_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info: Any) -> str:
        return _require_nonempty_identifier(value, info.field_name)

    @field_validator("world_file_sha256", mode="before")
    @classmethod
    def validate_world_hash(cls, value: object) -> str:
        return _require_sha256(value, "world_file_sha256")


class _ScenarioArtifactBody(_ScenarioModel):
    """Internal unsigned body; it cannot expose a trusted content digest."""

    artifact_hash_version: Literal[SCENARIO_ARTIFACT_HASH_VERSION]
    identity: _ScenarioArtifactIdentityWithoutContentHash
    task_definition: ScenarioTaskDefinition


class ScenarioArtifactLoadStatus(str, Enum):
    """Explicit, fail-closed outcomes for caller-supplied artifact input."""

    READY = "ready"
    INVALID_INPUT = "invalid_input"
    UNKNOWN_SCHEMA_VERSION = "unknown_schema_version"
    HASH_MISMATCH = "hash_mismatch"
    WORLD_IDENTITY_MISMATCH = "world_identity_mismatch"
    COORDINATE_REFERENCE_MISMATCH = "coordinate_reference_mismatch"
    MALFORMED_TASK_DEFINITION = "malformed_task_definition"
    FORBIDDEN_ZONE_INVALID = "forbidden_zone_invalid"


@dataclass(frozen=True, slots=True)
class ScenarioArtifactLoadResult:
    """Immutable load result that never contains a partial artifact."""

    status: ScenarioArtifactLoadStatus
    artifact: ScenarioArtifact | None
    diagnostic_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ScenarioArtifactLoadStatus):
            raise TypeError("status must be a ScenarioArtifactLoadStatus")
        if self.status is ScenarioArtifactLoadStatus.READY:
            if not isinstance(self.artifact, ScenarioArtifact):
                raise ValueError("READY result must contain a ScenarioArtifact")
        elif self.artifact is not None:
            raise ValueError("non-ready result must not contain an artifact")

    @property
    def ready(self) -> bool:
        """Whether this result contains one fully validated artifact."""

        return self.status is ScenarioArtifactLoadStatus.READY


def scenario_session_binding_from_ready_artifact(
    artifact_result: object,
    lifecycle_identity: object,
) -> ScenarioSessionBinding:
    """Copy a READY artifact identity into a lifecycle-bound scalar session.

    This factory is pure: it never reads an artifact file or retains an artifact
    object in the returned binding. Missing or non-ready results fail closed.
    """

    if not isinstance(artifact_result, ScenarioArtifactLoadResult):
        raise TypeError("artifact_result must be a ScenarioArtifactLoadResult")
    if not artifact_result.ready or artifact_result.artifact is None:
        raise ValueError("scenario artifact result must be READY")
    if not isinstance(lifecycle_identity, EpisodeLifecycleIdentity):
        raise TypeError("lifecycle_identity must be an EpisodeLifecycleIdentity")
    identity = artifact_result.artifact.identity
    return ScenarioSessionBinding(
        lifecycle_identity=lifecycle_identity,
        scenario_id=identity.scenario_id,
        scenario_version=identity.scenario_version,
        scenario_content_sha256=identity.scenario_content_sha256,
        gazebo_world_name=identity.gazebo_world_name,
        world_file_sha256=identity.world_file_sha256,
        coordinate_reference_id=identity.coordinate_reference_id,
    )


def canonical_scenario_artifact_json(unsigned_mapping: Mapping[str, object]) -> str:
    """Return canonical JSON for an unsigned artifact body supplied by a caller.

    ``unsigned_mapping`` must omit ``identity.scenario_content_sha256``.  The
    function is intentionally pure and is useful to a trusted artifact author
    or a test fixture, but it never writes an artifact file.
    """

    if not isinstance(unsigned_mapping, Mapping):
        raise TypeError("unsigned_mapping must be a mapping")
    body = _ScenarioArtifactBody.model_validate(dict(unsigned_mapping))
    payload = {
        "artifact_hash_version": body.artifact_hash_version,
        "artifact": {
            "identity": body.identity.model_dump(mode="json"),
            "task_definition": body.task_definition.model_dump(mode="json"),
        },
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def scenario_artifact_sha256(unsigned_mapping: Mapping[str, object]) -> str:
    """Return the lowercase full SHA-256 of canonical unsigned artifact data."""

    return hashlib.sha256(
        canonical_scenario_artifact_json(unsigned_mapping).encode("utf-8")
    ).hexdigest()


class ScenarioArtifactLoader:
    """Pure validator for one caller-provided immutable scenario artifact."""

    def __init__(
        self,
        *,
        expected_gazebo_world_name: str,
        expected_world_file_sha256: str,
        expected_coordinate_reference_id: str = GT_ODOM_2D_REFERENCE_ID,
    ) -> None:
        self._expected_gazebo_world_name = _require_nonempty_identifier(
            expected_gazebo_world_name,
            "expected_gazebo_world_name",
        )
        self._expected_world_file_sha256 = _require_sha256(
            expected_world_file_sha256,
            "expected_world_file_sha256",
        )
        self._expected_coordinate_reference_id = _require_nonempty_identifier(
            expected_coordinate_reference_id,
            "expected_coordinate_reference_id",
        )
        if self._expected_coordinate_reference_id != GT_ODOM_2D_REFERENCE_ID:
            raise ValueError("only expected_coordinate_reference_id GT_ODOM_2D is supported")

    @staticmethod
    def _result(
        status: ScenarioArtifactLoadStatus,
        diagnostic_code: str,
    ) -> ScenarioArtifactLoadResult:
        return ScenarioArtifactLoadResult(
            status=status,
            artifact=None,
            diagnostic_code=diagnostic_code,
        )

    @staticmethod
    def _validation_status(error: ValidationError) -> ScenarioArtifactLoadStatus:
        locations = {
            ".".join(str(part) for part in item["loc"])
            for item in error.errors()
        }
        if any(
            "artifact_schema_version" in location
            or "artifact_hash_version" in location
            for location in locations
        ):
            return ScenarioArtifactLoadStatus.UNKNOWN_SCHEMA_VERSION
        if any("forbidden_zone" in location for location in locations):
            return ScenarioArtifactLoadStatus.FORBIDDEN_ZONE_INVALID
        return ScenarioArtifactLoadStatus.MALFORMED_TASK_DEFINITION

    @staticmethod
    def _parse_source(source: Mapping[str, object] | str) -> Mapping[str, object] | None:
        if isinstance(source, str):
            try:
                parsed = json.loads(source)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, Mapping) else None
        return source if isinstance(source, Mapping) else None

    def load(self, source: Mapping[str, object] | str) -> ScenarioArtifactLoadResult:
        """Validate one supplied mapping or JSON text without any fallback state."""

        source_mapping = self._parse_source(source)
        if source_mapping is None:
            return self._result(ScenarioArtifactLoadStatus.INVALID_INPUT, "source_not_mapping_or_json_object")

        raw_mapping = dict(source_mapping)
        raw_identity = raw_mapping.get("identity")
        if not isinstance(raw_identity, Mapping):
            return self._result(ScenarioArtifactLoadStatus.INVALID_INPUT, "identity_missing_or_not_mapping")

        unsigned_identity = dict(raw_identity)
        supplied_digest = unsigned_identity.pop("scenario_content_sha256", None)
        try:
            supplied_digest = _require_sha256(supplied_digest, "scenario_content_sha256")
        except ValueError:
            return self._result(ScenarioArtifactLoadStatus.INVALID_INPUT, "scenario_content_sha256_invalid")

        raw_mapping["identity"] = unsigned_identity
        try:
            body = _ScenarioArtifactBody.model_validate(raw_mapping)
        except ValidationError as error:
            return self._result(self._validation_status(error), "schema_validation_failed")

        canonical_json = canonical_scenario_artifact_json(
            body.model_dump(mode="python")
        )
        computed_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        if supplied_digest != computed_digest:
            return self._result(ScenarioArtifactLoadStatus.HASH_MISMATCH, "scenario_content_sha256_mismatch")

        if (
            body.identity.gazebo_world_name != self._expected_gazebo_world_name
            or body.identity.world_file_sha256 != self._expected_world_file_sha256
        ):
            return self._result(ScenarioArtifactLoadStatus.WORLD_IDENTITY_MISMATCH, "expected_world_identity_mismatch")
        if body.identity.coordinate_reference_id != self._expected_coordinate_reference_id:
            return self._result(ScenarioArtifactLoadStatus.COORDINATE_REFERENCE_MISMATCH, "expected_coordinate_reference_mismatch")

        identity = ScenarioArtifactIdentity(
            artifact_schema_version=body.identity.artifact_schema_version,
            scenario_id=body.identity.scenario_id,
            scenario_version=body.identity.scenario_version,
            scenario_content_sha256=supplied_digest,
            gazebo_world_name=body.identity.gazebo_world_name,
            world_file_sha256=body.identity.world_file_sha256,
            coordinate_reference_id=body.identity.coordinate_reference_id,
        )
        artifact = ScenarioArtifact(
            artifact_hash_version=body.artifact_hash_version,
            identity=identity,
            task_definition=body.task_definition,
        )
        return ScenarioArtifactLoadResult(
            status=ScenarioArtifactLoadStatus.READY,
            artifact=artifact,
            diagnostic_code=None,
        )
