# Thiết kế Codex-owned GUI observation RUN002

**Trạng thái:** `OWNER_APPROVED_L2_IMPLEMENTATION`; implementation candidate
pending independent audit; `RUNTIME_NOT_AUTHORIZED`.

**Phạm vi:** B2.2 L2, một lượt GUI quan sát paused/inhibited sau khi Owner duyệt
pins và cấp quyền runtime riêng. RUN001 đã consume và `FAIL` tại commit
`09a3304e217628a11c44f0b1380ad1a7d5ae533a`; evidence lịch sử của nó không được
sửa hay tái sử dụng. RUN002 phải có packet, hash, audit và capacity-one guard
riêng.

## Acceptance L2 được Owner duyệt cho RUN002

Owner đã duyệt qua prompt `PROMPT_CODEX_B22_RUN002_OFFLINE_IMPLEMENTATION` việc
thay trực tiếp xác nhận scene bằng Codex kiểm tra ảnh thật của cửa sổ thuộc run.
Evidence giữ hai trường tách biệt:

```json
{
  "automated_observation_verdict": "PASS | FAIL",
  "owner_visual_review": "NOT_PERFORMED"
}
```

Trường thứ nhất ghi nhận kết quả kiểm tra máy/agent trên scene query và ảnh thật
của cửa sổ thuộc lượt chạy. Trường thứ hai ngăn diễn giải kết quả thành xác nhận
của con người. Acceptance này chỉ áp dụng RUN002; runtime vẫn cần exact packet/
commit audit và Owner runtime authorization riêng. Owner quyết định cấp quyền
trước run và xem xét evidence sau run.

## Tiến trình, identity và ownership

Một Codex-managed runner sẽ sở hữu đúng một run descriptor, một `session_id`
UUID, một `coordinator_ingress_instance_id` kiểu uint64 khác zero, một
`GZ_PARTITION`, `ROS_DOMAIN_ID` đã duyệt, thư mục tạm và process groups của
RSP, bridge, server, GUI cùng các observer phụ. Hai identity được sinh đúng một
lần trước khi tạo participant, ghi giống nhau vào acquisition/descriptor và
được truyền cho backend/consumer theo contract đã pin. `session_id` là string
UUID; coordinator ingress giữ nguyên kiểu integer/uint64 của source. Không
chuyển coordinator ingress thành UUID, không ép UUID thành số. Căn cứ source:
`artifacts/simulation/roadmap_b_b2/gui_observation_run001/tools/observation_runner.py`
function `build_runtime_plan` tạo `session_id = str(uuid.uuid4())` và
`ingress_id = secrets.randbits(64) or 1`; truyền nó vào audited
`build_launch_plan` rồi chép `plan.session_id`/`plan.coordinator_ingress_instance_id`
vào run descriptor và acquisition. Cùng source pattern có trong
`mecanum_nav_bringup/mecanum_nav_bringup/local_training_process_supervisor.py`
function `_run_from_cli`, tạo UUID string và nonzero 64-bit ID.
`mecanum_nav_bringup/mecanum_nav_bringup/local_training_launch_contract.py`
dataclass `LaunchPlan` định kiểu coordinator là `int`; `build_launch_plan` từ
chối bool/non-int/zero và giữ cùng giá trị trong plan; `bind_world_for_scenario`
ghi nó vào plugin SDF. `mecanum_nav_rl_interfaces/srv/LocalTrainingBackendControl.srv`
khai báo `uint64 coordinator_ingress_instance_id`. Backend
`mecanum_sim_backend/src/backend_system.cpp` đọc giá trị qua `ParseU64`, fault
khi zero và so sánh request identity với pin đã bind. `acquisition.session_id`
và `run_descriptor.session_id` cùng `LaunchPlan.session_id`, bound world,
backend status và consumer phải chứa cùng UUID. Các field
`coordinator_ingress_instance_id` trong acquisition, descriptor, LaunchPlan,
bound world plugin và consumer request phải chứa cùng uint64 khác zero. Không
sửa `.srv`, schema hoặc production interface cho thiết kế này.

