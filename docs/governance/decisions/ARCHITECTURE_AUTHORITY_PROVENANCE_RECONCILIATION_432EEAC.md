# Architecture Authority Provenance Reconciliation — 432EEAC

## Classification and scope

`L1_ARCHITECTURE_AUTHORITY_PROVENANCE_RECONCILIATION_ONLY`. This record reconciles Git-verifiable Architecture identity and stale provenance wording in the listed legacy/draft documents. It does not change technical semantics or activate any legacy/draft record as authority.

## Exact authority identities

At exact integration base `457926439220756f5dc18ed62c9d1143715668fc`, the Git blob for `docs/MECANUM_NAV_DRL_Architecture.docx` has SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`. This is the current Git-verifiable Architecture authority identity.

Historical provenance is `docs/MECANUM_NAV_DRL_Architecture.docx@86beff623dba3683f643c851a4a1374c635178b3`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`. This historical reference is provenance only and is not a current Architecture authority claim.

Git-verifiable provenance chain:

`86beff623dba3683f643c851a4a1374c635178b3` / historical blob SHA `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860` → `988a74b529fdb4bcf77f341db5c6d115e8511a9b` / Architecture blob SHA `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` → exact integration base `457926439220756f5dc18ed62c9d1143715668fc`.

Commit `988a74b529fdb4bcf77f341db5c6d115e8511a9b` is an ancestor of the base. Its subject and changed paths record the RFC 8785 map-hash serialization transition. The verified semantic delta is limited to §48: RFC 8785 JCS UTF-8 serialization for `map_content_hash`.

## Reconciliation disposition

Each of the 26 documents below is classified `HISTORICAL_PROVENANCE_ONLY` and `NOT_A_CURRENT_ARCHITECTURE_AUTHORITY_CLAIM`. Its Architecture provenance wording now identifies `f0fb1ebe…` as historical and points to the current Git-verifiable identity `432eeac…`. The reconciliation does not activate any decision, parameter, status, draft, acceptance criterion, scope, code authorization, runtime authorization, or other technical content in those documents.

1. `docs/A0_3_V3_Config_Compiler_And_Validation.md`
2. `docs/A0_4_V3_Config_Assets_And_Package_Boundary.md`
3. `docs/A0_5_2_2_Explicit_V3_Asset_Selection.md`
4. `docs/A0_5_2_3_Canonical_Asset_Envelope_Foundation.md`
5. `docs/A0_5_2_4_Explicit_Source_Selection_Extension.md`
6. `docs/A0_5_2_5_D13_D14_Decision_Closure.md`
7. `docs/A0_5_2_Canonical_Asset_Decision_Packet.md`
8. `docs/A0_5_2_V3_Canonical_Yaml_Migration_Readiness.md`
9. `docs/A0_Architecture_Config_Contract_Reconciliation.md`
10. `docs/S3_Control_Step_And_Simulation_Time_Contract_DRAFT.md`
11. `docs/S3_Controlled_Coordinate_And_Reset_Measurement_Plan_DRAFT.md`
12. `docs/S3_D2_Final_Issued_Command_Receipt_Design_DRAFT.md`
13. `docs/S3_D2_Receipt_Ownership_User_Decision_Packet_DRAFT.md`
14. `docs/S3_D6_Episode_Limit_Decision_Packet_DRAFT.md`
15. `docs/S3_Episode_Reward_Termination_Design_DRAFT.md`
16. `docs/S3_GT_2D_Coordinate_Relation_Decision_Packet_DRAFT.md`
17. `docs/S3_Goal_Oracle_Lifecycle_Join_Design_DRAFT.md`
18. `docs/S3_Reward_v3_Core_Scope_And_Input_Contract_DRAFT.md`
19. `docs/S3_Scenario_Artifact_Core_Implementation_Design_DRAFT.md`
20. `docs/S3_Scenario_V1_User_Decision_Packet_DRAFT.md`
21. `docs/S3_Simulation_Scenario_Artifact_Contract_DRAFT.md`
22. `docs/S3_Training_Task_Oracle_Core_Design_DRAFT.md`
23. `docs/S3_Training_Task_Reset_And_Collision_Design_Packet_DRAFT.md`
24. `docs/S3_Transition_Provenance_Decision_Packet_DRAFT.md`
25. `docs/S3_Trusted_Scenario_Session_Binding_Design_DRAFT.md`
26. `docs/S3_World_Geometry_And_Entity_Inventory_DRAFT.md`

This record does not modify the Architecture DOCX, map bytes or map-content hash, WP-04/WP-05 technical semantics, implementation source pins, package locks, profiles, global `config_hash`, or any authorization. No WP-04 or WP-05 status/dependency transition is made.

## Candidate lifecycle

At base `457926439220756f5dc18ed62c9d1143715668fc`, this is a review candidate. Only after independent audit PASS for the exact candidate, separate exact-commit User authorization, fast-forward, and remote-ref verification may it be described as an integrated provenance-reconciliation governance record only. Integration does not make any legacy/draft document active authority and does not activate technical semantics. No audit-report hash or new Owner decision is asserted.

## Status

WP-04 remains `BLOCKED_BY_CONTRACT`; Gate A `PASSED`; Gate B `NOT_STARTED`. WP-05 remains `OPEN`; map artifact remains `DRAFT_ON_INTEGRATION_NOT_APPROVED`; `WORLD_FRAME: NOT_DECLARED`; `RUNTIME_COMPATIBILITY: NOT_VALIDATED`; `RUNTIME_APPROVED: NOT_APPROVED`. No code/runtime authorization is granted by this record.
