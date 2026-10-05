# Đề xuất bundled contract amendment — phạm vi QoS §10(3) cho Gate A/Gate B

**Status:** `QOS_SECTION_10_3_AMENDMENT: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL`
**Work package:** `WP-04-QOS-SECTION-10-3-SCOPE-AMENDMENT-PROPOSAL`
**Source branch/commit:** `wp-04-qos-r4-e2-bundle-traceability-proposal@dc1d54ab13dec0e1a96744da6b8f1463f78e3d3b`
**Expected source parent:** `91743f4ac4672b9eb9db7179c44e136a0327be92`
**Integration reference:** `origin/integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f`
**Companion proposal:** `ACR_V3_PRIMITIVE_SCOPE_CLARIFICATION_PROPOSAL.md`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Mục đích, authority và giới hạn

Đây là đề xuất **formal bundled contract amendment/change-control** để independent audit và user decision về phạm vi QoS revision 4 §10(3) đối với Gate A primitive-only và Gate B connected/profile-resolving. Đây không phải erratum traceability-only, không sửa nội dung QoS revision 4 hiện hành, không phải canonical authority và không có hiệu lực trước khi được audit, user approval và canonical integration theo workflow.

Đề xuất đi cùng ACR revision 7. ACR revision 7 hiện vẫn là draft; QoS revision 4 hiện hành, ID/hash, canonical manifest, public protocol, QoS profile và transport semantics không đổi bởi tài liệu này. Approval workflow phải quyết định disposition/versioning/hash của mọi sửa đổi companion QoS; proposal này không chọn QoS revision tiếp theo, không tạo manifest/hash mới và không ghi nhận approval event trước ngày thực tế.

R4-E2 trong companion ACR proposal chỉ đề xuất traceability update current operative companion reference tại QoS §10(2). Nó không xử lý §10(3). Phạm vi §10(3) chỉ có thể thay đổi qua đề xuất formal riêng này nếu được phê duyệt bundled; không được gọi thay đổi đó là R4-E2 hoặc traceability-only.

## 2. Wording hiện hành và finding

QoS revision 4 §10 hiện ghi:

> This document is a design authority only after all of the following are approved together:
>
> 1. this Receipt Topic QoS Contract;
> 2. `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision 6, which already incorporates the planar-twist and final-publisher-instance rules and removes duplicated gap ownership; and
> 3. the resulting public-interface version/hash and resolved-config binding.

Điều kiện §10(3) được giữ nguyên văn ở đây:

> the resulting public-interface version/hash and resolved-config binding.

Tài liệu hiện hành không nói rõ điều kiện thứ ba áp dụng cho Gate A, Gate B hay cả hai. Audit `INDEPENDENT_ARCHITECTURE_AUDIT_dc1d54ab.md` kết luận rằng không thể tự miễn §10(3) cho Gate A, cũng như không đủ căn cứ để suy luận rằng structural primitives phải tạo public interface/resolved configuration. Vì vậy phạm vi hiện tại là **undetermined**; wording dưới đây là rule proposal, không phải cách diễn giải có hiệu lực của QoS revision 4.

## 3. Rule và wording §10(3) được đề xuất

### 3.1 Gate A — exact references và structural validation

Đề xuất rằng với một packet Gate A primitive-only, §10(3) được đáp ứng bằng việc packet tham chiếu chính xác các contract ID/SHA đã được duyệt và xác định structural validation tương ứng. Gate A chỉ xem xét type/structural validation; nó không tạo hoặc bind `ResolvedConfigV3`, không tạo config hash, và không triển khai public interface/topic. Do đó Gate A không tạo một “resulting public-interface version/hash and resolved-config binding”.

Các exact references liên quan mà packet phải giữ, không alias/fallback:

```text
S2: mecanum.snapshot-synchronization-temporal/v1
    1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f
Receipt interface: mecanum.final-issued-receipt/v1
    90348664c4563997b93de7f10e278b10d4053fcb96909b6bb85c1319db76c40e
Receipt QoS: mecanum.final-issued-receipt-topic-qos/v1
    a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62
