# ACR — Navigation V1 Dependency-Lock Provenance Envelope

**Change class:** `L2_GOVERNANCE_SCHEMA_INTERFACE_EXTENSION`
**Source-base review snapshot:** `f23af59d7a9458175928c2647532339ff933158b`
**Architecture authority:** `docs/MECANUM_NAV_DRL_Architecture.docx`, Git-blob SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`

## Decision

The Navigation V1 dependency-lock schema revision 2 requires the typed
`artifact_baseline_provenance` envelope. The envelope identifies immutable
provenance for the external artifact baseline. It supplements, and never
replaces, the exact package pins in the lock.

The envelope contains exactly `baseline_identity`, `artifact_closure`,
`ros_signing_key`, `correction_report_sha256`, and
`quarantined_non_closure_artifacts`. Every object is closed to unknown fields;
all declared fields are required. Digests, source commit, signing fingerprint,
paths, counts, and the quarantine classification have explicit structural
constraints in the JSON Schema.

The 14 logical dependency roots, their names and mapping semantics, existing
per-package fields, and fail-closed behavior remain unchanged. `launch_ros`
remains outside the logical root set. The static validator checks caller-supplied
values only; it performs no filesystem, artifact-bundle, container, network, or
runtime inspection and does not attest that an external artifact exists.

## Activation and boundaries

At the exact source-base snapshot above this ACR, schema, and validator are a
review candidate. Only after independent audit PASS for the exact candidate,
separate explicit User authorization for that exact commit, fast-forward, and
remote-ref verification may the amendment be described as an active authority
for the dependency-lock provenance schema only.

This amendment does not create a concrete lock instance or static profile
source, pin any package, resolve a profile, compute `config_hash`, approve a
map, change runtime semantics or ownership, or grant runtime authorization.
