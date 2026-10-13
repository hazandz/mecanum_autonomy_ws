# WP-04 OIC V3 — Ủy quyền triển khai bounded fail-closed

| Trường | Giá trị |
|---|---|
| Work package | `WP04-OIC-V3-BOUNDED-FAIL-CLOSED-IMPLEMENTATION-AUTHORIZATION` |
| Change class | `L1_BOUNDED_CODE_AUTHORIZATION_WITHIN_ACTIVE_L2_AUTHORITY` |
| Exact source/integration base | `5e5075b5860034527350629c686c2d26651fbfeb` |
| Architecture authority | `docs/MECANUM_NAV_DRL_Architecture.docx`; SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`; authority cao nhất, không sửa |
| Active abstract OIC | `docs/OBSERVATION_INPUT_CONTRACT_V3.md`; source SHA-256 `d44d33843c32d1f0d5c747522f3add09bfde21fcb0884e21da93a52476cb4dfc`; semantic-manifest SHA-256 `175a1af789b6641cfe455daeee8fedac80aaf80ad8c00792ba0a287c41acc0bb` |
| Active L2 runtime-binding | `docs/architecture/ACR_OBSERVATION_RUNTIME_BINDING_V3.md`, `docs/OBSERVATION_RUNTIME_BINDING_V3.md`, `docs/architecture/OBSERVATION_RUNTIME_BINDING_V3_SEMANTIC_MANIFEST.json`, và `docs/governance/decisions/WP-04_OBSERVATION_RUNTIME_BINDING_V3_DECISION.md`, integration-resident tại base |
| Candidate state | Tại base này, bản ghi dưới đây là governance review candidate. Chỉ sau independent audit PASS cho exact candidate, User authorization riêng cho exact commit, fast-forward và xác minh remote ref mới phát sinh `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION`. |

## Quyết định Owner và điều kiện hiệu lực

Owner chấp thuận có điều kiện một code candidate riêng sau này, giới hạn đúng các seam nội bộ dưới đây. Candidate governance này chưa cấp quyền hiện hành; tại source base `CODE_AUTHORIZATION: NOT_GRANTED`. Khi và chỉ khi đủ bốn điều kiện lifecycle cho exact governance candidate, quyết định tích hợp sẽ cấp duy nhất `BOUNDED_FAIL_CLOSED_IMPLEMENTATION_AUTHORIZATION` cho phạm vi liệt kê. Quyền đó không thay thế code review, yêu cầu test/offline evidence, acceptance của Gate B hoặc các authorization riêng bị loại trừ bên dưới.

## Allowlist triển khai được ủy quyền có điều kiện

Code candidate sau đó chỉ được triển khai các seam không chạy độc lập:

1. Typed snapshot/context data structures.
2. Validator fail-closed cho exact contract identity, `episode_generation`, `reset_epoch`, `runtime_generation`, `config_hash`, và exact topic/type/frame claims chỉ khi các claim ấy được cung cấp qua injected test fixture.
3. Pure-core assembler/synchronizer seam chỉ nhận typed inputs đã validate; thiếu, mismatch hoặc invalid phải trả no-vector. Không phát partial vector hoặc partial hash.
4. Dependency-injected internal adapter boundaries cho LiDAR, LocalReference, measured twist, và receipt/lifecycle context. Đây không phải ROS runtime ingress.

## Invariants và fail-closed

- Bất kỳ contract, frame, type, lifecycle-tuple hoặc config binding mismatch nào đều bị reject; không tạo vector 81D.
- Runtime source/package pins và measurements là điều kiện tiên quyết cho bring-up, không phải defaults. Những mục còn thiếu tiếp tục pending; không tự suy diễn source/version hoặc điền measurement, timeout, freshness hay skew.
- Legacy provenance, simulation source và alias không phải runtime binding hoặc fallback.
- `SafetyLifecycle`, `V3ObservationIngress`, `LidarIngressAdapterV3` và các target owners liên quan chỉ là implementation targets; tài liệu này không tạo runtime evidence.
- Thiếu/mismatch/unverifiable input không được sửa chữa bằng default, coercion, alias, zero-fill hoặc fallback.

## Phạm vi bị cấm

Ủy quyền có điều kiện này không cho phép:

- ROS subscription/publisher/service/action/client/server; ROS runtime ingress.
- Launch file, runtime YAML, parameter default, remap hoặc namespace.
- TF broadcaster/listener; Map Server, Nav2, AMCL, EKF hoặc `robot_localization` runtime setup.
- Tạo `ResolvedConfig` instance, global `config_hash`, resolved/partial profile hoặc partial config.
- Tự tạo package/version/source pin, measurement, timeout, freshness hoặc skew value.
- Sửa public ROS message/interface hoặc bất kỳ receipt v2/QoS6 authority nào.
- Thay đổi WP-05/map, Gate B start/pass hoặc WP-04 closure.
- Runtime, HIL, hardware, motor-enable, `deploy_sim` hay `deploy_real`.
- `RUNTIME_APPROVED` hoặc bất kỳ HIL/hardware/deployment authority.

Việc tích hợp candidate này không có nghĩa code đã được viết, profile/config hash đã resolve, runtime source đã pin, test đã pass, hoặc Gate B đã bắt đầu. Code review và test/acceptance evidence vẫn bắt buộc; quyền này không làm thay đổi Architecture, OIC v3, runtime-binding L2 semantics, receipt v2, QoS6, global 16-root `ResolvedConfig.config_hash`, hay `observation.input_profile`.

```text
Tại source base: CODE_AUTHORIZATION: NOT_GRANTED
WP-04: BLOCKED_BY_CONTRACT
GATE_A_STRUCTURAL_PRIMITIVES: PASSED
GATE_B: NOT_STARTED
WP-05: OPEN
RUNTIME_APPROVED: NOT_APPROVED
```
