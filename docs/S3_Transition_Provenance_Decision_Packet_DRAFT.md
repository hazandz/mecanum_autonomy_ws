# S3 Transition Provenance Decision Packet

Status: **DRAFT — PENDING_USER_APPROVAL**

Phạm vi: decision packet cho `sim_train` để ràng buộc facts của **một** transition trước khi triển khai reward, termination hoặc runtime. Đây không phải Architecture Change Record, user đã chọn D2-B/D3-B chỉ cho core-only implementation; chưa phê duyệt runtime D2/D3 hoặc chứng minh runtime producer đã tồn tại. `RESET_ABORT`/`STEP_ABORT` không phải Gym transition; command đã publish và va chạm vật lý không thể rollback.

## Authority và trạng thái evidence

- [Architecture authoritative](MECANUM_NAV_DRL_Architecture.docx), schema `3.0`, reward `reward-v3-baseline`, SHA-256 `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860`: §§16–23 khóa ContactLatch, exact/barrier synchronization, transactional reset, transition commit, previous-issued command, reward và terminal precedence.
- [S3 design draft](S3_Episode_Reward_Termination_Design_DRAFT.md): registry D1–D10 và same-transition provenance. Tài liệu đó vẫn `DRAFT — PENDING_USER_APPROVAL`.
- [ACR S1](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md) `APPROVED`: quyền dùng hidden Ground Truth cho oracle/reward/termination, nhưng cấm raw GT và object reachable từ GT đi vào policy.
- [ACR S2](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md) `DRAFT — PENDING_USER_APPROVAL`: exact-only có approval **core-only** riêng; receive-age, ingress identity, buffers/overflow và runtime barrier owner chưa được duyệt.
- [Lifecycle core](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/episode_lifecycle.py), [transition skeleton](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/transition.py), [terminal enums](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/enums.py), [previous-action history](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/actions/previous_action_history.py) và [exact pair gate](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/synchronizer.py) là implementation evidence, **không** là runtime/approval evidence.

## 1. Baseline core đã có

| Fact | Owner hiện tại và field | Bất biến core đã test | Chưa chứng minh được |
| --- | --- | --- | --- |
| `EpisodeLifecycleIdentity` | `EpisodeLifecycle`: `episode_generation`, `reset_epoch`, `runtime_generation` | Integer không âm, không nhận bool; stale/future generation bị từ chối; reset mới tăng generation/epoch | Runtime owner và nguồn của epoch/generation, relation với command/contact producer |
| Exact scan–odom provenance | `ExactSnapshotPairGate` với caller-injected metadata; lifecycle nhận `ExactObservationProvenance(identity, scan_timestamp_ns, odometry_timestamp_ns, observation_timestamp_ns)` | `VALID`, lifecycle/barrier khớp và ba stamp bằng nhau; 1 ns skew không READY | Runtime ingress, receive-age, buffer/overflow; pair thuộc đúng command receipt/transition nào |
| Reset reward baseline | `EpisodeLifecycle` nhận `ResetCommitCandidate`, commit `CommittedRewardBaseline(identity, observation_provenance, previous_goal_distance_m, previous_committed_sim_time_ns)` | Distance finite/không âm; time khớp observation0; abort không giữ baseline cũ; reset mới clear state | TaskOracle thực, observed simulator reset và provenance oracle tại observation0 |
| `TransitionIdentity` | `EpisodeLifecycle`: caller-supplied lifecycle identity, positive `step_index`, non-empty `transition_id` | Immutable; reject bool/NaN/implicit conversion; active-token and committed-token replay checks | Runtime token producer, cross-process uniqueness and action interval |
| `CommandReceiptSnapshot` | `EpisodeLifecycle`: `transition_identity`, `receipt_id`, normalized test-only `final_issued_command` | Receipt token phải khớp active step; receipt ID đã commit không replay; abort không consume | Publish thật, final physical command, action barrier và physical-to-normalized mapping |
| `ContactCandidateSnapshot` | `EpisodeLifecycle`: `transition_identity`, `event_id` | Token khớp active step; stage không consume; duplicate/đã consume bị từ chối; commit consume một lần; abort giữ unconsumed; reset clear | Event thuộc action interval thật hay pulse cũ; ContactLatch runtime và contact-source evidence |
| Consumed receipt/contact/token IDs | `EpisodeLifecycleSnapshot`: `consumed_receipt_ids`, `consumed_contact_event_ids`, `committed_transition_ids` | Chỉ advance ở successful step commit, không ở abort; reset generation mới xóa | Cross-process durability và runtime mapping sang source producers |

