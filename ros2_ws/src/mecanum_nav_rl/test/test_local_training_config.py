"""Offline schema 3.1 LOCAL_TRAINING configuration contracts."""

from __future__ import annotations

import ast
import json
from copy import deepcopy
from pathlib import Path

from mecanum_nav_rl.config.v3_compiler import (
    compile_resolved_document_v3,
    compile_v3_config,
)
from mecanum_nav_rl.config.v3_composition import (
    CanonicalFragmentKindV3,
    CanonicalFragmentV3,
    compose_canonical_v3_fragments,
)
from mecanum_nav_rl.config.v3_loader import load_v3_yaml_mapping
from mecanum_nav_rl.config.v3_models import (
    ActionContractV3,
    FrameTfContractV3,
    LocalTrainingContractV31,
    LocalTrainingFrameTfContractV31,
    ResolvedConfigV3,
)
from mecanum_nav_rl.config.v3_policy import ResolutionStageV3

from pydantic import ValidationError

import pytest


_ROOT = Path(__file__).resolve().parents[1] / 'config/v3'
_EXPECTED_SIM_EVAL_HASH = (
    '501a661b1ebde9b846325cc589927823e101375a6a189fcf84cac9ac8bf0aabe'
)


def _fragments():
    paths = (
        (CanonicalFragmentKindV3.BASE, 'local_training/base.yaml'),
        (CanonicalFragmentKindV3.FRAMES, 'local_training/frames.yaml'),
        (CanonicalFragmentKindV3.TOPICS_QOS, 'local_training/topics_qos.yaml'),
        (
            CanonicalFragmentKindV3.STATE_LOCALIZATION,
            'local_training/state_localization.yaml',
        ),
        (
            CanonicalFragmentKindV3.SYSTEM_CONTRACTS,
            'local_training/system_contracts.yaml',
        ),
        (CanonicalFragmentKindV3.RUNTIME_PROFILE, 'profiles/sim_train.yaml'),
        (CanonicalFragmentKindV3.NAVIGATION_MODE, 'modes/local_training.yaml'),
    )
    values = []
    for kind, path in paths:
        payload = load_v3_yaml_mapping(_ROOT / path)
        runtime = payload.get('runtime')
        if isinstance(runtime, dict):
            runtime.pop('allowed_navigation_modes', None)
        values.append(CanonicalFragmentV3(kind, payload))
    return tuple(values)


def _compile_inputs():
    composed = compose_canonical_v3_fragments(*_fragments())
    profile = load_v3_yaml_mapping(_ROOT / 'profiles/sim_train.yaml')
    profile['runtime'].pop('allowed_navigation_modes', None)
    mode = load_v3_yaml_mapping(_ROOT / 'modes/local_training.yaml')
    return composed, profile, mode


def test_schema_30_sim_eval_hash_and_serialization_remain_unchanged() -> None:
    """Keep the frozen schema 3.0 hash and omitted optional keys."""
    resolved_path = (
        Path(__file__).resolve().parents[1]
        / 'config/v3/resolved/sim_eval_nav2_baseline.resolved.json'
    )
    document = json.loads(resolved_path.read_text(encoding='utf-8'))
    unhashed = deepcopy(document)
    unhashed['provenance'].pop('config_hash')
    config = compile_resolved_document_v3(unhashed)
    assert config.provenance.config_hash == _EXPECTED_SIM_EVAL_HASH
    assert config.schema_version == '3.0'
    dumped = config.model_dump(mode='json', exclude_unset=True)
    assert set(dumped) == set(document)
    assert 'local_training' not in dumped['training']
    assert 'training_binding' not in dumped['map_identity']


