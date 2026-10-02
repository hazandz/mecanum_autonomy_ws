# A0.5.2.3 — D10-A Canonical Asset Envelope Foundation

**Trạng thái:** `D10-A IMPLEMENTED_CORE_ONLY — A0.5.2 YAML MIGRATION NOT STARTED — RUNTIME NOT APPROVED`

## Authority

`docs/MECANUM_NAV_DRL_Architecture.docx` đã được xác minh SHA-256:

```text
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

D10-A được Architect/User khóa: một V3 asset có thể mang envelope tường minh với đúng hai vùng `fragment` và `catalog`. D11–D14 vẫn `PENDING_ARCHITECT_USER_APPROVAL`; D15-B vẫn `IMPLEMENTED_CORE_ONLY`.

## API envelope

`mecanum_nav_rl.config.CanonicalV3AssetEnvelope` là model Pydantic strict, immutable và lazy-export. Model có đúng hai field bắt buộc:

- `fragment: Mapping[str, object]`: payload structural raw/pre-resolution, có thể trở thành input D08 sau này.
- `catalog: Mapping[str, object]`: metadata/pre-resolution không thuộc resolved payload.

Mỗi vùng chấp nhận rỗng để hỗ trợ asset fragment-only hoặc catalog-only, nhưng không cho phép cả hai vùng rỗng. Key top-level của mỗi vùng phải là string không rỗng, không chứa NUL. Validator `mode="before"` kiểm key raw trước Pydantic; integer và boolean key bị reject thay vì bị coercion sang string. Một key top-level không thể đồng thời ở `fragment` và `catalog`; vì vậy envelope không có duplicate semantic ownership.

Contract không normalize, rename, flatten hay infer nested content. Nó không kiểm model shape, không resolve token và không hash. `catalog` không tự đi vào `ResolvedConfigV3`; future grouping chỉ có thể lấy subtree `fragment` qua caller-supplied path tường minh ở scope riêng.

## Giới hạn immutability

`ConfigModelV3` ngăn gán lại field ở public boundary. Các raw nested mapping không được deep-freeze bởi pattern V3 hiện có; increment này không thêm serializer, adapter hoặc cơ chế deep-immutability mới. Consumer phải coi nested raw mappings là read-only cho tới khi có scope/authority riêng.

## Explicit non-goals

Không có YAML migration, grouping/extraction implementation, grouping manifest, filesystem access/discovery, YAML parsing/loading, loader/compiler/hash/validator/composition integration, token resolution, `ResolvedConfigV3` construction, selection API change, V1 change hay runtime I/O.

Không có ROS, Gazebo, gz, Gymnasium, SB3, Ground Truth, bridge, `/cmd_vel`, guard hoặc hardware operation.

## Evidence

Các validation offline đã pass:

- `python -m pytest src/mecanum_nav_rl/test/test_v3_asset_envelope.py -q`: 23 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_v3_asset_selection.py -q`: 34 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_v3_composition.py -q`: 10 passed.
- `python -m pytest src/mecanum_nav_rl/test -q`: 438 passed.
- `python -m colcon build --packages-select mecanum_nav_rl --symlink-install`: pass.
- `python -m colcon test --packages-select mecanum_nav_rl`: pass.
- `python -m colcon test-result --verbose`: 21 tests, 0 errors, 0 failures, 0 skipped.

Build/test chỉ chứng minh `SOURCE_IMPLEMENTATION`/`OFFLINE_EVIDENCE`; không phải runtime evidence.

`A0.5.2 YAML MIGRATION NOT STARTED — D11–D14 PENDING`  
`RUNTIME NOT APPROVED`
