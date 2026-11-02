# Roadmap B — master plan and status

**Ngày đối chiếu:** 2026-11-02
**Exact source commit:** `6f510b3048bd45030dd75418a820a684920c5a37`
**Phân loại:** L1 documentation/context reconciliation; work-branch governance candidate.

## Mục đích và giới hạn

Tài liệu này khôi phục chuỗi Roadmap B1–B8 để duy trì ngữ cảnh, báo cáo tiến độ và chỉ tới các nguồn có thẩm quyền. Đây là bản tổng hợp trên work branch; không thay thế Architecture, ACR hoặc bản canonical trên `integration/implementation`.

Tài liệu không cấp quyền runtime, training, integration, HIL, Gate acceptance hoặc thay đổi milestone. Không suy audit PASS, implementation completion hay runtime result từ ancestry. Các trạng thái dưới đây là snapshot đối chiếu ngày 2026-11-02; thay đổi sau ngày đó cần evidence và authority mới.

## Nguồn và provenance

- **Architecture:** `docs/MECANUM_NAV_DRL_Architecture.docx`, SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`, là authority kiến trúc tối cao.
- **Amendment hiện hành:** [ACR Roadmap B](../architecture/ACR_ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2.md), Decision ID `ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2`. Chỉ amendment đã được Owner duyệt, đúng phạm vi và có hiệu lực theo ACR mới thay đổi contract.
- **Nguồn quản trị:** [Project Execution Plan](PROJECT_EXECUTION_PLAN.md), [Canonical Source Registry](CANONICAL_SOURCE_REGISTRY.md) và [Project Progress Ledger](PROJECT_PROGRESS_LEDGER.md) ghi routing, pins và evidence; không vượt Architecture/ACR.
- **RUN002:** [Codex-owned GUI observation design](../architecture/B22_CODEX_OWNED_GUI_OBSERVATION_RUN002_DESIGN.md) là thiết kế đang chờ quyết định Owner theo ACR §9; không phải packet, implementation hoặc runtime authorization.
- **Nguồn lịch sử:** `Markdown đã dán (1)(20261026-185834).md`, do workspace đọc và cung cấp nội dung cấu trúc E, I, J, K–L, O–P trong chỉ dẫn Owner hiện hành. Nguồn mang trạng thái `DESIGN_REMEDIATED_PENDING_INDEPENDENT_REAUDIT`; Codex không trực tiếp truy cập Library và không tạo hash cho bản lịch sử. Đây là nguồn khôi phục cấu trúc kế hoạch, không phải toàn bộ thiết kế đã được duyệt.
- **Owner status input:** nội dung phục hồi và trạng thái ở bảng dưới được cung cấp trong chỉ dẫn Owner ngày 2026-11-02; không trình bày chúng như kết quả kiểm toán độc lập.

## Chuỗi phụ thuộc

**B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8**

Đây là Roadmap B, không phải roadmap bảy bước Candidate A/B/C, Roadmap Step-7 cũ hoặc các work package WP-01–WP-08.

## Các bước, điều kiện hoàn thành và status snapshot

| Bước | Ý nghĩa và phạm vi | Đầu ra/điều kiện hoàn thành | Trạng thái theo evidence hiện có ngày 2026-11-02 | Nguồn/status provenance |
|---|---|---|---|---|
| **B1 — Task/reward/termination và lõi giao dịch RL** | Đóng task, reward, termination, reset, receipt/cutoff và commit transition nhất quán. Pure/offline core; tự nó không bao gồm Gazebo, Gym hoặc PPO. | Core canonical được kiểm thử; audit và approval đúng phạm vi. | **CLOSED theo Owner.** ACR/Plan ghi nhận scope và quyết định tương ứng; không mở lại nếu chưa có mâu thuẫn mới, cụ thể và có căn cứ. Không suy audit PASS từ ancestry. | Owner status input; ACR §§2–3; Plan mục Roadmap B/B1 và B2.1. |
| **B2 — Nền mô phỏng cho RL** | Đường reset/action/receipt/sensor/contact/Safety/lifecycle để Gym sử dụng. | Substrate acceptance, fault coverage và bounded soak theo amendment; không Safety bypass hoặc invalid committed transition. | **OPEN.** B2.1 được Owner ghi nhận là source/offline integrated; B2.2 có source/offline delivery, RUN001 đã consume và FAIL, RUN002 mới ở mức thiết kế; B2.3 chưa triển khai theo thông tin hiện có. Không có B2/Gate PASS. | Owner status input; ACR §§2.2, 5, 8–9; Plan/Registry/Ledger B2.1–B2.2; RUN002 design. |
| **B3 — Gymnasium và PPO smoke** | Reset/step, terminated/truncated, observation cuối, truyền lỗi, dependency compatibility và checkpoint save/load. | Gym correctness và các điều kiện Gate 1 liên quan trước optimizer update đầu tiên; sau đó smoke functional và dependency lock. | **NOT_STARTED** theo nguồn quản trị đã đọc; chưa có evidence bàn giao mới. | ACR §2.2; Plan B1/B2 routing; Owner status input. |
| **B4 — Khóa đầu vào thí nghiệm** | Train/validation/final-test, scenario families, sampling, seed lineage, bounded noise, reset/geometry/path suitability và ngân sách dựa trên phép đo. | Split/input artifacts được kiểm tra và freeze; common B5 budget được duyệt trước full-training seed đầu tiên. | Chưa có bằng chứng bắt đầu trong tập nguồn đã đọc; không xác nhận toàn repository không có implementation. | Cấu trúc lịch sử do workspace cung cấp và Owner status input; đối chiếu 2026-11-02. |
| **B5 — Huấn luyện PPO với ba seed** | Ba seed độc lập theo cùng protocol/ngân sách; validation chọn một checkpoint cho từng seed. | Ba selected checkpoints A/B/C; training, validation, recovery và budget accounting đầy đủ. | Chưa có bằng chứng bắt đầu trong tập nguồn đã đọc; không xác nhận toàn repository không có implementation. | Cấu trúc lịch sử do workspace cung cấp và Owner status input; đối chiếu 2026-11-02. |
| **B6 — Kiểm chứng Hybrid với cả ba mô hình** | Nav2 global planner, LocalReference, policy inference, Safety/command ownership; cancel/preempt/reset/path expiry/lifecycle. | Cả ba model tương thích và dùng đúng data/command path; giữ nguyên ba model hashes sang B7/B8. | Chưa có bằng chứng bắt đầu trong tập nguồn đã đọc; không xác nhận toàn repository không có implementation. | Cấu trúc lịch sử do workspace cung cấp và Owner status input; đối chiếu 2026-11-02. |
| **B7 — Hạ tầng benchmark và khóa kế hoạch đánh giá** | Sequential runner, recorder/attempt records, metrics/statistics, golden traces, pairing/missing-data và development/validation dry run. | Phép đo được kiểm; preregistration và acceptance được duyệt trước khi mở final-test. | Chưa có bằng chứng bắt đầu trong tập nguồn đã đọc; không xác nhận toàn repository không có implementation. | Cấu trúc lịch sử do workspace cung cấp và Owner status input; đối chiếu 2026-11-02. |
| **B8 — Benchmark chính thức theo cặp kịch bản** | NAV2_BASELINE so với Hybrid A/B/C trên các case và điều kiện chung đã khóa. | Planned attempts hợp lệ và đầy đủ; raw data, metrics, uncertainty, limitations, report, independent audit và Owner acceptance. | Chưa có bằng chứng bắt đầu trong tập nguồn đã đọc; không xác nhận toàn repository không có implementation. | Cấu trúc lịch sử do workspace cung cấp và Owner status input; đối chiếu 2026-11-02. |

## Phân rã B2

- **B2.1 — config/schema/compiler/interface:** Owner ghi nhận source/offline đã tích hợp. Đây không phải runtime PASS.
- **B2.2 — simulation substrate:** backend, world/model, sensor/contact, trusted ports/reset adapters, launch/bridge/GUI, asset/scenario/provenance. RUN001 đã consume và FAIL; không retry hoặc sửa evidence. RUN002 mới là thiết kế, chưa có implementation/runtime approval mới.
- **B2.3 — integration:** coordinator, Safety, FinalTwistPublisher, lifecycle/observation0 và kiểm chứng tích hợp/bounded soak. Theo thông tin hiện có, chưa triển khai.

GUI mở được không đóng B2. Không nối tắt Safety để robot chuyển động sớm. Gym API, PPO update và full training thuộc bước sau.

## Lịch sử và amendment hiện hành

1. Cấu trúc B1–B8 được khôi phục từ các mục lịch sử E, I, J, K–L, O–P do workspace đọc và chỉ dẫn Owner hiện hành; Codex không trực tiếp đọc nguồn Library.
2. ACR §2.2 chốt Roadmap B simulation coverage/fault checks cộng **30 successful transactional resets và 1.000 issued commands**. Không khôi phục 500 reset/10.000 lệnh thành yêu cầu hiện hành cho phạm vi này. Đủ số đếm không tự chứng minh Gate PASS.
3. ACR §§2.3–2.5 chốt collection/rollout boundary. `COLLECTION_CUTOFF` không phải task terminal hoặc truncation và không tạo fake transition.
4. ACR §2.6 chốt NavFn+DWB cho benchmark Roadmap B. Hybrid dùng Nav2 Planner+PPO, không DWB/FollowPath song song.
5. ACR §§3, 5 và các authorization sau đó thay các phần task/reset/receipt/reference/contact/interface từng còn proposal trong phạm vi được duyệt.
6. Proposed candidate scope ở mục O của nguồn lịch sử không phải allowlist thực thi.
7. `RESOLVED` trong bảng remediation lịch sử không đồng nghĩa independent audit PASS.

## Thông số còn là đề xuất

Các mục sau giữ nhãn đề xuất; tài liệu này không phê duyệt chúng:

- Số scenario families, realizations, cases và episodes.
- Seed values 11/29/47 và PPO initial pins.
- Hai rollout/update cho smoke.
- Step/wall-time budget và checkpoint/validation cadence.
- Ví dụ selection-rule.
- Lookahead/replan/expiry chưa được freeze.
- Gate 2 quality thresholds và aggregation procedure chưa được duyệt.

Ngân sách B5 chung phải dựa trên measurements B3/B4 và được duyệt trước full-training seed đầu tiên. Không giảm ngân sách của seed sau theo kết quả seed trước.

## Ba seed và thống kê

- B5 chọn một checkpoint của A, một của B và một của C bằng validation rule được freeze trước training. Không chọn “best seed” rồi bỏ hai seed còn lại.
- B6 kiểm cả ba; giữ nguyên model hashes sang B8.
- Không dùng final-test để chọn checkpoint hoặc distribution; không âm thầm bật DWB fallback.
- Policy outcome kém không tự là source integration bug.
- B7 khóa phép đo, pairing, denominators, missing-data và kế hoạch đánh giá trước unseal.
- Mỗi paired case giữ baseline và ba model outcomes; giữ grouping case/family/model.
- Không coi nhiều episode của ba model là nhiều policy độc lập; không nhân một baseline outcome thành ba baseline sample độc lập.
- Giữ mọi attempt; không retry để thay outcome xấu. Recovery chỉ theo protocol/budget đã khóa.

Phân biệt `EXPERIMENT_VALID` / `EXPERIMENT_INVALID`, `EXPERIMENT_COMPLETE` / `EXPERIMENT_INCOMPLETE`, và policy quality / Gate 2. Roadmap B có thể hoàn tất nghiên cứu với Hybrid kém hơn DWB nếu thí nghiệm hợp lệ, đủ kế hoạch, audit và Owner chấp nhận. Không gọi invalid/incomplete data là kết quả âm hợp lệ.

## Giới hạn mô phỏng và robot thật

Roadmap B gốc là mô phỏng/RL, tích hợp Hybrid và nghiên cứu đánh giá. Nó không tự chứng minh sim-to-real, HIL, Gate 3/4 hoặc `REAL_READY`. Mục tiêu toàn dự án vẫn benchmark DRL+Nav2 so với DWB trên robot thật. Physical measurements/UART/PID/HIL/real deployment/real benchmark cần kế hoạch và evidence riêng; tài liệu này không gán chúng vào B8 hoặc tạo B9.

## RUN002 — điểm đang làm

- RUN001 đã consume và FAIL; không retry, reset guard hoặc sửa evidence.
- RUN002 hiện là thiết kế; chưa có implementation/runtime approval mới.
- D1: UUID session và nonzero `uint64` coordinator được truyền nguyên vẹn.
- D2: request/result mailbox; không Owner TTY/token/file phản hồi giữa lượt.
- Acceptance Codex kiểm ảnh vẫn `PENDING_OWNER_APPROVAL`.
- Nếu acceptance mới được duyệt, `owner_visual_review` ghi `NOT_PERFORMED`; không giả Owner ACK.
- Thiết kế hiện ghi checkpoint 15 giây. Workspace đề xuất 60 giây, giữ active/cleanup/total 240/60/300 giây; đề xuất 60 giây chưa được duyệt.
- Inventory Codex báo 47/47 installed fingerprints khớp; đây là báo cáo local, không phải runtime evidence.
- Inventory báo repo và `/tmp` rw, canonical evidence/approval paths ro; desktop Wayland có `DISPLAY` và socket X11 nhưng capture chưa thử.
- Không suy tool catalog thành operational capability hoặc coi cancel/join là thành công đã kiểm chứng.
- Không tự đổi root, renderer, desktop hoặc quyền hệ thống.

Bước kế tiếp: Owner chốt quyết định RUN002 còn mở; workspace phát hành prompt implementation cụ thể; Codex thực thi; workspace audit exact commit; chốt packet/pins/guard; Owner duyệt exact runtime; Codex chạy một lượt; workspace audit evidence. Trình tự này không phải runtime authorization hiện tại.

## Vai trò và báo cáo tiến độ

- Workspace thiết kế, chuẩn bị gói/prompt và audit độc lập.
- Codex kiểm kê/thực thi/check/Git/runtime đúng quyền.
- Owner phê duyệt quyết định và exact run; không phải chạy terminal hoặc tạo file điều phối giữa lượt.
- Báo cáo tiến độ giữ đủ B1–B8, mô tả, điều kiện hoàn thành, trạng thái, căn cứ và ngày; kèm tóm tắt và giải thích dễ hiểu.

## Nguồn tham chiếu

- [Architecture DOCX](../MECANUM_NAV_DRL_Architecture.docx)
- [Roadmap B ACR](../architecture/ACR_ROADMAP_B_TRAINING_SEMANTICS_AND_B1_SCOPE_L2.md)
- [RUN002 design](../architecture/B22_CODEX_OWNED_GUI_OBSERVATION_RUN002_DESIGN.md)
- [Project Execution Plan](PROJECT_EXECUTION_PLAN.md)
- [Canonical Source Registry](CANONICAL_SOURCE_REGISTRY.md)
- [Project Progress Ledger](PROJECT_PROGRESS_LEDGER.md)
