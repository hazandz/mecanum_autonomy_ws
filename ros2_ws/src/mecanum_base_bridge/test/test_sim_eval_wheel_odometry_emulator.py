from array import array
from copy import deepcopy
import ast
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from mecanum_base_bridge.sim_eval_wheel_odometry_emulator import (
    JOINT_NAMES,
    MAX_SOURCE_GAP_S,
    SimEvalWheelOdometryEmulator,
)


NAMES = [JOINT_NAMES[key] for key in ("FL", "FR", "RL", "RR")]


def message(stamp_ns, velocities, names=None):
    sec, nanosec = divmod(stamp_ns, 1_000_000_000)
    return NS(header=NS(stamp=NS(sec=sec, nanosec=nanosec)), name=NAMES.copy() if names is None else names,
              velocity=velocities)


def new_integrator():
    core = SimEvalWheelOdometryEmulator()
    assert core.process(message(1_000_000_000, [1.0] * 4)) is None
    return core


def test_array_double_sequence_baseline_then_integration_matches_list():
    rates = [1.5, 2.5, 3.5, 4.5]
    list_core = SimEvalWheelOdometryEmulator()
    array_core = SimEvalWheelOdometryEmulator()
    assert list_core.process(message(1_000_000_000, rates)) is None
    assert array_core.process(message(1_000_000_000, array("d", rates))) is None
    list_sample = list_core.process(message(1_100_000_000, rates))
    array_sample = array_core.process(message(1_100_000_000, array("d", rates)))
    assert array_sample is not None
    assert array_sample.linear_x == list_sample.linear_x
    assert array_sample.linear_y == list_sample.linear_y
    assert array_sample.angular_z == list_sample.angular_z
    assert (array_sample.x, array_sample.y, array_sample.yaw) == (list_sample.x, list_sample.y, list_sample.yaw)
    assert array_sample == list_sample
    assert array_sample.publishes_tf is False


@pytest.mark.parametrize(
    "bad_names,bad_velocity",
    [
        (NAMES[:-1], [1.0] * 3),
        (NAMES + [NAMES[0]], [1.0] * 5),
        (NAMES, [1.0] * 3),
        (NAMES, [1.0, float("nan"), 1.0, 1.0]),
        (NAMES, [1.0, float("inf"), 1.0, 1.0]),
        (NAMES, [1.0, True, 1.0, 1.0]),
    ],
)
def test_malformed_forward_sample_clears_interval_preserves_pose_and_rebaselines(bad_names, bad_velocity):
    core = new_integrator()
    trusted = core.process(message(1_100_000_000, [1.0] * 4))
    assert trusted is not None
    trusted_pose = core.trusted_pose
    assert core.process(message(1_200_000_000, bad_velocity, bad_names)) is None
    assert core.trusted_pose == trusted_pose
    assert core.last_stamp_ns is None
    assert core.process(message(1_300_000_000, [2.0] * 4)) is None
    resumed = core.process(message(1_400_000_000, [2.0] * 4))
    assert resumed is not None
    assert resumed.x - trusted_pose[0] == pytest.approx(resumed.linear_x * 0.1)
    assert resumed.stamp_ns == 1_400_000_000


def test_joint_reorder_is_resolved_by_joint_name():
    core = SimEvalWheelOdometryEmulator()
    reordered = [NAMES[2], NAMES[0], NAMES[3], NAMES[1]]
    rates = [3.0, 1.0, 4.0, 2.0]
    assert core.process(message(1_000_000_000, rates, reordered)) is None
    sample = core.process(message(1_100_000_000, rates, reordered))
    assert sample is not None
    reference = SimEvalWheelOdometryEmulator()
    ordered_rates = [1.0, 2.0, 3.0, 4.0]
    assert reference.process(message(1_000_000_000, ordered_rates)) is None
    assert reference.process(message(1_100_000_000, ordered_rates)) == sample


@pytest.mark.parametrize("bad_velocity", [(value for value in [1.0] * 4), "1,1,1,1", b"1234", bytearray(b"1234")])
def test_non_indexable_or_string_velocity_is_rejected(bad_velocity):
    core = SimEvalWheelOdometryEmulator()
    assert core.process(message(1_000_000_000, [1.0] * 4)) is None
    assert core.process(message(1_100_000_000, bad_velocity)) is None
    assert core.last_stamp_ns is None


def test_string_names_are_rejected_and_sequence_names_must_contain_strings():
    core = SimEvalWheelOdometryEmulator()
    assert core.process(message(1_000_000_000, [1.0] * 4, "|".join(NAMES))) is None
    assert core.process(message(1_100_000_000, [1.0] * 4, [*NAMES[:3], 4])) is None


