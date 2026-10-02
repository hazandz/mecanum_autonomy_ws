cmake_minimum_required(VERSION 3.22)
project(s3_d3_ecs_contact_diagnostic)

find_package(ament_cmake REQUIRED)
find_package(Protobuf REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(gz-sim8 8.11.0 EXACT REQUIRED)
find_package(gz-transport13 13.5.0 EXACT REQUIRED)
find_package(gz-msgs10 10.3.2 EXACT REQUIRED)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
protobuf_generate_cpp(RECEIPT_PROTO_SRCS RECEIPT_PROTO_HDRS
  proto/ecs_contact_sensor_diagnostic_receipt.proto)

add_library(s3_d3_ecs_contact_diagnostic_core STATIC
  src/core.cc src/run_spec.cc ${RECEIPT_PROTO_SRCS} ${RECEIPT_PROTO_HDRS})
set_target_properties(s3_d3_ecs_contact_diagnostic_core PROPERTIES
  POSITION_INDEPENDENT_CODE ON)
target_include_directories(s3_d3_ecs_contact_diagnostic_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
  $<INSTALL_INTERFACE:include>)
target_link_libraries(s3_d3_ecs_contact_diagnostic_core PUBLIC
  protobuf::libprotobuf OpenSSL::Crypto)
target_compile_options(s3_d3_ecs_contact_diagnostic_core PRIVATE -Wall -Wextra -Werror)

add_library(s3_d3_ecs_contact_diagnostic_collector STATIC src/collector.cc)
target_include_directories(s3_d3_ecs_contact_diagnostic_collector PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>)
target_link_libraries(s3_d3_ecs_contact_diagnostic_collector PUBLIC
  s3_d3_ecs_contact_diagnostic_core gz-transport13::gz-transport13 gz-msgs10::gz-msgs10)
target_compile_options(s3_d3_ecs_contact_diagnostic_collector PRIVATE -Wall -Wextra -Werror)

add_library(s3_d3_ecs_contact_diagnostic_system SHARED src/system.cc)
set_target_properties(s3_d3_ecs_contact_diagnostic_system PROPERTIES
  OUTPUT_NAME S3D3EcsContactSensorDiagnosticSystem)
target_include_directories(s3_d3_ecs_contact_diagnostic_system PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include ${CMAKE_CURRENT_BINARY_DIR})
target_link_libraries(s3_d3_ecs_contact_diagnostic_system PRIVATE
  s3_d3_ecs_contact_diagnostic_core gz-sim8::gz-sim8
  gz-transport13::gz-transport13 gz-msgs10::gz-msgs10)
target_compile_options(s3_d3_ecs_contact_diagnostic_system PRIVATE -Wall -Wextra -Werror)

add_executable(s3_d3_ecs_contact_diagnostic_collector_main src/collector_main.cc)
target_link_libraries(s3_d3_ecs_contact_diagnostic_collector_main PRIVATE
  s3_d3_ecs_contact_diagnostic_collector)
target_compile_options(s3_d3_ecs_contact_diagnostic_collector_main PRIVATE -Wall -Wextra -Werror)

add_executable(s3_d3_ecs_contact_diagnostic_world_renderer src/world_renderer_main.cc)
target_link_libraries(s3_d3_ecs_contact_diagnostic_world_renderer PRIVATE s3_d3_ecs_contact_diagnostic_core)
target_compile_options(s3_d3_ecs_contact_diagnostic_world_renderer PRIVATE -Wall -Wextra -Werror)

install(TARGETS s3_d3_ecs_contact_diagnostic_system
  LIBRARY DESTINATION lib)
install(TARGETS s3_d3_ecs_contact_diagnostic_collector_main s3_d3_ecs_contact_diagnostic_world_renderer
  RUNTIME DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include)
install(FILES proto/ecs_contact_sensor_diagnostic_receipt.proto DESTINATION share/${PROJECT_NAME}/proto)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  ament_add_gtest(test_core test/test_core.cc)
  target_include_directories(test_core PRIVATE ${CMAKE_CURRENT_BINARY_DIR})
  target_link_libraries(test_core s3_d3_ecs_contact_diagnostic_core s3_d3_ecs_contact_diagnostic_collector)
  add_test(NAME test_static_contract
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test/test_static_contract.py
      ${CMAKE_CURRENT_SOURCE_DIR})
endif()

ament_package()
