"""Capacity-one approval guard for Codex-owned GUI observation RUN002."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any


RUN_ID = 'B22_GUI_OBSERVATION_RUN002'
PACKET_SCHEMA_ID = 'b22_codex_owned_gui_observation_packet/v1'
APPROVAL_SCHEMA_ID = 'b22_gui_observation_owner_approval/v1'
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
STARTING_HEAD = '1060c7832c4b6a3c8cb12bb70182492e9b884423'
STARTING_PARENT = '6f510b3048bd45030dd75418a820a684920c5a37'
ORIGIN = 'https://github.com/hazandz/mecanum_autonomy_ws.git'
BRANCH = 'roadmap-b-b22-simulation-substrate'
ARCHITECTURE_SHA256 = (
    '432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204'
)
EVIDENCE_ROOT = Path(
    '/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002'
)
GUARD_PATH = EVIDENCE_ROOT / 'acquisition.json'
APPROVAL_PATH = Path(
    '/home/hazan/mecanum_runtime_approvals/'
    'B22_GUI_OBSERVATION_RUN002.owner.json'
)
PACKET_PATH = Path(__file__).resolve().parents[1] / 'packet.json'
TOOL_DIR = Path(__file__).resolve().parent
TOOL_NAMES = (
    'observation_guard.py', 'observation_runner.py',
    'observation_sink.py', 'test_observation_packet.py',
)
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_UUID = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z'
)
PACKET_FIELDS = {
    'schema_id', 'schema_version', 'run_id', 'capacity', 'gui',
    'repository', 'identity', 'scenario', 'composition', 'installation',
    'inputs', 'tool_sha256', 'host_capabilities', 'capture', 'mailbox',
    'timing', 'operations', 'approval_boundary', 'runtime_authorization',
    'acceptance', 'evidence', 'guard', 'commands_argv',
}


class GuardError(RuntimeError):
    """A pinned packet, approval, path or acquisition invariant failed."""


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 digest of a byte string."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file incrementally without loading it all into memory."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GuardError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def _reject_constant(value):
    raise GuardError(f'non-finite JSON value is forbidden: {value}')


def strict_json_loads(data: bytes, *, max_bytes: int = 16 * 1024) -> Any:
    """Parse bounded JSON while rejecting ambiguous encodings and keys."""
    if len(data) > max_bytes:
        raise GuardError('JSON exceeds the declared byte limit')
    try:
        text = data.decode('utf-8', errors='strict')
        return json.loads(
            text, object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError(f'invalid UTF-8 JSON: {error}') from error


def _mapping(value: Any, name: str, fields=None) -> dict:
    if not isinstance(value, dict):
        raise GuardError(f'{name} must be an object')
    if fields is not None and set(value) != set(fields):
        raise GuardError(f'{name} fields do not match the canonical schema')
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise GuardError(f'{name} must be non-empty text')
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise GuardError(f'{name} must be a lowercase SHA-256')
    return value


def _integer(value: Any, name: str, *, minimum=0, maximum=None) -> int:
    if type(value) is not int or value < minimum:
        raise GuardError(f'{name} must be an integer >= {minimum}')
    if maximum is not None and value > maximum:
        raise GuardError(f'{name} exceeds its maximum')
    return value


def _exact(value: Any, expected: Any, name: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise GuardError(f'{name} pin mismatch')


def packet_bindings(packet: dict[str, Any], tool_hashes: dict[str, str]):
    """Validate the canonical RUN002 packet schema before side effects."""
    packet = _mapping(packet, 'packet', PACKET_FIELDS)
    fixed = {
        'schema_id': PACKET_SCHEMA_ID, 'schema_version': 1,
        'run_id': RUN_ID, 'capacity': 1, 'gui': True,
    }
    for key, expected in fixed.items():
        _exact(packet.get(key), expected, key)
    repository = _mapping(packet['repository'], 'repository', {
        'origin', 'branch', 'starting_head', 'starting_sole_parent',
        'expected_remote_integration', 'architecture_sha256',
        'production_source_pin', 'remote_status_at_executor',
    })
    expected_repository = {
        'origin': ORIGIN, 'branch': BRANCH, 'starting_head': STARTING_HEAD,
        'starting_sole_parent': STARTING_PARENT,
        'expected_remote_integration': (
            'ef9e0281cfb9de04d89a2698d6d7899bcde92803'
        ),
        'architecture_sha256': ARCHITECTURE_SHA256,
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'remote_status_at_executor': 'REMOTE_UNVERIFIED_AT_EXECUTOR',
    }
    if repository != expected_repository:
        raise GuardError('repository pins mismatch')
    identity = _mapping(packet['identity'], 'identity', {
        'session_id', 'coordinator_ingress_instance_id', 'ros_domain_id',
        'gz_partition', 'world', 'robot', 'backend', 'scenario_id',
    })
    if identity['session_id'] != (
        'canonical UUID generated once before participant creation'
    ):
        raise GuardError('session_id generation contract mismatch')
    if identity['coordinator_ingress_instance_id'] != (
        'single nonzero uint64 generated once before participant creation'
    ):
        raise GuardError('coordinator ingress generation contract mismatch')
    for key, expected in {
        'ros_domain_id': 83, 'world': 'b2_training_arena',
        'robot': 'mecanum_b2', 'backend': 'NATIVE_B2_BACKEND_V1',
        'scenario_id': 'B2_SOAK_V1',
    }.items():
        _exact(identity[key], expected, f'identity.{key}')
    if identity['gz_partition'] != (
        'mecanum_b2_<session_uuid_without_hyphens>'
    ):
        raise GuardError('identity.gz_partition template mismatch')
    for section in ('scenario', 'composition', 'installation', 'inputs',
                    'host_capabilities', 'capture', 'mailbox', 'timing',
                    'operations', 'approval_boundary', 'acceptance',
                    'evidence', 'guard', 'commands_argv'):
        _mapping(packet[section], f'packet.{section}')
    installation = packet['installation']
    _mapping(installation, 'installation', {
        'overlay', 'install_prefix', 'method', 'packages', 'file_count',
        'file_sha256',
        'resolved_paths', 'dependency_fingerprints',
    })
    _integer(installation['file_count'], 'installation.file_count',
             minimum=1)
    files = _mapping(installation['file_sha256'],
                     'installation.file_sha256')
    if len(files) != installation['file_count']:
        raise GuardError('installed fingerprint count mismatch')
    for path, digest in files.items():
        if not Path(_text(path, 'installed fingerprint path')).is_absolute():
            raise GuardError('installed fingerprint path must be absolute')
        _hash(digest, f'installation.file_sha256[{path}]')
    if installation['overlay'] != (
        '/tmp/b22_gui_observation_run001_install'
    ) or installation['install_prefix'] != installation['overlay']:
        raise GuardError('overlay path differs from the pinned installation')
    paths = _mapping(installation['resolved_paths'],
                     'installation.resolved_paths')
    if not paths or any(
        not isinstance(value, str) or not Path(value).is_absolute()
        for value in paths.values()
    ):
        raise GuardError('resolved install paths must be absolute')
    dependency = _mapping(
        installation['dependency_fingerprints'],
        'installation.dependency_fingerprints',
    )
    for name in ('python', 'qt', 'desktop_tools', 'codex_tools', 'filesystem'):
        _mapping(dependency.get(name), f'dependency_fingerprints.{name}')
    inputs = _mapping(packet['inputs'], 'inputs', {
        'manifest_sha256', 'resolved_config_sha256', 'config_hash',
        'scenario_sha256',
    })
    if inputs != {
        'manifest_sha256': MANIFEST_SHA256,
        'resolved_config_sha256': RESOLVED_SHA256,
        'config_hash': CONFIG_HASH,
        'scenario_sha256': SCENARIO_SHA256,
    }:
        raise GuardError('production input pins mismatch')
    for key, value in inputs.items():
        _hash(value, f'inputs.{key}')
    tool_section = _mapping(packet['tool_sha256'], 'tool_sha256',
                            set(TOOL_NAMES))
    actual_tools = {name: _hash(value, f'tool_sha256.{name}')
                    for name, value in tool_section.items()}
    if actual_tools != tool_hashes:
        raise GuardError('packet tool hashes do not match current files')
    _exact(packet['runtime_authorization'], 'NOT_GRANTED',
           'runtime_authorization')
    if packet['timing'].get('review_checkpoint_s') != 60:
        raise GuardError('review checkpoint must be 60 seconds')
    if packet['timing'].get('active_cap_s') != 240:
        raise GuardError('active cap mismatch')
    if packet['timing'].get('cleanup_cap_s') != 60:
        raise GuardError('cleanup cap mismatch')
    if packet['timing'].get('total_cap_s') != 300:
        raise GuardError('total cap mismatch')
    if packet['timing'].get('observation_s') != 60:
        raise GuardError('observation duration mismatch')
    if packet['timing'].get('clock_stability_s') != 1:
        raise GuardError('clock stability duration mismatch')
    if packet['timing'].get('server_readiness_s') != 30:
        raise GuardError('server readiness deadline mismatch')
    if packet['timing'].get('gui_startup_s') != 30:
        raise GuardError('GUI startup deadline mismatch')
    if packet['timing'].get('graph_convergence_s') != 30:
        raise GuardError('graph convergence deadline mismatch')
    if packet['scenario'] != {
        'scenario_id': 'B2_SOAK_V1', 'world': 'b2_training_arena',
        'robot': 'mecanum_b2', 'backend': 'NATIVE_B2_BACKEND_V1',
    }:
        raise GuardError('scenario identity mismatch')
    composition = packet['composition']
    if composition.get('namespace') != '/' or composition.get(
        'persistent_ros_nodes'
    ) != [
        'b22_gui_observation_observer', 'robot_state_publisher',
        'ros_gz_bridge', 'mecanum_sim_backend',
    ] or composition.get('startup_temporary_ros_nodes') != [
        'b2_server_scene_readiness',
    ]:
        raise GuardError('ROS participant inventory contract mismatch')
    if composition.get('process_roles') != [
        'robot_state_publisher', 'parameter_bridge', 'server', 'gui',
    ]:
        raise GuardError('owned process role inventory mismatch')
    if packet['mailbox'] != {
        'root': str(EVIDENCE_ROOT / 'review_mailbox'),
        'request_schema': 'b22_gui_codex_review_request/v1',
        'result_schema': 'b22_gui_codex_review_result/v1',
        'max_json_bytes': 16384, 'directory_mode': '0700',
        'file_mode': '0600', 'publication': 'fsync+hard-link-no-replace',
    }:
        raise GuardError('review mailbox contract mismatch')
    if packet['guard'].get('acquisition_path') != str(GUARD_PATH):
        raise GuardError('production acquisition path is not canonical')
    if packet['evidence'].get('root') != str(EVIDENCE_ROOT):
        raise GuardError('production evidence root is not canonical')
    if packet['approval_boundary'].get('approval_path') != str(APPROVAL_PATH):
        raise GuardError('production approval path is not canonical')
    if (
        packet['approval_boundary'].get('runtime_authorization')
        != 'NOT_GRANTED'
    ):
        raise GuardError('packet cannot grant runtime authorization')
    if packet['capture'].get('profile') != 'X11_XCB_ONLY':
        raise GuardError('capture profile must be X11/XCB-only')
    if packet['capture'].get('whole_screen') is not False:
        raise GuardError('whole-screen capture is prohibited')
    if packet['capture'].get('max_png_bytes') != 32 * 1024 * 1024:
        raise GuardError('capture size bound mismatch')
    if packet['acceptance'].get('owner_visual_review') != 'NOT_PERFORMED':
        raise GuardError('Owner visual review must remain NOT_PERFORMED')
    if packet['acceptance'].get('automated_review_reviewer') != 'CODEX':
        raise GuardError('automated review reviewer must be CODEX')
    if packet['acceptance'].get('motion') != 'PROHIBITED':
        raise GuardError('motion must remain prohibited')
    if packet['guard'].get('capacity') != 1 or packet['guard'].get(
        'retry_after_consume'
    ) is not False:
        raise GuardError('capacity-one/no-retry guard contract mismatch')
    if (
        not isinstance(packet['operations'].get('prohibited'), list)
        or not packet['operations']['prohibited']
    ):
        raise GuardError('prohibited operation inventory is missing')
    if not isinstance(packet['operations'].get('allowed'), list) or not packet[
        'operations'
    ]['allowed']:
        raise GuardError('allowed operation inventory is missing')
    return {
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'input_sha256': inputs,
        'file_sha256': files,
        'dependency_fingerprints': dependency,
        'repository': repository,
        'identity': identity,
    }


def load_packet(path: Path, tool_paths: dict[str, Path]):
    """Load and validate the canonical packet against current tool bytes."""
    data = Path(path).read_bytes()
    packet = strict_json_loads(data, max_bytes=2 * 1024 * 1024)
    hashes = {name: sha256_file(tool_paths[name]) for name in TOOL_NAMES}
    return packet, sha256_bytes(data), packet_bindings(packet, hashes), hashes


def tool_hashes(tool_paths: dict[str, Path]) -> dict[str, str]:
    """Return hashes for the exact four RUN002 tool files."""
    if set(tool_paths) != set(TOOL_NAMES):
        raise GuardError('tool path set mismatch')
    return {name: sha256_file(tool_paths[name]) for name in TOOL_NAMES}


def validate_approval(
    *, packet_path: Path, approval_path: Path, expected_commit: str,
    tool_paths: dict[str, Path],
):
    """Validate Owner pins against the exact packet commit and tool bytes."""
    packet, packet_hash, bindings, hashes = load_packet(
        packet_path, tool_paths,
    )
    approval = strict_json_loads(Path(approval_path).read_bytes())
    approval = _mapping(approval, 'approval', {
        'schema_id', 'run_id', 'packet_sha256', 'packet_commit',
        'production_source_pin', 'tool_sha256',
    })
    expected = {
        'schema_id': APPROVAL_SCHEMA_ID, 'run_id': RUN_ID,
        'packet_sha256': packet_hash, 'packet_commit': expected_commit,
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'tool_sha256': hashes,
    }
    if approval != expected:
        raise GuardError('Owner approval pins do not match exact RUN002 bytes')
    return packet, packet_hash, hashes


def _reject_symlink_components(path: Path):
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise GuardError(
                f'canonical path component is a symlink: {current}'
            )


def validate_run_roots(
    guard_path=GUARD_PATH, evidence_root=EVIDENCE_ROOT,
    *, expected_guard=GUARD_PATH, expected_evidence=EVIDENCE_ROOT,
):
    """Reject redirected, aliased, or colliding fixed production roots."""
    guard = Path(os.path.abspath(guard_path))
    root = Path(os.path.abspath(evidence_root))
    if guard != Path(expected_guard) or root != Path(expected_evidence):
        raise GuardError('production root override is forbidden')
    if guard != root / 'acquisition.json':
        raise GuardError('guard/evidence root relationship mismatch')
    _reject_symlink_components(root)
    if guard.exists() or guard.is_symlink():
        raise GuardError('acquisition already exists; capacity is consumed')
    if root.exists() and any(root.iterdir()):
        raise GuardError('evidence root is not empty')
    return guard, root


def acquire_once(path: Path, payload: dict, *, open_fn=os.open):
    """Create a permanent record; partial creation still consumes capacity."""
    path = Path(path)
    if not path.parent.is_dir():
        raise GuardError('canonical acquisition directory must be provisioned')
    _reject_symlink_components(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    try:
        descriptor = open_fn(path, flags, 0o600)
    except FileExistsError as error:
        raise GuardError(
            'acquisition already exists; capacity is consumed and cannot retry'
        ) from error
    try:
        data = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        encoded = (data + '\n').encode('utf-8')
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError('short acquisition write')
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return path
