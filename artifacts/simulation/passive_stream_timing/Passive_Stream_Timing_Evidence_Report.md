# Passive Stream Timing Evidence Report

Status labels: OBSERVED, CANDIDATE_FOR_FUTURE_DECISION, PROPOSED_FROM_MEASUREMENT, NOT_ESTABLISHED.

## Run validity — OBSERVED

| run_id | status | invalid_reasons | cmd_vel_change |
| --- | --- | --- | --- |
| run-20260924T154000Z-01 | INVALID | cmd_vel publisher allowlist changed during run | True |
| run-20260924T155000Z-02 | VALID | - | False |
| run-20260924T155300Z-03 | VALID | - | False |
| run-20260924T155600Z-04 | VALID | - | False |
| run-20260924T155900Z-05 | VALID | - | False |
| run-20260924T160200Z-06 | VALID | - | False |

Only VALID runs below contribute to aggregate timing evidence.

## Graph metadata — OBSERVED

| run_id | topic | observed_types | publisher_count | publishers |
| --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | /clock | rosgraph_msgs/msg/Clock | 1 | /ros_gz_bridge |
| run-20260924T155000Z-02 | /ground_truth/odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155000Z-02 | /odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155000Z-02 | /scan | sensor_msgs/msg/LaserScan | 1 | /ros_gz_bridge |
| run-20260924T155000Z-02 | /tf | tf2_msgs/msg/TFMessage | 2 | /robot_state_publisher,/ros_gz_bridge |
| run-20260924T155300Z-03 | /clock | rosgraph_msgs/msg/Clock | 1 | /ros_gz_bridge |
| run-20260924T155300Z-03 | /ground_truth/odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155300Z-03 | /odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155300Z-03 | /scan | sensor_msgs/msg/LaserScan | 1 | /ros_gz_bridge |
| run-20260924T155300Z-03 | /tf | tf2_msgs/msg/TFMessage | 2 | /robot_state_publisher,/ros_gz_bridge |
| run-20260924T155600Z-04 | /clock | rosgraph_msgs/msg/Clock | 1 | /ros_gz_bridge |
| run-20260924T155600Z-04 | /ground_truth/odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155600Z-04 | /odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155600Z-04 | /scan | sensor_msgs/msg/LaserScan | 1 | /ros_gz_bridge |
| run-20260924T155600Z-04 | /tf | tf2_msgs/msg/TFMessage | 2 | /robot_state_publisher,/ros_gz_bridge |
| run-20260924T155900Z-05 | /clock | rosgraph_msgs/msg/Clock | 1 | /ros_gz_bridge |
| run-20260924T155900Z-05 | /ground_truth/odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155900Z-05 | /odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T155900Z-05 | /scan | sensor_msgs/msg/LaserScan | 1 | /ros_gz_bridge |
| run-20260924T155900Z-05 | /tf | tf2_msgs/msg/TFMessage | 2 | /robot_state_publisher,/ros_gz_bridge |
| run-20260924T160200Z-06 | /clock | rosgraph_msgs/msg/Clock | 1 | /ros_gz_bridge |
| run-20260924T160200Z-06 | /ground_truth/odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T160200Z-06 | /odom | nav_msgs/msg/Odometry | 1 | /ros_gz_bridge |
| run-20260924T160200Z-06 | /scan | sensor_msgs/msg/LaserScan | 1 | /ros_gz_bridge |
| run-20260924T160200Z-06 | /tf | tf2_msgs/msg/TFMessage | 2 | /robot_state_publisher,/ros_gz_bridge |

## Stream statistics — OBSERVED

### /clock

