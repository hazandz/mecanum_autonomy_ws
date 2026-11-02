# B22 GUI Observation RUN001

## Phạm vi

Gói này chuẩn bị đúng một lượt quan sát GUI cho `B2_SOAK_V1`, ở trạng thái
paused và actuator inhibited. Đây là công cụ `OFFLINE_IMPLEMENTATION`; tạo gói,
build, unit test và audit packet không chạy ROS graph, Gazebo, GUI, launch,
transport discovery, service, reset, motion, training, soak, HIL hoặc hardware.

RUN001 chỉ được gọi sau independent audit và Owner approval cho đúng packet
SHA-256, commit và bốn tool SHA-256. Không dùng approval của packet khác. Không
có retry: nếu acquisition path đã tồn tại, kể cả JSON dang dở, run bị coi là đã
consume/không xác định.

## Preflight và approval bên ngoài

`packet.json` ghi install prefix và file fingerprints thực tế của build 5
package tại `/tmp/b22_gui_observation_run001_install`. Runner kiểm tra lại các
pin/hash, working `HEAD`, bytes packet trong commit, approval JSON, TTY của
Owner và socket desktop hiện hữu trước khi consume. `gui:=false` bị từ chối
trước consume. Không dùng `xhost+`, sudo, virtual display hoặc cài dependency.

Owner approval file là do Owner cung cấp sau audit; gói này không tạo file đó.
Schema JSON chính xác:

```json
{
  "schema_id": "b22_gui_observation_owner_approval/v1",
  "run_id": "B22_GUI_OBSERVATION_RUN001",
  "packet_sha256": "<SHA-256 chính xác của packet.json>",
  "packet_commit": "<commit đã được Owner duyệt>",
  "production_source_pin": "7d4f2ad1c38c8021f13a6a88ebf707053718eb02",
  "tool_sha256": {
    "observation_guard.py": "<SHA-256>",
    "observation_runner.py": "<SHA-256>",
    "observation_sink.py": "<SHA-256>",
    "test_observation_packet.py": "<SHA-256>"
  }
}
```

Sau khi có approval riêng, lệnh dự kiến được Owner nhập trực tiếp trong
terminal có TTY, với environment của overlay đã ghi trong packet:

```sh
source /opt/ros/jazzy/setup.bash
source /tmp/b22_gui_observation_run001_install/local_setup.bash
/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python \
  artifacts/simulation/roadmap_b_b2/gui_observation_run001/tools/observation_runner.py \
  --gui true \
  --approval-file /absolute/path/to/owner-approval.json \
  --approved-commit <Owner-approved-commit>
```

Không chạy lệnh trên trong bước chuẩn bị này. Runner kiểm tra domain riêng
`ROS_DOMAIN_ID=83`, desktop socket, exact installed files và capacity-one guard
ngoài repository. Acquisition và evidence root không nhận CLI override; kiểm tra
symlink/collision xảy ra trước consume. Acquisition xảy ra trước mọi process/participant runtime.

## Trình tự runtime được đóng gói

1. Kiểm tra approval/pins/install/TTY/desktop và strict `--gui true`.
2. Tạo session ID, coordinator-ingress identity, GZ partition và bound-world
   descriptor đúng một lần; ghi rõ source-world hash và runtime-world hash.
3. Consume guard bằng exclusive atomic creation tại
   `/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN001/acquisition.json`.
4. Ghi evidence JSONL append-only ngoài repo; giữ bound world, descriptor và
   robot-state-publisher parameter file theo chế độ không ghi đè.
5. Dùng `build_launch_plan`, `write_bound_world`,
   `LocalTrainingProcessSupervisor`, `RclpyReadiness` và
   `SubprocessProcessLauncher` đã audit. Chạy một `robot_state_publisher`, một
   bridge, một server và một GUI trong các process group do runner sở hữu.
6. Chờ server/scene tối đa 30 s, GUI process tối đa 30 s, Owner acknowledgment
   tối đa 60 s. Owner nhập screenshot path tuyệt đối và tự gõ
   `OWNER_ACK_SCENE`; runner xác minh screenshot là file không rỗng và ghi hash.
7. Observer ROS context riêng chỉ subscribe `/mecanum/local_training/backend_state`
   và `/clock`; không tạo control publisher/service client. Chờ clock ổn định
   một giây rồi quan sát đủ 60 s. Inventory ROS phải có observer,
   `robot_state_publisher`, `ros_gz_bridge` và `mecanum_sim_backend` trong
   namespace `/`. `b2_server_scene_readiness` chỉ node tạm của startup; graph
   có tối đa 30 s sau readiness để phản ánh sự biến mất của node này và hội tụ
   các participant thường trực. Participant lạ, trùng hoặc participant thường
   trực còn thiếu sau budget làm lượt chạy thất bại.
8. PASS yêu cầu backend identity bất biến, `paused=true`,
   `actuator_inhibited=true`, `fault_flags=0`, không applied receipt, heartbeat
   không mất quá một giây và simulation clock không tiến. Scan/contact capability
   ở trạng thái paused không được chấm PASS.
9. Cleanup chỉ nhắm tới process group/session do runner sở hữu; escalation có
   giới hạn SIGINT → SIGTERM → SIGKILL. Ghi cleanup/residue lỗi trung thực.

Tổng hoạt động sau consume tối đa 240 s; cleanup tối đa 60 s riêng; tổng hard
cap 300 s. GUI crash, backend mismatch, evidence lỗi, timeout hoặc mất inhibit
thất bại và kích hoạt cleanup. `ABORTED_BY_OWNER` chỉ được ghi khi Owner trực
tiếp nhập `OWNER_ABORT_GUI` trên foreground TTY; GUI exit không rõ nguyên nhân
hoặc crash là `FAIL`. Không restart server hoặc GUI, không đổi motion permission.

## Trạng thái evidence

Packet/tool bytes là candidate chuẩn bị runtime, chưa có independent audit hoặc
Owner runtime approval. Evidence tối đa là `IMPLEMENTED_OFFLINE_ONLY`; chưa có
GUI observation hay runtime evidence. Không tạo guard acquisition thật trong
quá trình chuẩn bị.

## Lịch sử RUN001 và corrective observer

RUN001 đã được consume đúng một lần trên commit
`09a3304e217628a11c44f0b1380ad1a7d5ae533a` và kết thúc `FAIL`. Evidence ngoài
repository ghi `guard_consumed`, sau đó lỗi observer
`TypeError: 'NoneType' object does not support the context manager protocol`;
final status trong JSONL là `FAIL`. Log lịch sử không chứa traceback đầy đủ.
Corrective follow-up chuyển observer sang executor riêng gắn với context riêng
và thêm regression offline. Đây là source-level correction, không chứng minh
runtime đã thành công.

RUN001 không được chạy lại. Packet/tool hashes corrective mới không thể dùng lại
approval cũ; bất kỳ lượt quan sát nào sau này cần packet/run identity riêng,
independent exact-commit audit và Owner authorization mới. RUN002 Codex-owned
GUI capture hiện chỉ là thiết kế đề xuất; thay đổi acceptance L2 đang chờ Owner
phê duyệt.
