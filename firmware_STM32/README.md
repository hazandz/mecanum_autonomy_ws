# Firmware STM32F411

## UART runtime U3 (offline candidate)

`communication.c` vẫn là codec stateless UART v1. `communication_runtime.c`
là lớp USART6/FreeRTOS dùng codec đó: ISR chỉ chép chunk RX, chụp HAL tick,
latch lỗi và đánh thức task; `CommunicationTask` (tên RTOS `UARTComm`) sở hữu
parser, validation transport và mọi lời gọi UART TX. Task chạy ưu tiên ban đầu
24, stack 512 words; đây là ngân sách khởi đầu, chưa phải phép đo stack hoặc
thời gian trên phần cứng. Ở U3, task semantic và producer telemetry chưa có;
U4 thêm `ControlSafetyTask` với ưu tiên cao hơn.

HAL nhận tối đa 128 byte mỗi lần. RX có bốn chunk pending, mỗi chunk tối đa
128 byte và kèm tick callback: tổng payload chờ tối đa 512 byte, nhưng chỉ
bốn callback chunk, không phải 512 callback một byte. Queue candidate và TX
mỗi queue tám giá trị có kiểu; producer TX không chờ. Parser dùng buffer tối đa
98 byte theo codec, bỏ frame quá cỡ tới delimiter rồi đồng bộ lại. Mỗi lượt
service xử lý nhiều nhất bốn chunk và phát nhiều nhất một frame. `HAL_UART_Transmit`
có timeout 10 ms; task chờ notification hoặc tối đa 5 ms khi idle. Sau khi lấy
TX item và sau serialize, task kiểm tra lại lỗi trước điểm quyết định dispatch.
Candidate cũng được kiểm tra lại sau dequeue và trước handoff. Nếu fault được
chốt trước điểm đó thì item bị bỏ; frame đã cam kết truyền hoặc đang phát
không thể thu hồi.

USART6 dùng PA11/PA12, 115200 8N1, không flow control, `ReceiveToIdle_IT`,
không DMA. IRQ priority 6/subpriority 0. Callback kiểm tra `ErrorCode` trước
khi chép và rearm; mọi lỗi UART, rearm, TX hoặc queue overflow latch transport
unusable. Task hủy RX và bỏ ingress/outbound đang chờ; không tự retry/replay.
Frame TX đã bắt đầu có thể đã phát một phần và không thể thu hồi.
API công khai dành cho task kiểm tra IPSR trước RTOS task API; `service_once`
còn kiểm tra task handle owner. Callback UART chỉ dùng API `FromISR`.

**A1 — NO_PRECONFIG_TELEMETRY:** U3 không tự chấp nhận CONFIG, không gửi
CONFIG_STATUS, TELEMETRY, heartbeat, boot ID, encoder count hay reset epoch.
Khi chưa có semantic owner, startup và CONFIG_REQUEST hợp lệ về cú pháp đều
im lặng. Ở U4, semantic owner phải chấp nhận CONFIG trước CONFIG_STATUS;
TELEMETRY chỉ bắt đầu sau đó và Pi chỉ ACTIVE khi nhận telemetry đầu tiên
khớp boot ID/epoch. U3 plumbing test dùng TX fixtures chỉ kiểm tra copy/FIFO/
wire serialization, không chứng minh handshake hoặc session gating.

Motor permission vẫn false; startup gọi `safety_io_init_safe()` sau peripheral
init và không khởi chạy bench/PID/KIN/encoder diagnostic. `main.c`, MSP, IRQ,
IOC và linker là **development/integration glue** trong file dùng chung nóng;
chưa phải production bytes và cần reconcile ở U7. Không có HIL evidence.

Linker dành riêng sector 7 `0x08060000..0x0807FFFF` cho journal tương lai;
application FLASH giới hạn 384 KiB từ `0x08000000`, RAM giữ 128 KiB. U3 không
cài đặt journal. Boot ID/journal và recovery phục vụ session thuộc U4; U5 giữ
TELEMETRY với encoder cumulative và Pi `/wheel/odometry_raw`; physical UART/HIL
thuộc U6; consolidation production, audit và integration thuộc U7.

## Lộ trình U1–U7

