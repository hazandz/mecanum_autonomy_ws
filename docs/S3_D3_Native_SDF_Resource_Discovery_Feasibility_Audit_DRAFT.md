# S3 D3 Native SDF Resource-Discovery Feasibility Audit

Status: `DRAFT — READ-ONLY RESOURCE-DISCOVERY AUDIT — NO RUNTIME APPROVAL`

## Scope and decision boundary

This audit determines only whether the camera and LiDAR mesh files already
installed by `ROBOT_URDF_final_description` have an evidence-backed native-SDF
resource lookup path. It makes no source, package, launch, model, checker,
world, guard, or artifact change. It does not build, run Gazebo/ROS/`gz`, spawn,
bridge, call `RequestRaw`, issue a command/control action, or touch hardware.

The result is a static resource-lookup feasibility result. It does not prove
Gazebo renders a mesh, creates collision geometry, resolves a material, spawns
the model, publishes a sensor, or produces raw Contacts.

## 1. Version-matched authority

| Authority | Evidence used | What it establishes | Limit |
| --- | --- | --- | --- |
| Installed SDFormat 1.11 [`geometry.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/geometry.sdf) and [`mesh_shape.sdf`](/opt/ros/jazzy/opt/sdformat_vendor/share/sdformat14/1.11/mesh_shape.sdf) | `geometry` includes the mesh shape; `mesh/uri` is a required string. | A native `<geometry><mesh><uri>` is structurally valid. | The schema does not select a Gazebo resource root. |
| Official Gazebo Sim 8 [Finding resources](https://gazebosim.org/api/sim/8/resources.html) | Mesh URIs are searched from the current path/absolute path and paths on `GZ_SIM_RESOURCE_PATH`; `GZ_FILE_PATH` is not recommended. | A relative mesh resource path can be resolved from an explicit `GZ_SIM_RESOURCE_PATH` entry. | Actual loader success remains runtime evidence. |
| Installed Jazzy [`gz_sim.launch.py`](/opt/ros/jazzy/share/ros_gz_sim/launch/gz_sim.launch.py) | It preserves incoming `GZ_SIM_RESOURCE_PATH` while composing Gazebo's launch environment. | An explicit path set by the dedicated launch is part of the future Gazebo process environment. | It does not prove an individual mesh will load. |
| Current dedicated launch [`typed_scene_observer.launch.py`](../ros2_ws/src/ROBOT_URDF_final_description/launch/typed_scene_observer.launch.py) | It sets `GZ_SIM_RESOURCE_PATH` to `dirname(get_package_share_directory('ROBOT_URDF_final_description'))`, then preserves prior entries. | With the installed package share, the resource root is `/home/hazan/mecanum_autonomy_ws/ros2_ws/install/ROBOT_URDF_final_description/share`. | This route is not approved to launch. |

The installed Sim 8 documentation does not prove that the current package
layout supports `model://ROBOT_URDF_final/meshes/<file>`. Under the actual
layout, the named model is at `.../share/ROBOT_URDF_final_description/models/ROBOT_URDF_final`, while the meshes are siblings at `.../share/ROBOT_URDF_final_description/meshes`. Therefore this audit does **not** propose a `model://` URI.

## 2. Source inventory

The source Xacro uses ROS/Xacro substitution syntax, not a native SDF resource
contract:

| Link | Xacro visual mesh URI | Xacro collision mesh URI | Source file type | Source SHA-256 | Texture/material dependency |
| --- | --- | --- | --- | --- | --- |
| `IntelRealsense_D435_Multibody_1` | `file://$(find ROBOT_URDF_final_description)/meshes/IntelRealsense_D435_Multibody_1.stl` | Same URI | regular STL | `9d4cb148982e636605a0185a4e83bb6dbf3cbf00960fbcaf3ff7bbb3de3172ed` | URDF color material `camera_white`; no texture, `.mtl`, `.dae`, or image file exists in the package inventory. |
| `RPLiDAR_A1M8_1` | `file://$(find ROBOT_URDF_final_description)/meshes/RPLiDAR_A1M8_1.stl` | No mesh: source collision is a primitive cylinder. | regular STL | `4f34e4b5f83644cbab92574f0c1b6f258a8f73af75baf32213bb55d41d29a7ea` | URDF color material `black`; no texture, `.mtl`, `.dae`, or image file exists in the package inventory. |

`file://$(find ...)` is a ROS/Xacro expression and is neither retained nor
claimed here as a native SDF URI.

## 3. Installed-package inventory

S3.3.65 installed both files as regular files, with byte-identical content:

| Resource | Installed path relative to package share | Installed SHA-256 | Source/install parity |
| --- | --- | --- | --- |
| Camera STL | `ROBOT_URDF_final_description/meshes/IntelRealsense_D435_Multibody_1.stl` | `9d4cb148982e636605a0185a4e83bb6dbf3cbf00960fbcaf3ff7bbb3de3172ed` | Exact |
| LiDAR STL | `ROBOT_URDF_final_description/meshes/RPLiDAR_A1M8_1.stl` | `4f34e4b5f83644cbab92574f0c1b6f258a8f73af75baf32213bb55d41d29a7ea` | Exact |

The package also installs native `model.config` and `model.sdf` beneath
`ROBOT_URDF_final_description/models/ROBOT_URDF_final`, but there is no
`meshes/` directory inside that model directory. No texture or external
material resource was found in source or install space for these two STL files.

## 4. Native-SDF lookup analysis

The dedicated launch's explicit resource root is the parent of package shares:

```text
GZ_SIM_RESOURCE_PATH entry
= .../install/ROBOT_URDF_final_description/share

candidate URI path
= ROBOT_URDF_final_description/meshes/<mesh-file>.stl

resolved installed file
= .../share/ROBOT_URDF_final_description/meshes/<mesh-file>.stl
```

This is an evidence-backed candidate because the Sim 8 resource contract
searches mesh URI paths under `GZ_SIM_RESOURCE_PATH`, and each complete
candidate path exists as an installed regular file. It does not rely on current
working directory, a source-tree absolute path, ROS `$(find ...)`, a bridge, or
network/Fuel lookup.

| Resource | Native SDF candidate URI path | Static prerequisites evidenced | Decision | Runtime-only unknown |
| --- | --- | --- | --- | --- |
| Camera visual mesh | `ROBOT_URDF_final_description/meshes/IntelRealsense_D435_Multibody_1.stl` | Installed regular file with matching SHA; dedicated launch resource root is its parent share directory; SDFormat 1.11 accepts mesh `uri`. | `RESOLVABLE_FROM_INSTALLED_PACKAGE` | Gazebo mesh-loader/rendering success; visual pose/scale semantics; collision geometry behavior if a future approved design adds a mesh collision. |
| LiDAR visual mesh | `ROBOT_URDF_final_description/meshes/RPLiDAR_A1M8_1.stl` | Installed regular file with matching SHA; same resource root and schema evidence. | `RESOLVABLE_FROM_INSTALLED_PACKAGE` | Gazebo mesh-loader/rendering success and visual pose/scale semantics. Existing source LiDAR collision is primitive and remains a separate parity decision. |
| `model://ROBOT_URDF_final/meshes/...` for either mesh | No candidate proposed | The installed model directory lacks a `meshes/` child, and the configured resource root is not the parent of `models/ROBOT_URDF_final`. | `OFFICIAL_CONTRACT_UNRESOLVED` for this layout/URI combination | A different package layout plus an approved resource-root contract would need separate design evidence. |

## 5. Smallest bounded follow-up implementation

The evidence supports exactly one next source file if visual resource parity is
separately approved:

```text
ros2_ws/src/ROBOT_URDF_final_description/models/ROBOT_URDF_final/model.sdf
```

Its scope would be limited to native SDF **visual** geometry for the two links,
using the two package-relative candidate URI paths above and the existing
source pose/scale literals only after an explicit field-level review. It would
not change package layout, `setup.py`, model identity, ContactSensor, collision
policy, plugins, launch, bridge, ROS topology, or runtime authority. Camera
mesh collision and LiDAR collision remain distinct decisions and are not
approved by this feasibility audit.

## 6. Conclusion

```text
READY_FOR_ONE_FILE_RESOURCE_PARITY_IMPLEMENTATION
```

The two required STL files exist in source and install space with exact matching
SHA-256 values. The dedicated launch's explicit resource root and the official
Gazebo Sim 8 mesh lookup contract provide a deterministic package-relative
native SDF lookup path. Runtime resolution, rendering, physics, collision,
sensor behavior, raw Contacts, ContactLatch, reward/termination, Gym/training,
and hardware readiness remain unproven.
