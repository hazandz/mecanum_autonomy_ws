"""Pure, fail-closed B2.2 launch contract; it never spawns a process."""
from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from mecanum_nav_rl.config.v3_hashing import config_v3_sha256
from mecanum_nav_rl.config.v3_models import ResolvedConfigV3
from mecanum_nav_rl.tasks.scenario_artifact import (
    GT_ODOM_2D_REFERENCE_ID, ScenarioArtifactLoadStatus,
    ScenarioArtifactLoader, scenario_artifact_sha256,
)


@dataclass(frozen=True)
class LaunchPlan:
    """Validated launch inputs and process commands for one session."""

    gui_requested: bool
    world_file: Path
    gui_config: Path
    resolved_config: Path
    session_id: str
    config_hash: str
    asset_manifest_sha256: str
    coordinator_ingress_instance_id: int
    commands: tuple[tuple[str, ...], ...]
    environment: dict[str, str]


def parse_gui_argument(value: str) -> bool:
    """Parse only the exact lowercase GUI boolean spellings."""
    if value == 'true':
        return True
    if value == 'false':
        return False
    raise ValueError("gui must be exactly 'true' or 'false'")


def load_bound_config(path: Path) -> tuple[dict[str, object], str, str, str]:
    """Load and validate a production-bound LOCAL_TRAINING config."""
    path = path.resolve(strict=True)
    if not path.is_absolute() or not path.is_file():
        raise ValueError('resolved_config must be an existing absolute file')
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise ValueError('resolved config root must be an object')
    provenance = document.get('provenance')
    binding_root = document.get('map_identity')
    training_root = document.get('training')
    if (
        not isinstance(provenance, dict)
        or not isinstance(binding_root, dict)
        or not isinstance(training_root, dict)
    ):
        raise ValueError('resolved config lacks training provenance')
    model = ResolvedConfigV3.model_validate(document)
    binding = binding_root.get('training_binding')
    local = training_root.get('local_training')
    runtime = document.get('runtime')
    if (
        not isinstance(binding, dict)
        or not isinstance(local, dict)
        or not isinstance(runtime, dict)
    ):
        raise ValueError('resolved config lacks bound training sections')
    digest = provenance.get('config_hash')
    manifest = binding.get('asset_manifest_sha256')
    scenario = binding.get('scenario_id')
    if (
        binding.get('binding_status') != 'BOUND'
        or local.get('backend_id') != 'NATIVE_B2_BACKEND_V1'
    ):
        raise ValueError('launch requires a production BOUND B2 config')
    if (
        runtime.get('runtime_profile') != 'sim_train'
        or runtime.get('navigation_mode') != 'LOCAL_TRAINING'
    ):
        raise ValueError('launch only accepts sim_train/LOCAL_TRAINING')
    if not all(
        isinstance(item, str)
        and len(item) == 64
        and all(c in '0123456789abcdef' for c in item)
        for item in (digest, manifest)
    ):
        raise ValueError(
            'config and manifest hashes must be lowercase SHA-256'
        )
    unhashed = deepcopy(document)
    unhashed['provenance'].pop('config_hash')
    if config_v3_sha256(unhashed) != digest:
        raise ValueError(
            'resolved config hash does not match canonical V3 content'
        )
    if (
        model.map_identity.training_binding.world_id != 'b2_training_arena'
    ):
        raise ValueError(
            'resolved config world binding is not b2_training_arena'
        )
    if scenario not in {'B2_SOAK_V1', 'B2_GOAL_SETTLE_V1', 'B2_CONTACT_V1'}:
        raise ValueError('scenario id is not in the bound B2 catalog')
    return document, digest, manifest, scenario


