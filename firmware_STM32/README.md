# Firmware STM32F411

## UART runtime U3 (offline candidate)

`communication.c` vẫn là codec stateless UART v1. `communication_runtime.c`
là lớp USART6/FreeRTOS dùng codec đó: ISR chỉ chép chunk RX, chụp HAL tick,
latch lỗi và đánh thức task; `CommunicationTask` (tên RTOS `UARTComm`) sở hữu
parser, validation transport và mọi lời gọi UART TX. Task chạy ưu tiên ban đầu
24, stack 512 words; đây là ngân sách khởi đầu, chưa phải phép đo stack hoặc
thời gian trên phần cứng. Task semantic `ControlSafetyTask` tương lai phải có
ưu tiên cao hơn. U3 chưa tạo task semantic hoặc producer telemetry.

HAL nhận tối đa 128 byte mỗi lần. RX có bốn chunk pending, mỗi chunk tối đa
128 byte và kèm tick callback: tổng payload chờ tối đa 512 byte, nhưng chỉ
bốn callback chunk, không phải 512 callback một byte. Queue candidate và TX
mỗi queue tám giá trị có kiểu; producer TX không chờ. Parser dùng buffer tối đa
98 byte theo codec, bỏ frame quá cỡ tới delimiter rồi đồng bộ lại. Mỗi lượt
service xử lý nhiều nhất bốn chunk và phát nhiều nhất một frame. `HAL_UART_Transmit`
có timeout 10 ms; task chờ notification hoặc tối đa 5 ms khi idle.

USART6 dùng PA11/PA12, 115200 8N1, không flow control, `ReceiveToIdle_IT`,
không DMA. IRQ priority 6/subpriority 0. Callback kiểm tra `ErrorCode` trước
khi chép và rearm; mọi lỗi UART, rearm, TX hoặc queue overflow latch transport
unusable. Task hủy RX và bỏ ingress/outbound đang chờ; không tự retry/replay.
Frame TX đã bắt đầu có thể đã phát một phần và không thể thu hồi.

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
cài đặt journal. Boot journal, sequence/watchdog semantics và producer/gating
thuộc U4/U5; hardware validation thuộc U6; consolidation/production
reconciliation thuộc U7.

## Kiểm thử offline và ARM link

Từ repository root, host test chạy với fake HAL/FreeRTOS, không mở UART hoặc
khởi chạy RTOS thật:

```sh
cmake -S firmware_STM32 -B /tmp/wp07-u3-host -DCMAKE_BUILD_TYPE=Debug
cmake --build /tmp/wp07-u3-host --parallel 2
ASAN_OPTIONS=detect_leaks=0 ctest --test-dir /tmp/wp07-u3-host --output-on-failure
```

ARM build cần `arm-none-eabi-gcc` đã cài cùng HAL, CMSIS và FreeRTOS vendored:

```sh
ARM_GCC=/opt/st/stm32cubeide_2.2.0/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.linux64_1.0.100.202602081740/tools/bin/arm-none-eabi-gcc
cmake -S firmware_STM32 -B /tmp/wp07-u3-arm2 -DSTM32_ARM_BUILD=ON \
  -DCMAKE_BUILD_TYPE=MinSizeRel \
  -DCMAKE_C_COMPILER="$ARM_GCC" \
  -DCMAKE_ASM_COMPILER="$ARM_GCC"
cmake --build /tmp/wp07-u3-arm2 --parallel 4
```

ELF và map được ghi ngoài source tree ở `/tmp/wp07-u3-build`. Đây chỉ là
compile/link và kiểm tra tĩnh offline; không chạy ELF, flash, mở serial, chạy
ROS/Gazebo/Nav2, motor hoặc HIL.
