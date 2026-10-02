# S3 D3 Approval-Bound Guard Validation Report

## Scope

This is an offline-only S3.3.16 repair record. No Gazebo, ROS node, bridge, collector, publisher, service/action client, command, or hardware operation was started.

## Defect addressed

The earlier supervisor used the generic file `replacement_run_consumed.json` as a global stop condition. That immutable S3.3.12 record correctly preserved a consumed invalid run, but incorrectly blocked the separately approved S3.3.15 authority before it could be evaluated.

## Approval-bound guard

The artifact-owned supervisor now uses an approval-specific guard:

| Field | Bound value |
| --- | --- |
| Approval ID | `S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN` |
| Authority packet | `docs/S3_D3_Post_Repair_Passive_Contact_Run_Approval_Packet_DRAFT.md` |
| Packet SHA-256 | `5d7229a67a859bdd3f13e221ec5813b9fc6c275ba916be9040a51f4c53f6ea91` |
| World | `world_demo` |
| World SHA-256 | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Capacity | `1` |
| Initial state | `authorized_not_consumed` |

The separate record validates approval ID, authority packet path/hash, world identity/hash, collision, sensor, topics, types, bridge literal/direction, and capacity. It uses an exclusive lock directory and same-directory temporary-file plus `os.replace` for consumption. Missing, malformed, mismatched, locked, already-consumed, or atomic-write-failed state is fail-closed.

## Offline validation commands and results

| Command | Exit | Result |
| --- | --- | --- |
| `python3 -m py_compile ...approval_bound_guard.py ...run_contact_replacement_evidence.py` | `0` | PASS |
| `run_contact_replacement_evidence.py --offline-preflight-self-test` | `0` | PASS |
| `run_contact_replacement_evidence.py --offline-approval-guard-self-test` | `0` | PASS (final run, including world-hash mismatch) |
| `--initialize-s3-3-15-approval-guard` | `0` | PASS; creates only the non-consumed S3.3.15 authorization record. |

The parser self-test continues to pass current single-quoted SDF, equivalent double-quoted SDF, wrong/missing name, malformed XML, multiple worlds, and distinct world-name/Xacro stage mapping.

The approval-bound guard self-test passes: old consumed record unchanged; different approval ID is not blocked; one acquire/consume only; second acquire rejected; packet hash mismatch rejected; world-hash mismatch rejected; literal mismatch rejected; malformed record rejected; lock failure rejected; atomic-write failure rejected. Full machine-readable outputs are [preflight parser self-test](s3_d3_preflight_parser_self_test.json), [approval-bound guard self-test](s3_d3_approval_bound_guard_self_test_final.json), and [integrity record](s3_d3_approval_bound_guard_integrity.json).

## Historical artifact preservation

`replacement_run_consumed.json` remains byte-identical:

```text
before: c6891ff53d520345a11b2471493489c4030d0a810ac3584a2bd2cd754a8236c7
after:  c6891ff53d520345a11b2471493489c4030d0a810ac3584a2bd2cd754a8236c7
```

The two prior invalid run directories and their raw reports were not changed. The new S3.3.15 record is [S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN.json](../approval_guards/S3.3.15_POST_REPAIR_PASSIVE_CONTACT_RUN.json); it has no run ID and remains `authorized_not_consumed`.

## Boundary retained

This repair does not run or consume S3.3.15. Exactly one execution authority remains, subject to its packet/hash/literal gates. It is not approval for Gazebo, bridge delivery, collision policy, ContactLatch, reward/termination, Gym/training, command publication, or hardware.
