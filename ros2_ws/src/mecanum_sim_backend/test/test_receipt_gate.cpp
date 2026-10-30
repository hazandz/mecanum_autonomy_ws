#include <gtest/gtest.h>
#include <functional>
#include <limits>
#include <vector>

#include "mecanum_sim_backend/receipt_gate.hpp"

using namespace mecanum_sim_backend;
namespace
{
GateBinding Binding()
{
  GateBinding b; b.session_id = "run-1"; b.config_hash = std::string(64, 'a');
  b.final_publisher_instance_id = 81; b.safe_stop_source_instance_id = 9;
  b.policy_source_instance_id = 10; b.next_safe_stop_sequence = 1;
  b.barrier_stamp_ns = 1'000; b.episode_generation = 2; b.reset_epoch = 3;
  b.runtime_generation = 4; b.expected_step_index = 1; b.next_policy_sequence = 1;
  b.expected_transition_id = "policy-uuid-1"; return b;
}
ReceiptFacts Anchor()
{
  ReceiptFacts r; r.session_id = "run-1"; r.config_hash = std::string(64, 'a');
  r.key = {81, 100}; r.episode_generation = 2; r.reset_epoch = 3;
  r.runtime_generation = 4; r.source = 4; r.sequence = 1;
  r.source_instance_id = 9; r.stamp_ns = 1'000; r.frame_id = "base_link";
  return r;
}
ReceiptFacts Policy()
{
  auto r = Anchor(); r.key.publish_sequence = 101; r.step_index = 1;
  r.transition_id = "policy-uuid-1"; r.source = 1; r.sequence = 1;
  r.source_instance_id = 10; r.twist = {0.25, -0.20, 0.0, 0.0, 0.0, 0.80};
  return r;
}
void AcceptAnchor(ReceiptGate &gate)
{
  ASSERT_TRUE(gate.Enqueue(Anchor(), 2'000));
  EXPECT_EQ(gate.ConsumeNext(2'000, 2'000).disposition, GateDisposition::Anchored);
}
}

TEST(ReceiptGate, RequiresBoundPostBarrierSafeStopAnchorAndNextPolicy)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  ASSERT_TRUE(gate.Enqueue(Policy(), 2'100));
  const auto accepted = gate.ConsumeNext(2'100, 2'100);
  EXPECT_EQ(accepted.disposition, GateDisposition::Applied);
  EXPECT_TRUE(accepted.refresh_watchdog);
  EXPECT_EQ(gate.Watermark(), 101U);
}

TEST(ReceiptGate, ExactDuplicateDoesNotRefreshWatchdog)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate); auto r = Policy();
  ASSERT_TRUE(gate.Enqueue(r, 2'100)); EXPECT_EQ(gate.ConsumeNext(2'100, 2'100).disposition, GateDisposition::Applied);
  ASSERT_TRUE(gate.Enqueue(r, 3'000));
  const auto duplicate = gate.ConsumeNext(3'000, 3'000);
  EXPECT_EQ(duplicate.disposition, GateDisposition::Duplicate);
  EXPECT_FALSE(duplicate.refresh_watchdog);
  EXPECT_EQ(gate.LastAcceptedSteadyNs(), 2'100);
}

TEST(ReceiptGate, SameKeyChangedPayloadFaults)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate); auto r = Policy();
  ASSERT_TRUE(gate.Enqueue(r, 2'100)); (void)gate.ConsumeNext(2'100, 2'100);
  r.twist[1] = 0.1; ASSERT_TRUE(gate.Enqueue(r, 2'200));
  EXPECT_EQ(gate.ConsumeNext(2'200, 2'200).reason, "publication_key_content_conflict");
}

TEST(ReceiptGate, RejectsReplayAndFaultsSequenceGap)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate); auto r = Policy();
  ASSERT_TRUE(gate.Enqueue(r, 2'100)); (void)gate.ConsumeNext(2'100, 2'100);
  gate.SetExpectedPolicyStep(2, 2, "policy-uuid-2");
  auto second = Policy(); second.key.publish_sequence = 102;
  second.step_index = 2; second.sequence = 2; second.transition_id = "policy-uuid-2";
  ASSERT_TRUE(gate.Enqueue(second, 2'150));
  EXPECT_EQ(gate.ConsumeNext(2'150, 2'150).disposition, GateDisposition::Applied);
  ASSERT_TRUE(gate.Enqueue(r, 2'200));
  EXPECT_EQ(gate.ConsumeNext(2'200, 2'200).disposition, GateDisposition::Rejected);
  r.key.publish_sequence = 104; ASSERT_TRUE(gate.Enqueue(r, 2'300));
  EXPECT_EQ(gate.ConsumeNext(2'300, 2'300).reason, "final_publication_sequence_gap");
}

TEST(ReceiptGate, RejectsWrongIdentityFrameBarrierAndNonPlanarPayload)
{
  for (const auto &mutate : std::vector<std::function<void(ReceiptFacts &)>>{
      [](auto &r){r.session_id="other";}, [](auto &r){r.frame_id="odom";},
      [](auto &r){r.stamp_ns=999;}, [](auto &r){r.twist[2]=0.01;},
      [](auto &r){r.twist[0]=std::numeric_limits<double>::quiet_NaN();}})
  {
    ReceiptGate gate(Binding()); auto r = Anchor(); mutate(r);
    ASSERT_TRUE(gate.Enqueue(r, 2'000)); EXPECT_EQ(gate.ConsumeNext(2'000, 2'000).disposition, GateDisposition::Faulted);
  }
}

TEST(ReceiptGate, WatchdogUsesSteadyClockStrictlyBeyondOneHundredMilliseconds)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  EXPECT_FALSE(gate.WatchdogExpired(100'002'000));
  EXPECT_TRUE(gate.WatchdogExpired(100'002'001));
}

TEST(ReceiptGate, StartupRemainsInhibitedUntilValidAnchorArrives)
{
  ReceiptGate gate(Binding());
  EXPECT_FALSE(gate.WatchdogExpired(1'000'000'000));
  EXPECT_EQ(gate.ConsumeNext(1'000'000'000, 1'000'000'000).disposition,
            GateDisposition::Inhibited);
}

TEST(ReceiptGate, QueueOverflowIsStickyFault)
{
  ReceiptGate gate(Binding());
  for (std::size_t i=0; i<ReceiptGate::kQueueCapacity; ++i)
    ASSERT_TRUE(gate.Enqueue(Anchor(), static_cast<std::int64_t>(i)));
  EXPECT_FALSE(gate.Enqueue(Anchor(), 129)); EXPECT_TRUE(gate.Faulted());
  EXPECT_EQ(gate.ConsumeNext(200, 200).disposition, GateDisposition::Faulted);
}
