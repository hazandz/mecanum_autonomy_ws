# WP-05 Map Hash Serialization RFC 8785 Decision

**Record state:** CANDIDATE_PENDING_FOCUSED_AUDIT_AND_INTEGRATION_AUTHORIZATION
**Work package:** WP-05-MAP-HASH-SERIALIZATION-RFC8785-CHANGE-CONTROL
**Integration base:** c37a5bff9dd6cc32fc503cdd796b31720a58a616
**Candidate branch:** wp-05-map-hash-serialization-rfc8785-change-control-c37a5bff

## User decision and source packet

The Project Owner/User explicitly provided this decision in the prompt authorizing preparation of this change-control candidate:

USER_DECISION: APPROVED_FOR_WP05_MAP_HASH_SERIALIZATION_CHANGE_CONTROL

The decision selects RFC 8785 JSON Canonicalization Scheme (JCS) for map-content hash serialization. The source decision packet, reported as independently audited by the Project Owner/User, is pinned as follows:

- Branch: wp-05-map-hash-serialization-decision-packet-c37a5bff
- Commit: 38e496dc985969cb0d6a2e421b1eb7363c9b5a1f
- Packet: docs/WP-05_MAP_HASH_SERIALIZATION_DECISION_PACKET_DRAFT.md
- Packet SHA-256: ee31375df185c124f82a1fc56ee0daa12b4aa93297d2c5fe2c6e6cb0cd353515

## Approved serialization decision

For map_content_hash, the exact hashed payload is the map_hash_manifest projection with:

- schema mecanum_map_hash/v1;
- exactly two files entries, in the Architecture §48 order: map_yaml for relative name map.yaml, then occupancy_image for relative name map.pgm;
- each entry containing role, relative name, size_bytes and SHA-256 of the raw file bytes.

Serialize that projection using RFC 8785 JCS. The hash input is the exact JCS output encoded as UTF-8, with no BOM and no trailing newline. map_content_hash is SHA-256 of those exact bytes. The raw-file SHA-256 values and the resulting map_content_hash are distinct digests.

The hashed projection excludes metadata.yaml, any optional pose graph, manifest result fields, and map_content_hash itself. These exclusions prevent self-reference and preserve the approved map-content boundary.

## Candidate activation and scope

This record and its proposed Architecture §48 clarification are candidate content only. They are not active on integration/implementation until the exact candidate passes focused independent audit, the Project Owner/User separately authorizes integration of that exact candidate, and that exact commit is fast-forwarded with the remote integration ref verified. This prompt authorizes preparation and review of the candidate, not its integration.

The decision resolves serialization only. It does not select a map source or map ID, create or approve a map instance, select a scenario, or authorize code, ROS, runtime, HIL, hardware, motor operation, deploy_sim or deploy_real. WP-05 remains open; no status or dependency transition is made. CODE_AUTHORIZATION: NOT_GRANTED. RUNTIME_APPROVED: NOT_APPROVED.
