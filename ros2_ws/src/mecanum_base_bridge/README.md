# mecanum_base_bridge

The development package remains at version `0.3.0`; the U2 transport changes
below are unreleased. Release versioning will be reconciled during U7. The
package contains three distinct pieces:

- The UART v1 codec (`uart_v1_codec.py`) encodes and validates byte frames
  against the contract and golden vectors.
- The existing `sim_eval` source provides offline-only wheel/IMU ingress
  components and its launch entry point; this does not imply hardware or
  production runtime eligibility.
- `SerialTransport` is the U2 offline implementation of bounded raw-byte
  serial I/O. It owns one explicitly supplied port and does not implement
  protocol framing, session validation, ROS endpoints, or command state.

`SerialTransport(port, serial_factory=None, monotonic=time.monotonic)` does not
open a device during import or construction. `open()` applies 115200/8N1,
disables software and hardware flow control, uses nonblocking reads,
`write_timeout=0.020`, and requires exclusive access. A reconnect attempt made
before the one-second monotonic backoff expires returns `False`; after the
deadline the caller may call `open()` again.

Each `read()` returns at most 512 raw bytes (`b''` means no bytes available).
Each `write()` sends the exact caller-provided bytes in one call and accepts at
most `MAX_WIRE_FRAME_LENGTH`; short writes and serial errors close the handle
and are reported to the caller without replay.

Offline tests use only fake serial backends and a fake monotonic clock. They
provide no evidence of STM32 behavior or A1 handshake compliance. The U2
evidence level is `OFFLINE_ONLY`: production ROS/session behavior, HIL,
hardware validation, motor enable, and deployment have not been implemented
or authorized by this transport candidate. The physical port name and UART
wiring must be independently verified on the target machine before a future
separately authorized runtime activity.

The normative byte contract and expected vectors remain in
`docs/Pi_STM32_Interface_Contract.md` and
`docs/Pi_STM32_UART_v1_Golden_Vectors.md`. Passing codec or transport tests
does not establish the complete L2 design, runtime approval, HIL, motor safety,
or deployment readiness.

## U4 — phiên giao tiếp thuần Python, chỉ kiểm thử ngoại tuyến

`BridgeSession` nối với `SerialTransport` và codec đã có, nhưng không tạo node,
topic, message hay service ROS. Caller cung cấp cổng tường minh qua transport,
đồng hồ monotonic và lifecycle identity do `SafetyLifecycle` sở hữu. Snapshot
đầu chỉ lập baseline; CONFIG chỉ bắt đầu sau khi owner cấp `reset_epoch` khác
baseline đang chờ. Snapshot phải hợp lệ, mới và có sequence không lùi; trạng
thái motion `NON_READY` vẫn cho phép CONFIG. Cùng epoch đổi `ready` hoặc
`runtime_generation` không hoàn tất reset; generation chỉ xóa command cache.
Engine không tự cấp epoch, gọi reset/rearm hoặc giữ FIFO command; chỉ cache
lệnh mới nhất. Các state duy nhất là `DISCONNECTED`, `PORT_OPEN`,
`CONFIGURING` và `ACTIVE`.

Một lượt `io_once()` dùng cùng đồng hồ monotonic được inject, đọc tối đa 256
byte, giữ frame có giới hạn codec và phát nhiều nhất một COMMAND. Deadline được
kiểm trước khi đọc, sau khi read trả về và trước khi dispatch; đúng tại hạn đã
hết nên RX đến muộn không thể gia hạn phiên. Trước accepted CONFIG_STATUS,
CONFIG dùng timeout 500 ms, tối đa ba lần gửi với sequence tăng xuyên
reconnect; status của attempt hết hạn không được nhận. Sau accepted status đầu
tiên, retry CONFIG dừng và engine đợi TELEMETRY đầu tiên khớp boot ID/epoch tối
đa 200 ms; status trùng không gia hạn hạn chờ.
CONFIG_REJECTED kết thúc handshake đó. Chỉ TELEMETRY đã kiểm đủ session,
fault mask, E-stop byte, ACK, sequence và MCU time mới được xuất hoặc kích
ACTIVE. Status đơn lẻ hoặc telemetry đến trước status không kích hoạt phiên.
COMMAND bắt đầu ở sequence 1, giới hạn 50 Hz, dùng
`cmd_vel` mới nhận sau ACTIVE với timestamp số hữu hạn trong cùng miền
monotonic và freshness nhỏ hơn 100 ms. Timestamp sai kiểu, NaN hoặc vô cực làm
sạch cache; lệnh stale/không hợp lệ dừng luồng và engine không tạo lệnh zero.

Lỗi session hoặc timeout đóng transport, xóa frame/cache/baseline, yêu cầu
owner reset đã coalesce và chờ ít nhất 1 giây trước lần mở lại. Owner reset
được xác nhận trong backoff được giữ qua lần mở lại, không yêu cầu reset lần
hai. CRC/malformed/oversize và telemetry sai làm cờ `continuity_reset` được
giữ đến khi U5 lấy; frame lỗi không gia hạn telemetry timeout và không xóa
high-water guard trong cùng session. Sau reconnect phải nhận epoch mới rồi
bắt tay lại; UART được mở lại không có nghĩa MCU đã rearm chuyển động.
`mcu_fault_bits` chấp nhận đúng các bit contract 1, 2, 256, 512, 1024, 2048,
4096; bit policy/IMU/reserved bị loại. Pi-observed loss vẫn tách khỏi MCU
report. API `take_accepted_telemetry()` cùng cờ `continuity_reset` là seam
cho U5.

