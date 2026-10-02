# Candidate B Tool Repair Validation Report

## Scope and immutable evidence

This is an offline-only repair validation. The completed invalid run
`run-candidate-b-20260925T140736Z-01` was not edited: its raw logs, metadata,
report, and status remain unchanged.

The root cause was the missing `import sys` in
`tools/candidate_b_collector.py`. Python therefore raised
`NameError: name 'sys' is not defined` while resolving `sys.exit(main())`,
before `main()`, `rclpy.init()`, graph preflight, ROS subscriptions, client
creation, or any pose request.

## Files changed

| File | Change |
| --- | --- |
| `tools/candidate_b_collector.py` | Adds `import sys` and an `--offline-bootstrap-self-test` mode. |
| `tools/run_candidate_b_controlled_suitability.py` | Replaces force-kill fallback with SIGINT-only process-group shutdown plus an on-disk `SHUTDOWN_INCOMPLETE` blocker. |
| `repair_validation/collector_help.txt` | Captured offline `--help` output. |
| `repair_validation/offline_bootstrap_self_test.json` | Captured self-test result. |
| `repair_validation/validation_exit_codes.txt` | Captured command exit codes. |
| `repair_validation/Tool_Repair_Validation_Report.md` | This report. |

## Offline bootstrap contract

The collector self-test parses the immutable Candidate B manifest, checks the
entity, bridge literal, permitted stream list, and all six immutable probe
literals/order. It returns before `rclpy.init()`, creates no publisher, no
service/action client, and spawns no process.

## Validation commands and recorded results

| Command | Exit code | Result |
| --- | ---: | --- |
| `python3 -m py_compile tools/candidate_b_collector.py tools/run_candidate_b_controlled_suitability.py tools/analyze_candidate_b.py` | 0 | PASS |
| `python3 tools/candidate_b_collector.py --help` | 0 | PASS |
| `python3 tools/candidate_b_collector.py --offline-bootstrap-self-test` | 0 | PASS |
| Source scan for `.kill(`, `SIGKILL`, `kill -9`, or `SIGTERM` in replacement supervisor | 0 (no match) | PASS |

The captured self-test states `rclpy_initialized=false`,
`publishers_created=0`, `clients_created=0`, and
`processes_spawned=0`. No Gazebo, bridge, ROS service, pose request, command
publisher, or external process was started by this validation.

## Replacement shutdown policy

The repaired supervisor now uses a separate process group for each
measurement-created Gazebo/bridge process and sends only SIGINT to that group.

```text
SIGINT to measurement-created process group
→ bounded graceful wait
→ if still alive: SHUTDOWN_INCOMPLETE
→ write blocker in artifact root
→ block all replacement runs
→ require separate user/operator decision
```

There is no automatic SIGTERM, SIGKILL, `.kill()`, or equivalent fallback.
This remediation does not alter the old run, whose force-killed bridge remains
an immutable shutdown anomaly in its existing evidence.

## Remaining gate

The tooling is repaired only offline. A new approval packet is required before
any replacement run may launch Gazebo, create the temporary bridge, or send the
six Candidate B requests. This report grants no runtime, reset, collision,
scenario, oracle, reward, Gym/SB3, firmware, or hardware approval.

