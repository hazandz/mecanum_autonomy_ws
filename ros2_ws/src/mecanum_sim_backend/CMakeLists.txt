cmake_minimum_required(VERSION 3.16)
project(mecanum_sim_backend LANGUAGES CXX)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(ament_cmake REQUIRED)
find_package(gz-sim8 REQUIRED)
find_package(gz-msgs10 REQUIRED)
find_package(gz-transport13 REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(ros_gz_interfaces REQUIRED)
find_package(ament_index_cpp REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(mecanum_nav_rl_interfaces REQUIRED)

add_library(mecanum_sim_backend_core SHARED
  src/receipt_gate.cpp
  src/contact_coverage.cpp)
target_include_directories(mecanum_sim_backend_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_options(mecanum_sim_backend_core PRIVATE -Wall -Wextra -Wpedantic)

add_library(mecanum_sim_backend_system SHARED src/backend_system.cpp)
target_include_directories(mecanum_sim_backend_system PRIVATE include)
ament_target_dependencies(mecanum_sim_backend_system
  rclcpp nav_msgs geometry_msgs ros_gz_interfaces ament_index_cpp
  mecanum_nav_rl_interfaces)
target_link_libraries(mecanum_sim_backend_system
  mecanum_sim_backend_core gz-sim8::gz-sim8 gz-msgs10::gz-msgs10
  gz-transport13::gz-transport13 OpenSSL::Crypto)
target_compile_options(mecanum_sim_backend_system PRIVATE -Wall -Wextra -Wpedantic)

install(TARGETS mecanum_sim_backend_core mecanum_sim_backend_system
  ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)
ament_environment_hooks(env-hooks/mecanum_sim_backend.dsv.in)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_receipt_gate test/test_receipt_gate.cpp)
  target_link_libraries(test_receipt_gate mecanum_sim_backend_core)
  ament_add_gtest(test_contact_coverage test/test_contact_coverage.cpp)
  target_link_libraries(test_contact_coverage mecanum_sim_backend_core)
  ament_add_gtest(test_backend_invariants test/test_backend_invariants.cpp)
  ament_target_dependencies(test_backend_invariants
    rclcpp nav_msgs geometry_msgs ros_gz_interfaces ament_index_cpp
    mecanum_nav_rl_interfaces)
  target_link_libraries(test_backend_invariants
    mecanum_sim_backend_core gz-sim8::gz-sim8 gz-msgs10::gz-msgs10
    gz-transport13::gz-transport13 OpenSSL::Crypto)
endif()

ament_export_include_directories(include)
ament_export_libraries(mecanum_sim_backend_core)
ament_package()
