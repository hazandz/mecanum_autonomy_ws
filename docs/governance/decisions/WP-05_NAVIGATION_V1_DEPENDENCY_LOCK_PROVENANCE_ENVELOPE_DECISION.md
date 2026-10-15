# WP-05 Navigation V1 Dependency-Lock Provenance Envelope Decision

**Classification:** `L2_GOVERNANCE_SCHEMA_INTERFACE_EXTENSION`
**Exact source-base review snapshot:** `f23af59d7a9458175928c2647532339ff933158b`
**Architecture:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`

## Decision

The dependency-lock schema advances to revision 2 and requires a typed,
immutable `artifact_baseline_provenance` object with exactly five groups:
`baseline_identity`, `artifact_closure`, `ros_signing_key`,
`correction_report_sha256`, and `quarantined_non_closure_artifacts`.
All fields are required and every nested object rejects unknown fields. The
schema and static validator constrain identity formats, relative paths, integer
counts/bytes, and the exact quarantine classification.

The existing 14 logical roots and their mappings remain unchanged. `launch_ros`
is not a logical root. Existing per-package lock requirements and fail-closed
semantics remain in force. The validator inspects only caller-provided values;
it does not access the filesystem, external artifact bundle, Docker, network,
or runtime and cannot prove artifact existence.

## Lifecycle

This record describes a review candidate at source base
`f23af59d7a9458175928c2647532339ff933158b`. After independent audit PASS for
the exact candidate, separate explicit User authorization for that exact
commit, fast-forward, and remote-ref verification, the amendment is an active
authority only for dependency-lock provenance schema semantics.

No concrete dependency lock or profile source is created. No package is pinned
by this candidate; no runtime semantics, TF/lifecycle ownership, map approval,
profile resolution, `config_hash`, or runtime authorization changes. WP-05
remains `OPEN`; the map remains draft; runtime compatibility remains
`NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`.
