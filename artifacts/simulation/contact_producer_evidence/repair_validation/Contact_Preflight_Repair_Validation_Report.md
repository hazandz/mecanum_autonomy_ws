# S3 D3 Contact Preflight Repair Validation Report

## Scope

This is an offline repair-validation record only. It does not launch Gazebo, a bridge, a collector, a ROS node, or any process; it does not publish `/cmd_vel`, call a service/action, or operate hardware.

## Defect and repair

The consumed run `run-contact-replacement-20260926T145616Z-01` was fail-closed because its artifact-owned supervisor counted only the literal text `<world name="world_demo">`. The current valid SDF instead uses `<world name='world_demo'>`. The old `run_result.json` therefore reported an Xacro validation reason even though its recorded Xacro/literal checks passed.

Only [`run_contact_replacement_evidence.py`](../tools/run_contact_replacement_evidence.py) was repaired. It now parses SDF/XML using `xml.etree.ElementTree` and requires:

- parseable XML with `sdf` as root;
- exactly one `world` element;
- a nonempty `name` attribute equal to `world_demo`.

Malformed XML, a wrong or missing name, and more than one world element return a structured `stage: world_name` record. Static robot-description failures are now separately recorded as `stage: xacro_validation`; future `run_result.json` records carry the stage and reason independently. World hash failures use `stage: world_sha256`.

## Offline validation

| Check | Result |
| --- | --- |
| `python3 -m py_compile` for the supervisor, collector, and analyzer | PASS |
| `--offline-preflight-self-test` exit code | PASS (`0`) |
| Current `tugbot_depot.sdf` with single-quoted `world_demo` | PASS |
| Equivalent double-quoted fixture | PASS |
| Wrong world name | PASS: reject `world_name` |
| Missing world name | PASS: reject `world_name` |
| Malformed XML | PASS: reject `world_name` |
| Multiple world elements | PASS: reject `world_name` |
| Distinct `world_name` / `xacro_validation` stage-reason mapping | PASS |

The self-test output is retained in [offline_preflight_self_test.json](offline_preflight_self_test.json), with its [exit-code record](offline_preflight_self_test.exit_code).

## Revision and immutable-run preservation

The current post-edit source-world SHA-256 remains:

```text
1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271
```

No file inside the consumed invalid run was edited. For audit reference, the current hashes of its preserved records are:

| Preserved file | SHA-256 |
| --- | --- |
| `run_result.json` | `c6891ff53d520345a11b2471493489c4030d0a810ac3584a2bd2cd754a8236c7` |
| `Contact_Producer_Evidence_Report.md` | `3308a979027a341ceee3c4dc6e080d81872710a7a0a91aae021c6e62a2a40adb` |
| `static_robot_validation.json` | `88a823bce401106549503d8b3c9bc208724972d849e9c961ea0c576e3bce302e` |

## Boundary retained

This repair does not approve a new run. It does not establish Gazebo Contact-system loading, sensor delivery, bridge behavior, ContactLatch, collision policy, reward/termination, Gym/training, command publication, or hardware readiness. A further passive run requires a **new, explicit approval packet** after this repair.
