# B2.3 LOCAL_TRAINING

Base: `c035d95be8631cba87daf788a36d47cc47b8fe07`.
Nhánh: `roadmap-b-b23-local-training-integration`.

Owner đã duyệt L2-PAUSE, L2-ADMISSION, D03, D04, D05, offline/Git và B23_CAMPAIGN trong hội thoại giao việc. Quyền campaign chỉ có hiệu lực theo phase offline → smoke → fault/task → soak. Rollback time_only và chủ động SetEntityPose cho fixture task cần packet cụ thể được Owner duyệt.

`campaign.json` ghi authority, ma trận, deadline và trạng thái chưa chạy. Đây là hồ sơ thiết kế campaign, chưa phải packet có source/install/hook/argv pin đầy đủ hoặc bằng chứng runtime. Mỗi lượt thực tế cần ID, guard capacity-one, khóa chung, pin và evidence riêng. Không khởi chạy khi còn residue chưa xác minh.

Bốn sổ append-only bắt buộc: `policy_adapter_issued`, `policy_final_published`, `policy_backend_applied`, `b1_transition_committed`. Soak phải đạt cùng lượt: 30 reset B1 commit + backend confirm, 1.000 POLICY issuance tại adapter, 1.000 step apply và 1.000 B1 commit; không bù slot hoặc ghép lượt.

Acceptance ID cũ `ROADMAP_B_B2_BOUNDED_SOAK_PENDING_ASSET_BINDING` là định danh lịch sử trước asset binding. Nghiệm thu B2.3 phải dùng resolved config `BOUND` và xác minh asset closure của đúng install; không chuyển ID cũ thành bằng chứng PASS.

B2.2 đã đóng; nguyên nhân RUN008 vẫn `UNKNOWN`; Owner visual ACK `NOT_PERFORMED`. B2.3 chưa được audit/đóng; Gate, Gym/PPO và robot thật thuộc phạm vi riêng.

## Log phụ thuộc trực tiếp — standing authorization

- `artifacts/simulation/roadmap_b_b2/gui_verification/tools/observation_runner.py`: producer contact-only thực sự dùng interface backend-control đã lên schema 2; dùng constant từ generated request để không gửi schema 1 cứng.
- `artifacts/simulation/roadmap_b_b2/gui_verification/tools/test_observation_runner.py`: regression chạy đúng builder lồng của `run_contact()` với generated interface, kiểm schema, operation, sequence và reference START; không tạo ROS context.
- Quyền: Owner standing authorization B2.3 trong hội thoại; B23-SCOPE-01 không còn cần duyệt file riêng. Các path trên không đổi capture API hoặc acceptance GUI.

## Checkpoint offline đang thực hiện

- `80fd344e3291f215c43354dc81d39d9dcf4ea276`: normal QUERY revocation đã push; base vẫn `c035d95be8631cba87daf788a36d47cc47b8fe07`.
- Producer contact-only: RED trên builder schema 1, GREEN 53 tests với builder dùng generated constant. Không chạy lại runtime contact-only B2.2.
- Admission: ba regression production-path RED trước token gate. Vòng check đầu lộ hai regression legacy/fixture clock; sau đối chiếu và sửa có căn cứ, vòng thứ hai đạt native invariants 72, receipt gate 20, contact coverage 9, trace 4. Các log rớt được giữ riêng.
- Pause/fence: implementation và kiểm thử tiếp tục; các kết quả trên không chứng minh reset/POLICY runtime hoặc soak B2.3.
- Bốn vòng controller, hai vòng corrective collector và hai vòng preflight B2.2 cũ được giữ; không tính các lần pytest thành số vòng sửa.

- Lifecycle normal: source `SafetyLifecycleCore.rearm()` thật trả Active/READY với `motion_permitted=true`; consumer bind/contact/observation0 trước đây bắt buộc false. Consumer B2.3 tiếp nhận fact thật và vẫn giữ native POLICY đóng cho tới proof/admission/receipt. Reset NON_READY vẫn không được mang motion permission.
- `runtime_safety/safety_contract.py` và `safety_lifecycle_node.py`: LOCAL_TRAINING giữ event barrier cố định qua heartbeat, header giữ thời điểm publish thật; mode NAV2 mặc định giữ hành vi cũ. Đây là dependency để bind/request không đổi barrier do heartbeat; không sửa interface thứ ba.

