"""Pure, immutable task-data contracts for simulation-only core design."""

from mecanum_nav_rl.tasks.scenario_artifact import (
    ScenarioArtifact,
    ScenarioArtifactIdentity,
    ScenarioArtifactLoader,
    ScenarioArtifactLoadResult,
    ScenarioArtifactLoadStatus,
    ScenarioTaskDefinition,
    scenario_session_binding_from_ready_artifact,
)
from mecanum_nav_rl.tasks.training_task_oracle import (
    GoalFactJoinMode,
    GoalFactProvenance,
    GoalOracleFact,
    OraclePose2D,
    TaskOracleResult,
    TaskOracleStatus,
    TrainingTaskOracle,
)

__all__ = (
    "ScenarioArtifact",
    "ScenarioArtifactIdentity",
    "ScenarioArtifactLoader",
    "ScenarioArtifactLoadResult",
    "ScenarioArtifactLoadStatus",
    "ScenarioTaskDefinition",
    "scenario_session_binding_from_ready_artifact",
    "GoalFactJoinMode",
    "GoalFactProvenance",
    "GoalOracleFact",
    "OraclePose2D",
    "TaskOracleResult",
    "TaskOracleStatus",
    "TrainingTaskOracle",
)