`TransitionContext` hiện có `previous_applied_command`/`applied_command` và `delta_time_s`, nhưng không mang receipt, oracle/contact/clearance provenance. Tên `applied` ở skeleton không phải bằng chứng actuator đã áp dụng; không được dùng nó để vượt qua D2/D3. `PreviousActionHistory` hiện lưu decoder-accepted PPO action, **không** phải final issued command theo Architecture §20.

## 2. D2 — Final issued command receipt

Một transition phải tách sáu giá trị/sự kiện dưới đây. Không được dùng sự tồn tại của giá trị trước làm bằng chứng cho giá trị sau.

| Tầng | Ý nghĩa | Evidence hiện tại |
| --- | --- | --- |
| PPO desired action | Raw normalized `[vx, vy, wz]` do policy đề xuất | Input của decoder, chưa được chấp nhận |
| Decoder-accepted command | Action validated và desired physical `VelocityCommand` từ decoder | Core-only; chưa gửi command |
| SafetySupervisor/final-limiter command | Command sau arbitration/limit/smoothing tại safety boundary | Runtime producer chưa có |
| Final issued command | Lệnh cuối đã được FinalTwistPublisher publish theo architecture | Runtime producer/receipt chưa có; không đồng nghĩa actuator acknowledgement |
| Receipt sau publish | Bằng chứng có thể kiểm tra rằng đúng final command của active transition đã đi qua final publish boundary | `CommandReceiptSnapshot` hiện là **test-only fact**, không chứng minh publish |
| Measured twist | Vận tốc robot đo từ policy-safe odometry | Observation measurement; không chứng minh command đã issue hay motor đạt vận tốc |

Kiến trúc khóa *previous issued* là final limited/published command, không phải desired hoặc measured twist. Sau D2 approval, previous-command observation và reward smoothness chỉ được nhận normalized **final issued** command từ receipt hợp lệ và commit cùng transition. Quy tắc chuyển final physical command về normalized value, axis limits/version, zero/limiter handling và observation schema/hash/checkpoint migration vẫn cần quyết định; không clamp âm thầm và không tái dùng decoder-ready history như receipt. Đổi producer dù vector vẫn 3 phần tử là đổi observation semantics/hash.

### D2 lựa chọn định danh receipt

**D2-B: `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`.** D2-A không được chọn cho increment này. Core nhận token do caller cấp; token producer, final-publish receipt và action barrier runtime vẫn `NOT_IMPLEMENTED`.

| Lựa chọn | Owner sinh ID | Chống replay/stale và relation với lifecycle | Evidence sau publish cần có | Giới hạn/rủi ro và hệ quả history/reward |
| --- | --- | --- | --- | --- |
| **D2-A:** `identity + step_index + unique receipt_id` | Episode coordinator cấp active identity/step; final-publish boundary cấp hoặc xác nhận receipt ID unique — owner chính xác phải duyệt | Core đã reject sai identity/step và replay ID đã commit **trong episode**; runtime phải chứng minh ID unique, bound với reset/runtime generation và không tái dùng sau restart | Receipt từ final publisher chứng minh final physical command, publisher/boundary, publish completion, action ROS-time barrier và liên hệ với step đang chờ | Bộ ba ID chưa tự chứng minh thời điểm publish/action interval hay source sequence; aborted receipt cần diagnostic riêng. Chỉ receipt đã được validate và transition commit mới update previous-issued/smoothness history |
| **D2-B:** explicit `transition_id` do episode/runtime owner sinh trước submit | Episode/runtime transition coordinator là owner duy nhất; final-publish boundary echo/bind token trong receipt | Token phải unique trong lifecycle, không tái dùng qua reset/runtime generation; reject token cũ/sai và receipt duplicate; vẫn kiểm tra identity, step, source/lifecycle | Receipt sau publish phải bind token với final physical command và action barrier của đúng transition | Thêm contract producer/propagation; token một mình không chứng minh publish hay freshness. History/reward chỉ commit khi receipt token khớp candidate và toàn bộ facts khác valid |