- `runtime_safety/safety_supervisor_node.py`, `final_twist_publisher_node.py` và test tương ứng: nối mode LOCAL_TRAINING với đầu vào thật; giữ mode NAV2 mặc định. Safety không giả TF/localization của Nav2: xác minh extrinsic scan thực, noisy admission, lifecycle và backend/contact theo profile B2. Final publisher giữ POLICY key qua tick, dùng UUID từ B1, counter SAFE_STOP độc lập và publish-before-receipt.
- `safety/command_safety_core.py`: trích đúng phép giao velocity/acceleration/jerk thành helper dùng chung; regression core cũ giữ nguyên semantics và kết quả.
- `runtime_simulation/local_training_ingress.py` và `test_local_training_ingress.py`: producer schema 2, giữ receive/source time, ghép oracle/status bằng stamp và iteration thật, dữ liệu POLICY chỉ chứa noisy snapshot; không tạo proof hay application giả. ACK phải đi trước sample/admission; closing input không cần token.
- Native checkpoint `closing-check`: 94 invariants, 20 gate, 9 contact, 4 trace tests đạt; đây là kiểm chứng fakes/unit, chưa có runtime B2.3. Full coordinator/B1/runner và campaign vẫn đang triển khai.

- Sau checkpoint `0cf9382da1c6310bae2fd785067ad15c9c296fe4` đã push/readback: tiếp tục adapter B1 và runner; chưa có runtime B2.3.
- Adapter B1: lần check đầu có 3 failure cùng nguyên nhân truyền cả receipt reset trước action barrier vào core cutoff; giữ logs `b1-adapter`. Giới hạn cửa sổ pha ở adapter, giữ lịch sử/kiểm chuỗi toàn cục tại ingress; check tiếp theo 20 tests đạt, sau nối ledger là 48 tests đạt.
- Rclpy cài đặt `7.1.11`: source upstream đúng tag xác nhận MessageInfo là mapping không có publisher GID. Sửa consumer/fake theo API thật: pin graph endpoint, ghi bytes sau publication thật tại Safety producer rồi đối chiếu payload nhận qua DDS. Không sửa `SafetyState` hoặc thêm ROSIDL. Check nhóm source/consumer 80 tests đạt.
- Status native trước Safety input đầu tiên: regression exact checkpoint tái hiện lifecycle 0/0/0 sau BIND_SESSION APPLIED. Sửa nhánh đã bind để phát context native đã APPLIED; nhánh chưa bind/contact-only giữ nguồn cũ. Native invariants 95 tests đạt.
- Reset async dùng validator D03 và deadline chung; 52 tests reset đạt, gồm braking trước cửa sổ 21 mẫu. Không dùng thread/spin lồng hoặc coordinator ControlWorld pause trong đường này.
- `runtime_simulation/b23_runner.py` và `test_b23_runner.py`: WIP runner/ownership/deadline; cần hoàn thiện controller/entrypoint, build/install binding và kiểm offline trước smoke. FinalTwistPublisher phải là process riêng để ca R07d thay đúng process; boot chưa bind giữ inhibit, nối sources bằng ACK native gốc qua bootstrap riêng của runner. Không đổi interface thứ ba.

