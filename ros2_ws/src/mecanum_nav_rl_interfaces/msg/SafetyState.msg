# Trạng thái vận hành cuối cùng của safety runtime
uint8 STATE_INIT=0
uint8 STATE_NORMAL=1
uint8 STATE_LIMITED=2
uint8 STATE_STOPPED=3
uint8 STATE_ESTOPPED=4
uint8 STATE_FAULT=5

# Nguồn hoặc nguyên nhân tạo ra lệnh cuối cùng
uint8 COMMAND_SOURCE_NONE=0
uint8 COMMAND_SOURCE_POLICY=1
uint8 COMMAND_SOURCE_NAV2=2
uint8 COMMAND_SOURCE_TELEOP=3
uint8 COMMAND_SOURCE_SAFE_STOP=4
uint8 COMMAND_SOURCE_ESTOP=5

# Trạng thái public do SafetySupervisor publish
std_msgs/Header header
uint8 state
uint32 reset_epoch
uint32 runtime_generation

uint8 active_command_source
bool command_valid

bool scan_fresh
bool odom_fresh
bool tf_valid
bool localization_valid
bool navigation_state_fresh
bool path_valid
bool motion_permitted
bool policy_alive
bool mcu_alive
bool estop_active

uint32 scan_age_ms
uint32 odom_age_ms
uint32 policy_heartbeat_age_ms
uint32 mcu_heartbeat_age_ms
uint32 command_age_ms
uint32 navigation_state_age_ms

uint32 fault_bits
string[] intervention_reasons

geometry_msgs/Twist raw_command
geometry_msgs/Twist limited_command
geometry_msgs/Twist final_command
