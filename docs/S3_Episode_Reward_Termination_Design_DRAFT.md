# S3 Episode Lifecycle Reward And Termination Design Draft

Status: `DRAFT — PENDING_USER_APPROVAL`

Scope: thiết kế `sim_train` cho episode lifecycle, reward và termination. Tài
liệu này không tạo hoặc phê duyệt runtime, Gymnasium environment, Gazebo reset,
command publisher hay PPO training.

Authority và precedence:

1. [`MECANUM_NAV_DRL_Architecture.docx`](MECANUM_NAV_DRL_Architecture.docx) là
   file kiến trúc authoritative duy nhất được `AGENTS.md` và workspace
   hiện hành chỉ định.
2. [`ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md`](ACR_S1_Simulated_Odometry_And_Ground_Truth_Isolation.md)
   có status `APPROVED`; approval này chỉ khóa quyền và ranh giới dùng
   Ground Truth đã ghi trong ACR S1.
3. [`ACR_S2_Snapshot_Synchronization_Temporal_Contract.md`](ACR_S2_Snapshot_Synchronization_Temporal_Contract.md)
   vẫn là `DRAFT — PENDING_USER_APPROVAL`, và
   [`S2_Snapshot_Synchronization_Approval_Packet.md`](S2_Snapshot_Synchronization_Approval_Packet.md)
   vẫn là `PENDING_USER_APPROVAL`. Source/test exact-pair không tự thay đổi
   hai status này.
4. User instruction khởi động Phase S.2.2A.0 là evidence phê duyệt hẹp
   cho **core-only** `exact_timestamp_only` với `sync_tolerance_ns = 0` và
   test-only metadata. Nó không phê duyệt freshness, buffer, overflow,
   runtime ingress, Gazebo/Gym integration hay toàn bộ ACR S2.
5. Source thực tế chỉ là implementation evidence. Build/test pass không tự
   biến design, ACR hay runtime integration thành approved.

### Provenance của architecture và reward schema

| Thuộc tính | Giá trị đã đối chiếu |
| --- | --- |
| Authoritative path | `/home/hazan/mecanum_autonomy_ws/docs/MECANUM_NAV_DRL_Architecture.docx` |
| Tính duy nhất | `AGENTS.md` chỉ định đúng path trên; audit `docs/` chỉ thấy một file `MECANUM_NAV_DRL_Architecture*.docx` |
| Document status/date | `ARCHITECTURE_FROZEN \| IMPLEMENTATION_READY \| NOT_YET_REAL_ROBOT_VALIDATED`; ngày phát hành `16/09/2026` |
| System/config schema | `schema_version: "3.0"` |
| Observation/action schema | `obs-v3-l72-g3-t3-c3-f32`; `action-v3-holonomic-f32` |
| Reward schema | `reward-v3-baseline` |
| SHA-256 | `f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860` |

Workspace hiện hành không có authority thứ hai mang
`reward-v2.3-baseline`. Vì vậy S3 đối chiếu `reward-v3-baseline`; bản
v2.3 cũ, nếu từng xuất hiện ngoài workspace, không được dùng làm
authority. Hash trên nhận diện chính xác bytes của file đã audit; nếu
DOCX thay đổi thì S3 phải audit lại provenance trước implementation.

## 1. Trạng thái audit và thuật ngữ

Tài liệu dùng các nhãn sau, không suy diễn qua lại giữa chúng:

- `IMPLEMENTED_CORE`: source core-only thực tế tồn tại và có test tương
  ứng; không chứng minh runtime producer, lifecycle hay integration.
- `APPROVED_FOR_CORE`: user hoặc authority đã phê duyệt phạm vi core-only
  được nêu cụ thể; không mở rộng sang runtime.
- `PROPOSED_FOR_RUNTIME`: thiết kế runtime được khuyến nghị nhưng chưa
  được phê duyệt/triển khai.
- `REQUIRED_DECISION`: chưa được phép triển khai phần phụ thuộc cho
  đến khi có quyết định và evidence được chỉ rõ.
- `NOT_IMPLEMENTED`: không có producer/runtime thực tế; test fixture không
  được dùng để đổi nhãn này.

### 1.1 Evidence source thực tế

| Hạng mục | Evidence thực tế | Trạng thái |
| --- | --- | --- |
| Noisy simulated odometry | `simulation/simulated_odometry.py` — `SimulatedOdometryEmulator`, `GroundTruthSample`, `SimulatedOdometrySnapshot` | `IMPLEMENTED_CORE`; runtime Gazebo ingress chưa có |
| Exact pairing | `observations/synchronizer.py` — tên thực tế `ExactSnapshotPairGate`, không phải runtime `SnapshotSynchronizer` | `IMPLEMENTED_CORE`; exact-only được `APPROVED_FOR_CORE` bằng user instruction S.2.2A.0; ACR S2/runtime vẫn pending |
| Observation assembly | `observations/assembly.py` — `ObservationAssembler` | `IMPLEMENTED_CORE`, output 81 phần tử khi input hợp lệ |
| PPO action decode | `actions/ppo_decoder.py` — `PpoActionDecoder` | `IMPLEMENTED_CORE`, không publish command |
| Previous action history | `actions/previous_action_history.py` — `PreviousActionHistory` | `IMPLEMENTED_CORE`, nhưng semantics hiện là decoder-accepted PPO action; chưa phải authoritative final issued command |
| Core transition | `core/transition.py` — `TaskState`, `TransitionContext` | Skeleton `IMPLEMENTED_CORE`; chưa đủ oracle/collision/command-receipt provenance cho reward v3 |
| Core outcomes | `core/enums.py` — `TerminationReason`, `TruncationReason` | Core partial; thiếu `STUCK`, chưa có manager/precedence implementation |
| Infrastructure failures | `core/exceptions.py` | Các type cơ bản `IMPLEMENTED_CORE`; chưa có runtime recovery owner |
| Gym environment | `mecanum_nav_rl/env/` | `NOT_IMPLEMENTED`: thư mục rỗng |
| Reward | `mecanum_nav_rl/rewards/` | `NOT_IMPLEMENTED`: thư mục rỗng |
| Termination | `mecanum_nav_rl/termination/` | `NOT_IMPLEMENTED`: thư mục rỗng |
| Task/oracle | `mecanum_nav_rl/tasks/` | `NOT_IMPLEMENTED`: thư mục rỗng |
| ROS/runtime adapters | `mecanum_nav_rl/ros/` | `NOT_IMPLEMENTED`: thư mục rỗng |
| Simulator reset/contact adapters | ngoài emulator, các file planned trong `simulation/` | `NOT_IMPLEMENTED` |
| Reward/termination config | `config/models.py`, `config/base.yaml`, `config/profiles/sim_train.yaml` | `NOT_IMPLEMENTED`: chưa có typed reward, time-limit, goal, collision hoặc lifecycle config |

### 1.2 Mâu thuẫn và khoảng trống phải giữ hiển thị

1. Kiến trúc định nghĩa observation block cuối là **previous command đã được
   SafetySupervisor chấp nhận/giới hạn và publish**, không phải actuator
   acknowledgement. `PreviousActionHistory` hiện cập nhật ngay từ
   `PpoActionDecodeResult.READY`. Hai semantics này không tương đương nếu
   adapter/publish/safety thất bại hoặc limiter thay đổi command.
2. `PreviousNormalizedCommand` mô tả command đã issued, nhưng producer hiện có
   chỉ biết decoder-accepted action. Runtime không được dùng producer này làm
   bằng chứng command đã issued nếu chưa có commit receipt.
3. `TransitionContext` hiện giữ `previous_applied_command` và
   `applied_command`, nhưng không có receipt chứng minh command đã publish,
   không có oracle goal distances, collision/contact state, clearance
   provenance hay terminal-event provenance.
4. Kiến trúc đã khóa `reward-v3-baseline` và termination precedence. Source
   config/runtime chưa triển khai các contract đó. Đây là implementation gap,
   không phải quyền tự chọn công thức mới.
