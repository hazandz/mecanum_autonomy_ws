# Lifecycle identity and explicit action/reset readiness barrier.
uint8 PRIMARY_UNCONFIGURED=0
uint8 PRIMARY_INACTIVE=1
uint8 PRIMARY_ACTIVE=2
uint8 BARRIER_INIT=0
uint8 BARRIER_READY=1
uint8 BARRIER_NON_READY=2
uint8 BARRIER_FAULT=3

std_msgs/Header header
uint64 episode_generation
uint32 reset_epoch
uint32 runtime_generation
uint64 sequence
uint8 primary_state
uint8 barrier_state
builtin_interfaces/Time barrier_stamp
bool motion_permitted
string reason
