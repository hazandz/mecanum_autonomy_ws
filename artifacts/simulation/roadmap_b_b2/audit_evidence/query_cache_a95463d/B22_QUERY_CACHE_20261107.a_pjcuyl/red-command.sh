#!/bin/bash
set -e
source /opt/ros/jazzy/setup.bash
root=$(cat /tmp/b22-query-cache-current-root)
source /home/hazan/mecanum_runtime_evidence/B22_CONTACT_ONLY_20261107.vyuE1i/install-closure/setup.bash
set +e
MAKEFLAGS=-j2 colcon --log-base "$root/red-build-logs" build --base-paths "$root/red-snapshot/ros2_ws/src" --packages-select mecanum_sim_backend --build-base "$root/red-build" --install-base "$root/red-install" --merge-install --executor sequential --cmake-args -DBUILD_TESTING=ON > "$root/red-build.stdout" 2> "$root/red-build.stderr"
rc=$?
printf '%s\n' "$rc" > "$root/red-build.exit"
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
timeout --kill-after=1s 45s "$root/red-build/mecanum_sim_backend/test_backend_invariants" '--gtest_filter=ContactOnlyMode.CachedQueryRevokedAfter*:ContactOnlyMode.CallbackWaitingOnControlMutexSeesProofRevocation' --gtest_output="xml:$root/red.xml" > "$root/red.stdout" 2> "$root/red.stderr"
rc=$?
printf '%s\n' "$rc" > "$root/red.exit"
exit "$rc"
