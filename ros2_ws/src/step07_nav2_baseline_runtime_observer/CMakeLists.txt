cmake_minimum_required(VERSION 3.8)
project(step07_nav2_baseline_runtime_observer)
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rosgraph_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(mecanum_nav_rl_interfaces REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(OpenSSL REQUIRED)
add_executable(step07_nav2_baseline_runtime_observer
  src/step07_nav2_baseline_runtime_observer.cpp
  src/lifecycle_ingress.cpp)
ament_target_dependencies(step07_nav2_baseline_runtime_observer rclcpp rosgraph_msgs sensor_msgs nav_msgs tf2_msgs mecanum_nav_rl_interfaces)
target_link_libraries(step07_nav2_baseline_runtime_observer nlohmann_json::nlohmann_json OpenSSL::Crypto)
target_include_directories(step07_nav2_baseline_runtime_observer PRIVATE include)
install(TARGETS step07_nav2_baseline_runtime_observer DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_step07_nav2_baseline_runtime_observer
    test/test_step07_nav2_baseline_runtime_observer.cpp
    test/test_lifecycle_ingress.cpp
    src/lifecycle_ingress.cpp)
  ament_target_dependencies(test_step07_nav2_baseline_runtime_observer rclcpp rosgraph_msgs sensor_msgs nav_msgs tf2_msgs mecanum_nav_rl_interfaces)
  target_link_libraries(test_step07_nav2_baseline_runtime_observer nlohmann_json::nlohmann_json OpenSSL::Crypto)
  target_include_directories(test_step07_nav2_baseline_runtime_observer PRIVATE include)
  target_compile_definitions(test_step07_nav2_baseline_runtime_observer PRIVATE
    STEP07_RL_PYTHON_SOURCE="${CMAKE_CURRENT_SOURCE_DIR}/../mecanum_nav_rl"
    STEP07_REPOSITORY_ROOT="${CMAKE_CURRENT_SOURCE_DIR}/../../.."
    STEP07_RUN005_RUNNER="${CMAKE_CURRENT_SOURCE_DIR}/../../../artifacts/simulation/step07_nav2_baseline_campaign/tools/run_step07_nav2_baseline_run005.py")
endif()
ament_package()