def bind_world_for_scenario(
    world_source: bytes, model_source: bytes, scenario_id: str,
    session_id: str, config_hash: str, manifest_hash: str,
    coordinator_ingress_instance_id: int,
) -> bytes:
    """Bind the model identity and select the contact probe."""
    if not session_id or session_id != session_id.strip():
        raise ValueError('session_id must be a non-empty Run ID')
    if (
        type(coordinator_ingress_instance_id) is not int
        or coordinator_ingress_instance_id <= 0
    ):
        raise ValueError('coordinator ingress identity must be nonzero')
    for value in (config_hash, manifest_hash):
        if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('startup hashes must be lowercase SHA-256')
    root = ET.fromstring(world_source)
    world = root.find('world')
    if world is None:
        raise ValueError('B2 SDF is missing world')
    model_include = next(
        (
            item for item in world.findall('include')
            if item.findtext('name') == 'mecanum_b2'
        ),
        None,
    )
    if model_include is None:
        raise ValueError('B2 world is missing mecanum_b2 model include')
    model_root = ET.fromstring(model_source)
    model = model_root.find('model')
    if model is None or model.get('name') != 'mecanum_b2':
        raise ValueError('installed B2 model source is missing mecanum_b2')
    model = ET.fromstring(ET.tostring(model, encoding='utf-8'))
    model.set('name', 'mecanum_b2')
    include_index = list(world).index(model_include)
    world.remove(model_include)
    world.insert(include_index, model)
    plugin = model.find("plugin[@name='mecanum_sim_backend::BackendSystem']")
    if plugin is None:
        raise ValueError('B2 world is missing the native backend')
    for tag, value in (
        ('session_id', session_id),
        ('config_hash', config_hash),
        ('asset_manifest_sha256', manifest_hash),
        ('coordinator_ingress_instance_id',
         str(coordinator_ingress_instance_id)),
    ):
        node = plugin.find(tag)
        if node is None:
            raise ValueError(f'backend plugin is missing {tag}')
        node.text = value
    include = root.find(".//include[@name='b2_contact_probe']")
    if scenario_id == 'B2_CONTACT_V1':
        if include is None:
            include = ET.SubElement(
                world, 'include', {'name': 'b2_contact_probe'},
            )
            ET.SubElement(include, 'uri').text = 'model://b2_contact_probe'
            ET.SubElement(include, 'pose').text = '0.65 0 0.05 0 0 0'
    elif include is not None:
        world.remove(include)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def build_launch_plan(
    *, gui: str, resolved_config: Path, world_file: Path,
    gui_config: Path, session_id: str, partition: str,
    resource_paths: tuple[Path, ...], plugin_path: Path,
    asset_manifest_file: Path, scenario_directory: Path,
    runtime_world_directory: Path,
    coordinator_ingress_instance_id: int,
) -> LaunchPlan:
    """Validate installed assets and construct bound process commands."""
    gui_requested = parse_gui_argument(gui)
    if (
        type(coordinator_ingress_instance_id) is not int
        or coordinator_ingress_instance_id <= 0
    ):
        raise ValueError('coordinator ingress identity must be nonzero')
    document, config_hash, manifest_hash, scenario_id = load_bound_config(
        resolved_config,
    )
    manifest_file = asset_manifest_file.resolve(strict=True)
    manifest_bytes = manifest_file.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_hash:
        raise ValueError(
            'installed asset manifest bytes do not match resolved config'
        )
    manifest = json.loads(manifest_bytes)
    description_share = manifest_file.parents[2]
    if (
        manifest.get('schema_id') != 'roadmap_b_b2_asset_manifest/v1'
        or manifest.get('world_id') != 'b2_training_arena'
        or manifest.get('backend_id') != 'NATIVE_B2_BACKEND_V1'
    ):
        raise ValueError('installed asset manifest identity is invalid')
    binding = document['map_identity']['training_binding']
    if binding.get('world_id') != manifest['world_id']:
        raise ValueError(
            'resolved world binding differs from installed asset manifest'
        )
    closure = manifest.get('resource_closure')
    if not isinstance(closure, dict) or not closure:
        raise ValueError('installed asset manifest has no resource closure')
    resource_prefix = 'ROBOT_URDF_final_description/'
    for relative, expected_hash in closure.items():
        if (
            not isinstance(relative, str)
            or not relative.startswith(resource_prefix)
        ):
            raise ValueError(
                'asset manifest contains an invalid resource path'
            )
        resource = (
            description_share / relative[len(resource_prefix):]
        ).resolve(strict=True)
        if not resource.is_relative_to(description_share):
            raise ValueError(
                'asset resource escapes installed description share'
            )
        if (
            hashlib.sha256(resource.read_bytes()).hexdigest()
            != expected_hash
        ):
            raise ValueError(f'installed resource hash mismatch: {relative}')
    installed_world = world_file.resolve(strict=True)
    if (
        hashlib.sha256(installed_world.read_bytes()).hexdigest()
        != manifest.get('world_file_sha256')
    ):
        raise ValueError(
            'installed world bytes differ from asset manifest'
        )
    scenario_directory = scenario_directory.resolve(strict=True)
    scenario_binding = manifest.get('scenario_artifacts', {}).get(scenario_id)
    if not isinstance(scenario_binding, dict):
        raise ValueError('scenario is missing from installed manifest')
    scenario_path = (
        scenario_directory / scenario_binding['file']
    ).resolve(strict=True)
    if not scenario_path.is_relative_to(scenario_directory):
        raise ValueError('scenario path escapes installed catalog')
    scenario_document = json.loads(scenario_path.read_text(encoding='utf-8'))
    unsigned = deepcopy(scenario_document)
    unsigned['identity'].pop('scenario_content_sha256', None)
    if (
        scenario_artifact_sha256(unsigned)
        != scenario_binding.get('scenario_content_sha256')
    ):
        raise ValueError(
            'installed scenario content hash differs from manifest'
        )
    loader = ScenarioArtifactLoader(
        expected_gazebo_world_name=manifest['world_id'],
        expected_world_file_sha256=manifest['world_file_sha256'],
        expected_coordinate_reference_id=GT_ODOM_2D_REFERENCE_ID,
    )
    loaded = loader.load(scenario_document)
    if (
        loaded.status is not ScenarioArtifactLoadStatus.READY
        or loaded.artifact is None
        or loaded.artifact.identity.scenario_id != scenario_id
    ):
        raise ValueError('installed B2 scenario failed B1 artifact validation')
    world_file = world_file.resolve(strict=True)
    gui_config = gui_config.resolve(strict=True)
    runtime_world_directory = runtime_world_directory.resolve(strict=True)
    if (
        runtime_world_directory == world_file.parent
        or runtime_world_directory.is_relative_to(world_file.parent)
    ):
        raise ValueError(
            'runtime world copy must be outside installed package share'
        )
    world_file = runtime_world_directory / (
        f'{world_file.stem}.{scenario_id}.{session_id}.runtime.sdf'
    )
    if not partition or not partition.strip():
        raise ValueError('GZ_PARTITION must be explicitly bound')
    resource_value = os.pathsep.join(
        str(path.resolve(strict=True)) for path in resource_paths
    )
    environment = {
        'GZ_PARTITION': partition,
        'GZ_SIM_RESOURCE_PATH': resource_value,
        'GZ_SIM_SYSTEM_PLUGIN_PATH': str(plugin_path.resolve(strict=True)),
    }
    server = (
        'gz', 'sim', '--force-version', '8', '-s',
        '--headless-rendering', str(world_file),
    )
    gui_command = (
        'gz', 'sim', '--force-version', '8', '-g',
        '--gui-config', str(gui_config),
    )
    commands = (server, gui_command) if gui_requested else (server,)
    return LaunchPlan(
        gui_requested=gui_requested,
        world_file=world_file,
        gui_config=gui_config,
        resolved_config=resolved_config.resolve(),
        session_id=session_id,
        config_hash=config_hash,
        asset_manifest_sha256=manifest_hash,
        coordinator_ingress_instance_id=coordinator_ingress_instance_id,
        commands=commands,
        environment=environment,
    )


def write_bound_world(
    plan: LaunchPlan, installed_world: Path, installed_model: Path,
) -> Path:
    """Write a session-bound world copy outside the installed package."""
    source = installed_world.read_bytes()
    model_source = installed_model.read_bytes()
    document, _, _, scenario = load_bound_config(plan.resolved_config)
    bound = bind_world_for_scenario(
        source, model_source, scenario, plan.session_id,
        plan.config_hash, plan.asset_manifest_sha256,
        plan.coordinator_ingress_instance_id,
    )
    plan.world_file.parent.mkdir(parents=True, exist_ok=True)
    plan.world_file.write_bytes(bound)
    return plan.world_file
