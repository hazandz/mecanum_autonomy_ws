# A0.5.2 — Canonical Asset Decision Packet

**Status:** `D10-A/D11-A/D12-B/D15-B IMPLEMENTED_CORE_ONLY — D13–D14 PENDING_ARCHITECT_USER_APPROVAL`  
**Phạm vi:** D11-A/D12-B khóa hai future source paths trong caller-owned immutable selection API; D10-A envelope và D15-B selection vẫn core-only. Không tạo/migrate YAML, grouping/extraction, package installation, loader, composition, compiler, hashing, resolved-config construction, runtime hay architecture authority change.

## 1. Evidence snapshot

The authoritative architecture DOCX was read and its SHA-256 is verified as:

```text
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

The current read-only inventory and the A0.5.2.0.1 readiness report establish:

- `13/13` fragment-target assets are incomplete for complete D08 composition.
- `2/15` assets are intentional `CATALOG_ONLY` inputs: `qos.yaml` and `measurements.yaml`.
- There are `17` reproducible `DIRECT_STRUCTURAL_COPY` field-groups, identified as `DSC-01` through `DSC-17`; the count is `3 + (4 × 2) + 4 + 1 + 1 = 17`.
- D08 defines exactly seven composition inputs. The gap is not an eighth input: there are not yet sufficient canonical source mappings to populate those seven inputs as complete fragments.

This snapshot is `SOURCE_IMPLEMENTATION` and `OFFLINE_EVIDENCE` only. It is not `RUNTIME_EVIDENCE`; no runtime, Gazebo, ROS, bridge, controller, or hardware conclusion follows from it.

## 2. Decision worksheet

All decisions below remain pending. The listed questions must be answered explicitly by Architect/User before an implementation prompt can be written for the affected YAML migration work.

| ID | Status | Decision to lock | Minimum answer required |
| --- | --- | --- | --- |
| D10 | `APPROVED_BY_ARCHITECT_USER — OPTION D10-A` | Canonical asset envelope | Core-only `CanonicalV3AssetEnvelope` có đúng hai vùng raw `fragment`/`catalog`; one top-level semantic owner, không implicit extraction, loading, resolution, hashing, compiler hay `ResolvedConfigV3`. |
| D11 | `APPROVED_BY_ARCHITECT_USER — OPTION D11-A` | Future canonical `STATE_LOCALIZATION` source | Path `config/v3/state_localization.yaml` được khóa cho YAML migration riêng sau; selection API chỉ giữ opaque path, không tạo/đọc asset. |
| D12 | `APPROVED_BY_ARCHITECT_USER — OPTION D12-B` | Future canonical `SYSTEM_CONTRACTS` source | Path `config/v3/system_contracts.yaml` được khóa cho ba field `command_safety`, `reward`, `evaluation`; selection API chỉ giữ opaque path, không tạo/đọc asset. |
| D13 | `PENDING_ARCHITECT_USER_APPROVAL` | Canonical `topics_qos` | Explicit topic-to-QoS relation, canonical order, and source semantic authority. |
| D14 | `PENDING_ARCHITECT_USER_APPROVAL` | `NavigationContractV3` migration | Exact canonical field mapping for every mode and which fields remain typed pre-resolution tokens. |
| D15 | `APPROVED_BY_ARCHITECT_USER — OPTION D15-B` | D09-B caller-owned explicit selection/path-list | API core-only bất biến nhận một runtime/profile-mode selection tường minh và các opaque asset path bắt buộc; không package-owned manifest, scan, filename inference, load, composition, token resolution, hashing, compiler hay `ResolvedConfigV3`. |

## 3. Options and trade-offs

Every option in this section is a possible future direction, not a recommendation, selection, approval, or architecture authority. D01–D09 remain locked, including D03 catalog-only mode and PPO metadata, D04 measurement catalog handling, D05 non-self-referential hash rule, D08 structural base-side order, and D09-B explicit caller-supplied structural grouping.

### D10 — Envelope asset with fragment and catalog metadata

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D10-A | Permit a YAML envelope with an explicitly named fragment payload and an explicitly named catalog-only payload. | Preserves one semantic authority only if each field has one declared owner. The grouping layer may extract only the declared fragment subtree; it may not rename, default, infer, or consume catalog metadata. The 15-asset tree and install list could remain unchanged, but the envelope path and package boundary require authority. Future compiler scope remains excluded. |
| D10-B | Keep fragment payload and catalog metadata in separate assets or explicit external inputs. | Makes the D09-B structural boundary direct and avoids an envelope extraction rule. It can require a tree/install change if a new asset is introduced. Tokens remain fail-closed and catalog data cannot enter a resolved payload. Future compiler work remains separately scoped. |
| D10-C | Prohibit mixed fragment/catalog assets for canonical migration. | Enforces a strict one-role-per-input rule and may require restructuring the current tree, affecting D06/D09-B scope and package installation. It does not create missing canonical fields or permit compiler integration. |

**SOURCE_IMPLEMENTATION đã có:**

- `CanonicalV3AssetEnvelope`;
- exact root paths `fragment` và `catalog`;
- reject root extra, both-empty envelope, invalid key và duplicate top-level key;
- không có implicit extraction/loading/resolution.

**MISSING_EVIDENCE vẫn còn:**

- semantic field ownership dưới top-level key;
- content/model-shape validation;
- grouping/extraction implementation;
- D13–D14 decisions.

### D11 — Canonical source for `STATE_LOCALIZATION`

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D11-A | Add an explicitly owned canonical state/localization asset. | Gives the two D08 fields one visible semantic authority, but changes the present 15-asset tree and package-install inventory. The asset must provide model-complete mappings or typed tokens; grouping may only structurally map it. |
| D11-B | Assign two explicit, disjoint existing-asset paths to `state_estimation` and `localization`. | Retains the tree only if exact paths already have authority. It must not split fields by filename convention or infer ownership. Tokens remain fail-closed; any missing model field remains a blocker. |
| D11-C | Require caller-supplied external canonical fragment input outside the packaged tree. | Keeps package assets unchanged but requires an approved caller boundary, provenance treatment, and explicit path selection. It does not authorize path discovery, token resolution, or `ResolvedConfigV3` construction. |

**SOURCE_IMPLEMENTATION đã có:** caller selection nhận `state_localization_path` tường minh cho future source `config/v3/state_localization.yaml`.

**MISSING_EVIDENCE vẫn còn:** YAML source chưa tồn tại; semantic ownership/content/model-shape của `state_estimation` và `localization`; typed token/provenance; grouping/extraction implementation.

### D12 — Sources for `command_safety`, `reward`, and `evaluation`

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D12-A | Create three explicitly owned canonical sources, one for each missing top-level field. | Keeps ownership granular and avoids duplicate authority, but changes the 15-asset tree and package-install inventory. Each source must be model-complete or carry typed unresolved tokens without defaults. |
| D12-B | Create one explicitly owned canonical `system_contracts` source containing the three missing fields. | Centralizes the missing `SYSTEM_CONTRACTS` content, but requires a precise non-overlap rule with existing `training` and `acceptance` assets. It changes tree/install scope and permits no hidden merge behavior. |
| D12-C | Require three caller-supplied external canonical fragment inputs. | Avoids altering packaged assets, while requiring explicit caller ownership, selection, provenance, and package boundary decisions. It cannot fabricate values, wrappers, receipts, or Gate evidence. |

**SOURCE_IMPLEMENTATION đã có:** caller selection nhận `system_contracts_path` tường minh cho future source `config/v3/system_contracts.yaml`; source đó được khóa sở hữu `command_safety`, `reward`, `evaluation`.

**MISSING_EVIDENCE vẫn còn:** YAML source chưa tồn tại; content/model values, typed token/provenance và grouping/extraction implementation. D2 receipt vẫn là external `command_safety` contract.

### D13 — Canonical `topics_qos`

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D13-A | Author an ordered canonical tuple source whose records contain the complete topic/QoS contract. | Provides direct `topics_qos` records and one semantic authority. It may restructure `topics.yaml`, affect the 15-tree/install layout, and must use an explicit approved order rather than inferred names. |
| D13-B | Add a separate canonical tuple asset while retaining current topic and QoS catalogs as catalog-only inputs. | Avoids joining the current files and preserves their catalog roles, but changes the tree/install inventory. No duplicate semantic authority is allowed between the tuple and catalog entries. |
| D13-C | Define an explicit relation table with exact records and order, supplied as an approved structural input. | May preserve existing catalog assets, but the relation table needs an approved owner, location, package boundary, and schema. It must express records directly; name-based joining, aliases, and implicit ordering remain prohibited. |

**MISSING_EVIDENCE:** The present `topics.yaml` and `qos.yaml` do not establish an approved explicit relation, canonical tuple order, or complete source semantic authority for `TopicQosContractV3` records.

### D14 — Migration of `NavigationContractV3`

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D14-A | Make every mode asset contain its full canonical `NavigationContractV3` mapping. | Keeps navigation visibly co-located with a mode but requires field-complete, exact mappings for each mode. Mode selection remains caller-explicit under D03; no auto-selection, aliases, defaults, or invented owner/contract IDs are permitted. |
| D14-B | Keep mode assets for the mode key and add explicitly owned per-mode navigation contract sources. | Separates catalog/mode identity from the full contract, making ownership clearer but potentially changes the tree/install inventory. Grouping can only structurally combine declared disjoint descendants. |
| D14-C | Require caller-supplied explicit navigation contract fragments for each selected mode. | Retains current packaged mode assets while moving contract provenance and path selection to an approved caller boundary. It cannot resolve typed tokens, create a runtime profile, or invoke the compiler. |

**MISSING_EVIDENCE:** Current navigation assets are not full `NavigationContractV3` sources. Exact fields, owners, contract IDs, and the boundary between canonical literals and typed pre-resolution tokens have not been supplied.

### D15 — D09-B grouping manifest/path-list

**Decision lock:** `APPROVED_BY_ARCHITECT_USER — OPTION D15-B`. A0.5.2.2 chỉ hiện thực input contract bất biến do caller sở hữu. Nó không phải grouping manifest, filesystem reader, loader, composition adapter, compiler integration hay content-semantic validator.

| Option | Shape | Impact and constraints |
| --- | --- | --- |
| D15-A | Add a package-owned explicit grouping manifest that names every selected asset path and target fragment. | Gives a reviewable packaged contract and has package-install impact. Its schema must prohibit scanning, name inference, defaults, field renaming, topic/QoS joining, token resolution, hashing, and compiler calls. |
| D15-B | Define a caller API that receives an explicit typed path-list/selection without a packaged manifest. | Keeps grouping ownership at the caller boundary but requires an approved API, selection format, ownership, and install responsibility. The caller must select exactly one profile and one mode; D03 validates a pair only and does not choose one. |
| D15-C | Define an explicitly versioned external manifest supplied by the caller. | Keeps package source unchanged while requiring authority for storage, provenance, installation/availability, and the exact API boundary. It must map only the seven locked D08 inputs and fail closed for missing or conflicting paths. |

**SOURCE_IMPLEMENTATION đã có:** D15-B caller API `ExplicitV3AssetSelection` nhận 11 opaque paths và một D03-validated runtime selection; nó không scan, load hay suy diễn semantic path.

**MISSING_EVIDENCE vẫn còn:** grouping manifest/path-list location, grouping schema, package-install ownership, explicit structural extraction và content-semantic validation. `setup.py` inventory chỉ chứng minh installability hiện có; không phải grouping manifest.

## 4. Conditions to unlock an A0.5.2 implementation prompt

| Planned YAML action | Required approved decisions | Evidence required before prompt | Still prohibited in that prompt |
| --- | --- | --- | --- |
| Migrate a mixed-role asset into a fragment/catalog boundary | implemented D10-A envelope model, D15-B selection boundary | Exact owned field paths, token boundary, caller-provided explicit grouping selection | Auto-discovery, renaming, defaults, inferred joins, token resolution, compiler integration, hashing, `ResolvedConfigV3`, runtime. |
| Populate `STATE_LOCALIZATION` | implemented D11-A source path and D15-B selection boundary | Complete model mapping source(s), ownership, typed unresolved inputs, explicit path mapping | Fabricated state/localization fields, wrapper construction, runtime use. |
| Populate missing `SYSTEM_CONTRACTS` fields | implemented D12-B source path and D15-B selection boundary | Canonical sources for `command_safety`, `reward`, `evaluation`, ownership, typed tokens | D2 receipt fabrication, safety/reward/evaluation values, compiler or runtime integration. |
| Populate `TOPICS_QOS` | D13, D15 | Explicit topic-to-QoS records, canonical order, semantic authority | Name inference, convention-based joins, aliases, runtime topic changes. |
| Populate `NAVIGATION_MODE` fully | D14, D15 | Exact field mapping per mode and typed token boundary | Auto mode selection, invented IDs, navigation runtime integration. |
| Compose all seven D08 inputs as complete canonical fragments | implemented D10-A envelope model, D11-A source path, D12-B source path, D13, D14, plus implemented D15-B API, as applicable to every source | All relevant mappings above, one semantic authority per field, caller-provided explicit selection, manifest/path-list boundary evidence | Compiler integration, path discovery, token resolution, hash integration, `ResolvedConfigV3` construction, ROS/Gazebo/hardware/runtime work. |

D10-A, D11-A, D12-B và D15-B chỉ được hiện thực ở core input boundaries. Chỉ sau khi D13–D14 liên quan tới YAML action dự kiến được Architect/User quyết định tường minh thì mới có thể viết prompt implementation A0.5.2 riêng. Prompt đó vẫn chỉ giới hạn ở canonical YAML migration và không thể mở rộng sang grouping/extraction, compiler integration, token resolution, hashing, `ResolvedConfigV3` construction hay runtime activity.

## 5. Explicitly outside A0.5.2

The following require later increments and are not decisions forced by this packet:

- Concrete approved-registry/wrapper values and approval provenance.
- Concrete provenance and hash values.
- Concrete acceptance and Gate 4 values.
- D2 receipt values and S2, D6, or D10 numeric/timing values.
- Runtime, Gazebo, bridge, `/cmd_vel`, guard, collector, or hardware evidence.

All existing invariants remain unchanged: D03 catalog metadata stays outside resolved composition payload; D05 config hashing is non-self-referential and only applies to a normalized fully resolved payload; ground truth stays isolated; TF authority remains locked; FinalTwistPublisher remains the only `/cmd_vel` publisher; and `deploy_real` remains non-ready.

```text
A0.5.2.1 COMPLETE — DECISION PACKET ONLY
A0.5.2 YAML MIGRATION BLOCKED PENDING ARCHITECT_USER_DECISIONS
RUNTIME NOT APPROVED
```
