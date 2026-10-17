# WP06-6E Runtime Dual-Frame Evidence Disposition — L1 decision

**Classification:** `L1_GOVERNANCE_EVIDENCE_DISPOSITION_ONLY`
**Integrated source commit:** `8bd998d6c118239d70f1d4a7b73e145795e8f921`
**Evidence scope:** `SCAN_BRIDGE_RUNTIME_SCOPE_ONLY`
**Runtime evidence:** `/home/hazan/wp06_runtime_evidence/WP06_6E_ROS_GAZEBO_SCAN_BRIDGE_RUNTIME_RUN_003`

## Disposition

The independent raw-evidence audit for Run 003 returned
`WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_EVIDENCE_AUDIT_PASS`. Raw artifact hashes were recalculated against the audit references. Independent parsing of
the ROS transcripts confirmed `/scan` as `sensor_msgs/msg/LaserScan`, one data
publisher, bridge-node publications limited to `/scan`, `/parameter_events`,
and `/rosout`, no forbidden odometry/command/TF/map publications,
`header.frame_id == lidar_frame`, and 129 non-empty `ranges` values. Bootstrap
and bridge teardown evidence showed clean groups with no live or zombie process
members.

The original `run_record.json` retains its historical terminal outcome
`WP06_6E_RUNTIME_DUAL_FRAME_CONTRACT_FAIL_NO_RETRY`. Its parser failed to handle
the multi-document YAML scan sample and bridge node-info indentation; that
record is not rewritten. Its embedded self-hash is not a trust anchor. The
independently rehashed raw transcripts are the acceptance evidence. The
reconciliation addendum records an interpretation and does not replace or
mutate any raw transcript. Run 003 was not replayed. Run 001 and Run 002 remain
historical failures and are unchanged.

## Evidence boundary

This disposition establishes only the audited WP06-6E scan-bridge runtime
scope. It does not validate the full navigation profile, Nav2, AMCL, EKF, map,
localization, or navigation readiness. No endpoint-address pin, TF evidence,
profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B transition, or
runtime approval is created. Current status is
`WP06_6E_SCAN_BRIDGE_RUNTIME_OBSERVED_AND_AUDITED_PASS`;
`RUNTIME_APPROVED: NOT_APPROVED`; `GATE_B: NOT_STARTED`.

This is an L1 governance/evidence disposition candidate. It does not alter
source or runtime artifacts and does not authorize another runtime.