1. U1 — Authority + UART V1 closure.
2. U2 — Raspberry Pi transport.
3. U3 — STM32 UART runtime.
4. U4 — CONFIG + COMMAND session, gồm boot ID/journal và recovery phục vụ session.
5. U5 — TELEMETRY + `/wheel/odometry_raw`, giữ encoder cumulative và Pi wheel odometry.
6. U6 — Physical UART / HIL acceptance.
7. U7 — Clean production consolidation + audit + integration.

## U4 — CONFIG/COMMAND, watchdog, boot identity và recovery ngoại tuyến

`ControlSafetyTask` là owner duy nhất của session, CONFIG/COMMAND acceptance,
epoch, accepted sequence, watchdog và state. Task dùng static allocation,
priority 40, stack 512 words, chu kỳ 5 ms và tối đa tám candidate mỗi lượt.
Đây là budget ban đầu, chưa phải số đo HIL. Task kiểm tra watchdog trước khi
đọc backlog; COMMAND nhận quá 200 ms từ HAL RX tick không thể refresh. Watchdog
SAFE_STOP giữ configured session và accepted sequence; chỉ CONFIG hợp lệ mới
reset lịch sử này. Sequence COMMAND 0 bị từ chối, sequence tăng nghiêm ngặt,
không wrap và không có response frame.

CONFIG_STATUS được enqueue trước khi snapshot cho phép telemetry. U4 không tạo
TelemetryTask hoặc producer TELEMETRY; A1 vẫn bắt buộc status trước mọi
telemetry tương lai. Snapshot chỉ cung cấp state, configured, boot ID, epoch,
accepted sequence, fault bits và telemetry permission cho U5. `motor_enabled`
luôn false; không gọi PID/KIN, PWM, direction hoặc motor enable. Fault bits
chỉ dùng các giá trị đã có theo contract: transport 1, E-stop 2, command
timeout 256, command invalid 512, control loop 1024, motor driver 2048 và
encoder 4096. Không phát policy, IMU hoặc reserved bits khi chưa có owner input.
Watchdog timeout giữ đến CONFIG hợp lệ; invalid-command indication được xóa
bởi COMMAND hợp lệ tiếp theo. Transport invalidation đặt `configured=false`
và `SAFE_STOP`, nhưng giữ accepted-command history cùng boot ID; COMMAND mới
không khôi phục eligibility trước CONFIG hợp lệ. Chỉ boot mới hoặc CONFIG hợp
lệ mới xóa history về sequence 0.

Transport recovery chỉ bắt đầu sau khi ControlSafety đã vào SAFE_STOP và vô
hiệu configured eligibility. CommunicationTask hủy RX, xóa queues/parser và
rearm tối đa mỗi giây; generation counter ngăn HAL_OK xóa ISR fault mới. Thành
công phục hồi UART không khôi phục session hoặc command cũ. Boot ID dùng thuật
toán hẹp trên sector 7 đã reserve: 32768 cell 32-bit, marker 0, dirty/torn cell
được tiêu thụ, hole/full/program/readback lỗi đều fail closed; không erase,
wrap hoặc reclaim. HAL ghi marker bằng bốn lần program byte, kiểm readback và
giữ/khôi phục trạng thái data cache. Không có power-fail hoặc retention proof
trên silicon.

Generator U4 dùng manifest duy nhất, SHA-256 trên
`mecanum_hardware_config_hash/v1\0` + RFC8785 JCS của toàn mapping. CMake ARM
bắt buộc `MECANUM_HARDWARE_MANIFEST`; header và JSON được sinh trong build
directory. `communication_config_valid` chỉ xác nhận UART/profile identity,
không xác nhận hình học/sign TBD hoặc motor approval. `approval.yaml` vẫn là
evidence độc lập và motor permission tiếp tục false.

Test liên thông chạy Pi session engine và C runtime/codec thật trên host. Các
TELEMETRY fixtures được tạo trong test từ snapshot/tick giả định và được gắn
nhãn synthetic; chúng không chứng minh producer MCU hoặc A1 trên phần cứng.
Không có ROS node, launch, TelemetryTask, encoder snapshot runtime,
`/wheel/odometry_raw` hoặc heartbeat publisher trong U4.

## Lệnh kiểm thử offline và ARM link U4

Từ repository root, host test chạy với fake HAL/FreeRTOS, không mở UART hoặc
khởi chạy RTOS thật:

