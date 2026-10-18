#define WP06_OBSERVER_TESTING
#include "../src/wp06_6f_tf_ekf_runtime_observer.cpp"

#include <gtest/gtest.h>

TEST(Wp06fObserver, CanonicalizesPublisherGidAsLowercaseHex)
{
  const std::array<uint8_t, 4> bytes{0x00, 0x0a, 0x7f, 0xff};
  EXPECT_EQ(wp06_6f_observer::canonical_gid(bytes.data(), bytes.size()), "000a7fff");
}

TEST(Wp06fObserver, RejectsUnavailablePublisherGid)
{
  const std::array<uint8_t, 4> zero{};
  EXPECT_FALSE(wp06_6f_observer::canonical_gid(zero.data(), zero.size()).has_value());
  EXPECT_FALSE(wp06_6f_observer::canonical_gid(nullptr, 4).has_value());
}

TEST(Wp06fObserver, JsonCollectionsAreEmptyArraysAndDynamicGidPathAcceptsObjectRows)
{
  using wp06_6f_observer::Json;
  wp06_6f_observer::ObserverCollections collections;
  const auto empty_document = wp06_6f_observer::collection_document(collections);
  for (const auto * key : {"forbidden_edges", "clock_samples", "odom_samples", "dynamic_tf", "static_tf"}) {
    ASSERT_TRUE(empty_document.at(key).is_array()) << key;
    EXPECT_TRUE(empty_document.at(key).empty()) << key;
  }

  collections.dynamic_tf.push_back(Json{
    {"parent", "odom"}, {"child", "base_link"}, {"publisher_gid", "a1b2"},
    {"stamp_ns", 42}, {"valid", true}});
  std::set<std::string> gids;
  EXPECT_NO_THROW(gids = wp06_6f_observer::dynamic_edge_gids(collections.dynamic_tf));
  EXPECT_EQ(gids, (std::set<std::string>{"a1b2"}));
  const auto document = wp06_6f_observer::collection_document(collections);
  ASSERT_TRUE(document.at("dynamic_tf").is_array());
  ASSERT_EQ(document.at("dynamic_tf").size(), 1U);
  EXPECT_TRUE(document.at("dynamic_tf").front().is_object());
  EXPECT_NO_THROW(document.at("dynamic_tf").front().at("publisher_gid").get<std::string>());
}

TEST(Wp06fObserver, RejectsNestedCollectionRowsWithStructuredFailure)
{
  const wp06_6f_observer::Json malformed = wp06_6f_observer::Json::array({
    wp06_6f_observer::Json::array()});
  try {
    (void)wp06_6f_observer::dynamic_edge_gids(malformed);
    FAIL() << "expected fail-closed collection validation";
  } catch (const std::invalid_argument & error) {
    EXPECT_STREQ(error.what(), "OBSERVER_DYNAMIC_TF_ROW_INVALID");
  }
}

TEST(Wp06fObserver, FiltersOnlyTheApprovedDynamicAndForbiddenEdges)
{
  EXPECT_TRUE(wp06_6f_observer::is_dynamic_odom_edge("odom", "base_link"));
  EXPECT_FALSE(wp06_6f_observer::is_dynamic_odom_edge("map", "odom"));
  EXPECT_TRUE(wp06_6f_observer::is_map_odom_edge("map", "odom"));
  EXPECT_FALSE(wp06_6f_observer::is_map_odom_edge("odom", "base_link"));
}

TEST(Wp06fObserver, MapsGidToOneExactGraphEndpointAndOwner)
{
  using wp06_6f_observer::EndpointRecord;
  const std::vector<EndpointRecord> endpoints{
    {"gid-ekf", "ekf_filter_node", "/", "tf2_msgs/msg/TFMessage"},
    {"gid-rsp", "robot_state_publisher", "/", "tf2_msgs/msg/TFMessage"}};
  const auto result = wp06_6f_observer::map_gid_to_endpoint("gid-ekf", endpoints, "ekf_filter_node");
  EXPECT_TRUE(result.unique);
  EXPECT_TRUE(result.expected_owner);
  EXPECT_EQ(result.match_count, 1U);
  EXPECT_FALSE(wp06_6f_observer::map_gid_to_endpoint("missing", endpoints, "ekf_filter_node").unique);
  auto duplicate = endpoints;
  duplicate.push_back(endpoints.front());
  const auto ambiguous = wp06_6f_observer::map_gid_to_endpoint("gid-ekf", duplicate, "ekf_filter_node");
  EXPECT_FALSE(ambiguous.unique);
  EXPECT_FALSE(ambiguous.expected_owner);
  EXPECT_FALSE(wp06_6f_observer::map_gid_to_endpoint("gid-rsp", endpoints, "ekf_filter_node").expected_owner);
}