Composition giữ nguyên: một RSP, một bridge, một Gazebo server server-only với
`--headless-rendering`, một GUI-only cùng partition, backend và
readiness/observer đã audit. Không mở launch song song, simulator thứ hai,
publisher điều khiển hoặc service client điều khiển.

Runner xác minh PID, PGID, session ID và `/proc` start ticks trước mỗi signal;
chỉ process group do run tạo được cleanup. GUI close/crash không restart server,
GUI hoặc quyền chuyển động. Cleanup có giới hạn `SIGINT → SIGTERM → SIGKILL`
trong tối đa 60 s; residue/identity không xác minh được làm final result `FAIL`.

## GUI window binding và ảnh

Inventory ngoại tuyến tại thời điểm thiết kế tìm thấy các thành phần sau; đây là
package/API availability, không phải bằng chứng desktop đang hoạt động hay GUI
đã render:

| Thành phần | Kết quả đọc tĩnh hiện tại |
|---|---|
| `/usr/bin/xwininfo`, `/usr/bin/xprop` | Có; `x11-utils 7.7+6build2` |
| `PyQt5.QtGui.QScreen.grabWindow(WId, ...)` | Có trong PyQt5 5.15.10; callable API cho ảnh một cửa sổ |
| Qt XCB platform plugin | Có tại `/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms/libqxcb.so`; SHA-256 `8545cd0fee43b36561cc8bf14d6a87096b20c93da24ee103d0266c0afcf38364` |
| `xwd` | Có, nhưng Pillow 10.2.0 không có XWD decoder khả dụng; không chọn đường này |
| `wmctrl`, `xdotool`, ImageMagick `import`, `magick`, `gnome-screenshot`, `scrot`, `grim`, `swaymsg`, `wayland-info` | Không có trên PATH lúc kiểm kê |
| Codex local image viewer | `view_image` API khả dụng để agent xem file cục bộ sau capture; chưa dùng trong lượt offline này |
| Codex managed process/file tools | `exec_command` trả session handle cho tiến trình dài hạn; `write_stdin` có thể poll mà không gửi input; `view_image` đọc ảnh local; `exec_command` có thể chạy writer một lượt. API có trong tool catalog hiện tại, chưa được thử runtime |
| Local evidence filesystem | `/home/hazan` nằm trên `/` ext4; mount của sandbox hiện tại là `ro`. Python 3.12.3 có `O_NOFOLLOW`, directory flags, `os.open/link/fsync/fstat`; không thử ghi. Mặc định Codex sandbox hiện không thể publish mailbox trong canonical evidence root |

RUN002 design chọn **X11/XCB-only, fail-closed**. Sau consume, runner dùng
`xwininfo -root -tree` để lấy candidate top-level windows, rồi `xprop -id`
đọc `_NET_WM_PID`, `WM_CLASS`, `_NET_WM_NAME`/`WM_NAME`. Candidate chỉ được
chấp nhận nếu PID/start ticks/PGID khớp GUI process do run sở hữu hoặc child
được xác minh của group đó; role/class phải phù hợp Gazebo GUI. Runner đọc riêng
`GZ_PARTITION` của process từ `/proc/<pid>/environ` và đối chiếu partition đã
bind; không dump environment. Window ID, PID identity, class, partition,
timestamps và command output đã lọc được ghi vào evidence. Thiếu `_NET_WM_PID`,
window ambiguity, process mismatch hoặc không thể gắn partition là `FAIL`.

