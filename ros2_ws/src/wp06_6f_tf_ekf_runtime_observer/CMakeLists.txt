cmake_minimum_required(VERSION 3.8)
project(wp06_6f_tf_ekf_runtime_observer)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(rosgraph_msgs REQUIRED)
find_package(tf2_msgs REQUIRED)
find_package(nlohmann_json REQUIRED)

add_executable(wp06_6f_tf_ekf_runtime_observer
  src/wp06_6f_tf_ekf_runtime_observer.cpp
)
target_compile_features(wp06_6f_tf_ekf_runtime_observer PUBLIC cxx_std_17)
target_link_libraries(wp06_6f_tf_ekf_runtime_observer nlohmann_json::nlohmann_json)
ament_target_dependencies(wp06_6f_tf_ekf_runtime_observer
  geometry_msgs rclcpp nav_msgs rosgraph_msgs tf2_msgs
)
install(TARGETS wp06_6f_tf_ekf_runtime_observer
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_wp06_6f_tf_ekf_runtime_observer
    test/test_wp06_6f_tf_ekf_runtime_observer.cpp
  )
  target_compile_features(test_wp06_6f_tf_ekf_runtime_observer PUBLIC cxx_std_17)
  target_link_libraries(test_wp06_6f_tf_ekf_runtime_observer nlohmann_json::nlohmann_json)
  ament_target_dependencies(test_wp06_6f_tf_ekf_runtime_observer
    geometry_msgs rclcpp nav_msgs rosgraph_msgs tf2_msgs
  )
endif()

ament_package()
