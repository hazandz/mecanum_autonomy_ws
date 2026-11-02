# B22 GUI Observation RUN002

## Trạng thái và phạm vi

RUN002 là candidate công cụ chuẩn bị runtime cho B2.2. Owner đã duyệt riêng
acceptance/design implementation trong prompt `PROMPT_CODEX_B22_RUN002_OFFLINE_IMPLEMENTATION`:
Codex kiểm tra ảnh thật của cửa sổ thuộc run, ghi
`automated_observation_verdict`, và luôn ghi
`owner_visual_review: NOT_PERFORMED`. Đây không phải Owner ACK, không cấp runtime
authorization và không tạo approval/acquisition trong bundle.

RUN001 đã consume tại commit `09a3304e217628a11c44f0b1380ad1a7d5ae533a` rồi
kết thúc `FAIL`. Không retry, sửa hoặc tái sử dụng evidence/approval/capacity
RUN001. RUN002 có Run ID, packet, approval và acquisition riêng.

## Hợp đồng đã đóng gói

- Run ID cố định `B22_GUI_OBSERVATION_RUN002`, capacity 1, bắt buộc `--gui true`.
- Một RSP, một parameter bridge, một Gazebo Sim server-only, một GUI-only,
  một world `b2_training_arena`, robot `mecanum_b2` và backend
  `NATIVE_B2_BACKEND_V1`; không launch song song hoặc simulator thứ hai.
- Giữ Sensors, OGRE2/headless rendering, SceneBroadcaster và GUI config
  `MinimalScene`, `GzSceneManager`, `InteractiveViewControl`.
- `ROS_DOMAIN_ID=83`; một UUID session và một nonzero uint64 coordinator ingress
  được tạo một lần, truyền nguyên vẹn qua descriptor/LaunchPlan/bound world/
  consumers. `GZ_PARTITION=mecanum_b2_<uuid-without-hyphens>`.
- Observer sở hữu context và `SingleThreadedExecutor` riêng; chỉ đọc
  `/mecanum/local_training/backend_state` và `/clock`, với clock QoS
  BEST_EFFORT/VOLATILE/KEEP_LAST(10). Không control publisher/service client.
- Capture X11/XCB-only: `xwininfo`, `xprop`, và
  `PyQt5.QtGui.QScreen.grabWindow(WId)` chỉ cho cửa sổ được bind tới PID/PGID/
  start ticks/executable/argv/partition của GUI do run sở hữu. PNG mới, không
  chỉnh sửa, mode 0600, tối đa 32 MiB, decode và hash lại. Capture chạy trong
  helper process có ownership; parent kiểm tra PNG/hash trước atomic publication
  trong khi health monitor tiếp tục chạy.
- Trước capacity-one acquisition, runner xác minh Qt/XCB, X11 tools, Python
  module origins/versions, và pinned system-package versions từ metadata cài
  sẵn. Acquisition lưu các dependency facts đã đọc thực tế.
- Runner phát request JSON bất biến; Codex đọc request, rehash ảnh, mở ảnh thật,
  rehash lần nữa rồi gọi entry point publisher một lần. Mailbox dùng exact
  request/result schema, mode 0700/0600, `O_NOFOLLOW`, directory descriptors,
  `fsync` và hard-link no-replace. Mailbox là consistency/provenance boundary,
  không phải xác thực bảo mật.
- Review checkpoint 60 giây bắt đầu trước window enumeration, gồm bind/capture/
  persist/request/Codex review/publisher/runner validation. Không gia hạn.
  Trước checkpoint phải còn ít nhất 121 giây active budget. Sau review PASS,
  clock cần sample thật ổn định một giây rồi observation đủ 60 giây.
- Server readiness 30 giây, GUI startup 30 giây, graph convergence 30 giây;
  active/cleanup/total caps lần lượt 240/60/300 giây từ consume.
- Chỉ PASS nếu scene/graph/status/heartbeat/clock/ảnh/review/evidence đều đạt,
  cleanup sạch và final completion marker được ghi sau khi sink đóng thành công.
  Mọi process/evidence/health failure là FAIL; không restart/retry. Không suy
  contact/scan/physics/motion/braking/training/functional safety từ quan sát.
- Startup RUN002 dùng wrapper trên installed supervisor contract, nhưng bỏ hẳn
  nhánh Owner ACK sau GUI process readiness; sau đó runner chuyển sang window
  binding và Codex review. Binding cạnh tranh cùng process/health monitor và
  deadline review. Final verdict kiểm lại absolute cleanup/total deadline sau
  evidence write, sink close, stream hash và completion publication; marker
  được publish muộn không làm runner trả PASS.

## Capacity, approval và đường dẫn cố định

Packet pin evidence root
`/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002`, acquisition
`.../acquisition.json`, và approval
`/home/hazan/mecanum_runtime_approvals/B22_GUI_OBSERVATION_RUN002.owner.json`.
Production CLI không cho override các đường dẫn này. Approval tương lai phải
bind exact run ID, packet hash, packet commit, production source pin và tool
hashes. Guard là exclusive create; file acquisition tồn tại/dở dang vẫn tiêu
thụ lượt. Không dùng approval/guard RUN001.

Packet ghi 47 installed fingerprints của overlay
`/tmp/b22_gui_observation_run001_install` cùng Qt/XCB, X11 tools và tool-host
metadata. Static fingerprint không chứng minh renderer/engine đã load, desktop
đang hoạt động, ảnh render, mailbox ghi được, Codex đã mở ảnh hay process API
đã cleanup đúng. Packet hiện ghi runtime authorization `NOT_GRANTED` và các
runtime capability checks `NOT_PERFORMED`.

## Kiểm tra và evidence boundary

Các regression được phép dùng injected clocks/processes/filesystem/ROS factories;
không tạo middleware, `QApplication`, subprocess, X connection hoặc screenshot.
Offline test/lint/compile/hash chỉ xác nhận source/preflight contracts. Chúng
không phải runtime evidence, independent audit, Gate 1, B2 closure hoặc quyền chạy.
Lượt tiếp theo cần audit exact commit, packet/tool pins, và Owner runtime
authorization riêng trước khi có một invocation.
