"""Capacity-one, approval-bound guard for B22_GUI_OBSERVATION_RUN001."""
from __future__ import annotations

import hashlib
import json
import os
import re
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
EVIDENCE_ROOT = GUARD_PATH.parent
PACKET_SCHEMA_ID = 'b22_gui_observation_packet/v1'
TOOL_NAMES = {
    'observation_guard.py', 'observation_runner.py',
    'observation_sink.py', 'test_observation_packet.py',
}
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_PACKET_FIELDS = {
    'acceptance', 'allowed_operations', 'approval_boundary', 'backend',
    'capacity', 'commands_argv', 'evidence', 'guard', 'gui',
    'identity_binding', 'input_sha256', 'installation', 'non_retry_rule',
    'prohibited_operations', 'repository', 'robot', 'run_id', 'scenario_id',
    'schema_id', 'status', 'timing_steady_seconds', 'tool_sha256', 'world',
}


def packet_bindings(
    packet: dict[str, object], tool_hashes: dict[str, str],
) -> dict[str, object]:
    """Validate the complete canonical packet and return pinned sections."""
    if not isinstance(packet, dict) or set(packet) != _PACKET_FIELDS:
        raise GuardError('packet fields do not match the canonical schema')

    def mapping(value, name, fields=None):
        if not isinstance(value, dict):
            raise GuardError(f'packet {name} must be an object')
        if fields is not None and set(value) != set(fields):
            raise GuardError(f'packet {name} fields do not match schema')
        return value

    def text(value, name):
        if not isinstance(value, str) or not value:
            raise GuardError(f'packet {name} must be a non-empty string')
        return value

    def hash_map(value, name, keys=None):
        result = mapping(value, name, keys)
        for key, digest in result.items():
            text(key, f'{name} key')
            if not isinstance(digest, str) or not _HASH.fullmatch(digest):
                raise GuardError(f'packet {name}.{key} is not a SHA-256')
        return result

    def string_list(value, name):
        if not isinstance(value, list) or not value or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise GuardError(f'packet {name} must be a non-empty string list')
        return value

    fixed = {
        'schema_id': PACKET_SCHEMA_ID,
        'run_id': RUN_ID,
        'capacity': 1,
        'gui': True,
        'scenario_id': 'B2_SOAK_V1',
        'world': 'b2_training_arena',
        'robot': 'mecanum_b2',
        'backend': 'NATIVE_B2_BACKEND_V1',
        'status': (
            'RUNTIME_PACKET_DELIVERED_PENDING_INDEPENDENT_EXACT_COMMIT_AUDIT'
        ),
    }
    for key, expected in fixed.items():
        value = packet[key]
        if type(value) is not type(expected) or value != expected:
            raise GuardError(f'packet pin mismatch: {key}')

    repository = mapping(packet['repository'], 'repository', {
        'architecture_sha256', 'branch', 'expected_remote_integration',
        'origin', 'production_source_pin', 'starting_head',
        'starting_sole_parent',
    })
    if repository != {
        'architecture_sha256': (
            '432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204'
        ),
        'branch': 'roadmap-b-b22-simulation-substrate',
        'expected_remote_integration': (
            'ef9e0281cfb9de04d89a2698d6d7899bcde92803'
        ),
        'origin': 'https://github.com/hazandz/mecanum_autonomy_ws.git',
        'production_source_pin': PRODUCTION_SOURCE_PIN,
        'starting_head': PRODUCTION_SOURCE_PIN,
        'starting_sole_parent': '0aa37a8ab48d42e144df89d47b3f10dcc271c6d2',
    }:
        raise GuardError('packet repository/source pins do not match RUN001')

    inputs = hash_map(packet['input_sha256'], 'input_sha256', {
        'asset_manifest', 'config_hash', 'resolved_soak', 'scenario',
    })
    expected_inputs = {
        'asset_manifest': MANIFEST_SHA256,
        'config_hash': CONFIG_HASH,
        'resolved_soak': RESOLVED_SHA256,
        'scenario': SCENARIO_SHA256,
    }
    if inputs != expected_inputs:
        raise GuardError('packet production input pins do not match RUN001')

    installation = mapping(packet['installation'], 'installation', {
        'dependency_fingerprints', 'file_count', 'file_sha256',
        'install_prefix', 'method', 'packages', 'resolved_paths',
    })
    if (type(installation['file_count']) is not int
            or installation['file_count'] != 47):
        raise GuardError('packet installation file_count mismatch')
    prefix = Path(text(
        installation['install_prefix'], 'installation.install_prefix',
    ))
    if not prefix.is_absolute():
        raise GuardError('packet install_prefix must be absolute')
    if installation['method'] != (
        'fresh_external_non_symlink_five_package_colcon_build'
    ):
        raise GuardError('packet installation method mismatch')
    if installation['packages'] != [
        'mecanum_nav_rl_interfaces', 'ROBOT_URDF_final_description',
        'mecanum_nav_rl', 'mecanum_sim_backend', 'mecanum_nav_bringup',
    ]:
        raise GuardError('packet installation packages mismatch')
    installed = hash_map(
        installation['file_sha256'], 'installation.file_sha256',
    )
    if len(installed) != installation['file_count'] or any(
        not Path(path).is_absolute() for path in installed
    ):
        raise GuardError('packet installed file fingerprint map is invalid')
    if prefix != Path('/tmp/b22_gui_observation_run001_install'):
        raise GuardError('packet install prefix is not the verified overlay')
    resolved_paths = mapping(
        installation['resolved_paths'], 'installation.resolved_paths',
    )
    for key, value in resolved_paths.items():
        text(key, 'installation.resolved_paths key')
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise GuardError(f'packet resolved path is invalid: {key}')
    dependencies = mapping(
        installation['dependency_fingerprints'],
        'installation.dependency_fingerprints',
        {
            'gazebo', 'python', 'ros_clock_subscription_qos',
            'ros_distro', 'ros_underlay', 'system_packages',
        },
    )
    python_facts = mapping(
        dependencies['python'], 'dependency_fingerprints.python', {
            'executable', 'modules', 'version',
        },
    )
    if python_facts['version'] != '3.12.3' or not Path(
        text(python_facts['executable'], 'python.executable')
    ).is_absolute():
        raise GuardError('packet Python fingerprint is invalid')
    modules = mapping(python_facts['modules'], 'python.modules', {
        'numpy', 'pydantic', 'pytest',
    })
    expected_versions = {
        'numpy': '1.26.4', 'pydantic': '2.10.6', 'pytest': '7.4.4',
    }
    for module, version in expected_versions.items():
        facts = mapping(
            modules[module], f'python.modules.{module}', {'origin', 'version'},
        )
        if facts['version'] != version or not Path(
            text(facts['origin'], f'python.modules.{module}.origin')
        ).is_absolute():
            raise GuardError(
                f'packet Python module fingerprint mismatch: {module}'
            )
    text(dependencies['ros_distro'], 'dependency_fingerprints.ros_distro')
    underlay = Path(text(
        dependencies['ros_underlay'], 'dependency_fingerprints.ros_underlay',
    ))
    if not underlay.is_absolute():
        raise GuardError('packet ROS underlay must be absolute')
    mapping(
        dependencies['system_packages'],
        'dependency_fingerprints.system_packages',
    )
    gazebo = mapping(dependencies['gazebo'], 'dependency_fingerprints.gazebo')
    if (gazebo.get('major_version') != 8
            or gazebo.get('server_mode')
            != 'server-only with --headless-rendering'):
        raise GuardError('packet Gazebo mode/version mismatch')
    clock_qos = mapping(
        dependencies['ros_clock_subscription_qos'],
        'dependency_fingerprints.ros_clock_subscription_qos',
        {'bridge_profile', 'depth', 'durability', 'history', 'reliability'},
    )
    if clock_qos != {
        'bridge_profile': 'CLOCK', 'depth': 10,
        'durability': 'VOLATILE', 'history': 'KEEP_LAST',
        'reliability': 'BEST_EFFORT',
    }:
        raise GuardError('packet /clock QoS does not match RUN001')

    actual_tools = hash_map(tool_hashes, 'current tool hashes', TOOL_NAMES)
    packet_tools = hash_map(packet['tool_sha256'], 'tool_sha256', TOOL_NAMES)
    if packet_tools != actual_tools:
        raise GuardError('packet tool hashes differ from current tool bytes')

    timing = mapping(
        packet['timing_steady_seconds'], 'timing_steady_seconds', {
            'backend_heartbeat_max_gap', 'cleanup_cap_separate',
            'clock_stability_gate', 'consume_to_end_hard_cap',
            'gui_process_startup', 'observation_after_ack_and_clock_stable',
            'owner_acknowledgment', 'runtime_cap_after_consume',
            'server_readiness',
        },
    )
    expected_timing = {
        'backend_heartbeat_max_gap': 1, 'cleanup_cap_separate': 60,
        'clock_stability_gate': 1, 'consume_to_end_hard_cap': 300,
        'gui_process_startup': 30,
        'observation_after_ack_and_clock_stable': 60,
        'owner_acknowledgment': 60, 'runtime_cap_after_consume': 240,
        'server_readiness': 30,
    }
    if timing != expected_timing:
        raise GuardError('packet RUN001 timing pins mismatch')

    guard = mapping(packet['guard'], 'guard', {
        'acquisition', 'owner_approval_fields',
        'owner_approval_schema', 'path',
    })
    if (guard['path'] != str(GUARD_PATH)
            or guard['owner_approval_schema']
            != 'b22_gui_observation_owner_approval/v1'):
        raise GuardError('packet capacity-one guard identity mismatch')
    if guard['acquisition'] != (
        'exclusive atomic create, mode 0600; existing or partial file '
        'consumes capacity; no reset or retry'
    ):
        raise GuardError('packet acquisition semantics mismatch')
    if guard['owner_approval_fields'] != [
        'run_id', 'packet_sha256', 'packet_commit',
        'production_source_pin', 'tool_sha256',
    ]:
        raise GuardError('packet Owner approval fields mismatch')
    evidence = mapping(packet['evidence'], 'evidence', {
        'format', 'retained_assets', 'root', 'stream',
    })
    if evidence != {
        'format': (
            'append-only JSONL, exclusive create, mode 0600, per-record fsync'
        ),
        'retained_assets': [
            'runtime_assets/run_descriptor.json',
            'runtime_assets/<session-bound-world>.runtime.sdf',
            'runtime_assets/robot_state_publisher.params.yaml',
            'Owner screenshot reference and SHA-256',
        ],
        'root': str(EVIDENCE_ROOT), 'stream': 'observation.jsonl',
    }:
        raise GuardError('packet evidence root mismatch')

    identity_binding = mapping(
        packet['identity_binding'], 'identity_binding', {
            'coordinator_ingress_instance_id', 'expected_ros_node_names',
            'gz_partition', 'host_binding', 'resource_plugin_environment',
            'ros_domain_id', 'session_id',
        },
    )
    if (type(identity_binding['ros_domain_id']) is not int
            or identity_binding['ros_domain_id'] != 83):
        raise GuardError('packet ROS domain identity mismatch')
    if identity_binding['expected_ros_node_names'] != [
        'b22_gui_observation_observer', 'robot_state_publisher',
        'ros_gz_bridge', 'b2_server_scene_readiness',
    ]:
        raise GuardError('packet ROS graph participant allowlist mismatch')
    if identity_binding['host_binding'] != [
        'hostname', 'Linux boot_id', 'runner pid', 'process group',
        'session', 'proc start ticks',
    ]:
        raise GuardError('packet host/process identity fields mismatch')
    for field in ('coordinator_ingress_instance_id', 'gz_partition',
                  'resource_plugin_environment', 'session_id'):
        text(identity_binding[field], f'identity_binding.{field}')

    commands = mapping(packet['commands_argv'], 'commands_argv', {
        'composition', 'exact_templates', 'substitutions',
    })
    text(commands['composition'], 'commands_argv.composition')
    command_templates = mapping(
        commands['exact_templates'], 'commands_argv.exact_templates',
        {'gui', 'parameter_bridge', 'robot_state_publisher', 'server'},
    )
    for name, argv in command_templates.items():
        string_list(argv, f'commands_argv.exact_templates.{name}')
    if command_templates['gui'][-2] != '--gui-config':
        raise GuardError('packet GUI command template is malformed')
    if command_templates['parameter_bridge'][:4] != [
        'ros2', 'run', 'ros_gz_bridge', 'parameter_bridge',
    ]:
        raise GuardError('packet bridge command template is malformed')
    substitutions = mapping(
        commands['substitutions'], 'commands_argv.substitutions',
    )
    for key, value in substitutions.items():
        text(key, 'commands_argv.substitutions key')
        text(value, f'commands_argv.substitutions.{key}')

    if packet['acceptance'] != {
        'cleanup_escalation': ['SIGINT', 'SIGTERM', 'SIGKILL'],
        'contact_capability': 'UNKNOWN_ALLOWED',
        'failure': (
            'GUI/backend/evidence failure, timeout, identity mismatch, lost '
            'inhibit, clock progress or owned cleanup residue => FAIL; Owner '
            'direct OWNER_ABORT_GUI token => ABORTED_BY_OWNER; '
            'no restart/retry'
        ),
        'owner': (
            'Owner directly confirms rendered world/robot and provides '
            'existing nonempty screenshot file; record its SHA-256; '
            'OWNER_ABORT_GUI is required to classify Owner abort'
        ),
        'pass_requires': (
            'all listed identity, Owner screenshot, stable paused/inhibited '
            'status, heartbeat, clock and cleanup conditions; '
            'no runner-created '
            'command/control operation'
        ),
        'scan_health': 'NOT_EVALUATED_WHILE_PAUSED',
        'scene': (
            'world b2_training_arena; exactly one mecanum_b2 model in '
            'readiness query; bound backend session/config identity; '
            'one owned server and one owned GUI'
        ),
        'status_all_observation_samples': {
            'actuator_inhibited': True, 'applied_receipt_valid': False,
            'backend_heartbeat_gap_max_s': 1,
            'backend_identity_unchanged': True, 'fault_flags': 0,
            'paused': True, 'simulation_clock_advances': False,
        },
    }:
        raise GuardError(
            'packet acceptance contract does not match RUN001'
        )

    ack = mapping(packet['acceptance'], 'acceptance')
    status_facts = mapping(
        ack.get('status_all_observation_samples'),
        'acceptance.status_all_observation_samples', {
            'actuator_inhibited', 'applied_receipt_valid',
            'backend_heartbeat_gap_max_s', 'backend_identity_unchanged',
            'fault_flags', 'paused', 'simulation_clock_advances',
        },
    )
    if status_facts != {
        'actuator_inhibited': True, 'applied_receipt_valid': False,
        'backend_heartbeat_gap_max_s': 1, 'backend_identity_unchanged': True,
        'fault_flags': 0, 'paused': True, 'simulation_clock_advances': False,
    }:
        raise GuardError(
            'packet paused/inhibited acceptance contract mismatch'
        )
    for field in (
        'cleanup_escalation', 'contact_capability', 'failure', 'owner',
        'pass_requires', 'scan_health', 'scene',
    ):
        if field not in ack:
            raise GuardError(f'packet acceptance.{field} is missing')
    for field in ('approval_boundary', 'non_retry_rule'):
        text(packet[field], field)
    string_list(packet['allowed_operations'], 'allowed_operations')
    string_list(packet['prohibited_operations'], 'prohibited_operations')
    return {
        'production_source_pin': repository['production_source_pin'],
        'input_sha256': inputs,
        'file_sha256': installed,
        'dependency_fingerprints': dependencies,
    }


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
    try:
        packet = json.loads(packet_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GuardError('packet.json is not valid UTF-8 JSON') from error
    approval = json.loads(approval_path.read_text(encoding='utf-8'))
    actual_tools = tool_hashes(tool_paths)
    if not isinstance(approval, dict) or set(approval) != {
        'schema_id', 'run_id', 'packet_sha256', 'packet_commit',
        'production_source_pin', 'tool_sha256',
    }:
        raise GuardError('Owner approval fields do not match schema')
    bindings = packet_bindings(packet, actual_tools)
    required = {
        'schema_id': 'b22_gui_observation_owner_approval/v1',
        'run_id': RUN_ID,
        'packet_sha256': packet_hash,
        'packet_commit': expected_commit,
        'production_source_pin': bindings['production_source_pin'],
        'tool_sha256': actual_tools,
    }
    for field, expected in required.items():
        if approval.get(field) != expected:
            raise GuardError(f'Owner approval mismatch: {field}')
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
