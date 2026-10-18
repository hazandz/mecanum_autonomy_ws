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

TEST(Wp06fObserver, RequiresNonzeroStrictlyIncreasingTimestamps)
{
  EXPECT_TRUE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 12, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({0, 11, 12, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 11, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 12, 11, 13, 14}));
  EXPECT_FALSE(wp06_6f_observer::strictly_increasing_nonzero({10, 11, 12, 13}));
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
