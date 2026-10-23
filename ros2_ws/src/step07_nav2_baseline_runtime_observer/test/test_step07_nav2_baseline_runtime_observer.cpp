#define STEP07_OBSERVER_TEST
#include "../src/step07_nav2_baseline_runtime_observer.cpp"
#include <gtest/gtest.h>
#include <fstream>
#include <filesystem>

TEST(Step07Observer, CollectionsAreEmptyArraysNotNestedArrays) {
  const auto document = step07_observer::empty_collection_document();
  for (const auto *name : {"clock", "scan", "wheel_odometry_raw", "imu_data",
                           "filtered_odometry", "tf", "tf_static", "map_to_odom", "world_to_map"}) {
    ASSERT_TRUE(document.at(name).is_array());
    EXPECT_TRUE(document.at(name).empty());
  }
}

TEST(Step07Observer, ReadinessArtifactWriteIsAtomicAndReadable) {
  const auto path = std::filesystem::temp_directory_path() /
      ("step07-observer-ready-" + std::to_string(::getpid()) + ".json");
  const auto document = step07_observer::Json{{"state", "READY"},
      {"ros_context_valid", true}, {"subscriptions_created", {"/scan"}}};
  ASSERT_TRUE(step07_observer::write_json_atomic(path.string(), document));
  std::ifstream input(path);
  step07_observer::Json readback;
  input >> readback;
  EXPECT_EQ(readback, document);
  std::filesystem::remove(path);
}

TEST(Step07Observer, FinishChecksContextBeforeEndpointQueriesAndShutdownFollowsFinish) {
  const auto source_path = std::filesystem::path(__FILE__).parent_path().parent_path() /
      "src/step07_nav2_baseline_runtime_observer.cpp";
  std::ifstream input(source_path);
  const std::string source((std::istreambuf_iterator<char>(input)), {});
  const auto finish = source.find("void finish() {");
  const auto finish_end = source.find("\n private:", finish);
  ASSERT_NE(finish, std::string::npos);
  ASSERT_NE(finish_end, std::string::npos);
  const auto finish_body = source.substr(finish, finish_end - finish);
  const auto endpoint_query = source.find("endpoint_rows(*this", finish);
  const auto context_guard = source.find("if (!context_is_valid())", finish);
  ASSERT_NE(endpoint_query, std::string::npos);
  ASSERT_NE(context_guard, std::string::npos);
  EXPECT_LT(context_guard, endpoint_query);
  EXPECT_EQ(finish_body.find("rclcpp::shutdown();"), std::string::npos);
  EXPECT_NE(source.find("SignalHandlerOptions::None"), std::string::npos);
}

TEST(Step07Observer, CanonicalGidIsFullLowercaseHex) {
  const uint8_t gid[] = {0x00, 0x01, 0xa0, 0xff};
  EXPECT_EQ(step07_observer::canonical_gid(gid, sizeof(gid)), "0001a0ff");
}

TEST(Step07Observer, DynamicAndStaticEdgePredicatesAreDistinct) {
  EXPECT_TRUE(step07_observer::is_dynamic_edge("odom", "base_link"));
  EXPECT_TRUE(step07_observer::is_static_edge("base_link", "lidar_frame"));
  EXPECT_FALSE(step07_observer::is_dynamic_edge("base_link", "lidar_frame"));
  EXPECT_FALSE(step07_observer::is_static_edge("map", "odom"));
}

TEST(Step07Observer, DynamicSamplesRequireFiveNonzeroStrictlyIncreasingStamps) {
  auto samples = step07_observer::Json::array();
  for (int64_t stamp = 1; stamp <= 5; ++stamp) {
    samples.push_back({{"stamp_sec", 0}, {"stamp_nanosec", stamp}});
  }
  EXPECT_TRUE(step07_observer::strictly_increasing_nonzero(samples));
  samples[4]["stamp_nanosec"] = 4;
  EXPECT_FALSE(step07_observer::strictly_increasing_nonzero(samples));
  samples[4]["stamp_nanosec"] = 0;
  EXPECT_FALSE(step07_observer::strictly_increasing_nonzero(samples));
}

