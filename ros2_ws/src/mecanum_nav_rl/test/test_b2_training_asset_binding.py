"""Offline binding tests for real source assets and three B1 scenarios."""
from __future__ import annotations

from pathlib import Path

from mecanum_nav_rl.config.v3_compiler import compile_resolved_document_v3
from mecanum_nav_rl.config.v3_loader import load_v3_yaml_mapping
from mecanum_nav_rl.config.v3_models import ResolvedConfigV3
from mecanum_nav_rl.simulation.training_asset_binding import (
    build_training_asset_bundle,
)


_ROOT = Path(__file__).resolve().parents[4]


def test_manifest_scenarios_and_resolved_outputs_bind_real_assets() -> None:
    """Build outputs bind to the actual source asset manifest."""
    bundle = build_training_asset_bundle(_ROOT)
    assert len(bundle.manifest_sha256) == 64
    assert set(bundle.scenario_sha256) == {
        'B2_SOAK_V1', 'B2_GOAL_SETTLE_V1', 'B2_CONTACT_V1',
    }
    assert set(bundle.resolved_bytes) == {
        'sim_train_local_training_soak.resolved.json',
        'sim_train_local_training_goal_settle.resolved.json',
        'sim_train_local_training_contact.resolved.json',
    }
    assert all(len(value) == 64 for value in bundle.resolved_sha256.values())
    manifest = bundle.manifest_bytes.decode()
    assert (
        'REQUIRED_BUILD_INPUT' not in manifest
        and 'TEST_ONLY' not in manifest
    )
    for filename, content in bundle.resolved_bytes.items():
        document = __import__('json').loads(content)
        model = ResolvedConfigV3.model_validate(document)
        assert (
            model.provenance.source_manifest_sha256
            == bundle.manifest_sha256
        )
        assert (
            model.training.local_training.backend_id
            == 'NATIVE_B2_BACKEND_V1'
        )
        assert model.map_identity.training_binding.binding_status == 'BOUND'
        assert (
            document['provenance']['config_hash']
            == bundle.resolved_sha256[filename]
        )


def test_scenario_outputs_follow_exact_b1_ids_and_contact_selection() -> None:
    """Manifest records the B1 scenario IDs and probe selection."""
    bundle = build_training_asset_bundle(_ROOT)
    contact = bundle.manifest_bytes.decode()
    assert '"active_contact_probe": true' in contact
    assert contact.count('"active_contact_probe": false') == 2
    base = load_v3_yaml_mapping(
        _ROOT / (
            'ros2_ws/src/mecanum_nav_rl/config/v3/'
            'local_training/base.yaml'
        ),
    )
    assert (
        base['map_identity']['training_binding']['binding_status']
        == 'UNRESOLVED'
    )


def test_test_only_or_placeholder_resolved_input_cannot_be_sealed() -> None:
    """Production compiler rejects TEST_ONLY binding status."""
    bundle = build_training_asset_bundle(_ROOT)
    import json
    document = json.loads(next(iter(bundle.resolved_bytes.values())))
    document[
        'map_identity'
    ]['training_binding']['binding_status'] = 'TEST_ONLY'
    document['map_identity']['training_binding'].pop('asset_manifest_sha256')
    document['provenance'].pop('config_hash', None)
    try:
        compile_resolved_document_v3(document)
    except ValueError:
        pass
    else:
        raise AssertionError('TEST_ONLY config was compiled')


def _copy_description_for_mutation(tmp_path):
    """Copy source assets outside the repository for mutation checks."""
    import shutil

    destination = tmp_path / 'description'
    shutil.copytree(
        _ROOT / 'ros2_ws/src/ROBOT_URDF_final_description', destination,
        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'),
    )
    return destination


def test_asset_binder_rejects_sensor_and_extrinsic_mutations(tmp_path):
    """Sensor rate and RSP extrinsic mutations fail semantic validation."""
    import pytest
    from mecanum_nav_rl.simulation.training_asset_binding import (
        validate_b2_asset_sources,
    )

    description = _copy_description_for_mutation(tmp_path)
    model_path = description / 'models/mecanum_b2/model.sdf'
    original = model_path.read_text(encoding='utf-8')
    model_path.write_text(
        original.replace(
            '<update_rate>10</update_rate>',
            '<update_rate>11</update_rate>', 1,
        ),
        encoding='utf-8',
    )
    with pytest.raises(ValueError, match='LiDAR'):
        validate_b2_asset_sources(description)
    model_path.write_text(original, encoding='utf-8')

    urdf_path = description / 'urdf/mecanum_b2_static.urdf'
    urdf = urdf_path.read_text(encoding='utf-8')
    urdf_path.write_text(
        urdf.replace('-0.031765', '-0.030000', 1), encoding='utf-8',
    )
    with pytest.raises(ValueError, match='extrinsic'):
        validate_b2_asset_sources(description)


def test_binder_rejects_collision_geometry_name_and_plugin_mutations(tmp_path):
    """Check collision registry, geometry and actuator plugin count."""
    import pytest
    import xml.etree.ElementTree as ET
    from mecanum_nav_rl.simulation.training_asset_binding import (
        validate_b2_asset_sources,
    )

    description = _copy_description_for_mutation(tmp_path)
    model_path = description / 'models/mecanum_b2/model.sdf'
    original = model_path.read_text(encoding='utf-8')
    for before, after, reason in (
        ('0.4 0.28 0.10', '0.41 0.28 0.10', 'chassis collision'),
        (
            's3_d3_base_contact_collision', 'renamed_collision',
            'linked contact sensor',
        ),
    ):
        model_path.write_text(
            original.replace(before, after, 1), encoding='utf-8',
        )
        with pytest.raises(ValueError, match=reason):
            validate_b2_asset_sources(description)
    model_path.write_text(original, encoding='utf-8')
    root = ET.fromstring(original)
    model = root.find('model')
    assert model is not None
    ET.SubElement(
        model, 'plugin', {
            'name': 'second_actuator', 'filename': 'unknown_actuator',
        },
    )
    model_path.write_bytes(ET.tostring(root))
    with pytest.raises(ValueError, match='exactly one native backend'):
        validate_b2_asset_sources(description)


