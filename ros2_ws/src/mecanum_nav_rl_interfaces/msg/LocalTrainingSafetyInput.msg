uint16 SCHEMA_VERSION=1

uint8 ODOM_VALID=0
uint8 ODOM_DELAYED=1
uint8 ODOM_DROPPED=2

uint8 ADMISSION_INHIBITED=0
uint8 ADMISSION_ZERO_ONLY=1
uint8 ADMISSION_POLICY_OPEN=2

std_msgs/Header header
uint16 schema_version
string<=64 session_id
string<=64 config_hash

uint64 ingress_instance_id
uint64 sample_sequence
uint64 episode_generation
uint32 reset_epoch
uint32 runtime_generation

uint8 odometry_status
float64[<=3] measured_twist

uint8 admission_state
builtin_interfaces/Time observation0_cutoff
uint64 observation0_final_publisher_instance_id
uint64 observation0_final_publish_sequence
