# WP-04 Gate B canonical input-source selection record

**Status:** `CANDIDATE_ONLY_PENDING_FOCUSED_AUDIT_AND_SEPARATE_INTEGRATION_AUTHORIZATION`
**Work package:** `WP04-GATE-B-CANONICAL-INPUT-SOURCE-SELECTION`
**Integration base:** `29080644f3020f7ecd208dc45433c7d36ecc5e2e`
**Decision provenance:** Project Owner/User source-selection rule supplied for this work package on 2026-10-12. This record does not assert a separate audit-report hash.

## 1. Authority and decision boundary

The frozen Architecture remains highest authority. At the stated base, ACR revision 3 and Observation V3 Specification revision 5 remain the active technical authority for the observation-input-profile schema and semantics. Their status/provenance successors do not alter that contract. ACR revision 3 defines the required immutable-reference schema; this record does not amend it, change profile semantics, select a previously missing contract, or make this candidate active.

The Owner's source-selection rule is:

1. Only a source explicitly established as current authority by the Canonical Source Registry or an applicable approval record may be selected as canonical.
2. ACR revision 3 and Observation V3 Specification revision 5 continue to control current profile schema and semantics.
3. Observation Input Contract V3 revision 6, review candidates, and drafts are provenance only; they do not supply authority or inferred fields/defaults.
4. A profile is an immutable record referring to selected contract sources. Each populated reference requires exact identity/revision, immutable Git commit, repository path, source-file digest, contract digest where specified, and provenance.
5. If there is no single currently approved source, the item remains pending. No alias, inferred contract ID, digest, measurement, or default is permitted.

This is source selection/provenance governance, not a new technical contract. No Architecture Change Record revision is required for this record because no Architecture, ACR3, or Specification rev.5 semantics are changed and no new contract source is selected. If closing a pending row later requires changing public contract semantics, schema, topic/QoS, TF, observation, or safety boundaries, stop and perform the applicable ACR/version change-control first.

## 2. Exact active authorities checked

