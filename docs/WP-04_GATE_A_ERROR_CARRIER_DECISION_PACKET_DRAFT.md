# WP-04 Gate A — decision packet: error carrier

**Status:** `DRAFT_FOR_FOCUSED_AUDIT_AND_PROJECT_OWNER_USER_DECISION`
**Base:** `origin/integration/implementation@f9987be4429349ef9110c45cf97a89728a5e4229`
**Implementation-packet source:** `wp-04-gate-a-implementation-authorization-packet-f9987be@8ef93277502b9cc7282a544459ae3aa495b2f049`; path `docs/WP-04_GATE_A_IMPLEMENTATION_AUTHORIZATION_PACKET_DRAFT.md`; SHA-256 `431c993a837a156ea2af2e6cad3e6b6d886caa544fd466f524c6bfe4dd662d11`
**Canonical schema:** `docs/OBSERVATION_GATE_A_STRUCTURAL_SCHEMA.md`; SHA-256 `43537b8f0edafbe809e6f70bda86808f87b12f146ed45509c4bfbacd26956ad3`

Đây là packet trình bày lựa chọn, không chọn thay Project Owner/User. Chưa phương án nào dưới đây được phê duyệt. Packet không sửa implementation packet gốc, không cấp `CODE_AUTHORIZATION`, không xác nhận Gate A đã đạt và không thay đổi WP status/dependency.

## 1. Hai mapping đã được chọn — giữ nguyên

Canonical schema và implementation packet ghi đúng hai failure/status mapping:

| Failure theo schema | Status đã chọn |
|---|---|
| `` `cutoff_time_ns` is not strictly after either barrier `` — cutoff không lớn hơn action barrier hoặc reset barrier | `CUTOFF_BARRIER_ORDER_NON_READY` |
| `` Either supplied contract ID/SHA pair does not exactly match its selected pair `` — contract ID/SHA pair không khớp chính xác pair đã chọn | `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |

Không option nào được đổi tên, giá trị hoặc ý nghĩa hai status này; không tạo canonical status mới.

## 2. Hai API profile để User lựa chọn

### Option A — status trực tiếp trên exception

```python
GateASchemaValidationError.status: str | None
GateASchemaValidationError.failure_kind: str
GateASchemaValidationError.field_name: str | None
```

- Runtime type của `status`: exact built-in `str` cho hai mapped failure, chứa đúng literal status ở §1; exact `None` cho failure không có mapping.
- `failure_kind` là exact built-in `str` từ tập diagnostic-only labels cần được User chốt ở §4; không phải ACR status. `field_name` là exact built-in `str` hoặc `None`.
- Caller bắt `GateASchemaValidationError`, đọc `exc.status`, `exc.failure_kind` và tùy trường hợp `exc.field_name`.
- Bảo vệ mutation: ba property chỉ đọc, không setter; exception khóa các giá trị sau construction và không có public mutator. Gán lại `exc.status` hoặc metadata phải bị từ chối.
- API impact: một exception type với status truy cập trực tiếp; construction errors vẫn có property `status`, nhưng giá trị là `None`.

### Option B — immutable typed detail/result trên exception

```python
GateASchemaValidationError.detail: GateASchemaMappedFailure | GateASchemaConstructionFailure

@dataclass(frozen=True, slots=True, kw_only=True)
class GateASchemaMappedFailure:
    status: str
    failure_kind: str
    field_name: str | None

@dataclass(frozen=True, slots=True, kw_only=True)
class GateASchemaConstructionFailure:
    reason: str
    field_name: str | None
