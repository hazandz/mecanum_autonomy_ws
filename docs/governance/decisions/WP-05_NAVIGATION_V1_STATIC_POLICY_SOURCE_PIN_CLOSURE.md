# WP-05 Navigation V1 Static Policy Source Pin Closure

## Decision scope

This is an L1 provenance record for three existing Navigation V1 static policy
sources. It pins their source commit, repository-relative paths, and file
SHA-256 values. The classification is
`PINNED_STATIC_POLICY_SOURCE_ONLY`.

The source commit for all three entries is
`c1d37b3d7ec349c0942790063d57887e5d201484`. The exact path and digest pairs
are recorded in
`docs/governance/evidence/WP-05_NAVIGATION_V1_STATIC_POLICY_SOURCE_PIN_MANIFEST.json`.

## What the pin establishes

The pin establishes provenance for the bytes of these three files at the
specified commit. Their contents intentionally remain pending policy templates
with `STATIC_TEMPLATE_ONLY` classification and `runtime_eligible: false`. The
manifest does not update or populate `workspace_source_locks` in the external
dependency-lock record.

Pinning a file does not resolve its content or turn its purpose into a
workspace-source role pin or runtime-source pin. In particular,
`nav2_lifecycle_bringup`, `remap_namespace_policy`,
`lifecycle_startup_policy`, and every other workspace-source role remain
`PENDING_IMPLEMENTATION_SOURCE_PIN`.

## Fail-closed and non-goals

The record does not authorize Nav2 activation, lifecycle transitions, runtime
graph creation, or profile resolution. It is not a
`WORKSPACE_SOURCE_ROLE_PIN`, `RUNTIME_SOURCE_PIN`, `RESOLVED_PROFILE_INPUT`,
`MAP_APPROVAL`, `RUNTIME_EVIDENCE`, or `RUNTIME_AUTHORIZATION`. Missing or
unverified required source pins and policy evidence continue to prohibit Nav2
activation under the static policies.

No concrete namespace/remap values, lifecycle transition values, runtime
defaults, source-role resolution, map approval, `config_hash`, or runtime
evidence is introduced by this record. WP-05 remains `OPEN`; the map remains
draft; `WORLD_FRAME` remains `NOT_DECLARED`; runtime compatibility remains
`NOT_VALIDATED`; and `RUNTIME_APPROVED` remains `NOT_APPROVED`.

## Candidate lifecycle

This decision and its manifest are a review candidate based on integration
`c1d37b3d7ec349c0942790063d57887e5d201484`. They record source provenance only;
they do not claim an audit result, integration of this candidate, or new
authorization.
