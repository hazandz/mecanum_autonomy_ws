# PID-0 motor identification lab

Firmware thử nghiệm độc lập, thử nghiệm vòng hở. Không có closed-loop PID. Mỗi lệnh chỉ chạy một bánh, giới hạn duty firmware 400 permille (40%), thời hạn tối đa 120 s; E-stop vật lý và giám sát tại chỗ vẫn cần thiết. Không chạy khi robot có thể lao khỏi giá đỡ. USART6 CSV dump chỉ được gọi sau khi motor đã disable.

Workflow:

1. flash experiment firmware
2. open ST-Link debugger
3. inspect g_pid0
4. select wheel
5. select direction
6. configure max duty
7. clear log
8. RUN_SWEEP
9. wait COMPLETE
10. verify motor disabled
11. DUMP_UART
12. save CSV
13. run pid0_analyze.py

Trong STM32CubeIDE Expressions/Watch, chọn `g_pid0.selected_wheel`: FL=0, FR=1, RL=2, RR=3; `g_pid0.direction`: FORWARD=1, REVERSE=2. Mặc định sweep là 100..400 bước 50 permille, settle=400 ms, measure=800 ms, zero gap=400 ms. `sweep_max_permille` là giới hạn của sweep; firmware từ chối giá trị trên 400. Đặt `g_pid0.request=PID0_REQUEST_CLEAR_LOG` (4), rồi `PID0_REQUEST_RUN_SWEEP` (2). Không có test tự khởi động sau boot.

Để dừng khẩn cấp bằng debugger, đặt `g_pid0.request=PID0_REQUEST_ABORT` (3). ABORT được xử lý ưu tiên ở lần gọi task kế tiếp; E-stop vật lý vẫn là phương tiện dừng tức thời. Sau `COMPLETE`, kiểm tra `MCU_MOTOR_ENABLE` LOW trước `DUMP_UART` (5). Lưu toàn bộ UART CSV vào file rồi chạy:

```bash
python3 pid0_analyze.py pid0.csv
python3 pid0_analyze.py --self-test
```

Analyzer ước lượng feedforward và có thể in `CONSERVATIVE_PI_SEED`; đây chỉ là gợi ý khởi đầu cho PID-1, không phải gain đã được xác nhận. Kết quả phụ thuộc encoder, nguồn, mặt tải và điều kiện thí nghiệm thực tế.
