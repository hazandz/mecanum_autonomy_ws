import hashlib
import json
from pathlib import Path

import pytest
import rfc8785

from mecanum_base_bridge.hardware_config import (
    DOMAIN, HardwareConfigError, generate, load_manifest, manifest_digest, wheel_geometry,
)


ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / 'artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml'


def test_manifest_digest_uses_domain_nul_and_complete_mapping():
    mapping = load_manifest(MANIFEST)
    digest = manifest_digest(mapping)
    expected = hashlib.sha256(
        b'mecanum_hardware_config_hash/v1\x00' + rfc8785.dumps(mapping)
    ).digest()
    assert DOMAIN == b'mecanum_hardware_config_hash/v1\x00'
    assert digest == expected
    altered = dict(mapping)
    altered['unrelated_manifest_field'] = 'included in complete mapping'
    assert manifest_digest(altered) != digest


def test_generator_outputs_same_raw_digest_to_header_and_pi_json(tmp_path):
    header = tmp_path / 'generated.h'
    profile = tmp_path / 'hardware.json'
    digest = generate(MANIFEST, header, profile)
    header_text = header.read_text()
    metadata = json.loads(profile.read_text())
    assert metadata['hardware_config_hash_hex'] == digest
    assert metadata['communication_config_valid'] is True
    assert metadata['wheel_order'] == ['FL', 'FR', 'RL', 'RR']
    assert metadata['wheel_geometry']['wheel_diameter_m'] == 0.097
    assert metadata['wheel_geometry']['ticks_per_wheel_revolution'] == 937.2
    assert metadata['wheel_geometry']['encoder_tick_signs'] is None
    assert ', '.join(f'0x{b:02X}U' for b in bytes.fromhex(digest)) in header_text
    assert 'MECANUM_COMMUNICATION_CONFIG_VALID 1U' in header_text
    # Owner geometry is present; unresolved signs still fail motion startup.
    manifest = load_manifest(MANIFEST)
    assert manifest['kinematics']['wheel_diameter_m']['value'] == 0.097
    with pytest.raises(HardwareConfigError, match='signs are unresolved'):
        wheel_geometry(manifest)


@pytest.mark.parametrize('text', [
    'a: 1\na: 2\n',
    'a: &x 1\nb: *x\n',
    'a: !!str value\n',
    'a: 2026-10-25\n',
    '<<: {a: 1}\n',
    '1: value\n',
    'a: .nan\n',
])
def test_strict_yaml_rejects_ambiguous_or_non_json_inputs(tmp_path, text):
    p = tmp_path / 'bad.yaml'
    p.write_text(text)
    with pytest.raises(HardwareConfigError):
        load_manifest(p)


def test_rfc8785_number_formatting_and_unicode_vector():
    vector = {'unicode': 'é', 'small': 1e-6, 'large': 1e+21, 'negative_zero': -0.0}
    canonical = rfc8785.dumps(vector)
    assert canonical == '{"large":1e+21,"negative_zero":0,"small":0.000001,"unicode":"é"}'.encode()
    # Python json.dumps formats this vector differently, so cannot replace JCS.
    assert json.dumps(vector, ensure_ascii=False, sort_keys=True).encode() != canonical
