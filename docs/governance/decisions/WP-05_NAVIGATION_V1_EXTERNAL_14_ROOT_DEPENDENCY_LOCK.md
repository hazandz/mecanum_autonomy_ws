# WP-05 Navigation V1 External 14-Root Dependency Lock Record

## Status and scope

This is an L1 external dependency-lock record for review from exact integration
base `ab5c62f866985b72cbaff370fae38cdd6192dbcc`. It records immutable package
artifact pins for the 14 logical roots in the active
`mecanum_navigation_v1_dependency_lock/v2` schema. It does not create a static
profile source, workspace-source pins, resolved profile, or `config_hash`.

The JSON record is intentionally schema-only: its top-level keys and package
entry keys are limited to those allowed by schema v2. The lock's
`artifact_baseline_provenance.baseline_identity.source_commit` identifies the
collection provenance commit `f23af59d7a9458175928c2647532339ff933158b`; the
candidate's integration base is `ab5c62f866985b72cbaff370fae38cdd6192dbcc`.
These commits identify different repository states and must not be treated as
the same workspace state. The artifact locator is only an external evidence
locator; it is neither a runtime path nor authority by itself.

## External artifact evidence

The record references the Owner-accepted simulation baseline for
`linux/amd64`, with base image
`ubuntu@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55`,
purpose `NAVIGATION_V1_SIM_BASELINE_BOOTSTRAP_ONLY`, and a closure of 1,280
artifacts totaling 700,260,532 bytes. The closure manifest SHA-256 is
`54077ab6ee43af793ec266f92e6ea74fc21ee5af9606b1939ca83fc49714600e`. The ROS
keyring SHA-256 is
`4a91c49af0d6f0016108b93698782b596c27ccd836937e18e0e36c3347dc602f`; its
primary signing-key fingerprint is
`C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654`. The fingerprint-record SHA-256 is
`5b1eee4d0b26fa8788abfcfb5bb628641eb0ba635e02b40e00ae00c68f33e31d`, and the
baseline correction-report SHA-256 is
`95c055de96037a1402911dcaf3e952fedfe98d6eede1986b71cd6c6b1d8315fe`.

The six quarantined non-closure artifacts remain excluded. Their manifest is
`metadata/quarantined_non_closure_artifacts.sha256`, SHA-256
`44a9831b1686dc334a198f16630a31d5adee1f1a3e6d789e43289bdd378d96b8`, count 6,
classification `QUARANTINED_NON_CLOSURE_ARTIFACT_NOT_PART_OF_NAVIGATION_V1_LOCK`.
`ros-jazzy-launch-ros` is closure support only and is not a schema logical
root or package entry in this lock.

At this review snapshot, local read-only verification matched each of the 14
listed `.deb` files' package, version, architecture, and SHA-256 against the
closure manifest. The JSON record is validated structurally against schema
v2; neither that validation nor Git integration proves runtime installation,
runtime behavior, or continued availability of the external evidence bundle.
No `.deb`, APT list, keyring binary, or artifact bundle is committed to Git.

## Boundary and pending evidence

`workspace_source_locks` is `[]` because no valid workspace-source pins are
selected. The active static runtime validator requires ten workspace roles;
this record therefore must not be supplied as a complete runtime input and is
rejected by that validator for incomplete workspace-source locks. It is an
external lock record only, not a resolved Navigation V1 profile.

Map Server/AMCL/EKF configuration and launch sources, remap/namespace policy,
lifecycle/startup source, TF geometry source, and the other required workspace
roles remain unpinned. `warehouse_map2` remains
`DRAFT_ON_INTEGRATION_NOT_APPROVED`; this record does not approve a map, declare
a world transform, validate runtime compatibility, or grant runtime
authorization. Missing or mismatched pins remain fail-closed: no profile
resolution, `config_hash`, or bring-up follows from this record.

This is a review candidate at the stated source-base snapshot. Only after
independent audit PASS for the exact candidate, separate explicit User
authorization for that exact commit, fast-forward, and remote-ref verification
may the record be described as integrated. Those conditions do not promote it
beyond external dependency-lock provenance.

## Status

WP-05 remains `OPEN`; map remains draft and not approved; `WORLD_FRAME` remains
`NOT_DECLARED`; `RUNTIME_COMPATIBILITY` remains `NOT_VALIDATED`;
`RUNTIME_APPROVED` remains `NOT_APPROVED`. WP-04 remains
`BLOCKED_BY_CONTRACT`; Gate B remains `NOT_STARTED`.
