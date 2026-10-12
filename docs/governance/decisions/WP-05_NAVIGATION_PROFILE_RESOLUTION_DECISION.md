# WP-05 — Quyết định target và quy trình resolve Navigation V1 profile cho `warehouse_map2`

**Work package:** `WP05-WAREHOUSE-MAP2-NAVIGATION-PROFILE-RESOLUTION`
**Exact integration base:** `29080644f3020f7ecd208dc45433c7d36ecc5e2e`
**Candidate branch:** `wp-05-warehouse-map2-navigation-profile-resolution-29080644`
**Candidate state:** chỉ là governance review candidate; chờ focused independent audit, ủy quyền riêng cho exact commit, fast-forward và xác minh remote ref.
**WP-05:** `OPEN`

## 1. Phạm vi và phân loại quyết định

Tài liệu này ghi nhận target Navigation V1 do Project Owner/User cung cấp (`USER_SUPPLIED_DECISION`) và đặt quy trình để sau này resolve một profile tĩnh, Git-pinned. Nó không tạo profile instance, không coi profile đã resolve, không chọn map cho navigation, và không thay đổi artifact hay trạng thái của nó.

Các quyết định User đã cung cấp cho candidate này:

- Target Navigation V1 là Map Server + AMCL với `nav2_amcl::OmniMotionModel`.
- SLAM Toolbox chỉ thuộc mode `MAPPING`; không chạy đồng thời làm localization trong `NAV2_BASELINE` hoặc `HYBRID_AI_LOCAL`.
- Intended map/global frame là `map`.
- User xác nhận `warehouse_map2` được tạo bằng SLAM khi dùng `tugbot_depot.sdf`.

Ba mệnh đề về SLAM/world phải được giữ tách biệt: quan hệ tạo map từ `tugbot_depot.sdf` là `USER_SUPPLIED_DECISION`; Git pin chỉ nhận diện bytes của SDF; không mệnh đề nào ở đây chứng minh `map == world`, transform, metric alignment, TF runtime, localization correctness hoặc compatibility. Evidence record world-frame hiện có chỉ nhận diện subject và quyết định khai báo theo ACR; metadata canonical vẫn `world_frame.state: NOT_DECLARED`.

## 2. Trạng thái artifact và identity tại base

Tại exact base `29080644f3020f7ecd208dc45433c7d36ecc5e2e`, các bytes được kiểm tra trực tiếp:

| Thành phần | Giá trị tại base | SHA-256 / trạng thái |
|---|---|---|
| Root | `artifacts/maps/warehouse_map2/` | Có trong integration; đây là artifact draft, không phải map được chọn/approved cho navigation |
| `map_id` | `warehouse_map2` | Khớp tên thư mục |
| `artifact_identity` | `4a8a23d0-7e27-4a50-8201-dd1abf1a3db4` | Identity bất biến |
| `map_content_hash` | — | `2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90` |
| `map.yaml` | `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` |
| `map.pgm` | `artifacts/maps/warehouse_map2/map.pgm` | `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55` |
| `approval_status` | `draft` | Chưa approved; Architecture §48 yêu cầu approved map trước Navigation |
| `world_frame.state` | `NOT_DECLARED` | Không có transition trong candidate này |
| `runtime_compatibility.state` | `NOT_VALIDATED` | Không có transition trong candidate này |

Giữ nguyên Architecture §48 hash boundary: chỉ projection của `map.yaml` và `map.pgm` nằm trong `map_content_hash`; metadata, manifest, evidence và result hashes nằm ngoài payload. Profile phải pin cả map ID, artifact identity và hash; không được coi raw-file SHA hay Git provenance là thay thế cho chúng.

## 3. Authority và nguồn/config inventory

Architecture DOCX tại exact base có SHA-256 `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`. Các yêu cầu chi phối gồm §4–5 (`ResolvedConfig`, profile/mode và `config_hash` bất biến), §11, §13–14 (topic/TF/frame authority), §41 (EKF), §42–43 (mode và Map Server/AMCL Omni), §48–50 (map approval/hash, lifecycle và verification), cùng Appendix A. Architecture có precedence; config bên dưới là evidence về bytes/config hiện có, không phải lựa chọn nguồn canonical.

