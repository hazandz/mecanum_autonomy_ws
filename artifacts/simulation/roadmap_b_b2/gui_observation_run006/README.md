# B22 GUI Observation RUN006

## Trạng thái và phạm vi

RUN006 là candidate công cụ chuẩn bị runtime cho B2.2. Owner đã duyệt việc kế
thừa acceptance §10 của ACR trong prompt chuẩn bị RUN006: Codex kiểm tra ảnh
thật của cửa sổ thuộc run, ghi
`automated_observation_verdict`, và luôn ghi
`owner_visual_review: NOT_PERFORMED`. Đây không phải Owner ACK, không cấp runtime
authorization và không tạo approval/acquisition trong bundle.

RUN001–RUN005 đều đã consume và kết thúc `FAIL`. Không retry, sửa hoặc tái sử
dụng evidence/approval/capacity của chúng. RUN006 có Run ID, packet, approval,
acquisition, mailbox và evidence path riêng.

RUN006 preparation base: `09d638f2a8e8407b2c353191345073f44b7cf561`, sole
parent `d76212b48a10b2244b36b3263e4c55ade3811d9d`. Production source pin
vẫn là `d6dc1c9cfe9d8820a37fa6aed290a13b7efe1336`; corrective này chỉ thay
packet-scoped helper launcher và không sửa package production. Architecture SHA-256
`432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
Production source pin và preparation base cùng trỏ tới commit chính xác này;
backend aggregate source fingerprint được pin riêng. Hash manifest, resolved
SOAK, semantic config và scenario được đối chiếu với bytes source/cài đặt thật.

## Hợp đồng đã đóng gói

- Run ID cố định `B22_GUI_OBSERVATION_RUN006`, capacity 1, bắt buộc `--gui true`.
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
- Các helper ngắn `window_helper`, `capture_helper` và `publisher` khởi chạy
  qua wrapper hai pha: wrapper giữ PID/PGID/SID/start ticks trong session riêng,
  parent kiểm identity và ghi evidence callback, rồi mới gửi release khớp nonce,
  argv hash và absolute deadline. Control dùng AF_UNIX framed JSON riêng, không
  lẫn stdout/stderr của lệnh đích. Wrapper gọi `execvpe` trong cùng process sau
  release; không dùng shell ghép lệnh. Mismatch, EOF, timeout, cancellation hoặc
  lỗi evidence trước release không cho target chạy.
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
- Startup RUN006 dùng wrapper trên installed supervisor contract, nhưng bỏ hẳn
  nhánh Owner ACK sau GUI process readiness; sau đó runner chuyển sang window
  binding và Codex review. Binding cạnh tranh cùng process/health monitor và
  deadline review. Final verdict kiểm lại absolute cleanup/total deadline sau
  evidence write, sink close, stream hash và completion publication; marker
  được publish muộn không làm runner trả PASS.
- Runner có first-failure latch: reason/source/phase và detection monotonic time
  được giữ trong bộ nhớ trước evidence I/O và cleanup. Latch không bị lỗi sau
  ghi đè; failure event được ghi ngay tại điểm phát hiện. Sink lỗi vẫn giữ latch
  trong final evidence nếu còn ghi được. Final result tách
  `primary_failure`, `secondary_failures` và `cleanup_errors`.
- Trước signal, cleanup ghi intent gắn với process identity đã xác minh. Exit
  sau signal đã yêu cầu được phân loại là cleanup event; exit không được yêu cầu
  trong cleanup vẫn là secondary failure. Không blanket-ignore process exit.

## Capacity, approval và đường dẫn cố định

Packet pin evidence root
`/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN006`, acquisition
`.../acquisition.json`, và approval
`/home/hazan/mecanum_runtime_approvals/B22_GUI_OBSERVATION_RUN006.owner.json`.
Production CLI không cho override các đường dẫn này. Approval tương lai phải
bind exact run ID, packet hash, packet commit, production source pin và tool
hashes. Guard là exclusive create; file acquisition tồn tại/dở dang vẫn tiêu
thụ lượt. Không dùng approval/guard RUN001.

Packet dùng chung install Debug đã pin tại
`/tmp/b22-run005-fresh-d6dc1c9/install` cùng Qt/XCB, X11 tools và tool-host
metadata. Static fingerprint không chứng minh renderer/engine đã load, desktop
đang hoạt động, ảnh render, mailbox ghi được, Codex đã mở ảnh hay process API
đã cleanup đúng. Đây chỉ là dùng chung install prefix tĩnh, không tái sử dụng
runtime evidence hoặc capacity RUN005. Packet hiện ghi runtime authorization `NOT_GRANTED` và các
runtime capability checks `NOT_PERFORMED`.

## Readiness worker RUN006

Server-scene readiness dùng đúng `RclpyReadiness` đã cài từ source pin, với
`bind_evidence_sink()` được forward qua adapter RUN006. Adapter chỉ đối chiếu
`plan.environment`; nó không gọi `bind_environment()` trên delegate.
`RclpyReadiness` sở hữu tiến trình tạm
`/home/hazan/step07_runtime_python312_pydantic_2_10_6/bin/python -m
mecanum_nav_bringup.local_training_readiness_worker`; đây là startup helper,
không phải main daemon. Node tạm vẫn là `b2_server_scene_readiness`.

Khi lỗi dẫn tới hủy operation, readiness worker và orchestration dùng cùng
CleanupWindow 60 giây của lượt. Giới hạn worker cleanup 3 giây nằm bên trong
cửa sổ này, không cộng thêm. Operation chưa join được giữ làm residue UNKNOWN
và kết quả là FAIL.

Mỗi backend status và clock sample được ghi tại thời điểm nhận trước khi
validation. `RECEIVED_NOT_VALIDATED` chỉ ghi nhận dữ liệu thô; event phát hiện
lỗi gắn sample index và detection time trước cleanup. Receive gap không phải
bằng chứng backend publish gap. RUN003 journal không được sửa hoặc diễn giải
lại.

Các regression RUN006 kiểm first-failure attribution trên default production
orchestration với readiness/process/evidence boundaries giả. Chúng không chứng
minh thời điểm lỗi backend thực trong RUN004; finding R003-02 vẫn UNKNOWN.

## Kiểm tra và evidence boundary

Các regression được phép dùng injected clocks/processes/filesystem/ROS factories;
không tạo middleware, `QApplication`, subprocess, X connection hoặc screenshot.
Offline test/lint/compile/hash chỉ xác nhận source/preflight contracts. Chúng
không phải runtime evidence, independent audit, Gate 1, B2 closure hoặc quyền chạy.
Sau khi exact commit và packet/tool pins được audit, một prompt runtime riêng
của Owner mới có thể cấp quyền. Khi được cấp, Codex tự source ROS Jazzy và
install prefix đã pin, kiểm identity/dependencies/roots trước consume, gọi
runner đúng một lần, theo dõi startup và health, capture cửa sổ đã bind, mở ảnh
đã hash, publish mailbox result, thu evidence và cleanup. Owner không cần chạy
terminal, nhập ACK/token, gửi ảnh hoặc tạo file phản hồi giữa lượt. Lượt chuẩn
bị hiện tại chưa tạo approval/acquisition và chưa được phép chạy.

## Corrective R005-01–R005-03

Cleanup intent, dispatch outcome và process exit được ghi riêng, gắn với
identity đầy đủ của process đã xác minh. Event exit sau dispatch chỉ ghi thứ
tự quan sát, không khẳng định signal là nguyên nhân; exit của leader không
được gọi là requested nếu chỉ descendants được signal hoặc dispatch không
được xác nhận.

Các lỗi backend, clock, graph và heartbeat được latch tại điểm phát hiện trước
khi ghi event failure và trước cleanup. Completion giữ cả lỗi sticky trong
latch lẫn lỗi cleanup/finalization; verdict vẫn FAIL nếu evidence I/O hoặc
cleanup có lỗi. Các kiểm tra này là offline regressions dùng fakes, không xác
nhận runtime behavior của RUN004 hoặc RUN006.

## RUN006 helper release protocol

Short-lived window, capture, and file-only publisher helpers start as managed
wrappers in their own process session. The parent records and validates the
live process identity and writes pre-release evidence before authorizing target
execution. A private control channel, separate from target stdout/stderr, uses
`READY_FOR_RELEASE` → `RELEASE` → `RELEASE_ACCEPTED` → `EXEC_COMMIT`. The
wrapper calls `execvpe` only after the final bound commit, retaining its
PID/session identity. Parent loss or channel EOF before that commit leaves the
target unexecuted. This is an offline corrective and grants no runtime or
capacity authority.
