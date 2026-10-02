# S3 Passive Stream Timing Evidence

This directory contains only externally run passive evidence tooling and outputs
approved by Phase S3.2.0C. It is not a ROS package and must never be imported
by production code.

The collector observes only /clock, /ground_truth/odom, /odom, /scan, and /tf.
It has no publisher, service client, action client, policy, reset, or
simulator-control capability. It does not touch UART or hardware.

A pre-capture /cmd_vel publisher snapshot is frozen for each run. A pre-existing
two-way ros_gz_bridge publisher is permitted only if present in that actual
snapshot. The collector never publishes a command; a new publisher outside the
frozen allowlist invalidates the run.

The analyzer reads only JSON and JSONL artifacts. It never initializes ROS.

Generated report labels are OBSERVED, CANDIDATE_FOR_FUTURE_DECISION,
PROPOSED_FROM_MEASUREMENT, and NOT_ESTABLISHED.

Idle timing evidence cannot establish a TaskOracle, ContactLatch, task goal or
bounds, collision, STUCK, D6 limit, reward, termination, Gym behavior, or
real-robot behavior.