`hardware_config.py` đọc duy nhất hardware manifest, từ chối YAML có key trùng,
tag/anchor/alias/merge hoặc giá trị ngoài JSON, rồi tính SHA-256 theo domain
separator và RFC8785 JCS. Header C và JSON Pi được sinh cùng một lần từ cùng
mapping. Manifest DRAFT vẫn có thể xác nhận cấu hình giao tiếp; giá trị hình
học/sign TBD và `approval.yaml` không được chuyển thành quyền motor. Cần
`PyYAML>=6,<7` và `rfc8785==0.1.4` trong extra `hardware-config`.

Bằng chứng U4 chỉ là `OFFLINE_ONLY`: test liên thông dùng peer C native và
TELEMETRY synthetic chỉ trong test. Chưa có `bridge_node`, ROS endpoint,
TelemetryTask/producer thật, HIL, xác minh cổng vật lý hoặc quyền bật motor.
Phiên bản package vẫn `0.3.0`; mục U4 tiếp tục nằm dưới `Unreleased`.

## U5 — telemetry encoder, wheel odometry và Heartbeat

U5 nối encoder TIM2/TIM5 (32 bit), TIM1/TIM4 (16 bit), bộ mở rộng signed cumulative `int64` lấy mẫu trong callback TIM10 1 ms, và `TelemetryTask` 50 Hz. Task so sánh revision session trước/sau snapshot, chỉ enqueue sau CONFIG accepted và mọi input hợp lệ. CommunicationTask vẫn là chủ sở hữu duy nhất UART TX; status CONFIG phải đứng trước telemetry trong FIFO. Ticks MCU là raw cumulative, không tính delta/velocity/FK trên STM32. Đây là code offline, chưa xác nhận scheduling, missed wraps hoặc timing trên phần cứng.

Manifest chứa geometry Owner-confirmed: diameter 0.097 m, radius 0.0485 m, wheelbase 0.216 m, track 0.190 m và 937.2 tick/vòng; K=0.203 m. Counts/channel và gear ratio vẫn TBD. Dấu encoder vẫn TBD nên node từ chối khởi tạo wheel odometry và không dùng dấu mặc định. Manifest generator dùng cùng RFC8785 hash cho Pi/STM32; approval.yaml không tham gia digest. Chưa có GPIO/polarity E-stop phụ được xác nhận: `safety_io_read_estop_aux()` trả invalid, vì vậy firmware không phát telemetry production với E-stop giả.

Pi dùng session U4 và codec hiện có, giữ tối đa 8 accepted reports; overflow xóa baseline. FK chỉ dùng hai snapshot hợp lệ liền kề cùng boot/epoch, dấu được áp dụng một lần, tính delta tick integer trước float, rồi tích phân SE(2). MCU time tạo dt vận tốc; ROS receive stamp dùng cho header. Gaps giữ pose và xóa baseline; không phát delta/zero tổng hợp. Covariance là giá trị kỹ thuật ban đầu, chưa calibration. Output là `/wheel/odometry_raw` với frame `odom`/`base_link`; node không phát TF, không sửa EKF/bringup và không tự chạy trong Sim-Eval.

`mecanum_uart_bridge` yêu cầu `serial_device` và đường dẫn `hardware_manifest` tường minh, `use_sim_time=false`, dùng SingleThreadedExecutor, lifecycle QoS Reliable/Volatile, lifecycle freshness 0.6 s (publisher hiện có chạy 5 Hz), IO timer 5 ms và Heartbeat 10 Hz. Reset gọi service hiện có async/coalesced; không gọi rearm. Heartbeat dùng `SOURCE_MCU`; Pi-observed loss không thêm MCU fault bit, còn MCU fault chỉ được sao chép từ telemetry đã xác thực và còn fresh. Endpoint Heartbeat mặc định `/mcu/heartbeat` chỉ là endpoint component; consumer chưa được bringup tích hợp.

Unit/host tests có thể dùng ticks, lifecycle và E-stop synthetic có nhãn; đó không phải ROS runtime hay hardware evidence. E-stop mapping, encoder signs, U6 physical UART/HIL và U7 clean production consolidation/audit/integration vẫn còn. Motor permission luôn false; chưa có Gate 3/4, deploy_real hoặc robot validation.

Build package/interface ngoại tuyến (không chạy node): `colcon --log-base /tmp/wp07-u5-roslog build --base-paths ros2_ws/src --build-base /tmp/wp07-u5-rosbuild --install-base /tmp/wp07-u5-rosinstall --packages-up-to mecanum_base_bridge --symlink-install`. Chạy Python suite cần venv U4 cùng ROS Jazzy Python paths đã cài; CTest/native và ARM build commands U4 vẫn dùng cùng CMake modes, đổi output directory thành `/tmp/wp07-u5-host` và `/tmp/wp07-u5-arm`. ROS package build không phải ROS runtime evidence.