```sh
cmake -S firmware_STM32 -B /tmp/wp07-u4-host -DCMAKE_BUILD_TYPE=Debug \
  -DPython3_EXECUTABLE=/tmp/wp07-u4-venv/bin/python
cmake --build /tmp/wp07-u4-host --parallel 2
ASAN_OPTIONS=detect_leaks=0 ctest --test-dir /tmp/wp07-u4-host --output-on-failure
PYTHONPATH=ros2_ws/src/mecanum_base_bridge \
WP07_U4_INTEROP_PEER=/tmp/wp07-u4-host/test_communication_runtime \
/tmp/wp07-u4-venv/bin/python -m pytest ros2_ws/src/mecanum_base_bridge/test -q
```

ARM build cần `arm-none-eabi-gcc` đã cài cùng HAL, CMSIS và FreeRTOS vendored:

```sh
ARM_GCC=/opt/st/stm32cubeide_2.2.0/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.linux64_1.0.100.202602081740/tools/bin/arm-none-eabi-gcc
cmake -S firmware_STM32 -B /tmp/wp07-u4-arm -DSTM32_ARM_BUILD=ON \
  -DCMAKE_BUILD_TYPE=MinSizeRel \
  -DCMAKE_C_COMPILER="$ARM_GCC" \
  -DCMAKE_ASM_COMPILER="$ARM_GCC" \
  -DPython3_EXECUTABLE=/tmp/wp07-u4-venv/bin/python \
  -DMECANUM_HARDWARE_MANIFEST="$PWD/artifacts/hardware/mecanum_f411_tb6612_ga25_370_rev_a/hardware_manifest.yaml"
cmake --build /tmp/wp07-u4-arm --parallel 4
```

Mỗi build directory giữ executable, map và CTest binary riêng; mọi đường dẫn
đều ngoài source tree. Đây chỉ là
compile/link và kiểm tra tĩnh offline; không chạy ELF, flash, mở serial, chạy
ROS/Gazebo/Nav2, motor hoặc HIL.

## U5 encoder và telemetry

TIM2 FL/TIM5 FR dùng bộ đếm 32 bit; TIM1 RL/TIM4 RR dùng 16 bit. Encoder counting-only bắt đầu sau peripheral init; callback TIM10 lấy mẫu 1 ms và mở rộng modular delta thành cumulative signed `int64`. Exact half-range và tràn `int64` làm snapshot invalid. Giả định displacement giữa hai mẫu nhỏ hơn nửa range; kiểm thử offline không chứng minh lịch scheduler hoặc không bỏ wrap trên hardware. Snapshot dùng critical section ngắn và thời gian HAL tick 64 bit, độ phân giải 1 ms biểu diễn bằng microsecond, không phải microsecond precision.

`TelemetryTask` static, 50 Hz, priority 8 dưới ControlSafetyTask, chỉ enqueue snapshot khi CONFIG/telemetry permission và các input đều hợp lệ. Revision session được so sánh trước/sau khi chụp để loại snapshot qua CONFIG replacement. CommunicationTask vẫn là sole UART TX owner; không có delta/FK hay velocity trên STM32. Sequence không wrap; boot ID giữ nguyên qua CONFIG/recovery.

Manifest geometry Owner-confirmed: diameter 0.097 m, radius 0.0485 m, wheelbase 0.216 m, track 0.190 m, 937.2 tick/vòng, K=0.203 m. Dấu encoder chưa xác nhận. Hardware manifest không có pin/polarity E-stop auxiliary; API `safety_io_read_estop_aux()` trả invalid nên production telemetry không phát giá trị E-stop giả. Test seam dùng synthetic inputs và không phải hardware evidence. Motor output/permission vẫn disabled. U6 phải xác nhận encoder signs, E-stop mapping, UART vật lý, flash retention và timing; U7 phải reconcile development glue trước consolidation.

U5 native gate: `cmake -S firmware_STM32 -B /tmp/wp07-u5-host -DCMAKE_BUILD_TYPE=Debug -DPython3_EXECUTABLE=/tmp/wp07-u4-venv/bin/python`, `cmake --build /tmp/wp07-u5-host --parallel 2` và `ASAN_OPTIONS=detect_leaks=0 ctest --test-dir /tmp/wp07-u5-host --output-on-failure`. ARM gate giữ U4 flags/toolchain/manifest, dùng `/tmp/wp07-u5-arm`; map và ELF nằm trong build directory này. Leak detection được tắt do LeakSanitizer không chạy được trong host ptrace sandbox.