Chỉ sau khi scene query đã xác nhận `b2_training_arena` và đúng một model
`mecanum_b2`, runner dùng PyQt `QScreen.grabWindow(WId)` để capture **cửa sổ cụ thể**,
không toàn màn hình. Screenshot được ghi độc quyền, mode 0600, fsync, kèm kích
thước, UTC/steady timestamps và SHA-256. Kiểm tra nền đen/trắng gần như đồng
nhất, kích thước rỗng hoặc capture lỗi là `FAIL`. Những ngưỡng pixel chỉ loại
ảnh rỗng/chưa render rõ ràng; không chứng minh semantic scene. Codex mở đúng file
đã hash qua `view_image` và kiểm tra trực tiếp world/robot/render. Handoff dùng
mailbox file RUN002 trong evidence root, không dùng stdin, foreground TTY hoặc
giả `OWNER_ACK_SCENE`. Runner tạo request; Codex đọc request, xem ảnh, rồi
atomically xuất result. Runner tiếp tục health/process monitoring trong lúc chờ
result. Kết quả chỉ là verdict do Codex tạo; không mang Owner provenance hoặc
human approval. Nếu tool không trả đúng ảnh cho agent hoặc hash thay đổi giữa
capture và review, verdict là `FAIL`.

X11 window enumeration/capture phụ thuộc desktop X11 đang tồn tại và quyền truy
cập hiện hành. Nếu chỉ có Wayland native mà không có X11 window, nếu screenshot
không ánh xạ duy nhất tới GUI thuộc lượt chạy, hoặc Codex không thể mở ảnh cục bộ,
RUN002 phải dừng/fail theo preflight hoặc sau consume tương ứng; không chuyển
sang screenshot toàn màn hình, Xvfb, `xhost+`, cài thêm công cụ, renderer khác
hoặc GUI giả. Preflight chỉ kiểm tra executable/plugin hash, `DISPLAY`, X socket
và quyền truy cập không khởi tạo GUI; xác minh window/render là runtime check.

### Dependency fingerprints cần pin trong packet RUN002

- PyQt5 5.15.10, `PyQt5.QtGui` origin và hash; Qt platform plugin `libqxcb.so`
  hash và package version của `libqt5gui5t64`.
- `xwininfo` và `xprop` executable hashes cùng `x11-utils` version.
- Codex image-viewer capability/source/tool identity (external capability,
  không giả thành package hệ thống).
- Linux/Python file API và backing filesystem phải hỗ trợ `O_NOFOLLOW`,
  directory descriptors, hard-link no-replace trong cùng filesystem, atomic
  link visibility và `fsync(file/directory)`; fingerprint Python/tool API cùng
  filesystem type/options và quyền evidence root.
- Codex process-session handle, local path access, image-viewer identity và
  writer invocation capability phải được packet ghi như external tool
  fingerprints/capabilities; tool invocation reference optional đúng khi
  platform không cấp stable reference.
- Giữ nguyên tất cả 47 production/install fingerprints của packet RUN001 nếu
  từng file vẫn khớp; thay đổi nào cũng đòi packet mới và giải trình.
- Không fingerprint renderer như “đã load”; chỉ runtime render/capture mới có
  thể chứng minh frame pixels đã xuất hiện. Không đổi OGRE2, Sensors,
  SceneBroadcaster hoặc engine.

## Codex review mailbox

Evidence root cố định cho RUN002:
`/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002`.
Mailbox root:
`/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002/review_mailbox`.
Runner tạo request tại
`review_mailbox/requests/<review_request_id>.json`; Codex chỉ đọc request đó.
Codex tạo result tại
`review_mailbox/results/<review_request_id>.json`; runner chỉ đọc đúng path
được suy ra từ request ID hiện hành. Screenshot là file riêng trong
`screenshots/<review_request_id>-<sha256>.png`. Đây là path schema thiết kế;
không tạo mailbox file nào trong lượt này. JSON blocks bên dưới minh họa schema
bằng placeholder, không phải runtime evidence, screenshot identity hoặc approval.

### Request schema `b22_gui_codex_review_request/v1`

JSON object chính xác, không có key phụ:

