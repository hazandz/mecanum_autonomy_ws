# S3 D3 Durable Evidence Option 1 Offline Validation

Status: `OFFLINE VALIDATION COMPLETE — RUNTIME NOT APPROVED`

## Implemented future-run contract

- One opaque run ID is created before the future runtime callbacks and is passed
  unchanged to the durable directory, supervisor records, and guard consumption.
- The helper compile binary remains temporary; helper output is directed to the
  pre-created durable run directory.
- Mandatory future records are `run_manifest.json`, `scene_summary.json`,
  `request_metadata.json`, `create_process.json`, `helper_process.json`, and
  `shutdown_outcome.json`. A complete response also commits
  `scene_response.pb` and `scene_response.sha256`; no-response outcomes commit
  neither and use a null summary SHA.
- Option 1 wording is exact: the supervisor sends SIGINT only to its owned
  groups; a launcher may manage and escalate its own child. This is not
  end-to-end SIGINT-only.

## Offline evidence

| Check | Result |
| --- | --- |
| Python syntax | PASS |
| Supervisor unit tests | PASS — 28 tests |
| Dedicated launch static checker | PASS |
| C++ build | PASS — temporary binary, `-Wall -Wextra -Werror` |
| C++ offline self-test | PASS |
| C++ offline artifact self-test | PASS |
| Source boundary scan | PASS — no shell, retry, SIGTERM, SIGKILL, or `.kill()`; helper has exactly one `RequestRaw` in runtime-only code |

The validation did not launch Gazebo, ROS, `ros2 launch`, create, helper runtime,
Transport request, bridge, command/control path, or hardware. No guard was
acquired or consumed.

## Remaining blocker

The `base_link_collision` runtime warning versus the configured
`s3_d3_base_contact_collision` remains a separate static collision/conversion
investigation. This increment does not resolve collision identity, contact
endpoint behavior, ContactLatch, reward, termination, training, or hardware.
