import importlib.util
import math
from pathlib import Path

from mecanum_nav_rl.observations.step07_gate_b_observer_node import validate_vector_samples


def test_accepts_five_immutable_finite_observation81_samples():
    rows = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81}
            for i in range(1, 6)]
    assert validate_vector_samples(rows)


def test_rejects_partial_nonfinite_and_nonmonotonic_vectors():
    row = {"stamp_ns": 1, "dimension": 81, "dtype": "float32", "values": [0.0] * 81}
    assert not validate_vector_samples([row] * 4)
    bad = [dict(row, stamp_ns=i, values=[0.0] * 80) for i in range(1, 6)]
    assert not validate_vector_samples(bad)
    bad = [dict(row, stamp_ns=i, values=[float("nan")] + [0.0] * 80) for i in range(1, 6)]
    assert not validate_vector_samples(bad)
    bad = [dict(row, stamp_ns=1, values=[0.0] * 81) for _ in range(5)]
    assert not validate_vector_samples(bad)


def test_runtime_observer_source_has_no_with_info_or_command_publisher():
    path = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "step07_gate_b_observer_node.py"
    source = path.read_text(encoding="utf-8")
    assert "with_info" not in source
    assert "create_publisher" not in source
    assert "cmd_vel" not in source


def test_local_reference_adapter_uses_successful_compute_path_result_only():
    source = (Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "step07_gate_b_observer_node.py").read_text(encoding="utf-8")
    assert "STATUS_SUCCEEDED" in source
    assert "ComputePathToPose" in source
    assert "_features_from_path" in source
    assert '"map"' in source and '"base_link"' in source
