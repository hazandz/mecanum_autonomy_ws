# WP-06 sim_eval ROS–Gazebo scan bridge — L2 decision

**Classification:** `L2_PROFILE_SPECIFIC_ROS_GAZEBO_SCAN_BRIDGE_IMPLEMENTATION`
**Evidence ceiling:** `IMPLEMENTED_OFFLINE_BUILD_ONLY`
**Integration base:** `abcdffb4d1683c6b337b7c8a8916d0c9317d111e`
**Review branch:** `wp06-sim-eval-ros-gz-scan-bridge-abcdffb`

## Decision

Implement one profile-specific, one-way bridge mapping:

| Boundary | Contract |
|---|---|
| Gazebo topic/type | `/scan`, `gz.msgs.LaserScan` |
| ROS topic/type | `/scan`, `sensor_msgs/msg/LaserScan` |
| Direction | `GZ_TO_ROS` |
| Lazy / queues | `false`; subscriber `10`; publisher `10` |
| Simulation clock | `use_sim_time: true` |
| Gazebo partition | launch argument `gz_partition`, default `sim_eval` |
| Bridge executable | `ros_gz_bridge` / `parameter_bridge`, configured by installed YAML `config_file` |

The stable Gazebo endpoint identity selected by this source is the topic and
message type pair `/scan` + `gz.msgs.LaserScan`. TCP transport addresses are
ephemeral observations and are explicitly not pinned. The static bridge
contract and its validator remain historical/provenance evidence and are not
modified.

The dedicated launch validates that `use_sim_time` is exactly true and that
`gz_partition` is non-empty before setting `GZ_PARTITION` or starting exactly
one `parameter_bridge` node. It starts no Gazebo server/client, spawn/create
action, robot state publisher, custom ROS publisher/subscriber, TF publisher,
odometry bridge, or command bridge. The bridge does not repair or mutate
`LaserScan.header.frame_id`.

## Evidence and limits

This candidate is source/configuration/launch plus offline-test and package
build evidence only. It does not prove that a runtime bridge is connected or
publishing ROS `/scan`. A later, separately authorized runtime must verify
exactly one ROS publisher for `/scan`, type
`sensor_msgs/msg/LaserScan`, `header.frame_id == lidar_frame`, valid non-empty
`ranges`, and no unexpected TF, odometry, or command publisher.

The historical Run005 parser replay establishes only a Gazebo-side observed
publisher for `/scan` with type `gz.msgs.LaserScan`; it does not pin an
ephemeral TCP address or prove the ROS bridge boundary. This candidate creates
no runtime evidence, endpoint-address pin, ROS `/scan` observation, TF
evidence, profile resolution, `ResolvedConfigV3`, `config_hash`, Gate B
transition, or runtime authorization. Runtime compatibility remains
`NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.

WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; Gate A remains
`PASSED`; Gate B remains `NOT_STARTED`. No navigation-ready assertion is
made.

## Future runtime boundary

Any runtime assessment requires independent review and a separate exact-scope
Owner authorization. It must use the same `GZ_PARTITION` for Gazebo and the
bridge. Even successful ROS-side publisher/type/frame/range checks would be
runtime compatibility evidence only and would not, by themselves, authorize
Gate B or change `RUNTIME_APPROVED`.

## WP06-6E dependency-lock clarification

The WP-05 external 14-root lock and its source-lock template remain unchanged.
They define common Navigation V1 dependency roots only. The package-level
`exec_depend` entries `ros_gz_bridge`, `launch`, and `launch_ros` are
profile-specific runtime dependencies for this `sim_eval` bridge; they are
not added to WP-05 `direct_dependency_roots` or `external_package_locks`.
The package manifest lists the 14 common roots first and these three
profile-specific dependencies afterward.

The bridge dependencies are declared in source but have not been runtime
validated. This correction changes only the offline dependency-lock test's
classification of common versus profile-specific dependencies and records
that distinction here. It does not change WP-05 lock content, runtime
compatibility status, runtime authorization, Gate B, or `RUNTIME_APPROVED`.


## Corrective source-owned LaserScan frame contract

The historical WP06-6E Runtime Run 001 is not a full acceptance pass. It
passed ROS `/scan` existence, `sensor_msgs/msg/LaserScan` type, one data
publisher, non-empty ranges, and clean bootstrap/bridge teardown. The
`/parameter_events` and `/rosout` publications are standard ROS node
endpoints and are not bridge-scope violations. The sole audited failure was
the source-owned `LaserScan.header.frame_id`: the observed value was
`ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO`, while the required value is
`lidar_frame`. The historical Run 001 evidence is not modified or promoted
to a full pass.

The earlier source correction added `<frame_id>lidar_frame</frame_id>` to the
existing `YDLIDAR_X3_PRO` Gazebo sensor. This corrective candidate retains
that field and adds `<gz_frame_id>lidar_frame</gz_frame_id>` as a second direct
sensor child, as required by the Gazebo Harmonic URDF/Gazebo path. Both fields
must occur exactly once with the exact value `lidar_frame`; the test rejects a
missing, duplicate, misplaced, or incorrect field/sensor/reference. The
current static-profile Gazebo source SHA-256 is reconciled across the YAML,
Python descriptor, WP-05 manifest, and WP06 evidence. The bridge does not
rewrite the message header; no bridge-side adapter, remap, TF publisher, or
ROS node is added. The WP-05 historical workspace inventory and external
14-root lock are unchanged.

Runtime Run 002 remains the immutable historical outcome
`WP06_6E_RUNTIME_FRAME_CONTRACT_FAIL_NO_RETRY`: the observed header frame was
`ROBOT_URDF_final/base_link/YDLIDAR_X3_PRO`, not `lidar_frame`. The run did
observe the GZ `/scan` to ROS `/scan` bridge, the expected
`sensor_msgs/msg/LaserScan` type, one data publisher, non-empty ranges, and
clean teardown; the frame mismatch remains the sole acceptance failure. The
source and offline checks in this candidate do not change that record and do
not promote the run to a pass. No runtime retry is performed. Only a separate
capacity-one runtime authorization after independent audit of the exact
corrective commit may assess the new dual-frame source contract.

This candidate provides source, offline-test, and build evidence only. A new
capacity-one runtime attempt requires independent audit and separate Owner
authorization for the exact corrective commit. No runtime approval, endpoint
pin, Gate B transition, or full runtime acceptance is created. Runtime
compatibility remains `NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.
WP-04 remains `BLOCKED_BY_CONTRACT`; WP-05 remains `OPEN`; Gate A remains
`PASSED`; Gate B remains `NOT_STARTED`.