TEST(Wp06fObserver, StaticEdgeOwnershipRequiresUniqueRobotStatePublisherEndpoint)
{
  using wp06_6f_observer::EndpointRecord;
  using wp06_6f_observer::map_gid_to_endpoint;
  using wp06_6f_observer::static_gid_failure_literal;
  const std::vector<EndpointRecord> endpoints{
    {"gid-rsp", "robot_state_publisher", "/", "tf2_msgs/msg/TFMessage"}};
  const auto mapped = map_gid_to_endpoint("gid-rsp", endpoints, "robot_state_publisher");
  EXPECT_TRUE(mapped.unique);
  EXPECT_TRUE(mapped.expected_owner);
  EXPECT_TRUE(static_gid_failure_literal(mapped).empty());
  const auto missing = map_gid_to_endpoint("unknown", endpoints, "robot_state_publisher");
  EXPECT_EQ(static_gid_failure_literal(missing), "TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE");
  auto duplicate = endpoints;
  duplicate.push_back(endpoints.front());
  const auto ambiguous = map_gid_to_endpoint("gid-rsp", duplicate, "robot_state_publisher");
  EXPECT_EQ(static_gid_failure_literal(ambiguous), "TF_STATIC_EDGE_PUBLISHER_GID_NOT_UNIQUE");
  const std::vector<EndpointRecord> wrong_owner{
    {"gid-other", "other_node", "/", "tf2_msgs/msg/TFMessage"}};
  const auto other = map_gid_to_endpoint("gid-other", wrong_owner, "robot_state_publisher");
  EXPECT_EQ(static_gid_failure_literal(other), "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER");
  const std::vector<EndpointRecord> wrong_namespace{
    {"gid-ns", "robot_state_publisher", "/nested", "tf2_msgs/msg/TFMessage"}};
  EXPECT_EQ(static_gid_failure_literal(map_gid_to_endpoint("gid-ns", wrong_namespace, "robot_state_publisher")),
    "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER");
  const std::vector<EndpointRecord> wrong_type{
    {"gid-type", "robot_state_publisher", "/", "std_msgs/msg/String"}};
  EXPECT_EQ(static_gid_failure_literal(map_gid_to_endpoint("gid-type", wrong_type, "robot_state_publisher")),
    "TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER");
}

TEST(Wp06fObserver, RequiresNonzeroStrictlyIncreasingTimestamps)
{
  EXPECT_TRUE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 12, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({0, 11, 12, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 11, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 12, 11, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 12, 13}));
}

TEST(Wp06fObserver, DynamicTfQosIsBestEffortVolatileKeepLast100)
{
  const auto profile = wp06_6f_observer::dynamic_tf_qos().get_rmw_qos_profile();
  EXPECT_EQ(profile.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(profile.depth, 100U);
  EXPECT_EQ(profile.reliability, RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT);
  EXPECT_EQ(profile.durability, RMW_QOS_POLICY_DURABILITY_VOLATILE);
}

TEST(Wp06fObserver, StaticTfQosRemainsReliableTransientLocalKeepLast1)
{
  const auto profile = wp06_6f_observer::static_tf_qos().get_rmw_qos_profile();
  EXPECT_EQ(profile.history, RMW_QOS_POLICY_HISTORY_KEEP_LAST);
  EXPECT_EQ(profile.depth, 1U);
  EXPECT_EQ(profile.reliability, RMW_QOS_POLICY_RELIABILITY_RELIABLE);
  EXPECT_EQ(profile.durability, RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL);
}

TEST(Wp06fObserver, TeardownPredicateIsSingleFailClosedContract)
{
  using wp06_6f_observer::TeardownRecord;
  EXPECT_TRUE(wp06_6f_observer::teardown_pass(TeardownRecord{0, {}, {}, "STOPPED"}));
  EXPECT_FALSE(wp06_6f_observer::teardown_pass(TeardownRecord{1, {}, {}, "STOPPED"}));
  EXPECT_FALSE(wp06_6f_observer::teardown_pass(TeardownRecord{0, {42}, {}, "STOPPED"}));
  EXPECT_FALSE(wp06_6f_observer::teardown_pass(TeardownRecord{0, {}, {42}, "STOPPED"}));
  EXPECT_FALSE(wp06_6f_observer::teardown_pass(TeardownRecord{0, {}, {}, "TEARDOWN_FAILED"}));
}
