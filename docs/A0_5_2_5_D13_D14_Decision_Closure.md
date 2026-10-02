# A0.5.2.5 — D13/D14 Canonical Migration Decision Closure

**Trạng thái:** `PENDING_ARCHITECT_USER_SELECTION — DOCUMENTATION ONLY — RUNTIME NOT APPROVED`

## 1. Authority và truth layers

`docs/MECANUM_NAV_DRL_Architecture.docx` đã được xác minh SHA-256:

```text
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

| Truth layer | Điều được dùng trong decision closure | Điều không được suy ra |
| --- | --- | --- |
| `ARCHITECTURE_TARGET` | D03 caller-explicit profile/mode; D05/D2/token rules; GT isolation; TF ownership; FinalTwistPublisher là publisher duy nhất `/cmd_vel`; model shape V3. | Topic/QoS records, owner, contract ID, token provenance, threshold, hoặc runtime value chưa có authority. |
| `SOURCE_IMPLEMENTATION` | `TopicQosContractV3` và `NavigationContractV3` hiện có; `topics.yaml`, `qos.yaml`, và bốn mode YAML hiện có không phải direct canonical mapping complete; selection giữ opaque paths. | YAML mới, relation/order canonical, full navigation mapping, grouping/extraction, compiler integration. |
| `OFFLINE_EVIDENCE` | Các docs readiness/packet ghi asset/model boundary và prior offline test evidence. | Bất kỳ bằng chứng runtime hoặc việc D13/D14 đã được chọn. |
| `RUNTIME_EVIDENCE` | Không có bằng chứng mới. | Tính đúng runtime, Gazebo/ROS graph, hardware, deploy-real readiness, hay authority cho values. |

Không có runtime evidence được tạo hoặc kiểm tra trong increment này.

## 2. D13 — canonical `topics_qos`

`TopicQosContractV3` yêu cầu một record direct có các field model-owned: `name`, `message_type`, `publisher_owner`, `subscriber_owner`, `qos_profile_id`, `frame_contract_id`, `freshness_policy_id`. Đây là field shape, không phải values được điền trong tài liệu này.

| Option | Canonical semantic owner của từng record | Vai trò `topics.yaml` / `qos.yaml` sau migration | Target tree còn đúng 17 assets? | Cần asset mới ngoài hai source D11/D12? | Explicit relation/order | Rủi ro bị cấm | Evidence còn thiếu |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D13-A | Một direct canonical record source trong `topics.yaml`; mỗi record sở hữu trọn vẹn semantic topic/QoS contract. | `topics.yaml` mang direct records; `qos.yaml` chỉ catalog-only khi direct source khác đã được phê duyệt. | Có. | Không. | Tuple/list record được author theo thứ tự explicit trong chính direct source. | Cấm join `topic_contracts` và `qos_contracts` bằng name, file order, alias hoặc convention; cấm auto-discovery và duplicate authority. | Toàn bộ record values, exact order, token boundary, provenance và chứng cứ one-authority. |
| D13-B | Một asset tuple canonical riêng sở hữu từng direct record. | Cả `topics.yaml` và `qos.yaml` là catalog-only. | Không; cần amendment vì vượt target 17. | Có, một asset canonical tuple ngoài D11/D12. | Asset mới biểu diễn record ordered tường minh. | Không được join catalog bằng tên/alias/order; cấm duplicate authority với catalog. | Asset path/package-install decision, record values/order/tokens/provenance. |
| D13-C | Một relation source explicit sở hữu association và order; record source phải được quyết định tường minh cùng relation source. | Vai trò hai catalog chỉ có thể giữ catalog-only sau khi có direct record source được phê duyệt. | Chưa xác định; không thể khẳng định target 17 nếu không biết relation source đặt ở đâu. | Có thể có; cần authority riêng nếu relation/direct source không nằm trong asset hiện có. | Relation biểu diễn record association và order trực tiếp, không bằng naming convention. | Cấm name-based join, alias, implicit file order, auto-discovery và duplicate authority. | Location/schema/owner của relation và direct record source; values/order/tokens/provenance. |

Mọi option D13 đều cấm join `topic_contracts` và `qos_contracts` bằng tên, thứ tự file, alias hoặc convention. `qos.yaml` chỉ được giữ `CATALOG_ONLY` nếu một canonical direct record source khác đã được Architect/User phê duyệt.

### Approval worksheet D13

Architect/User phải chọn **đúng một**: `D13-A`, `D13-B`, hoặc `D13-C`; đồng thời khóa canonical semantic owner của từng record, role hậu-migration của `topics.yaml`/`qos.yaml`, source path, representation explicit relation/order, tree impact, và typed pre-resolution token boundary. Chưa có option nào được chọn trong document này.

## 3. D14 — canonical `NavigationContractV3`

Mỗi navigation mapping complete phải có đầy đủ field shape: `planner_owner`, `controller_owner`, `path_validity_contract_id`, `local_reference_contract_id`, `goal_type`, `goal_settle_contract_id`. Tên field là model shape hiện có; document này không tạo value, ID, owner hay token cụ thể.

| Option | Canonical semantic owner | Tác động tới bốn mode asset hiện có | Target tree 17 assets | D03 caller-explicit / fail-closed | Full field shape, evidence và token boundary | Rủi ro bị cấm |
| --- | --- | --- | --- | --- | --- |
| D14-A | Mỗi mode asset là owner của full `NavigationContractV3` ứng với chính mode đó. | Bốn mode YAML được migrate từ alias hiện có thành mapping complete theo model shape. | Có. | Caller vẫn chọn một profile và một mode; `RuntimeSelectionV3` chỉ validate pair, không auto-select mode. | Cần sáu field cho từng mode. Hiện chỉ có mode literal và owner-like aliases ở source; các field/values/IDs chưa có authority là `MISSING_EVIDENCE` hoặc typed pre-resolution token sau authority. | Cấm alias, default, inferred field, fabricated contract ID, auto-selection và runtime mapping. |
| D14-B | Mỗi mode dùng một source navigation canonical riêng, owner tách khỏi mode asset. | Mode YAML giữ mode identity; cần bốn source navigation riêng hoặc authority equivalent. | Không; cần amendment vì thêm source ngoài target 17. | Selection profile/mode vẫn caller-explicit; no fallback or inferred source choice. | Cần sáu field trên từng source. Existing mode aliases không chứng minh mapping/values; token boundary và provenance còn thiếu. | Cấm filename-based source selection, aliases/defaults, fabricated IDs và duplicate semantic authority. |
| D14-C | Caller-supplied external canonical navigation fragment là owner cho mode đã chọn. | Mode YAML có thể chỉ giữ identity; external source boundary phải được quyết định riêng. | Có thể vẫn 17 package assets, nhưng external boundary không có authority/source implementation hiện tại. | Caller phải pass selection tường minh; D03 chỉ validate profile/mode pair, không chọn external fragment. | Cần sáu field per selected mode; current evidence không cấp values/IDs. Exact typed-token boundary/provenance và caller API cần authority. | Cấm inferred fragment from mode name/path, auto-selection, aliases/defaults, fabricated IDs và compiler/runtime integration. |

### Approval worksheet D14

Architect/User phải chọn **đúng một**: `D14-A`, `D14-B`, hoặc `D14-C`; đồng thời khóa canonical semantic owner, exact source mapping/path per mode, tree impact, six-field mapping, typed pre-resolution token boundary, và provenance responsibility. Chưa có option nào được chọn trong document này.

## 4. Exact unblock contract

| Input bắt buộc sau lựa chọn D13/D14 | Prompt YAML migration phải nhận tường minh | Evidence còn thiếu không được bịa | File được phép sửa/tạo trong prompt tương lai | Vẫn bị cấm |
| --- | --- | --- | --- | --- |
| D13 option đã phê duyệt | Option, canonical owner, direct source mapping/path, relation/order representation, role hậu-migration của `topics.yaml` và `qos.yaml`. | Record values, QoS/topic details, owner/contract IDs, token provenance chưa được authority cấp. | Chỉ asset/source paths được option đã chọn và prompt riêng liệt kê; mọi asset mới phải phù hợp D06 target 17 hoặc amendment explicit. | Name/file-order/alias/convention join, auto-discovery, defaults, compiler/runtime integration. |
| D14 option đã phê duyệt | Option, canonical owner, mapping/path cho từng mode, sáu model fields, caller-explicit profile/mode selection. | Values/IDs, token provenance, model content evidence chưa được authority cấp. | Chỉ mode/source paths được option đã chọn và prompt riêng liệt kê; tree impact phải khớp D06 hoặc amendment explicit. | Auto-select mode/source, aliases/defaults, fabricated IDs, compiler/runtime integration. |
| Canonical field ownership | One semantic authority for every direct field, D10 envelope boundary nếu asset mixed-role, D11/D12 source locks, D15 caller selection boundary. | Nested semantic ownership, model-shape content, grouping/extraction details. | Các YAML đã được quyết định và chỉ trong migration prompt riêng. | Token resolution, hash, `ResolvedConfigV3` construction, loader/compiler change. |
| Explicit ordering/selection | Direct record order D13; caller profile/mode selection D03; explicit source paths only. | Any missing relation/order or source selection semantics. | Không file nào ngoài scope prompt riêng. | Scan filesystem, fallback, name inference. |
| Typed pre-resolution token boundary | Field-level token class/reference/provenance from authority. | Mọi token/value/registry/provenance concrete chưa được cấp. | Không tự tạo token data ngoài prompt/authority sau. | Resolve token, hash, deploy-real enablement, runtime. |

Chỉ sau khi Architect/User chọn D13 và D14, một prompt A0.5.2 YAML migration riêng mới có thể định rõ source mapping và file scope. Lựa chọn đó không tự cấp compiler integration, token resolution, hashing, `ResolvedConfigV3` construction, grouping/extraction, hoặc runtime authority.

```text
A0.5.2 YAML MIGRATION REMAINS BLOCKED PENDING ARCHITECT_USER_SELECTION OF D13 AND D14
NO YAML, SOURCE, TEST, OR RUNTIME IMPLEMENTATION WAS PERFORMED
RUNTIME NOT APPROVED
```
