#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
root=$(cat /tmp/b22-query-cache-current-root)
cd "$root/snapshot/ros2_ws"
set +e
MAKEFLAGS=-j2 colcon --log-base "$root/build-logs" build --base-paths src --packages-select mecanum_nav_rl_interfaces ROBOT_URDF_final_description mecanum_nav_rl mecanum_sim_backend mecanum_nav_bringup --build-base "$root/build" --install-base "$root/install" --merge-install --executor sequential --cmake-args -DBUILD_TESTING=ON > "$root/build.stdout" 2> "$root/build.stderr"
rc=$?
printf '%s\n' "$rc" > "$root/build.exit"
exit "$rc"
