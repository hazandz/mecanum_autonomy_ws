# Đề xuất bundled contract amendment — phạm vi QoS §10(3) cho Gate A/Gate B

**Status:** `QOS_SECTION_10_3_AMENDMENT: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL`
**Work package:** `WP-04-QOS-SECTION-10-3-SCOPE-AMENDMENT-PROPOSAL`
**Source branch/commit:** `wp-04-qos-r4-e2-bundle-traceability-proposal@dc1d54ab13dec0e1a96744da6b8f1463f78e3d3b`
**Expected source parent:** `91743f4ac4672b9eb9db7179c44e136a0327be92`
**Integration reference:** `origin/integration/implementation@f8933bcff2bb30b1dad57d71d91678e36746326f`
**Companion proposal:** `ACR_V3_PRIMITIVE_SCOPE_CLARIFICATION_PROPOSAL.md`
**Runtime status:** `RUNTIME_NOT_APPROVED`

## 1. Mục đích, authority và giới hạn

Đây là supporting proposal cho audit/user decision về formal amendment của QoS §10(3) đối với Gate A primitive-only và Gate B connected/profile-resolving. Vehicle versioning được đề xuất là document revision 5, ở `RECEIPT_TOPIC_QOS_CONTRACT_REVISION_5_PROPOSAL.md` với SHA-256 `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`. Tài liệu này chỉ là rationale/evidence; nó không phải sidecar amendment authority. QoS revision 4 vẫn là authority hiện hành cho đến khi revision 5 bundle được audit, user-approved và canonical-integrated.

Đề xuất đi cùng ACR revision 7. Giữ nguyên transport contract ID `mecanum.final-issued-receipt-topic-qos/v1` và canonical transport-manifest SHA-256 `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`; chúng nhận diện transport, không phải toàn bộ document normative. QoS document revision 5 SHA và transport manifest SHA là hai giá trị khác nhau. Giữ nguyên manifest chỉ khi JSON canonical byte-identical với QoS revision 4 và hash tính lại khớp; nếu không, dừng `STOPPED_VERSION_HASH_DISPOSITION_UNRESOLVED`.

R4-A1 là nhãn change-control cho substantive approval-scope amendment, được hợp nhất vào QoS revision 5 §10.3; không có authority độc lập ngoài draft revision 5 đã versioned/hash. Không thêm R4-A1 làm runtime `TopicQosContractV3` field hoặc đưa vào `config_hash`. Không tạo canonical hash riêng cho R4-A1: bundle pin document revision 5 bằng document SHA bên trên. Nếu governance sau này yêu cầu record/hash amendment riêng thì phải xử lý trong workflow; proposal này không bịa thêm identity.

R4-E2 không được áp dụng lên QoS revision 4 lịch sử. Thay vào đó, reference ACR revision 7 trong draft revision 5 §10.2 thể hiện prospective traceability disposition; historical approval §1 với ACR rev.6 và R4-E1 được giữ nguyên. R4-A1 được hợp nhất trong draft revision 5 §10.3. Bundle đề xuất gồm ACR revision 7 và QoS document revision 5 exact SHA, trong khi transport ID/manifest SHA giữ nguyên. Chỉ có hiệu lực sau independent audit, explicit bundled user approval và canonical integration; approval mới phải ghi ngày thực tế.

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

### 3.3 Wording đề xuất được mang bởi QoS document revision 5

Phần wording đầy đủ, có version và hash chính xác, nằm trong `RECEIPT_TOPIC_QOS_CONTRACT_REVISION_5_PROPOSAL.md` §§10.1–10.4, document SHA-256 `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`. Draft đó tích hợp prospective companion reference ở §10.2 (R4-E2 disposition) và normative Gate A/Gate B approval scope ở §10.3 (R4-A1 incorporated). File hiện tại chỉ giải thích rationale; không dùng bản sao wording tại đây như sidecar hay authority khác.

### 3.4 Tách biệt transport manifest hash và R4-A1

Canonical JSON manifest SHA-256 chỉ bind transport contract (endpoint, interface reference, QoS profile và transport/status semantics); nó không bind approval wording của §10(3). Manifest trong QoS revision 4 và source commit `100f9f17e2142ea206a2a6fd02d94397547f2388` được so sánh byte-for-byte; bytes bằng nhau. Hash tính lại trên canonical JSON bytes không có trailing newline là `a3bc1a965fc6885825ab961289fa4028862aa7af4b3f3156bc40542f7ee08f62`, khớp SHA đã công bố.

Document QoS revision 5 có document SHA-256 `9f87f4d09ec50aacf8c0cf69e11bff8bceb4219b8d09f68998288907afb8302b`; hash này nhận diện toàn bộ bytes normative draft revision 5 và khác manifest SHA ở trên. Hash được ghi trong proposal/approval record bên ngoài document để tránh tự tham chiếu. Contract ID `/v1` cùng `version: 1` trong canonical manifest là transport identity/version; chúng không phải document revision và được giữ nguyên. R4-A1 không trở thành `TopicQosContractV3` runtime field, config input hoặc `config_hash`; không có R4-A1 hash riêng trong disposition này.

