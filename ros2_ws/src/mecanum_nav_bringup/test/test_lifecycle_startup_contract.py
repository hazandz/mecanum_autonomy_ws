from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STAGES = [
    "robot_description", "drivers_bridge", "EKF", "Map_Server", "AMCL",
    "healthy_LocalizationMonitor", "Planner_global_costmap", "Safety",
    "selected_controller_or_manager", "mission_acceptance",
]


def test_startup_declaration_is_disabled_and_health_gated_in_exact_order():
    config = yaml.safe_load((ROOT / "config/lifecycle/navigation_v1_startup.yaml").read_text(encoding="utf-8"))
    assert config["classification"] == "STATIC_TEMPLATE_ONLY"
    assert config["runtime_eligible"] is False
    assert config["autostart"] is False
    assert [entry["stage"] for entry in config["stages"]] == EXPECTED_STAGES
    assert all(entry["requires_previous_stage_healthy"] is True for entry in config["stages"])
    assert config["activation_policy"] == "DECLARATION_ONLY" and config["fail_closed"] is True
