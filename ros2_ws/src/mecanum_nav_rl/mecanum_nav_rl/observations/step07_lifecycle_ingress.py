"""Bounded reader/reference client for the native Run005 lifecycle ingress."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

SCHEMA = "mecanum.step07-run005.lifecycle-ingress/v1"
MAX_RECORDS = 64
MAX_RECORD_BYTES = 8192
MAX_ARTIFACT_BYTES = 1_048_576
MAX_REFERENCES = 5
PROTOCOL_REVISION = "2.0"


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        if key in result:
            raise ValueError("LIFECYCLE_INGRESS_DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise ValueError("LIFECYCLE_INGRESS_NONFINITE_JSON")


def canonical_json_bytes(document: Any) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_bounded(path: Path, maximum: int) -> bytes:
    if path.is_symlink():
        raise ValueError("LIFECYCLE_INGRESS_SYMLINK_FORBIDDEN")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise ValueError("LIFECYCLE_INGRESS_READ_FAILED") from error
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("LIFECYCLE_INGRESS_FILE_TYPE_OR_SIZE_INVALID")
        chunks = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > maximum:
            raise ValueError("LIFECYCLE_INGRESS_FILE_OVERSIZE")
        return raw
    finally:
        os.close(fd)


def strict_json(path: str | Path, *, maximum: int) -> tuple[dict[str, Any], bytes]:
    raw = _read_bounded(Path(path), maximum)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("LIFECYCLE_INGRESS_BOM_FORBIDDEN")
    try:
        document = json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("LIFECYCLE_INGRESS_JSON_INVALID") from error
    if type(document) is not dict:
        raise ValueError("LIFECYCLE_INGRESS_ROOT_INVALID")
    return document, raw


def atomic_write(path: str | Path, document: dict[str, Any], *, maximum: int) -> bytes:
    target = Path(path)
    if target.parent.is_symlink():
        raise ValueError("LIFECYCLE_INGRESS_PARENT_SYMLINK_FORBIDDEN")
    raw = canonical_json_bytes(document)
    if len(raw) > maximum:
        raise ValueError("LIFECYCLE_INGRESS_ARTIFACT_OVERSIZE")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    return raw


class LifecycleIngressClient:
    def __init__(self, *, live_path: str | Path, references_path: str | Path,
                 final_path: str | Path, invocation_id: str, collector_session_id: str,
                 config_hash: str):
        if not invocation_id or not collector_session_id or len(config_hash) != 64:
            raise ValueError("LIFECYCLE_INGRESS_CLIENT_IDENTITY_INVALID")
        self.live_path = Path(live_path)
        self.references_path = Path(references_path)
        self.final_path = Path(final_path)
        self.invocation_id = invocation_id
        self.collector_session_id = collector_session_id
        self.config_hash = config_hash
        self._revision = 0
        self._expected_ack: dict[str, Any] | None = None
        self._committed: dict[int, str] = {}
        self._pending: tuple[int, str] | None = None
        self._expected_sample_references: list[dict[str, Any]] | None = None
        self._sample_references: list[dict[str, Any]] = []

    def read_live(self) -> dict[str, Any]:
        document, _ = strict_json(self.live_path, maximum=MAX_ARTIFACT_BYTES)
        if (document.get("schema") != SCHEMA or document.get("schema_version") != "1.0"
                or document.get("protocol_revision") != PROTOCOL_REVISION
                or document.get("invocation_id") != self.invocation_id
                or document.get("collector_session_id") != self.collector_session_id
                or document.get("config_hash") != self.config_hash):
            raise ValueError("LIFECYCLE_INGRESS_IDENTITY_MISMATCH")
        if document.get("state") == "FAILED":
            raise ValueError("LIFECYCLE_INGRESS_NATIVE_FAILURE")
        endpoint = document.get("endpoint_binding")
        if (type(endpoint) is not dict or endpoint.get("publisher_gid") in (None, "")
                or endpoint.get("topic") != "/mecanum/safety_lifecycle_state"
                or endpoint.get("type") != "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState"
                or endpoint.get("node_name") != "safety_lifecycle"
                or endpoint.get("node_namespace") != "/"
                or endpoint.get("reliability") != 1 or endpoint.get("durability") != 2
                or endpoint.get("qos_history_depth_status") not in ("OBSERVED_MATCH", "UNOBSERVABLE")):
            raise ValueError("LIFECYCLE_INGRESS_ENDPOINT_NOT_PINNED")
        records = document.get("records")
        if type(records) is not list or len(records) > MAX_RECORDS:
            raise ValueError("LIFECYCLE_INGRESS_RECORD_WINDOW_INVALID")
        previous_index = 0
        previous_sequence = -1
        for row in records:
            if type(row) is not dict:
                raise ValueError("LIFECYCLE_INGRESS_RECORD_INVALID")
            serialized = canonical_json_bytes(row)
            if len(serialized) > MAX_RECORD_BYTES:
                raise ValueError("LIFECYCLE_INGRESS_RECORD_OVERSIZE")
            index = row.get("record_index")
            sequence = row.get("sequence")
            receive = row.get("receive_time")
            if (type(index) is not int or index <= previous_index or type(sequence) is not int
                    or sequence < previous_sequence or type(receive) is not dict
                    or receive.get("clock") != "CLOCK_MONOTONIC"
                    or type(receive.get("monotonic_ns")) is not int
                    or row.get("publisher_gid") != endpoint.get("publisher_gid")
                    or row.get("validity") != "ADMITTED"
                    or row.get("payload_provenance") != "rclcpp::MessageInfo.publisher_gid"
                    or type(row.get("payload")) is not dict
                    or row["payload"].get("sequence") != sequence):
                raise ValueError("LIFECYCLE_INGRESS_RECORD_ORDER_OR_PROVENANCE_INVALID")
            previous_index, previous_sequence = index, sequence
        if type(document.get("acknowledged_references")) is not list:
            raise ValueError("LIFECYCLE_INGRESS_ACK_SCHEMA_INVALID")
        return document

    def _request(self, operation: str, row: dict[str, Any],
                 sample_references: list[dict[str, Any]] | None = None) -> str:
        if type(row) is not dict or type(row.get("record_index")) is not int:
            raise ValueError("LIFECYCLE_INGRESS_REFERENCE_INVALID")
        index = row["record_index"]
        digest = hashlib.sha256(canonical_json_bytes(row)).hexdigest()
        if operation == "RESERVE":
            if self._pending is not None and self._pending != (index, digest):
                raise ValueError("LIFECYCLE_INGRESS_PENDING_REFERENCE_ALREADY_RESERVED")
            if index not in self._committed:
                if len(self._committed) >= MAX_REFERENCES:
                    raise ValueError("LIFECYCLE_INGRESS_COMMITTED_REFERENCE_LIMIT_EXCEEDED")
                self._pending = (index, digest)
        elif operation == "PROMOTE":
            if index not in self._committed and self._pending != (index, digest):
                raise ValueError("LIFECYCLE_INGRESS_PROMOTION_WITHOUT_RESERVATION")
        elif operation == "RELEASE":
            if self._pending != (index, digest):
                raise ValueError("LIFECYCLE_INGRESS_RELEASE_WITHOUT_RESERVATION")
        else:
            raise ValueError("LIFECYCLE_INGRESS_OPERATION_INVALID")
        if self._revision >= 2**64 - 1:
            raise ValueError("LIFECYCLE_INGRESS_REVISION_OVERFLOW")
        self._revision += 1
        refs = sample_references if sample_references is not None else []
        if type(refs) is not list or len(refs) > MAX_REFERENCES:
            raise ValueError("LIFECYCLE_INGRESS_SAMPLE_REFERENCE_COUNT_INVALID")
        normalized_refs = [{"record_index": item.get("record_index"),
            "record_sha256": item.get("record_sha256")} for item in refs if type(item) is dict]
        if len(normalized_refs) != len(refs):
            raise ValueError("LIFECYCLE_INGRESS_SAMPLE_REFERENCE_ROW_INVALID")
        target_ref = {"record_index": index, "record_sha256": digest}
        if operation == "PROMOTE":
            if normalized_refs != [*self._sample_references, target_ref]:
                raise ValueError("LIFECYCLE_INGRESS_SAMPLE_REFERENCE_ORDER_MISMATCH")
        elif normalized_refs != self._sample_references:
            raise ValueError("LIFECYCLE_INGRESS_SAMPLE_REFERENCE_ORDER_MISMATCH")
        request = {"schema": SCHEMA, "schema_version": "1.0",
                   "protocol_revision": PROTOCOL_REVISION,
                   "invocation_id": self.invocation_id,
                   "collector_session_id": self.collector_session_id,
                   "config_hash": self.config_hash,
                   "request_revision": self._revision,
                   "operation": operation, "record_index": index,
                   "record_sha256": digest,
                   "references": refs}
        request_digest = hashlib.sha256(canonical_json_bytes(request)).hexdigest()
        request["request_digest"] = request_digest
        raw = atomic_write(self.references_path, request, maximum=8192)
        self._expected_ack = {"revision": self._revision, "request_digest": request_digest,
                              "operation": operation, "record_index": index,
                              "record_sha256": digest}
        self._expected_sample_references = normalized_refs
        return hashlib.sha256(raw).hexdigest()

    def request_references(self, records: list[dict[str, Any]], *,
                           sample_references: list[dict[str, Any]] | None = None) -> str:
        if type(records) is not list or len(records) != 1:
            raise ValueError("LIFECYCLE_INGRESS_REFERENCE_OPERATION_REQUIRES_ONE_RECORD")
        return self._request("RESERVE", records[0], sample_references)

    def promote_reference(self, row: dict[str, Any], *,
                          sample_references: list[dict[str, Any]]) -> str:
        return self._request("PROMOTE", row, sample_references)

    def release_reference(self, row: dict[str, Any], *,
                          sample_references: list[dict[str, Any]]) -> str:
        return self._request("RELEASE", row, sample_references)

    def acknowledged(self, document: dict[str, Any]) -> bool:
        expected = self._expected_ack
        ack = document.get("reference_ack")
        if (expected is None or document.get("protocol_revision") != PROTOCOL_REVISION
                or type(ack) is not dict or ack.get("status") != "ACKNOWLEDGED"
                or any(ack.get(key) != value for key, value in expected.items())):
            return False
        operation, index, digest = expected["operation"], expected["record_index"], expected["record_sha256"]
        if operation == "PROMOTE":
            self._committed[index] = digest
            if self._pending == (index, digest):
                self._pending = None
            self._sample_references = list(self._expected_sample_references or [])
        elif operation == "RELEASE":
            self._pending = None
        return True

    def verify_final(self) -> dict[str, Any]:
        final, _ = strict_json(self.final_path, maximum=MAX_ARTIFACT_BYTES)
        if (final.get("schema") != SCHEMA or final.get("schema_version") != "1.0"
                or final.get("protocol_revision") != PROTOCOL_REVISION
                or final.get("invocation_id") != self.invocation_id
                or final.get("collector_session_id") != self.collector_session_id
                or final.get("config_hash") != self.config_hash or final.get("state") != "FINALIZED"):
            raise ValueError("LIFECYCLE_INGRESS_FINAL_IDENTITY_OR_STATE_INVALID")
        rows = final.get("retained_references")
        if type(rows) is not list or len(rows) > MAX_REFERENCES:
            raise ValueError("LIFECYCLE_INGRESS_FINAL_REFERENCES_INVALID")
        expected = [{"record_index": index, "record_sha256": digest}
                    for index, digest in sorted(self._committed.items())]
        if final.get("committed_references") != expected:
            raise ValueError("LIFECYCLE_INGRESS_FINAL_REFERENCE_SET_MISMATCH")
        return final
