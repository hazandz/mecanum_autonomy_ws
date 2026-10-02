# A0.5.2 V3 Canonical YAML Migration Readiness

**Trạng thái:** `DOCUMENTATION_ONLY — FIELD_LEVEL_TRACEABILITY — RUNTIME NOT APPROVED`  
**Phạm vi:** A0.5.2.0 chỉ đánh giá tĩnh; không migrate YAML, không gọi compiler, không construct `ResolvedConfigV3`, không hash và không resolve token.

## 1. Evidence inventory

| Evidence | Kết luận | Lớp |
| --- | --- | --- |
| `docs/MECANUM_NAV_DRL_Architecture.docx` SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860` | Hash authority đã khớp; schema 3.0, D03, D05, TF/GT/safety, token và deploy-real constraints là yêu cầu khóa. | `ARCHITECTURE_TARGET` |
| `docs/A0_5_V3_Canonical_Composable_Layer_ADR.md` | D01–D08 và D09-B khóa canonical boundaries; A0.5.2 cần prompt implementation riêng. | `ARCHITECTURE_TARGET` |
| `v3_models.py`, `v3_composition.py`, `v3_loader.py`, `v3_validators.py` | Model có 7 ownership groups, primitive nhận đúng 7 mapping in-memory, loader chỉ parse/copy mapping; không có asset grouping/path API. | `SOURCE_IMPLEMENTATION` |
| `test_config_v3_assets.py`, A0.4 record | 15 assets được kiểm parse/install trong evidence offline trước đây; evidence không chứng minh canonical composition. | `OFFLINE_EVIDENCE` |
| ROS/Gazebo/training/hardware | Không được chạy trong increment này và không có evidence mới. | `RUNTIME_EVIDENCE` |

15 asset hiện có là: `base.yaml`; bốn `profiles/*.yaml`; bốn `modes/*.yaml`; `topics.yaml`; `qos.yaml`; `frames.yaml`; `acceptance.yaml`; `measurements.yaml`; `algorithms/ppo.yaml`.

`setup.py` liệt kê đúng 15 asset trong bốn install destinations dưới `share/mecanum_nav_rl/config/v3/`: root (6), `profiles/` (4), `modes/` (4), `algorithms/` (1). Đây là package-install boundary hiện có, không phải grouping manifest/path-list. Kết luận này là `SOURCE_IMPLEMENTATION`.

## 1.1 A0.5.2.0.1 metric correction

### Asset status theo intended role

| Asset | Intended role | Fragment target hoặc catalog-only | Status chính xác | Kỳ vọng thành complete D08 fragment? |
| --- | --- | --- | --- | --- |
| `base.yaml` | Base configuration | `BASE` | Fragment-target incomplete | Có |
| `profiles/sim_train.yaml` | Sim-train profile | `RUNTIME_PROFILE` | Fragment-target incomplete | Có |
| `profiles/sim_eval.yaml` | Sim-eval profile | `RUNTIME_PROFILE` | Fragment-target incomplete | Có |
| `profiles/deploy_sim.yaml` | Deploy-sim profile | `RUNTIME_PROFILE` | Fragment-target incomplete | Có |
| `profiles/deploy_real.yaml` | Deploy-real profile | `RUNTIME_PROFILE` | Fragment-target incomplete | Có |
| `modes/local_training.yaml` | Local-training navigation mode | `NAVIGATION_MODE` | Fragment-target incomplete | Có |
| `modes/mapping.yaml` | Mapping navigation mode | `NAVIGATION_MODE` | Fragment-target incomplete | Có |
| `modes/nav2_baseline.yaml` | Nav2-baseline navigation mode | `NAVIGATION_MODE` | Fragment-target incomplete | Có |
| `modes/hybrid_ai_local.yaml` | Hybrid navigation mode | `NAVIGATION_MODE` | Fragment-target incomplete | Có |
| `topics.yaml` | Topic contract source | `TOPICS_QOS` | Fragment-target incomplete | Có |
| `qos.yaml` | QoS catalog source | `CATALOG_ONLY` | Intentional catalog-only exclusion | Không |
| `frames.yaml` | Frame/TF contract source | `FRAMES` | Fragment-target incomplete | Có |
| `acceptance.yaml` | Acceptance contract source | `SYSTEM_CONTRACTS` | Fragment-target incomplete | Có |
| `measurements.yaml` | Measured-registry pointer catalog | `CATALOG_ONLY` | Intentional catalog-only exclusion | Không |
| `algorithms/ppo.yaml` | Training contract source | `SYSTEM_CONTRACTS` | Fragment-target incomplete | Có |

**Reproducible status metric:** `13/13 fragment-target assets are incomplete for complete D08 composition.` `2/15 assets are intentional CATALOG_ONLY inputs.` `qos.yaml` và `measurements.yaml` không phải failed D08 fragments.

### Metric DIRECT_STRUCTURAL_COPY

Một **field-group** là đúng một raw leaf hoặc contiguous raw subtree trong một asset, có cùng canonical target path và có thể copy nguyên trạng mà không rename, default, alias conversion, name inference hoặc join. Field-group partial vẫn không biến asset thành complete fragment.

| ID | Asset path | Raw key/path → canonical target path | Lý do direct structural copy |
| --- | --- | --- | --- |
| DSC-01 | `base.yaml` | `schema_version` → `schema_version` | Cùng scalar architecture literal. |
| DSC-02 | `base.yaml` | `observation` → `observation` | Cùng subtree D05; không đổi tên hay bổ sung field. |
| DSC-03 | `base.yaml` | `action` → `action` | Cùng subtree action; không đổi tên hay bổ sung field. |
| DSC-04 | `profiles/sim_train.yaml` | `runtime.runtime_profile` → cùng path | Cùng D03 literal. |
| DSC-05 | `profiles/sim_train.yaml` | `runtime.use_sim_time` → cùng path | Cùng boolean D03. |
| DSC-06 | `profiles/sim_eval.yaml` | `runtime.runtime_profile` → cùng path | Cùng D03 literal. |
| DSC-07 | `profiles/sim_eval.yaml` | `runtime.use_sim_time` → cùng path | Cùng boolean D03. |
| DSC-08 | `profiles/deploy_sim.yaml` | `runtime.runtime_profile` → cùng path | Cùng D03 literal. |
| DSC-09 | `profiles/deploy_sim.yaml` | `runtime.use_sim_time` → cùng path | Cùng boolean D03. |
| DSC-10 | `profiles/deploy_real.yaml` | `runtime.runtime_profile` → cùng path | Cùng D03 literal. |
| DSC-11 | `profiles/deploy_real.yaml` | `runtime.use_sim_time` → cùng path | Cùng boolean D03. |
| DSC-12 | `modes/local_training.yaml` | `runtime.navigation_mode` → cùng path | Cùng D03 literal. |
| DSC-13 | `modes/mapping.yaml` | `runtime.navigation_mode` → cùng path | Cùng D03 literal. |
| DSC-14 | `modes/nav2_baseline.yaml` | `runtime.navigation_mode` → cùng path | Cùng D03 literal. |
| DSC-15 | `modes/hybrid_ai_local.yaml` | `runtime.navigation_mode` → cùng path | Cùng D03 literal. |
| DSC-16 | `frames.yaml` | Existing `frames_tf` literals → corresponding `frames_tf` paths | Các literal frame/authority hiện có giữ tên/path; missing GT field được ghi blocker riêng. |
| DSC-17 | `algorithms/ppo.yaml` | `training.algorithm_id` → cùng path | Cùng algorithm literal; contract hash không được suy ra. |

**Reproducible total:** `DIRECT_STRUCTURAL_COPY = 3 + (4 × 2) + 4 + 1 + 1 = 17`, tương ứng DSC-01 đến DSC-17. Bất kỳ field không nằm trong danh sách này phải giữ transformation class hiện có hoặc là `UNVERIFIED`; không được suy ra direct-copy từ report cũ.

## 2. Field-level mapping từng asset

Một mục `DIRECT_STRUCTURAL_COPY` chỉ có nghĩa raw field-group có thể được copy cùng tên/path, không cần rename, default, alias conversion, name inference hoặc join. Nó không đồng nghĩa asset đã là fragment hoàn chỉnh hoặc resolved config.

| Asset path | Raw key/path hiện có → canonical target field path | Target D08 | Transformation class | Token/provenance boundary | Status và blocker | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `base.yaml` | `schema_version`, `observation`, `action` → cùng path | `BASE` | `DIRECT_STRUCTURAL_COPY` | Không resolve token trong các phần này | Partial only; `project`/`provenance` còn token | Asset + `ResolvedConfigV3` |
| `base.yaml` | `project.*`, `provenance.resolution_policy_id`, `provenance.source_manifest_sha256` → cùng path | `BASE` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` | `FIXED_ARCH`/`REQUIRED_BUILD_INPUT` | Không là resolved fragment | Asset + token policy |
| `base.yaml` | `map_identity.source_root` | `CATALOG_ONLY` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | Không phải `MapIdentityV3` field | Không đưa vào resolved payload | Asset + model |
| `base.yaml` | `map_identity.map_id`, `canonical_manifest_sha256`; thiếu `artifact_contract_id` | `BASE` | `NOT_MIGRATABLE_IN_A0_5_2` | Build tokens preserved only before resolution | Thiếu required canonical field; không tự bổ sung | Asset + model |
| `profiles/sim_train.yaml` | `runtime.runtime_profile`, `runtime.use_sim_time` → cùng path | `RUNTIME_PROFILE` | `DIRECT_STRUCTURAL_COPY` | Không resolve | Partial only | Asset + D03 model |
| `profiles/sim_train.yaml` | `motion_limits.*` token objects | `RUNTIME_PROFILE` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` | `SIM_BASELINE` | Không là resolved motion limits | Asset + token policy |
| `profiles/sim_train.yaml` | `runtime.allowed_navigation_modes` | `CATALOG_ONLY` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | D03 validates explicit pair only | Metadata, không auto-select | Asset + D03 decision |
| `profiles/sim_eval.yaml` | `runtime.runtime_profile`, `runtime.use_sim_time` → cùng path | `RUNTIME_PROFILE` | `DIRECT_STRUCTURAL_COPY` | Không resolve | Partial only | Asset + D03 model |
| `profiles/sim_eval.yaml` | `motion_limits.*` token objects; `allowed_navigation_modes` | `RUNTIME_PROFILE` / `CATALOG_ONLY` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` / `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | `SIM_BASELINE`; mode metadata outside payload | Không là complete fragment | Asset + D03/D07 |
| `profiles/deploy_sim.yaml` | `runtime.runtime_profile`, `runtime.use_sim_time` → cùng path | `RUNTIME_PROFILE` | `DIRECT_STRUCTURAL_COPY` | Không resolve | Partial only | Asset + D03 model |
| `profiles/deploy_sim.yaml` | `motion_limits.*`; `allowed_navigation_modes` | `RUNTIME_PROFILE` / `CATALOG_ONLY` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` / `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | `TBD_MEASURED`; registry remains external | No registry wrapper/value | Asset + D04/D07 |
| `profiles/deploy_real.yaml` | `runtime.runtime_profile`, `runtime.use_sim_time` → cùng path | `RUNTIME_PROFILE` | `DIRECT_STRUCTURAL_COPY` | Deploy-real remains non-ready | Partial only | Asset + D03 model |
| `profiles/deploy_real.yaml` | `motion_limits.*`; `required_build_inputs`; `allowed_navigation_modes` | `RUNTIME_PROFILE` / `CATALOG_ONLY` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` / `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | `TBD_MEASURED`/`REQUIRED_BUILD_INPUT`; D03 metadata | No wrapper; required inputs not resolved payload | Asset + D03/D04/D07 |
| `modes/local_training.yaml` | `runtime.navigation_mode` → cùng path | `NAVIGATION_MODE` | `DIRECT_STRUCTURAL_COPY` | Explicit selected mode only | Navigation body still blocked | Asset + D03 model |
| `modes/local_training.yaml` | `navigation.local_controller_owner`, `path_planner_owner` | `NAVIGATION_MODE` | `NOT_MIGRATABLE_IN_A0_5_2` | Fixed/token pre-resolution only | Alias shape; thiếu full `NavigationContractV3` | Asset + model/D02 |
| `modes/mapping.yaml` | `runtime.navigation_mode` → cùng path | `NAVIGATION_MODE` | `DIRECT_STRUCTURAL_COPY` | Explicit selected mode only | Navigation body still blocked | Asset + D03 model |
| `modes/mapping.yaml` | `navigation.local_controller_owner`, `path_planner_owner` | `NAVIGATION_MODE` | `NOT_MIGRATABLE_IN_A0_5_2` | Fixed/token pre-resolution only | Alias shape; thiếu full `NavigationContractV3` | Asset + model/D02 |
| `modes/nav2_baseline.yaml` | `runtime.navigation_mode` → cùng path | `NAVIGATION_MODE` | `DIRECT_STRUCTURAL_COPY` | Explicit selected mode only | Navigation body still blocked | Asset + D03 model |
| `modes/nav2_baseline.yaml` | `navigation.local_controller_owner`, `path_planner_owner` | `NAVIGATION_MODE` | `NOT_MIGRATABLE_IN_A0_5_2` | Contract IDs absent | Alias shape; thiếu full `NavigationContractV3` | Asset + model/D02 |
| `modes/hybrid_ai_local.yaml` | `runtime.navigation_mode` → cùng path | `NAVIGATION_MODE` | `DIRECT_STRUCTURAL_COPY` | Explicit selected mode only | Navigation body still blocked | Asset + D03 model |
| `modes/hybrid_ai_local.yaml` | `navigation.local_controller_owner`, `path_planner_owner`, `local_reference_owner` | `NAVIGATION_MODE` | `NOT_MIGRATABLE_IN_A0_5_2` | Contract IDs absent | Alias shape; thiếu full `NavigationContractV3` | Asset + model/D02 |
| `topics.yaml` | `topic_contracts.*` | `TOPICS_QOS` | `REQUIRES_EXPLICIT_RELATION` | Topic tokens remain pre-resolution | Không có full `TopicQosContractV3` hoặc relation QoS | Asset + model/D01 |
| `qos.yaml` | `qos_contracts.*` | `CATALOG_ONLY` | `REQUIRES_EXPLICIT_RELATION` | QoS tokens remain pre-resolution | Không có approved relation/order tới topics | Asset + model/D01 |
| `frames.yaml` | frame names + two literal authorities → same `frames_tf.*` paths | `FRAMES` | `DIRECT_STRUCTURAL_COPY` | `map_to_odom_authority` token pre-resolution | Partial; thiếu GT isolation policy ID | Asset + model |
| `frames.yaml` | `map_to_odom_authority`; missing `ground_truth_isolation_policy_id` | `FRAMES` | `REQUIRES_NEW_AUTHORITY` | Token/ID only before resolution | Required model field source missing | Asset + model/GT invariant |
| `acceptance.yaml` | `acceptance.contract_id`, `contract_sha256` token objects | `SYSTEM_CONTRACTS` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` | `TBD_PROJECT_ACCEPTANCE` | `SYSTEM_CONTRACTS` also lacks four other fields | Asset + model |
| `measurements.yaml` | `measured_registry.*` | `CATALOG_ONLY` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | External registry + approval provenance only | Not an `ApprovedMeasuredRegistryV3` wrapper | Asset + D04 |
| `algorithms/ppo.yaml` | `training.algorithm_id` → same path | `SYSTEM_CONTRACTS` | `DIRECT_STRUCTURAL_COPY` | No value inference | Partial only | Asset + model |
| `algorithms/ppo.yaml` | `training.contract_sha256` token | `SYSTEM_CONTRACTS` | `EXPLICIT_TOKEN_PRESERVED_PRE_RESOLUTION` | `FIXED_ARCH` pre-resolution | No resolved hash | Asset + token policy |
| `algorithms/ppo.yaml` | `observation_action_contract.*` | `CATALOG_ONLY` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | D03 metadata | Must not enter resolved payload | Asset + D03 |

Đếm metric authoritative cho report này ở §1.1: `DIRECT_STRUCTURAL_COPY = 17` qua DSC-01…DSC-17. Chỉ `13/13` fragment-target asset incomplete; `2/15` asset là `CATALOG_ONLY` intentional exclusion và không được đếm là failed D08 fragment.

## 3. Bảy primitive inputs D08

| Input | Có thể tạo structural mapping chỉ từ explicit path hiện hữu? | Asset/key đóng góp theo evidence | Missing/collision | Token trước resolution | Cần quyết định Architect/User? |
| --- | --- | --- | --- | --- | --- |
| `BASE` | Không hoàn chỉnh | `base.yaml` schema/observation/action; tokenized project/provenance | `source_root` catalog-only; thiếu `artifact_contract_id` | Có | Cần source/authority cho artifact contract, không tự tạo |
| `FRAMES` | Không hoàn chỉnh | `frames.yaml: frames_tf.*` | Thiếu `ground_truth_isolation_policy_id` | Có | Cần authority/source cho policy ID |
| `TOPICS_QOS` | Không | `topics.yaml: topic_contracts.*`; `qos.yaml: qos_contracts.*` | Relation, full record fields và canonical order đều `MISSING_EVIDENCE` | Có | Cần explicit relation/order; D01 không cho inference |
| `STATE_LOCALIZATION` | Không | Không có asset canonical | Cả `state_estimation` lẫn `localization` absent | Không có evidence token source | Cần source/authority; không thiết kế hộ |
| `SYSTEM_CONTRACTS` | Không hoàn chỉnh | `acceptance.yaml: acceptance`; `algorithms/ppo.yaml: training` | Thiếu `command_safety`, `reward`, `evaluation`; metadata PPO catalog-only | Có | Cần canonical sources/authority, không tự bổ sung |
| `RUNTIME_PROFILE` | Không hoàn chỉnh | Một profile explicit: runtime + motion tokens | Catalog `allowed_navigation_modes` tách; no resolved limits/wrapper | Có | D03/D07 ownership locked; wrapper/provenance still missing |
| `NAVIGATION_MODE` | Không hoàn chỉnh | Một mode explicit: `runtime.navigation_mode` | Navigation aliases không full `NavigationContractV3` | Có | D02 shape locked; exact IDs vẫn missing authority |

Không có collision structural giữa selected profile `runtime.runtime_profile`/`use_sim_time` và selected mode `runtime.navigation_mode` nếu input fragments canonical đã tồn tại; tuy nhiên current assets chưa là fragments canonical. Không asset nào được thêm field để che các thiếu hụt trên.

## 4. Topics/QoS evidence

Không có evidence static cho một relation explicit topic ↔ QoS giữa `topics.yaml.topic_contracts` và `qos.yaml.qos_contracts`. Không có canonical order cho `topics_qos`. Cả hai kết luận là `MISSING_EVIDENCE`. D01 khóa tuple direct ở resolved boundary, nhưng không cấp relation/order để dựng tuple. Suy ra quan hệ từ tên `scan`, `heartbeat`, `final_command`, vị trí file hoặc convention là bị cấm.

## 5. Metadata và envelope boundary

| Item | Static classification | Kết luận |
| --- | --- | --- |
| `allowed_navigation_modes` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | D03 metadata, không auto-select mode. |
| PPO `observation_action_contract` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | Không thuộc `TrainingContractV3`; không vào resolved payload. |
| `required_build_inputs` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | Không có model field/envelope path được định nghĩa; deploy-real input remains pre-resolution. |
| `map_identity.source_root` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | Không thuộc `MapIdentityV3`; map artifact identity cần fields model-owned. |
| `measurements.yaml` | `CATALOG_ONLY_OUTSIDE_RESOLVED_PAYLOAD` | D04 pointer catalog, không phải wrapper. |

Nếu cùng YAML cần đồng thời payload fragment và catalog metadata, hiện không có envelope/field path tường minh được định nghĩa trong source/ADR. Kết luận là `REQUIRES_ARCHITECT_USER_DECISION`; report không thiết kế envelope.

## 6. Blockers và quyết định cần thiết

| Blocker | Evidence | Impact | Exact architect/user decision required |
| --- | --- | --- | --- |
| `STATE_LOCALIZATION` | Không có asset trong 15-file tree; primitive yêu cầu `state_estimation` + `localization`. | Không thể tạo input thứ tư. | Chỉ rõ canonical source asset/path và field ownership, hoặc cho phép asset mới trong scope riêng. |
| `SYSTEM_CONTRACTS` thiếu ba field | Chỉ `training` và `acceptance` hiện diện. | Không thể tạo input thứ năm. | Chỉ rõ canonical source/asset path cho `command_safety`, `reward`, `evaluation`; không chọn literal. |
| Direct `topics_qos` | Hai source separate, không relation/order/full record. | Không thể tạo input thứ ba. | Khóa relation explicit, canonical record order và source ownership. |
| Full `NavigationContractV3` | Mode YAML dùng aliases thay sáu model fields. | Không thể tạo input thứ bảy. | Cấp authority cho exact canonical field mapping/IDs hoặc typed tokens. |
| Grouping manifest/path-list | D09-B yêu cầu future explicit caller list nhưng location, shape, package boundary chưa có source. | Không có permitted grouping implementation surface. | Chỉ rõ location, schema, install/package ownership và caller API scope. |
| Token/wrapper/provenance | Registry is pointer; build/acceptance/project tokens unresolved. | Không resolved config/hash/deploy-real. | Chỉ rõ wrapper/manifest authority source; không fabricate registry/provenance. |

## 7. Fail-closed conclusion

Có thể migrate mà không bịa dữ liệu chỉ là các **raw direct structural field-groups** đã đếm ở §2; chúng không đủ để tạo bất kỳ complete D08 fragment. Không asset nào hiện được phép migrate thành complete `BASE`, `FRAMES`, `TOPICS_QOS`, `STATE_LOCALIZATION`, `SYSTEM_CONTRACTS`, `RUNTIME_PROFILE` hoặc `NAVIGATION_MODE` mapping.

Chưa có đủ canonical source mappings để populate bảy input D08 thành complete fragments. Điều kiện tối thiểu trước prompt A0.5.2 là các quyết định cụ thể ở §6, đặc biệt source state/localization, ba system-contract fields, direct topics/QoS relation/order, full navigation shape, và grouping manifest/path-list boundary. Token/wrapper/provenance phải vẫn fail-closed.

`A0.5.2 YAML MIGRATION BLOCKED — MISSING_EVIDENCE/DECISION REQUIRED`

`RUNTIME NOT APPROVED`

`A0.5.2.0.1 COMPLETE — DOCUMENTATION ONLY`  
`A0.5.2 YAML MIGRATION NOT STARTED`  
`RUNTIME NOT APPROVED`
