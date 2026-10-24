#include "step07_nav2_baseline_runtime_observer/lifecycle_ingress.hpp"

#include <gtest/gtest.h>
#include <rmw/qos_policy_kind.h>
#include <rmw/types.h>

#include <chrono>
#include <filesystem>
#include <stdexcept>
#include <thread>
#include <unistd.h>
#include <utility>

namespace {
using step07_observer::LifecycleIngress;
using step07_observer::LifecyclePublisherEndpoint;

std::filesystem::path make_directory() {
  std::string pattern = "/tmp/step07-lifecycle-ingress-test-XXXXXX";
  auto *created = ::mkdtemp(pattern.data());
  if (created == nullptr) throw std::runtime_error("mkdtemp failed");
  return created;
}

LifecyclePublisherEndpoint endpoint(std::string gid = std::string(2 * RMW_GID_STORAGE_SIZE, 'a')) {
  return {"/mecanum/safety_lifecycle_state",
          "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState",
          "safety_lifecycle", "/", std::move(gid),
          RMW_QOS_POLICY_RELIABILITY_RELIABLE,
          RMW_QOS_POLICY_DURABILITY_VOLATILE,
          RMW_QOS_POLICY_HISTORY_KEEP_LAST, 10};
}

bool wait_for(const std::filesystem::path &path) {
  for (int i = 0; i < 100; ++i) {
    if (std::filesystem::is_regular_file(path)) return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return false;
}
}  // namespace

TEST(LifecycleIngress, PinsSingleEndpointAndPublishesAdmittedMessage) {
  const auto root = make_directory();
  const auto live = root / "lifecycle_ingress.live.json";
  LifecycleIngress ingress(live.string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-1", "session-1", std::string(64, 'a'));
  EXPECT_FALSE(ingress.ready());
  EXPECT_TRUE(ingress.pin_endpoint({endpoint()}));
  EXPECT_TRUE(ingress.ready());
  EXPECT_TRUE(ingress.admit({{"sequence", 7}, {"motion_permitted", true}},
      endpoint().gid, 1234, 5678));
  ASSERT_TRUE(wait_for(live));
  const auto document = ingress.live_document();
  ASSERT_EQ(document.at("records").size(), 1u);
  EXPECT_EQ(document.at("records").at(0).at("record_index"), 1u);
  EXPECT_EQ(document.at("records").at(0).at("sequence"), 7u);
  EXPECT_EQ(document.at("records").at(0).at("receive_time").at("clock"), "CLOCK_MONOTONIC");
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("state"), "FINALIZED");
  EXPECT_TRUE(std::filesystem::is_regular_file(root / "final.json"));
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, ExtraPublisherAndChangedMessageGidFailClosed) {
  const auto root = make_directory();
  LifecycleIngress extra((root / "live.json").string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-2", "session-2", std::string(64, 'b'));
  EXPECT_FALSE(extra.pin_endpoint({endpoint(), endpoint(std::string(2 * RMW_GID_STORAGE_SIZE, 'b'))}));
  EXPECT_TRUE(extra.failed());
  EXPECT_EQ(extra.failure_literal(), "LIFECYCLE_EXTRA_OR_AMBIGUOUS_PUBLISHER");
  extra.finalize();

  LifecycleIngress changed((root / "live2.json").string(), (root / "refs2.json").string(),
      (root / "final2.json").string(), "invocation-3", "session-3", std::string(64, 'c'));
  ASSERT_TRUE(changed.pin_endpoint({endpoint()}));
  EXPECT_FALSE(changed.admit({{"sequence", 1}}, std::string(2 * RMW_GID_STORAGE_SIZE, 'c'), 1, 2));
  EXPECT_EQ(changed.failure_literal(), "LIFECYCLE_MESSAGE_GID_MISMATCH");
  changed.finalize();
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, HeartbeatSequenceMayRepeatButRegressionFails) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  LifecycleIngress ingress(live.string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-4", "session-4", std::string(64, 'd'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  ASSERT_TRUE(ingress.admit({{"sequence", 8}}, endpoint().gid, 1, 2));
  ASSERT_TRUE(ingress.admit({{"sequence", 8}}, endpoint().gid, 2, 3));
  ASSERT_TRUE(ingress.admit({{"sequence", 7}}, endpoint().gid, 3, 4) == false);
  EXPECT_EQ(ingress.failure_literal(), "LIFECYCLE_BARRIER_SEQUENCE_REGRESSION");
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("state"), "FAILED");
  std::filesystem::remove_all(root);
}