- Nối runner R01a: Final publisher process riêng, boot chưa bind không publish; ACK source binding dùng bytes native gốc qua bootstrap private, giữ một publisher `/cmd_vel`. Auxiliary launch đi qua registration/admission của supervisor hiện có, không override `start()`. `setup.py` thêm entry point campaign do runner B2.3 cần được cài.
- Control replay giữ request bytes và sequence/revision; QUERY invalidated từ native không bị Python thay bằng proof cũ. Lock wait dùng deadline gốc. Check `bootstrap-replay`: 85 tests; `step-wiring`: 88; `evidence-io`: 91. Không cộng các số test lặp thành tổng test duy nhất.
- Check `runner-entry` giữ 96 passed/1 failed do fixture `/proc/stat` đặt starttime cột 21 thay vì 22; lưu nguyên source/log. Sửa đúng fixture, `runner-entry2` 97 passed. Không gọi lỗi fixture là behavioral RED.
- Phần packet/guard/parent/terminal R01a đang kiểm offline; chưa consume hoặc chạy runtime. Các ca fault/task và soak chưa được triển khai đủ để chạy.
- Summary failure giữ nguyên pending cleanup batch: RED `pending-batch-red` tái hiện TypeError serialize DTO thật; sửa serializer chỉ cho dataclass/Path, không tạo trạng thái sạch. Nhóm `runner-cleanup-budget` 102 tests đạt. IPC JSON xuất atomic/no-overwrite để reader không nhận record đang ghi dở.
- `B23-RESET-STOP-BUDGET`: RED `reset-braking-red` tái hiện braking >2 s ROS vẫn đi tiếp trong 5 s steady. Giữ budget cũ, nối stop deadline từ mốc reset bắt đầu và W0 source stamp; nhóm `reset-stop-budget` 157 tests đạt, gồm 55 reset tests. Đây là một vòng RED–sửa–GREEN của finding mới; không đặt lại lịch sử các finding trước.
- Snapshot `runner-check`: build đúng năm package đạt, 760 test duy nhất từ 29 suite Python và bốn binary native đạt; bản runner sau kiểm deadline/terminal đang được chốt lại. Không gọi các số tổng hợp/lặp lại là một lần test mới hoặc runtime evidence.
- Snapshot `runner-final` tiếp theo: build năm package, 768 tests (29 suite Python + bốn binary native) và install/ELF closure đạt. Sau review entrypoint, giữ preflight manager `running`, bảo toàn `INVOCATION_ID` thật qua env sạch, không expand argv/environment packet; nhóm `unit-env` 158 tests đạt. Các bytes này đang được build thành prefix riêng trước runtime.
- Host metadata hiện hành: hazan/UID 1000, systemd 255.4-1ubuntu8.18, user manager running, cgroup v2 rw. Chỉ đọc metadata; chưa tạo unit. Hai lượt B2.2 cuối có terminal/outer cleanup đã audit, được giữ nguyên.
- Outer unit R01a pin Type=exec, RemainAfterExit=yes để giữ terminal facts trước guarded stop, KillMode=control-group và cap 180 s; worker/parent dùng active 120 s + một cleanup deadline tối đa 60 s. Giới hạn memory riêng unit 5 GiB, OOMPolicy=stop; không đổi cấu hình host hoặc threshold Safety. Mẫu argv trong packet chỉ thay self-hash sau publication, giữ InvocationID thật qua wrapper env sạch.
- `runner-smoke`: 769 tests và install/ELF closure đạt trên snapshot riêng. Source packet/property pin vừa chốt được kiểm trong snapshot tiếp theo trước bất kỳ consume nào; không cộng các lượt test trùng thành tổng mới.
- `B23-POLICY-TOPIC-01`: Architecture DOCX quy định `/mecanum/cmd_policy` là CommandEnvelope sau adapter. RED hai regression (publisher wiring trong source thật và constructor Safety bằng Node fake) tái hiện topic WIP sai. Sửa đúng hai đầu LOCAL_TRAINING sang topic canonical; nhóm `policy-topic-green` 161 tests đạt, mode NAV2 mặc định không đổi. Không thay contract.
- Gazebo cài thật là 8.11.0; đọc `cmdsim8.rb` xác nhận `--seed` được truyền vào runServer. R01a pin world seed 20261029 trong argv server thực, episode seed 2026102900/2026102901 trong packet; không chỉ ghi seed như metadata.
- Snapshot `smoke-exact`: 924 tests duy nhất trong 32 suite Python và bốn binary native đạt; build năm package và install/ELF closure đạt. Đọc systemd 255 xác nhận biến trong ExecStart mặc định bị expand: mẫu launch khóa `--expand-environment=no`, giữ wrapper env/InvocationID đúng bytes. Chỉ chốt runtime sau kiểm bytes cập nhật này.