5. ACR S1 `Migration Status` và ACR S2 `API impact` đã lỗi thời một phần so với
   source mới: emulator, exact pair gate và observation assembly hiện đã tồn
   tại. ACR S2 vẫn đúng ở điểm runtime sources, receive-age và bounded buffering
   chưa có.
6. Project Tree vẫn có một số entry planned mang tên khác source thực tế. Tài
   liệu này dùng tên source thật nêu trong bảng trên.

## 2. Data flow và ownership

### 2.1 Canonical proposed flow cho một step

```text
Policy observation 81-D
  -> PPO raw normalized action [vx, vy, wz]
  -> PpoActionDecoder
  -> decoded desired VelocityCommand
  -> future policy command adapter / CommandEnvelope
  -> SafetySupervisor validation and limiting
  -> FinalTwistPublisher / simulator actuator path
  -> explicit command commit receipt
  -> action ROS-time barrier

Hidden Gazebo Ground Truth ------------------------------+
  -> SimulatedOdometryEmulator -> policy-safe odometry   |
LiDAR -> RawLidarScan                                    |
  -> ExactSnapshotPairGate -> ObservationAssembler       |
  -> next policy observation 81-D                        |
                                                         |
Hidden task oracle --------------------------------------+
  -> goal/success/out-of-bounds facts                    |
Gazebo contact source -> ContactLatch -> collision fact  |
Committed transition inputs -----------------------------+
  -> TerminationEvaluator -> TerminationDecision
  -> RewardEvaluator -> RewardBreakdown
  -> atomic StepOutcome commit
```

### 2.2 Ownership table

| Dữ liệu | Owner/source | Consumer được phép | Consumer bị cấm | Trạng thái |
| --- | --- | --- | --- | --- |
| Observation 81-D | `ObservationAssembler` từ exact policy-safe pair, local goal và previous issued command | PPO policy | Reward/oracle dùng nó như authoritative Ground Truth | `IMPLEMENTED_CORE`; runtime source thiếu |
| Local goal feature | Future task/reference adapter; hiện chỉ có typed `LocalGoal2D` | `GoalFeatureExtractor`, policy observation | Reward dùng feature đã clip làm oracle success/distance | Producer `NOT_IMPLEMENTED` |
| PPO raw action | PPO/Gym caller | `PpoActionDecoder` duy nhất | History nhận raw action trực tiếp | Decoder `IMPLEMENTED_CORE` |
| Decoder-accepted normalized action | `PpoActionDecoder` sau validation | Core action flow, test-only `PreviousActionHistory` hiện tại | Tự được coi là lệnh đã issue | `IMPLEMENTED_CORE`; không phải runtime receipt |
| Desired physical velocity | `PpoActionDecoder` scale theo `MotionLimitsConfig` | Future command adapter | Tự được coi là published/applied | Value `IMPLEMENTED_CORE`; runtime path `NOT_IMPLEMENTED` |
| Final issued command | Future SafetySupervisor + FinalTwistPublisher commit receipt | Previous-issued-command history, reward smoothness, transition record | Suy diễn từ decoder `READY` | `NOT_IMPLEMENTED`, `REQUIRED_DECISION` về receipt/commit |
| Hidden Ground Truth pose | Gazebo hidden ingress | `SimulatedOdometryEmulator`, `TrainingTaskOracle`, reset validation, reward, success/termination, evaluator | PolicyNode, observation code, policy runtime, object reachable từ policy | Quyền truy cập đã được ACR S1 `APPROVED`; providers `NOT_IMPLEMENTED` |
| Policy pose/twist | `SimulatedOdometryEmulator` output | Synchronizer, observation feature extractors | Oracle dùng làm authoritative GT | `IMPLEMENTED_CORE` |
| Collision | Future Gazebo contact source + `ContactLatch` với reset epoch | Termination/reward oracle | Suy ra từ LiDAR silence hoặc raw contact object truyền vào policy | `NOT_IMPLEMENTED`; contact contract còn required build input |
| Clearance | Chưa có source authoritative đã nối vào transition | Reward safety term | Tự lấy một giá trị không có frame/provenance | `REQUIRED_DECISION` |
| Measured robot twist | `SimulatedOdometryMeasurement.vx_mps/vy_mps/wz_radps` trong policy-safe odometry | Measured-twist observation block; diagnostics | Dùng thay final issued command hoặc ngược lại | Extractor `IMPLEMENTED_CORE`; runtime ingress `NOT_IMPLEMENTED` |
| Reward | Future pure `RewardEvaluator/RewardManager` chỉ đọc immutable inputs cùng transition | Gym step result/logger | Đọc ROS callback/global mutable state | Formula/precedence khóa bởi architecture; implementation `NOT_IMPLEMENTED` |

### 2.3 Ground Truth isolation

ACR S1 có status `APPROVED` cho quyền dùng privileged Ground Truth cho reward,
success/termination, reset validation và evaluator. Vì vậy việc dùng Ground
Truth **không còn là REQUIRED_DECISION về quyền**. Việc chọn provider và typed
provenance cụ thể vẫn là `REQUIRED_DECISION` vì source runtime chưa tồn tại.

Oracle chỉ được truyền các derived immutable facts cần thiết, ví dụ
`previous_goal_distance_m`, `current_goal_distance_m`, `goal_reached`,
`out_of_bounds` và collision event. Nó không được truyền raw GT message, pose
object, buffer hoặc object graph có thể đi tới policy observation/runtime.

## 3. Episode lifecycle state machine

### 3.1 Proposed states

| State | Owner | Điều kiện vào | Điều kiện ra | Được phép | Bị cấm / failure behavior |
| --- | --- | --- | --- | --- | --- |
| `UNINITIALIZED` | Future `EpisodeLifecycleManager` | Env được tạo nhưng chưa reset thành công | `reset()` bắt đầu | Validate config/runtime readiness | `step()`, command publish, observation reuse |
| `RESETTING` | `ResetManager` transaction dưới lifecycle manager | Giữ reset lock; command sources inhibited | To `WAITING_FOR_INITIAL_OBSERVATION` chỉ sau simulator acknowledgement và state validation | Gửi/giữ zero, tăng lifecycle identifiers, clear caches, seed task/emulator, request reset | Policy action; coi service response là đủ; on failure -> `FAULT`/`RESET_ABORT` |
| `WAITING_FOR_INITIAL_OBSERVATION` | Reset manager + sensor adapter | Simulator mutation đã được xác nhận; barriers đã đặt | Exact valid observation0 đúng lifecycle và mới hơn barriers | Read sensors/oracle validation only | Nonzero command, old sample fallback; timeout/failure -> `FAULT` |
| `RUNNING` | Environment transition coordinator | Observation0 và all health preconditions valid | Terminal/truncation commit hoặc abort/fault | Decode action, command transaction, wait exact new pair, evaluate/commit transition | Reuse old observation, direct GT policy input, partial transition commit |
| `TERMINATED` | Episode lifecycle manager | True MDP terminal committed | Chỉ reset generation mới hoặc close | Expose final committed step once | Further `step()`, duplicate terminal reward |
| `TRUNCATED` | Episode lifecycle manager | External limit committed | Chỉ reset generation mới hoặc close | Expose final committed step once | Further `step()`, relabel thành success/failure terminal |
| `FAULT` | Episode lifecycle manager / RunSupervisor | Reset/step infrastructure or contract failure before commit | Close/restart/reset theo policy được duyệt | Inhibit commands, diagnostics, cleanup | Fabricate reward, observation hoặc Gym transition |

`RESET_ABORT` và `STEP_ABORT` là operation outcomes, không nhất thiết là persistent
states. Cả hai đưa lifecycle về `FAULT` trừ khi một recovery policy riêng được
phê duyệt.

### 3.2 Transactional reset ordering

Proposed ordering, bám sát Architecture section 18:

