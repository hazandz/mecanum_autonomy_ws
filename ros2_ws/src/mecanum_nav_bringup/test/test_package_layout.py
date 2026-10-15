import ast
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NEW_PACKAGE_DATA = {
    "config/state_estimation/ekf_sim.yaml",
    "config/localization/amcl_omni.yaml",
    "config/navigation/nav2_baseline.yaml",
    "config/lifecycle/navigation_v1_startup.yaml",
    "config/remaps/navigation_v1.yaml",
    "launch/navigation_v1.launch.py",
    "launch/navigation_v1_lifecycle.launch.py",
}


def test_new_sources_exist_and_are_installed_as_package_data():
    assert all((ROOT / path).is_file() for path in NEW_PACKAGE_DATA)
    package = ET.parse(ROOT / "package.xml").getroot()
    assert package.findtext("name") == "mecanum_nav_bringup"
    assert package.findtext("export/build_type") == "ament_python"
    tree = ast.parse((ROOT / "setup.py").read_text(encoding="utf-8"))
    setup_call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup")
    data_files = next(keyword.value for keyword in setup_call.keywords if keyword.arg == "data_files")
    installed = {node.value for node in ast.walk(data_files) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert NEW_PACKAGE_DATA <= installed
