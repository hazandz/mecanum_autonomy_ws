# PEP-001 Amendment Proposal — WP-04 V3 Contract Primitives

**Status:** `DRAFT_FOR_INDEPENDENT_ARCHITECTURE_AUDIT`\
**Date:** `2026-10-04`\
**Applies to:** proposed revision of `PEP-001`, currently `0.1.0`\
**Repository evidence:** `origin/integration/implementation@afa23732fb6a74beafceec21c2319a52f5f87b3f`\
**PEP header authority at that ref:** `docs/governance/PROJECT_EXECUTION_PLAN.md` metadata: Plan ID `PEP-001`, Revision `0.1.0`\
**Architecture authority:** `MECANUM_NAV_DRL_Architecture(4).docx`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`\
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Purpose and decision boundary

This is a proposal to clarify the first constrained deliverable *inside the
existing* `WP-04-POLICY-CORE-P0`. It does not create `WP-05A` or any other new
work-package ID.

It is not a code prompt, branch authorization, source change, test permission,
runtime approval, or PEP revision with canonical force. The current canonical
PEP remains unchanged until this proposal passes independent audit and is
accepted through the required integration workflow.

The PEP metadata above is quoted from the PEP header at the stated evidence
ref. A later PEP integration packet must re-read that header on its exact base
and stop if its Plan ID or current revision differs; it must not assume that
`PEP-001`/`0.1.0` remains current.

## 2. Why the amendment is needed

The approved V3 scope closure separates two activities that must not be mixed:

1. define immutable V3 contract primitives; and
2. later attach those primitives to `ResolvedConfigV3`, compiler, hash and
   authoritative profiles in one atomic migration.

Making `observation_input` mandatory in `ResolvedConfigV3` now would invalidate
the existing complete config constructions while this scope forbids profile
migration. Therefore the first deliverable is deliberately non-integrated.

## 3. Proposed PEP metadata change

| PEP field | Current | Proposed after audit and user approval |
| --- | --- | --- |
| Plan ID | `PEP-001` | unchanged |
| Revision | `0.1.0` | `0.2.0` |
| Work-package IDs | existing list | unchanged; no `WP-05A` |
| WP-04 status | `BLOCKED_BY_CONTRACT` | unchanged in this amendment |

The revision increases because the plan gains a governed, narrower WP-04
deliverable and explicit gates. It does not alter frozen architecture semantics
or any public ROS contract.

## 4. Exact proposed replacement for the WP-04 row

Replace only the `WP-04-POLICY-CORE-P0` row in the ordered-work-packages table
with the following row:

| Order | ID | Scope | Depends on | Initial status |
| --- | --- | --- | --- | --- |
| 04 | `WP-04-POLICY-CORE-P0` | V3 policy-observation core. First constrained deliverable: non-integrated immutable V3 contract primitives — `ObservationCutoffV3` core type/validation and `ObservationInputContractV3` structural models. Any LiDAR/LocalReference normalization, final-issued receipt integration, V3 assembler/encoder, compiler/profile closure or runtime bridge requires a separate independently approved implementation packet. | WP-03; user-approved V3 scope closure; semantic bundle closure for S2 rev.2, Observation Input Contract rev.6 and V3 Observation Boundary rev.7; separate exact implementation packet | `BLOCKED_BY_CONTRACT` |

The original WP-04 identity, ordering and dependency on WP-03 are preserved.
The status remains `BLOCKED_BY_CONTRACT`: this amendment neither treats a draft
design as code authority nor transitions WP-04 to an implementable state.

## 5. Proposed new PEP subsection after the work-package table

### WP-04 constrained first deliverable — V3 immutable contract primitives

This deliverable is a narrowed part of `WP-04`, not a sub-package and not a
separate canonical ID.

It may define only:

1. `ObservationCutoffV3` as an immutable V3 core type with structural,
   fail-closed validation. The type does not generate barriers, cut-off time,
   lifecycle identity, receipt or configuration hash.
2. `ObservationInputContractV3` as immutable structural model shapes for
   validated input variants and exact S2/receipt contract references.

Ownership remains explicit:

| Concern | Owner | Constraint |
| --- | --- | --- |
| Action/reset barriers | `SafetyLifecycle` | sole producer of barrier values |
| One observation cut-off per transition | `RobotRuntimeAdapter.wait_transition_snapshot(after=receipt)` | sole operational creator; it supplies facts to the type |
| Type shape and invariant validation | V3 core primitive module | no ROS/DDS/runtime behavior |
| Input-model structure | V3 non-integrated structural model module | no profile resolution or compiler ownership |

The first deliverable must not modify or add:

- `ResolvedConfigV3`, raw V3 configuration inputs, loader, compiler,
  composition, normal config hash calculation, YAML or any resolved profile;
- ROS nodes/messages, ROSIDL, QoS, TF, DDS, sensor adapters, `/cmd_vel` or
  other runtime code;
- S2 buffers/synchronizer, LiDAR sectorizer, V3 assembler, encoder or 81D
  observation vector construction;
- final-issued receipt interface, topic bridge, history implementation or
  safety/final-publisher implementation;
- V1 observation, decoder, history or snapshot code, including aliases,
  wrappers, fallback or deletion.

Test fixtures for the future implementation packet are structural in-memory
data only. They are not profile values, provenance evidence, hardware
measurements, `deploy_sim`/`deploy_real` configuration or runtime evidence.

## 6. Required gates and dependency evidence

| Gate | Required evidence | Effect on WP-04 |
| --- | --- | --- |
| Scope closure | `V3_PURE_PYTHON_WORK_PACKAGE_READINESS_REVIEW` rev.3 accepted by independent audit and approved by the user | narrows the first deliverable; does not unblock code |
| Semantic bundle | User decision for S2 rev.2, Observation Input Contract rev.6 and V3 Observation Boundary rev.7, recorded in their governing documents without hash/semantic drift | closes the observation meaning required before any implementation packet |
| PEP amendment | This proposal independently audited, then accepted as a reviewed PEP revision | creates canonical governance traceability only |
| Implementation packet | A separate exact packet that names branch/base, allowed files, static checks, unit-test permission and report requirements | only possible source-edit authorization |

At the time this draft is written, no source-edit packet is authorized. WP-04
must remain `BLOCKED_BY_CONTRACT` until semantic-bundle closure is recorded and
a separate implementation packet is approved.

## 7. Plan-change-control record for a later canonical update

| Required PEP change-control item | Proposed record |
| --- | --- |
| Plan ID and revision | `PEP-001`, `0.1.0 → 0.2.0` |
| Exact status transition | No WP-04 status transition: `BLOCKED_BY_CONTRACT → BLOCKED_BY_CONTRACT` |
| Work package, branch, base SHA, commit SHA | `WP-04-POLICY-CORE-P0`; no branch/base/commit exists for this draft. The later PEP integration packet must supply all three. |
| Dependency/evidence impact | Adds explicit scope-closure, semantic-bundle and implementation-packet gates; retains WP-03 dependency. |
| Architecture/ACR impact | No architecture change. The final-issued receipt ACR/QoS bundle has separate authority and is unchanged. S2 rev.2, Observation Input Contract rev.6 and V3 Observation Boundary rev.7 remain a semantic gate; this proposal does not claim them approved or closed. It creates no topic, QoS, TF, schema or safety change. |
| Ledger entry | Append only in the later PEP integration work package; this draft does not update the ledger. |
| User approval | Required after independent audit and before PEP integration. |

## 8. Independent-audit questions

The independent reviewer must verify that this proposal:

1. preserves the canonical `WP-04-POLICY-CORE-P0` ID and creates no hidden
   sub-package;
2. does not accidentally authorize code or change the blocked status;
3. does not pull compiler/profile closure, ROS/QoS/TF, S2, assembler, encoder,
   receipt interface or V1 work into the first deliverable;
4. assigns `ObservationCutoffV3` type validation separately from operational
   barrier/cut-off ownership; and
5. retains the requirement for a separate, exact implementation packet after
   semantic closure.

## 9. Final state

`PEP_AMENDMENT_PROPOSAL: DRAFT_FOR_INDEPENDENT_ARCHITECTURE_AUDIT`\
`WP-04: BLOCKED_BY_CONTRACT`\
`CODE_AUTHORIZATION: NOT_GRANTED`\
`RUNTIME_NOT_APPROVED`