```json
{
  "schema_id": "b22_gui_codex_review_request/v1",
  "schema_version": 1,
  "run_id": "B22_GUI_OBSERVATION_RUN002",
  "session_id": "<canonical UUID string>",
  "packet_sha256": "<64 lowercase hex>",
  "review_request_id": "<new canonical UUID string>",
  "screenshot_path": "/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002/screenshots/<review_request_id>-<sha256>.png",
  "screenshot_sha256": "<64 lowercase hex>",
  "window_process_identity": {
    "evidence_sequence": 1,
    "window_id": "<X11 hexadecimal XID>",
    "pid": 1,
    "pgid": 1,
    "process_start_ticks": 1,
    "gz_partition": "<exact run partition>"
  },
  "request_created_utc": "<RFC3339 UTC timestamp>",
  "request_created_steady_ns": 1,
  "review_deadline_steady_ns": 2,
  "result_path": "/home/hazan/mecanum_runtime_evidence/B22_GUI_OBSERVATION_RUN002/review_mailbox/results/<review_request_id>.json"
}
```

Version/evidence sequence/PID/PGID/start ticks/steady values are positive
integers, not booleans. IDs are canonical UUID strings; hashes are 64 lowercase
hex; screenshot/result paths must equal the exact absolute canonical paths
derived from the current RUN002 root and request ID. Window ID, partition and
timestamps are nonempty strings with the declared formats. Deadline is an
absolute runner monotonic timestamp later than request creation. Runner
computes the request SHA-256 over exact published bytes. Window/process values
reference runner evidence already written; they are not provided by Codex.

### Result schema `b22_gui_codex_review_result/v1`

JSON object chính xác, không có key phụ:

```json
{
  "schema_id": "b22_gui_codex_review_result/v1",
  "schema_version": 1,
  "run_id": "B22_GUI_OBSERVATION_RUN002",
  "session_id": "<same canonical UUID string>",
  "packet_sha256": "<same 64 lowercase hex>",
  "review_request_id": "<same canonical UUID string>",
  "request_sha256": "<SHA-256 of exact request bytes>",
  "screenshot_sha256": "<same screenshot SHA-256>",
  "reviewer_kind": "CODEX",
  "verdict": "PASS",
  "reason": "<concise description of the rendered pixels actually inspected>",
  "viewer_interaction_ref": null,
  "viewer_ref_state": "TOOL_NO_STABLE_REFERENCE",
  "result_created_utc": "<RFC3339 UTC timestamp>"
}
```

`verdict` chỉ nhận `PASS|FAIL`; `reason` là UTF-8 text không rỗng, tối đa 512
bytes; `reviewer_kind` phải đúng `CODEX`; viewer reference tối đa 256 ký tự
hoặc null. Nếu image-viewer tool cấp interaction reference ổn định, Codex phải
ghi reference đó và `viewer_ref_state=AVAILABLE`; nếu không cấp, ghi null cùng
`TOOL_NO_STABLE_REFERENCE`. Không có field Owner/token. Runner đối chiếu
run/session/packet/request/request-hash/screenshot-hash với trạng thái runner
đang giữ; result không mang window/PID/partition/capture facts để thay facts
đã bind. Đây là consistency/provenance boundary, không phải xác thực bảo mật.

### Atomic publication, replay và invalidation

Preflight xác minh evidence root mới, canonical, không symlink/alias và không có
dữ liệu cũ. Runner tạo mailbox subdirectories mode 0700; screenshot/request/
result là file mode 0600. Dùng directory descriptor đã giữ, `openat` với
`O_NOFOLLOW` và kiểm tra từng directory component; path escape, symlink,
non-regular file hoặc collision làm fail.

Producer ghi bytes hoàn chỉnh vào temp file mới trong cùng directory bằng
`O_CREAT|O_EXCL|O_NOFOLLOW`, xử lý partial write, `fsync(file)`, rồi publish
atomically bằng hard-link no-replace sang tên đích; sau đó unlink temp link và
`fsync(parent directory)`. Collision hoặc filesystem không hỗ trợ no-replace
publication làm fail; không truncate/overwrite, không ghi trực tiếp, không
fallback. Reader mở tên đích sau publication, kiểm type/mode/size, đọc trong
giới hạn schema, hash exact bytes rồi parse đúng một JSON object hoàn chỉnh.
JSON dang dở, key/type sai, trailing data, path/hash mismatch đều fail.

