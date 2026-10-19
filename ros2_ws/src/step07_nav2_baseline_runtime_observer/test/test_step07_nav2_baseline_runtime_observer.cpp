#define STEP07_OBSERVER_TEST
#include "../src/step07_nav2_baseline_runtime_observer.cpp"
#include <gtest/gtest.h>

TEST(Step07Observer, CollectionsAreEmptyArraysNotNestedArrays) {
  const auto document = step07_observer::empty_collection_document();
  for (const auto *name : {"clock", "scan", "wheel_odometry_raw", "imu_data",
                           "filtered_odometry", "tf", "tf_static", "map_to_odom", "world_to_map"}) {
    ASSERT_TRUE(document.at(name).is_array());
    EXPECT_TRUE(document.at(name).empty());
  }
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