`receipt_id` có thể tiếp tục là identity của **một receipt**, còn `transition_id` (nếu chọn D2-B) là identity của **một transition**; không tự đồng nhất hai khái niệm. Không quyết định timeout, QoS, ROS topic, source-sequence format hoặc actuator acknowledgement ở packet này. Receipt chỉ xác nhận final publish boundary theo semantics được user duyệt, không xác nhận robot đã chuyển động.

## 3. D3 — Contact provenance

Contact candidate phải mang active `episode_generation/reset_epoch/runtime_generation`, gắn được với action interval của transition sắp commit, và chứng minh không phải pulse từ step/epoch trước. Architecture §16 khóa pulse latch: contact `true` rồi `false` trước tick vẫn phải hiện ở transition; silence không có nghĩa contact đã hết. Build transition chỉ **snapshot read-only**, reward/termination chỉ đọc snapshot; ContactLatch consume đúng một lần tại atomic commit thành công. `STEP_ABORT` vào `FAULT` không consume và không tạo Gym transition; reset/restart kế tiếp clear latch/state theo lifecycle mới, không rò pulse sang episode khác. Physical collision không thể rollback.

### D3 lựa chọn gắn event với transition

**D3-B: `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`.** D3-A không được chọn cho increment này. Core chỉ nhận immutable snapshot cùng active token; runtime snapshot owner, ContactLatch và contact source vẫn `NOT_IMPLEMENTED`.

| Lựa chọn | Owner và cách gắn | Evidence cần có | Giới hạn/rủi ro |
| --- | --- | --- | --- |
| **D3-A:** ContactLatch mang transition/step identity | Episode/runtime owner cung cấp active lifecycle + step/transition identity cho latch; latch tạo immutable event candidate với identity đó | Controlled pulse/sustained-contact tests; event timestamp/order so với action barrier; delayed old-epoch event bị reject; snapshot không consume, commit consume-once, abort/reset clear | Nếu identity được gắn lúc callback thay vì lúc action interval, event cũ có thể bị relabel; owner/ordering phải được duyệt |
| **D3-B:** Runtime owner snapshot contact bằng explicit transition token | Contact source/latch giữ event identity/lifecycle; episode coordinator lấy immutable snapshot cho token của transition hiện hành | Token từ cùng transition với receipt và exact pair; chứng minh event nằm trong interval; consume atomic theo token/event ID; duplicate/replay, short pulse và reset tests | Snapshot muộn hoặc không có temporal boundary có thể kéo pulse cũ sang step mới; token không tự thay thế contact-source health |

`ContactCandidateSnapshot(transition_identity, event_id)` core đã join được step/token, nhưng chưa có event timing hay action-interval proof. Việc thêm runtime producer, event timestamp/window, plugin, ROS node hay ContactLatch API nằm ngoài packet này. ACR S1 cho phép oracle đọc hidden GT nhưng không cho phép raw contact/GT object đi vào policy.

## 4. Quy tắc join tối thiểu cho một transition

Mọi fact chỉ được join sau khi cùng active lifecycle và cùng transition/action interval theo lựa chọn D2/D3 đã duyệt. Cùng ID **không** thay thế barrier, timestamp hay freshness checks. Simulation/ROS stamp và local steady receive time là hai domain khác nhau; không trừ chéo.

| Fact | Điều kiện bắt buộc để join | Trạng thái |
| --- | --- | --- |
| Exact observation | `VALID` policy-safe odometry; scan/odom/observation stamp bằng nhau, đúng epoch/generation, strictly sau action/reset ROS barriers; no GT fallback | Exact-pair semantics `IMPLEMENTED_CORE`; barrier/ingress/receive-age producer `REQUIRED_DECISION`, `RUNTIME_EVIDENCE_REQUIRED` |
| Final command receipt | Cùng lifecycle + step/token, receipt unique/not replayed, final command đúng final-publish boundary; receipt ROS barrier xác định interval của pair | Token/receipt replay guard `IMPLEMENTED_CORE`; publish receipt owner/schema/barrier `REQUIRED_DECISION`, producer `NOT_IMPLEMENTED` |
| Oracle goal distance | `previous_goal_distance_m` từ reset/step commit trước trong cùng episode; current derived distance finite/không âm, đúng task và current transition point, không raw GT đi vào policy | Baseline validation `IMPLEMENTED_CORE`; TaskOracle/alignment `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| Contact | Immutable candidate đúng lifecycle và current action interval/token, event mới hoặc pending hợp lệ; read-only trước commit, consume-once tại commit | Core token match/stage/consume `IMPLEMENTED_CORE`; event interval provenance/latch producer `REQUIRED_DECISION`, `NOT_IMPLEMENTED`, `RUNTIME_EVIDENCE_REQUIRED` |
| Future clearance | `c` có source/frame/time/footprint semantics được duyệt, cùng transition; `d_safe` có config/version hợp lệ | D10 `REQUIRED_DECISION`; source `NOT_IMPLEMENTED` |
| Sim time | Current simulation timestamp thuộc exact observation/current oracle point, lớn hơn previous committed simulation timestamp; `dt_sim_s` là hiệu dương cùng simulation domain, step đầu dùng reset baseline | Baseline/strict-increase guard `IMPLEMENTED_CORE`; runtime clock/oracle join `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |

