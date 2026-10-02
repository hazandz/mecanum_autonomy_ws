cmake_minimum_required(VERSION 3.8)

project(mecanum_nav_rl_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Heartbeat.msg"
  "msg/SafetyState.msg"
  "msg/NavigationState.msg"
  "msg/CommandEnvelope.msg"
  DEPENDENCIES
    std_msgs
    geometry_msgs
)

ament_export_dependencies(rosidl_default_runtime)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_interface_contracts
    test/test_interface_contracts.py
  )
endif()

ament_package()