1. Acquire reset lock; reject concurrent `reset()`/`step()`; set state
   `RESETTING`.
2. Inhibit all old command sources. Request/publish zero through the same
   safety/actuator boundary; wait approved acknowledgement or measured
   near-zero evidence. Timeout policy vẫn `REQUIRED_DECISION`.
3. Increment `reset_epoch` before simulator mutation. Advance explicit episode
   generation/token. `runtime_generation` chỉ tăng khi runtime restart/clock
   discontinuity policy yêu cầu; không alias ba identifiers ngầm với nhau.
4. Atomically clear synchronizer runtime buffers, contact latch, reward
   accumulators/windows **và committed reward baseline**, termination windows,
   action smoother và old command sequence/cache. Baseline mới chưa tồn tại
   trong lúc reset đang chạy; không dùng giá trị episode cũ hoặc numeric sentinel.
   Trong cùng thao tác này, khởi tạo history của episode mới về previous **final
   issued command** `(0.0, 0.0, 0.0)`. Zero này là episode-initial state rõ
   ràng, không phải fallback khi input lỗi.
5. Derive episode seed lineage; reset `SimulatedOdometryEmulator` bias, drift,
   delay queue và dropout RNG. Store sampled parameter manifest.
6. Deterministically choose/validate scenario, start và goal theo approved
   sampler/manifest. Không mutate policy state bằng raw GT.
7. Request simulator pause/teleport/entity/task reset. Service success chỉ là
   transport acknowledgement, **không phải reset success**.
8. Validate observed simulator entity pose/state, commanded zero/near-zero,
   correct task identity, contact health và absence of old-epoch callbacks.
9. Unpause if applicable. Record reset ROS-time barrier only after approved
   simulator acknowledgement/validation. Record local steady start for waiting
   timeout in the separate clock domain.
10. Enter `WAITING_FOR_INITIAL_OBSERVATION`; accept only scan/odom with matching
    epoch/generation, exact equal timestamps, and timestamps strictly newer
    than reset/action barriers.
11. Tại đúng lifecycle và observation0 transition point, yêu cầu TaskOracle
    tạo `initial_goal_distance_m` và `initial_sim_time_ros_ns` (hoặc timestamp
    simulation tương đương được architecture cho phép). Cả hai phải thuộc cùng
    active `episode_generation`, `reset_epoch`, `runtime_generation` và cùng
    timestamp của exact scan–odom pair dùng cho observation0. Validate distance
    finite và `>= 0`; timestamp là integer simulation/ROS domain hợp lệ, không
    suy ra từ action, wall clock hay steady clock. Thiếu field, NaN/Inf, epoch/
    generation mismatch hoặc timestamp không cùng observation0 provenance đều
    gây `RESET_ABORT`: giữ zero/inhibit, không trả observation0.
12. Build và validate observation0 shape/dtype/finite contract **using the
    already initialized zero previous-issued command from step 4**. Observation0
    must never observe history from the previous episode.
13. Chỉ tại reset commit atomically lưu `initial_goal_distance_m` thành
    `previous_goal_distance_m` và `initial_sim_time_ros_ns` thành
    `previous_committed_sim_time`; đồng thời commit state `RUNNING`, step index
    `0` và return `(observation0, info)`. Any failure before this point yields
    `RESET_ABORT`, giữ zero/inhibit, không để lại reward baseline đã commit,
    không trả observation giả và đóng/fault environment.

Design test bắt buộc cho hai reset liên tiếp:

1. Reset generation `g` thành công, tạo baseline từ oracle tại observation0,
   sau đó commit một nonzero issued command và một contact event hợp lệ.
2. Gọi reset generation `g+1`; xác minh history zero và baseline cũ đã bị clear
   trước `ObservationAssembler`, rồi baseline mới hợp lệ được commit cùng
   observation0 trước step đầu.
3. Gọi reset generation `g+2` ngay lập tức khi chưa có action; xác minh
   observation0 thứ hai dùng zero và baseline mới của chính `g+2`, không dùng
   baseline/contact/reward/buffer từ `g+1`; callback cũ bị reject.
4. Nếu initial oracle distance/timestamp thiếu hoặc lỗi, reset là `RESET_ABORT`,
   không có observation0/baseline đã commit; lần reset sau phải tạo baseline mới.
5. Nếu reset fail trước commit, không khôi phục history, baseline hoặc latch cũ.

## 4. Proposed reset and step contracts

### 4.1 `reset(seed, options)`

Preconditions:

- lifecycle is `UNINITIALIZED`, terminal/truncated, or an approved restartable
  state;
- no step/reset transaction is active;
- config hashes, simulator identity and required endpoints pass startup checks.

Postcondition on success:

- returns exactly `(observation0, info)`;
- observation0 is current, exact-paired, same active lifecycle, newer than
  reset/action barriers, finite and 81-D;
- reset oracle baseline is finite/non-negative and timestamp-valid for the same
  lifecycle and exact observation0 transition point, then committed atomically
  as `previous_goal_distance_m` and `previous_committed_sim_time`;
- reward/termination/history/emulator state belongs only to the new episode;
- `info` includes episode generation, reset epoch, seed lineage, hashes and
  reset evidence identifiers, without raw GT.

Postcondition on failure:

- returns no Gym observation tuple;
- keeps command inhibited/zero;
- raises typed `ResetFailedError` or derived error;
- creates a failed-attempt diagnostic record, not an RL transition;
- leaves no committed reward baseline. Missing/non-finite/negative/mismatched
  initial oracle distance or timestamp means `RESET_ABORT`, no observation0.

### 4.2 `step(raw_action)` sequence

1. Require lifecycle `RUNNING`; capture active generation/epoch and the current
   committed before-state, gồm `previous_goal_distance_m` và
   `previous_committed_sim_time` đã tạo ở reset commit hoặc transition commit
   trước đó. Nếu baseline không tồn tại/không hợp lifecycle, abort trước khi
   tạo reward input.
2. Decode with `PpoActionDecoder`. Any status other than `READY` causes
   `STEP_ABORT`: no command, no history update, no reward and no Gym
   transition.
3. Submit decoded desired physical command to the future runtime command path.
   Decoder `READY` alone does **not** prove submit, Safety acceptance, limiting
   or publish.
4. Wait for an explicit command commit receipt. Minimum `PROPOSED_FOR_RUNTIME`
   receipt facts:
   lifecycle IDs, source sequence/instance, desired command, final issued
   physical command, equivalent normalized issued command, ROS receipt/barrier
   stamp, local steady receive/publish evidence and status.
5. If adapter, Safety or publish fails **before a valid final-publish receipt**,
   return `STEP_ABORT`, keep no committed history for that action, inhibit/zero
   as required, and fault/close the env.
6. Set the action ROS-time barrier from the approved receipt owner. Start wait
   budget using local steady time only.
7. Wait for scan/odom exact pair matching active lifecycle and strictly newer
   than both action/reset barriers. Never reuse the previous pair.
8. Assemble the next 81-D observation using a **staged** previous-issued-command
   value derived from the receipt, not directly from PPO raw/decoded action.
9. Build immutable oracle/reward/termination inputs cho cùng transition. Tại
   bước này chỉ snapshot một immutable contact candidate kèm reset epoch,
   runtime generation và event/transition identity. Snapshot **không mutate
   hoặc consume ContactLatch**. Evaluator chỉ đọc candidate snapshot đó.
10. Evaluate terminal precedence, rồi reward đúng một lần trên candidate hợp
    lệ. `delta_d` và `dt_sim_s` của step đầu dùng baseline đã commit tại reset;
    các step sau dùng committed point trước đó. Infrastructure error has no
    reward.
11. Validate observation, reward breakdown, decision, contact snapshot và info.
    Chỉ sau khi tất cả hợp lệ mới atomic commit: step index,
    previous-issued-command history, reward baseline/state, committed simulation
    time, và lifecycle terminal/truncated state. Trong cùng atomic commit này,
    ContactLatch consume contact pulse đúng một lần theo lifecycle/event identity.
