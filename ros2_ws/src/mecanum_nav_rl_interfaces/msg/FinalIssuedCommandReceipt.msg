# Canonical receipt v2 interface: mecanum.final-issued-receipt/v2.
# ROSIDL generation is enabled; this does not claim runtime or Gate B acceptance.
uint8 SOURCE_UNKNOWN=0
uint8 SOURCE_POLICY=1
uint8 SOURCE_NAV2=2
uint8 SOURCE_TELEOP=3
uint8 SOURCE_SAFE_STOP=4

std_msgs/Header header
uint64 episode_generation
uint32 reset_epoch
uint32 runtime_generation
uint64 step_index
string<=36 transition_id
uint8 source
uint64 sequence
uint64 source_instance_id
uint64 final_publisher_instance_id
uint64 final_publish_sequence
geometry_msgs/Twist final_command
