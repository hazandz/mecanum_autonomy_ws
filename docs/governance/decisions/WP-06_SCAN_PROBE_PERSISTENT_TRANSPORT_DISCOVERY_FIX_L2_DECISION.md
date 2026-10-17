# WP06 Run 005 persistent Gazebo Transport discovery — corrective L2 decision

## Classification and scope

`L2_SIM_EVAL_SCAN_PROBE_PERSISTENT_TRANSPORT_DISCOVERY_FIX` remains a source,
offline-test and offline-build candidate only. This corrective review commit
fixes the Run 005 runtime preflight topology so that a separately authorized
future session can execute on an exact review commit while the integration
ref remains at the known base `83f13d67ab212fec03b18cd2ed830349b7013ab3`.
It does not authorize runtime by itself.

## Corrected review/integration topology

The session runner takes two distinct exact 40-hex values:

- `--expected-review-commit`: the exact reviewed corrective commit that must
  equal `HEAD` and from which all candidate source, manifest, decision,
  evidence and guard blobs are verified byte-for-byte;
- `--expected-integration-base`: the known integration base that must equal
  `origin/integration/implementation` and be an ancestor of the review commit.

The integration ref is intentionally not required to equal the review commit
before runtime. A clean checkout at the exact review commit may be run only
after independent audit and a separate Owner authorization naming that exact
review commit. The base is an ancestry/ref check only; it is never used as the
source of candidate bytes. The run record distinguishes `review_commit` from
`integration_base`.

## Preserved Run 005 contract

The persistent Gazebo Transport Node discovery, Run 005 partition, exact service,
create command and success bytes, probe command, source pins, process-group
ownership and teardown policy remain unchanged. The delayed binding import
must succeed before guard acquisition. Any failed ref, ancestry, clean-tree,
authority, manifest, guard, source-blob, command/context or binding check must
leave the capacity-one guard pending and unconsumed.

## Evidence and authorization boundary

The Run 005 guard remains capacity one and
`PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION` in this source candidate.
This candidate does not consume it. Evidence remains
`IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`; no runtime was executed.
Runtime requires independent audit and a separate Owner authorization for the
exact review commit. A future runtime pass does not itself authorize
integration. Only after a runtime pass may the Owner decide whether to
integrate that exact review commit.

Even a future successful observation means only
`GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. It does not establish ROS
`/scan`, `ros_gz_bridge`, TF, AMCL, EKF, Nav2, runtime compatibility, Gate B,
`RUNTIME_APPROVED`, `ResolvedConfigV3` or `config_hash`. No bridge, endpoint
pin, runtime evidence or runtime approval is created here.

`WP-04: BLOCKED_BY_CONTRACT`; `WP-05: OPEN`; `Gate A: PASSED`;
`Gate B: NOT_STARTED`; `RUNTIME_APPROVED: NOT_APPROVED` remain unchanged.


## Corrective candidate: Gazebo Transport 13 binding and pre-acquire Node

This corrective candidate fixes the host binding contract without changing
Run 005 topology, partition, world, LiDAR source, probe, create command, or
process-group teardown. Gazebo Harmonic uses Gazebo Transport 13; the host
prerequisite is package `python3-gz-transport13`, providing the runtime import
`from gz.transport13 import Node, NodeOptions`. The candidate does not run
`apt`, `sudo`, ROS, Gazebo, launch, the session runner, or any runtime.

After exact review-commit source/ref preflight and before creating the run
directory or acquiring the pending guard, the future runner imports the
Transport 13 binding, constructs one `NodeOptions`, assigns the exact Run 005
partition, constructs exactly one `Node`, and verifies `service_list` is
callable. Any failure returns
`GZ_TRANSPORT13_BINDING_OR_NODE_PREACQUIRE_UNAVAILABLE` before guard
consumption and before run-directory creation. After acquisition, persistent
discovery reuses that same Node. No second Node or `gz service --list` is
used.

The Run 005 guard remains capacity one and
`PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`; this offline candidate
does not consume it or grant runtime authorization. Evidence remains
`IMPLEMENTED_OFFLINE_GUARD_AND_SESSION_SOURCE_ONLY`. Existing review/integration
topology is preserved: candidate source bytes are verified against the exact
review commit, while the integration ref remains the exact base and must be
an ancestor. No bridge, ROS `/scan`, TF, endpoint pin, runtime evidence,
`ResolvedConfigV3`, `config_hash`, Gate B transition, or runtime approval is
created. `RUNTIME_APPROVED: NOT_APPROVED` and WP/Gate statuses are unchanged.


## Corrective candidate: Harmonic topic-info footer parser replay

This is a parser-only correction on the existing Run 005 review line. The
historical Run 005 session was invoked exactly once on review commit
`20814c9009cee588f6b330ee227f69d886949593`; its immutable run record remains
`PROBE_NOT_EXACTLY_ONE_MATCH`, and its runtime-host authorization was consumed.
The Git source guard remains the pending seed snapshot; it does not permit a
second Run 005 runtime session. No Run 005 retry is authorized or performed.

Independent review of the preserved 111-byte `gz topic -i -t /scan` raw
transcript confirmed one unbracketed Harmonic publisher entry:
`tcp://127.0.0.1:44619, gz.msgs.LaserScan`, followed by
`No subscribers on topic [/scan]`. Offline replay of those exact bytes with
the corrected parser returns `EXACTLY_ONE_MATCH` and
`GZ_LASERSCAN_ENDPOINT_OBSERVED_NOT_PINNED`. The historical run-record
terminal outcome is not rewritten. The correction accepts that exact
no-subscribers footer, requires one publisher record with exact
`gz.msgs.LaserScan`, and fails closed for missing, malformed, wrong-type or
ambiguous publishers.

This replay does not establish a ROS `/scan` publisher, ROS–Gazebo bridge, TF,
runtime compatibility, endpoint pin, runtime approval, or Gate B. No runtime
was rerun for this correction; Run 005 remains consumed and must not be run
again.