12. Return Gymnasium five-tuple only for a committed transition:
    `(observation, reward, terminated, truncated, info)`.

Nếu lỗi xảy ra ở bất kỳ bước nào trước atomic commit, operation là `STEP_ABORT`;
contact candidate chưa được coi là consumed. Lifecycle vào `FAULT`; reset/restart
kế tiếp clear ContactLatch và toàn bộ lifecycle state, vì vậy event không được
dùng lại trong episode kế tiếp. Candidate pulse của bước lỗi không được chuyển
sang bước khác; latch chỉ được clear trong reset/restart của lifecycle mới. Quy
định này không đảo ngược va chạm vật lý hoặc command đã publish.

### 4.3 Failure after the command has been issued is not rollback

Sau khi FinalTwistPublisher đã publish final command và receipt hợp lệ chứng
minh việc issue, robot/simulator có thể đã bị tác động. Sensor timeout,
reward error hoặc observation validation failure xảy ra sau đó **không thể
rollback hành động đã publish**. Transactional semantics chỉ bảo vệ commit
của RL transition và internal state, không tuyên bố hoàn tác physical effect.

Policy đề xuất cho trường hợp này là `PROPOSED_FOR_RUNTIME` và cần user
duyệt trong D1/D2:

1. Ngay khi lỗi được phát hiện, inhibit nguồn command episode hiện tại
   và yêu cầu zero qua chính Safety/FinalTwistPublisher boundary. Không publish
   trực tiếp bỏ qua Safety.
2. Kết quả operation là `STEP_ABORT`; không trả Gym five-tuple, không
   reward, không terminal/truncation giả và hủy rollout segment chưa commit.
3. Lifecycle rời `RUNNING` sang `FAULT`; không cho step tiếp theo. Việc reset
   in-process hay restart process là `REQUIRED_DECISION`. Cho đến khi policy đó
   được duyệt, fail-closed là close/restart sau zero/inhibit evidence.
4. Receipt của command đã issue được giữ trong diagnostic abort record
   để không xóa dấu tác động, nhưng **không commit** vào previous-command
   observation history, reward smoothness history, reward baseline/accumulator,
   contact consume hay transition counter.
5. Reset/restart kế tiếp phải tăng lifecycle token theo owner được duyệt,
   clear sensor buffers, command staging/receipts, contact latch, reward/terminal
   windows và khởi tạo previous-issued command về zero trước observation0.
   Không dữ liệu nào của failed step được đi vào episode sau.

### 4.4 Command semantics and history commit point

Current core `PreviousActionHistory` updates on decoder `READY`. That behavior
is useful only as core phase evidence; it does not satisfy Architecture section
20 for runtime. Three options require explicit decision:

| Option | Semantics | Risk | Recommendation |
| --- | --- | --- | --- |
| Update at decoder `READY` | Stores requested PPO action before runtime acceptance | Lies when publish fails or Safety limits/changes command | Reject for runtime |
| Update after adapter accepts desired command | Proves handoff to adapter, not final issue | Still diverges from Safety/final publisher output | Insufficient |
| Stage after FinalTwistPublisher/Safety commit receipt; atomically commit with transition | Matches authoritative previous-issued-command definition; not actuator acknowledgement | Requires typed receipt and abort/fault handling | `PROPOSED_FOR_RUNTIME` |

The history API may need a prepare/commit redesign or a separate issued-command
history owner. This document does not approve that code change.

Bốn giá trị không được đồng nhất:

| Value | Meaning | Allowed use |
| --- | --- | --- |
| Desired PPO action | Raw normalized `[vx, vy, wz]` do policy đề xuất | Chỉ input cho decoder |
| Decoder-accepted action | Normalized action đã qua dimension/finite/bounds validation; decoder có thể scale thành desired physical velocity | Command candidate; không phải issued receipt |
| Final issued command | Physical `vx_mps, vy_mps, wz_radps` sau Safety/Smoother/limiter, đã publish và có receipt hợp lệ | Nguồn đề xuất duy nhất cho previous-command observation và reward smoothness |
| Measured robot twist | Vận tốc đo từ `SimulatedOdometryMeasurement`/state estimator | Measured-twist observation; không chứng minh command đã issue |

Final issued physical command phải được chuẩn hóa bằng cùng axis order
và limits/version đã khóa trong observation/action contract, ví dụ
`[vx/max_vx, vy/max_vy, wz/max_wz]`, sau đó fail-closed nếu receipt không
finite, sai lifecycle hoặc vượt limits. Công thức, owner receipt, xử lý
zero/limiter và exact schema metadata vẫn là `REQUIRED_DECISION`; không
được tự clamp để làm hợp lệ một receipt sai.

Thay producer hiện tại từ decoder-accepted action sang normalized final-issued
receipt là thay đổi **semantics** của block observation dù shape vẫn là 3.
Theo Architecture section 20, issued-command definition và normalization nằm
trong observation schema hash. Migration phải bump/update schema/hash phù hợp,
invalidate hoặc migrate checkpoint/normalization artifact cũ, và không được
resume model cũ im lặng. S3 không sửa `PreviousActionHistory` trong bước này.

## 5. Outcome semantics and event precedence

Architecture sections 22–25 already lock true terminal versus truncation and
infrastructure failure behavior. This design preserves that precedence.

| Event(s) in one candidate step | Proposed operation outcome | `terminated` | `truncated` | Observation/reward | Authority/status |
| --- | --- | --- | --- | --- | --- |
| Collision contact | Commit terminal transition | true | false | Valid new observation; collision terminal reward once | Precedence `APPROVED_FOR_CORE` by Architecture section 23; runtime source `NOT_IMPLEMENTED` |
| Goal reached | Commit terminal transition | true | false | Valid new observation; goal reward once | Precedence `APPROVED_FOR_CORE` by Architecture section 23; runtime source `NOT_IMPLEMENTED` |
| Out of bounds | Commit terminal transition | true | false | Valid new observation; terminal reward per v3 contract | Precedence `APPROVED_FOR_CORE` by Architecture section 23; runtime source `NOT_IMPLEMENTED` |
| Stuck | Commit terminal transition | true | false | Valid new observation; stuck terminal reward once | Precedence `APPROVED_FOR_CORE`; detector/config `REQUIRED_DECISION` |
| Max steps or max simulation time | Commit truncated transition | false | true | Valid new observation and non-terminal step reward | Semantics `APPROVED_FOR_CORE`; concrete limits `REQUIRED_DECISION` |
| Collision and goal together | Collision wins | true | false | Collision terminal term only | `APPROVED_FOR_CORE` by Architecture sections 22–23 |
| Goal and timeout together | Goal wins external timeout | true | false | Goal terminal term once | `APPROVED_FOR_CORE` by Architecture section 23 |
| Action invalid/out of bounds/config invalid | `STEP_ABORT` | N/A | N/A | No command, observation, reward or transition | Core decoder fail-closed `IMPLEMENTED_CORE`; episode abort mapping `PROPOSED_FOR_RUNTIME` |
| Odometry delayed/dropped/stale | `STEP_ABORT` after wait policy fails | N/A | N/A | No fallback/old observation; no reward | Core non-ready `IMPLEMENTED_CORE`; runtime age/wait `REQUIRED_DECISION` |
| No exact pair, including 1 ns skew | Pending until approved wait bound, then `STEP_ABORT` | N/A | N/A | No nearest/old pair; no reward | Exact-only `APPROVED_FOR_CORE` and `IMPLEMENTED_CORE`; wait bound/runtime unresolved |
| Simulator reset failure | `RESET_ABORT` -> `FAULT` | N/A | N/A | No observation0/reward | No-fabrication rule authoritative; concrete recovery `REQUIRED_DECISION` |
| Transport/runtime command failure | `STEP_ABORT` -> `FAULT` | N/A | N/A | No transition; command inhibit/zero | `PROPOSED_FOR_RUNTIME` receipt/error mapping |
| ROS/simulation clock jumps backward | Invalidate buffers, advance runtime generation, `STEP_ABORT` | N/A | N/A | No transition/reward | Architecture principle; runtime owner missing |
| Multiple terminal causes | First cause in locked precedence table | As selected | false unless only time limit | One terminal term, one commit | `APPROVED_FOR_CORE` by authoritative precedence |

