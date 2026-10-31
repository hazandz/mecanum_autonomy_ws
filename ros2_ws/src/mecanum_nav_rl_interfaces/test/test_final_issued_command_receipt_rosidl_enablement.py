"""Offline structural tests for the receipt ROSIDL build-interface change."""

import hashlib
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parents[2]
RECEIPT_PATH = PACKAGE_ROOT / "msg" / "FinalIssuedCommandReceipt.msg"
EVIDENCE_PATH = (
    REPOSITORY_ROOT
    / "docs/governance/evidence/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_EVIDENCE.json"
)
REGISTRY_PATH = REPOSITORY_ROOT / "docs/governance/CANONICAL_SOURCE_REGISTRY.md"
EXPECTED_RECEIPT_SHA256 = (
    "bc8bfd11960079271b78ddfe2b3c3dbf0204959d6dcef44fa8565b6a6384fa0c"
)
HISTORICAL_RECEIPT_SHA256 = (
    "0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a"
)
# Live ROSIDL inventory for package version 2.7.0.
EXPECTED_LIVE_INTERFACE_FILES = [
    "msg/Heartbeat.msg",
    "msg/SafetyState.msg",
    "msg/NavigationState.msg",
    "msg/CommandEnvelope.msg",
    "msg/FinalIssuedCommandReceipt.msg",
    "msg/SafetyLifecycleState.msg",
    'msg/LocalTrainingSafetyInput.msg',
    'msg/SimulationContactState.msg',
]
EXPECTED_LIVE_SERVICE_FILES = ['srv/LocalTrainingBackendControl.srv']
# This list belongs to the immutable historical WP-06 evidence packet.
EXPECTED_ALLOWLIST = [
    "ros2_ws/src/mecanum_nav_rl_interfaces/CMakeLists.txt",
    "ros2_ws/src/mecanum_nav_rl_interfaces/package.xml",
    "ros2_ws/src/mecanum_nav_rl_interfaces/CHANGELOG.md",
    "ros2_ws/src/mecanum_nav_rl_interfaces/test/test_interface_contracts.py",
    "ros2_ws/src/mecanum_nav_rl_interfaces/test/test_final_issued_command_receipt_rosidl_enablement.py",
    "docs/governance/decisions/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_DECISION.md",
    "docs/governance/evidence/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_EVIDENCE.json",
    "docs/governance/CANONICAL_SOURCE_REGISTRY.md",
    "docs/governance/PROJECT_EXECUTION_PLAN.md",
    "docs/governance/PROJECT_PROGRESS_LEDGER.md",
]


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, f"duplicate JSON key: {key}"
        result[key] = value
    return result


def test_receipt_hash_and_rosidl_interface_list_are_exact() -> None:
    raw = RECEIPT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_RECEIPT_SHA256
    cmake = (PACKAGE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    generation = re.search(
        r"rosidl_generate_interfaces\(\$\{PROJECT_NAME\}(.*?)\n\)",
        cmake,
        re.DOTALL,
    )
    assert generation is not None
    interfaces = re.findall(r'"(msg/[^"\n]+\.msg)"', generation.group(1))
    services = re.findall(r'"(srv/[^"\n]+\.srv)"', generation.group(1))
    assert len(interfaces) == len(set(interfaces))
    assert len(services) == len(set(services))
    assert interfaces == EXPECTED_LIVE_INTERFACE_FILES
    assert services == EXPECTED_LIVE_SERVICE_FILES
    assert cmake.count('"msg/FinalIssuedCommandReceipt.msg"') == 1
    assert cmake.count('"srv/LocalTrainingBackendControl.srv"') == 1
    assert "ament_add_pytest_test(test_final_issued_command_receipt_rosidl_enablement" in cmake


def test_version_and_no_runtime_executable_or_library() -> None:
    package = ET.parse(PACKAGE_ROOT / "package.xml").getroot()
    assert package.findtext('version') == '2.7.0'
    cmake = (PACKAGE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "add_executable(" not in cmake
    assert "add_library(" not in cmake


def test_atomic_l2_packet_is_routed_by_registry_without_runtime_claim() -> None:
    raw = EVIDENCE_PATH.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    assert not text.endswith("\n")
    data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert raw == canonical
    assert set(data) == {
        "authority_fingerprints",
        "candidate_lifecycle",
        "future_state_after_exact_integration",
        "historical_annotation_disposition",
        "implementation_allowlist",
        "non_goals",
        "receipt_contract",
        "schema_id",
        "schema_revision",
    }
    assert data["schema_id"] == "mecanum_wp06_receipt_v2_rosidl_enablement_atomic_evidence/v1"
    assert data["schema_revision"] == 1
    assert data["authority_fingerprints"]["base_commit"] == "c8b178a2f1feee115a3a01553afaec616cabf737"
    assert data["authority_fingerprints"]["architecture"]["sha256"] == "432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204"
    assert data["authority_fingerprints"]["canonical_source_registry"]["sha256"] == "91d0fd7864f8e18012b5e0b91d41bfbcacedba97e6232cc06e8e390ead90bc74"
    assert data["authority_fingerprints"]["project_execution_plan"]["sha256"] == "d05edf287000093d7b61346b01e2f72197216df5d5caa73ea52c627f26017b52"
    assert data["authority_fingerprints"]["project_progress_ledger"]["sha256"] == "3dcffb51f355090aa6eb0ad71aa6e956f03011cc0afa01a1ea8402a0961b028b"
    assert data["receipt_contract"]["interface_id"] == "mecanum.final-issued-receipt/v2"
    assert data["receipt_contract"]["schema_revision"] == 2
    assert data["receipt_contract"]["source_sha256"] == HISTORICAL_RECEIPT_SHA256
    assert data["receipt_contract"]["dependency_closure_sha256"] == "0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73"
    assert data["receipt_contract"]["qos6_document_sha256"] == "4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022"
    assert data["receipt_contract"]["qos6_transport_manifest_sha256"] == "338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620"
    assert data["implementation_allowlist"] == EXPECTED_ALLOWLIST
    assert data["historical_annotation_disposition"]["annotations"][1]["post_integration_scope"] == "SUPERSEDED_ONLY_FOR_ROSIDL_BUILD_GENERATION"
    assert data["future_state_after_exact_integration"]["WP06_RECEIPT_V2_ROSIDL_GENERATION"] == "IMPLEMENTED_OFFLINE_BUILD_INTERFACE_ONLY"
    assert data["future_state_after_exact_integration"]["RUNTIME_APPROVED"] == "NOT_APPROVED"
    assert "RUNTIME_AUTHORIZATION" in data["non_goals"]
    assert data["candidate_lifecycle"]["pre_integration_status"] == "REVIEW_CANDIDATE_ONLY"
    registry = REGISTRY_PATH.read_text(encoding="utf-8")
    assert EXPECTED_RECEIPT_SHA256 in registry
    assert "WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_DECISION.md" in registry
    assert "IMPLEMENTED_OFFLINE_BUILD_INTERFACE_ONLY" in registry
    assert "/mecanum/final_issued_command" in registry
    decision = (
        REPOSITORY_ROOT
        / "docs/governance/decisions/WP-06_RECEIPT_V2_ROSIDL_ENABLEMENT_ATOMIC_L2_DECISION.md"
    ).read_text(encoding="utf-8")
    assert "L2_PUBLIC_INTERFACE_BUILD_ENABLEMENT_AND_HISTORICAL_STATUS_SUPERSESSION" in decision
    assert "does not downgrade the already established canonical receipt v2" in decision
    assert "no implementation or runtime authorization" in decision
    assert "RUNTIME_APPROVED: NOT_APPROVED" in decision
