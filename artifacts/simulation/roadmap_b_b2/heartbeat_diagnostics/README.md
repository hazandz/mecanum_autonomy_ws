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
    PublishCoverage,
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

Các loại event được hỗ trợ gồm `publish_begin`, `publish_return`,
`status_received`, `status_ready`, `take`, `callback_entry`,
`status_validation` và `heartbeat_check`. `status_received` là mốc nhận middleware
có provenance rõ; `status_ready` là mốc mẫu sẵn sàng được callback xử lý.
Event cũ `receive_or_ready` vẫn được nhận diện để tương thích dữ liệu nhưng có
nghĩa mơ hồ nên không được dùng để phân loại.
`status_validation` ghi rõ mẫu callback đã được chấp nhận hay bị từ chối;
callback entry tự nó không chứng minh heartbeat được cập nhật.
Kết quả có thể phân loại `no_publish_attempt_observed`,
`receive_path_delayed` hoặc `callback_service_delayed` chỉ khi đủ bằng chứng,
mốc cùng miền đồng hồ và identity không mơ hồ. Thiếu event, metadata không
được xác nhận, sai clock, identity trùng/sai hoặc buffer overflow đều trả
`UNKNOWN`/incomplete. Một kết quả phân loại không chứng minh acceptance runtime.

`no_publish_attempt_observed` chỉ được trả khi `PublishCoverage` xác nhận nguồn
đã thu liên tục, không mất event, cùng binding/clock domain, bắt đầu không muộn
hơn mẫu heartbeat hợp lệ sớm nhất và kết thúc không sớm hơn lần kiểm lỗi muộn
nhất. Nguồn phải xác nhận không có publish đang in-flight tại đầu cửa sổ.
Kết luận chỉ nói rằng không quan sát thấy lời gọi `publish_begin` trong cửa sổ
được bao phủ; nó không chứng minh backend đã chết. Cửa sổ thiếu, có event rơi,
còn publish in-flight hoặc có bằng chứng mẫu mâu thuẫn thì kết quả là `UNKNOWN`.

Mốc thời gian được xét theo khoảng `timestamp_ns ± uncertainty_ns`. Hạn
heartbeat có một cận sớm nhất và một cận muộn nhất từ khoảng thời gian mẫu cuối
cộng ngưỡng một giây. Chỉ coi event đúng hạn khi toàn bộ khoảng của nó không
muộn hơn hạn sớm nhất; chỉ coi event trễ khi toàn bộ khoảng của nó muộn hơn hạn
muộn nhất. Nếu khoảng sai số chạm hoặc bắc qua vùng không phân định được thì
nguyên nhân là `UNKNOWN`, dù riêng phép so sánh heartbeat tại thời điểm kiểm
đã xác định gap vượt một giây.

Các callback sau baseline được xét theo `status_sequence`, nhưng không được bỏ
qua mẫu có thể ảnh hưởng lần kiểm lỗi cho đến khi kết quả validation và thứ tự
callback → validation → check đã rõ. Validation bị từ chối sau check hoặc có
khoảng sai số chồng lấn callback không giải quyết được mẫu tại thời điểm check;
kết quả là `UNKNOWN` và nêu sequence. Một mẫu được chấp nhận trước check mâu
thuẫn với giả định baseline cũ. Mẫu phát sau lần kiểm không giải thích ngược
lần kiểm trước.

Trước khi phân loại, công cụ cũng kiểm thứ tự nhân quả trên từng mẫu bằng các
khoảng sai số: nếu có `publish_begin`, nó phải được chứng minh xảy ra trước
`status_received` hoặc `status_ready`; ready phải đi trước callback; callback
phải đi trước validation. `publish_return` không bắt buộc phải đi trước ready
vì lời gọi publish có thể chưa trả về khi subscriber đã sẵn sàng nhận. `take`
không thay thế mốc nhận. Chỉ `status_received` có nghĩa xác định mới được dùng
để kết luận đường nhận bị trễ; chỉ `status_ready` có thể hỗ trợ phân loại
callback bị phục vụ muộn. Ready hoặc `take` không chứng minh gói đến muộn.
Nếu thứ tự cần thiết chồng lấn sai số hoặc mâu thuẫn với các mốc danh nghĩa,
nguyên nhân là `UNKNOWN`.

Publish event của sequence trước lần kiểm mà chưa có receive, callback hoặc
validation là mẫu chưa được giải thích, không phải bằng chứng mẫu đã bị loại.
Công cụ trả `UNKNOWN` và nêu sequence đó. Mẫu sau chỉ được dùng khi mẫu trước
đã được xác nhận bị loại bằng callback và validation đúng identity, đúng thứ
tự, hoàn tất trước lần kiểm.

Quy tắc này áp dụng cho toàn bộ event có thể ảnh hưởng cùng sequence tại thời
điểm check: publish begin/return, middleware receive, ready, take, callback và
validation. Một mốc ngoài miền đồng hồ của check hoặc thiếu provenance không
được dùng để bỏ qua sequence. Nếu có publish/receive/ready/take/callback có thể
đã xảy ra trước check nhưng việc từ chối mẫu chỉ được ghi sau check, sequence
vẫn chưa được giải quyết tại check và nguyên nhân là `UNKNOWN`.

`take` có trường `take_succeeded` tường minh. Chỉ take thành công với clock,
identity và provenance đã xác minh mới có thể tham gia thứ tự nhân quả; nó phải
được chứng minh xảy ra sau ready (nếu có) và trước callback. Take không thay
thế `status_received` hoặc `status_ready`, và không chứng minh thời điểm gói
đến. Take xảy ra sau callback, hoặc khoảng sai số không xác lập được thứ tự,
không hỗ trợ phân loại dương.

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
  không có lần gọi publish nếu khoảng thu không bao phủ đầy đủ mẫu cuối đến lần
  kiểm lỗi, hoặc chưa loại trừ publish đang trên đường.

Instrument production/backend, RMW tracing, hoặc nối công cụ này vào runner cần
allowlist và quyết định riêng. Candidate hiện tại không sửa RUN008, không tạo
RUN009, không đổi QoS/lịch publish/ngưỡng một giây và không cấp runtime.