| run_id | records | messages | rate_hz | duplicates | regressions | steady_p99_ns | steady_max_ns | frames | children |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 5698 | 5698 | 94.99791345003769 | 0 | 0 | 27015344.399999995 | 43121187 | - | - |
| run-20260924T155300Z-03 | 5600 | 5600 | 93.32185811963903 | 0 | 0 | 29438867.219999988 | 72431199 | - | - |
| run-20260924T155600Z-04 | 5737 | 5737 | 95.66186899649495 | 0 | 0 | 26663320.19999999 | 53985649 | - | - |
| run-20260924T155900Z-05 | 5778 | 5778 | 96.2869570095117 | 0 | 0 | 24782931.879999988 | 52754190 | - | - |
| run-20260924T160200Z-06 | 5854 | 5854 | 97.54835979911705 | 0 | 0 | 23295328.599999968 | 50255594 | - | - |

### /ground_truth/odom

| run_id | records | messages | rate_hz | duplicates | regressions | steady_p99_ns | steady_max_ns | frames | children |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 2849 | 2849 | 47.494624361465505 | 0 | 0 | 40279874.940000124 | 64565041 | world | base_link |
| run-20260924T155300Z-03 | 2800 | 2800 | 46.661716876094964 | 0 | 0 | 47708013.519999996 | 81272000 | world | base_link |
| run-20260924T155600Z-04 | 2869 | 2869 | 47.82763664423716 | 0 | 0 | 40032490.66 | 62969864 | world | base_link |
| run-20260924T155900Z-05 | 2889 | 2889 | 48.14792175640517 | 0 | 0 | 37472513.46000003 | 61772025 | world | base_link |
| run-20260924T160200Z-06 | 2926 | 2926 | 48.77333427189614 | 0 | 0 | 35757885.91999998 | 58195303 | world | base_link |

### /odom

| run_id | records | messages | rate_hz | duplicates | regressions | steady_p99_ns | steady_max_ns | frames | children |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 2850 | 2850 | 47.486062819561255 | 0 | 0 | 40521849.4 | 64803017 | odom | base_link |
| run-20260924T155300Z-03 | 2800 | 2800 | 46.66071508340014 | 0 | 0 | 46004471.519999996 | 77666658 | odom | base_link |
| run-20260924T155600Z-04 | 2869 | 2869 | 47.828683121136926 | 0 | 0 | 40722410.60999998 | 63230653 | odom | base_link |
| run-20260924T155900Z-05 | 2889 | 2889 | 48.147232213926436 | 0 | 0 | 37880403.01000007 | 62437188 | odom | base_link |
| run-20260924T160200Z-06 | 2926 | 2926 | 48.772409529726616 | 0 | 0 | 35667197.159999914 | 59212061 | odom | base_link |

### /scan

| run_id | records | messages | rate_hz | duplicates | regressions | steady_p99_ns | steady_max_ns | frames | children |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 570 | 570 | 9.498937698989943 | 0 | 0 | 138375688.68000016 | 158385923 | ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar | - |
| run-20260924T155300Z-03 | 560 | 560 | 9.332430559789435 | 0 | 0 | 143287362.9799999 | 174848339 | ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar | - |
| run-20260924T155600Z-04 | 574 | 574 | 9.560268340692428 | 0 | 0 | 137627373.99999997 | 155410608 | ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar | - |
| run-20260924T155900Z-05 | 577 | 577 | 9.627724471157196 | 0 | 0 | 135794412.5 | 143419617 | ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar | - |
| run-20260924T160200Z-06 | 585 | 585 | 9.753197257790585 | 0 | 0 | 129109335.04999995 | 138713042 | ROBOT_URDF_final/RPLiDAR_A1M8_1/rplidar | - |

### /tf

