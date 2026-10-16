"""Offline checks for the additive receipt ROSIDL declaration."""

import hashlib
import re
from pathlib import Path
import xml.etree.ElementTree as ET


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = PACKAGE_ROOT / "msg" / "FinalIssuedCommandReceipt.msg"
EXPECTED_SHA256 = "0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a"
EXPECTED_CONSTANTS = [
    "uint8 SOURCE_UNKNOWN=0",
    "uint8 SOURCE_POLICY=1",
    "uint8 SOURCE_NAV2=2",
    "uint8 SOURCE_TELEOP=3",
    "uint8 SOURCE_SAFE_STOP=4",
]
EXPECTED_FIELDS = [
    "std_msgs/Header header",
    "uint64 episode_generation",
    "uint32 reset_epoch",
    "uint32 runtime_generation",
    "uint64 step_index",
    "string<=36 transition_id",
    "uint8 source",
    "uint64 sequence",
    "uint64 source_instance_id",
    "uint64 final_publisher_instance_id",
    "uint64 final_publish_sequence",
    "geometry_msgs/Twist final_command",
]


def test_receipt_schema_hash_and_ordered_contract_are_pinned() -> None:
    raw = RECEIPT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    lines = raw.decode("utf-8").splitlines()
    contract_lines = [line for line in lines if line and not line.startswith("#")]
    assert contract_lines == EXPECTED_CONSTANTS + EXPECTED_FIELDS


def test_cmake_generates_exact_five_interfaces_and_registers_offline_test() -> None:
    cmake = (PACKAGE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(
        r"rosidl_generate_interfaces\(\$\{PROJECT_NAME\}(.*?)\n\)",
        cmake,
        re.DOTALL,
    )
    assert match is not None
    interface_entries = re.findall(r'"(msg/[^"\n]+\.msg)"', match.group(1))
    assert interface_entries == [
        "msg/Heartbeat.msg",
        "msg/SafetyState.msg",
        "msg/NavigationState.msg",
        "msg/CommandEnvelope.msg",
        "msg/FinalIssuedCommandReceipt.msg",
    ]
    assert cmake.count('"msg/FinalIssuedCommandReceipt.msg"') == 1
    assert "ament_add_pytest_test(test_final_issued_command_receipt_rosidl_enablement" in cmake
    assert "test/test_final_issued_command_receipt_rosidl_enablement.py" in cmake
    assert "add_executable(" not in cmake
    assert "add_library(" not in cmake


def test_package_version_and_scope_are_interface_only() -> None:
    package = ET.parse(PACKAGE_ROOT / "package.xml").getroot()
    assert package.findtext("version") == "2.5.0"
    changelog = (PACKAGE_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a" in changelog
    assert "/mecanum/final_issued_command" in changelog
    assert "does not create a publisher" in changelog
    assert "does not" in changelog and "runtime QoS" in changelog