def test_schema_31_local_training_contract_values() -> None:
    """Validate the seven-fragment local-training contract values."""
    composed, _, _ = _compile_inputs()
    assert composed['schema_version'] == '3.1'
    assert composed['runtime'] == {
        'runtime_profile': 'sim_train',
        'use_sim_time': True,
        'navigation_mode': 'LOCAL_TRAINING',
    }
    assert composed['state_estimation']['provider'] == (
        'INTERNAL_SIMULATED_ODOMETRY'
    )
    assert composed['localization']['provider'] == (
        'NOT_APPLICABLE_LOCAL_TRAINING'
    )
    assert composed['map_identity']['training_binding']['binding_status'] == (
        'UNRESOLVED'
    )
    assert composed['frames_tf']['map_frame'] is None
    assert composed['frames_tf']['odom_to_base_link_authority'] is None
    assert 'nav_msgs/msg/Odometry' not in str(composed['topics_qos'])
    assert 'gui' not in str(composed).lower()

    training = composed['training']['local_training']
    typed = LocalTrainingContractV31.model_validate(training)
    assert typed.command_components == ('vx', 'vy', 'wz')
    assert typed.max_planar_speed_mps == pytest.approx(0.32015621187164245)
    assert typed.stopping_distance_m == pytest.approx(0.906224, abs=1e-6)
    assert typed.stopping_distance_limit_m == 0.92
    assert (
        typed.noise_delay_samples == 0
        and typed.noise_dropout_probability == 0.0
    )
    assert typed.negative_delay_samples == 30
    assert typed.negative_dropout_probability == 1.0


def test_invalid_pairing_noise_and_stopping_contract_values_reject() -> None:
    """Reject temporal, numeric, and stopping-envelope deviations."""
    data = load_v3_yaml_mapping(_ROOT / 'local_training/system_contracts.yaml')
    training = deepcopy(data['training']['local_training'])
    training['pairing_tolerance_ns'] = 1
    with pytest.raises(ValidationError, match='pairing_tolerance_ns'):
        LocalTrainingContractV31.model_validate(training)
    training = deepcopy(data['training']['local_training'])
    training['position_bias_sigma_m'] = '0.005'
    with pytest.raises(ValidationError):
        LocalTrainingContractV31.model_validate(training)
    training = deepcopy(data['training']['local_training'])
    training['stopping_distance_limit_m'] = 0.90
    with pytest.raises(
        ValidationError, match='differs from approved contract'
    ):
        LocalTrainingContractV31.model_validate(training)


def test_compiler_rejects_unbound_or_test_only_assets_before_hashing() -> None:
    """Require a production binding before config hashing or resolution."""
    composed, profile, mode = _compile_inputs()
    with pytest.raises(ValueError, match='unresolved'):
        compile_v3_config(
            base_layer=composed,
            runtime_profile_layer=profile,
            navigation_mode_layer=mode,
            experiment_override_layer=None,
            measured_hardware_registry_layer=None,
            output_stage=ResolutionStageV3.CONFIG_INPUT,
            gate4=False,
        )
    test_only = deepcopy(composed)
    test_only['map_identity']['training_binding'][
        'binding_status'
    ] = 'TEST_ONLY'
    with pytest.raises(ValueError, match='TEST_ONLY'):
        compile_resolved_document_v3(test_only)
    no_binding = deepcopy(composed)
    no_binding['map_identity'].pop('training_binding')
    with pytest.raises(ValueError, match='requires an asset/scenario binding'):
        compile_v3_config(
            base_layer=no_binding,
            runtime_profile_layer=profile,
            navigation_mode_layer=mode,
            experiment_override_layer=None,
            measured_hardware_registry_layer=None,
            output_stage=ResolutionStageV3.CONFIG_INPUT,
            gate4=False,
        )


def test_compiler_rejects_mixed_nav2_authority_and_unknown_root() -> None:
    """Reject mixed navigation ownership and unknown canonical sections."""
    composed, profile, mode = _compile_inputs()
    bad = deepcopy(mode)
    bad['navigation']['controller_owner'] = 'Nav2ControllerServer'
    with pytest.raises(ValueError):
        compile_v3_config(
            base_layer=composed,
            runtime_profile_layer=profile,
            navigation_mode_layer=bad,
            experiment_override_layer=None,
            measured_hardware_registry_layer=None,
            output_stage=ResolutionStageV3.CONFIG_INPUT,
            gate4=False,
        )
    with pytest.raises(ValueError, match='unknown canonical top-level field'):
        compose_canonical_v3_fragments(
            CanonicalFragmentV3(
                CanonicalFragmentKindV3.BASE,
                {
                    **_fragments()[0].values,
                    'backend': {'owner': 'fake'},
                },
            ),
            *_fragments()[1:],
        )


