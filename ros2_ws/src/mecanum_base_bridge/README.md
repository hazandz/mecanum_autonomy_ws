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
đồng hồ monotonic và lifecycle identity do `SafetyLifecycle` sở hữu. Engine
không tự cấp epoch, gọi reset/rearm hoặc giữ FIFO command; chỉ cache lệnh mới
nhất. Các state duy nhất là `DISCONNECTED`, `PORT_OPEN`, `CONFIGURING` và
`ACTIVE`.

Một lượt `io_once()` đọc tối đa 256 byte, giữ frame có giới hạn codec, xử lý
timer và phát nhiều nhất một COMMAND. CONFIG dùng timeout 500 ms, tối đa ba
lần gửi với sequence tương quan riêng; sau CONFIG_STATUS được chấp nhận, engine
đợi TELEMETRY đầu tiên khớp boot ID/epoch trong 200 ms. Chỉ TELEMETRY hợp lệ
mới đưa engine sang ACTIVE; status đơn lẻ hoặc telemetry đến trước status
không kích hoạt phiên. COMMAND bắt đầu ở sequence 1, giới hạn 50 Hz, dùng
`cmd_vel` mới nhận sau ACTIVE với freshness nhỏ hơn 100 ms. Lệnh stale/không
hợp lệ làm sạch cache và dừng luồng; engine không tạo lệnh zero.

Lỗi, mismatch hoặc timeout đóng transport, xóa frame/cache/baseline, yêu cầu
owner reset đã coalesce và chờ ít nhất 1 giây trước lần mở lại. Sau reconnect
phải nhận lifecycle identity mới rồi bắt tay lại; UART được mở lại không có
nghĩa MCU đã rearm chuyển động. `mcu_fault_bits` được giữ riêng với
`transport_healthy` do Pi quan sát. API `take_accepted_telemetry()` cùng cờ
`continuity_reset` là seam cho U5.

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
