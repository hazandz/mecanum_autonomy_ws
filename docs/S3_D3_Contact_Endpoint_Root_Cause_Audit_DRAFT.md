# S3 D3 — Contact Endpoint Root-Cause Audit

**Status: DRAFT — READ-ONLY ROOT-CAUSE AUDIT — NO RUNTIME APPROVAL**

## Scope and evidence boundary

This audit reconstructs the S3.3.17 failure of the expected Gazebo Transport endpoint `/s3_d3/contact/raw` using only current source, retained run evidence, and locally installed Gazebo Sim 8 examples and headers. It does not modify the robot description, world, launch, bridge, collector, guard, or retained artifacts. It does not run Gazebo, ROS, `gz`, a bridge, a collector, a service, or a command path.

The retained run is [`run-contact-replacement-20260926T153527Z-01`](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/). Its classification was `INVALID` at the GZ raw-endpoint preflight; the temporary bridge and collector did not start. The result does not establish a collision outcome, ContactLatch behavior, collision policy, reward, termination, Gym/training behavior, or hardware behavior.

## 1. Evidence chain: source to the proposed bridge endpoint

| Layer | Status | Direct evidence | What this does and does not establish |
| --- | --- | --- | --- |
| A. Source literal exists | `CONFIRMED` | [`ROBOT_URDF_final.xacro`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.xacro) names the existing `base_link` box collision `s3_d3_base_contact_collision`; [`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo) contains one `sensor` named `s3_d3_base_contact_sensor`, type `contact`, target collision literal, and topic `/s3_d3/contact/raw`; [`tugbot_depot.sdf`](../ros2_ws/src/ROBOT_URDF_final_description/launch/tugbot_depot.sdf) declares one `gz::sim::systems::Contact` plugin. | The approved literals are present in current source. Source presence alone does not prove conversion, spawn, sensor creation, or publication. |
| B. Xacro render preserves ContactSensor/literal | `CONFIRMED` | The run's [`static_robot_validation.json`](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/static_robot_validation.json) records successful Xacro rendering and counts one sensor, one sensor topic, one target collision, and the approved literals. | The rendered robot-description input preserves the extension. Xacro validity is not evidence that the Gazebo-spawned SDF/entity retained it. |
| C. Spawn / URDF-to-SDF conversion preserves sensor | `INSUFFICIENT_EVIDENCE` | The retained artifact contains rendered-Xacro validation, but no captured final spawned SDF, Gazebo entity-component inspection, or sensor-creation log for `s3_d3_base_contact_sensor`. | The conversion/spawn boundary was not observed. Neither success of Xacro nor the absence of an endpoint can identify what the spawned entity contains. |
| D. Gazebo loads Contact system successfully | `CONFIRMED` | [`gazebo_launch.log`](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/logs/gazebo_launch.log) line 41 records `Loaded system [gz::sim::systems::Contact] for entity [1]`. | The world-level Contact system loaded in this run. It does not prove a robot ContactSensor was created or that a specific sensor endpoint exists. |
| E. Gazebo creates ContactSensor entity | `INSUFFICIENT_EVIDENCE` | No retained log line, component/entity listing, or sensor registration record names `s3_d3_base_contact_sensor`. | This layer was not measured. It must not be inferred either from the world Contact-system load or from the configured source literal. |
| F. Gazebo publishes the requested GZ `Contacts` endpoint | `CONTRADICTED` | The retained [`gz_topic_info.log`](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/logs/gz_topic_info.log), produced by passive `gz topic -l`, does not list `/s3_d3/contact/raw`. [`run_result.json`](../artifacts/simulation/contact_producer_evidence/run-contact-replacement-20260926T153527Z-01/run_result.json) consequently records `gz_topic` preflight failure. | The requested endpoint was absent from that runtime listing. This is a failure before bridge startup and before collector startup. It does not prove that no physical/simulated contact existed. |
| G. Endpoint name/type matches the bridge candidate | `NOT_OBSERVED` | Because layer F did not expose `/s3_d3/contact/raw`, the required runtime type `gz::msgs::Contacts` could not be queried or verified, and no one-topic bridge was started. | The installed type conversion is only static feasibility; no matching live endpoint/type was observed. |

The preflight order matters: a missing GZ endpoint stops the run before the temporary GZ-to-ROS bridge and before the ROS collector. It is therefore not a bridge-delivery or collector-subscription failure.

## 2. Current project syntax compared with local Gazebo Sim 8 evidence

The installed Gazebo Sim 8 example [`contact_sensor.sdf`](/opt/ros/jazzy/opt/gz_sim_vendor/share/gz/gz-sim8/worlds/contact_sensor.sdf) provides the local reference pattern:

```xml
<plugin filename="gz-sim-contact-system" name="gz::sim::systems::Contact"/>
...
<link name="link">
  <collision name="collision_sphere">...</collision>
  <sensor name="sensor_contact" type="contact">
    <contact>
      <collision>collision_sphere</collision>
      <topic>/contact_example</topic>
    </contact>
    <always_on>1</always_on>
    <update_rate>100</update_rate>
  </sensor>
</link>
```

| Aspect | Current project source | Local installed example / header evidence | Audit consequence |
| --- | --- | --- | --- |
| Contact system placement | World scope in `tugbot_depot.sdf`, using `gz-sim-contact-system` and `gz::sim::systems::Contact`. | The local example uses the same plugin filename/name at world scope. The S3.3.17 log also confirms load. | No observed mismatch at the world-system layer. |
| Sensor placement | A URDF/Xacro Gazebo extension under `<gazebo reference="base_link">` in `ROBOT_URDF_final.gazebo`. | The local example is native SDF: the contact sensor is nested directly under a concrete `<link>`. | This is a real representation-path difference. Local static evidence does not prove that this project's URDF-to-SDF/spawn path preserves the extension as a Gazebo ContactSensor. |
| Sensor fields | `type="contact"`, approved sensor name, `<contact><collision>...<topic>/s3_d3/contact/raw</topic></contact>`, and `<always_on>true</always_on>`. | The local example uses the same `type`, `contact/collision/topic`, and `always_on` structure; it also sets `update_rate`. | The basic field shape is locally evidenced, but no runtime observation proves the project conversion accepts the extension or publishes this endpoint. The absence of `update_rate` is not assigned causal meaning by this audit. |
| Collision target | Named `base_link` box collision literal in Xacro. | The example refers to a collision local to its SDF link. | The configured literal survives Xacro, but resolution against the spawned link/collision is unobserved. |
| Topic syntax and scope | Absolute literal `/s3_d3/contact/raw`. | The local example uses an absolute `/contact_example` literal. | An absolute topic literal is locally exemplified. Static evidence does not establish the final runtime scope, advertised name, or whether this extension reaches sensor creation. |
| Payload type | Proposed `gz::msgs::Contacts` and GZ-to-ROS conversion. | Installed Gazebo headers include `contactsensor.pb.h`; the prior static audit records installed `contacts.proto` and `ros_gz_bridge` conversion declarations. | Type support is installed, but it is not proof of a project producer or endpoint. |

The comparison does not authorize a source change. In particular, it does not establish the runtime scoped name of the sensor, an endpoint naming rule, timestamp population, duplicate behavior, or an action-interval/contact provenance contract.

## 3. Interpretation limits

- A successful Xacro render is not evidence that Gazebo spawn or URDF-to-SDF conversion retained the contact sensor.
- The absent `/s3_d3/contact/raw` listing is not evidence that the robot did not collide; this passive run did not classify collision and did not create a ContactLatch.
- The absent endpoint is upstream of the bridge and collector. The S3.3.17 bridge/collector did not start, so their behavior is not implicated by this run.
- The loaded Contact system proves only the world-level system-load layer. It does not prove sensor entity creation, collision-target resolution, or producer publication.

## 4. Ranked hypotheses — not root-cause findings

| Rank | Suspected layer / hypothesis | Evidence supporting | Evidence against or limiting | Missing evidence | Verification in one future approved run |
| --- | --- | --- | --- | --- | --- |
| 1 | URDF/Xacro Gazebo-extension to spawned-SDF conversion did not retain or instantiate the contact sensor in a form recognized by Gazebo Sensors/Contact. | The local working example places a native SDF contact sensor directly beneath a link; the project uses a URDF `<gazebo reference>` extension. Layers A and B pass, while E and F are unobserved/absent. | No generated spawned SDF or entity-component evidence was captured, so this is not a root-cause conclusion. | Converted/spawned SDF and direct evidence of the sensor component/entity. | Capture the post-spawn converted description or read-only entity/sensor-component evidence before endpoint preflight, then record the discovered endpoint/type without sending commands or control actions. |
| 2 | The named collision target is not resolved against the spawned `base_link` collision identity. | The target is asserted only at source/Xacro layers; there is no Gazebo-side collision-component evidence. | The current collision literal is explicit and source validation passed. | Spawned link/collision identity and the sensor's resolved target. | In a future approved passive run, collect Gazebo-side sensor/collision entity identity evidence and compare it losslessly to the configured literal. |
| 3 | The endpoint is emitted under a different scoped/name rule, or the configured `<topic>` is not honored on this conversion path. | The exact requested absolute topic is absent; final runtime topic derivation was never observed. | The local native-SDF example also uses an absolute topic literal, so the literal itself is not statically contradicted. | Sensor creation plus its runtime advertised topic/type. | After proving sensor creation, passively enumerate Gazebo endpoints and query their types; do not infer names from source alone. |
| 4 | Contact-system load succeeded but its interaction with this sensor configuration requires additional runtime conditions before advertising. | The system is confirmed loaded, but no sensor endpoint is listed. | Local source/example in this audit does not establish an activation/advertisement rule for this exact stack; no collision/contact was induced or classified. | Local implementation semantics or approved runtime evidence of contact-sensor advertisement behavior. | A future approved passive evidence design must explicitly state what it observes and avoid treating an idle trace as proof of absence of contact. |
| 5 | Contact-system load failed. | None. | The launch log explicitly reports successful loading of `gz::sim::systems::Contact`. | None needed for this layer. | Not a leading verification target; retain the load-log gate in any future run. |

## 5. Smallest correction candidate — design only

**REQUIRES_USER_APPROVAL — DO NOT IMPLEMENT.** The smallest candidate is to re-express the one approved ContactSensor at the robot description's conversion-supported, native SDF link scope, rather than relying on the current URDF `<gazebo reference="base_link">` extension. The likely implementation surface is [`ROBOT_URDF_final.gazebo`](../ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo); the exact representation and location must first be selected from conversion evidence, not guessed from this audit.

| Item | Candidate scope | Risk and required validation |
| --- | --- | --- |
| Potential file | `ros2_ws/src/ROBOT_URDF_final_description/urdf/ROBOT_URDF_final.gazebo` | It can alter URDF-to-SDF conversion behavior. Approval must constrain the change to the one existing approved collision/sensor purpose and preserve existing geometry, inertial, visual, motor, and motion-plugin behavior. |
| Potential correction | Represent exactly one contact sensor in a conversion-supported native SDF link scope for the existing named base collision. | Do not duplicate the sensor or create a second collision. Validate rendered output, final spawned-SDF/entity evidence, exact GZ topic/type, one-way bridge behavior, and a new approved passive run. |
| Explicitly excluded | ContactLatch, collision filters, terminal/reward behavior, action barriers, reset semantics, and official runtime topic contract. | None may be inferred from endpoint creation or raw payload delivery. |

This candidate is deliberately conditional. If future evidence instead proves that the current conversion retains the sensor and resolves the collision, the candidate must be re-evaluated rather than applied.

## Conclusion

**BLOCKED_BY_CONTACT_ENDPOINT_ROOT_CAUSE**

The source literals, Xacro render, and world-level Contact-system load are confirmed. The requested GZ endpoint was absent, which prevented type verification and stopped the run before bridge/collector startup. The audit has not established whether the cause is conversion/spawn retention, collision-target resolution, runtime topic derivation, or sensor-advertisement behavior. A new, narrowly approved diagnostic/passive evidence design is required before any correction or another run.
