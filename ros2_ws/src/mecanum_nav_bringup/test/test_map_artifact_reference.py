from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__PROFILE_RESOLVED_ARTIFACT_YAML_REQUIRED__"


def test_map_server_requires_profile_resolved_artifact_binding():
    config_path = ROOT / "config/navigation/nav2_baseline.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    server = config["map_server"]["ros__parameters"]
    assert server == {
        "use_sim_time": True,
        "frame_id": "map",
        "topic_name": "/map",
        "yaml_filename": MARKER,
    }
    text = config_path.read_text(encoding="utf-8")
    assert "warehouse_map2" not in text
    assert "map_content_hash" not in text
    assert "approval" not in text.lower()
    assert not any(line.strip().startswith("yaml_filename:") and line.split(":", 1)[1].strip().startswith("/") for line in text.splitlines())
    assert "ros2_ws/src/" not in text and "artifacts/maps/" not in text