| run_id | records | messages | rate_hz | duplicates | regressions | steady_p99_ns | steady_max_ns | frames | children |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 7410 | 3990 | 66.48601631225179 | 570 | 0 | 34535726.39999997 | 51139231 | base_link,odom | Wheel_LB_1,Wheel_LF_1,Wheel_RB_1,Wheel_RF_1,base_link |
| run-20260924T155300Z-03 | 7280 | 3920 | 65.3318341085399 | 560 | 1 | 37142252.400000006 | 80445547 | base_link,odom | Wheel_LB_1,Wheel_LF_1,Wheel_RB_1,Wheel_RF_1,base_link |
| run-20260924T155600Z-04 | 7461 | 4017 | 66.97374135527603 | 574 | 0 | 34940502.79999996 | 62905410 | base_link,odom | Wheel_LB_1,Wheel_LF_1,Wheel_RB_1,Wheel_RF_1,base_link |
| run-20260924T155900Z-05 | 7513 | 4045 | 67.41898603594694 | 578 | 0 | 33104734.680000126 | 60604948 | base_link,odom | Wheel_LB_1,Wheel_LF_1,Wheel_RB_1,Wheel_RF_1,base_link |
| run-20260924T160200Z-06 | 7610 | 4097 | 68.29655619689932 | 586 | 0 | 31725088.4 | 59726731 | base_link,odom | Wheel_LB_1,Wheel_LF_1,Wheel_RB_1,Wheel_RF_1,base_link |

## Timestamp pairing — OBSERVED

### ground_truth_odom_to_odom

| run_id | pairs | exact | nonzero | p99_skew_ns | max_skew_ns |
| --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 2849 | 2849 | 0 | 0.0 | 0 |
| run-20260924T155300Z-03 | 2800 | 2800 | 0 | 0.0 | 0 |
| run-20260924T155600Z-04 | 2869 | 2869 | 0 | 0.0 | 0 |
| run-20260924T155900Z-05 | 2889 | 2889 | 0 | 0.0 | 0 |
| run-20260924T160200Z-06 | 2926 | 2926 | 0 | 0.0 | 0 |

### scan_to_odom

| run_id | pairs | exact | nonzero | p99_skew_ns | max_skew_ns |
| --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 570 | 570 | 0 | 0.0 | 0 |
| run-20260924T155300Z-03 | 560 | 560 | 0 | 0.0 | 0 |
| run-20260924T155600Z-04 | 574 | 574 | 0 | 0.0 | 0 |
| run-20260924T155900Z-05 | 577 | 577 | 0 | 0.0 | 0 |
| run-20260924T160200Z-06 | 585 | 585 | 0 | 0.0 | 0 |

### scan_to_ground_truth_odom

| run_id | pairs | exact | nonzero | p99_skew_ns | max_skew_ns |
| --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | 570 | 569 | 1 | 0.0 | 20000000 |
| run-20260924T155300Z-03 | 560 | 560 | 0 | 0.0 | 0 |
| run-20260924T155600Z-04 | 574 | 574 | 0 | 0.0 | 0 |
| run-20260924T155900Z-05 | 577 | 577 | 0 | 0.0 | 0 |
| run-20260924T160200Z-06 | 585 | 585 | 0 | 0.0 | 0 |

## Nonzero timestamp-skew outliers — OBSERVED

| run_id | pair | left_stamp_ns | right_stamp_ns | absolute_skew_ns | left_index | right_index |
| --- | --- | --- | --- | --- | --- | --- |
| run-20260924T155000Z-02 | scan_to_ground_truth_odom | 2000000000 | 2020000000 | 20000000 | 1 | 1 |

## TF relations — OBSERVED

| parent_frame | child_frame |
| --- | --- |
| base_link | Wheel_LB_1 |
| base_link | Wheel_LF_1 |
| base_link | Wheel_RB_1 |
| base_link | Wheel_RF_1 |
| odom | base_link |

## Ground-truth stream assessment

CANDIDATE_FOR_FUTURE_DECISION: valid runs observed /ground_truth/odom with world to base_link frame metadata. This is not a TrainingTaskOracle and does not authorize GT for policy observation.

## Limitations — NOT_ESTABLISHED

This idle passive evidence does not establish ContactLatch/collision, task goal or bounds, STUCK policy, D6 limit, reward, termination, Gym behavior, actuator behavior, or hardware behavior.
A permitted pre-existing ros_gz_bridge publisher does not prove no external command was sent. The evidence only records graph changes and that the collector declares no command publish or control-service operation.
