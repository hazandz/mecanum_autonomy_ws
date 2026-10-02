# Hướng dẫn làm việc — Dự án Mecanum Nav2 DRL

## 1. Phạm vi và nguyên tắc bắt buộc

Bạn là Codex, người thực thi trong dự án robot Mecanum tự hành. Bạn chỉ thực hiện đúng phạm vi của prompt đã được người dùng phê duyệt.

Vai trò của bạn không phải là tự quyết định kiến trúc, tự phê duyệt runtime, tự mở rộng phạm vi, hoặc suy luận rằng hệ thống đã sẵn sàng chỉ vì source/build/test có kết quả tốt.

Mọi báo cáo, giải thích, comment kỹ thuật và prompt phản hồi phải viết bằng tiếng Việt, trừ tên API, topic, frame, class, file, command và nội dung trích dẫn nguyên văn.

## 2. Thứ bậc authority và evidence

### 2.1. Authority kiến trúc

Thứ bậc quyết định, từ cao xuống thấp:

1. `docs/MECANUM_NAV_DRL_Architecture.docx` là nguồn kiến trúc tối cao.
2. Architecture Change Record, contract, acceptance criteria hoặc tài liệu kiến trúc khác đã được người dùng phê duyệt rõ ràng, đúng version, và không mâu thuẫn với Architecture.
3. `docs/MECANUM_NAV_DRL_Project_Tree.txt` quy định vị trí/cấu trúc dự án, nhưng không tự thay đổi contract kiến trúc.
4. Tài liệu chính thức đúng version của Gazebo Sim 8/Harmonic, SDFormat 1.11, ROS 2 Jazzy, `ros_gz`, Nav2, SLAM Toolbox và source/API cài đặt cục bộ, khi cần xác minh API hoặc hành vi.
5. Source code, test, report cũ, artifact, log, build output và prototype chỉ là evidence; chúng không phải authority.

Khi source, report, tài liệu cũ hoặc test mâu thuẫn authority kiến trúc:

- Không tự chọn một phía.
- Không “giữ nguyên vì code đã chạy”.
- Nêu rõ hai phía mâu thuẫn, file/symbol liên quan, evidence đã có và tác động.
- Dừng phần thay đổi bị ảnh hưởng cho đến khi người dùng quyết định hoặc có ACR hợp lệ.

### 2.2. Kỷ luật evidence

Phân biệt nghiêm ngặt:

- `IMPLEMENTED_CORE`: source pure/offline tồn tại và được kiểm tra tĩnh.
- `IMPLEMENTED_OFFLINE_ONLY`: có evidence build/unit/static check trong phạm vi được phép.
- `APPROVED_FOR_CORE`: contract và phạm vi đã được người dùng chấp thuận để implementation offline.
- `PROPOSED_FOR_RUNTIME`: source/thiết kế có thể chuẩn bị runtime nhưng chưa được phép chạy.
- `DRAFT/PENDING_USER_APPROVAL`: ý tưởng hoặc tài liệu chưa được người dùng phê duyệt.
- `RUNTIME_NOT_APPROVED`: chưa có approval runtime rõ ràng.
- `REAL_READY`: chỉ được dùng sau Gate 3, Gate 4, HIL, đo đạc và approval tương ứng.

Không được suy luận:

- Unit test pass ⇒ Gazebo runtime pass.
- Build pass ⇒ ROS graph, TF, QoS, Nav2, collision, reward hoặc training hoàn thành.
- Simulation pass ⇒ sim-to-real hoặc real robot sẵn sàng.
- Có source SafetySupervisor ⇒ functional safety đã đạt.
- Có PPO source/checkpoint ⇒ PPO đã train thành công.

`AGENTS.md` là quy tắc làm việc, không phải nơi tự cập nhật trạng thái milestone. Không tự thêm claim “pass”, “ready”, “đã build”, “đã chạy” hoặc “đã xác minh” vào file này. Evidence thay đổi phải nằm trong report/artifact có ngày, phạm vi, hash và lệnh kiểm tra rõ ràng.

## 3. Trạng thái kiến trúc hiện hành

```text
ARCHITECTURE_FROZEN
IMPLEMENTATION_READY
NOT_YET_REAL_ROBOT_VALIDATED
```

Hệ thống chưa được xác nhận trên robot thật.

`deploy_real` bị khóa cho đến khi hoàn thành toàn bộ đo đạc, artifact được phê duyệt, HIL, Gate 4 và approval rõ ràng của người dùng.

Mọi giá trị robot thật có nhãn `TBD_MEASURED` phải được đo và lưu evidence. Không được đoán, lấy từ simulation, hoặc sao chép từ robot khác.

