# Thiết kế đề xuất: Codex-owned GUI observation RUN002

**Trạng thái:** `READY_FOR_OWNER_REVIEW` — thiết kế, chưa phải runtime packet,
implementation hoặc runtime approval.

**Phạm vi:** B2.2 L2, một lượt GUI quan sát paused/inhibited sau khi Owner duyệt
pins và cấp quyền runtime riêng. RUN001 đã consume và `FAIL` tại commit
`09a3304e217628a11c44f0b1380ad1a7d5ae533a`; evidence lịch sử của nó không được
sửa hay tái sử dụng. RUN002 phải có packet, hash, audit và capacity-one guard
riêng.

## Thay đổi acceptance đang chờ duyệt

ACR L2 §8 hiện hành yêu cầu Owner trực tiếp xác nhận scene và cung cấp screenshot
sau một runtime được cấp quyền riêng. Đề xuất này thay thao tác đó bằng kiểm tra
ảnh do Codex vận hành, với hai trường tách biệt:

```json
{
  "automated_observation_verdict": "PASS | FAIL",
  "owner_visual_review": "NOT_PERFORMED"
}
```

Trường thứ nhất ghi nhận kết quả kiểm tra máy/agent trên scene query và ảnh thật
của cửa sổ thuộc lượt chạy. Trường thứ hai ngăn diễn giải kết quả thành xác nhận
của con người. Thay đổi acceptance chưa được kích hoạt; ACR có mục đề xuất riêng
ở trạng thái `PENDING_OWNER_APPROVAL`. Owner vẫn duyệt exact packet trước run và
xem xét evidence sau run.

## Tiến trình, identity và ownership

Một Codex-controlled foreground runner sẽ sở hữu đúng một run descriptor, một
session UUID, một coordinator-ingress UUID, một `GZ_PARTITION`, `ROS_DOMAIN_ID`
đã duyệt, thư mục tạm và process groups của RSP, bridge, server, GUI cùng các
observer phụ. Tất cả identity được ghi vào acquisition/evidence trước khi tạo
participant. Composition giữ nguyên: một RSP, một bridge, một Gazebo server
server-only với `--headless-rendering`, một GUI-only cùng partition, backend và
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
đã hash qua `view_image` và kiểm tra trực tiếp world/robot/render. Agent gửi về
runner một kết quả **Codex-generated** gắn cùng hash ảnh; event đó không mang tên
Owner ACK và không được coi là human approval. Nếu tool không trả đúng ảnh cho
agent hoặc hash thay đổi giữa capture và review, verdict là `FAIL`.

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
- Giữ nguyên tất cả 47 production/install fingerprints của packet RUN001 nếu
  từng file vẫn khớp; thay đổi nào cũng đòi packet mới và giải trình.
- Không fingerprint renderer như “đã load”; chỉ runtime render/capture mới có
  thể chứng minh frame pixels đã xuất hiện. Không đổi OGRE2, Sensors,
  SceneBroadcaster hoặc engine.

## Trình tự đề xuất

1. **Preflight (trước consume):** exact Git/packet/tool approval pins, RUN002
   canonical capacity chưa tồn tại, evidence root mới/rỗng, desktop X11 thật,
   Codex foreground session có thể giữ runner, executable/plugin hashes,
   install closure, process cleanup support và clock. Không ROS/Gazebo discovery
   trước consume. Missing precondition dừng mà không tiêu thụ capacity.
2. **Acquire once:** exclusive atomic creation; ghi packet/commit/source/tool/
   input/install/dependency hashes, process/host identity, session and
   coordinator IDs, partition, steady/UTC timestamps. Không retry sau bước này.
3. **Startup:** đặt environment riêng cho process groups; ghi ownership ngay khi
   launcher trả handle; start RSP, bridge/server theo audited composition và
   một GUI. Giới hạn server readiness 30 s, GUI process startup 30 s. Quan sát
   backend status, exact scene, namespace graph và foreign participant theo
   packet; graph convergence tối đa 30 s. Không play/step/reset/probe/rearm.
4. **Render verification:** bind top-level window duy nhất với GUI PID/PGID,
   start identity và `GZ_PARTITION`; scene query phải trả world/model đúng.
   Capture riêng window, validate pixels, hash/fsync. Trong tối đa 15 s tổng cho
   window binding, capture và Codex image inspection, giao đúng screenshot qua
   image viewer. Runner chờ một structured machine-result gắn screenshot hash;
   không chờ hoặc tổng hợp Owner token. Timeout/ambiguous render là FAIL.
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
stability 1 s; Codex window/capture/image inspection tối đa 15 s; observation
đủ 60 s sau clock gate và automated review. Các giai đoạn song song/overlap phải
được tính theo deadline steady tuyệt đối, không cộng thêm ngân sách hoặc gia hạn
cleanup fallback. Nếu tổng active work không thể hoàn tất trước 240 s, dừng và
cleanup trong ngân sách còn lại.

## PASS/FAIL và abort

`PASS` chỉ khi đúng một server/world/robot/backend/GUI, exact scene query, GUI
window thuộc process/partition đã bind, screenshot thật được Codex xem và xác
nhận rendered scene, ảnh không rỗng/đen, graph không có participant lạ, clock
đạt gate, toàn observation giữ inhibit/pause/zero faults/no receipt/heartbeat,
không có control operation, evidence complete và cleanup không để residue.

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

## Allowlist dự kiến cho implementation RUN002

Chỉ sau khi Owner duyệt acceptance change và prompt implementation riêng:

1. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/packet.json`
2. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/README.md`
3. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_guard.py`
4. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_sink.py`
5. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/observation_runner.py`
6. `artifacts/simulation/roadmap_b_b2/gui_observation_run002/tools/test_observation_packet.py`
7. `docs/architecture/ACR_ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2.md`

RUN001 files/evidence remain immutable historical inputs. This design file is
not a packet and does not authorize creation of RUN002 guard, approval, or
runtime implementation.

## Điểm cần Owner quyết định / blocker

1. Chấp thuận hoặc bác bỏ thay đổi L2 từ direct Owner scene acknowledgment sang
   `automated_observation_verdict` với `owner_visual_review: NOT_PERFORMED`.
2. Chấp thuận X11/XCB-only capture profile; static inventory cho thấy API và
   executable cần thiết có mặt, nhưng không xác minh active desktop session,
   Qt window metadata, capture permission hoặc Codex image-viewer handoff ở
   runtime.
3. Implementation phải pin fingerprints mới và chứng minh tích hợp pause/review
   checkpoint mà không giả Owner input; thiết kế này chưa tạo packet hoặc code.

**Kết luận:** `READY_FOR_OWNER_REVIEW` cho quyết định acceptance/design. Runtime
khả năng cụ thể vẫn phụ thuộc desktop/X11 và image handoff thực tế; nếu các điều
kiện đó thiếu ở lượt được cấp quyền, phải fail closed.
