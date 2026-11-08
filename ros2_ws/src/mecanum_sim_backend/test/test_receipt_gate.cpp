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
  r.source_instance_id = 9; r.stamp_ns = 1'001; r.frame_id = "base_link";
  return r;
}
ReceiptFacts Policy()
{
  auto r = Anchor(); r.key.publish_sequence = 101; r.stamp_ns = 1'002; r.step_index = 1;
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
  ASSERT_TRUE(gate.SetExpectedPolicyStep(2, 2, "policy-uuid-2"));
  auto current_timer = Policy(); current_timer.key.publish_sequence = 102;
  ASSERT_TRUE(gate.Enqueue(current_timer, 2'125));
  EXPECT_EQ(gate.ConsumeNext(2'125, 2'125).disposition,
            GateDisposition::Applied);
  auto second = Policy(); second.key.publish_sequence = 102;
  second.key.publish_sequence = 103;
  second.step_index = 2; second.sequence = 2; second.transition_id = "policy-uuid-2";
  ASSERT_TRUE(gate.Enqueue(second, 2'150));
  EXPECT_EQ(gate.ConsumeNext(2'150, 2'150).disposition,
            GateDisposition::Applied);
  ASSERT_TRUE(gate.Enqueue(r, 2'200));
  EXPECT_EQ(gate.ConsumeNext(2'200, 2'200).disposition, GateDisposition::Rejected);
  r.key.publish_sequence = 104; r.stamp_ns = 1'003;
  ASSERT_TRUE(gate.Enqueue(r, 2'300));
  EXPECT_EQ(gate.ConsumeNext(2'300, 2'300).reason,
            "policy_issuance_binding_mismatch");
}

TEST(ReceiptGate, PendingBarrierKeepsCurrentAndSafeStopLiveUntilPromotion)
{
  ReceiptGate gate(Binding());
  AcceptAnchor(gate);
  auto first = Policy();
  ASSERT_TRUE(gate.Enqueue(first, 2'100));
  ASSERT_EQ(gate.ConsumeNext(2'100, 2'100).disposition,
            GateDisposition::Applied);
  ASSERT_TRUE(gate.SetExpectedPolicyStep(2, 2, "policy-uuid-2", 1'100));

  auto current_timer = first;
  current_timer.key.publish_sequence = 102;
  current_timer.stamp_ns = 1'050;
  ASSERT_TRUE(gate.Enqueue(current_timer, 2'110));
  EXPECT_EQ(gate.ConsumeNext(2'110, 2'110).disposition,
            GateDisposition::Applied);

  auto early_pending = Policy();
  early_pending.key.publish_sequence = 103;
  early_pending.stamp_ns = 1'099;
  early_pending.step_index = 2;
  early_pending.sequence = 2;
  early_pending.transition_id = "policy-uuid-2";
  ASSERT_TRUE(gate.Enqueue(early_pending, 2'120));
  EXPECT_EQ(gate.ConsumeNext(2'120, 2'120).disposition,
            GateDisposition::Rejected);
  EXPECT_EQ(gate.Watermark(), 102u);

  auto safe_stop = Anchor();
  safe_stop.key.publish_sequence = 103;
  safe_stop.stamp_ns = 1'060;
  safe_stop.sequence = 2;
  ASSERT_TRUE(gate.Enqueue(safe_stop, 2'130));
  EXPECT_EQ(gate.ConsumeNext(2'130, 2'130).disposition,
            GateDisposition::Applied);
  EXPECT_EQ(gate.Watermark(), 103u);

  auto equal_pending = early_pending;
  equal_pending.key.publish_sequence = 104;
  equal_pending.stamp_ns = 1'100;
  ASSERT_TRUE(gate.Enqueue(equal_pending, 2'140));
  EXPECT_EQ(gate.ConsumeNext(2'140, 2'140).disposition,
            GateDisposition::Rejected);
  EXPECT_EQ(gate.Watermark(), 103u);

  auto pending = early_pending;
  pending.key.publish_sequence = 104;
  pending.stamp_ns = 1'101;
  ASSERT_TRUE(gate.Enqueue(pending, 2'150));
  EXPECT_EQ(gate.ConsumeNext(2'150, 2'150).disposition,
            GateDisposition::Applied);
  EXPECT_EQ(gate.Watermark(), 104u);

  auto old_identity = first;
  old_identity.key.publish_sequence = 105;
  old_identity.stamp_ns = 1'102;
  ASSERT_TRUE(gate.Enqueue(old_identity, 2'160));
  EXPECT_EQ(gate.ConsumeNext(2'160, 2'160).disposition,
            GateDisposition::Faulted);
  EXPECT_EQ(gate.Watermark(), 104u);
}

TEST(ReceiptGate, FinalPublicationSequenceGapFaultsBeforePolicyApply)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  auto skipped = Policy(); skipped.key.publish_sequence = 103;
  ASSERT_TRUE(gate.Enqueue(skipped, 2'100));
  EXPECT_EQ(gate.ConsumeNext(2'100, 2'100).reason,
            "final_publication_sequence_gap");
}

TEST(ReceiptGate, RejectsWrongIdentityFrameBarrierAndNonPlanarPayload)
{
  for (const auto &mutate : std::vector<std::function<void(ReceiptFacts &)>>{
      [](auto &r){r.session_id="other";}, [](auto &r){r.frame_id="odom";},
      [](auto &r){r.stamp_ns=1'000;}, [](auto &r){r.twist[2]=0.01;},
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

TEST(ReceiptGate, SourceTimestampRollbackClosesAdmission)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  auto first = Policy();
  ASSERT_TRUE(gate.Enqueue(first, 2'100));
  ASSERT_EQ(gate.ConsumeNext(2'100, 2'100).disposition, GateDisposition::Applied);
  ASSERT_TRUE(gate.SetExpectedPolicyStep(2, 2, "policy-uuid-2"));
  auto next = Policy();
  next.key.publish_sequence = 102; next.stamp_ns = 1'001;
  next.step_index = 2; next.sequence = 2; next.transition_id = "policy-uuid-2";
  ASSERT_TRUE(gate.Enqueue(next, 2'200));
  EXPECT_EQ(gate.ConsumeNext(2'200, 2'200).disposition, GateDisposition::Faulted);
  EXPECT_EQ(gate.FaultReason(), "source_timestamp_rollback");
}

TEST(ReceiptGate, ResetContextPreservesPublicationWatermarkAndRequiresNewAnchor)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  auto policy = Policy();
  ASSERT_TRUE(gate.Enqueue(policy, 2'100));
  ASSERT_EQ(gate.ConsumeNext(2'100, 2'100).disposition,
            GateDisposition::Applied);
  const auto watermark = gate.Watermark();
  gate.Invalidate("reset_pending");
  ASSERT_TRUE(gate.BindResetContext(2'000, 3, 4, 5, 2));
  EXPECT_EQ(gate.Watermark(), watermark);
  auto next = Anchor();
  next.key.publish_sequence = watermark + 1;
  next.stamp_ns = 2'001;
  next.episode_generation = 3;
  next.reset_epoch = 4;
  next.runtime_generation = 5;
  next.sequence = 2;
  ASSERT_TRUE(gate.Enqueue(next, 2'200));
  EXPECT_EQ(gate.ConsumeNext(2'200, 2'200).disposition,
            GateDisposition::Anchored);
  EXPECT_EQ(gate.Watermark(), watermark + 1);
  EXPECT_FALSE(gate.BindResetContext(1'999, 4, 5, 6, 2));
}

namespace
{
AdmissionToken Token(std::uint8_t value)
{
  AdmissionToken token{};
  token.fill(value);
  return token;
}
GateBinding AdmissionBinding()
{
  auto binding = Binding();
  binding.require_policy_admission = true;
  binding.expected_step_index = 0;
  binding.next_policy_sequence = 0;
  binding.expected_transition_id.clear();
  return binding;
}
void BindFirstAdmission(ReceiptGate &gate)
{
  AcceptAnchor(gate);
  ASSERT_TRUE(gate.SetExpectedPolicyStep(1, 1, "policy-uuid-1", 1'100,
                                        Token(1), 1'100, 2'000));
}
ReceiptFacts AdmissionPolicy()
{
  auto policy = Policy();
  policy.stamp_ns = 1'200;
  return policy;
}
}

TEST(ReceiptAdmission, ReceiptFirstDoesNotPromoteOrRefreshUntilMatchingSample)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  const auto waiting = gate.ConsumeNext(1'300, 3'000);
  EXPECT_EQ(waiting.disposition, GateDisposition::Inhibited);
  EXPECT_EQ(waiting.reason, "waiting_for_matching_admission");
  EXPECT_FALSE(waiting.refresh_watchdog);
  EXPECT_EQ(gate.Watermark(), 100u);
  EXPECT_EQ(gate.LastAcceptedSteadyNs(), 2'000);
  EXPECT_TRUE(gate.HasPendingPolicyStep());
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(1), 1'201, 3'001));
  const auto applied = gate.ConsumeNext(1'400, 3'002);
  ASSERT_EQ(applied.disposition, GateDisposition::Applied);
  EXPECT_EQ(gate.Watermark(), 101u);
  EXPECT_FALSE(gate.HasPendingPolicyStep());
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 4'000));
  EXPECT_EQ(gate.ConsumeNext(1'500, 4'000).disposition, GateDisposition::Duplicate);
  EXPECT_EQ(gate.LastAcceptedSteadyNs(), 3'000);
}

TEST(ReceiptAdmission, AdmissionFirstRejectsWrongEmptyAndPreBindSamples)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(0), 1'201, 3'001));
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(2), 1'201, 3'001));
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(1), 1'100, 3'001));
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(1), 1'201, 1'999));
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(1), 1'201, 2'001));
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  EXPECT_EQ(gate.ConsumeNext(1'400, 3'000).disposition, GateDisposition::Applied);
}

TEST(ReceiptAdmission, ReceiptWaitExpiresWithoutApplyAtFortyMilliseconds)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  EXPECT_EQ(gate.ConsumeNext(1'300, 40'002'999).disposition, GateDisposition::Inhibited);
  const auto expired = gate.ConsumeNext(1'400, 40'003'000);
  EXPECT_EQ(expired.disposition, GateDisposition::Faulted);
  EXPECT_EQ(expired.reason, "policy_admission_wait_expired");
  EXPECT_EQ(gate.Watermark(), 100u);
  EXPECT_EQ(gate.LastAcceptedSteadyNs(), 2'000);
}

TEST(ReceiptAdmission, SafeStopBehindWaitingPolicyClosesBeforeAnyPolicyApply)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  auto stop = Anchor();
  stop.key.publish_sequence = 102;
  stop.sequence = 2;
  stop.stamp_ns = 1'300;
  ASSERT_TRUE(gate.Enqueue(stop, 3'001));
  const auto closed = gate.ConsumeNext(1'400, 3'002);
  EXPECT_EQ(closed.disposition, GateDisposition::Faulted);
  EXPECT_EQ(closed.reason, "safe_stop_cancelled_queued_policy_before_apply");
  EXPECT_EQ(gate.Watermark(), 100u);
  EXPECT_FALSE(closed.accepted);
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(1), 1'400, 3'003));
}

TEST(ReceiptAdmission, SafeStopRevokesPreviouslyOpenTokenAndLatePolicy)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(1), 1'201, 2'001));
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  ASSERT_EQ(gate.ConsumeNext(1'400, 3'000).disposition, GateDisposition::Applied);
  auto stop = Anchor();
  stop.key.publish_sequence = 102;
  stop.sequence = 2;
  stop.stamp_ns = 1'400;
  ASSERT_TRUE(gate.Enqueue(stop, 3'001));
  const auto closed = gate.ConsumeNext(1'500, 3'002);
  ASSERT_EQ(closed.disposition, GateDisposition::Applied);
  ASSERT_TRUE(closed.accepted);
  EXPECT_EQ(closed.accepted->source, 4);
  EXPECT_FALSE(gate.RecordPolicyAdmission(Token(1), 1'500, 3'003));
  auto late = AdmissionPolicy(); late.key.publish_sequence = 103; late.stamp_ns = 1'600;
  ASSERT_TRUE(gate.Enqueue(late, 3'004));
  EXPECT_EQ(gate.ConsumeNext(1'700, 3'005).reason, "policy_admission_revoked");
  EXPECT_EQ(gate.Watermark(), 102u);
}

TEST(ReceiptAdmission, CurrentTokenCannotPromoteNewPendingSlot)
{
  ReceiptGate gate(AdmissionBinding());
  BindFirstAdmission(gate);
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(1), 1'201, 2'001));
  ASSERT_TRUE(gate.Enqueue(AdmissionPolicy(), 3'000));
  ASSERT_EQ(gate.ConsumeNext(1'400, 3'000).disposition, GateDisposition::Applied);
  ASSERT_TRUE(gate.SetExpectedPolicyStep(2, 2, "policy-uuid-2", 1'400,
                                        Token(2), 1'400, 3'001));
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(1), 1'501, 3'002));
  auto next = AdmissionPolicy(); next.key.publish_sequence = 102;
  next.step_index = next.sequence = 2; next.transition_id = "policy-uuid-2"; next.stamp_ns = 1'500;
  ASSERT_TRUE(gate.Enqueue(next, 3'003));
  EXPECT_EQ(gate.ConsumeNext(1'600, 3'004).disposition, GateDisposition::Inhibited);
  EXPECT_EQ(gate.Watermark(), 101u);
  ASSERT_TRUE(gate.RecordPolicyAdmission(Token(2), 1'501, 3'004));
  EXPECT_EQ(gate.ConsumeNext(1'600, 3'005).disposition, GateDisposition::Applied);
  EXPECT_EQ(gate.Watermark(), 102u);
}

TEST(ReceiptResetFence, DuplicateAcrossResetDoesNotRefreshAndConflictsFault)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  ASSERT_TRUE(gate.PinResetFence(100));
  ASSERT_TRUE(gate.Enqueue(Anchor(), 3'000));
  EXPECT_EQ(gate.ConsumeNext(2'000, 3'000).disposition, GateDisposition::Duplicate);
  EXPECT_EQ(gate.LastAcceptedSteadyNs(), 2'000);
  ASSERT_TRUE(gate.BindResetContext(2'000, 3, 4, 5, 2));
  ASSERT_TRUE(gate.Enqueue(Anchor(), 4'000));
  EXPECT_EQ(gate.ConsumeNext(2'100, 4'000).disposition, GateDisposition::Duplicate);
  EXPECT_EQ(gate.Watermark(), 100u);
  auto conflict = Anchor(); conflict.twist[0] = 0.1;
  ASSERT_TRUE(gate.Enqueue(conflict, 4'001));
  EXPECT_EQ(gate.ConsumeNext(2'100, 4'001).reason, "publication_key_content_conflict");
}

TEST(ReceiptResetFence, ReceiptBeyondPinnedWatermarkFaultsWithoutApply)
{
  ReceiptGate gate(Binding()); AcceptAnchor(gate);
  ASSERT_TRUE(gate.PinResetFence(100));
  EXPECT_FALSE(gate.Enqueue(Policy(), 3'000));
  EXPECT_TRUE(gate.Faulted());
  EXPECT_EQ(gate.FaultReason(), "receipt_beyond_reset_fence");
  EXPECT_EQ(gate.Watermark(), 100u);
}
