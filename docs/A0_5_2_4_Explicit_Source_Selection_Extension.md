# A0.5.2.4 — D11-A/D12-B Explicit Source Selection Extension

**Trạng thái:** `D11-A/D12-B/D15-B IMPLEMENTED_CORE_ONLY — A0.5.2 YAML MIGRATION NOT STARTED — RUNTIME NOT APPROVED`

## Authority

`docs/MECANUM_NAV_DRL_Architecture.docx` đã được xác minh SHA-256:

```text
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

D11-A khóa canonical source tương lai `config/v3/state_localization.yaml`. D12-B khóa canonical source chung tương lai `config/v3/system_contracts.yaml` cho `command_safety`, `reward` và `evaluation`. D06 được amend: giữ nguyên 15 asset hiện có và chỉ thêm đúng hai source này trong YAML migration riêng sau; target tree sẽ có 17 assets.

## Selection boundary

`ExplicitV3AssetSelection` nay yêu cầu đúng 11 opaque paths cùng `runtime_selection`:

- 9 path trước đây: `base_path`, `frames_path`, `topics_catalog_path`, `qos_catalog_path`, `acceptance_path`, `measurements_catalog_path`, `ppo_path`, `profile_path`, `mode_path`.
- 2 path source tương lai: `state_localization_path`, `system_contracts_path`.

Mười một path phải là strict string, không rỗng/whitespace/NUL và pairwise distinct. String được giữ nguyên; API không suy ra semantic, profile/mode hoặc nội dung asset từ path/filename. `RuntimeSelectionV3` tiếp tục tái sử dụng D03 nested validation.

## Không phải YAML migration

Hai YAML source trên **chưa tồn tại** và không được tạo trong increment này. API không load/kiểm tra tồn tại path, scan filesystem, parse YAML, compose, resolve token, hash, construct `ResolvedConfigV3`, gọi loader/compiler, hay implement grouping/extraction.

D13 và D14 vẫn `PENDING_ARCHITECT_USER_APPROVAL`. Content, model shape, token/provenance và semantic ownership cụ thể bên trong hai source vẫn là `MISSING_EVIDENCE` cho YAML migration sau.

## Evidence

Các validation offline đã pass:

- `python -m pytest src/mecanum_nav_rl/test/test_v3_asset_selection.py -q`: 44 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_v3_asset_envelope.py -q`: 23 passed.
- `python -m pytest src/mecanum_nav_rl/test -q`: 448 passed.
- `python -m colcon build --packages-select mecanum_nav_rl --symlink-install`: pass.
- `python -m colcon test --packages-select mecanum_nav_rl`: pass.
- `python -m colcon test-result --verbose`: 21 tests, 0 errors, 0 failures, 0 skipped.

Build/test chỉ là `SOURCE_IMPLEMENTATION`/`OFFLINE_EVIDENCE`, không phải runtime evidence.

`A0.5.2 YAML MIGRATION NOT STARTED — D13/D14 PENDING`  
`RUNTIME NOT APPROVED`