## 4. Bảng trước/sau và tác động

| Phạm vi | QoS revision 4 hiện hành | Rule đề xuất trong QoS document revision 5 | Tác động nếu được duyệt và tích hợp |
|---|---|---|---|
| Gate A primitive-only | §10(3) nêu public-interface version/hash và resolved-config binding, nhưng không phân định Gate A | Exact approved contract ID/SHA và structural validation; không yêu cầu tạo/bind resolved config, config hash hoặc public interface/topic | Có thể xem xét packet primitive-only mà không tạo artifact ngoài scope; không tự cấp code authorization |
| Gate B connected/profile-resolving | Cần public-interface version/hash và resolved-config binding; ACR §8 giữ sáu gate | Giữ nguyên điều kiện §10(3) và tất cả gate ACR hiện hành | Connected/profile-resolving work vẫn bị chặn tới khi đủ bundle, binding và evidence |
| Safety/governance | Các contract/PEP hiện hành có authority | Không miễn safety, lifecycle, temporal, Ground Truth isolation hay WP-03 dependency | WP-03 phải đóng hoặc dependency được xử lý bằng PEP/governance amendment riêng |

Cho đến khi QoS document revision 5 và ACR revision 7 được audit, bundled user-approved và canonically integrated, **không áp dụng cột “Rule đề xuất”**. QoS revision 4 §10(3) hiện hành chưa được sửa và Gate A không được coi là đã miễn điều kiện này.

## 5. Điều kiện không thay đổi và dependency

Đề xuất này không thay đổi các điều kiện sau:

- Safety/lifecycle ownership, action/reset barriers, cutoff/time-domain consistency và fail-closed semantics vẫn áp dụng.
- Ground Truth isolation trong policy path vẫn bắt buộc.
- `WP-04-POLICY-CORE-P0` vẫn phụ thuộc WP-03 theo PEP-001 revision `0.2.0`; đề xuất này không sửa PEP, ledger, sequencing hoặc status. Chỉ closure WP-03 hoặc PEP/governance amendment riêng, được audit và duyệt riêng, mới xử lý dependency.
- WP-03 và WP-04 vẫn `BLOCKED_BY_CONTRACT`.
- Draft QoS document revision 5 không đổi transport profile, message fields, topic, protocol semantics, canonical manifest, contract ID hoặc manifest hash. Document SHA-256 chỉ nhận diện toàn bộ draft revision 5; không thay transport manifest hash.
- Không có code authorization, implementation packet authorization hoặc runtime authorization.

## 6. Change-control workflow và trạng thái

Đề xuất này phải được independent audit và user decision cùng ACR revision 7, sau đó mới có thể được xử lý bundled/canonical theo workflow. Approval ACR revision 7 không tự phê duyệt điều khoản QoS §10(3); điều khoản amendment phải được nêu rõ trong cùng disposition. Mọi canonical record phải lưu lịch sử approval ngày `2026-10-03` với ACR revision 6 và, nếu xảy ra, ghi approval bundle mới bằng ngày thực tế.

Disposition hiện được đề xuất là phát hành document QoS revision 5 làm vehicle cho normative §10(3), giữ transport ID/manifest hash không đổi và bind bundle bằng document SHA-256 chính xác. R4-A1 được incorporate vào §10.3; R4-E2 không áp dụng revision 4 lịch sử và được thể hiện prospective ở §10.2 revision 5. Đây vẫn là proposal, không phải canonical decision hay approval.

```text
ACR_REVISION_7: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
QOS_SECTION_10_3_AMENDMENT: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
QOS_REVISION_4: CURRENT_AUTHORITY_UNTIL_REVISION_5_BUNDLE_APPROVED_AND_CANONICALLY_INTEGRATED
QOS_REVISION_5: DRAFT_PENDING_INDEPENDENT_AUDIT_AND_USER_APPROVAL
R4_E2: PROPOSED_REFERENCE_IN_REVISION_5_ONLY; NOT_APPLIED_TO_HISTORICAL_REVISION_4
R4_A1: INCORPORATED_IN_DRAFT_REVISION_5_SECTION_10_3; NO_SEPARATE_AUTHORITY
WP-03: BLOCKED_BY_CONTRACT
WP-04: BLOCKED_BY_CONTRACT
CODE_AUTHORIZATION: NOT_GRANTED
RUNTIME_NOT_APPROVED
```

Tài liệu này là supporting proposal/rationale. Nó không sửa QoS revision 4, ACR revision 6, PEP, ledger, source hay interface; không tích hợp QoS revision 5 canonical; và không cấp quyền code/runtime.
