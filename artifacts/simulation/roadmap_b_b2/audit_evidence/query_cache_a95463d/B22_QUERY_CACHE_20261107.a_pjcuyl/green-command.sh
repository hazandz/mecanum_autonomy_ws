#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
root=$(cat /tmp/b22-query-cache-current-root)
source "$root/install/setup.bash"
for name in test_backend_invariants test_receipt_gate test_contact_coverage test_heartbeat_trace; do
 set +e
 timeout --kill-after=1s 45s "$root/build/mecanum_sim_backend/$name" --gtest_output="xml:$root/green-$name.xml" > "$root/green-$name.stdout" 2> "$root/green-$name.stderr"
 rc=$?
 printf '%s\n' "$rc" > "$root/green-$name.exit"
 set -e
 if [ "$rc" -ne 0 ]; then exit "$rc"; fi
done
export MECANUM_ROBOT_DESCRIPTION_INSTALL_BASE="$root/install"
export PYTHONPATH="$root/snapshot/ros2_ws/src/mecanum_nav_rl:$root/snapshot/ros2_ws/src/mecanum_nav_bringup:$PYTHONPATH"
export PYTHONPYCACHEPREFIX="$root/pycache"
set +e
timeout --kill-after=1s 45s /home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python -m pytest -q -o "cache_dir=$root/pytest-cache" --junitxml="$root/green-python.xml" "$root/snapshot/ros2_ws/src/mecanum_nav_rl/test/test_b2_training_asset_binding.py" "$root/snapshot/ros2_ws/src/ROBOT_URDF_final_description/test/test_b2_training_assets.py" "$root/snapshot/ros2_ws/src/mecanum_nav_bringup/test/test_local_training_launch.py" "$root/snapshot/artifacts/simulation/roadmap_b_b2/gui_verification/tools/test_observation_runner.py" > "$root/green-python.stdout" 2> "$root/green-python.stderr"
rc=$?
printf '%s\n' "$rc" > "$root/green-python.exit"
exit "$rc"