```

Đề xuất này không làm các reference trên thành authority mới; chúng phải tiếp tục đúng theo approval/canonical status hiện hữu.

### 3.2 Gate B — public-interface/hash và resolved-config binding

Với Gate B connected/profile-resolving, điều kiện “the resulting public-interface version/hash and resolved-config binding” tiếp tục là điều kiện bắt buộc trước implementation tương ứng. Phải có version/hash public interface được phê duyệt và binding vào resolved configuration được phê duyệt, cùng với các gate ACR hiện hành khác. Không được rút gọn điều kiện này thành kiểm tra ID/SHA structural của Gate A.

Gate B tiếp tục giữ đủ sáu gate hiện hành trong ACR §8: canonical recording ACR/specification; approval QoS bundle và record; `ObservationInputContractV3` cùng canonical source/compiler/composition validation; receipt message/topic và compatibility; pure-Python ingress seams; independent audit về 81D và process/safety isolation. Profile-specific evidence tiếp tục là yêu cầu riêng; đề xuất này không chọn timing, buffer, freshness, measured-twist hoặc X3 values.

### 3.3 Wording thay thế đề xuất cho QoS §10

> **DRAFT — proposed replacement for QoS Contract §10, to be approved only as part of one audited and user-approved bundle with ACR revision 7. Not effective under the current QoS revision 4.**
>
> This document may serve as design authority only after the applicable gates below are approved together with the companion ACR revision 7. The approval record must retain the historical bundled approval of 2026-10-03 with ACR revision 6 as a separate event; any later approval of ACR revision 7 and this QoS contract must be recorded as a new event on its actual date.
>
> 1. Approve this Receipt Topic QoS Contract under the revision/hash disposition established by the approval workflow.
> 2. Approve the companion `ACR_V3_OBSERVATION_BOUNDARY_CLOSURE` revision 7 in the same bundle.
> 3. **Gate A:** For a primitive-only packet, record the exact approved contract ID/SHA references and the structural validation scope. This gate does not create or bind `ResolvedConfigV3`, create a config hash, or implement a public interface/topic. Under this proposed amendment, the public-interface version/hash and resolved-config binding requirement in item 4 is not a Gate A deliverable or precondition.
> 4. **Gate B:** Before connected/profile-resolving implementation, approve the resulting public-interface version/hash and resolved-config binding, in addition to the other applicable ACR gates.
>
> This section changes no transport QoS, message fields, topic, protocol semantics, canonical QoS manifest, or QoS profile. It does not waive safety, lifecycle, temporal, or Ground Truth isolation requirements; alter the WP-04 dependency on WP-03; close WP-03; or authorize code or runtime.

Wording trên cố ý đề xuất thay đổi phạm vi của §10(3): Gate A không phải tạo/bind interface-version/hash/config-resolution artifact mà nó bị cấm tạo, còn Gate B phải đáp ứng yêu cầu đó. Đây là lựa chọn change-control để audit/user quyết định, không phải kết luận rằng rule đã được chấp thuận.

## 4. Bảng trước/sau và tác động

| Phạm vi | QoS revision 4 hiện hành | Rule được đề xuất | Tác động nếu được duyệt và tích hợp |
|---|---|---|---|
| Gate A primitive-only | §10(3) nêu public-interface version/hash và resolved-config binding, nhưng không phân định Gate A | Exact approved contract ID/SHA và structural validation; không yêu cầu tạo/bind resolved config, config hash hoặc public interface/topic | Có thể xem xét packet primitive-only mà không tạo artifact ngoài scope; không tự cấp code authorization |
| Gate B connected/profile-resolving | Cần public-interface version/hash và resolved-config binding; ACR §8 giữ sáu gate | Giữ nguyên điều kiện §10(3) và tất cả gate ACR hiện hành | Connected/profile-resolving work vẫn bị chặn tới khi đủ bundle, binding và evidence |
| Safety/governance | Các contract/PEP hiện hành có authority | Không miễn safety, lifecycle, temporal, Ground Truth isolation hay WP-03 dependency | WP-03 phải đóng hoặc dependency được xử lý bằng PEP/governance amendment riêng |

Cho đến khi formal amendment được audit, user approved và canonically integrated, **không áp dụng cột “Rule được đề xuất”**. QoS revision 4 §10(3) hiện hành chưa được sửa và Gate A không được coi là đã miễn điều kiện này.

## 5. Điều kiện không thay đổi và dependency

Đề xuất này không thay đổi các điều kiện sau:

- Safety/lifecycle ownership, action/reset barriers, cutoff/time-domain consistency và fail-closed semantics vẫn áp dụng.
- Ground Truth isolation trong policy path vẫn bắt buộc.
- `WP-04-POLICY-CORE-P0` vẫn phụ thuộc WP-03 theo PEP-001 revision `0.2.0`; đề xuất này không sửa PEP, ledger, sequencing hoặc status. Chỉ closure WP-03 hoặc PEP/governance amendment riêng, được audit và duyệt riêng, mới xử lý dependency.
- WP-03 và WP-04 vẫn `BLOCKED_BY_CONTRACT`.
- Không đổi QoS transport profile, message fields, topic, protocol semantics, canonical manifest, contract ID hoặc hash. QoS revision/hash tiếp theo (nếu có) phải được approval workflow xác định; không tự gán tại đây.
- Không có code authorization, implementation packet authorization hoặc runtime authorization.

## 6. Change-control workflow và trạng thái

Đề xuất này phải được independent audit và user decision cùng ACR revision 7, sau đó mới có thể được xử lý bundled/canonical theo workflow. Approval ACR revision 7 không tự phê duyệt điều khoản QoS §10(3); điều khoản amendment phải được nêu rõ trong cùng disposition. Mọi canonical record phải lưu lịch sử approval ngày `2026-10-03` với ACR revision 6 và, nếu xảy ra, ghi approval bundle mới bằng ngày thực tế.

Quyết định revision/hash QoS không được suy ra từ proposal này. Nếu governance quyết định cần revision/hash mới, phải xác định trong approval workflow trước canonical integration; không dùng R4-E2 để ngầm tạo revision/hash.

```text
ACR_REVISION_7: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
QOS_SECTION_10_3_AMENDMENT: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
QOS_REVISION_4: CURRENT_AUTHORITY_UNTIL_AMENDED_BY_APPROVED_WORKFLOW
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Tài liệu này là proposal để audit và user decision. Nó không sửa QoS revision 4, ACR revision 6, PEP, ledger, source hay interface; không tích hợp canonical; và không cấp quyền code/runtime.
