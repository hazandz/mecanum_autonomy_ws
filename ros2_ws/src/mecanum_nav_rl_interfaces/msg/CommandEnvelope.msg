uint8 SOURCE_UNKNOWN=0
uint8 SOURCE_POLICY=1
uint8 SOURCE_NAV2=2
uint8 SOURCE_TELEOP=3
uint8 SOURCE_SAFE_STOP=4

std_msgs/Header header
uint8 source
uint64 sequence
uint32 reset_epoch
uint32 runtime_generation
uint64 source_instance_id
geometry_msgs/Twist twist
