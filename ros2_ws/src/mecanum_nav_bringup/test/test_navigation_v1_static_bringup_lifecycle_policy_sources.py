"""Offline checks for fail-closed, non-executable Navigation V1 policy sources."""

from pathlib import Path
import re


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PACKAGE_ROOT / "config"
POLICY_FILES = (
    "navigation_v1_namespace_remap_policy.static.yaml",
    "navigation_v1_lifecycle_startup_policy.static.yaml",
    "navigation_v1_health_gate_policy.static.yaml",
)
REQUIRED_SOURCE_ROLES = (
    "nav2_lifecycle_bringup",
    "map_server",
    "amcl_omni",
    "robot_localization_ekf",
    "robot_state_publisher",
    "tf_ownership",
    "scan_adapter",
    "map_artifact_binding",
    "remap_namespace_policy",
    "lifecycle_startup_policy",
)
PENDING = "PENDING_IMPLEMENTATION_SOURCE_PIN"
FORBIDDEN_CONFIG_KEYS = re.compile(
    r"^\s*(?:namespace|remap|remaps|package_path|node_name|config_path|"
    r"source_sha256|timeout|startup_order|lifecycle_transition)\s*:",
    re.MULTILINE,
)
RUNTIME_GRAPH_PATTERNS = re.compile(
    r"(?:^\s*(?:from\s+(?:rclpy|launch|launch_ros)|import\s+(?:rclpy|launch|launch_ros))\b|"
    r"\b(?:create_node|create_publisher|create_subscription|TransformBroadcaster|"
    r"LifecycleNode)\s*\()",
    re.MULTILINE,
)


def _policy_texts():
    return {
        name: (CONFIG_ROOT / name).read_text(encoding="utf-8")
        for name in POLICY_FILES
    }


def test_three_policy_sources_exist_and_are_static_non_executable():
    texts = _policy_texts()
    assert set(texts) == set(POLICY_FILES)
    for text in texts.values():
        assert "classification: STATIC_TEMPLATE_ONLY" in text
        assert "runtime_eligible: false" in text
        assert "runtime_graph_creation: FORBIDDEN" in text


def test_all_workspace_source_roles_remain_pending_in_each_policy():
    for text in _policy_texts().values():
        for role in REQUIRED_SOURCE_ROLES:
            assert re.search(
                rf"^  {re.escape(role)}: {PENDING}$", text, re.MULTILINE
            )
        assert PENDING in text


def test_fail_closed_activation_requires_source_and_evidence():
    namespace_policy = _policy_texts()[POLICY_FILES[0]]
    lifecycle_policy = _policy_texts()[POLICY_FILES[1]]
    health_policy = _policy_texts()[POLICY_FILES[2]]
    assert "missing_or_unverified_source_pin: NAV2_ACTIVATION_FORBIDDEN" in namespace_policy
    assert "missing_namespace_remap_policy: NAV2_ACTIVATION_FORBIDDEN" in namespace_policy
    assert "missing_lifecycle_evidence: NAV2_ACTIVATION_FORBIDDEN" in lifecycle_policy
    assert "missing_health_gate_evidence: NAV2_ACTIVATION_FORBIDDEN" in health_policy
    assert "pending_marker_present: NAV2_ACTIVATION_FORBIDDEN" in "".join(
        (namespace_policy, lifecycle_policy, health_policy)
    )


def test_no_concrete_runtime_defaults_profile_or_workspace_lock_are_introduced():
    combined = "\n".join(_policy_texts().values())
    assert not FORBIDDEN_CONFIG_KEYS.search(combined)
    assert "ResolvedConfig" not in combined
    assert "config_hash" not in combined
    assert "resolved_profile" not in combined
    assert "workspace_source_locks" not in combined
    assert "map_approval" not in combined
    assert "map_content_hash" not in combined


def test_policy_sources_do_not_create_ros_runtime_graph():
    for text in _policy_texts().values():
        assert not RUNTIME_GRAPH_PATTERNS.search(text)
