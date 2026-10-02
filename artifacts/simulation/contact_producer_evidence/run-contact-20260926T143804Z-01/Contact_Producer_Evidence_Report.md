# S3 D3 Contact Producer Evidence Report

Run: `run-contact-20260926T143804Z-01`

Status: **INVALID — preflight fail-closed; no runtime capture**

## Scope and result

This was the one approved passive raw-contact run attempt. It stopped before launching Gazebo, the temporary bridge, or the collector because the mandatory world-file SHA-256 gate did not match.

| Preflight item | Required | Observed | Result |
| --- | --- | --- | --- |
| Gazebo world identity | `world_demo` | Static source world is `world_demo` | Not reached as a runtime preflight stage |
| World-file SHA-256 | `a5e9c9b1e9b8ad11e0399855f06de687f04c702258b8b74ce563523d78ed55fe` | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` after the approved Contact-system source edit | **FAIL** |
| Gazebo launch | Required only after all gates pass | Not started | Not applicable |
| Temporary one-service bridge | `/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts` | Not started | Not applicable |
| Passive collector | raw Contacts, `/clock`, graph metadata only | Not started | Not applicable |

The mismatch is recorded losslessly in [`preflight_failure.json`](preflight_failure.json). Adding the approved world-scope built-in Contact system necessarily changed `tugbot_depot.sdf`; this report does not substitute the new hash for the approved gate.

## Static implementation evidence

The source-level contact surface was present before the SHA gate was evaluated:

- existing `base_link` box collision is named `s3_d3_base_contact_collision`;
- exactly one `s3_d3_base_contact_sensor` targets that literal and `/s3_d3/contact/raw`;
- exactly one world-scope `gz-sim-contact-system` Contact system is declared.

The installed `parameter_bridge --help` documents `[` as Gazebo-to-ROS. The approved temporary bridge argument uses that one-way marker:

```text
/s3_d3/contact/raw@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts
```

No bridge process was started, so direction is static command-syntax evidence only, not graph/runtime delivery evidence.

## Raw-contact and identity evidence

No Gazebo process ran. Therefore:

| Evidence item | Count / state |
| --- | --- |
| `ros_gz_interfaces/msg/Contacts` payloads | `0` |
| `/clock` messages | `0` |
| Runtime graph snapshots | Not available |
| Contact header/timestamp status | Not observed |
| Entity or scoped-name evidence | Not observed |
| Duplicate or multiplicity observations | Not observed |

No absent payload may be read as absence of contact or collision.

## Control boundary and shutdown

The measurement tooling source scan found no publisher, service client, or action client in the collector/analyzer. The preflight failure occurred before any measurement-created runtime process existed:

- `/cmd_vel` publications by measurement tooling: `0`;
- simulator-control services called: `0`;
- training, teleoperation, and hardware operations: `0`;
- shutdown record: complete, with no created process group to signal.

## Retained non-claims

This invalid preflight attempt establishes neither Contact-system runtime loading, bridge delivery, timestamp population, scoped names, duplicate behavior, collision classification, ContactLatch semantics, action-interval provenance, reset semantics, reward/termination, Gym/training, nor hardware readiness.

The one-run approval is consumed. Any future attempt requires a user-approved post-edit world SHA-256 and a separate run approval; it must not be treated as a retry of this attempt.
