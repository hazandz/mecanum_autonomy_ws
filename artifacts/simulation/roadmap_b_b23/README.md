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
