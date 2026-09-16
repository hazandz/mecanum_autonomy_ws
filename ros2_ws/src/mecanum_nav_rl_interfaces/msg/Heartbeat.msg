# Nguồn phát heartbeat
uint8 SOURCE_UNKNOWN=0
uint8 SOURCE_POLICY=1
uint8 SOURCE_MCU=2

# Không có lỗi
uint32 FAULT_NONE=0

# Lỗi chung: có thể xảy ra với AI hoặc MCU
uint32 FAULT_TRANSPORT=1
uint32 FAULT_ESTOP_ACTIVE=2

# Lỗi chỉ thuộc AI / PolicyNode
uint32 FAULT_POLICY_INFERENCE=4
uint32 FAULT_POLICY_COMMAND_INVALID=8
uint32 FAULT_POLICY_CONTROL_LOOP=16
uint32 FAULT_POLICY_MODEL_CONTRACT=32

# Lỗi chỉ thuộc STM32 / MCU bridge
uint32 FAULT_MCU_COMMAND_TIMEOUT=256
uint32 FAULT_MCU_COMMAND_INVALID=512
uint32 FAULT_MCU_CONTROL_LOOP=1024
uint32 FAULT_MOTOR_DRIVER=2048
uint32 FAULT_ENCODER=4096
uint32 FAULT_IMU=8192

# Thông tin heartbeat
std_msgs/Header header
uint8 source
uint32 sequence
uint32 reset_epoch
bool healthy
uint32 fault_bits
string detail
