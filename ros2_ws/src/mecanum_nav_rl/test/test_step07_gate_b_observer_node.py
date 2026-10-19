import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

from mecanum_nav_rl.observations.step07_gate_b_observer_node import (
    LIFECYCLE_STATE_QOS_CONTRACT, LIFECYCLE_STATE_TOPIC,
    lifecycle_state_qos_profile, validate_vector_samples,
)


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


def test_lifecycle_qos_is_reliable_volatile_keep_last_ten_and_separate_from_receipt():
    captured = {}
    def profile(**kwargs):
        captured.update(kwargs)
        return kwargs
    qos = SimpleNamespace(
        QoSProfile=profile,
        HistoryPolicy=SimpleNamespace(KEEP_LAST="KEEP_LAST"),
        ReliabilityPolicy=SimpleNamespace(RELIABLE="RELIABLE"),
        DurabilityPolicy=SimpleNamespace(VOLATILE="VOLATILE"),
    )
    assert lifecycle_state_qos_profile(qos) == {
        "history": "KEEP_LAST", "depth": 10,
        "reliability": "RELIABLE", "durability": "VOLATILE",
    }
    assert LIFECYCLE_STATE_QOS_CONTRACT == {
        "history": "KEEP_LAST", "depth": 10,
        "reliability": "RELIABLE", "durability": "VOLATILE",
    }
    assert LIFECYCLE_STATE_TOPIC == "/mecanum/safety_lifecycle_state"


def test_lifecycle_contract_is_consistent_across_publisher_both_observers_and_validator():
    root = Path(__file__).parents[4]
    py_observer = (root / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py").read_text(encoding="utf-8")
    cpp_observer = (root / "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp").read_text(encoding="utf-8")
    publisher = (root / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py").read_text(encoding="utf-8")
    validator = (root / "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py").read_text(encoding="utf-8")
    canonical = "/mecanum/safety_lifecycle_state"
    obsolete = "/mecanum/safety/lifecycle_state"
    assert canonical in publisher and canonical in py_observer and canonical in cpp_observer
    assert 'SafetyLifecycleState, LIFECYCLE_STATE_TOPIC, self._lifecycle, lifecycle_qos' in py_observer
    assert 'SafetyLifecycleState>("/mecanum/safety_lifecycle_state", lifecycle_qos' in cpp_observer
    assert 'durability=qos.DurabilityPolicy.VOLATILE' in py_observer
    assert 'QoS(rclcpp::KeepLast(10)).reliable().durability_volatile()' in cpp_observer
    assert 'durability=DurabilityPolicy.VOLATILE' in publisher
    assert 'depth=10' in publisher and 'depth=10' in py_observer
    assert 'lifecycle_endpoint_qos_contract' in validator
    # The legacy string may appear only as a rejection/snapshot key, never as a subscription target.
    assert obsolete not in [line for line in py_observer.splitlines() if "create_subscription" in line]
    assert obsolete not in [line for line in cpp_observer.splitlines() if "create_subscription" in line]
    lifecycle_qos_body = py_observer.split("def lifecycle_state_qos_profile", 1)[1].split("def _json_bytes", 1)[0]
    assert "TRANSIENT_LOCAL" not in lifecycle_qos_body
