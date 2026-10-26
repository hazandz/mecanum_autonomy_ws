"""Sinh cấu hình giao tiếp Pi/STM32 từ hardware manifest đã khóa."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import rfc8785
import yaml
from yaml.tokens import AliasToken, AnchorToken, TagToken


DOMAIN = b"mecanum_hardware_config_hash/v1\x00"
EXPECTED_PROFILE = "mecanum_f411_tb6612_ga25_370_rev_a"
EXPECTED_WHEEL_ORDER = ["FL", "FR", "RL", "RR"]


class HardwareConfigError(ValueError):
    """Manifest đầu vào không phải mapping JSON nghiêm ngặt được hỗ trợ."""


class _StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader: _StrictLoader, node: yaml.MappingNode, deep: bool = False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise HardwareConfigError("manifest keys must be strings")
        if key == "<<":
            raise HardwareConfigError("YAML merge keys are not supported")
        if key in result:
            raise HardwareConfigError(f"duplicate manifest key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictLoader.add_constructor("tag:yaml.org,2002:map", _mapping)


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise HardwareConfigError(f"non-finite number at {path}")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _validate_json_value(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise HardwareConfigError(f"non-string mapping key at {path}")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise HardwareConfigError(f"non-JSON YAML value at {path}: {type(value).__name__}")


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Đọc một lần, phân tích một mapping và từ chối YAML có tham chiếu gián tiếp."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        for token in yaml.scan(text):
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise HardwareConfigError("YAML tags, anchors, and aliases are not supported")
        loader = _StrictLoader(text)
        try:
            value = loader.get_single_data()
        finally:
            loader.dispose()
    except HardwareConfigError:
        raise
    except yaml.YAMLError as exc:
        raise HardwareConfigError(f"invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise HardwareConfigError("manifest root must be a mapping")
    _validate_json_value(value)
    return value


def communication_config_valid(manifest: dict[str, Any]) -> bool:
    """Chỉ kiểm tra UART/profile được hỗ trợ, không xác nhận chuyển động."""
    uart = manifest.get("uart")
    return bool(
        manifest.get("schema_version") == "mecanum_hardware_manifest/v1"
        and manifest.get("hardware_profile_id") == EXPECTED_PROFILE
        and manifest.get("wheel_order") == EXPECTED_WHEEL_ORDER
        and isinstance(uart, dict)
        and uart.get("electrical_level") == "3v3_ttl"
        and uart.get("protocol_version") == 1
        and uart.get("stm32_tx") == {"port": "A", "pin": 11, "peripheral": "USART6_TX"}
        and uart.get("stm32_rx") == {"port": "A", "pin": 12, "peripheral": "USART6_RX"}
        and uart.get("shared_ground_required") is True
        and manifest.get("hash_contract") == {
            "canonicalization": "RFC8785_JCS_UTF8",
            "digest": "SHA-256",
            "domain_separator": "mecanum_hardware_config_hash/v1",
        }
    )


def wheel_geometry(manifest: dict[str, Any], require_signs: bool = True) -> dict[str, Any]:
    """Return geometry only when all wheel signs are explicitly resolved."""
    try:
        kin = manifest["kinematics"]
        enc = manifest["encoders"]
        signs = manifest["wheel_sign_mapping"]
        values = {
            "wheel_diameter_m": kin["wheel_diameter_m"]["value"],
            "wheel_radius_m": kin["wheel_radius_m"]["value"],
            "wheelbase_m": kin["wheelbase_m"]["value"],
            "track_m": kin["track_m"]["value"],
            "ticks_per_wheel_revolution": enc["ticks_per_wheel_revolution"]["value"],
        }
        resolved_signs = [signs[name]["encoder_tick_sign"]["value"]
                          for name in EXPECTED_WHEEL_ORDER]
    except (KeyError, TypeError) as exc:
        raise HardwareConfigError("manifest lacks wheel geometry/sign fields") from exc
    if any(type(value) not in (int, float) for value in values.values()):
        raise HardwareConfigError("wheel geometry is unresolved")
    signs_valid = all(type(sign) is int and sign in (-1, 1) for sign in resolved_signs)
    if require_signs and not signs_valid:
        raise HardwareConfigError("wheel encoder signs are unresolved")
    if any(value <= 0 for value in values.values()):
        raise HardwareConfigError("wheel geometry must be positive")
    if abs(values["wheel_radius_m"] * 2.0 - values["wheel_diameter_m"]) > 1e-12:
        raise HardwareConfigError("wheel radius does not match diameter")
    return {**values, "encoder_tick_signs": resolved_signs if signs_valid else None,
            "rotational_lever_arm_m": (values["wheelbase_m"] + values["track_m"]) / 2.0}


def manifest_digest(manifest: dict[str, Any]) -> bytes:
    try:
        return hashlib.sha256(DOMAIN + rfc8785.dumps(manifest)).digest()
    except (TypeError, ValueError, rfc8785.CanonicalizationError) as exc:
        raise HardwareConfigError(f"RFC8785 cannot represent the manifest: {exc}") from exc


def render_header(digest: bytes, valid: bool) -> str:
    values = ", ".join(f"0x{byte:02X}U" for byte in digest)
    return (
        "#ifndef GENERATED_HARDWARE_CONFIG_H\n#define GENERATED_HARDWARE_CONFIG_H\n"
        "#include <stdint.h>\n"
        f"#define MECANUM_COMMUNICATION_CONFIG_VALID {1 if valid else 0}U\n"
        "static const uint8_t mecanum_hardware_config_hash[32] = { "
        f"{values} }};\n"
        "#endif\n"
    )


def generate(manifest_path: str | Path, header_path: str | Path, json_path: str | Path) -> str:
    manifest = load_manifest(manifest_path)
    valid = communication_config_valid(manifest)
    if not valid:
        raise HardwareConfigError("manifest communication identity is unsupported")
    digest = manifest_digest(manifest)
    profile = {
        "hardware_profile_id": manifest["hardware_profile_id"],
        "firmware_hardware_configuration_version": manifest.get("firmware_hardware_configuration_version"),
        "hardware_config_hash_hex": digest.hex(),
        "communication_config_valid": True,
        "wheel_order": manifest["wheel_order"],
        "protocol_version": manifest["uart"]["protocol_version"],
        "hash_contract": manifest["hash_contract"],
        "wheel_geometry": wheel_geometry(manifest, require_signs=False),
    }
    header = Path(header_path)
    metadata = Path(json_path)
    header.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    header.write_text(render_header(digest, valid), encoding="utf-8")
    metadata.write_bytes(rfc8785.dumps(profile) + b"\n")
    return digest.hex()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--header", required=True)
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    try:
        digest = generate(args.manifest, args.header, args.json)
    except (OSError, HardwareConfigError) as exc:
        parser.error(str(exc))
    print(digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