Gymnasium does not define `None` observation as a safe failure transition.
Returning zero/old observation with a penalty would fabricate an MDP sample.
The authoritative architecture instead requires an exception before transition
commit, partial-rollout discard and clean process restart. Therefore the
recommended policy is typed `RESET_ABORT/STEP_ABORT` outside the Gym five-tuple.
Changing this requires an ACR because it changes failure semantics.

## 6. Reward contract

### 6.1 Architecture-defined baseline

The authoritative architecture already defines `reward-v3-baseline`:

```text
delta_d      = previous.goal_distance - current.goal_distance
r_progress   = clip(2.00 * delta_d, -1.00, 1.00)
r_time       = -0.10 * dt_sim_s
r_clearance  = -0.20 * max(0, (d_safe - c) / d_safe) * dt_sim_s / 0.10
du           = normalized_applied - normalized_previous_applied
r_smooth     = clip(-0.005 * dot(du, du) / max(dt_sim_s, 1e-6), -1.0, 0.0)
r_terminal   = +15 goal | -15 collision | -3 stuck | 0 otherwise
r_total      = sum(terms)
abs(r_total - logged_sum) <= 1e-6
```

Các hệ số trên là `APPROVED_FOR_CORE` vì được khóa trực tiếp bởi
authoritative Architecture section 22; chúng chưa phải optimum. Không được
tự thay trong S3 implementation. Thay formula/weight/schema phải có ACR/reward
schema version mới và ablation multi-seed evidence.

### 6.2 Component provenance và reset state

| Component | Formula/sign/unit | Required input source | Apply/reset rules | Reward-hacking risk / status |
| --- | --- | --- | --- | --- |
| Goal success | `+15`, unitless once | Hidden task oracle goal decision derived from GT; threshold/settle configuration | Apply once on committed `goal_reached`; clear terminal-consumed flag on reset | Noisy policy pose must not be used as authoritative success. Goal thresholds remain unresolved. |
| Collision | `-15`, unitless once | Immutable contact candidate snapshot from ContactLatch for the active epoch/generation | Snapshot is read-only during evaluation; consume exactly once only inside successful atomic transition commit; pre-commit abort does not consume; reset/restart clears latch | Contact silence cannot mean no collision. Runtime source/consume owner not implemented. |
| Progress | `clip(2 * (d_prev-d_curr), -1, 1)`; distance input in metres | Previous committed oracle distance, initialized by reset oracle at observation0, and current oracle distance for this transition | Reset commit stores baseline only after exact observation0 and matching oracle provenance; abort never commits/advances it | Endpoint-only shaping can invite oscillation if source/order is inconsistent. Same-episode provenance mandatory. |
| Time cost | `-0.10 * dt_sim_s` | Positive difference between current same-transition simulation timestamp and previous committed simulation time; first step uses reset baseline | Reset commit stores `previous_committed_sim_time`; no value for aborted step; never use wall/steady time or infer from action | Discourages standing still/rotation without progress. Clock rollback aborts; no negative/zero fabricated dt. |
| Safe distance | Negative, time-scaled formula above | `c` clearance source is not yet defined; `d_safe` config absent | Only committed transition; reset any filters/windows | Raw LiDAR min, footprint clearance and privileged geometry are not equivalent. `REQUIRED_DECISION`. |
| Smoothness | Negative squared change in normalized final issued command | Two consecutive committed issued-command receipts | Reset previous issued command to zero; no update on failed command/step | Decoder actions cannot substitute if Safety limits output. Commit receipt `REQUIRED_DECISION`. |
| Stuck terminal | `-3` once | Future stuck detector using approved window/threshold | Apply once on terminal commit; reset detector window | Threshold/window remain project acceptance/config decisions. |
| Other terminal/truncation | `0` terminal term | Termination decision | Progress/time/etc. may still apply to a valid truncated transition | Do not invent infrastructure penalty. |

### 6.3 Reward invariants

- Reward evaluator is pure and reads one immutable `RewardInputs`; it does not
  read ROS callbacks, Gazebo handles, policy objects or global mutable state.
- Progress uses `previous_goal_distance_m` from the reset/previous transition
  commit and the current oracle distance from the same transition provenance.
  Both must match episode generation/reset epoch. It is undefined when reset
  baseline is absent or across reset, dropout, abort or clock discontinuity.
- `dt_sim_s` uses the current transition simulation timestamp minus
  `previous_committed_sim_time`; reset initializes the latter from the exact
  observation0 oracle snapshot. An aborted step does not advance either baseline.
- Terminal reward is consumed exactly once. Repeated `step()` after terminal
  is an API error and cannot add reward again.
- A stationary robot accumulates time cost and no positive progress. Rotating
  in place does not earn progress; it can incur time/smoothness cost.
- Reverse or lateral motion is not penalized merely by direction; it earns
  progress only if oracle distance decreases. This preserves holonomic
  behavior.
- Oscillation cannot accumulate net progress across inconsistent samples;
  ordered same-episode points and smoothness/time terms must be logged.
- Reward and every component are finite. `total` must equal the logged sum
  within `1e-6`.
- Infrastructure/reset/command/sensor failure before commit has no reward and
  is not converted into collision, timeout or task penalty.

## 7. Clock and provenance contract

| Field/domain | Owner/source | Use | Forbidden use |
| --- | --- | --- | --- |
| Scan/odom ROS or simulation timestamp | Sensor/emulator ingress | Exact pairing and strict-after barriers | Freshness by comparison with steady clock |
| Action/reset barrier ROS timestamp | Future command/reset transaction owner | Reject sensor data at/before barrier | Wall-clock timeout |
| Local steady receive time | Future runtime ingress adapter | Receive age and bounded wait | Subtract from ROS/sim timestamps |
| Episode elapsed simulation time | Episode coordinator from committed ROS/sim points | Time-limit and `dt_sim_s` reward | Runtime callback timeout |
| `reset_epoch` | ResetManager | Reject pre-reset cache/contact/command data | Infer from timestamp value |
| `runtime_generation` | Runtime/clock lifecycle owner | Reject data across restart/clock rollback | Treat as episode step counter |
| `episode_generation` | Episode lifecycle owner | Bind history/reward/termination to one episode | Alias implicitly to reset epoch/generation |
| Source/command sequence | Source adapter/Safety receipt | Detect duplicate/backward command provenance | Prove actuator reached velocity |
| Odometry sequence | Emulator output | Candidate identity/diagnostic | Apply one monotonic check across VALID/DELAYED/DROPPED delivery events |

### 7.1 Same-transition provenance bundle

Một candidate transition chỉ được commit khi tất cả input dưới đây được
bind vào cùng `transition_id`, `episode_generation`, `reset_epoch` và
`runtime_generation`. Việc có cùng ID không cho phép bỏ qua timestamp/barrier
checks; provenance phải chứng minh chúng thuộc cùng action interval.

