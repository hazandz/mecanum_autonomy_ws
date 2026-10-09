# WP-05 Map Hash Serialization Decision Packet

**Trạng thái:** DRAFT — PROPOSED_FOR_USER_DECISION
**Baseline:** origin/integration/implementation@c37a5bff9dd6cc32fc503cdd796b31720a58a616
**Authority hiện hành:** Architecture §48 và WP-05 canonical artifact-foundation decision đã tích hợp.
**Mục đích:** Xin Project Owner/User quyết định quy tắc serialization bytes cho mecanum_map_hash/v1 trước khi tạo canonical map artifact.

Packet chỉ đề xuất lựa chọn. Nó không sửa Architecture, không chọn serialization rule đang có hiệu lực, không tạo map artifact và không cấp code/runtime authority.

## 1. Vấn đề cần quyết định

Architecture §48 xác định map_content_hash = SHA256(canonical_json(map_hash_manifest)); projection có schema mecanum_map_hash/v1 và hai file entry cho map.yaml (map_yaml) cùng map.pgm (occupancy_image); mỗi entry pin relative name, byte size và SHA-256 raw file. Metadata không nằm trong hash; pose graph dùng hash manifest riêng. WP-05 foundation Registry giữ nguyên ranh giới đó và loại result field khỏi digest input.

Các authority hiện hành chưa định nghĩa chính xác bytes do canonical_json(...) tạo ra. Hai implementation có thể dùng cùng logical fields nhưng khác byte stream và cho ra digest khác nhau. Vì vậy hash chưa thể tái lập liên nền tảng một cách xác định.

Quy ước RFC8785_JCS_UTF8 trong foundation áp dụng cho scenario artifact. Nó không tự trở thành map-hash authority.

## 2. Những điểm cần quyết định

1. JSON canonicalization standard: tiêu chuẩn công khai hay đặc tả nội bộ chuẩn tắc.
2. Encoding và BOM policy của bytes được băm.
3. Object-key ordering cho từng object.
4. Array/entry ordering cho files; thứ tự cố định theo role hay quy tắc khác.
5. Number/string rules: biểu diễn số; escaping chuỗi, Unicode, slash/control characters; xử lý dữ liệu không hợp lệ.
6. Exact hashed projection: đầy đủ object/field đầu vào, phân biệt projection được băm với toàn bộ map_manifest.json.
7. Self-reference: map_content_hash và mọi result/derived field không được nằm trong payload được băm; quy định cách tạo projection để loại chúng ổn định.
8. Phân biệt hai digest:
   - raw-file SHA-256 trên đúng bytes map.yaml và map.pgm, được ghi trong các file entries;
   - resulting map_content_hash, SHA-256 trên serialized manifest projection.

   Hai digest có payload và mục đích khác nhau, không thay thế nhau.

## 3. Lựa chọn để Project Owner/User quyết định

| Lựa chọn | Trạng thái | Hệ quả |
|---|---|---|
| **A — RFC 8785 JCS, UTF-8 không BOM** | PROPOSED_FOR_USER_DECISION | Dùng RFC 8785 JSON Canonicalization Scheme, encode UTF-8 không BOM rồi SHA-256. Cần chốt array ordering, exact hashed projection và self-reference exclusion trong map contract. Đây chỉ là đề xuất; không kế thừa tự động từ scenario. |
| **B — Đặc tả nội bộ đầy đủ** | PROPOSED_FOR_USER_DECISION | Phê duyệt đặc tả map-specific gồm mọi mục ở §2: byte grammar, key/array order, escaping, number domain, encoding, BOM và projection. Phải đủ chặt để hai implementation độc lập tạo cùng bytes. |
| **C — Defer** | PROPOSED_FOR_USER_DECISION | Chưa chốt serialization; không tạo hoặc công nhận canonical map instance cho tới khi có quyết định và change control tương ứng. |

Project Owner/User có thể chọn A, B hoặc C, hoặc yêu cầu packet sửa. Packet không chọn thay.

## 4. Test vector minh họa — proposal, không phải authority

Vector minh họa lựa chọn A cho projection ví dụ; đây không phải map instance, hash authority hay test bắt buộc hiện hành. Hai raw SHA là SHA-256 của chuỗi rỗng chỉ để vector có đầu vào xác định; size_bytes: 0 không mô tả map hợp lệ.

**Input projection đề xuất:** schema mecanum_map_hash/v1; files theo thứ tự đề xuất map_yaml rồi occupancy_image; mỗi entry có tên map.yaml/map.pgm, size_bytes 0 và sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.

**Canonical bytes nếu chọn RFC 8785:** UTF-8 không BOM, không whitespace ngoài chuỗi, JCS key ordering, không newline cuối. Bytes chính xác:

    {"files":[{"name":"map.yaml","role":"map_yaml","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0},{"name":"map.pgm","role":"occupancy_image","sha256":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size_bytes":0}],"schema":"mecanum_map_hash/v1"}

SHA-256 của đúng bytes trên:

    99d14072bd33fbf57c1374861c0994e5a6e9118db9317a4d65c48ef70eb1b639

Digest chỉ minh họa vector và giả định serialization nêu trên. Nó không kích hoạt RFC 8785 cho map, không tạo acceptance vector chính thức và không được gắn vào artifact.

## 5. Acceptance criteria sau quyết định

Sau khi quyết định được ghi nhận qua change control, implementation/validator phù hợp phải:

- tạo cùng serialized bytes và SHA-256 trên các môi trường độc lập;
- xác thực schema, roles, relative names, byte sizes và raw-file SHA-256;
- loại map_content_hash và mọi manifest result/derived fields khỏi payload trước serialization;
- giữ metadata.yaml, manifest result fields và optional pose graph ngoài map_content_hash;
- phân biệt raw-file digest với resulting map-content digest;
- từ chối representation ngoài đặc tả được phê duyệt, không tự chọn cách chuẩn hóa;
- có test vectors chính thức được phê duyệt, gồm bytes chính xác và expected SHA-256.

Các tiêu chí này không tự phê duyệt artifact hay cho phép runtime.

## 6. Record/change control sau quyết định

Sau khi Project Owner/User chọn A hoặc B:

1. Ghi quyết định, phạm vi và test vectors trong governance decision record mới.
2. Nếu làm rõ Architecture §48 hoặc thay đổi authority map-hash, dùng change-control vehicle phù hợp với Architecture hierarchy (ví dụ ACR/Architecture clarification); không kích hoạt quy tắc mới chỉ bằng cách sửa Registry.
3. Chỉ cập nhật Registry/PEP/Ledger khi có prompt riêng cho đúng path và nội dung. Ledger nếu được phép cập nhật phải append-only.
4. Audit và authorization/integration vẫn là các bước riêng; candidate decision record không tự kích hoạt thay đổi.
5. Chỉ sau khi serialization authority active mới chuẩn bị lại canonical map candidate với source, raw hashes và provenance riêng.

Nếu chọn C, ghi nhận defer và giữ điều kiện chưa thể tạo canonical map hash.

## 7. Ranh giới

- Không chọn map source hoặc map ID; không tạo artifacts/maps/**, map.yaml, map.pgm, metadata hay manifest.
- Không chọn scenario/world/value, không tạo scenario.json.
- Không đo hardware, không tạo measurement plan/result và không sửa hardware approval.
- Không sửa Architecture DOCX, PEP, Registry, Ledger, contracts, source hoặc WP-04.
- Không thay WP status/dependency; WP-05 vẫn mở.
- Không cấp code, ROS, runtime, HIL, hardware, deploy_sim hoặc deploy_real authority.