def test_asset_binder_rejects_base_inertia_mutation(tmp_path):
    """Canonical chassis mass and inertia remain source-derived."""
    import pytest
    from mecanum_nav_rl.simulation.training_asset_binding import (
        validate_b2_asset_sources,
    )

    description = _copy_description_for_mutation(tmp_path)
    model_path = description / 'models/mecanum_b2/model.sdf'
    original = model_path.read_text(encoding='utf-8')
    model_path.write_text(
        original.replace(
            '<mass>2</mass>', '<mass>2.1</mass>', 1,
        ),
        encoding='utf-8',
    )
    with pytest.raises(ValueError, match='mass/inertia'):
        validate_b2_asset_sources(description)


def test_asset_binder_rejects_probe_inertia_sensor_and_collision_mutations(
    tmp_path,
):
    """The capability fixture is source-validated before it is bound."""
    import pytest
    from mecanum_nav_rl.simulation.training_asset_binding import (
        validate_b2_asset_sources,
    )

    description = _copy_description_for_mutation(tmp_path)
    model_path = description / 'models/b2_contact_probe/model.sdf'
    original = model_path.read_text(encoding='utf-8')
    for before, after in (
        ('<ixx>0.001666666666666667</ixx>', '<ixx>0.0017</ixx>'),
        ('<update_rate>100</update_rate>', '<update_rate>50</update_rate>'),
        ('<collision>collision</collision>', '<collision>other</collision>'),
    ):
        model_path.write_text(
            original.replace(before, after, 1), encoding='utf-8',
        )
    with pytest.raises(
        ValueError, match='probe geometry, inertia, or sensor',
    ):
        validate_b2_asset_sources(description)


def test_backend_fingerprint_covers_headers_interfaces_and_probe_inputs(
    tmp_path,
):
    """Fingerprint backend, ROSIDL and fixture-service dependencies."""
    import shutil
    from mecanum_nav_rl.simulation.training_asset_binding import (
        backend_source_fingerprint,
    )

    source_root = _ROOT
    original = backend_source_fingerprint(source_root)
    copy_root = tmp_path / 'repo'
    package = source_root / 'ros2_ws/src/mecanum_sim_backend'
    target = copy_root / 'ros2_ws/src/mecanum_sim_backend'
    shutil.copytree(package, target)
    interfaces = source_root / 'ros2_ws/src/mecanum_nav_rl_interfaces'
    interface_target = copy_root / 'ros2_ws/src/mecanum_nav_rl_interfaces'
    shutil.copytree(interfaces, interface_target)
    bringup = source_root / 'ros2_ws/src/mecanum_nav_bringup'
    shutil.copytree(bringup, copy_root / 'ros2_ws/src/mecanum_nav_bringup')
    header = target / 'include/mecanum_sim_backend/receipt_gate.hpp'
    header.write_text(
        header.read_text(encoding='utf-8') + '\n// fingerprint mutation\n',
        encoding='utf-8',
    )
    changed = backend_source_fingerprint(copy_root)
    assert changed['fingerprint_sha256'] != original['fingerprint_sha256']
    relative_header = (
        'mecanum_sim_backend/include/mecanum_sim_backend/receipt_gate.hpp'
    )
    assert changed[relative_header] != original[relative_header]
    hook = target / 'env-hooks/mecanum_sim_backend.dsv.in'
    hook.write_text(
        hook.read_text(encoding='utf-8') + '# fingerprint mutation\n',
        encoding='utf-8',
    )
    changed_hook = backend_source_fingerprint(copy_root)
    assert (
        changed_hook['fingerprint_sha256']
        != changed['fingerprint_sha256']
    )
    relative_hook = 'mecanum_sim_backend/env-hooks/mecanum_sim_backend.dsv.in'
    assert changed_hook[relative_hook] != changed[relative_hook]
    receipt = (
        interface_target / 'msg/FinalIssuedCommandReceipt.msg'
    )
    receipt.write_text(
        receipt.read_text(encoding='utf-8') + '# fingerprint mutation\n',
        encoding='utf-8',
    )
    changed_receipt = backend_source_fingerprint(copy_root)
    assert (
        changed_receipt['fingerprint_sha256']
        != changed_hook['fingerprint_sha256']
    )
    relative_receipt = (
        'mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg'
    )
    assert changed_receipt[relative_receipt] != changed_hook[relative_receipt]
    for relative in (
        'mecanum_nav_rl_interfaces/srv/LocalTrainingBackendControl.srv',
        'mecanum_nav_rl_interfaces/CMakeLists.txt',
        'mecanum_nav_rl_interfaces/package.xml',
        'mecanum_nav_bringup/config/bridge/local_training.runtime.yaml',
    ):
        source = source_root / 'ros2_ws/src' / relative
        copied = copy_root / 'ros2_ws/src' / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(source.read_bytes())
        before = backend_source_fingerprint(copy_root)
        copied.write_bytes(copied.read_bytes() + b'\n# fingerprint mutation\n')
        after = backend_source_fingerprint(copy_root)
        assert after['fingerprint_sha256'] != before['fingerprint_sha256']
        assert after[relative] != before[relative]
