#!/bin/bash
set -e
exec 9>/home/hazan/.local/state/ros2_nav2_drl/b22-simulation-runtime.lock
flock -n 9
source /opt/ros/jazzy/setup.bash
source /home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/install/setup.bash
set +e
/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python -B /home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/runtime-snapshot/artifacts/simulation/roadmap_b_b2/gui_verification/tools/observation_runner.py --evidence /home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl --run-id B22_CONTACT_QUERY_CACHE_VERIFY_001 --install /home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/install --source-commit a95463dbe265355e12bf891937e080e95f8b58d0 --authority 'Owner authorized B2.2 cached QUERY corrective: Codex packet review, fresh capacity-one contact and GUI confirmation; no B2.3 or hardware' --profile /home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/contact-001-profile.json --profile-sha256 85f5d844864ffde80b07f63e1be818c1346634c37cd6c76b42a2573dd3ce29c5
B22_PY_EXIT=$?
printf "%s\n" "$B22_PY_EXIT" >/home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/contact-001-python.exit
B22_WRITE_EXIT=$?
printf "%s\n" "$B22_WRITE_EXIT" >/home/hazan/mecanum_runtime_evidence/B22_QUERY_CACHE_20261107.a_pjcuyl/contact-001-writer.exit
if [ "$B22_PY_EXIT" -ne 0 ]; then exit "$B22_PY_EXIT"; fi
exit "$B22_WRITE_EXIT"
