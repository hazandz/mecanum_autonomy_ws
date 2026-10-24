import hashlib
import json

import pytest

from mecanum_nav_rl.observations.step07_lifecycle_ingress import (
    MAX_ARTIFACT_BYTES,
    SCHEMA,
    LifecycleIngressClient,
    atomic_write,
    canonical_json_bytes,
)


def _client(tmp_path):
    return LifecycleIngressClient(
        live_path=tmp_path / "lifecycle_ingress.live.json",
        references_path=tmp_path / "lifecycle_ingress.references.json",
        final_path=tmp_path / "lifecycle_ingress.final.json",
        invocation_id="invocation-test", collector_session_id="session-test",
        config_hash="a" * 64)


def _record(index=1, sequence=4, gid="11" * 24):
    return {"record_index": index, "sequence": sequence,
            "receive_time": {"clock": "CLOCK_MONOTONIC", "monotonic_ns": index * 10},
            "ros_stamp_ns": index * 100, "publisher_gid": gid,
            "payload_provenance": "rclcpp::MessageInfo.publisher_gid",
            "payload": {"sequence": sequence, "motion_permitted": True}, "validity": "ADMITTED"}


def _live(records=None, **overrides):
    document = {"schema": SCHEMA, "schema_version": "1.0", "invocation_id": "invocation-test",
        "collector_session_id": "session-test", "config_hash": "a" * 64, "state": "READY",
        "protocol_revision": "2.0",
        "failure": None, "endpoint_binding": {
            "publisher_gid": "11" * 24,
            "topic": "/mecanum/safety_lifecycle_state",
            "type": "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState",
            "node_name": "safety_lifecycle", "node_namespace": "/",
            "reliability": 1, "durability": 2,
            "qos_history_depth_status": "UNOBSERVABLE",
        },
        "records": [_record()] if records is None else records,
        "acknowledged_references": [], "reference_ack": {},
        "retained_reference_count": 0, "record_index_next": 2}
    document.update(overrides)
    return document


def test_bounded_atomic_reader_and_exact_identity(tmp_path):
    client = _client(tmp_path)
    atomic_write(client.live_path, _live(), maximum=MAX_ARTIFACT_BYTES)
    assert client.read_live()["records"][0]["record_index"] == 1
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        atomic_write(client.live_path, _live(invocation_id="wrong"), maximum=MAX_ARTIFACT_BYTES)
        client.read_live()


def test_reader_rejects_extra_publisher_context_failure_and_record_order(tmp_path):
    client = _client(tmp_path)
    for document in (
        _live(state="FAILED"),
        _live(records=[_record(2), _record(1)]),
        _live(endpoint_binding={"publisher_gid": "22" * 24}),
    ):
        atomic_write(client.live_path, document, maximum=MAX_ARTIFACT_BYTES)
        with pytest.raises(ValueError):
            client.read_live()


