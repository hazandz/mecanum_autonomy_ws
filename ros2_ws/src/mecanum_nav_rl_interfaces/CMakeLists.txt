cmake_minimum_required(VERSION 3.8)

project(mecanum_nav_rl_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Heartbeat.msg"
  "msg/SafetyState.msg"
  "msg/NavigationState.msg"
  "msg/CommandEnvelope.msg"
  "msg/FinalIssuedCommandReceipt.msg"
  "msg/SafetyLifecycleState.msg"
  "msg/LocalTrainingSafetyInput.msg"
  "msg/SimulationContactState.msg"
  DEPENDENCIES
    std_msgs
    geometry_msgs
    builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_interface_contracts
    test/test_interface_contracts.py
  )
  ament_add_pytest_test(test_final_issued_command_receipt_rosidl_enablement
    test/test_final_issued_command_receipt_rosidl_enablement.py
  )
  ament_add_pytest_test(test_safety_lifecycle_state_interface
    test/test_safety_lifecycle_state_interface.py
  )
  ament_add_pytest_test(test_local_training_interfaces
    test/test_local_training_interfaces.py
  )
endif()

ament_package()
