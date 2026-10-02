# A0.5.2.2 — Explicit V3 Asset Selection Foundation

**Trạng thái:** `D15-B IMPLEMENTED_CORE_ONLY — A0.5.2 YAML MIGRATION BLOCKED — RUNTIME NOT APPROVED`

## Authority

`docs/MECANUM_NAV_DRL_Architecture.docx` đã được xác minh SHA-256:

```text
f0fb1ebede5f4fa18604610c04bb13587d456173b4fd942dba77e44d49777860
```

Authority bổ sung: ADR A0.5 canonical composable layer, readiness A0.5.2.0.1 và decision packet A0.5.2.1. D15-B khóa caller-owned explicit selection/path-list; D10–D14 vẫn chờ quyết định.

## API contract

`mecanum_nav_rl.config.ExplicitV3AssetSelection` là model Pydantic strict, immutable, lazy-export từ package boundary. Nó nhận:

- `runtime_selection: RuntimeSelectionV3`;
- chín opaque string paths: `base_path`, `frames_path`, `topics_catalog_path`, `qos_catalog_path`, `acceptance_path`, `measurements_catalog_path`, `ppo_path`, `profile_path`, `mode_path`.

Mỗi path phải là string, không rỗng sau `strip`, không chứa NUL byte và khác mọi path field còn lại. API giữ nguyên string caller truyền; không normalize relative/absolute path và không suy ra profile/mode hoặc semantic nội dung từ tên path.

`RuntimeSelectionV3` là nested model nên validator D03 model-owned `validate_profile_mode_v3` được tái sử dụng, không copy runtime/profile-mode matrix và không tạo circular import. D03 chỉ xác thực cặp caller cung cấp; không auto-select profile hoặc mode.

## Explicit non-goals

API này không scan/discover filesystem, không kiểm existence hay loại file, không parse/load YAML, không compose fragment, không resolve token, không construct `ResolvedConfigV3`, không hash, không gọi compiler, và không xác nhận YAML tại path mang semantic phù hợp với runtime selection.

Không có YAML migration, grouping manifest package-owned, loader/compiler/hash/composition change, V1 change, ROS/Gazebo/runtime I/O, `/cmd_vel`, guard, bridge hay hardware operation.

## Evidence

Các validation offline đã pass:

- `python -m pytest src/mecanum_nav_rl/test/test_v3_asset_selection.py -q`: 34 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_config_v3_schema.py -q`: 50 passed.
- `python -m pytest src/mecanum_nav_rl/test/test_v3_composition.py -q`: 10 passed.
- `python -m pytest src/mecanum_nav_rl/test -q`: 415 passed.
- `python -m colcon build --packages-select mecanum_nav_rl --symlink-install`: pass.
- `python -m colcon test --packages-select mecanum_nav_rl`: pass.
- `python -m colcon test-result --verbose`: 21 tests, 0 errors, 0 failures, 0 skipped.

Build/test chỉ chứng minh source/API offline; không phải runtime evidence.

`A0.5.2 YAML MIGRATION BLOCKED PENDING D10–D14`  
`RUNTIME NOT APPROVED`