| Authority | Exact source at this base | Permitted use here |
|---|---|---|
| Architecture | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` | Highest architecture authority; observation, frame, lifecycle and configuration constraints. |
| Observation profile ACR | `docs/architecture/ARCH_CHANGE_RECORD_OBSERVATION_INPUT_PROFILE_V3.md`; active technical revision 3 SHA-256 `38cb74c0b09cd9c3ecbbac30c6520e0d01f7711adb788414a0a46489e844d9f8`; activated at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` | Defines profile member set, immutable reference shape, exact pin requirements and fail-closed resolution. File revision 5 is status/provenance history only. |
| Observation specification | `docs/OBSERVATION_V3_SPECIFICATION.md`; active technical revision 5 SHA-256 `4092ee19d48a760b329ff49b9a79e39ab8389ff232aabd5dd06db83f8d83e5a2`; activated with ACR3 at `8c3de26521d7028a933f0a3ebe780fcb372f7a3a` | Defines observation boundary and profile applicability; file revision 7 is status/provenance history only. |
| Gate A/B ACR | `docs/ACR_V3_OBSERVATION_BOUNDARY_CLOSURE.md`; ACR8 SHA-256 `03fef021f6b9731f811f83a5e53aae1c430bdc2ea76815a8ada416f1a5bf772c` | Approved Gate B gates and existing status/failure vocabulary, as selected by Registry and the integrated bundle approval. |
| Receipt Topic QoS contract | `docs/RECEIPT_TOPIC_QOS_CONTRACT.md`; QoS6 SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022` | Approved receipt transport contract; exact identity/manifest pin below. |
| Bundle approval | `docs/governance/decisions/QOS_REVISION_6_ACR_REVISION_8_BUNDLE_APPROVAL.md`; SHA-256 `4d740559f850f179387db802df845748068f75a21266fd1edb52402b2c72c529` | User approval/provenance for the canonical QoS6/ACR8 bundle and receipt v2 pins. |

The ACR8/QoS6 source files preserve historical pre-integration draft labels. Their approved canonical status is established by the integrated bundle approval and Registry, not by those historical labels alone.

## 3. Source-by-source inventory

Pins below are Git-verifiable at immutable commits. A verified source-file digest is not interchangeable with a semantic contract digest, transport-manifest digest, or full-document digest. Only the already approved receipt and transport sources are selected as populated profile-reference sources here.

| Profile source group | Active canonical source / exact pins verified | Current disposition and remaining evidence |
|---|---|---|
| LiDAR snapshot contract | Architecture and activated ACR3/Specification rev.5 define the observation boundary, but the active Registry/approval does not select a unique LiDAR snapshot contract ID/revision and semantic digest. | `PENDING_OWNER_DECISION`; then verify exact approved immutable source commit/path/source-file SHA and contract digest. Do not derive pins from OIC rev.6, config examples, or drafts. |
| LocalReference/goal input contract | Architecture and activated ACR3/Specification rev.5 define required LocalReference role/boundary, but no unique approved contract identity/digest is selected. | `PENDING_OWNER_DECISION`; then verify immutable source bytes and provenance. Do not treat similar frame/topic names as equivalence. |
| Measured-twist snapshot contract | Architecture and activated ACR3/Specification rev.5 define the three measured-twist features and exclusion boundary; no unique approved snapshot contract identity/digest is selected. | `PENDING_OWNER_DECISION`; then verify immutable source bytes and provenance. Measurement-dependent validity, freshness, covariance, and provenance values separately remain `PENDING_MEASUREMENT`. |
| Frame contract | Architecture constrains TF/frame relationships; `ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` is within the Registry-approved V3 input family, but the Registry/approval does not select it as a unique canonical frame-contract source with a profile contract ID/digest. | `PENDING_OWNER_DECISION`; do not promote the config file or infer frame aliases. After an approved source is selected, verify its exact commit/path/bytes. |
| Lifecycle/reset/action-barrier policy | Activated ACR3 and ACR8 provide lifecycle/barrier semantics and failure boundaries, but do not supply one selected profile contract ID/revision and semantic digest with immutable source reference. | `PENDING_OWNER_DECISION`; then verify exact source pins. Runtime lifecycle values and barrier occurrences remain runtime facts, never static profile values. |
| Final-issued receipt interface | `mecanum.final-issued-receipt/v2`, schema revision `2`; canonical path `ros2_ws/src/mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt.msg`; source commit `2e7a2980cb75f0567182ea694c04328d7d8643e0`; schema/source SHA-256 `0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a`. Dependency-closure v1 path `docs/RECEIPT_INTERFACE_DEPENDENCY_CLOSURE_MANIFEST.json`, SHA-256 `0872fa8c10179f69c2e9e9546392ac734a4f4e94ade176a8be431f06905ecf73`, is a distinct approved pin at the same commit. | Approved identity/schema/dependency pins are present and byte-verified against the integrated bundle. No ROSIDL generation or runtime compatibility evidence is claimed. Do not treat the receipt instance/payload as profile data. |
| Receipt topic/QoS contract | `mecanum.final-issued-receipt-topic-qos/v2`; QoS revision `6`; canonical transport manifest `docs/RECEIPT_TOPIC_QOS_TRANSPORT_MANIFEST.json`, source commit `2e7a2980cb75f0567182ea694c04328d7d8643e0`, manifest/source SHA-256 `338bea1b7350d3b82146c7e728516ec7947471ee68db0f8871ddb72071b79620`; QoS full-document SHA-256 `4200cd2fbdc81a19400f168dd3526eb7871ac2251049fc7c4f5d5c2fddfd2022`. | Approved identity and transport-manifest pin are present and byte-verified against the integrated bundle. Manifest SHA and full-document SHA are distinct. This does not prove ROS/QoS runtime integration. |
| Concrete profile source | ACR3 defines the required `profile_source` immutable Git reference shape, but no unique concrete profile file/source has been selected by the active Registry/approval. | `PENDING_OWNER_DECISION`; after selection, pin exact commit/path/source-file SHA and verify bytes. No profile instance is resolved by this record. |

The ACR3 requirement for exact IDs/digests on the LiDAR, LocalReference, measured-twist, frame, and lifecycle/reset/barrier references remains controlling. Existing Architecture/ACR/specification semantics do not by themselves provide those missing profile contract identifiers and digests. The user-approved source-selection rule does not fill them.

## 4. Evidence classes and fail-closed boundary

- **Offline source selection/pinning:** verify Registry/approval authority, commit ancestry where relevant, exact path bytes, and separate source/contract/manifest digests. This candidate verifies the existing receipt and QoS pins only.
- **Measurement evidence:** timing, receipt-after-barrier timeout, skew, buffer limits, sensor freshness, measured-twist validity/covariance/provenance, LiDAR timing, and YDLIDAR X3 extrinsic/range/frame remain `PENDING_MEASUREMENT` as specified by active authority. No value is selected here.
- **Implementation/acceptance evidence:** ACR8 Gate B conditions, typed core/compiler behavior, projection/JCS vectors, schema migration, and applicable-profile rejection/acceptance evidence are not produced by this governance record.
- **ROS adapter/runtime/HIL evidence:** ROSIDL generation, message/QoS/frame/freshness/provenance integration, runtime behavior, HIL, hardware, and deployment evidence remain separate and unclaimed.

Under active ACR3, any required pin or evidence that is missing, unresolved, unsupported by exact authority, or still required as `PENDING_MEASUREMENT` makes the dependent profile ineligible. The compiler must reject the entire resolved config and emit neither a partial `ResolvedConfig` nor a partial `config_hash`. This record creates no resolved profile instance and does not start or pass Gate B.

## 5. Candidate and status boundary

This source-selection record, its Registry entry, and its Ledger entry are candidate-only pending focused independent audit, separate User authorization for the exact final commit, fast-forward, and remote-ref verification. The existing receipt v2/QoS6 pins remain active at the base; this candidate does not newly activate them or any other source.

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
