from types import SimpleNamespace as NS

import pytest

from mecanum_base_bridge.sim_eval_imu_runtime_evidence import (
    ImuEvidenceParseError,
    parse_single_imu_message,
)
from mecanum_base_bridge.sim_eval_imu_normalizer import SimEvalImuNormalizer


def imu(stamp_ns, frame="base_link", q=(0.0, 0.0, 0.0, 1.0), w=(0.1, 0.2, 0.3), a=(1.0, 2.0, 3.0)):
    sec, nanosec = divmod(stamp_ns, 1_000_000_000)
    return NS(header=NS(stamp=NS(sec=sec, nanosec=nanosec), frame_id=frame),
              orientation=NS(x=q[0], y=q[1], z=q[2], w=q[3]),
              angular_velocity=NS(x=w[0], y=w[1], z=w[2]),
              linear_acceleration=NS(x=a[0], y=a[1], z=a[2]))


def test_valid_imu_keeps_stamp_values_and_sets_exact_covariance():
    core = SimEvalImuNormalizer()
    sample = core.process(imu(1_000_000_001))
    assert sample.stamp_ns == 1_000_000_001
    assert sample.frame_id == "base_link"
    assert sample.orientation_xyzw == (0.0, 0.0, 0.0, 1.0)
    assert sample.angular_velocity_xyz == (0.1, 0.2, 0.3)
    assert sample.linear_acceleration_xyz == (1.0, 2.0, 3.0)
    assert sample.publishes_tf is False
    assert tuple(sample.orientation_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0, 1_000_000.0, 0.007615435)
    assert tuple(sample.angular_velocity_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0, 1_000_000.0, 0.01)
    assert tuple(sample.linear_acceleration_covariance[i * 3 + i] for i in range(3)) == (1_000_000.0,) * 3


def test_wrong_frame_invalid_quaternion_and_nonfinite_are_dropped():
    core = SimEvalImuNormalizer()
    assert core.process(imu(1_000_000_000, frame="imu_link")) is None
    assert core.process(imu(1_000_000_000, q=(0.0, 0.0, 0.0, 0.5))) is None
    assert core.process(imu(1_000_000_000, w=(float("nan"), 0.0, 0.0))) is None
    assert core.process(imu(1_000_000_000, a=(0.0, float("inf"), 0.0))) is None
    assert core.process(imu(1_000_000_000, q=(True, 0.0, 0.0, 1.0))) is None


def test_duplicate_or_rollback_stamp_is_dropped_without_rewinding_accepted_stamp():
    core = SimEvalImuNormalizer()
    assert core.process(imu(1_000_000_000)) is not None
    assert core.process(imu(1_000_000_000)) is None
    assert core.process(imu(1_100_000_000)) is not None
    assert core.process(imu(1_050_000_000)) is None
    assert core.process(imu(1_200_000_000)) is not None


def test_diagnostic_api_reports_exact_first_rejection_gate_without_changing_process_contract():
    cases = (
        (imu(-1), "stamp"),
        (imu(1_000_000_000, frame="imu_link"), "frame_id"),
        (imu(1_000_000_000, w=(float("nan"), 0.0, 0.0)), "finite_values"),
        (imu(1_000_000_000, q=(0.0, 0.0, 0.0, 0.5)), "quaternion_norm"),
    )
    for message, expected_gate in cases:
        sample, details = SimEvalImuNormalizer().process_with_diagnostics(message)
        assert sample is None
        assert details["accepted"] is False
        assert details["rejection_gate"] == expected_gate
        assert "stamp" in details
        assert "frame_id" in details
        assert "finite_values" in details
        assert "values" in details
        assert "quaternion_norm" in details
        assert "monotonic_timestamp" in details

    core = SimEvalImuNormalizer()
    accepted, accepted_details = core.process_with_diagnostics(imu(1_000_000_000))
    assert accepted is not None
    assert accepted_details["accepted"] is True
    assert accepted_details["rejection_gate"] is None
    rejected, repeated = core.process_with_diagnostics(imu(1_000_000_000))
    assert rejected is None
    assert repeated["rejection_gate"] == "monotonic_timestamp"
    assert repeated["monotonic_timestamp"] == {
        "last_accepted_stamp_ns": 1_000_000_000,
        "strictly_increasing": False,
    }


def test_runtime_imu_transcript_parser_uses_multi_document_yaml_and_requires_one_mapping():
    raw = b"header:\n  frame_id: base_link\norientation:\n  w: 1.0\n---\n"
    assert parse_single_imu_message(raw) == {
        "header": {"frame_id": "base_link"},
        "orientation": {"w": 1.0},
    }
    with pytest.raises(ImuEvidenceParseError, match="found 2"):
        parse_single_imu_message("header: {}\n---\nheader: {}\n")
    with pytest.raises(ImuEvidenceParseError, match="malformed YAML"):
        parse_single_imu_message("header: [\n")