Request/result là immutable new-file evidence; JSONL vẫn append-only và không
bị sửa. Đọc lặp cùng result bytes là idempotent, không gia hạn deadline hoặc mở
review mới. Bytes thay đổi/duplicate mâu thuẫn là FAIL. Request ID chỉ dùng một
lần; run/session/packet/request/screenshot khác, replay, result cũ hoặc file
ngoài path hiện hành đều bị từ chối. Timeout/cancel làm checkpoint
`INVALIDATED`; result đến muộn có thể được giữ như file evidence mới, nhưng
runner không đọc nó để khôi phục checkpoint hoặc đổi final FAIL. Nếu JSONL đã
đóng, late result vẫn giữ binding trong file riêng và không được diễn giải là
accepted result.

### Producer/consumer và trạng thái

| Producer | Consumer | Giao diện/schema | Deadline | Failure |
|---|---|---|---|---|
| Runner | Codex | Atomic request JSON `b22_gui_codex_review_request/v1` tại `review_mailbox/requests/<id>.json` | Tạo và giao request trong cùng checkpoint ≤60 s | Publish/read/hash/schema lỗi: review FAIL |
| Codex | Runner | Atomic result JSON `b22_gui_codex_review_result/v1` tại `review_mailbox/results/<id>.json` | Cùng absolute steady deadline ≤60 s | Viewer unavailable, ảnh không xem được, result sai/thiếu/late: FAIL |
| Runner health monitor | Runner review state machine | Backend/clock/graph/process/evidence facts đã bind trong run | Liên tục đến review accept hoặc invalidate | GUI crash, inhibit loss, fault, timeout, cancellation hoặc evidence failure lập tức invalidate và cleanup |

State machine: `IDLE → WINDOW_BOUND → SCREENSHOT_PUBLISHED → REQUEST_PUBLISHED
→ REVIEW_PENDING → RESULT_VALIDATED`. Chỉ result `PASS` đúng schema/hash và
được nhận trước deadline chuyển sang `REVIEW_ACCEPTED`; sau đó mới có thể qua
clock-stability gate và observation. `FAIL` chuyển `REVIEW_REJECTED`. Timeout,
cancellation hoặc health failure chuyển trạng thái đang chờ sang
`INVALIDATED → CLEANUP → FINAL_FAIL`. Không có transition từ `INVALIDATED` quay
lại review/observation.

### Managed process handoff và deadline

Runner chạy như managed non-PTY process/session qua Codex process API. API trả
session handle để Codex poll process output/session trong khi gọi `view_image`;
RUN002 không cần Owner-accessible terminal, TTY hoặc stdin. Sau khi request được
atomically publish, runner phát event review-ready có request path/ID. Codex đọc
request và kiểm run/session/packet/request IDs cùng request hash. Codex rehash
screenshot trước khi mở, dùng viewer trên đúng path, rồi rehash lần nữa. Chỉ khi
bytes còn cùng hash Codex mới kết luận review và chạy one-shot managed file-writer
operation để publish result atomic. Codex đợi writer exit và kiểm exit status;
writer không khởi tạo ROS/Gazebo và không tạo participant. Runner vẫn giám sát
health/process trong toàn bộ khoảng chờ. Không dùng stdin cho mailbox.

Checkpoint 60 s bắt đầu ngay trước window enumeration/binding; bao gồm window
binding, capture/persist/hash, request publication, Codex đọc request/mở ảnh/
kiểm ảnh, result publisher, runner validation và kiểm tra publisher exit.
Effective deadline là `min(review_started_steady_ns + 60 s, consume_steady_ns +
240 s)`. Duplicate, tool delay hoặc retry không gia hạn deadline. Active cap
240 s, cleanup cap riêng 60 s và total cap 300 s không đổi. Không bắt đầu
checkpoint khi active budget còn dưới 121 s; dành tối đa 60 s review, 1 s clock
gate và đủ 60 s observation. Round-trip chưa đo; 60 s là budget đã được duyệt,
không phải cam kết thời gian hoàn thành.

