"""Build immutable Roadmap B training asset and resolved-config bytes.

This module reads only the exact asset sources named in the manifest. It does
not launch a simulator, resolve Fuel resources, or write on import. The CLI is
an explicit offline build tool that writes only the three allowlisted resolved
outputs and the allowlisted manifest.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mecanum_nav_rl.config.v3_compiler import compile_resolved_document_v3
from mecanum_nav_rl.config.v3_composition import (
    CanonicalFragmentKindV3,
    CanonicalFragmentV3,
    compose_canonical_v3_fragments,
)
from mecanum_nav_rl.tasks.scenario_artifact import (
    GT_ODOM_2D_REFERENCE_ID,
    SCENARIO_ARTIFACT_HASH_VERSION,
    SCENARIO_ARTIFACT_SCHEMA_VERSION,
    ScenarioArtifactLoadStatus,
    ScenarioArtifactLoader,
    scenario_artifact_sha256,
)

import yaml


SCENARIO_IDS = ('B2_SOAK_V1', 'B2_GOAL_SETTLE_V1', 'B2_CONTACT_V1')
_RESOLVED_NAMES = {
    'B2_SOAK_V1': 'sim_train_local_training_soak.resolved.json',
    'B2_GOAL_SETTLE_V1': 'sim_train_local_training_goal_settle.resolved.json',
    'B2_CONTACT_V1': 'sim_train_local_training_contact.resolved.json',
}
_SCENARIO_NAMES = {name: f'{name}.json' for name in SCENARIO_IDS}
_COLLISIONS = (
    'b2_training_arena::mecanum_b2::base_link::s3_d3_base_contact_collision',
    'b2_training_arena::mecanum_b2::Wheel_LF_1::Wheel_LF_1_collision',
    'b2_training_arena::mecanum_b2::Wheel_RF_1::Wheel_RF_1_collision',
    'b2_training_arena::mecanum_b2::Wheel_RB_1::Wheel_RB_1_collision',
    'b2_training_arena::mecanum_b2::Wheel_LB_1::Wheel_LB_1_collision',
)
_RESOURCES = (
    'worlds/b2_training_arena.sdf',
    'models/mecanum_b2/model.config',
    'models/mecanum_b2/model.sdf',
    'models/b2_contact_probe/model.config',
    'models/b2_contact_probe/model.sdf',
    'urdf/mecanum_b2_static.urdf',
    'meshes/base_link.stl',
    'meshes/Wheel_LF_1.stl',
    'meshes/Wheel_RF_1.stl',
    'meshes/Wheel_RB_1.stl',
    'meshes/Wheel_LB_1.stl',
)


@dataclass(frozen=True)
class TrainingAssetBundle:
    """Hold canonical manifest, scenario and resolved-config bytes."""

    manifest_bytes: bytes
    manifest_sha256: str
    scenario_bytes: Mapping[str, bytes]
    scenario_sha256: Mapping[str, str]
    resolved_bytes: Mapping[str, bytes]
    resolved_sha256: Mapping[str, str]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_mapping(path: Path) -> dict[str, object]:
    raw = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError(f'expected mapping in {path}')
    return raw


def _scenario_document(scenario_id: str, world_sha: str) -> dict[str, object]:
    settle = scenario_id == 'B2_GOAL_SETTLE_V1'
    goal_x = goal_y = 0.0 if settle else 2.0
    actual_start_x = actual_start_y = 0.0
    unsigned: dict[str, object] = {
        'artifact_hash_version': SCENARIO_ARTIFACT_HASH_VERSION,
        'identity': {
            'artifact_schema_version': SCENARIO_ARTIFACT_SCHEMA_VERSION,
            'scenario_id': scenario_id,
            'scenario_version': '1.0.0',
            'gazebo_world_name': 'b2_training_arena',
            'world_file_sha256': world_sha,
            'coordinate_reference_id': GT_ODOM_2D_REFERENCE_ID,
        },
        'task_definition': {
            'goal': {
                'x_m': goal_x, 'y_m': goal_y, 'goal_radius_m': 0.15,
                'goal_rule_id': 'distance_to_goal_lte_radius_2d',
            },
            'start_pose_catalog': [{
                'start_id': 'start_0', 'x_m': actual_start_x,
                'y_m': actual_start_y, 'yaw_rad': 0.0,
            }],
            'candidate_task_bounds': {
                'shape_type': 'axis_aligned_rectangle', 'min_x_m': -4.0,
                'max_x_m': 4.0, 'min_y_m': -4.0, 'max_y_m': 4.0,
                'boundary_semantics': 'boundary_invalid',
            },
            'forbidden_zone_policy': 'none_provisional',
            'forbidden_zones': [], 'randomization': 'disabled',
        },
    }
    signed = deepcopy(unsigned)
    identity = signed['identity']
    assert isinstance(identity, dict)
    identity['scenario_content_sha256'] = scenario_artifact_sha256(unsigned)
    return signed


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n'
    ).encode('utf-8')


def build_training_asset_bundle(repository_root: Path) -> TrainingAssetBundle:
    """Bind real assets and B1 scenarios through the production compiler."""
    root = repository_root.resolve()
    description = root / 'ros2_ws/src/ROBOT_URDF_final_description'
    rl_package = root / 'ros2_ws/src/mecanum_nav_rl'
    world_path = description / 'worlds/b2_training_arena.sdf'
    world_sha = _sha256(world_path.read_bytes())
    scenarios = {
        name: _scenario_document(name, world_sha) for name in SCENARIO_IDS
    }
    scenario_bytes = {
        name: _canonical_bytes(doc) for name, doc in scenarios.items()
    }
    scenario_hashes = {
        name: str(doc['identity']['scenario_content_sha256'])
        for name, doc in scenarios.items()
    }
    loader = ScenarioArtifactLoader(
        expected_gazebo_world_name='b2_training_arena',
        expected_world_file_sha256=world_sha,
        expected_coordinate_reference_id=GT_ODOM_2D_REFERENCE_ID,
    )
    for name, document in scenarios.items():
        result = loader.load(document)
        if result.status is not ScenarioArtifactLoadStatus.READY:
            raise ValueError(
                f'scenario {name} failed B1 validation: '
                f'{result.diagnostic_code}'
            )

    asset_sources = [
        (f'ROBOT_URDF_final_description/{rel}', description / rel)
        for rel in _RESOURCES
    ]
    asset_sources.extend([
        (
            'ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro',
            description / 'urdf/ROBOT_URDF_final.xacro',
        ),
    ])
    asset_hashes = {
        key: _sha256(path.read_bytes()) for key, path in asset_sources
    }
    manifest = {
        'schema_id': 'roadmap_b_b2_asset_manifest/v1',
        'world_id': 'b2_training_arena',
        'world_file': (
            'ROBOT_URDF_final_description/worlds/'
            'b2_training_arena.sdf'
        ),
        'world_file_sha256': world_sha,
        'robot_entity': 'mecanum_b2',
        'backend_id': 'NATIVE_B2_BACKEND_V1',
        'backend_contract': {
            'receipt_core_sha256': _sha256(
                (root / 'ros2_ws/src/mecanum_sim_backend/src/receipt_gate.cpp')
                .read_bytes()
            ),
            'contact_core_sha256': _sha256(
                (
                    root / (
                        'ros2_ws/src/mecanum_sim_backend/src/'
                        'contact_coverage.cpp'
                    )
                ).read_bytes()
            ),
            'plugin_source_sha256': _sha256(
                (
                    root / (
                        'ros2_ws/src/mecanum_sim_backend/src/'
                        'backend_system.cpp'
                    )
                ).read_bytes()
            ),
        },
        'physics': {
            'step_ros_s': 0.01,
            'target_real_time_factor': 1.0,
        },
        'arena': {
            'interior_m': [8.0, 8.0],
            'wall_height_m': 1.0,
            'wall_thickness_m': 0.20,
            'obstacle_center_xy_m': [2.5, 0.0],
            'obstacle_size_xyz_m': [0.20, 1.0, 1.0],
        },
        'sensor': {
            'profile_id': 'B2_GENERIC_2D_V1',
            'topic': '/b2/scan',
            'frame_id': 'lidar_frame',
            'rate_hz': 10.0,
            'beams': 500,
            'angle_rad': [-3.141592653589793, 3.141592653589793],
            'range_m': [0.10, 8.0],
            'extrinsic_xyz_m': [-0.031765, 0.0, 0.140],
            'extrinsic_rpy_rad': [0.0, 0.0, 0.0],
        },
        'ground_truth': {
            'topic': '/b2/ground_truth/odom',
            'rate_hz': 100.0,
            'pose_frame': 'world',
            'twist_child_frame': 'base_link',
            'tf_broadcast': False,
        },
        'collision_registry': {
            'maximum': 64,
            'tracked_collision_names': list(_COLLISIONS),
            'wheel_floor_ignore': {
                'normal_vertical_angle_max_deg': 15.0,
                'depth_m': [0.0, 0.005],
            },
            'probe_model': 'b2_contact_probe',
            'probe_collision': (
                'b2_training_arena::b2_contact_probe::link::collision'
            ),
        },
        'resource_closure': asset_hashes,
        'scenario_artifacts': {
            name: {
                'file': _SCENARIO_NAMES[name],
                'scenario_content_sha256': scenario_hashes[name],
                'active_contact_probe': name == 'B2_CONTACT_V1',
                'world_to_task_mapping': 'IDENTITY_XY_YAW',
                'coordinate_reference_id': GT_ODOM_2D_REFERENCE_ID,
            }
            for name in SCENARIO_IDS
        },
    }
    manifest_bytes = _canonical_bytes(manifest)
    manifest_hash = _sha256(manifest_bytes)

    v3 = rl_package / 'config/v3'
    kinds = (
        ('local_training/base.yaml', CanonicalFragmentKindV3.BASE),
        ('local_training/frames.yaml', CanonicalFragmentKindV3.FRAMES),
        ('local_training/topics_qos.yaml', CanonicalFragmentKindV3.TOPICS_QOS),
        (
            'local_training/state_localization.yaml',
            CanonicalFragmentKindV3.STATE_LOCALIZATION,
        ),
        (
            'local_training/system_contracts.yaml',
            CanonicalFragmentKindV3.SYSTEM_CONTRACTS,
        ),
        ('profiles/sim_train.yaml', CanonicalFragmentKindV3.RUNTIME_PROFILE),
        ('modes/local_training.yaml', CanonicalFragmentKindV3.NAVIGATION_MODE),
    )
    fragments = [
        CanonicalFragmentV3(kind, _read_mapping(v3 / rel))
        for rel, kind in kinds
    ]
    profile_values = next(
        fragment.values for fragment in fragments
        if fragment.kind is CanonicalFragmentKindV3.RUNTIME_PROFILE
    )
    profile_runtime = profile_values.get('runtime')
    if isinstance(profile_runtime, dict):
        profile_runtime.pop('allowed_navigation_modes', None)
    composed = compose_canonical_v3_fragments(*fragments)
    composed_runtime = composed.get('runtime')
    if isinstance(composed_runtime, dict):
        composed_runtime.pop('allowed_navigation_modes', None)
    outputs: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    for scenario_id in SCENARIO_IDS:
        document = deepcopy(composed)
        provenance = document['provenance']
        assert isinstance(provenance, dict)
        provenance['source_manifest_sha256'] = manifest_hash
        training = document['training']
        assert isinstance(training, dict)
        local = training['local_training']
        assert isinstance(local, dict)
        local['backend_id'] = 'NATIVE_B2_BACKEND_V1'
        map_identity = document['map_identity']
        assert isinstance(map_identity, dict)
        map_identity['training_binding'] = {
            'scenario_id': scenario_id, 'world_id': 'b2_training_arena',
            'asset_manifest_sha256': manifest_hash, 'binding_status': 'BOUND',
        }
        compiled = compile_resolved_document_v3(document)
        payload = compiled.model_dump(mode='json')
        file_name = _RESOLVED_NAMES[scenario_id]
        outputs[file_name] = _canonical_bytes(payload)
        hashes[file_name] = str(payload['provenance']['config_hash'])
    return TrainingAssetBundle(
        manifest_bytes=manifest_bytes, manifest_sha256=manifest_hash,
        scenario_bytes={
            _SCENARIO_NAMES[name]: scenario_bytes[name]
            for name in SCENARIO_IDS
        },
        scenario_sha256=scenario_hashes,
        resolved_bytes=outputs, resolved_sha256=hashes,
    )


def write_training_asset_bundle(repository_root: Path) -> TrainingAssetBundle:
    """Write the allowlisted manifest, scenarios and resolved configs."""
    bundle = build_training_asset_bundle(repository_root)
    root = repository_root.resolve()
    (
        root / 'artifacts/simulation/roadmap_b_b2/asset_manifest.json'
    ).write_bytes(bundle.manifest_bytes)
    for name, content in bundle.scenario_bytes.items():
        (
            root / 'ros2_ws/src/mecanum_nav_rl/scenarios/local_training' / name
        ).write_bytes(content)
    for name, content in bundle.resolved_bytes.items():
        (
            root / 'ros2_ws/src/mecanum_nav_rl/config/v3/resolved' / name
        ).write_bytes(content)
    return bundle


if __name__ == '__main__':
    repository_root = Path(__file__).resolve().parents[5]
    result = write_training_asset_bundle(repository_root)
    for name, digest in sorted(result.resolved_sha256.items()):
        print(f'{name} {digest}')