TEST(Step07Observer, StaticTransformMustMatchThePinnedEdgeAndValues) {
  const auto valid = step07_observer::Json{{"parent", "base_link"}, {"child", "lidar_frame"},
      {"translation", {-0.031765, 0.0, 0.140}}, {"rotation", {0.0, 0.0, 0.0, 1.0}}};
  EXPECT_TRUE(step07_observer::static_transform_matches(valid));
  auto changed = valid;
  changed["translation"][2] = 0.141;
  EXPECT_FALSE(step07_observer::static_transform_matches(changed));
  changed = valid;
  changed["child"] = "other_frame";
  EXPECT_FALSE(step07_observer::static_transform_matches(changed));
}

TEST(Step07Observer, DynamicTfUsesBestEffortVolatileKeepLast100) {
  const auto profile = step07_observer::dynamic_tf_qos().get_rmw_qos_profile();
  EXPECT_EQ(profile.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(profile.depth, 100U);
  EXPECT_EQ(profile.reliability, RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
  EXPECT_EQ(profile.durability, RMW_QOS_POLICY_DURABILITY_VOLATILE);
}

TEST(Step07Observer, StaticTfUsesReliableTransientLocalKeepLast1) {
  const auto profile = step07_observer::static_tf_qos().get_rmw_qos_profile();
  EXPECT_EQ(profile.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(profile.depth, 1U);
  EXPECT_EQ(profile.reliability, RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  EXPECT_EQ(profile.durability, RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);
}

TEST(Step07Observer, LifecycleStateUsesDistinctReliableVolatileKeepLast10) {
  const auto profile = step07_observer::lifecycle_state_qos().get_rmw_qos_profile();
  EXPECT_EQ(profile.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(profile.depth, 10U);
  EXPECT_EQ(profile.reliability, RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  EXPECT_EQ(profile.durability, RMW_QOS_POLICY_DURABILITY_VOLATILE);
  const auto receipt = step07_observer::receipt_qos().get_rmw_qos_profile();
  EXPECT_EQ(receipt.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(receipt.depth, 1U);
  EXPECT_EQ(receipt.reliability, RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  EXPECT_EQ(receipt.durability, RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);
  const auto offered_receipt = step07_observer::Json::array({{{"node_name", "final_twist_publisher"},
      {"node_namespace", "/"}, {"topic_type", "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt"},
      {"endpoint_type", "PUBLISHER"}, {"reliability", RMW_QOS_POLICY_RELIABILITY_RELIABLE},
      {"durability", RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL}, {"history", RMW_QOS_POLICY_HISTORY_KEEP_LAST}, {"depth", 1}}});
  EXPECT_TRUE(step07_observer::receipt_publisher_contract(offered_receipt));
  auto conflated_receipt = offered_receipt;
  conflated_receipt[0]["depth"] = 10;
  EXPECT_FALSE(step07_observer::receipt_publisher_contract(conflated_receipt));
}

TEST(Step07Observer, UnknownHistoryDepthIsUnobservableAndPolicyMismatchStillFails) {
  step07_observer::Json endpoint = {{"reliability", RMW_QOS_POLICY_RELIABILITY_RELIABLE},
    {"durability", RMW_QOS_POLICY_DURABILITY_VOLATILE},
    {"history", RMW_QOS_POLICY_HISTORY_UNKNOWN}, {"depth", 0}};
  EXPECT_EQ(step07_observer::endpoint_policy_status(endpoint,
      RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_VOLATILE, 10),
      step07_observer::EndpointPolicyStatus::Unobservable);
  endpoint["reliability"] = RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT;
  EXPECT_EQ(step07_observer::endpoint_policy_status(endpoint,
      RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_VOLATILE, 10),
      step07_observer::EndpointPolicyStatus::Mismatch);
  endpoint["reliability"] = RMW_QOS_POLICY_RELIABILITY_RELIABLE;
  endpoint["durability"] = RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL;
  EXPECT_EQ(step07_observer::endpoint_policy_status(endpoint,
      RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_VOLATILE, 10),
      step07_observer::EndpointPolicyStatus::Mismatch);
}

TEST(Step07Observer, LifecyclePublisherRequiresExactOwnerTypeAndOfferedQos) {
  auto publisher = step07_observer::Json::array({{{"node_name", "safety_lifecycle"},
      {"node_namespace", "/"}, {"topic_type", "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState"},
      {"endpoint_type", "PUBLISHER"}, {"reliability", RMW_QOS_POLICY_RELIABILITY_RELIABLE},
      {"durability", RMW_QOS_POLICY_DURABILITY_VOLATILE}, {"history", RMW_QOS_POLICY_HISTORY_KEEP_LAST}, {"depth", 10}}});
  EXPECT_TRUE(step07_observer::lifecycle_publisher_contract(publisher));
  publisher[0]["node_name"] = "other";
  EXPECT_FALSE(step07_observer::lifecycle_publisher_contract(publisher));
  publisher[0]["node_name"] = "safety_lifecycle";
  publisher[0]["durability"] = RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL;
  EXPECT_FALSE(step07_observer::lifecycle_publisher_contract(publisher));
}

TEST(Step07Observer, LifecycleGraphRequiresExactConsumersAndQos) {
  auto subscribers = step07_observer::Json::array();
  for (const auto *name : {"safety_supervisor", "final_twist_publisher",
                           "step07_nav2_baseline_runtime_observer", "step07_gate_b_observer"}) {
    subscribers.push_back({{"node_name", name}, {"node_namespace", "/"},
      {"topic_type", "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState"}, {"endpoint_type", "SUBSCRIPTION"},
      {"reliability", RMW_QOS_POLICY_RELIABILITY_RELIABLE}, {"durability", RMW_QOS_POLICY_DURABILITY_VOLATILE},
      {"history", RMW_QOS_POLICY_HISTORY_KEEP_LAST}, {"depth", 10}});
  }
  EXPECT_TRUE(step07_observer::lifecycle_observer_subscriptions_contract(subscribers));
  subscribers[3]["durability"] = RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL;
  EXPECT_FALSE(step07_observer::lifecycle_observer_subscriptions_contract(subscribers));
  subscribers[3]["durability"] = RMW_QOS_POLICY_DURABILITY_VOLATILE;
  subscribers.push_back(subscribers.front());
  EXPECT_FALSE(step07_observer::lifecycle_observer_subscriptions_contract(subscribers));
}

TEST(Step07Observer, LifecycleAndReceiptIdentityMustMatchExactly) {
  EXPECT_TRUE(step07_observer::lifecycle_receipt_identity_matches(7, 3, 9, 7, 3, 9));
  EXPECT_FALSE(step07_observer::lifecycle_receipt_identity_matches(7, 3, 9, 7, 4, 9));
}

TEST(Step07Observer, GidMappingRequiresUniqueExactOwnerEndpoint) {
  const auto endpoints = step07_observer::Json::array({
      {{"gid", "gid-a"}, {"node_name", "robot_state_publisher"}, {"node_namespace", "/"},
       {"topic_type", "tf2_msgs/msg/TFMessage"}},
      {{"gid", "gid-b"}, {"node_name", "other"}, {"node_namespace", "/"},
       {"topic_type", "tf2_msgs/msg/TFMessage"}}});
  EXPECT_TRUE(step07_observer::exact_owner_for_gid(endpoints, "gid-a", "robot_state_publisher"));
  EXPECT_FALSE(step07_observer::exact_owner_for_gid(endpoints, "gid-a", "ekf_filter_node"));
  auto duplicate = endpoints;
  duplicate.push_back(endpoints.front());
  EXPECT_FALSE(step07_observer::exact_owner_for_gid(duplicate, "gid-a", "robot_state_publisher"));
}

TEST(Step07Observer, EveryReceiptMustMatchAReadyLifecycleIdentity) {
  const auto lifecycle = step07_observer::Json::array({{{"episode_generation", 7}, {"reset_epoch", 3},
      {"runtime_generation", 9}, {"primary_state", 2}, {"barrier_state", 1}, {"motion_permitted", true}}});
  const auto receipts = step07_observer::Json::array({{{"episode_generation", 7}, {"reset_epoch", 3},
      {"runtime_generation", 9}}});
  EXPECT_TRUE(step07_observer::lifecycle_receipts_match(lifecycle, receipts));
  auto mismatch = receipts;
  mismatch[0]["runtime_generation"] = 10;
  EXPECT_FALSE(step07_observer::lifecycle_receipts_match(lifecycle, mismatch));
}

TEST(Step07Observer, UnobservableQosIsRawStatusNotCollectorFailure) {
  const auto source_path = std::filesystem::path(__FILE__).parent_path().parent_path() /
      "src/step07_nav2_baseline_runtime_observer.cpp";
  std::ifstream input(source_path);
  const std::string source((std::istreambuf_iterator<char>(input)), {});
  EXPECT_NE(source.find("\"UNOBSERVABLE\""), std::string::npos);
  EXPECT_NE(source.find("if (!unknown_qos) doc_[\"errors\"].push_back"), std::string::npos);
  EXPECT_NE(source.find("\"qos_verdict\""), std::string::npos);
  EXPECT_NE(source.find("row.value(\"topic_type\", \"\") == type"), std::string::npos);
  EXPECT_NE(source.find("observed != expected"), std::string::npos);
  EXPECT_NE(source.find("return failed_closed_ ? 2 : 0"), std::string::npos);
  EXPECT_NE(source.find("qos_verdict_details"), std::string::npos);
  EXPECT_NE(source.find("RMW_HISTORY_DEPTH_METADATA_UNAVAILABLE"), std::string::npos);
}

TEST(Step07Observer, RawEndpointEvidenceIncludesDirectionIdentityPolicyAndDiscoveryTime) {
  const auto source_path = std::filesystem::path(__FILE__).parent_path().parent_path() /
      "src/step07_nav2_baseline_runtime_observer.cpp";
  std::ifstream input(source_path);
  const std::string source((std::istreambuf_iterator<char>(input)), {});
  for (const auto *field : {"topic_name", "endpoint_type", "topic_type", "reliability",
                            "durability", "history", "depth", "gid",
                            "discovery_monotonic_ns", "ENDPOINT_NOT_DISCOVERED_AT_FINAL_SNAPSHOT"}) {
    EXPECT_NE(source.find(field), std::string::npos) << field;
  }
}

TEST(Step07Observer, QosVerdictDoesNotControlCollectorExitStatus) {
  const auto source_path = std::filesystem::path(__FILE__).parent_path().parent_path() /
      "src/step07_nav2_baseline_runtime_observer.cpp";
  std::ifstream input(source_path);
  const std::string source((std::istreambuf_iterator<char>(input)), {});
  const auto exit_start = source.find("int exit_code() const {");
  const auto exit_end = source.find("\n  }", exit_start);
  ASSERT_NE(exit_start, std::string::npos);
  ASSERT_NE(exit_end, std::string::npos);
  const auto body = source.substr(exit_start, exit_end - exit_start);
  EXPECT_NE(body.find("return failed_closed_ ? 2 : 0"), std::string::npos);
  EXPECT_EQ(body.find("doc_[\"errors\"]"), std::string::npos);
}

TEST(Step07Observer, RunnerControlledModeDisablesObserverSelfFinalizationTimer) {
  const auto source_path = std::filesystem::path(__FILE__).parent_path().parent_path() /
      "src/step07_nav2_baseline_runtime_observer.cpp";
  std::ifstream input(source_path);
  const std::string source((std::istreambuf_iterator<char>(input)), {});
  EXPECT_NE(source.find("runner_controlled_shutdown_ = declare_parameter<bool>(\"runner_controlled_shutdown\", false)"), std::string::npos);
  EXPECT_NE(source.find("if (!runner_controlled_shutdown_)"), std::string::npos);
  EXPECT_NE(source.find("if (!node->finished()) node->finish();"), std::string::npos);
}
