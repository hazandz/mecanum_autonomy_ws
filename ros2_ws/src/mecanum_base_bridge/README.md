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

## MANUAL_SLAM review candidate

`mecanum_nav_bringup/launch/manual_slam.launch.py` is a separate direct Joy
route: `joy_node -> slam_manual_joy -> /cmd_vel -> mecanum_uart_bridge`. It does
not launch `SafetySupervisor`, `FinalTwistPublisher`, or SLAM Toolbox. SLAM
Toolbox belongs in a second terminal. The launch includes the existing
`safety_lifecycle` identity/reset component and lifecycle manager, but never
calls rearm; the state remains non-ready until an operator action, so the
bridge/session remains fail-closed for motion.

The mapper requires `/manual_slam/enable`, then a fresh neutral Joy sample.
Invalid/stale Joy, Joy timeout, detected extra `/cmd_vel` publishers, and
`/manual_slam/disarm` publish zero and disarm the mapper. `/manual_slam/disarm`
is software-only and is not an E-stop. `joy_node` autorepeats unchanged input
at 20 Hz; mapper Joy timeout is 0.25 s, measured with a steady clock for receive
age and ROS time for the message stamp. The mapper checks discovered `/cmd_vel`
publishers and disarms when it sees another publisher; ROS graph discovery does
not guarantee exclusivity.

Use one identical explicit `hardware_manifest` path for mapper and bridge, and
use that same file as firmware CMake's `MECANUM_HARDWARE_MANIFEST` when building
the matching image. The manifest/hash must be regenerated and checked against
STM32 `CONFIG_STATUS`; a successful source build alone does not prove the
installed MCU hash. Firmware now represents the PID4 experiment per wheel and
direction in order FL/FR/RL/RR. Kp is `0.084 permille/(tick/s)`, Ki is
`1.05 permille/tick`, the original PID4 experiment target limit was
`1400 tick/s`, integral limit is `±80 permille`, and output cap is
`400 permille`. The current MANUAL_SLAM offline target candidate accepts up to
`2000 tick/s`; PID4 gains/feedforward are not experimentally validated above
1400 tick/s. Feedforward is
`u0 + kv × |target_cps|`, with `u0` in
permille and `kv` in permille per count/second:

| Wheel | Forward u0 | Forward kv | Reverse u0 | Reverse kv |
|---|---:|---:|---:|---:|
| FL | 40.330665 | 0.217819026 | 36.253577 | 0.225076821 |
| FR | 32.415574 | 0.231811480 | 34.233335 | 0.226312521 |
| RL | 61.698998 | 0.212679580 | 54.760209 | 0.223609266 |
| RR | 37.521999 | 0.223981830 | 32.707200 | 0.229221684 |

These values are sourced from PID4 commit
`231010db7de8a3f49f49a715da4339e129a48755` and evidence record
`476d114697f5f3fb034dddd48c82d9297c3888b7`. Runtime converts permille through
the TIM3 auto-reload value using `(ARR+1) × rounded_permille / 1000`; the
checked-in TIM3 ARR is 65535, so 400 permille maps to CCR 26214. The profile is
enabled in this MANUAL_SLAM firmware candidate, but output remains off at boot
and until the existing session accepts a matching CONFIG and a nonzero command.
The ARM build must pass the same explicit bench manifest used by mapper and
bridge; generated firmware constants include its geometry, encoder signs and
hash. Canonical manifests with unresolved encoder signs make the MANUAL_SLAM
profile invalid and prevent session configuration.

The runtime preserves PID4's 20 ms control period, one-second full-scale ramp
(a slew limit equal to the larger current/requested target magnitude per
second; an equal-magnitude direction reversal therefore takes about two
seconds through zero), maximum 100 ms
control dt, wrong-direction 100 tick/s for 200 ms guard, stall guard after
400 ms grace plus 500 ms at >=120 permille and <100 tick/s, and synchronization
guard for comparable four-wheel targets after its 500 ms grace plus 500 ms
above 300 tick/s spread. The 150 tick/s sync warning is internal and not
published. The PID4 one-shot 10 s arm delay, fixed 5 s autorun, 6 s test-run
timeout and 1 s stop hold are omitted because MANUAL_SLAM uses continuous
session commands; zero, watchdog and session faults stop immediately. A runtime
guard fault latches the MCU session into SAFE_STOP until a new accepted CONFIG.
The evidence source
worktree was dirty and has no exact ELF/flash image pinned, so this remains an
offline implementation candidate, not evidence of motor behavior.

MANUAL_SLAM selects five target fractions `40%, 55%, 70%, 85%, 100%`, or
`800, 1100, 1400, 1700, 2000 tick/s`; startup selects 40%. L1/R1 change the
tier once per rising edge and clamp at the endpoints. Android Gamepad physical
button indices are not inferred from an Xbox layout: configure
`joy_button_a_index`, `joy_button_b_index`, `joy_button_x_index`,
`joy_button_y_index`, `joy_button_l1_index`, and `joy_button_r1_index` in
`config/slam_manual_joy.yaml` from captured `/joy` arrays. `-1` leaves a button
unconfigured and ignored; analog movement remains available. Unit tests use an
intentionally shuffled synthetic index map, not hardware evidence.