Nếu một fact thiếu hoặc mismatch trước commit: `STEP_ABORT`/`FAULT`, không reward, termination hay fabricated Gym transition. Nếu command đã publish, zero/inhibit và recovery policy là quyết định runtime riêng; transaction không rollback command đã issue.

## 5. Hệ quả và phạm vi increment sau

**Core-only đã được user chọn:** D2-B/D3-B cho phép immutable `TransitionIdentity`, token join và replay/stale/reset/abort tests bằng test-only facts. Chúng không chứng minh same-transition runtime provenance. Có thể chuẩn bị contract cho previous-issued history mà không coi decoder-ready action là final-issued. Không tự thêm runtime publisher, ContactLatch hoặc reward/termination evaluator chỉ vì packet được duyệt.

**Vẫn bị chặn:** D6 chưa có numeric step/sim-time limits; D10 chưa có clearance source/`d_safe`. ACR S2 runtime vẫn thiếu receive-age, buffer capacity/overflow, ingress IDs và barrier sources. D2/D3 approval cũng không thay thế TaskOracle, final-publish receipt, contact-source, simulator reset và fault-injection runtime evidence. Full reward-v3 evaluator và termination/runtime integration chỉ bắt đầu khi các input/decision phụ thuộc tương ứng đã được duyệt; không bỏ term hoặc bịa numeric value.

Increment này sửa [`core/episode_lifecycle.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/episode_lifecycle.py) và tests. [`core/transition.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/core/transition.py) vẫn giữ nguyên vì migration applied-command sang issued receipt chưa an toàn. Increment sau có thể ảnh hưởng [`actions/previous_action_history.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/actions/previous_action_history.py) hoặc issued-command history owner mới (semantics), [`observations/synchronizer.py`](../ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/synchronizer.py) (chỉ sau ACR S2 runtime approval), cùng tests tương ứng. Runtime Safety/FinalTwistPublisher, TaskOracle và ContactLatch là future components, **không** được tạo từ packet này.

## 6. Checklist để user duyệt

- [x] **D2 core-only:** user chọn D2-B explicit `transition_id`; core kiểm tra token nhưng chưa chứng minh command đã publish.
- [ ] Chốt runtime owner sinh/propagate `transition_id`, uniqueness scope và relation với reset/runtime generation.
- [ ] Định nghĩa “issued receipt” tại final-publish boundary: evidence sau publish, final physical/normalized command, action barrier và fail/replay handling; **không** gọi là actuator acknowledgement.
- [x] **D3 core-only:** user chọn D3-B, runtime owner snapshot contact theo cùng token; core chỉ validate test-only candidate.
- [ ] Chốt runtime owner gắn event với action interval và cách loại pulse cũ.
- [ ] Chốt reset/abort: contact snapshot không consume trước commit; `STEP_ABORT` vào `FAULT`, clear latch/history ở reset mới; command đã publish không rollback; zero/inhibit/restart owner cần approval riêng.
- [ ] Chốt runtime evidence trước reward/termination runtime: publish receipt và wrong-generation/replay tests; controlled contact pulse/sustained/reset tests; exact-pair/barrier/freshness tests; TaskOracle/clearance/time provenance và fault-injection.

Chỉ hai lựa chọn core-only được đánh dấu theo user instruction. Runtime D2/D3 và các dependency khác vẫn **PENDING_USER_APPROVAL**; token producer, final-publish receipt và ContactLatch vẫn `NOT_IMPLEMENTED`.
