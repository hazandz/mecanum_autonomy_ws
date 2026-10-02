# S3 D3 — Final One-Shot Typed Scene Observer Runtime Run

**Status: DRAFT — FINAL ONE-SHOT RUNTIME RUN PENDING USER APPROVAL**

## Authority

Approval ID: `S3.3.53_TYPED_SCENE_OBSERVER_FINAL_ONE_SHOT_RUNTIME_RUN`.
This packet alone may authorize one future run. It remains a draft and creates
no execution authority until explicit user approval.

## Immutable scope

| Item | Locked value |
| --- | --- |
| World / entity | `world_demo` / `ROBOT_URDF_final` |
| Hierarchy question | `ROBOT_URDF_final → base_link → s3_d3_base_contact_sensor` |
| Scene service | `/world/world_demo/scene/info`: `gz::msgs::Empty → gz::msgs::Scene` |
| Create argv | `-topic /robot_description -name ROBOT_URDF_final -allow_renaming false -x 0 -y 0 -z 0.1 -Y 0` |
| Helper timings | `90000/5000/10 ms` preflight/request/poll |
| Create timings | `90000/2000/5000 ms` timeout/post-delay/SIGINT grace |
| Cardinality | One bootstrap spawn, one direct create, one Scene request, no retry, capacity `1` |
| Shutdown | Measurement-created groups only; SIGINT-only |

The only bootstrap mutation is the initial robot spawn. After bootstrap there
is one create and one typed Scene request. No bridge, `/cmd_vel`, pose/reset,
world-control, training, hardware, or second run is authorized.

## Hash-locked inputs

| Input | SHA-256 |
| --- | --- |
| Supervisor | `991a27ae86402092d3ce4b8c04d9cbed13a7659c316891f14dbc3632b0210c74` |
| Typed helper | `ff6cc497ce845e136469f8cc026c8d6076c129da39f53591072d3b62e6241424` |
| Dedicated launch | `b6acf767471527f37c4e2d7c67cc46b693298cb4bf7028afb96be8d00c4f255d` |
| World SDF | `1c50f90d151a12559d426796c5d153c829b8777a5b4e8ef94c007a2023f6e271` |
| Direct create executable | `549a91ca31d5b943457b1fa6ae25cc726867b6afa69d789e1afbd2af139fe02d` |

The independent S3.3.53 guard also binds this packet SHA, its own helper SHA,
all literals, paths, capacity, and trusted-context lease metadata. Drift,
symlink, traversal, malformed record, lock collision, or atomic-write failure
fails closed before any process.

## Terminal diagnostic outcomes

A valid retained diagnostic result may be any of:

- `SCENE_SERVICE_UNAVAILABLE`
- `SCENE_REQUEST_INCOMPLETE`
- `SCENE_RESPONSE_UNDECODABLE`
- `SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_LINK_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY`
- `SCENE_SENSOR_PRESENT_IDENTITY_ONLY`

These outcomes preserve evidence only. They do not prove collision, ContactLatch,
reward, termination, training, reset receipt, or hardware readiness.

## Required approval

User approval must name the exact approval ID, all locked literals/hashes,
capacity one, no retry, and SIGINT-only shutdown. This draft is not approved.
