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