@pytest.mark.parametrize("bad_stamp", [1_100_000_000, 1_400_000_001])
def test_duplicate_stamp_and_forward_gap_clear_interval_keep_trusted_pose(bad_stamp):
    core = SimEvalWheelOdometryEmulator()
    baseline = message(1_000_000_000, [1.0] * 4)
    assert core.process(baseline) is None
    accepted = core.process(message(1_100_000_000, [1.0] * 4))
    trusted_pose = core.trusted_pose
    assert accepted is not None
    assert core.process(message(bad_stamp, [1.0] * 4)) is None
    assert core.trusted_pose == trusted_pose
    assert core.last_stamp_ns is None


def test_timestamp_rollback_resets_pose_and_requires_new_baseline():
    core = new_integrator()
    assert core.process(message(1_100_000_000, [1.0] * 4)) is not None
    assert core.trusted_pose != (0.0, 0.0, 0.0)
    assert core.process(message(900_000_000, [1.0] * 4)) is None
    assert core.trusted_pose == (0.0, 0.0, 0.0)
    assert core.last_stamp_ns is None
    assert core.process(message(950_000_000, [1.0] * 4)) is None
    assert core.process(message(1_000_000_000, [1.0] * 4)) is not None


@pytest.mark.parametrize(
    "malformed_names,malformed_velocity",
    [
        (NAMES, [1.0, float("nan"), 1.0, 1.0]),
        (NAMES[:-1], [1.0, 1.0, 1.0]),
        (NAMES + [NAMES[0]], [1.0] * 5),
    ],
    ids=("nan-rate", "missing-joint", "duplicate-joint"),
)
def test_backward_timestamp_takes_precedence_over_malformed_wheel_payload(
    malformed_names, malformed_velocity
):
    core = new_integrator()
    assert core.process(message(1_100_000_000, [1.0] * 4)) is not None
    assert core.trusted_pose != (0.0, 0.0, 0.0)

    assert core.process(message(0, malformed_velocity, malformed_names)) is None
    assert core.trusted_pose == (0.0, 0.0, 0.0)
    assert core.last_stamp_ns is None

    assert core.process(message(100_000_000, [1.0] * 4)) is None
    assert core.last_stamp_ns == 100_000_000
    assert core.trusted_pose == (0.0, 0.0, 0.0)
    resumed = core.process(message(200_000_000, [1.0] * 4))
    assert resumed is not None
    assert resumed.stamp_ns == 200_000_000
    assert resumed.x > 0.0


def test_source_orders_timestamp_rollback_before_payload_validation_and_keeps_sequence_support():
    source_path = (
        Path(__file__).resolve().parents[1]
        / "mecanum_base_bridge"
        / "sim_eval_wheel_odometry_emulator.py"
    )
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    process = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "process"
    )
    process_text = ast.get_source_segment(source, process)
    stamp_call = process_text.index("stamp_ns = self._stamp_ns(message)")
    rollback_check = process_text.index("stamp_ns < self._last_stamp_ns")
    rollback_reset = process_text.index("self.reset_pose_and_baseline()", rollback_check)
    payload_access = min(process_text.index("message.name"), process_text.index("message.velocity"))
    assert stamp_call < rollback_check < rollback_reset < payload_access
    assert "from collections.abc import Sequence" in source
    assert "isinstance(value, Sequence)" in source
    assert "array(" not in source  # array.array is accepted through Sequence, without source coercion.
    assert "type(names) in (list, tuple)" not in source

    # Keep direct behavioral evidence that ROSIDL's array('d') survives both stages.
    core = SimEvalWheelOdometryEmulator()
    values = array("d", [1.0] * 4)
    assert core.process(message(1_000_000_000, values)) is None
    assert core.process(message(1_100_000_000, array("d", values))) is not None


def test_nonfinite_kinematics_does_not_mutate_trusted_pose():
    core = new_integrator()
    assert core.process(message(1_100_000_000, [1.0] * 4)) is not None
    pose = deepcopy(core.trusted_pose)
    assert core.process(message(1_200_000_000, [1e308] * 4)) is None
    assert core.trusted_pose == pose
    assert core.last_stamp_ns is None


def test_covariance_is_finite_diagonal_and_no_tf():
    core = SimEvalWheelOdometryEmulator()
    assert core.process(message(1_000_000_000, [1.0] * 4)) is None
    sample = core.process(message(1_100_000_000, [1.0] * 4))
    assert sample.publishes_tf is False
    for matrix in (sample.pose_covariance, sample.twist_covariance):
        assert len(matrix) == 36
        assert all(value == value and abs(value) != float("inf") for value in matrix)
        assert all(matrix[row * 6 + column] == 0.0 for row in range(6) for column in range(6) if row != column)
    assert MAX_SOURCE_GAP_S == 0.20
