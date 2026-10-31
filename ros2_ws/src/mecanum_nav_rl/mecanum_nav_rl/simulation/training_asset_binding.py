"""Build immutable Roadmap B training asset and resolved-config bytes.

This module reads only the exact asset sources named in the manifest. It does
not launch a simulator, resolve Fuel resources, or write on import. The CLI is
an explicit offline build tool that writes only the three allowlisted resolved
outputs and the allowlisted manifest.
"""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
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
_WHEEL_LINKS = {'Wheel_LF_1', 'Wheel_RF_1', 'Wheel_RB_1', 'Wheel_LB_1'}
_BACKEND_FINGERPRINT_INPUTS = (
    'mecanum_sim_backend/CMakeLists.txt',
    'mecanum_sim_backend/package.xml',
    'mecanum_sim_backend/env-hooks/mecanum_sim_backend.dsv.in',
    'mecanum_sim_backend/include/mecanum_sim_backend/backend_system.hpp',
    'mecanum_sim_backend/include/mecanum_sim_backend/receipt_gate.hpp',
    'mecanum_sim_backend/include/mecanum_sim_backend/contact_coverage.hpp',
    'mecanum_sim_backend/src/backend_system.cpp',
    'mecanum_sim_backend/src/receipt_gate.cpp',
    'mecanum_sim_backend/src/contact_coverage.cpp',
    'mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg',
    'mecanum_nav_rl_interfaces/msg/LocalTrainingSafetyInput.msg',
    'mecanum_nav_rl_interfaces/msg/SimulationContactState.msg',
    'mecanum_nav_rl_interfaces/srv/LocalTrainingBackendControl.srv',
    'mecanum_nav_rl_interfaces/CMakeLists.txt',
    'mecanum_nav_rl_interfaces/package.xml',
    'mecanum_nav_bringup/config/bridge/local_training.runtime.yaml',
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


def backend_source_fingerprint(repository_root: Path) -> dict[str, str]:
    """Hash all backend behavior headers, implementations and build inputs."""
    source_root = repository_root / 'ros2_ws/src'
    sources = {
        relative: _sha256(
            (source_root / relative).read_bytes(),
        )
        for relative in _BACKEND_FINGERPRINT_INPUTS
    }
    return {
        **sources,
        'fingerprint_sha256': _sha256(_canonical_bytes(sources)),
    }


def validate_b2_asset_sources(description: Path) -> dict[str, object]:
    """Check world, model, contact and sensor facts from source bytes."""
    description = description.resolve(strict=True)
    world_root = ET.parse(
        description / 'worlds/b2_training_arena.sdf',
    ).getroot()
    world = world_root.find('world')
    if world_root.get('version') != '1.11' or world is None:
        raise ValueError('B2 world must be a complete SDFormat 1.11 world')
    world_name = world.get('name')
    physics = world.find('physics')
    if world_name != 'b2_training_arena' or physics is None:
        raise ValueError('B2 world identity or physics element is invalid')
    step_s = float(physics.findtext('max_step_size', 'nan'))
    rtf = float(physics.findtext('real_time_factor', 'nan'))
    if step_s != 0.01 or rtf != 1.0:
        raise ValueError('B2 physics step or target real-time factor differs')
    plugins = world.findall('plugin')
    required_systems = {
        'gz::sim::systems::Physics', 'gz::sim::systems::Sensors',
        'gz::sim::systems::SceneBroadcaster',
        'gz::sim::systems::UserCommands', 'gz::sim::systems::Contact',
    }
    if {item.get('name') for item in plugins} != required_systems:
        raise ValueError('B2 world plugin inventory differs from contract')
    if len(plugins) != len(required_systems):
        raise ValueError('B2 world has duplicate or extra system plugins')

    model_root = ET.parse(
        description / 'models/mecanum_b2/model.sdf',
    ).getroot()
    model = model_root.find('model')
    if (
        model_root.get('version') != '1.11' or model is None
        or model.get('name') != 'mecanum_b2'
    ):
        raise ValueError('B2 robot model identity is invalid')
    probe_root = ET.parse(
        description / 'models/b2_contact_probe/model.sdf',
    ).getroot()
    probe = probe_root.find('model')
    probe_collision = None if probe is None else probe.find('.//collision')
    probe_mass = None if probe is None else probe.findtext('.//inertial/mass')
    probe_inertia = (
        None if probe is None else probe.find('link/inertial/inertia')
    )
    probe_inertia_values = (
        None if probe_inertia is None else tuple(
            probe_inertia.findtext(name, '') for name in (
                'ixx', 'iyy', 'izz', 'ixy', 'ixz', 'iyz',
            )
        )
    )
    probe_size = (
        None if probe_collision is None
        else probe_collision.findtext('geometry/box/size')
    )
    probe_sensor = (
        None if probe is None
        else probe.find("./link/sensor[@type='contact']")
    )
    if (
        probe_root.get('version') != '1.11' or probe is None
        or probe.get('name') != 'b2_contact_probe'
        or probe.findtext('static') != 'false'
        or probe_size != '0.10 0.10 0.10'
        or float(probe_mass or 'nan') != 1.0
        or probe_inertia_values != (
            '0.001666666666666667', '0.001666666666666667',
            '0.001666666666666667', '0', '0', '0',
        )
        or probe_collision is None
        or probe_collision.get('name') != 'collision'
        or probe_sensor is None
        or probe_sensor.get('name') != 'contact_sensor'
        or probe_sensor.findtext('contact/collision') != 'collision'
        or probe_sensor.findtext('update_rate') != '100'
        or probe_sensor.findtext('always_on') != 'true'
    ):
        raise ValueError('contact probe geometry, inertia, or sensor differs')
    model_plugins = model.findall('plugin')
    if (
        len(model_plugins) != 1
        or model_plugins[0].get('name')
        != 'mecanum_sim_backend::BackendSystem'
        or model_plugins[0].get('filename')
        != 'mecanum_sim_backend_system'
    ):
        raise ValueError(
            'B2 robot must contain exactly one native backend plugin'
        )
    serialized = ET.tostring(model, encoding='unicode')
    if any(
        name in serialized
        for name in ('VelocityControl', 'MecanumDrive', 'ros2_control')
    ):
        raise ValueError(
            'B2 robot contains a second actuator or control plugin'
        )
    links = {item.get('name'): item for item in model.findall('link')}
    expected_links = {'base_link', 'lidar_frame', *_WHEEL_LINKS}
    if set(links) != expected_links:
        raise ValueError(
            'B2 robot link inventory differs from declared surrogate'
        )

    collision_names: set[str] = set()
    collision_records: list[dict[str, object]] = []
    plugin = model_plugins[0]
    declared: dict[str, dict[str, str]] = {}
    for element in plugin.findall('tracked_collision'):
        collision_name = element.get('name')
        sensor_name = element.get('sensor')
        wheel_ignore = element.get('wheel_floor_ignore')
        if (
            not collision_name or not sensor_name
            or wheel_ignore not in {'true', 'false'}
        ):
            raise ValueError(
                'contact registry entry must bind collision, sensor and '
                'wheel-floor policy'
            )
        if collision_name in declared:
            raise ValueError(
                'contact registry contains duplicate collision identity'
            )
        declared[collision_name] = {
            'sensor': sensor_name,
            'wheel_floor_ignore': wheel_ignore,
        }
    for link_name, link in links.items():
        for collision in link.findall('collision'):
            leaf = collision.get('name')
            if not leaf:
                raise ValueError(
                    f'B2 collision under {link_name} has no explicit name'
                )
            scoped = f'{world_name}::mecanum_b2::{link_name}::{leaf}'
            if scoped in collision_names:
                raise ValueError(
                    'B2 model contains duplicate scoped collisions'
                )
            collision_names.add(scoped)
            sensors = []
            for sensor in link.findall("sensor[@type='contact']"):
                if sensor.findtext('contact/collision') == leaf:
                    sensors.append(sensor)
            if len(sensors) != 1:
                raise ValueError(
                    f'collision {scoped} must have exactly one linked '
                    'contact sensor'
                )
            sensor = sensors[0]
            sensor_scoped = (
                f'{world_name}::mecanum_b2::{link_name}::'
                f'{sensor.get("name")}'
            )
            record = {
                'collision': scoped,
                'sensor': sensor_scoped,
                'wheel_floor_ignore': link_name in _WHEEL_LINKS,
            }
            collision_records.append(record)
    if set(declared) != collision_names:
        raise ValueError(
            'contact registry does not exactly cover the model collision set'
        )
    for record in collision_records:
        entry = declared[str(record['collision'])]
        if (
            entry['sensor'] != record['sensor']
            or entry['wheel_floor_ignore']
            != str(record['wheel_floor_ignore']).lower()
        ):
            raise ValueError(
                'contact registry differs from source collision/sensor '
                'mapping'
            )

    lidar_sensors = [
        sensor for link in links.values()
        for sensor in link.findall("sensor[@type='gpu_lidar']")
    ]
    if len(lidar_sensors) != 1:
        raise ValueError('B2 robot must contain exactly one GPU LiDAR')
    lidar = lidar_sensors[0]
    angle = lidar.find('lidar/scan/horizontal')
    range_node = lidar.find('lidar/range')
    if (
        lidar.get('name') != 'B2_GENERIC_2D_V1'
        or float(lidar.findtext('update_rate', 'nan')) != 10.0
        or lidar.findtext('topic') != '/b2/scan'
        or lidar.findtext('lidar/scan/horizontal/samples') != '500'
        or angle is None
        or float(angle.findtext('min_angle', 'nan')) != -3.141592653589793
        or float(angle.findtext('max_angle', 'nan')) != 3.141592653589793
        or range_node is None
        or float(range_node.findtext('min', 'nan')) != 0.10
        or float(range_node.findtext('max', 'nan')) != 8.0
    ):
        raise ValueError(
            'B2 LiDAR rate/frame/topic/geometry differs from profile'
        )
    lidar_pose = links['lidar_frame'].findtext('pose', '').split()
    if len(lidar_pose) != 6:
        raise ValueError(
            'B2 lidar_frame requires a full six-value static pose'
        )
    urdf_root = ET.parse(description / 'urdf/mecanum_b2_static.urdf').getroot()
    joint = urdf_root.find("joint[@name='base_link_to_lidar_frame']")
    origin = None if joint is None else joint.find('origin')
    if (
        origin is None
        or origin.get('xyz') != '-0.031765 0 0.140'
        or origin.get('rpy') != '0 0 0'
    ):
        raise ValueError(
            'RSP static extrinsic differs from the approved B2 profile'
        )
    if (
        [float(value) for value in lidar_pose[:3]] != [-0.031765, 0.0, 0.14]
        or [float(value) for value in lidar_pose[3:]] != [0.0, 0.0, 0.0]
    ):
        raise ValueError(
            'Gazebo lidar pose differs from the RSP-owned extrinsic'
        )
    canonical_root = ET.parse(
        description / 'urdf/ROBOT_URDF_final.xacro',
    ).getroot()
    canonical_links = {
        item.get('name'): item for item in canonical_root.findall('link')
    }
    b2_base = links['base_link'].find('collision/geometry/box/size')
    canonical_base = canonical_links.get('base_link')
    canonical_base_size = (
        None if canonical_base is None else
        (lambda node: None if node is None else node.get('size'))(
            canonical_base.find('collision/geometry/box'),
        )
    )
    canonical_base_collision = (
        None if canonical_base is None else canonical_base.find('collision')
    )
    b2_base_collision = links['base_link'].find('collision')
    if (
        b2_base is None or b2_base.text != canonical_base_size
        or canonical_base_collision is None or b2_base_collision is None
        or canonical_base_collision.get('name')
        != b2_base_collision.get('name')
    ):
        raise ValueError(
            'B2 chassis collision differs from canonical geometry'
        )
    canonical_inertial = (
        None if canonical_base is None else canonical_base.find('inertial')
    )
    b2_inertial = links['base_link'].find('inertial')
    canonical_mass = (
        None if canonical_inertial is None else canonical_inertial.find('mass')
    )
    b2_mass = None if b2_inertial is None else b2_inertial.find('mass')
    canonical_matrix = (
        None if canonical_inertial is None
        else canonical_inertial.find('inertia')
    )
    b2_matrix = None if b2_inertial is None else b2_inertial.find('inertia')
    canonical_origin = (
        None if canonical_inertial is None
        else canonical_inertial.find('origin')
    )
    b2_pose = None if b2_inertial is None else b2_inertial.findtext('pose')
    if (
        canonical_mass is None or b2_mass is None
        or float(canonical_mass.get('value', 'nan'))
        != float(b2_mass.text or 'nan')
        or canonical_matrix is None or b2_matrix is None
        or canonical_origin is None or b2_pose is None
    ):
        raise ValueError('B2 chassis mass/inertia is incomplete or differs')
    for component in ('ixx', 'iyy', 'izz', 'ixy', 'iyz', 'ixz'):
        target = b2_matrix.findtext(component)
        if (
            canonical_matrix.get(component) is None or target is None
            or float(canonical_matrix.get(component, 'nan'))
            != float(target)
        ):
            raise ValueError(
                'B2 chassis inertia differs from canonical source'
            )
    inertial_origin = canonical_origin.get('xyz', '').split()
    inertial_rpy = canonical_origin.get('rpy', '').split()
    parsed_pose = b2_pose.split()
    if (
        len(inertial_origin) != 3 or len(inertial_rpy) != 3
        or len(parsed_pose) != 6
        or [float(value) for value in parsed_pose[:3]]
        != [float(value) for value in inertial_origin]
        or [float(value) for value in parsed_pose[3:]]
        != [float(value) for value in inertial_rpy]
    ):
        raise ValueError(
            'B2 chassis inertial pose differs from canonical source'
        )
    for wheel_name in sorted(_WHEEL_LINKS):
        canonical_link = canonical_links.get(wheel_name)
        b2_link = links[wheel_name]
        source_cylinder = (
            None if canonical_link is None
            else canonical_link.find('collision/geometry/cylinder')
        )
        b2_cylinder = b2_link.find('collision/geometry/cylinder')
        source_collision = (
            None if canonical_link is None
            else canonical_link.find('collision')
        )
        b2_collision = b2_link.find('collision')
        if (
            source_cylinder is None or b2_cylinder is None
            or float(source_cylinder.get('radius', 'nan'))
            != float(b2_cylinder.findtext('radius', 'nan'))
            or float(source_cylinder.get('length', 'nan'))
            != float(b2_cylinder.findtext('length', 'nan'))
            or source_collision is None or b2_collision is None
            or b2_collision.get('name') != f'{wheel_name}_collision'
        ):
            raise ValueError(
                f'B2 wheel collision geometry differs for {wheel_name}'
            )
        source_inertial = canonical_link.find('inertial')
        b2_inertial = b2_link.find('inertial')
        if source_inertial is None or b2_inertial is None:
            raise ValueError(f'B2 wheel inertia is missing for {wheel_name}')
        source_mass = source_inertial.find('mass')
        b2_mass = b2_inertial.find('mass')
        source_matrix = source_inertial.find('inertia')
        b2_matrix = b2_inertial.find('inertia')
        if (
            source_mass is None or b2_mass is None
            or source_matrix is None or b2_matrix is None
        ):
            raise ValueError(
                f'B2 wheel mass/inertia is incomplete for {wheel_name}'
            )
        if (
            float(source_mass.get('value', 'nan'))
            != float(b2_mass.text or 'nan')
        ):
            raise ValueError(
                f'B2 wheel mass differs from canonical source for {wheel_name}'
            )
        for component in ('ixx', 'iyy', 'izz'):
            if (
                float(source_matrix.get(component, 'nan'))
                != float(b2_matrix.findtext(component, 'nan'))
            ):
                raise ValueError(
                    'B2 wheel inertia differs from canonical source for '
                    f'{wheel_name}'
                )
        source_joint = canonical_root.find(
            f"joint[@name='{wheel_name.replace('_1', '_Joint')}']",
        )
        source_origin = (
            None if source_joint is None
            else source_joint.find('origin')
        )
        b2_pose = b2_link.findtext('pose', '').split()
        if (
            source_origin is None or len(b2_pose) != 6
            or [float(value) for value in b2_pose[:3]]
            != [
                float(value)
                for value in source_origin.get('xyz', '').split()
            ]
        ):
            raise ValueError(
                f'B2 wheel position differs from canonical joint for '
                f'{wheel_name}'
            )
    # The intentional surrogate differences are derived from the source pair.
    surrogate_differences = [
        'wheel joints are fixed links; wheel rotation is not simulated',
        'canonical wheel inertial-origin offsets are omitted from B2 '
        'link inertials',
        'canonical IntelRealsense_D435_Multibody_1 link and collision '
        'are omitted',
        'B2 planar body-motion commands bypass wheel traction and motor '
        'dynamics',
    ]
    if 'IntelRealsense_D435_Multibody_1' not in canonical_links or any(
        name == 'IntelRealsense_D435_Multibody_1' for name in links
    ):
        raise ValueError('canonical camera omission comparison is invalid')
    mesh_uris = [
        node.text.strip() for node in model.findall('.//uri')
        if node.text and node.text.strip().startswith(
            'model://ROBOT_URDF_final_description/meshes/'
        )
    ]
    if not mesh_uris:
        raise ValueError(
            'B2 model must declare canonical installed mesh resources'
        )
    for uri in mesh_uris:
        target = (
            description / 'meshes' / uri.rsplit('/', 1)[-1]
        ).resolve(strict=True)
        if not target.is_relative_to(description / 'meshes'):
            raise ValueError(
                'B2 mesh resource escapes canonical package share'
            )

    arena = world.find("model[@name='arena_walls']")
    obstacle = world.find("model[@name='obstacle_0']")
    if arena is None or obstacle is None:
        raise ValueError('B2 arena wall or obstacle geometry is missing')
    wall_sizes = [
        item.findtext('geometry/box/size')
        for item in arena.findall('.//collision')
    ]
    if wall_sizes != ['0.2 8.4 1', '0.2 8.4 1', '8 0.2 1', '8 0.2 1']:
        raise ValueError(
            'B2 wall collision inventory/geometry differs'
        )
    obstacle_size = obstacle.findtext('.//collision/geometry/box/size')
    obstacle_pose = obstacle.findtext('pose', '').split()
    if (
        obstacle_size != '0.2 1 1'
        or obstacle_pose != ['2.5', '0', '0.5', '0', '0', '0']
    ):
        raise ValueError('B2 obstacle identity/geometry differs')
    return {
        'world_name': world_name, 'physics_step_s': step_s,
        'target_real_time_factor': rtf,
        'contact_capability_probe': {
            'source_model_name': 'b2_contact_probe',
            'runtime_entity_name': 'b2_capability_probe',
            'collision_name': 'collision',
            'collision_size_m': [0.10, 0.10, 0.10],
            'mass_kg': 1.0,
            'inertia_kg_m2': [
                0.001666666666666667,
                0.001666666666666667,
                0.001666666666666667,
                0.0, 0.0, 0.0,
            ],
            'contact_sensor_name': 'contact_sensor',
            'contact_sensor_rate_hz': 100.0,
            'contact_sensor_collision': 'collision',
            'spawn_world_pose_xyz_yaw': [-2.0, 0.0, 0.07, 0.0],
            'separation_world_z_m': 0.20,
            'required_contact_samples': 3,
            'required_covered_empty_samples': 3,
            'minimum_sample_span_ros_s': 0.02,
            'probe_timeout_steady_s': 5.0,
            'cleanup_reserve_steady_s': 1.0,
        },
        'collision_registry': collision_records,
        'surrogate_differences': surrogate_differences,
        'lidar_rate_hz': 10.0, 'lidar_beams': 500,
        'lidar_topic': '/b2/scan', 'lidar_frame': 'lidar_frame',
        'lidar_min_angle_rad': -3.141592653589793,
        'lidar_max_angle_rad': 3.141592653589793,
        'lidar_range_m': [0.10, 8.0],
        'lidar_extrinsic_xyz_m': [-0.031765, 0.0, 0.140],
        'lidar_extrinsic_rpy_rad': [0.0, 0.0, 0.0],
        'wall_sizes_xyz_m': [
            [0.2, 8.4, 1.0], [0.2, 8.4, 1.0],
            [8.0, 0.2, 1.0], [8.0, 0.2, 1.0],
        ],
        'obstacle_center_xy_m': [2.5, 0.0],
        'obstacle_size_xyz_m': [0.2, 1.0, 1.0],
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n'
    ).encode('utf-8')


def build_training_asset_bundle(repository_root: Path) -> TrainingAssetBundle:
    """Bind real assets and B1 scenarios through the production compiler."""
    root = repository_root.resolve()
    description = root / 'ros2_ws/src/ROBOT_URDF_final_description'
    rl_package = root / 'ros2_ws/src/mecanum_nav_rl'
    semantics = validate_b2_asset_sources(description)
    backend_fingerprint = backend_source_fingerprint(root)
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
        'backend_contract': backend_fingerprint,
        'contact_capability_probe': semantics['contact_capability_probe'],
        'physics': {
            'step_ros_s': semantics['physics_step_s'],
            'target_real_time_factor': semantics['target_real_time_factor'],
        },
        'arena': {
            'interior_m': [8.0, 8.0],
            'wall_height_m': 1.0,
            'wall_thickness_m': 0.20,
            'wall_sizes_xyz_m': semantics['wall_sizes_xyz_m'],
            'obstacle_center_xy_m': semantics['obstacle_center_xy_m'],
            'obstacle_size_xyz_m': semantics['obstacle_size_xyz_m'],
        },
        'sensor': {
            'profile_id': 'B2_GENERIC_2D_V1',
            'topic': semantics['lidar_topic'],
            'frame_id': semantics['lidar_frame'],
            'rate_hz': semantics['lidar_rate_hz'],
            'beams': semantics['lidar_beams'],
            'angle_rad': [
                semantics['lidar_min_angle_rad'],
                semantics['lidar_max_angle_rad'],
            ],
            'range_m': semantics['lidar_range_m'],
            'extrinsic_xyz_m': semantics['lidar_extrinsic_xyz_m'],
            'extrinsic_rpy_rad': semantics['lidar_extrinsic_rpy_rad'],
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
            'tracked_collisions': semantics['collision_registry'],
            'canonical_geometry_comparison': {
                'surrogate_differences': semantics['surrogate_differences'],
            },
            'wheel_floor_ignore': {
                'normal_vertical_angle_max_deg': 15.0,
                'depth_m': [0.0, 0.005],
            },
            'probe_model': 'b2_contact_probe',
            'probe_collision': (
                'b2_training_arena::b2_capability_probe::link::collision'
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