At 2000 tick/s the unchanged feedforward values request 476/496/487/485
permille forward and 486/487/502/491 permille reverse (FL/FR/RL/RR). The
unchanged PID output cap clamps these requests to 400 permille, so this target
candidate may saturate before tracking the selected wheel rate. This is a
source-based calculation, not a measured speed or diagnosis of the reported
motor noise; it is not operating validation.

Example form (driver launch names and measurement values are supplied by the
Owner for the exact Pi installation; this is not an executed command):

```bash
ros2 launch mecanum_nav_bringup manual_slam.launch.py \\
  serial_device:=/dev/ttyAMA0 \\
  hardware_manifest:=/absolute/path/hardware_manifest_slam_manual_bench.yaml \\
  ekf_params_file:=/absolute/path/owner_ekf_real.yaml \\
  lidar_launch_file:=/absolute/path/owner_ydlidar.launch.py \\
  lidar_port:=/dev/serial/by-id/OWNER_LIDAR_DEVICE \\
  imu_launch_file:=/absolute/path/owner_bno055.launch.py \\
  lidar_x:=MEASURED lidar_y:=MEASURED lidar_z:=MEASURED \\
  lidar_roll:=MEASURED lidar_pitch:=MEASURED lidar_yaw:=MEASURED \\
  imu_x:=MEASURED imu_y:=MEASURED imu_z:=MEASURED \\
  imu_roll:=MEASURED imu_pitch:=MEASURED imu_yaw:=MEASURED
```

The supplied driver launch files must map LiDAR output to `lidar_frame` and
IMU output to `imu_link`, use `use_sim_time=false`, and accept the configurable
port/frame and I2C bus/address launch argument names. Defaults for I2C are bus
1 and decimal address 41 (`0x29`); verify the exact Pi hardware. EKF config,
driver versions/parameters, sensor transforms, and ROS graph are not validated
in this repository. The MANUAL_SLAM bench manifest records all four encoder
signs as `OWNER_REPORTED` from the Owner's manual forward rotation observation.
The raw `/home/hazan/slam-config-telemetry-20261111-175136.json` and the
separate FR reconnect result file were not present on this laptop; the FR
filename is not guessed. The manifest records provenance without promoting
this to raw measured evidence. Provide the original files and paths/hashes for
independent review. The canonical manifest is unchanged by this sign update.
Verify the Owner's main power switch disconnects power to both motor drivers;
that behavior has not been tested or assumed. The firmware
reports auxiliary E-stop `UNKNOWN`; it is not converted to inactive. No
physical E-stop is present, no Joy stop button is assigned, and this candidate
does not validate output gating, stopping distance, or the Owner's main switch
on hardware. The profile requires independent audit before any hardware trial.

Unit/host tests có thể dùng ticks, lifecycle và E-stop synthetic có nhãn; đó không phải ROS runtime hay hardware evidence. E-stop mapping, encoder signs, U6 physical UART/HIL và U7 clean production consolidation/audit/integration vẫn còn. Motor permission luôn false; chưa có Gate 3/4, deploy_real hoặc robot validation.

### U6 corrective — E-stop auxiliary UNKNOWN (offline)

UART v1 telemetry giữ payload 65 byte, protocol `0x0001` và offset hiện hữu.
Byte `estop_aux_active` nhận `0=INACTIVE`, `1=ACTIVE`, `2=UNKNOWN`; giá trị
khác bị từ chối. Firmware đọc validity riêng với value; auxiliary chưa có
mapping tạo UNKNOWN, không tự đặt `FAULT_ESTOP_ACTIVE`, còn telemetry chỉ được
enqueue sau CONFIG và các gate snapshot/encoder/session/motor-disabled hiện
hữu. Pi giữ session ACTIVE và telemetry fresh khi session hợp lệ; Heartbeat báo
unhealthy, `Heartbeat.estop_aux_state=ESTOP_AUX_UNKNOWN`, detail
`E-stop auxiliary UNKNOWN`, và giữ fault MCU khác.
UNKNOWN chỉ là diagnostic; không thêm gate COMMAND hoặc motor permission.
Receiver cũ chỉ hiểu 0/1 sẽ từ chối 2, nên hai đầu phải được cập nhật đồng bộ.
Đây là evidence offline; không chứng minh UART vật lý, E-stop độc lập, HIL,
motor output hay runtime.

Build package/interface ngoại tuyến (không chạy node): `colcon --log-base /tmp/wp07-u5-roslog build --base-paths ros2_ws/src --build-base /tmp/wp07-u5-rosbuild --install-base /tmp/wp07-u5-rosinstall --packages-up-to mecanum_base_bridge --symlink-install`. Chạy Python suite cần venv U4 cùng ROS Jazzy Python paths đã cài; CTest/native và ARM build commands U4 vẫn dùng cùng CMake modes, đổi output directory thành `/tmp/wp07-u5-host` và `/tmp/wp07-u5-arm`. ROS package build không phải ROS runtime evidence.