def test_local_training_topics_qos_and_pure_module_import_boundary() -> None:
    """Keep topic ownership exact and pure config free of runtime imports."""
    topics = load_v3_yaml_mapping(
        _ROOT / 'local_training/topics_qos.yaml'
    )['topics_qos']
    by_name = {topic['name']: topic for topic in topics}
    assert by_name['/mecanum/local_training/safety_input']['message_type'] == (
        'mecanum_nav_rl_interfaces/msg/LocalTrainingSafetyInput'
    )
    safety_qos = by_name[
        '/mecanum/local_training/safety_input'
    ]['qos_profile_id']
    assert safety_qos == (
        'RELIABLE_VOLATILE_KEEP_LAST_10'
    )
    backend_qos = by_name[
        '/mecanum/local_training/backend_state'
    ]['qos_profile_id']
    assert backend_qos == (
        'RELIABLE_VOLATILE_KEEP_LAST_50'
    )
    assert by_name['/cmd_vel']['publisher_owner'] == 'FinalTwistPublisher'
    assert by_name['/mecanum/final_issued_command']['message_type'].endswith(
        'FinalIssuedCommandReceipt'
    )
    forbidden = {'rclpy', 'gazebo', 'gymnasium', 'stable_baselines3'}
    package = (
        Path(__file__).resolve().parents[1] / 'mecanum_nav_rl/config'
    )
    modules = (
        'v3_models.py',
        'v3_validators.py',
        'v3_composition.py',
        'v3_compiler.py',
    )
    for module in modules:
        tree = ast.parse((package / module).read_text(encoding='utf-8'))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split('.')[0])
        assert not roots & forbidden, module


def _compile_training_input(composed, profile=None, mode=None):
    profile = (
        deepcopy(profile)
        if profile is not None
        else load_v3_yaml_mapping(_ROOT / 'profiles/sim_train.yaml')
    )
    profile['runtime'].pop('allowed_navigation_modes', None)
    mode = deepcopy(mode) if mode is not None else load_v3_yaml_mapping(
        _ROOT / 'modes/local_training.yaml'
    )
    return compile_v3_config(
        base_layer=composed,
        runtime_profile_layer=profile,
        navigation_mode_layer=mode,
        experiment_override_layer=None,
        measured_hardware_registry_layer=None,
        output_stage=ResolutionStageV3.CONFIG_INPUT,
        gate4=False,
    )


def test_local_training_has_canonical_roots_and_action_contract() -> None:
    """Check all seven composed fragments before unresolved assets reject."""
    composed, _, _ = _compile_inputs()
    assert set(composed) == set(ResolvedConfigV3.model_fields)
    action = ActionContractV3.model_validate(composed['action'])
    assert action.component_order == ('vx', 'vy', 'wz')
    assert action.dimension == 3
    assert action.normalized_minimum == -1.0
    assert action.normalized_maximum == 1.0
    for invalid_action in (
        None,
        {**composed['action'], 'component_order': ['vx', 'wz', 'vy']},
        {**composed['action'], 'dimension': 2},
        {**composed['action'], 'normalized_minimum': -2.0},
    ):
        invalid = deepcopy(composed)
        if invalid_action is None:
            invalid.pop('action')
        else:
            invalid['action'] = invalid_action
        with pytest.raises(
            (ValueError, ValidationError), match='action|canonical root'
        ):
            _compile_training_input(invalid)


def test_schema_30_frame_contract_remains_non_nullable() -> None:
    """Schema 3.0 continues to reject absent frame identity and authority."""
    document = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / 'config/v3/resolved/sim_eval_nav2_baseline.resolved.json'
        ).read_text(encoding='utf-8')
    )
    document.pop('provenance', {}).pop('config_hash', None)
    for field in ('map_frame', 'odom_frame', 'map_to_odom_authority',
                  'odom_to_base_link_authority'):
        invalid = deepcopy(document)
        invalid['frames_tf'][field] = None
        with pytest.raises((ValueError, ValidationError)):
            compile_resolved_document_v3(invalid)
    combined = deepcopy(document)
    combined['frames_tf']['map_frame'] = None
    combined['frames_tf']['odom_frame'] = None
    with pytest.raises((ValueError, ValidationError)):
        compile_resolved_document_v3(combined)
    wrong_authority = deepcopy(document)
    wrong_authority['frames_tf']['map_to_odom_authority'] = 'WRONG_AUTHORITY'
    with pytest.raises((ValueError, ValidationError)):
        compile_resolved_document_v3(wrong_authority)
    missing_authority = deepcopy(document)
    missing_authority['frames_tf'].pop('odom_to_base_link_authority')
    with pytest.raises((ValueError, ValidationError)):
        compile_resolved_document_v3(missing_authority)
    with pytest.raises(ValidationError):
        FrameTfContractV3.model_validate(
            {**document['frames_tf'], 'map_frame': None}
        )
    composed, _, _ = _compile_inputs()
    assert composed['frames_tf']['map_frame'] is None
    assert composed['frames_tf']['odom_frame'] is None
    training_frames = LocalTrainingFrameTfContractV31.model_validate(
        composed['frames_tf']
    )
    assert training_frames.map_to_odom_authority is None
    assert training_frames.odom_to_base_link_authority is None


