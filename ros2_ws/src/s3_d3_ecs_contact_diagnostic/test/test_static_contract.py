#!/usr/bin/env python3
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
files = list((root / "src").glob("*.cc")) + list((root / "include").rglob("*.hh"))
text = "\n".join(path.read_text(encoding="utf-8") for path in files)
for forbidden in ("rclcpp", "ros_gz", "/cmd_vel", "ContactSensorData", "ISystemPreUpdate", "ISystemUpdate", "RequestRaw", "WorldPoseCmd", "CreateEntity", "RemoveEntity", ".kill(", "SIGTERM", "SIGKILL", "retry", "AdvertiseService"):
    assert forbidden not in text, forbidden
assert "ISystemPostUpdate" in text
assert "const gz::sim::EntityComponentManager" in text
assert text.count("publisher_.Publish(") == 1
assert "SubscribeRaw" in text
assert "descriptor()->full_name()" in text
assert "Subscribe<EcsContactSensorDiagnosticReceipt>" not in text
assert "RENAME_NOREPLACE" in text and "SYS_renameat2" in text
assert "errno == EINTR" in text
assert "--runtime-collector" in text
print("static_contract_pass")
