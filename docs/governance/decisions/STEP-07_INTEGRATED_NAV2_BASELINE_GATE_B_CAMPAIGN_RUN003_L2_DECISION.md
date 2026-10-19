# Step-7 NAV2_BASELINE Run003 — sửa chuẩn hóa đường dẫn Fuel cache

Phân loại: `L2_STEP07_FUEL_CACHE_PATH_NORMALIZATION_AND_RUN003_CAPACITY_ONE_CORRECTION`.

## Cơ sở và phạm vi

Candidate dựa trên `6d730bd54d7f99429ee4832a3f6f96beffae020f`; integration base vẫn là `f7f98c683d59cf4c62e462da9f37d4ffb2455c80`. SHA-256 Architecture: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.

Run002 là historical immutable failure với terminal outcome `STEP07_NAV2_BASELINE_RUN002_PREACQUIRE_PREFLIGHT_FAILED_NO_GUARD_CONSUMED` và root cause `FUEL_CACHE_PATH_CASE_NORMALIZATION_MISMATCH`. Run002 đã chứng minh cơ chế ghi bằng chứng pre-acquire; không retry và không sửa lại source pin, guard, record hay evidence lịch sử Run002.

## Quyết định cache bất biến

SDF tiếp tục chứa chính xác URI case-sensitive `https://fuel.gazebosim.org/1.0/OpenRobotics/models/Depot` và `https://fuel.gazebosim.org/1.0/MovAi/models/Tugbot`. Runner Run003 chỉ ánh xạ lần lượt tới `fuel.gazebosim.org/openrobotics/models/depot/<positive-integer-version>` và `fuel.gazebosim.org/movai/models/tugbot/<positive-integer-version>` bên dưới `$HOME/.gz/fuel`.

Runner kiểm tra parent/version/file theo các path chính xác, không dùng `rglob`, không nhận cache root tùy biến, từ chối uppercase owner/model path và symlink thoát cache root, và yêu cầu đúng một version trực tiếp có `model.config` cùng `model.sdf`. Candidate không tải, provision, hoặc thay asset. Depot host asset chưa được xác minh là sẵn có; đây vẫn là precondition riêng cho runtime tương lai.

## Run003 capacity-one seed và pre-acquire

Run003 có ID `STEP07_NAV2_BASELINE_RUN_003`, partition `mecanum_step7_nav2_run003_f7f98c6`, integration base đã nêu, capacity 1, acquisition count 0, state `PENDING_EXACT_INTEGRATION_AND_USER_AUTHORIZATION`, `runtime_authorization=NOT_GRANTED`, `retry_permitted=false`. Trước acquire, build/host preflight failure được ghi thành canonical `run_record.json`, `preflight_failure.json`, `artifact_manifest.json` và `SHA256SUMS.txt`, không lock, không guard mutation, không runtime process và không teardown. Nếu preflight đạt, campaign one-shot và teardown composite-trước-bootstrap/finalization-sau-teardown của Run002 được kế thừa.

## Evidence ceiling và trạng thái

Đây là source/offline-test candidate; không phải runtime evidence. `GATE_B=NOT_STARTED`; `RUNTIME_APPROVED=NOT_APPROVED`; Step 7 chưa được xác nhận PASS. Run001, Run002 và WP06 historical artifacts giữ nguyên.

Chi tiết pin/scope nằm trong `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_L2_EVIDENCE.json` và `docs/governance/evidence/STEP-07_INTEGRATED_NAV2_BASELINE_GATE_B_CAMPAIGN_RUN003_GUARD_MANIFEST.json`.

## Đối soát test pin lịch sử Run002 và scope hiện hành

Owner phê duyệt mở rộng đúng một path, `artifacts/simulation/step07_nav2_baseline_campaign/tools/test_step07_run002_runtime_guard.py`, để sửa kiểm thử historical source-pin. Kiểm thử đọc Git blob Run002 tại commit `6d730bd54d7f99429ee4832a3f6f96beffae020f`, xác minh SHA-256 và kích thước byte, đồng thời fail-closed khi thiếu commit/blob hoặc có mismatch; không dùng bytes checkout hiện hành làm fallback. Đây là test reconciliation L1, không đổi Run002 guard, runner, evidence, outcome hoặc semantics.

Scope trực tiếp hiện hành của Run003 là đúng 14 path: 13 path Run003 ban đầu cộng test lịch sử được Owner duyệt. Test lịch sử bổ sung không được thêm thành source pin runtime Run003; Run003 tiếp tục giữ 16 source pins hiện có. Run002 không retry; Run003 vẫn PENDING, capacity 1, acquisition count 0, `runtime_authorization=NOT_GRANTED`; không runtime được chạy, `GATE_B=NOT_STARTED`, `RUNTIME_APPROVED=NOT_APPROVED`.