Mọi Git pin trong ma trận dưới đây nhận diện file tại commit `29080644f3020f7ecd208dc45433c7d36ecc5e2e`; SHA-256 là hash bytes của file tại commit đó.

| Nguồn đã đọc tại base | SHA-256 | Ý nghĩa / giới hạn dùng |
|---|---|---|
| `docs/MECANUM_NAV_DRL_Architecture.docx` | `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204` | Authority kiến trúc; §43 chọn Map Server + AMCL Omni; §49 startup sequence; §48 approval/hash boundary |
| `artifacts/maps/warehouse_map2/map.yaml` | `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68` | Artifact map bytes; source of truth tại artifact root, chưa approval |
| `artifacts/maps/warehouse_map2/map.pgm` | `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55` | Artifact occupancy image bytes |
| `artifacts/maps/warehouse_map2/metadata.yaml` | `44a3adf3a50d1e002c0fda0703dc605a6df2777928f922eab548dd939455bf5b` | Trực tiếp ghi `draft`, `NOT_DECLARED`, `NOT_VALIDATED` |
| `artifacts/maps/warehouse_map2/map_manifest.json` | `94795a8f2f92399b5ce8620b18ab8c5bfbc0af67bd7020ce3110ed1fc15c5df8` | Pin identity, projection và metadata descriptor; không phải Nav profile |
| `docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json` | `4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294` | Evidence record integration-resident; association `USER_SUPPLIED_DECISION`, SDF Git pin chỉ xác nhận source bytes |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf` tại `e89aeda5ca78859bfeedac4e7b94bcd6c7dcc7f0` | `a4b6253340baa866d89640d62a94d04fbea51425e9af1deca591422a0a36d91d` | Git-pinned SDF source do User nêu; không chứng minh map/world relation hoặc transform |
| `ros2_ws/src/ROBOT_URDF_final_description/config/nav2_params.yaml` | `26c37806f98e131e5993672122dee7efc5a4de1011f0bcb69e4c3a6e273ef4af` | Registry phân loại nguồn ngoài V3 là `PRE_V3_NONCANONICAL`; chỉ static legacy evidence |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/nav2_bringup.launch.py` | `97f70679cb107411e882e387a49c87ec80243c3fa43d70846083f8be1b3e143e` | Legacy launch; default map trỏ về ROS package copy `maps/warehouse_map2.yaml`, không phải canonical artifact root |
| `ros2_ws/src/ROBOT_URDF_final_description/config/mapper_params_online_async.yaml` | `8e363a5e141cb275f201ea78b84f2816b5b56c087a2435b2bd4f094fbd150c7a` | Legacy MAPPING config; không là Navigation localization config |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/slam.launch.py` | `28bf46d825fdcdaf79081897d1f0933dcf6946b4df17008c5a158563d03fe728` | Legacy SLAM launch; không dùng SLAM Toolbox làm NAV2 localization |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro` | `7a8f72894d024598f908b12b5a867c4c90e7e6ba167d9130e3e941e0129b5477` | Robot-description evidence có link/joint `RPLiDAR_A1M8_1`; không tự chọn profile scan frame |
| `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | `6c7d0b9e90c2ed87a1de7aaf83b2c3ad07a897b5b1d1b2d26737054020d3f0fc` | Static sensor config khai báo `/scan` và frame `RPLiDAR_A1M8_1`; không phải runtime header evidence |
| `ros2_ws/src/ROBOT_URDF_final_description/launch/gazebo.launch.py` | `2f0e2b329b4ad600e777a4a1b0578f3cc08fd9aea3a93705875e7a5afddae325` | Static launch có bridge `/scan` và TF với scoped child khác; không xác nhận runtime graph |
| `ros2_ws/src/mecanum_nav_rl/config/v3/base.yaml` | `f190f53f5c33519a48d4d6dab3f25c9da5d96200e7123704534c955d34e17d91` | V3 input skeleton; map identity/hash là `REQUIRED_BUILD_INPUT`, không resolved config |
| `ros2_ws/src/mecanum_nav_rl/config/v3/frames.yaml` | `815bff5df49f6de07a48e61275a21c728904ff699b771a0c970507483d0ff9da` | V3 input ghi `map`, `odom`, `base_link`, generic `lidar_frame`, EKF/RSP ownership; không chứng minh alias/geometry |
| `ros2_ws/src/mecanum_nav_rl/config/v3/topics.yaml` | `7dc2156aef44e83ca767528774fff6acd543814be3a0d9eb0b6373c4f5217a2d` | V3 input ghi `/scan`; không pin `LaserScan.header.frame_id` |
| `ros2_ws/src/mecanum_nav_rl/config/v3/modes/nav2_baseline.yaml` | `8b62ce6595c8545fa6b73a020872b08df3403d87f9ea5ea99ccd11eb449725ae` | Chỉ ownership Planner/Controller; không có Nav2/Map Server profile instance |
| `ros2_ws/src/mecanum_nav_rl/config/v3/modes/mapping.yaml` | `bc59f7dc34c44a401cf28ed5d2f55f58d316da65d1af1b1a519b72fa9078afb5` | Teleop/safety mode skeleton; không dùng làm Navigation localization |
| `ros2_ws/src/mecanum_nav_rl/config/v3/modes/hybrid_ai_local.yaml` | `3fcf860fda1511366c2ecdaa71bbc68cfab606529996af864b598ac9b0c24c72` | Planner/PPO/LocalReference ownership skeleton; không dùng cho V1 baseline controller profile |
| `ros2_ws/src/mecanum_nav_rl/config/v3/profiles/sim_eval.yaml` | `d5e9075c22c330d799c2250df03e76697e1fce5a5fced7161a4994cb3a653d04` | Overlay skeleton; không pin map/Nav2/EKF/frame instance |
| `ros2_ws/src/mecanum_nav_rl/config/v3/profiles/deploy_sim.yaml` | `1f2cb003b97eef135dc8a524bcb4b72cfacd30a8a918a4499a7435350c10c6c5` | Overlay skeleton; không pin map/Nav2/EKF/frame instance |

Tại base không có tracked `mecanum_nav_bringup/config/**`, Map Server profile config hay EKF config (`ekf_sim.yaml`/`ekf_real.yaml`). Architecture project tree mô tả package/paths đích; nó không làm các file đó hiện hữu. Không có exact ROS/Nav2 package-version lock hoặc pinned install manifest cho profile.

### 3.1 Static findings — không phải runtime findings

- Legacy `nav2_params.yaml` có `robot_model_type: nav2_amcl::OmniMotionModel`, `global_frame_id: map`, `odom_frame_id: odom`, `base_frame_id: base_link`; nhưng AMCL scan topic là relative `scan`, costmaps dùng `/scan`, `bt_navigator` dùng `/odom`, loopback khai `base_scan` và comment nhắc `rplidar_link`, còn Map Server YAML stanza bị comment. Không có một lựa chọn remap/profile thống nhất được pin.
- Legacy `nav2_bringup.launch.py` tự chọn map package-copy làm default và set `autostart: true`. Đây không được chọn làm nguồn canonical; Architecture §48 đòi artifact root duy nhất và §49 định nghĩa thứ tự startup/health gating.
- Robot description/Gazebo sensor khai link/frame `RPLiDAR_A1M8_1`; V3 skeleton dùng tên `lidar_frame`; Architecture §13/Table profile dùng `sim_lidar` cho sim_eval/deploy_sim và `real_lidar` cho deploy_real; loopback config còn có `base_scan`/commented `rplidar_link`. Những tên này không được coi là alias tương đương.
- Architecture cố định `/scan` làm scan topic, `/wheel/odometry_raw` và `/imu/data` làm EKF inputs, `/odometry/filtered` làm filtered odometry input; chỉ EKF sở hữu `odom → base_link`. Per-profile scan frame/link, exact EKF/Nav2 config and version pins vẫn cần được resolve.

## 4. Ma trận target/profile resolution

“Target đã khóa” nghĩa là kiến trúc/decisions đã có; nó không có nghĩa file config đã pin hay runtime đã xác minh. Profile instance chỉ được gọi resolved sau khi mọi mục required dưới đây có đúng một nguồn được chọn, pin bất biến (repository, full commit, path, SHA-256 hoặc package/version lock), kiểm tra consistency tĩnh đạt, và không còn `PENDING_OWNER_DECISION`/`PENDING_EVIDENCE`.

| Field / obligation | Authority và bằng chứng hiện có | Trạng thái tại base / điều kiện resolve |
|---|---|---|
| Map root, `map_id`, identity, `map_content_hash` | Architecture §48; artifact files/manifest nêu ở §2; ACR metadata v1 | Giá trị đã pin cho draft subject, nhưng dùng cho Navigation còn block bởi `approval_status: draft`; không phải map selection/approval |
| Runtime profile/mode | Architecture §§5, 42–43; V3 profile/mode skeletons | V1 mode là `NAV2_BASELINE` theo target Map Server + AMCL; runtime profile (ví dụ `sim_eval` hay `deploy_sim`) và scope sử dụng cụ thể `PENDING_OWNER_DECISION`; không suy ra từ source SDF |
| Nav2 package/version, Map Server config/launch | Architecture §§43, 49; legacy launch/config | Không có canonical bringup hay package-version pin. Exact package versions, immutable config/launch pins, namespace/remaps, artifact path injection và lifecycle binding `PENDING_EVIDENCE`/`PENDING_OWNER_DECISION` |
| Map Server input | Architecture §48 yêu cầu `map_path`, expected ID và hash; legacy launch default trỏ package copy | Resolved profile phải trỏ `artifacts/maps/warehouse_map2/map.yaml`, kiểm tra map ID/hash đã pin; cách launch truyền các giá trị và xác minh chúng `PENDING_EVIDENCE` |
| AMCL provider/model | Architecture §43; legacy config có model Omni | Target provider `AMCL`, model `nav2_amcl::OmniMotionModel` đã được Architecture/User quyết định; concrete parameters, parameter authority/version, initial-pose workflow, covariance/freshness/jump bounds và exact config pin `PENDING_OWNER_DECISION`/`PENDING_EVIDENCE` |
| `map → odom` | Architecture decision D08 và §13: duy nhất AMCL trong Navigation V1 | Ownership đã khóa; cụ thể node/config pin và runtime single-publisher proof còn thiếu |
| `odom → base_link` và odometry | Architecture §41; EKF-only ownership; `/wheel/odometry_raw`, `/imu/data` → EKF → `/odometry/filtered` | Contract topics/ownership đã khóa; EKF config/path/hash và input source profile không tồn tại trong tracked bringup tại base: `PENDING_EVIDENCE` |
| `base_link → lidar` TF edge/geometry | Architecture §§13–14; Xacro và V3 frame skeleton khác nhau về tên | RSP ownership là Architecture target; exact child frame, URDF/config pin, resolved static geometry và matching profile source `PENDING_OWNER_DECISION`/`PENDING_EVIDENCE` |
| Scan topic/type/frame | Architecture topic contract `/scan`, `sensor_msgs/msg/LaserScan`; config sources có `/scan` và relative `scan` | Topic `/scan`/type là fixed contract; canonical `header.frame_id` chưa được chọn/xác minh. Không đồng nhất `sim_lidar`, `RPLiDAR_A1M8_1`, `lidar_frame`, `base_scan`, `rplidar_link` hay scoped alias. Chốt frame/remaps cần Owner decision dựa trên selected robot/sensor config và static transform evidence; runtime header check còn bắt buộc |
| Remaps/namespaces | Architecture §§11–12, 21; legacy launch/config thiếu nhất quán | Exact remap table cho AMCL, costmaps, Nav2 output (`cmd_vel` → `/cmd_vel_nav2_raw`), scan, odom, lifecycle/action endpoints và namespace `PENDING_OWNER_DECISION`/`PENDING_EVIDENCE`; không có implicit alias |
| Lifecycle/startup | Architecture §49–50 | Thứ tự bắt buộc: robot description → drivers/bridge → EKF → Map Server → AMCL → LocalizationMonitor valid → Planner/global costmap → Safety → selected controller/manager → mission acceptance; mọi upstream health/contract check phải healthy trước downstream motion. Launch implementation/version and offline mapping `PENDING_EVIDENCE`; runtime lifecycle proof riêng |
| Resolved `config_hash` | Architecture §4 | Hash trên toàn bộ immutable, fully resolved static `ResolvedConfig`, không gồm runtime timestamp; resolve order và RFC 8785/static hash contract do Architecture quyết định. Chưa có profile instance hoặc exact source manifest; hash chưa tồn tại và không được bịa |
| Version/source closure | Architecture §§4–5, PEP-001 và Registry | Cần exact commit/path/SHA cho mọi config, launch, robot description, package/version source và map subject; Git refs phải immutable. Existing static hashes ở §3 chỉ là inventory/provenance, chưa được chọn thành profile pins |

## 5. Offline và runtime evidence

**Offline evidence cần trước khi profile có thể được gọi resolved (tĩnh):** selected runtime profile và `NAV2_BASELINE`; map subject/manifest hashes; exact Nav2/Map Server/AMCL/EKF/config/launch/robot-description pins; AMCL model/parameters; EKF topic/config; từng TF edge owner và static geometry; exact canonical scan frame/header expectation; mọi remap/namespace; lifecycle declaration; package versions; schema/authority consistency; deterministic resolution và `config_hash` theo Architecture §4. Pinning phải full commit + repository-relative path + digest; branch/tag không đủ. Legacy/static hash inventory không tự chọn source.

**Runtime evidence riêng, không có trong candidate này:** xác nhận node/package/version thực tế; Map Server load đúng artifact ID/hash; lifecycle states/startup inhibition; AMCL initial pose và localization freshness/covariance/jump health; `LaserScan.header.frame_id` thực tế; TF graph/timestamps/authority duy nhất cho `map → odom → base_link → selected lidar frame`; topic publishers/subscribers/remaps; EKF filtered odometry freshness; map identity/hash được nạp. Cần work package/authorization runtime riêng trước khi chạy; không được suy ra từ static config.

Map approval theo Architecture §48 là điều kiện độc lập trước navigation. World-frame validation theo metadata schema là điều kiện/evidence khác; User-supplied SDF provenance không chứng minh transform hay alignment. Profile resolution, map approval, world/frame validation và runtime compatibility không gộp thành một status.

## 6. Quy trình resolve và immutable map/profile generations

1. Project Owner/User chốt các `PENDING_OWNER_DECISION`: runtime profile/use scope; canonical LiDAR `header.frame_id`/child TF frame và remap; các giá trị AMCL/config nếu Architecture không khóa; cùng mọi mâu thuẫn nguồn còn lại. Không chọn theo số lần xuất hiện trong legacy files.
2. Chọn source có authority, tạo hoặc chỉ định Nav2/Map Server/AMCL/EKF/launch/config và package-version pins thuộc đúng ownership. Mỗi source được xác minh bằng exact Git commit, path và SHA-256. Không dùng map copy trong ROS package thay `artifacts/maps/**`.
3. Resolve cấu hình tĩnh, chứng minh toàn bộ required fields/source closure, TF edge ownership duy nhất, remaps và lifecycle consistency; tính `config_hash` chỉ khi toàn bộ input hợp lệ. Bất kỳ pin/field nào thiếu hoặc conflict thì profile vẫn unresolved.
4. Gắn profile bất biến với map `map_id`, `artifact_identity`, `map_content_hash` và config hash. Thay map content/provenance tạo map identity mới; giữ artifact/profile cũ bất biến và tạo profile generation/hash mới. Không mutate hoặc dùng hash profile cũ cho map mới.
5. Sau khi map riêng được approved và profile offline đã resolve, runtime validation chỉ tiến hành theo runtime work package được phê duyệt riêng. Không profile/documentation commit nào tự cấp quyền chạy.

Trạng thái review candidate này không ghi Navigation profile là `resolved`, `canonical`, `active` hay `navigation-ready`; cũng không thay artifact metadata. WP-05 vẫn `OPEN`; `CODE_AUTHORIZATION: NOT_GRANTED`; `RUNTIME_APPROVED: NOT_APPROVED`.