| Input | Same-transition rule | Producer/evidence hiện có | Trạng thái |
| --- | --- | --- | --- |
| Final command receipt | Core bind test-only receipt vào active `TransitionIdentity` (lifecycle, step, token), reject token/receipt-ID replay; runtime vẫn phải chứng minh final publish, source sequence, action barrier, final physical command và normalized equivalent | Core token join `IMPLEMENTED_CORE`; SafetySupervisor/FinalTwistPublisher receipt runtime chưa có | D2-B `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`; runtime `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| Exact scan–odom pair | Hai stamp bằng nhau tuyệt đối, đúng lifecycle và strictly newer than action/reset barriers | `ExactSnapshotPairGate` chứng minh semantic core-only; metadata do caller/test inject | `APPROVED_FOR_CORE`, `IMPLEMENTED_CORE`; runtime ingress `NOT_IMPLEMENTED` |
| Oracle goal distance | `previous_goal_distance_m` là giá trị đã commit của step trước trong cùng episode; `current_goal_distance_m` là derived fact tại transition timestamp/task state hiện tại | ACR S1 cho phép oracle đọc GT; `TrainingTaskOracle` producer chưa có | Quyền `APPROVED`; typed producer/alignment `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| Contact latch | Build step chỉ snapshot immutable candidate gắn active `TransitionIdentity` và event ID; evaluator đọc snapshot; latch chỉ consume đúng một lần trong atomic commit thành công | Core token match/stage/consume `IMPLEMENTED_CORE`; ContactLatch runtime chưa có | D3-B `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION`; action-interval proof/producer `REQUIRED_DECISION`, `NOT_IMPLEMENTED`; STEP_ABORT giữ event chưa consumed cho tới lifecycle reset clear |
| Reset reward baseline | Oracle cung cấp `initial_goal_distance_m` và `initial_sim_time_ros_ns` khớp exact observation0 và active lifecycle; reset commit lưu chúng làm previous committed distance/time | TaskOracle/runtime reset producer chưa có | `REQUIRED_DECISION`, `NOT_IMPLEMENTED`; thiếu/non-finite/negative/mismatched input -> `RESET_ABORT` |
| Clearance `c` | Phải nêu rõ sensor/geometry source, frame, timestamp và relation với exact pair; không trộn raw GT hay giá trị tự bịa | Chưa có source authoritative | `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |
| `dt_sim_s` | Hiệu dương giữa timestamp simulation của current transition và `previous_committed_sim_time`; step đầu dùng reset baseline; aborted step không cập nhật baseline | Chưa có episode coordinator/runtime clock owner | `REQUIRED_DECISION`, `NOT_IMPLEMENTED` |

Reward, termination và observation phải được build từ bundle này trước
một commit duy nhất. Nếu bất kỳ producer/provenance nào thiếu, không
được dựng giá trị test fixture trong runtime; operation là `STEP_ABORT` và
không tạo Gym transition.

`ExactSnapshotPairGate` enforces exact timestamp, lifecycle match and barriers
for one candidate pair. It does not implement receive-age, queues, capacity,
overflow, timeout or runtime ingress ownership. Those remain pending in ACR S2
and cannot be silently added by the episode environment.

Late data is rejected at three boundaries:

1. ingress metadata rejects old epoch/generation;
2. exact pair gate rejects barrier/timestamp mismatch and non-VALID odometry;
3. episode coordinator rechecks active lifecycle before atomic transition
   commit.

## 8. Proposed core-only API

The names below are design proposals, not existing classes.

### 8.1 `EpisodeState`

Owner: future `env/episode_state.py` or pure lifecycle module.

Minimum sourced fields:

- lifecycle enum;
- `episode_id` and `episode_generation` from episode manager;
- `reset_epoch` and `runtime_generation` from approved lifecycle owners;
- `step_index`;
- episode seed lineage/scenario ID from task manager;
- reset/action barrier ROS timestamps from transaction receipts;
- initial/last committed observation provenance, not raw GT;
- elapsed simulation time from committed simulation timestamps;
- terminal/truncated decision if committed.

It must not contain raw Ground Truth, ROS nodes/messages or mutable buffers.

### 8.2 `StepOutcome`

Owner: episode transition coordinator; Gym adapter consumes only committed
outcomes.

Minimum fields:

- status: `COMMITTED`, `TERMINATED`, `TRUNCATED`, `STEP_ABORT`;
- lifecycle IDs and step index;
- observation vector only for committed statuses;
- `RewardBreakdown` and `TerminationDecision` only for committed statuses;
- command receipt ID/provenance for committed action;
- structured abort code for `STEP_ABORT`, never a fabricated reward.

The Gym environment converts only the first three committed statuses to a
five-tuple. `STEP_ABORT` raises a typed exception and is not a Gym transition.

### 8.3 `RewardInputs`

Owner: transition builder; consumed only by pure reward evaluator.

Minimum fields with identifiable future sources:

- episode/reset/runtime identifiers;
- reset-initialized `previous_goal_distance_m` and current oracle goal distance
  in metres, each with lifecycle and simulation timestamp provenance;
- reset-initialized `previous_committed_sim_time` and current simulation-time
  commit point from the same transition, producing positive `dt_sim_s`;
- immutable contact candidate snapshot with lifecycle/event identity; evaluator
  reads this value and the owner consumes the latch only at atomic commit;
- clearance `c` and `d_safe` only after source/config approval;
- previous/current normalized **issued** command from command receipts;
- selected `TerminationDecision`;
- one transition identity to enforce consume-once, including ContactLatch event
  consumption and reward terminal consumption.

It carries derived oracle scalars/events, never raw GT objects.

### 8.4 `RewardBreakdown`

Owner: pure reward evaluator.

Fields: `progress`, `time_cost`, `clearance`, `smoothness`, `terminal`, `total`,
reward schema ID and transition identity. All finite; immutable; `total` equals
component sum within the locked tolerance.

### 8.5 `TerminationDecision`

Owner: pure termination evaluator.

Minimum fields:

- `terminated`, `truncated` with mutual-exclusion validation;
- typed reason from locked precedence;
- `is_success`;
- selected priority and transition identity;
- contributing event flags for diagnostics without applying multiple terminal
  rewards.

Inputs must be immutable derived facts: collision latch result, goal decision,
out-of-bounds, stuck, step/time limits and matching lifecycle IDs.

### 8.6 Required adjacent contracts not yet sourced

- command commit receipt from Safety/FinalTwistPublisher boundary;
- task-oracle snapshot containing derived goal/outcome facts;
- collision/contact transition event with reset-epoch provenance;
- simulator reset receipt plus observed post-reset validation;
- approved receive-age/wait/buffer lifecycle metadata.

Creating placeholder fields without a producer would hide a runtime gap, so
these contracts must be approved before corresponding API implementation.

## 9. Test matrix before implementation

| Test | Expected evidence | Level |
| --- | --- | --- |
| Two consecutive resets | Mỗi reset initializes previous-issued zero and creates a fresh oracle reward/time baseline before observation0 commit; reset thứ hai không thấy command/history/contact/reward/buffer/baseline từ generation trước; old callbacks rejected | Core unit plus Gazebo integration |
| Reset reward baseline valid | Oracle distance finite/non-negative and simulation timestamp valid for same lifecycle and exact observation0 point; reset commits both before first step | Core unit with explicitly test-only oracle fixture; runtime producer evidence separately |
| Reset baseline invalid/missing | Missing, NaN/Inf, negative distance, wrong epoch/generation, or timestamp not matching observation0 causes `RESET_ABORT`, zero/inhibit, no observation0 and no committed baseline | Core unit; oracle/runtime integration separately |
| First step baseline | `delta_d` and `dt_sim_s` use exact distance/time committed at reset, never zero/default or wall/steady time | Core unit |
| Abort after publish with pending contact | `STEP_ABORT` does not consume contact candidate; FAULT then reset clears old latch and baseline; next episode cannot see either | Core transaction unit plus runtime fault integration |
| Invalid PPO action | `STEP_ABORT`, no command receipt/history/reward/transition | Core unit |
| Goal and collision same transition | Collision selected, one terminal term | Core unit; contact source integration separately |
| Goal and timeout same transition | Goal terminated wins truncation | Core unit |
| Max step/sim time only | Valid final observation, `truncated=true`, no terminal bonus | Core unit |
| Missing scan/odom | Pending until approved bound, then typed abort; no old observation | Core unit after age decision; Gazebo timing integration |
| Exact-pair skew 1 ns | Not ready/abort, no nearest fallback | Core unit, already proven at pair gate |
| DELAYED/DROPPED odometry | No pair, no GT/old-odom fallback | Core unit, pair gate evidence exists |
| Callback from old generation/epoch | Rejected before transition builder | Core unit plus runtime integration |
| ROS clock rollback | Buffers invalidated, runtime generation advanced, step abort, no reward | Core unit state machine plus Gazebo integration |
| Simulator reset service returns but pose/state wrong | Reset fails; no observation0 | Gazebo integration |
| Command publish/adapter failure | History not committed; step abort; zero/inhibit path | Core transaction test plus runtime integration |
| Command receipt hợp lệ nhưng sensor/reward/observation lỗi sau publish | Không tuyên bố rollback; zero/inhibit, `STEP_ABORT`, lifecycle `FAULT`, discard rollout chưa commit; abort diagnostic giữ receipt nhưng history/reward/contact không rò sang episode sau | Core transaction test plus runtime fault integration |
| Terminal reward called twice | Second consume rejected; no duplicate terminal reward | Core unit |
| Progress across reset/dropout | Rejected; no cross-boundary delta | Core unit |
| Ground Truth isolation | Reward gets derived oracle facts; policy object graph cannot reach raw GT | Static/unit plus ROS graph integration |
| Fixed seed reset | Same scenario, emulator parameters and deterministic core outcome trace | Core unit; Gazebo statistical/replay evidence |
| Robot stationary/rotation/reverse/lateral traces | No direction loophole; progress and costs follow formula | Core unit/property tests |
| Reward sum | Components finite and sum equals total within `1e-6` | Core unit/property tests |

No test that directly constructs a future runtime receipt/provider can be used
as evidence that the real provider exists.

## 10. Decision registry for user approval

The decisions are ordered by dependency.

| ID | Trạng thái hiện tại | Evidence có thật | Phần còn chờ duyệt |
| --- | --- | --- | --- |
| D1 | No-fabricated-transition là `APPROVED_FOR_CORE`; recovery runtime là `REQUIRED_DECISION` | Architecture sections 19, 23 và 25 | Typed abort API, zero/inhibit receipt, discard/restart policy; pre-commit contact không consume và reset/restart clear latch |
| D2 | Final-issued semantics là `APPROVED_FOR_CORE`; D2-B explicit token `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION` và token join `IMPLEMENTED_CORE`; runtime receipt/commit là `REQUIRED_DECISION` | Architecture sections 20–21; [transition provenance packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md); source history hiện chỉ lưu decoder-ready action | Runtime token/receipt owner, final-publish evidence, physical-to-normalized rule, checkpoint migration |
| D3 | Quyền oracle/GT là `APPROVED` bởi ACR S1; D3-B contact token snapshot `USER_SELECTED_FOR_CORE_ONLY_IMPLEMENTATION` và token join `IMPLEMENTED_CORE`; runtime producers là `REQUIRED_DECISION` | ACR S1 status `APPROVED`; [transition provenance packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md) | Typed oracle/contact runtime boundaries; action-interval evidence; consume tại commit; alignment/lifecycle provenance |
| D4 | `APPROVED_FOR_CORE` | Architecture sections 22–23 khóa precedence collision > goal > out-of-bounds > stuck > limit | Chỉ implementation/tests; runtime event producers thuộc D3/D6 |
| D5 | Formula/coefficients `reward-v3-baseline` là `APPROVED_FOR_CORE`; full evaluator bị block bởi input thiếu | Architecture sections 22–23 và provenance hash ở đầu tài liệu | Clearance source/`d_safe`, stuck inputs, typed config/schema migration |
| D6 | `REQUIRED_DECISION` | Architecture khóa semantics terminal-vs-truncation nhưng không cung cấp numeric limits | Max steps, max sim time và control cadence evidence |
| D7 | Versioned/seeded manifest principle là `APPROVED_FOR_CORE`; runtime sampler/reset là `REQUIRED_DECISION` | Architecture sections 18, 24 | Scenario artifacts, checks, provider và reset integration |
| D8 | Exact-only `APPROVED_FOR_CORE` bằng user instruction S.2.2A.0 và `IMPLEMENTED_CORE`; runtime là `REQUIRED_DECISION` | `ExactSnapshotPairGate` tests; ACR S2/approval packet vẫn pending | Receive age, buffer/capacity, overflow, ingress IDs, barriers, runtime graph |
| D9 | Observed reset validation principle là `APPROVED_FOR_CORE`; runtime là `REQUIRED_DECISION` | Architecture section 18 | Simulator receipt/probes, timeout, retry/restart budget |
| D10 | `REQUIRED_DECISION` | Architecture có clearance term nhưng source `c`/`d_safe` chưa có trong config/runtime | Semantic source, frame/time alignment, threshold/evidence |

Không dòng nào trong bảng này thay đổi status của ACR S2. Các nhãn
`APPROVED_FOR_CORE` chỉ cho phép implement/test pure-core đúng contract đã
nêu; chúng không cho phép Gazebo/Gym/ROS runtime.

### D1 Failure without a valid observation

| Option | Trade-off |
| --- | --- |
| A. Typed `RESET_ABORT/STEP_ABORT`, no Gym transition; if command was already issued, record the irreversible receipt, request zero/inhibit, enter `FAULT`, leave pre-commit ContactLatch pulse unconsumed, then reset/restart and discard uncommitted rollout | Preserves MDP integrity without pretending the published command or collision was rolled back; operationally more complex |
| B. Return last valid observation with `truncated=true` | Gym-compatible but fabricates temporal state and contaminates rollout |
| C. Return zero observation with penalty | Simple but fabricates state/reward and teaches infrastructure artifacts |

Recommendation: **A**. This matches authoritative architecture; B/C would
require an ACR. User approval should confirm the concrete zero/inhibit,
exception, reset/restart, ContactLatch clear and diagnostic-retention policy,
not reopen the no-fabricated-transition rule.

### D2 Command commit and previous-issued history

| Option | Trade-off |
| --- | --- |
| A. Commit on decoder `READY` | Already easy, but contractually too early |
| B. Commit on command adapter receipt | Detects adapter failure, not Safety limiting/final publish |
| C. Commit from Safety/FinalTwistPublisher receipt and atomically with transition | Correct authoritative semantics; needs new typed receipt and staging |

Recommendation: **C**. Evidence required: runtime ownership design and tests
for publish failure, limiting, stale receipt and generation mismatch.

### D3 Goal and collision sources

| Option | Trade-off |
| --- | --- |
| A. Hidden `TrainingTaskOracle` goal facts plus a read-only ContactLatch candidate snapshot, consumed only on successful atomic commit | Matches ACR S1 and contact architecture; requires providers/contracts |
| B. Policy noisy pose/LiDAR only | Avoids privileged data but weakens authoritative task/collision truth |
| C. Raw GT/contact messages inside reward manager | Direct but violates separation and pure RewardManager ownership |

Recommendation: **A**. Need generated collision contract, controlled-contact
evidence, goal-settle thresholds and oracle typed boundary. D3 also requires a
two-phase contact contract: snapshot for evaluation, consume only at successful
atomic commit; abort preserves the candidate until reset/restart clears its
lifecycle.

D2-B/D3-B ở [transition provenance packet](S3_Transition_Provenance_Decision_Packet_DRAFT.md) là lựa chọn **định danh transition** cho core-only, độc lập với phương án C về thời điểm commit command ở D2 và phương án A về nguồn oracle/contact ở D3 phía trên. Core chỉ nhận `TransitionIdentity` do caller/test cung cấp để join receipt, contact candidate và step candidate; runtime token producer, final-publish receipt, ContactLatch và action-interval evidence vẫn `NOT_IMPLEMENTED`/`REQUIRED_DECISION`. `TransitionContext.previous_applied_command`/`applied_command` không được coi là final-issued receipt; migration chưa được phê duyệt.

### D4 Event precedence and terminal semantics

| Option | Trade-off |
| --- | --- |
| A. Locked order collision > goal > out-of-bounds > stuck > external time limit | Deterministic and already authoritative |
| B. Sum all simultaneous terminal outcomes | Can give contradictory success/collision labels and duplicate terminal reward |
| C. Choose callback arrival order | Nondeterministic under ROS/Gazebo scheduling |

Recommendation: **A**. Any different choice requires ACR.

### D5 Reward formula and coefficients

| Option | Trade-off |
| --- | --- |
| A. Implement locked `reward-v3-baseline` exactly | Comparable baseline; current config schema must be extended/versioned |
| B. Create reward-v4 via ACR after ablation/multi-seed evidence | Allows improvement but delays baseline and changes checkpoint contract |
| C. Defer reward implementation | Avoids premature config, but blocks Gym/training |

Recommendation: **A**. `d_safe` provenance/value, stuck detector and terminal
thresholds still require decisions; the listed coefficients themselves are not
open without ACR.

### D6 Time and step limits

| Option | Trade-off |
| --- | --- |
| A. Maximum simulation time only | Rate-independent but needs robust sim-clock handling |
| B. Maximum steps only | Simple but coupled to control cadence |
| C. Both; truncate when either is reached, terminal MDP event wins same step | Bounded in both domains; more config/test surface |

Recommendation: **C**. Values remain `REQUIRED_DECISION`; collect desired task
horizon/control cadence evidence. Never use steady time as simulated task time.

### D7 Reset and start-goal sampling

| Option | Trade-off |
| --- | --- |
| A. Versioned scenario manifests with deterministic seeded sampler and validity checks | Reproducible and evaluation-safe; requires task tooling |
| B. Online random sampling from world bounds only | Faster but can generate unreachable/unsafe pairs |
| C. Fixed start/goal only | Simple smoke test, insufficient training coverage |

Recommendation: **A**, with C allowed only for initial integration fixture.
Need world/scenario hashes, reachability/clearance checks and seed-lineage tests.

### D8 Freshness, buffering and overflow

| Option | Trade-off |
| --- | --- |
| A. Implement runtime buffers now with guessed bounds | Fast but violates pending S2 decisions |
| B. Keep exact core gate; collect motion/reset/contention evidence, then approve bounded ages/capacities/overflow | Fail-closed and evidence-based; delays runtime integration |
| C. Unbounded wait/buffer | Memory/liveness risk and no deterministic failure bound |

Recommendation: **B**. Required evidence remains as listed in ACR S2.

### D9 Simulator reset validation

| Option | Trade-off |
| --- | --- |
| A. Service return alone | Low latency but cannot prove mutation/state convergence |
| B. Service acknowledgement plus observed pose/twist/contact/task/sensor/barrier validation | Strong transaction evidence; needs more probes/timeouts |
| C. Fixed sleep after service | Scheduling-sensitive and cannot prove correctness |

Recommendation: **B**. Timeout and retry/restart budget remain
`REQUIRED_DECISION`.

### D10 Safe-clearance reward source

| Option | Trade-off |
| --- | --- |
| A. Minimum policy-safe LiDAR sector/range | Reuses observation-side sensor but is not footprint clearance |
| B. Footprint-aware clearance derived in oracle from Gazebo geometry | Better geometric meaning but privileged and more complex |
| C. Remove clearance term | Conflicts with locked reward-v3 contract unless ACR changes it |

Recommendation: `REQUIRED_MEASUREMENT/REQUIRED_DECISION`. First define what
`c` and `d_safe` mean in the locked formula, then test occlusion, near-field
invalid rays and holonomic side clearance. No numeric threshold is proposed.

## 11. Implementation plan after approval

| Increment | Start condition | Deliverable and pass criteria | Forbidden until later |
| --- | --- | --- | --- |
| S3.1 Core episode contract | Core-only exit criteria bên dưới đạt | Immutable episode/outcome types; reset/step state-machine unit tests; no ROS/Gym imports | Simulator service calls, Gym env |
| S3.2 Core termination evaluator | D3, D4, D6 sources/values approved | Pure precedence evaluator; simultaneous-event/property tests | Gazebo callbacks inside evaluator |
| S3.3 Core reward evaluator | D2, D5, D10 approved | Exact reward-v3 breakdown; finite/sum/consume-once/reset tests | Training or YAML guesses |
| S3.4 Core transaction tests | S3.1–S3.3 complete | Reset twice, abort, generation, terminal/time conflict, deterministic seed tests | Runtime claims |
| S3.5 Runtime adapter and reset transaction | S2 freshness/buffer decisions, command receipt and simulator lifecycle approved | Gazebo reset validation, contact/oracle providers, command receipt, exact fresh snapshot integration evidence | Gym rollout/training |
| S3.6 Gymnasium environment | Runtime adapters stable and failure policy approved | API checker passes; five-tuple only for committed transitions; reset returns valid observation0 | SB3 training before integration gate |
| S3.7 Integration and fault tests | Gym env core contract passes | Gazebo reset/contact/clock/dropout/command failure evidence; GT isolation graph test | Gate 1 claim before all pass |
| S3.8 PPO training | Gate 1 criteria satisfied and configs/hashes frozen | Reproducible smoke rollout then training pipeline | Final evaluation claims before preregistration |

## 12. Exit criteria for this draft

### 12.1 Khi được bắt đầu riêng S3.1 core-only

S3.1 core-only chỉ được bắt đầu khi user duyệt tối thiểu:

- lifecycle states và transition table cho pure-core;
- D1 typed `RESET_ABORT/STEP_ABORT` không tạo Gym transition;
- reset ordering, bao gồm previous-issued zero trước observation0;
- immutable lifecycle identifiers và quy tắc stale/future generation;
- cho phép dùng explicit **test-only** receipts/oracle/contact/time facts để
  test state machine, với nhãn rõ chúng không phải runtime producer;
- D2-B/D3-B core-only: caller-supplied immutable `TransitionIdentity` phải bind active step, test-only receipt, contact candidate và commit; token mismatch/replay fail-closed, abort không consume, reset mới clear token/fact state; runtime producer chưa được triển khai;
- reset oracle baseline (`previous_goal_distance_m`,
  `previous_committed_sim_time`) phải được khởi tạo và validate cùng
  `observation0` bằng test-only facts trong core scope;
- phạm vi S3.1 không import ROS/Gazebo/Gymnasium, không publish command và
  không tuyên bố runtime recovery.

S3.1 có thể định nghĩa interfaces/status thuần và test ordering/abort, nhưng
không được dựng producer giả. Reward evaluator chỉ được bắt đầu cho
các component có input semantics đã khóa; clearance component vẫn bị block
bởi D10.

### 12.2 Khi mới được làm Gazebo/Gym runtime

Runtime/Gym không được bắt đầu cho đến khi:

- ACR S2/runtime temporal lifecycle được phê duyệt, gồm receive-age,
  buffers/capacity, overflow, ingress identity và barrier owners;
- D2 command receipt/final-issued normalization và post-publish abort handling
  được phê duyệt;
- D3/D9 có typed runtime producers cho oracle, read-only contact candidate,
  commit-time consume và simulator reset validation; reset oracle baseline
  (`initial_goal_distance_m`, `initial_sim_time_ros_ns`) được validate/commit
  cùng observation0; D6 có numeric limits/config được phê duyệt;
- D10 có clearance semantics/source hoặc một ACR chính thức thay đổi reward
  schema; không được bỏ term im lặng;
- fault-injection chứng minh command đã publish không bị mô tả như rollback,
  zero/inhibit được request qua owner đúng và failed-step state không rò
  sang episode kế tiếp;
- Ground Truth isolation và same-transition provenance có integration evidence.

This document does not declare Gate 1 complete, Gymnasium-ready, simulator
reset-ready or PPO-training-ready.

**Final status: `DRAFT — PENDING_USER_APPROVAL`.**
