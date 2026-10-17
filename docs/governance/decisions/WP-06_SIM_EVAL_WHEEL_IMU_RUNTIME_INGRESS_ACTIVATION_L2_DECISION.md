# WP06-6C sim_eval wheel/IMU runtime ingress activation — L2 decision

**Classification:** `L2_PROFILE_SPECIFIC_WHEEL_IMU_RUNTIME_INGRESS_IMPLEMENTATION`
**Exact base:** `bd749560e50e11963873c33a51f806e420c38392`
**Evidence ceiling:** `IMPLEMENTED_OFFLINE_BRIDGE_AND_INGRESS_SOURCE_ONLY`
**Runtime eligible:** `false`

## Bounded data path

This candidate adds two GZ-to-ROS staging mappings and one ingress node. Wheel
samples flow from Gazebo `/joint_states` (`gz.msgs.Model`) to ROS
`/sim_eval/wheel_joint_states` (`sensor_msgs/msg/JointState`), then the existing
`SimEvalWheelOdometryEmulator` derives canonical `/wheel/odometry_raw`
(`nav_msgs/msg/Odometry`). IMU samples flow from Gazebo `/sim_eval/imu/raw`
(`gz.msgs.IMU`) to ROS `/sim_eval/imu_raw` (`sensor_msgs/msg/Imu`), then the
existing normalizer supplies canonical `/imu/data` (`sensor_msgs/msg/Imu`).
Both bridge directions are `GZ_TO_ROS`; staging QoS is best-effort, volatile,
keep-last depth 10.

The launch defaults `gz_partition` to `sim_eval`, sets `GZ_PARTITION` from that
argument, and requires effective `use_sim_time=true`. It starts only the
`ros_gz_bridge/parameter_bridge` and `mecanum_base_bridge/
sim_eval_wheel_imu_ingress` nodes. It does not start EKF, Nav2, AMCL, Map
Server, a TF publisher, or a command publisher. The Gazebo IMU sensor
`sim_eval_base_imu` under `gazebo reference="base_link"` has exactly one direct
`<frame_id>base_link</frame_id>` and one direct
`<gz_frame_id>base_link</gz_frame_id>`. Existing wheel kinematics, covariance,
rollback barrier, IMU normalizer, sensor rate/topic/pose, LiDAR source and
other Gazebo systems are retained.

No mapping is added for Gazebo `/odom`, `/ground_truth/odom`, `/tf`, or
`/tf_static`. Ground Truth is not an input. The only odometry output in this
path is the existing wheel-odometry estimate derived from JointState; it is
not Gazebo odometry or Ground Truth. The ingress continues to publish no TF.

## Provenance and status boundary

Adding the two IMU frame tags changes the current Gazebo source SHA-256 from
`9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` to `7bbaa475578600d8e18e437fa83720483b90b4af2bf4212151257152429576a2`. Only the current WP-05 static-profile YAML, Python
contract, related current-provenance tests, and WP-05 static-profile manifest
are reconciled to the new source bytes. The WP-05 external 14-root dependency
lock, historical workspace inventory, and static-policy manifest are
unchanged. WP06-6E Run 003 disposition and raw evidence remain historical to
source SHA `9ff2dd9578b069cc492c9ff05e7f7f0d952c8bad0c5ecd9710ccea63d9fb1bbd` and are not modified, replayed, or contradicted; their
audited result remains bounded to the scan-bridge scope.

Candidate status is `IMPLEMENTED_OFFLINE_BRIDGE_AND_INGRESS_SOURCE_ONLY`;
`runtime_eligible: false`; `runtime_evidence_status: NOT_CREATED`. WP-04 stays
`BLOCKED_BY_CONTRACT`, WP-05 stays `OPEN`, `RUNTIME_APPROVED: NOT_APPROVED`,
and `GATE_B: NOT_STARTED`. No navigation-ready, EKF-validated, TF-validated,
endpoint-address pin, `ResolvedConfigV3`, `config_hash`, runtime
authorization, or Gate B transition is created. This candidate does not run
ROS, Gazebo, `gz`, launch, or runtime.

## Corrective observability disposition — Run 001

The historical Run 001 remains `WP06_6C_RUNTIME_FAIL_NO_RETRY` and is
immutable. Its recalculated artifact hashes match the external artifact
manifest and `SHA256SUMS.txt`. The run captured one ROS publisher and one
subscriber endpoint for `/sim_eval/imu_raw`, but captured no staging payload:
the only `/imu/data` echo transcript is empty, timed out with exit code 124,
and no `/sim_eval/imu_raw` sample transcript exists. These facts do not prove
whether (A) the Gazebo sensor emitted no IMU message, (B) the bridge did not
transfer a message, or (C) the ingress normalizer rejected input. Finding:
`RUN001_RAW_IMU_STAGING_SAMPLE_NOT_CAPTURED_ROOT_CAUSE_NOT_PROVABLE`.

This correction adds bounded, structured first-accept/first-rejection
normalizer diagnostics and a pure offline parser for ROS CLI YAML
multi-document transcripts. It does not change IMU acceptance semantics,
sensor declaration, bridge mapping, wheel behavior, or public topics. A future
capacity-one runtime packet must preserve a Gazebo-side source sample from
`/sim_eval/imu/raw` to distinguish source emission from bridge transfer, and
must capture the ROS staging sample `/sim_eval/imu_raw`, its
`ros2 topic info --verbose` output, `/imu/data`, and ingress diagnostic logs.
The raw and canonical ROS samples must be parsed with `yaml.safe_load_all`.
If staging data exists but canonical output does not, the record must identify
the concrete normalizer gate and its stamp, frame, finite-value status,
quaternion norm, prior accepted timestamp, and monotonic comparison. Publisher
counts alone are not payload evidence.

The new source and tests are offline-only; they are not runtime evidence and
do not prove or claim a repaired sensor, bridge, or normalizer semantic cause.
`runtime_eligible: false`; no runtime retry or authorization is created.
`RUNTIME_APPROVED: NOT_APPROVED`; Gate B remains `NOT_STARTED`.