```

- `detail` là exact tagged type union như trên, trả qua read-only `exc.detail`.
- Với mapped failures, `status` là exact built-in `str` chứa một trong hai literal ở §1. Caller đọc `exc.detail.status` sau khi xác định detail là `GateASchemaMappedFailure`.
- Với construction failures, `GateASchemaConstructionFailure` **không có status member**; caller phân biệt bằng exact detail type và đọc `reason`/`field_name`.
- `failure_kind`, `reason` là exact built-in `str` từ các diagnostic-only labels cần User chốt ở §4; `field_name` là exact built-in `str | None`. Các dataclass frozen/slots và property `detail` không setter ngăn caller thay đổi status/detail sau construction.
- API impact: exception không có `.status`; thêm hai public detail types và một bước type-dispatch khi caller đọc lỗi.

Cả hai option giữ nguyên status mapping và fail-closed semantics. Label `failure_kind`/`reason` là phân loại lỗi cục bộ, không phải status mới và không được đưa vào ACR8 vocabulary.

## 3. Construction failures không có mapping

Schema liệt kê: missing/unknown constructor field, wrong exact type, `bool` thay cho `int`, integer âm và string rỗng. Chúng fail tại construction bằng typed `GateASchemaValidationError`; không có ACR8 status mapping.

- Với Option A: cùng exception type; `status is None`; `failure_kind` phân biệt failure; `field_name` chứa tên field khi xác định được, nếu không thì `None`.
- Với Option B: cùng exception type; `detail` là `GateASchemaConstructionFailure`, loại này không có status; `reason` phân biệt failure; `field_name` chứa tên field khi xác định được, nếu không thì `None`.
- Đề xuất dữ liệu tối thiểu: loại lỗi và tên field tùy chọn; không cần giữ raw input value. Việc giữ/thêm dữ liệu khác không được suy diễn từ schema.
- “Syntax” ở đây chỉ là lỗi shape/signature của construction. Không thêm generic syntax validation cho ID/SHA; schema chỉ yêu cầu exact ID/SHA pair match.

## 4. Diagnostic labels cần User quyết định

Để không để lựa chọn ngầm, packet đề xuất tập nhãn sau dưới `PROPOSAL_ONLY`:

| Tình huống | Label đề xuất | Loại |
|---|---|---|
| Cutoff không qua một trong hai barrier | `CUTOFF_BARRIER_ORDER` | `failure_kind`, diagnostic-only; status vẫn là `CUTOFF_BARRIER_ORDER_NON_READY` |
| Exact ID/SHA pair mismatch | `CONTRACT_REFERENCE_MISMATCH` | `failure_kind`, diagnostic-only; status vẫn là `LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY` |
| Thiếu argument | `MISSING_FIELD` | `failure_kind` hoặc `reason`; không có status |
| Argument không biết | `UNKNOWN_FIELD` | `failure_kind` hoặc `reason`; không có status |
| Kiểu không đúng | `WRONG_TYPE` | `failure_kind` hoặc `reason`; không có status |
| `bool` truyền vào field integer | `BOOL_AS_INT` | `failure_kind` hoặc `reason`; không có status |
| Integer âm | `NEGATIVE_VALUE` | `failure_kind` hoặc `reason`; không có status |
| String rỗng | `EMPTY_STRING` | `failure_kind` hoặc `reason`; không có status |

Các labels trên chưa được User chấp thuận. Nếu chọn Option B, hai label đầu dùng trong `GateASchemaMappedFailure.failure_kind`; các label construction dùng trong `GateASchemaConstructionFailure.reason`. Nếu chọn Option A, dùng labels tương ứng trong `failure_kind`.

## 5. Tác động đến packet gốc và tests

- Hai mapped failures tiếp tục phải được test với đúng status strings ở §1; Option A assert `exc.status`, Option B assert exact detail type rồi `exc.detail.status`.
- Construction failures phải được test là không có ACR8 status: Option A assert `exc.status is None`; Option B assert detail đúng là `GateASchemaConstructionFailure` và type này không có status member.
- Tests phải xác nhận property/detail không thể bị caller mutate, label và `field_name` theo lựa chọn User, và construction errors phân biệt được với hai mapped failures.
- Các positive construction, field/type matrix, immutable dataclass semantics, reference-pair, import-purity và exclusions khác của packet gốc không đổi.
- Lựa chọn Option B làm public API lớn hơn nhưng biểu đạt “mapped” và “no mapping” bằng hai detail types; Option A ít type hơn nhưng status property có union `str | None` và cùng exception class dùng cho cả hai nhóm.

## 6. Decision questions

Project Owner/User vui lòng trả lời cụ thể:

1. Chọn **Option A** hay **Option B** cho mapped status carrier?
2. Chọn tập diagnostic labels tại §4 nguyên trạng, hay cung cấp danh sách thay thế chính xác? Xác nhận các labels không phải canonical status.
3. Xác nhận `field_name` là `str | None`, và `None` khi không thể quy lỗi về một field đơn lẻ?
4. Có chấp thuận không lưu raw input values trong error object không?

```text
WP-04: BLOCKED_BY_CONTRACT
GATE_A: NOT_PASSED
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_APPROVED: NOT_APPROVED
```
