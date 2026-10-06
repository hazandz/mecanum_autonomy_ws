# Bản nháp hồ sơ approval/change-control theo bundle — QoS revision 5 + ACR revision 7

**Status:** `DRAFT_FOR_INDEPENDENT_AUDIT_AND_USER_DECISION`
**Work package:** `WP-04-QOS-ACR-BUNDLE-APPROVAL-RECORD-DRAFT`
**Mục đích:** Evidence đề xuất để định danh chính xác artifacts và các trường quyết định cho một bundled approval có thể diễn ra sau này.
**Hiệu lực:** Không có. Bản nháp này không phải approval, canonical integration, quyết định implementation eligibility hay code/runtime authorization.

## 1. Provenance của source

Hồ sơ draft này dựa trên source candidate sau:

```text
Repository:       https://github.com/hazandz/mecanum_autonomy_ws.git
Source branch:    wp-04-qos-revision-5-gate-amendment-proposal
Source commit:    5d251d770948656a8d96acff7ccc2e8017d3ccbb
Integration ref:  origin/integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f
```

Source commit là provenance của proposal branch, không phải canonical integration commit. Integration ref xác định evidence baseline đã được xem xét cho draft này; nó không có nghĩa các artifact đề xuất bên dưới đã được tích hợp tại đó.

## 2. Artifacts chính xác được đề xuất cho bundle

| Artifact | Loại tài liệu | Revision đề xuất | Path chính xác | Full-document SHA-256 |
|---|---|---:|---|---|
| QoS artifact | Proposal Receipt Topic QoS Contract | 5 | `docs/architecture/proposals/v3-observation-contracts/RECEIPT_TOPIC_QOS_CONTRACT_REVISION_5_PROPOSAL.md` | `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b` |
| ACR artifact | Proposal amendment §8 V3 Observation Boundary Closure | 7 | `docs/architecture/proposals/v3-observation-contracts/ACR_V3_PRIMITIVE_SCOPE_CLARIFICATION_PROPOSAL.md` | `cb111c84c3b8f7d1393256b4c15f28c5f0bcafa1d2a84dde08e2cb0cd823ce0f` |

Các hash này định danh toàn bộ bytes của từng proposal artifact, không phải transport-manifest hash. Revision và nội dung được đề xuất vẫn là draft; việc liệt kê identity chính xác không đồng nghĩa approval hay canonicalization.

## 3. Transport identity riêng biệt

Transport identity trong QoS artifact:

```text
Transport contract ID:       mecanum.final-issued-receipt-topic-qos/v1
Canonical manifest SHA-256:  a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

Transport-manifest hash chỉ định danh canonical transport manifest. Nó không thay thế hoặc đại diện cho full-document SHA-256 của QoS revision 5 proposal hay ACR revision 7 proposal. Record được đề xuất phải giữ riêng cả ba identity.

## 4. Architecture authority và bối cảnh approval hiện tại

```text
Architecture document: docs/MECANUM_NAV_DRL_Architecture.docx
Architecture SHA-256:  f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

Hồ sơ hiện có ghi nhận QoS revision 4 và ACR revision 6 chỉ là **user-approved follow-on-design bundle** trong approval scope đã ghi nhận, bao gồm sự kiện approval lịch sử ngày `2026-10-03`. Approval đó không làm cho hai tài liệu trở thành canonical repository authority; chúng chưa phải canonical repository authority được tích hợp theo governance workflow. Mô tả này không mở rộng approval scope đã ghi nhận.

QoS revision 5 và ACR revision 7 vẫn là proposal draft. Chúng không trở thành current/canonical authority thông qua record draft này. Cho đến khi có bundled approval và canonical integration mới, ACR revision 6 §8 và QoS revision 4 §10 tiếp tục áp dụng chỉ trong scope follow-on design đã được user phê duyệt và ghi nhận; chúng chưa phải canonical repository authority được tích hợp theo governance.

## 5. Scope decision đề xuất để user quyết định sau này

Bundle scope được đề xuất là phân chia Gate A/Gate B trong ACR revision 7 và QoS revision 5 §10.3:

- **Gate A, primitive-only:** exact approved contract ID/SHA references and structural validation; no `ResolvedConfigV3` creation/binding, config-hash generation, or public-interface/topic implementation.
- **Gate B, connected/profile-resolving:** public-interface version/hash and resolved-config binding remain required, along with the applicable ACR gates and profile-specific evidence.

Cách diễn đạt này hiện chưa có hiệu lực. Nó không sửa ACR revision 6 §8 hoặc QoS revision 4 §10(3) hiện hành; các điều khoản đó tiếp tục áp dụng cho đến khi hoàn tất approval hợp lệ và canonical integration workflow. Nội dung trên chỉ là scope decision được đề xuất, không phải record cho thấy user đã approve.

## 6. Các trường decision và integration — đang chờ

Các trường sau chưa thể biết tại thời điểm soạn draft và phải để `PENDING`:

```text
User decision/result:                PENDING
Ngày bundled approval thực tế:       PENDING
Canonical integration commit cuối:   PENDING
Canonical approval/change-control record path: PENDING_USER_DECISION
Canonical record status before canonical integration: DRAFT_ONLY
```

Không điền ngày approval trước khi decision thực sự xảy ra. Chỉ điền integration commit sau khi canonical integration commit đã được tạo thực tế và SHA đã xác minh. Không suy luận hai trường này từ proposal commit, branch push, review hoặc draft record này.

## 7. Nội dung bắt buộc của canonical record trong tương lai

Nếu bundle được approve và tích hợp sau này, canonical record phải pin các thông tin sau, không thay thế bằng giá trị khác:

1. exact path, loại tài liệu, proposed revision và full-document SHA-256 của cả hai artifact tại §2;
2. transport contract ID và canonical manifest SHA-256 tại §3, được phân biệt rõ với full-document hashes;
3. scope decision Gate A/Gate B chính xác cùng decision/result;
4. ngày thực tế của approval event; và
5. SHA của canonical integration commit cuối, chỉ được thêm sau khi commit đó tồn tại và đã xác minh.

Quy tắc promotion được đề xuất:

```text
Promotion rule: the canonical path must be selected or explicitly approved in
the bundled user decision. Promotion must occur through a separate authorized
governance work package. This draft path has no canonical or operative effect.
```

Không tự chọn canonical path thay cho user. Path của record canonical chỉ được xác định bằng decision bundle; việc promotion cần một governance work package riêng được authorize. Path của draft này không có hiệu lực canonical hoặc operative.

Bất kỳ record nào trong tương lai cũng phải giữ riêng user decision, approval event và canonical integration. Draft này không chứa SHA-256 của chính nó và không được làm thành self-referential.

## 8. Governance boundary và trạng thái

PEP-001 revision `0.2.0` tiếp tục yêu cầu `WP-04-POLICY-CORE-P0` phụ thuộc WP-03. Draft này không đóng WP-03, không đổi dependency, không đổi status của work package nào và không thiết lập implementation eligibility. Bundle approval trong tương lai tự nó cũng không đáp ứng điều kiện đóng WP-03 hoặc authorize implementation packet.

```text
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

File này chỉ là proposal evidence. Nó không khẳng định QoS revision 5 / ACR revision 7 bundle đã được approve hoặc canonical-integrate, và không cấp code, build, test, runtime, HIL hay hardware authorization.