Nếu managed process/session handle, local file access, image viewer hoặc
atomic writer không khả dụng, dừng trước consume nếu preflight nhận diện được;
nếu lỗi sau consume, invalidate, cleanup và FAIL. Không dùng Owner command, copy
file, screenshot hoặc token làm fallback. Codex cancellation sau consume cũng
invalidate; GUI close/crash không được suy thành Owner abort.

File-writer operation có session handle riêng do Codex tool runtime quản lý.
Codex lưu process/session identity do tool trả nếu có, đợi exit và kiểm kết quả;
nếu writer còn chạy sát/hết deadline thì cancel/join qua handle đó trong phần
budget còn lại. Không đoán PID hoặc signal ngoài handle. Writer không thuộc
simulator process groups và runner không signal nó như process Gazebo; residue
của writer phải được báo unknown, checkpoint vẫn FAIL.

## Trình tự đề xuất

1. **Preflight (trước consume):** exact Git/packet/tool approval pins, RUN002
   canonical capacity chưa tồn tại, evidence root mới/rỗng, desktop X11 thật,
   Codex managed process handle, local file access, image viewer và atomic writer
   capability sẵn dùng, executable/plugin hashes, install closure, process
   cleanup support và clock. Không ROS/Gazebo discovery trước consume. Không cần
   Owner-accessible TTY. Missing precondition dừng mà không tiêu thụ capacity.
2. **Acquire once:** exclusive atomic creation; ghi packet/commit/source/tool/
   input/install/dependency hashes, process/host identity, session and
   coordinator IDs, partition, steady/UTC timestamps. Không retry sau bước này.
3. **Startup:** đặt environment riêng cho process groups; ghi ownership ngay khi
   launcher trả handle; start RSP, bridge/server theo audited composition và
   một GUI. Giới hạn server readiness 30 s, GUI process startup 30 s. Quan sát
   backend status, exact scene, namespace graph và foreign participant theo
   packet; graph convergence tối đa 30 s. Không play/step/reset/probe/rearm.
4. **Render review checkpoint:** bắt đầu deadline steady 60 s trước window
   enumeration. Bind top-level window duy nhất với GUI PID/PGID, start identity
   và `GZ_PARTITION`; scene query phải trả world/model đúng. Capture riêng window,
   persist/hash và publish request JSON. Codex đọc request, mở đúng screenshot,
   kiểm ảnh và publish result JSON atomic qua mailbox. Runner vẫn giám sát health
   trong lúc chờ; chỉ result PASS đúng binding trước deadline mới được chấp nhận.
   Không có TTY/stdin/Owner token. Timeout/ambiguous render là FAIL.
5. **Clock gate và observation:** cần clock sample thực, cùng giá trị ít nhất
   1 s steady; silence không được xem là stable. Sau gate và automated image
   review, quan sát đủ 60 s. Backend sequence phải tăng, heartbeat gap ≤1 s,
   identity không đổi, paused=true, inhibited=true, fault_flags=0,
   applied_receipt_valid=false; clock được nhận nhưng không tiến. Giữ read-only
   graph/process health check xuyên thời gian. Không kết luận scan/contact/
   physics/motion capability.
6. **Cleanup/finalization:** dừng mọi owned observer/task, đóng contexts thuộc
   runner đúng một lần, cleanup owned groups trong deadline cleanup chung 60 s,
   kiểm PID reuse/residue, finalize temporary directory. Ghi final verdict chỉ
   sau cleanup; sink write/close lỗi làm evidence incomplete, không PASS.

## Budget đề xuất

Giữ hard caps hiện hành: active ≤240 s từ consume, cleanup riêng ≤60 s, tổng
≤300 s. Server readiness 30 s; GUI startup 30 s; graph convergence 30 s; clock
stability 1 s; checkpoint 60 s tính từ trước window enumeration đến khi runner
validate result; observation đủ 60 s sau clock gate và review PASS. Checkpoint
bao gồm binding, capture, request/result I/O, Codex tool round-trip và validation.
15 s là budget đề xuất lịch sử đã được thay bằng checkpoint 60 s theo quyết định
Owner ngày 2026-11-02. Tool round-trip vẫn chưa được đo; budget không bảo đảm
hoàn tất trong mọi môi trường. Các giai đoạn overlap dùng absolute steady deadlines; nếu
active budget không đủ thì fail/cleanup trong giới hạn còn lại.

