# mecanum_sim_backend

Native Gazebo Sim 8 plugin and pure C++ receipt/contact contracts for the
Owner-approved Roadmap B B2.2 offline implementation. The actuator is inhibited
until a fresh, bound SAFE_STOP receipt anchors the final publication sequence.
Receipt-v2 is the only actuator carrier; `/cmd_vel` is captured for evidence
and is never applied by this package.

The `Link::SetLinearVelocity` and `Link::SetAngularVelocity` APIs in the
installed Gazebo Sim 8.11.0 headers explicitly take values in the Link frame.
The body-motion surrogate therefore rotates measured world twist into the
body frame using the measured orientation, replaces only body vx/vy/wz, and
preserves the measured vertical and roll/pitch components. Missing measurement
is a fault; emergency zero is explicitly marked as local override and has no
receipt key.

This package does not implement B2.3 POLICY issuance, Safety runtime,
FinalTwistPublisher, observation0 commit, or explicit rearm. It cannot prove
contact-engine capability offline; a real contact observation must establish
the controlled probe outcome before coverage can be healthy. The plugin's
initial state is inhibited.

The offline launch contract accepts `gui:=true|false`. With GUI enabled it
starts one Gazebo server and a GUI-only client against the same partition and
world. These command examples are design documentation only and were not run:

```bash
ros2 launch mecanum_nav_bringup sim_train_local_training.launch.py \
  gui:=true resolved_config:=/ABS/PATH/TO/verified_training.resolved.json
```

```bash
ros2 launch mecanum_nav_bringup sim_train_local_training.launch.py \
  gui:=false resolved_config:=/ABS/PATH/TO/verified_training.resolved.json
```

This source/build/test package is not evidence that a simulator, sensor,
contact system, reset, GUI, actuator, stop envelope, training job, or robot has
run successfully. Runtime remains unauthorized pending exact audit and a
separate capacity-one runtime authorization.
