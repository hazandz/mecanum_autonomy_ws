#!/usr/bin/env python3
"""Static-only audit of the controlled-measurement artifact tool boundary."""

import ast
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def calls(source: str) -> list[str]:
    tree = ast.parse(source)
    result = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            result.append(node.func.attr)
    return sorted(result)


def main() -> int:
    collector = TOOLS / "controlled_measurement_collector.py"
    supervisor = TOOLS / "run_controlled_measurement_with_bridge.py"
    collector_source = collector.read_text(encoding="utf-8")
    supervisor_source = supervisor.read_text(encoding="utf-8")
    collector_calls = calls(collector_source)
    prohibited = [name for name in ("create_publisher", "create_action_client") if name in collector_calls]
    checks = {
        "no_create_publisher": "create_publisher" not in collector_calls,
        "no_create_action_client": "create_action_client" not in collector_calls,
        "only_SetEntityPose_client_literal": 'self.create_client(SetEntityPose, POSE_SERVICE)' in collector_source,
        "only_pose_call_async_literal": 'node.pose_client.call_async(request)' in collector_source,
        "fixed_entity_literal": 'ENTITY_NAME = "ROBOT_URDF_final"' in collector_source,
        "fixed_probe_order_literal": '("P0", -4.0, -3.0, 0.1, 0.0)' in collector_source
        and '("P1", -4.0, 0.0, 0.1, 1.57079632679)' in collector_source
        and '("P2", -2.0, -3.0, 0.1, -1.57079632679)' in collector_source,
        "exact_one_bridge_argument": "BRIDGE_ARGUMENT = (" in supervisor_source and "/world/world_demo/set_pose@ros_gz_interfaces/srv/SetEntityPose@" in supervisor_source and "gz.msgs.Pose@gz.msgs.Boolean" in supervisor_source and "BRIDGE_COMMAND = [\"ros2\", \"run\", \"ros_gz_bridge\", \"parameter_bridge\", BRIDGE_ARGUMENT]" in supervisor_source,
        "no_cmd_vel_bridge_argument": '"/cmd_vel@' not in supervisor_source,
    }
    result = {
        "schema_version": "s3_controlled_measurement_tool_scope_audit/v1",
        "tool_sha256": {
            collector.name: hashlib.sha256(collector_source.encode()).hexdigest(),
            supervisor.name: hashlib.sha256(supervisor_source.encode()).hexdigest(),
        },
        "collector_call_attributes": collector_calls,
        "prohibited_call_attributes_found": prohibited,
        "checks": checks,
        "result": "PASS" if all(checks.values()) and not prohibited else "FAIL",
        "scope_note": "Static source audit only; it does not prove absence of commands from unrelated processes.",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["result"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