## PASS/FAIL và abort

`PASS` chỉ khi đúng một server/world/robot/backend/GUI, exact scene query, GUI
window thuộc process/partition đã bind, screenshot thật được Codex xem và xác
nhận rendered scene, ảnh không rỗng/đen, graph không có participant lạ, clock
đạt gate, toàn observation giữ inhibit/pause/zero faults/no receipt/heartbeat,
không có control operation, evidence complete và cleanup không để residue.
Evidence đồng thời ghi `automated_observation_verdict=PASS` và
`owner_visual_review=NOT_PERFORMED`; không tạo Owner ACK và không tự diễn giải
automated review thành xác nhận của Owner.

GUI crash, process exit bất thường, window identity mismatch, stale/foreign
participant, scene mismatch, black/unrendered image, status/clock/heartbeat
failure, missing Codex review, evidence lỗi, timeout hoặc cleanup uncertainty
đều `FAIL`. Codex cancellation trước acquisition dừng không consume; cancellation
sau acquisition cleanup rồi ghi `FAIL`/`CANCELLED_AFTER_CONSUME` theo packet.
Không tự suy cancellation là Owner abort. GUI close không tự mang provenance
Owner và không thay đổi motion permission.

## Test offline và runtime checks

Offline fakes phải bao phủ atomic guard, approval/tool pins, process/window
binding parser, ambiguity/foreign PID/PGID/partition, window capture errors,
empty/black/hash-changing screenshot, Codex-result hash binding, cancellation,
deadline, status/clock/graph monitoring, evidence failure, startup rollback,
cleanup escalation/residue và no-retry. Tests không khởi tạo middleware, GUI
application, Gazebo transport, display capture hoặc runtime process.

Chỉ runtime được cấp quyền riêng mới có thể chứng minh X11 session/window thực,
process-to-window binding, screenshot thực và render pixels, scene identity,
paused/inhibited backend/clock/graph, heartbeat và cleanup. Kết quả không chứng
minh Owner visual review, physical contact, motion, braking, functional safety,
training/soak, HIL hoặc robot readiness.

## Allowlist implementation RUN002 đã được duyệt

Prompt Owner đã duyệt acceptance/design và cấp implementation ngoại tuyến trong
đúng phạm vi này:

1. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/packet.json`
2. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/README.md`
3. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_guard.py`
4. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_sink.py`
5. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_runner.py`
6. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/test_observation_packet.py`
7. `docs/architecture/ACR_ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2.md`
8. `docs/architecture/B22_CODEX_OWNED_GUI_OBSERVATION_RUN002_DESIGN.md`

RUN001 files/evidence remain immutable historical inputs. This design document
is approved for RUN002 offline implementation, but it is not a runtime packet,
runtime approval, or authority to create/consume the real guard.

## Giới hạn và blocker còn lại

1. X11/XCB-only capture phụ thuộc desktop, quyền display và khả năng gắn window
   với đúng process/partition; các điều kiện runtime này chưa được thử.
2. Codex image viewer, managed process handoff và writer capability mới được
   ghi theo tool metadata; round-trip thực tế chưa được chứng minh.
3. Installed fingerprints là static; không chứng minh renderer/engine đã load,
   frame đã render, mailbox ghi được hoặc cleanup runtime thành công.
4. Canonical evidence/approval paths phải được kiểm tra quyền/collision trong
   exact runtime context sau authorization; không đổi root hoặc quyền hệ thống.
5. Checkpoint 60 s đã được Owner duyệt cho implementation; latency chưa đo và
   60 s không phải cam kết hoàn tất. Active/cleanup/total caps vẫn 240/60/300 s.

**Kết luận:** `READY_FOR_OFFLINE_IMPLEMENTATION_AUDIT`; runtime capability và
runtime authorization vẫn chưa có.