@pytest.mark.parametrize(
    ('mutation', 'message'),
    (
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_vx_mps', 0.20), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_vx_mps', 0.30), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_vy_mps', 0.10), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_vy_mps', 0.30), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_wz_radps', 0.70), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'max_wz_radps', 0.90), 'motion_limits'),
        (lambda data, profile: profile['motion_limits'].__setitem__(
            'source_class', 'TBD'),
         'source_class'),
        (
            lambda data, profile: data['map_identity'][
                'training_binding'
            ].__setitem__('world_id', 'another_world'),
            'world',
        ),
        (lambda data, profile: data['training']['local_training'].__setitem__(
            'navigation_mode', 'NAV2_BASELINE'), 'mode'),
    ),
)
def test_training_cross_section_invariants_precede_asset_rejection(
    mutation, message
) -> None:
    """Find static section errors before unresolved input rejection."""
    composed, _, _ = _compile_inputs()
    invalid = deepcopy(composed)
    profile = load_v3_yaml_mapping(_ROOT / 'profiles/sim_train.yaml')
    mutation(invalid, profile)
    with pytest.raises(ValueError, match=message):
        _compile_training_input(invalid, profile)


def test_scan_qos_is_exact_and_duplicate_topics_reject() -> None:
    """The local-training scan keeps its approved best-effort QoS contract."""
    composed, _, _ = _compile_inputs()
    scan = [
        topic for topic in composed['topics_qos'] if topic['name'] == '/scan'
    ]
    assert len(scan) == 1
    assert scan[0]['qos_profile_id'] == 'BEST_EFFORT_VOLATILE_KEEP_LAST_5'
    for invalid in (
        [
            {**topic, 'qos_profile_id': 'RELIABLE_VOLATILE_KEEP_LAST_10'}
            if topic['name'] == '/scan' else topic
            for topic in composed['topics_qos']
        ],
        [*composed['topics_qos'], deepcopy(scan[0])],
    ):
        changed = deepcopy(composed)
        changed['topics_qos'] = invalid
        with pytest.raises(ValueError, match='scan|topic'):
            _compile_training_input(changed)


def test_training_manifest_is_unresolved_input_and_rejects_before_hash(
    monkeypatch,
) -> None:
    """Unresolved source manifest cannot produce a production hash/object."""
    from mecanum_nav_rl.config import v3_compiler

    composed, profile, mode = _compile_inputs()
    assert isinstance(
        composed['provenance']['source_manifest_sha256'], dict
    )
    assert composed['provenance']['source_manifest_sha256'] == {
        'field_path': 'provenance.source_manifest_sha256',
        'token': 'REQUIRED_BUILD_INPUT',
        'reference_id': 'b2_training_asset_manifest',
    }
    source_text = (_ROOT / 'local_training/base.yaml').read_text(
        encoding='utf-8'
    )
    assert (
        '7e0a380b0d8df32f9a4fc30dd0dbbe9ed08aafdcd5efb3764bccd844b98c1cb1'
        not in source_text
    )
    calls = []
    monkeypatch.setattr(
        v3_compiler,
        'config_v3_sha256',
        lambda value: calls.append(value) or '0' * 64,
    )
    with pytest.raises(ValueError, match='unresolved tokenized input'):
        compile_v3_config(
            base_layer=composed,
            runtime_profile_layer=profile,
            navigation_mode_layer=mode,
            experiment_override_layer=None,
            measured_hardware_registry_layer=None,
            output_stage=ResolutionStageV3.CONFIG_INPUT,
            gate4=False,
        )
    with pytest.raises(ValueError, match='unresolved tokenized input'):
        compile_resolved_document_v3(composed)
    assert calls == []