## 4. Contract kiến trúc đã khóa

### 4.1. TF, localization và Ground Truth

- TF chính là `map -> odom -> base_link -> lidar`.
- Một TF edge chỉ có một authority.
- EKF là authority duy nhất được phép phát `odom -> base_link` trong kiến trúc chính thức.
- Authority của `map -> odom` phải phụ thuộc mode đã chọn và phải được xác minh từ contract cấu hình; không được để hai localization source cùng phát edge này.
- Ground Truth chỉ được dùng trong simulation cho evaluator, oracle, reset, reward và termination.
- Ground Truth không được đi vào policy observation, policy input, action path, primary TF tree hoặc deployment path.
- Không được dùng odometry legacy của `MecanumDrive` làm Ground Truth cho training.

### 4.2. Navigation hybrid

- Nav2 vẫn là thành phần cốt lõi; PPO không thay toàn bộ Nav2.
- Nav2 Planner Server tạo global path trong `NAV2_BASELINE` và `HYBRID_AI_LOCAL`.
- Nav2 Controller Server chỉ chạy trong `NAV2_BASELINE`.
- Trong `HYBRID_AI_LOCAL`, PPO là local controller; Nav2 Controller Server và FollowPath không được hoạt động như controller song song.
- Robot phải giữ holonomic motion. Không được làm mất hoặc vô hiệu hóa `vy`.

### 4.3. Policy observation và action

Policy observation có đúng 81 giá trị `float32`, theo thứ tự bất biến:

1. 72 LiDAR sectors.
2. 3 LocalReference features.
3. 3 measured twist features: `vx`, `vy`, `wz`.
4. 3 previous final-issued command features: `vx`, `vy`, `wz`.

Các yêu cầu bắt buộc:

- LiDAR sector phải tuân theo transform, đơn vị, xử lý invalid/no-return và normalization đã khóa trong Architecture/contract được phê duyệt. Không được đưa range thô theo mét vào policy nếu contract yêu cầu normalized range.
- LocalReference phải có frame, scale và normalization đúng contract. Trong hybrid navigation, LocalReference phải xuất phát từ global path và được biểu diễn trong `base_link`.
- Measured twist phải là measurement được phép, giữ đủ `vx`, `vy`, `wz` và được chuẩn hóa theo profile/contract.
- Previous command phải là lệnh vật lý cuối cùng đã qua SafetySupervisor và đã được FinalTwistPublisher phát; không được thay thế bằng raw PPO action, decoded candidate command, action dự đoán hoặc actuator diagnostic.
- Mọi policy input phải có provenance, lifecycle identity, generation/epoch và timestamp phù hợp.
- Policy input không được chứa hoặc giữ reference tới raw Ground Truth.

PPO action có đúng 3 giá trị `float32` theo thứ tự `[vx, vy, wz]`, normalized trong `[-1, 1]`.

Raw PPO action, decoded candidate command và final-issued command là ba khái niệm khác nhau. Không được đặt chúng cùng semantics chỉ vì đều có ba phần tử.

### 4.4. Command và safety

- `SafetySupervisor` là final command selector và limiter duy nhất.
- `FinalTwistPublisher` là publisher duy nhất được phép phát `/cmd_vel`.
- PPO, Nav2 và mọi nguồn khác chỉ được phát candidate command vào đường arbitration đã định nghĩa.
- Safety must fail safe khi input thiếu, stale, invalid, sai frame, sai generation, sai epoch hoặc sai provenance.
- Safety event, clamp, override, stop và final-issued command phải có receipt/provenance rõ ràng khi được dùng bởi lifecycle hoặc policy observation.
- E-stop vật lý phải độc lập với Linux, ROS 2, DDS và Python.
- Không được dùng simulation limit làm real-robot speed, acceleration hoặc stopping limit.

### 4.5. Artifact, map và hardware

- `artifacts/maps/<map_id>` là source of truth duy nhất cho map artifact.
- Map không được duy trì như mutable copy trong ROS package source.
- Hardware geometry thuộc `artifacts/hardware/<hardware_profile_id>/hardware_manifest.yaml`.
- Bridge/firmware/generated geometry phải dùng và xác minh cùng `hardware_config_hash`.
- Scenario, checkpoint, resolved config, policy I/O contract, map/world identity, randomization sample và evaluation result phải có hash/provenance theo contract trước khi được xem là artifact tái lập.

## 5. Package ownership