def test_reader_rejects_symlink_duplicate_nonfinite_and_oversize(tmp_path):
    client = _client(tmp_path)
    target = tmp_path / "real.json"
    target.write_text(canonical_json_bytes(_live()).decode(), encoding="utf-8")
    client.live_path.symlink_to(target)
    with pytest.raises(ValueError, match="SYMLINK"):
        client.read_live()
    client.live_path.unlink()
    client.live_path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON_INVALID"):
        client.read_live()
    client.live_path.write_text('{"x":NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON_INVALID"):
        client.read_live()
    client.live_path.write_bytes(b" " * (MAX_ARTIFACT_BYTES + 1))
    with pytest.raises(ValueError, match="SIZE|OVERSIZE"):
        client.read_live()


def test_reference_request_is_bounded_and_ack_requires_exact_hash(tmp_path):
    client = _client(tmp_path)
    row = _record()
    request_hash = client.request_references([row])
    request = json.loads(client.references_path.read_text(encoding="utf-8"))
    assert request_hash == hashlib.sha256(client.references_path.read_bytes()).hexdigest()
    digest = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
    assert request["protocol_revision"] == "2.0"
    assert request["operation"] == "RESERVE"
    assert request["record_index"] == 1
    assert request["record_sha256"] == digest
    unsigned = dict(request); request_digest = unsigned.pop("request_digest")
    assert request_digest == hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    assert not client.acknowledged(_live())
    doc = _live(reference_ack={"revision": request["request_revision"],
        "request_digest": request_digest, "operation": "RESERVE", "record_index": 1,
        "record_sha256": digest, "status": "ACKNOWLEDGED"})
    assert client.acknowledged(doc)


def test_reference_protocol_promotes_and_releases_pending_without_revision_reuse(tmp_path):
    client = _client(tmp_path)
    row = _record()
    digest = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
    client.request_references([row])
    reserve = json.loads(client.references_path.read_text())
    client.acknowledged(_live(reference_ack={"revision": 1,
        "request_digest": reserve["request_digest"], "operation": "RESERVE",
        "record_index": 1, "record_sha256": digest, "status": "ACKNOWLEDGED"}))
    client.promote_reference(row, sample_references=[{"record_index": 1, "record_sha256": digest}])
    promote = json.loads(client.references_path.read_text())
    assert promote["request_revision"] == 2 and promote["operation"] == "PROMOTE"
    client.acknowledged(_live(reference_ack={"revision": 2,
        "request_digest": promote["request_digest"], "operation": "PROMOTE",
        "record_index": 1, "record_sha256": digest, "status": "ACKNOWLEDGED"}))
    client.request_references([row], sample_references=[{"record_index": 1,
        "record_sha256": digest}])
    repeated = json.loads(client.references_path.read_text())
    assert repeated["request_revision"] == 3 and repeated["operation"] == "RESERVE"


def test_repeated_discarded_pending_reservations_release_without_capacity_leak(tmp_path):
    client = _client(tmp_path)
    row = _record()
    digest = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
    sample_refs = []
    for _ in range(8):
        client.request_references([row], sample_references=sample_refs)
        reserve = json.loads(client.references_path.read_text(encoding="utf-8"))
        assert client.acknowledged(_live(reference_ack={
            "revision": reserve["request_revision"], "request_digest": reserve["request_digest"],
            "operation": "RESERVE", "record_index": 1, "record_sha256": digest,
            "status": "ACKNOWLEDGED"}))
        client.release_reference(row, sample_references=sample_refs)
        release = json.loads(client.references_path.read_text(encoding="utf-8"))
        assert release["request_revision"] == reserve["request_revision"] + 1
        assert client.acknowledged(_live(reference_ack={
            "revision": release["request_revision"], "request_digest": release["request_digest"],
            "operation": "RELEASE", "record_index": 1, "record_sha256": digest,
            "status": "ACKNOWLEDGED"}))
    assert client._pending is None
    assert client._committed == {}
    client.request_references([row], sample_references=sample_refs)
    assert json.loads(client.references_path.read_text(encoding="utf-8"))["operation"] == "RESERVE"


def test_five_samples_may_reference_one_committed_native_record(tmp_path):
    client = _client(tmp_path)
    row = _record()
    digest = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
    client.request_references([row], sample_references=[])
    request = json.loads(client.references_path.read_text(encoding="utf-8"))
    client.acknowledged(_live(reference_ack={"revision": request["request_revision"],
        "request_digest": request["request_digest"], "operation": "RESERVE",
        "record_index": 1, "record_sha256": digest, "status": "ACKNOWLEDGED"}))
    refs = []
    for _ in range(5):
        refs.append({"record_index": 1, "record_sha256": digest})
        client.promote_reference(row, sample_references=refs)
        request = json.loads(client.references_path.read_text(encoding="utf-8"))
        assert client.acknowledged(_live(reference_ack={
            "revision": request["request_revision"], "request_digest": request["request_digest"],
            "operation": "PROMOTE", "record_index": 1, "record_sha256": digest,
            "status": "ACKNOWLEDGED"}))
    assert client._committed == {1: digest}
    assert client._sample_references == refs and len(refs) == 5


def test_wrong_session_and_final_missing_reference_fail_closed(tmp_path):
    client = _client(tmp_path)
    atomic_write(client.live_path, _live(collector_session_id="wrong"), maximum=MAX_ARTIFACT_BYTES)
    with pytest.raises(ValueError, match="IDENTITY_MISMATCH"):
        client.read_live()
