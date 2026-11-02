"""Capacity-one, approval-bound guard for B22_GUI_OBSERVATION_RUN001."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


RUN_ID = 'B22_GUI_OBSERVATION_RUN001'
PRODUCTION_SOURCE_PIN = '7d4f2ad1c38c8021f13a6a88ebf707053718eb02'
MANIFEST_SHA256 = (
    '200035538282ce7035ae1b48f25fc25359d8bf7cf5c3476caa8a38286d1a5b0c'
)
RESOLVED_SHA256 = (
    '9e75df82e30d61f03eeba7d503b8f85277e03f0163abee0a8dcb79850f9d5ba3'
)
CONFIG_HASH = (
    'e0743e903cbc5edf417084d114ad632ff5c34be404a5a144aae96dcc49c44ac7'
)
SCENARIO_SHA256 = (
    '9140e53daa5408af8b0897b6cf007847eef9048ffb40bbefddc61115123d4ea4'
)
GUARD_PATH = Path(
    '/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN001/'
    'acquisition.json'
)


class GuardError(RuntimeError):
    """Raised when approval pins or capacity-one state are invalid."""


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file incrementally without loading its full contents."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def tool_hashes(tool_paths: dict[str, Path]) -> dict[str, str]:
    """Return tool hashes in deterministic name order."""
    return {
        name: sha256_file(path)
        for name, path in sorted(tool_paths.items())
    }


def validate_approval(
    *, packet_path: Path, approval_path: Path, expected_commit: str,
    tool_paths: dict[str, Path],
) -> tuple[dict[str, object], str, dict[str, str]]:
    """Check a separately supplied Owner approval without side effects."""
    packet_bytes = packet_path.read_bytes()
    packet_hash = sha256_bytes(packet_bytes)
    packet = json.loads(packet_bytes)
    approval = json.loads(approval_path.read_text(encoding='utf-8'))
    actual_tools = tool_hashes(tool_paths)
    required = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': RUN_ID,
        'packet_sha256': packet_hash,
        'packet_commit': expected_commit,
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'tool_sha256': actual_tools,
    }
    for field, expected in required.items():
        if approval.get(field) != expected:
            raise GuardError(f'Owner approval mismatch: {field}')
    if packet.get('run_id') != RUN_ID:
        raise GuardError('packet run_id mismatch')
    if packet.get('production_source_pin') != PRODUCTION_SOURCE_PIN:
        raise GuardError('packet production source pin mismatch')
    if packet.get('tool_sha256') != actual_tools:
        raise GuardError('packet tool hashes differ from current tool bytes')
    return packet, packet_hash, actual_tools


def acquire_once(
    path: Path, payload: dict[str, object], *, open_fn=os.open,
) -> None:
    """Create acquisition exclusively; a partial file consumes the run."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = open_fn(path, flags, 0o600)
    except FileExistsError as error:
        raise GuardError('capacity-one acquisition already exists') from error
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, sort_keys=True, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Deliberately retain the partial file: it is still consumed.
        raise