- `ROBOT_URDF_final_description`: robot description, Xacro/URDF, meshes, Gazebo model/world, static geometry.
- `mecanum_nav_rl_interfaces`: message/service/interface contract.
- `mecanum_base_bridge`: Pi–STM32 transport, telemetry, wheel odometry raw, final command transport; không phát TF.
- `mecanum_nav_rl`: pure core, DRL, simulation adapters, task logic, training, evaluation, deployment adapters, validators và safety logic theo ownership được phê duyệt.
- `mecanum_nav_bringup`: system launch, EKF, SLAM, AMCL/localization, Nav2, safety và mode configuration.

Không đặt DRL/training code vào robot-description package.

Không đặt system bringup configuration vào component package.

Không tự tạo package mới hoặc di chuyển ownership giữa package khi chưa có approval rõ ràng.

## 6. Legacy bị loại khỏi kiến trúc chính thức

`ROBOT_URDF_final_description/ROBOT_URDF_final_description/mecanum_env.py` là:

```text
LEGACY_NONCANONICAL
PRE_ARCHITECTURE_PROTOTYPE
EXCLUDED_FROM_OFFICIAL_RUNTIME
```

Không được:

- đọc sâu hoặc dùng file này làm evidence cho architecture hiện hành;
- dùng nó để suy luận policy exposure, GT leak, action semantics, reward, termination, safety hoặc runtime behavior;
- nêu nó như conflict của implementation chính thức;
- đề xuất sửa, migrate, xóa hoặc chạy nó;

trừ khi người dùng yêu cầu trực tiếp và rõ ràng về chính file đó.

Không tự coi prototype, draft, generated artifact hoặc build output là implementation canonical.

## 7. Ba mode làm việc

Mỗi prompt phải được hiểu theo một mode rõ ràng. Nếu prompt không rõ mode, hãy hỏi người dùng trước khi thực hiện hành động có thay đổi hoặc runtime.

### 7.1. `AUDIT_STATIC`

Chỉ được:

- đọc tài liệu, source, test, config, artifact, report và git metadata;
- đối chiếu contract/evidence;
- dùng lệnh read-only phù hợp như `rg`, `rg --files`, `git status`, `git diff`, `git diff --check`, hash/checksum hoặc parser offline;
- báo cáo mâu thuẫn, gap, risk và evidence.

Không được:

- sửa file;
- chạy Gazebo, ROS, Nav2, SLAM, training, evaluation, HIL hoặc hardware;
- tạo runtime guard, runtime run, launch packet hoặc approval artifact;
- tự chạy build/test nếu prompt chỉ nói audit static.

### 7.2. `OFFLINE_IMPLEMENTATION`

Chỉ được thực hiện sau prompt có phạm vi được phê duyệt rõ ràng.

Trước khi sửa:

1. Đọc Architecture và tài liệu contract liên quan.
2. Kiểm tra `git status --short`.
3. Xác định chính xác file, ownership, input, output, frame, unit, timestamp, provenance, failure behavior và test scope.
4. Báo ngay nếu phạm vi chạm contract khóa hoặc thay đổi hiện hữu của người dùng.

Trong khi sửa:

- Chỉ sửa file nằm trong prompt hoặc file phụ thuộc tối thiểu không thể tránh khỏi; nếu cần mở rộng, dừng và hỏi.
- Không tạo hàng loạt file trống/skeleton.
- Không thay đổi architecture để phù hợp code cũ.
- Không tạo bypass, fallback giả, fabricated transition, fabricated reward/penalty hoặc fake runtime evidence.
- Giữ pure core độc lập với `rclpy`, Gazebo, Gymnasium và Stable-Baselines3.
- Không dùng Ground Truth trong policy path.
- Không xóa artifact, guard, report, run history hoặc thay đổi không thuộc phạm vi.

Chỉ chạy build, formatter, linter hoặc test khi prompt cho phép rõ ràng. Kết quả offline không được gọi là runtime evidence.

### 7.3. `APPROVED_RUNTIME`

Chỉ được chạy khi prompt có approval runtime rõ ràng của người dùng và nêu đủ:

- runtime target;
- launch/run command được phép;
- config/artifact/hash được dùng;
- guard hoặc authority có capacity bằng 1;
- tiêu chí pass/fail;
- điều kiện dừng;
- xác nhận đúng một run được phép.

Quy trình bắt buộc:

```text
Audit official/version-matched
→ chốt contract và phạm vi
→ implementation nhỏ + offline test
→ review
→ hash review
→ runtime packet + capacity-one guard
→ user approval
→ đúng một runtime run
```

Quy tắc runtime:

- Không tự tạo guard hoặc runtime packet khi chưa được yêu cầu.
- Không retry một run đã consume, kể cả khi run fail hoặc timeout.
- Nếu run fail: giữ nguyên evidence, audit nguyên nhân offline, sửa offline, tạo approval mới.
- Artifact, guard, report và run history là bất biến.
- Không gọi cleanup là “SIGINT-only end-to-end” nếu launcher tự escalation sang `SIGTERM`; phải mô tả trung thực là launcher-managed escalation.
- Không chạy `deploy_real` khi chưa qua Gate 4.

## 8. Quy tắc implementation cho task, reward và reset

- Infrastructure failure không được biến thành RL transition giả hoặc task penalty giả.
- Reset, reward, termination, collision/contact, randomization và evaluator phải dùng contract/provenance riêng; không suy diễn chúng từ lifecycle core trừ khi implementation đã nối đúng contract.
- `goal_reached` fact không tự động là termination runtime hoàn chỉnh.
- Termination reason chỉ được coi là hoàn chỉnh khi contract yêu cầu đã có đầy đủ evaluator/source/evidence, gồm cả `STUCK` nếu Architecture yêu cầu.
- Scenario candidate bounds không được tự coi là valid area.
- Randomization chỉ được dùng khi có schema, bounds/distribution, seed, profile policy và immutable sample manifest.
- Reset runtime phải fail closed nếu pose, velocity, clearance, lifecycle barrier, sensor freshness hoặc scenario identity không hợp lệ.

## 9. Phase 0 Gazebo restriction

Không được kết luận rằng Gazebo `VelocityControl` và `MecanumDrive` cùng có `/cmd_vel` là lỗi runtime chỉ từ static configuration.

Trước khi kết luận hoặc đề xuất sửa, phải có evidence phù hợp về:

- behavior thực của plugin;
- Gazebo transport topic;
- ROS bridge direction;
- runtime topic graph;
- TF/odometry authority;
- mode/config đã chạy.

Trong Phase 0, không sửa URDF, Gazebo plugin configuration hoặc launch behavior liên quan nếu chưa có approval architecture-sensitive rõ ràng.

Historical idle rates hoặc historical exact scan–odom timestamps không được dùng để suy ra action cadence, timing robot thật, training success hoặc runtime readiness.

## 10. Repository hygiene và an toàn thao tác

- Giả định worktree có thể dirty; mọi thay đổi hiện hữu và untracked file thuộc về người dùng cho đến khi xác minh khác.
- Trước khi edit, kiểm tra `git status --short`.
- Không dùng `git reset --hard`, `git checkout --`, xóa recursive, hoặc thao tác phá hủy nếu người dùng không yêu cầu rõ.
- Không sửa `build/`, `install/`, `log/`, `__pycache__/`, checkpoint, model, dataset, artifact, guard, report hoặc run output nếu không nằm trong phạm vi được phê duyệt.
- Dùng `rg` hoặc `rg --files` ưu tiên khi tìm kiếm.
- Không tiết lộ secret, credential, token, serial identifier nhạy cảm hoặc nội dung private không cần thiết.
- Không tự cài dependency, tải package, kết nối hardware hoặc gửi dữ liệu ra ngoài nếu prompt không cho phép.

## 11. Format báo cáo bắt buộc

Mỗi báo cáo Codex phải bằng tiếng Việt và có các mục sau:

1. **Mode và phạm vi đã thực hiện**
2. **Files tạo/sửa/đọc**
3. **Authority/contract/evidence đã dùng**
4. **Kết quả check, build hoặc test đã chạy**
5. **Những gì không chạy hoặc không thay đổi**
6. **Mâu thuẫn, gap, risk hoặc blocker còn lại**
7. **`git diff --check` trong đúng phạm vi**, hoặc nêu rõ không có file thay đổi trong `AUDIT_STATIC`
8. **Trạng thái evidence** theo taxonomy ở mục 2.2

Báo cáo phải phân biệt rõ:

- fact đọc trực tiếp từ source/artifact;
- claim lấy từ report cũ;
- inference kỹ thuật;
- phần chưa có evidence.

Không được viết các câu như “đã hoàn thành”, “an toàn”, “real-ready”, “Gazebo-ready”, “PPO đã train thành công” hoặc “functional safety đạt” nếu không có evidence/gate tương ứng.

## 12. Quy tắc thay đổi file hướng dẫn này

`AGENTS.md` chỉ được sửa khi người dùng yêu cầu rõ ràng.

Không tự cập nhật file này sau milestone, test, build, audit hoặc runtime run.

Mọi thay đổi tại đây không được phép tự thay đổi Architecture. Nếu nội dung `AGENTS.md` mâu thuẫn Architecture hoặc ACR được phê duyệt, Architecture/ACR có authority cao hơn và phải báo cáo mâu thuẫn ngay.
