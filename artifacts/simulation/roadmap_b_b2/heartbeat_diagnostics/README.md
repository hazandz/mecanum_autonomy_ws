# Công cụ chẩn đoán heartbeat B2.2 (ngoại tuyến)

Phân loại: **L0 — công cụ nội bộ và test độc lập**. Candidate này nhận các
event do caller cung cấp, ghép chúng theo session/backend/config/world/sequence,
và trả về kết luận chẩn đoán hoặc `UNKNOWN`. Nó không thu event, không ghi file,
không kết nối ROS/RMW/Gazebo, không phát runtime verdict và không thay đổi
heartbeat acceptance.

## Bối cảnh và giới hạn

RUN008 đã FAIL tại heartbeat gap lớn hơn một giây sau khi observer ghi nhận
backend status sequence 3. Journal ghi callback receive, thời điểm xử lý và
thời điểm tạo record, nhưng không ghi thời điểm backend bắt đầu/kết thúc publish,
mốc RMW receive/ready đã xác minh, hoặc thời điểm `fsync` hoàn tất. Vì vậy dữ
liệu hiện có chưa phân biệt được publisher ngừng, đường nhận chậm, callback bị
phục vụ muộn hay phần khác của vòng lặp bị trễ. Nguyên nhân RUN008 vẫn
`ROOT_CAUSE_UNRESOLVED`.

Timestamp của mỗi event phải ghi rõ `clock_domain`, `provenance` và sai số đo
(`uncertainty_ns`). Công cụ không ghép mẫu theo thứ tự đến hoặc timestamp gần
nhau; khóa ghép là `(session_id, backend_instance_id, status_sequence)`, đồng
thời phải khớp `config_hash` và `world`. Middleware sequence chỉ là metadata
phụ. Không có trường `publisher_gid` bắt buộc vì binding Python đang pin chưa
được xác minh cho trường đó.

Không trừ timestamp Unix-epoch của RMW khỏi `monotonic_ns`. Mốc
`receive_or_ready` chỉ có giá trị định vị nếu caller xác nhận nguồn và semantics
của đúng implementation; `take` chỉ chứng minh thao tác take tại thời điểm
được đo, không chứng minh thời điểm message đến DDS. `publish_return` chỉ chứng
minh lời gọi publish đã trả về, không chứng minh subscriber đã nhận.

## API

```python
from heartbeat_diagnostics import (
    Binding, BoundedEventBuffer, DiagnosticEvent, EventKind, analyze,
)

binding = Binding(session_id, backend_instance_id, config_hash, world)
events = BoundedEventBuffer(capacity=128)
events.append(DiagnosticEvent(
    kind=EventKind.CALLBACK_ENTRY,
    session_id=session_id,
    backend_instance_id=backend_instance_id,
    status_sequence=status_sequence,
    config_hash=config_hash,
    world=world,
    timestamp_ns=callback_monotonic_ns,
    clock_domain='host-CLOCK_MONOTONIC',
    provenance='observer callback-entry instrumentation v1',
    source_verified=True,
))
result = analyze(events, expected=binding)
```

Các loại event được hỗ trợ: `publish_begin`, `publish_return`,
`receive_or_ready`, `take`, `callback_entry`, `heartbeat_check`. Kết quả có thể
phân loại `backend_stopped`, `receive_path_delayed` hoặc
`callback_service_delayed` chỉ khi đủ bằng chứng, mốc cùng miền đồng hồ và
identity không mơ hồ. Thiếu event, metadata không được xác nhận, sai clock,
identity trùng/sai hoặc buffer overflow đều trả `UNKNOWN`/incomplete. Một kết
quả phân loại không chứng minh acceptance runtime.

`measure_once()` bọc một callable giả hoặc callable do caller sở hữu. Nó gọi
callable đúng một lần, đo monotonic trước/sau kể cả khi callable ném exception,
trả nguyên giá trị hoặc ném lại đúng exception đó. Measurement không tự ghi ra
đĩa và không retry. `heartbeat_expired_reference()` chỉ mô hình hóa phép so
sánh nghiêm ngặt `gap > 1 s` hiện hành để kiểm fixture ngoại tuyến.

## Kiểm tra ngoại tuyến

Chạy từ thư mục này bằng Python đã pin hoặc Python 3 có standard library:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_heartbeat_diagnostics.py
```

Các test dùng timestamp/clock giả xác định; không dùng `sleep()` và không replay
RUN008. Không chạy `ros2 trace`, không tạo trace session và không khởi động
middleware.

## Dữ liệu đo tối thiểu cho công cụ tương lai

- Backend: publish begin/return cùng status sequence và backend/session identity;
  ghi bằng vùng đệm/trace bounded, không ghi đồng bộ vào journal trong đường
  publish.
- RMW: chỉ ghi metadata nếu binding và đúng implementation được xác minh hỗ
  trợ; lưu raw timestamp, sequence, miền đồng hồ và provenance.
- Observer: callback entry, heartbeat-check và thời lượng toàn bộ một lần gọi
  `sink.record()` trong cùng miền monotonic. Không thêm `fsync` vào callback.
- Báo overflow hoặc mất event; không coi sự vắng mặt của event là bằng chứng
  publisher không phát nếu khoảng thu không được chứng minh đầy đủ.

Instrument production/backend, RMW tracing, hoặc nối công cụ này vào runner cần
allowlist và quyết định riêng. Candidate hiện tại không sửa RUN008, không tạo
RUN009, không đổi QoS/lịch publish/ngưỡng một giây và không cấp runtime.
