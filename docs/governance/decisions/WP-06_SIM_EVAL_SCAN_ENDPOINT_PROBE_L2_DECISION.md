# WP06 sim_eval Scan endpoint probe — L2 source candidate

## Classification and lifecycle

- Classification: `L2_SIM_EVAL_SCAN_ENDPOINT_PROBE_SOURCE_IMPLEMENTATION`.
- Exact source base: `46be7a2bde222475fbaaaac8a6749211edfd2ba0`.
- Review branch: `wp06-sim-eval-scan-endpoint-probe-46be7a2`.
- Evidence ceiling: `IMPLEMENTED_OFFLINE_BUILD_AND_TEST_ONLY`.
- This candidate adds an inert-on-import command-line probe source, static descriptor, offline fake-runner tests and governance records. The probe is not executed in this candidate.

## Source and discovery boundary

The static sensor source declares `<topic>scan</topic>`, which is a relative sensor topic and is not a full Gazebo Transport endpoint. The probe source, when separately executed in a future approved run, is constrained to `gz topic -l` followed by `gz topic -i -t <absolute-topic>` for every discovered topic, selecting only an exact `gz.msgs.LaserScan` type token. It does not select by topic name, suffix, frame, world, model or sensor name. Any reported topic is `OBSERVED_NOT_PINNED`; no endpoint is persisted or pinned.

This candidate does not execute the probe, `gz`, ROS, Gazebo, bridge or launch. A future probe run requires a separate capacity-one `APPROVED_RUNTIME` packet specifying the exact command, pass/fail criteria and stop conditions, plus explicit User approval. Any observation requires a separate Owner decision before WP06-6E. WP06-6E remains the sole owner of canonical ROS–Gazebo bridge implementation.

## Boundaries and status

No endpoint pin, bridge configuration/implementation, ROS `/scan` publisher, TF, cadence/latency/frame validation, profile resolution, runtime evidence or runtime authorization is created. The legacy `/clock` bridge remains clock-only. The WP05 static profile pin reconciliation and LiDAR source are not modified.

WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; Gate A remains `PASSED`; Gate B remains `NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED`. No Gate B transition is claimed.

## Allowlist

The exact nine candidate paths and authority fingerprints are recorded in the accompanying evidence JSON. It contains no probe result or endpoint observation.
