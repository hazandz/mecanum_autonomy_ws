#include "mecanum_sim_backend/receipt_gate.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <iterator>
#include <regex>
#include <utility>

namespace mecanum_sim_backend
{
namespace
{
bool IsZero(const ReceiptFacts &r)
{
  return std::all_of(r.twist.begin(), r.twist.end(),
                     [](double value) { return value == 0.0; });
}
bool ValidHash(const std::string &value)
{
  static const std::regex pattern("[0-9a-f]{64}");
  return std::regex_match(value, pattern);
}
}  // namespace

ReceiptGate::ReceiptGate(GateBinding binding)
: binding_(std::move(binding)),
  current_action_barrier_ns_(binding_.barrier_stamp_ns) {}

bool ReceiptGate::Enqueue(ReceiptFacts receipt, std::int64_t receive_steady_ns)
{
  if (faulted_) return false;
  if (reset_fence_ && receipt.key.publish_sequence > *reset_fence_)
  {
    Invalidate("receipt_beyond_reset_fence");
    return false;
  }
  if (receive_steady_ns < 0 || queue_.size() >= kQueueCapacity)
  {
    faulted_ = true;
    fault_reason_ = receive_steady_ns < 0 ? "invalid_receive_clock" : "queue_overflow";
    queue_.clear();
    return false;
  }
  queue_.push_back({std::move(receipt), receive_steady_ns});
  return true;
}

bool ReceiptGate::ValidPayload(const ReceiptFacts &r, std::string &reason) const
{
  if (r.session_id != binding_.session_id || r.config_hash != binding_.config_hash)
    reason = "session_or_config_mismatch";
  else if (!ValidHash(r.config_hash)) reason = "invalid_config_hash";
  else if (r.key.publisher_instance_id == 0 || r.key.publish_sequence == 0)
    reason = "invalid_publication_key";
  else if (binding_.final_publisher_instance_id == 0 ||
           r.key.publisher_instance_id != binding_.final_publisher_instance_id)
    reason = "final_publisher_instance_mismatch";
  else if (r.frame_id != binding_.frame_id) reason = "frame_mismatch";
  else if (r.episode_generation != binding_.episode_generation ||
           r.reset_epoch != binding_.reset_epoch ||
           r.runtime_generation != binding_.runtime_generation)
    reason = "lifecycle_mismatch";
  else if (r.stamp_ns <= binding_.barrier_stamp_ns) reason = "not_strictly_post_barrier";
  else if (r.stamp_ns < 0) reason = "invalid_stamp";
  else if (!std::all_of(r.twist.begin(), r.twist.end(),
                        [](double value) { return std::isfinite(value); }))
    reason = "non_finite_command";
  else if (r.twist[2] != 0.0 || r.twist[3] != 0.0 || r.twist[4] != 0.0)
    reason = "non_planar_command";
  else if (std::abs(r.twist[0]) > binding_.max_vx ||
           std::abs(r.twist[1]) > binding_.max_vy ||
           std::abs(r.twist[5]) > binding_.max_wz)
    reason = "command_outside_envelope";
  return reason.empty();
}

bool ReceiptGate::Equal(const ReceiptFacts &a, const ReceiptFacts &b)
{
  return a.session_id == b.session_id && a.config_hash == b.config_hash &&
         a.key.publisher_instance_id == b.key.publisher_instance_id &&
         a.key.publish_sequence == b.key.publish_sequence &&
         a.episode_generation == b.episode_generation &&
         a.reset_epoch == b.reset_epoch && a.runtime_generation == b.runtime_generation &&
         a.step_index == b.step_index && a.transition_id == b.transition_id &&
         a.source == b.source && a.sequence == b.sequence &&
         a.source_instance_id == b.source_instance_id && a.stamp_ns == b.stamp_ns &&
         a.frame_id == b.frame_id && a.twist == b.twist;
}

GateResult ReceiptGate::Fault(std::string reason)
{
  faulted_ = true;
  fault_reason_ = std::move(reason);
  queue_.clear();
  return {GateDisposition::Faulted, fault_reason_, std::nullopt, false};
}

GateResult ReceiptGate::ConsumeNext(std::int64_t now_ros_ns,
                                    std::int64_t now_steady_ns)
{
  if (faulted_) return {GateDisposition::Faulted, fault_reason_, std::nullopt, false};
  if (queue_.empty()) return {GateDisposition::Inhibited, "no_receipt", std::nullopt, false};
  const auto &item = queue_.front();
  const auto &r = item.facts;
  // Sau fence/reset, chỉ replay đúng bytes đã thấy mới vô hại; không làm mới TTL.
  const bool old_context = r.episode_generation != binding_.episode_generation ||
      r.reset_epoch != binding_.reset_epoch || r.runtime_generation != binding_.runtime_generation;
  if (old_context || reset_fence_ || (last_receipt_ &&
      r.key.publish_sequence == last_receipt_->key.publish_sequence))
  {
    const auto seen = std::find_if(replay_history_.begin(), replay_history_.end(),
        [&r](const auto &old) { return old.key.publisher_instance_id == r.key.publisher_instance_id &&
            old.key.publish_sequence == r.key.publish_sequence; });
    if (seen != replay_history_.end())
    {
      if (!Equal(r, *seen)) return Fault("publication_key_content_conflict");
      queue_.pop_front();
      return {GateDisposition::Duplicate, "exact_duplicate", std::nullopt, false};
    }
  }
  std::string reason;
  if (!ValidPayload(r, reason)) return Fault(reason);
  if (now_ros_ns < r.stamp_ns || now_steady_ns < item.receive_steady_ns)
    return Fault("future_timestamp");
  if (last_source_stamp_ns_ && r.stamp_ns < *last_source_stamp_ns_)
    return Fault("source_timestamp_rollback");
  if (now_ros_ns - r.stamp_ns > binding_.max_ros_age_ns ||
      now_steady_ns - item.receive_steady_ns > binding_.max_steady_age_ns)
    return Fault("stale_receipt");

  if (last_receipt_ && r.key.publisher_instance_id == last_receipt_->key.publisher_instance_id &&
      r.key.publish_sequence == last_receipt_->key.publish_sequence)
  {
    if (!Equal(r, *last_receipt_)) return Fault("publication_key_content_conflict");
    queue_.pop_front();
    return {GateDisposition::Duplicate, "exact_duplicate", std::nullopt, false};
  }
  if (r.key.publish_sequence <= watermark_)
  {
    queue_.pop_front();
    return {GateDisposition::Rejected, "replay_or_old_sequence", std::nullopt, false};
  }

  if (!anchored_)
  {
    if (r.source != 4 || r.source_instance_id != binding_.safe_stop_source_instance_id ||
        r.sequence != binding_.next_safe_stop_sequence ||
        r.step_index != 0 || !r.transition_id.empty() || !IsZero(r) ||
        (require_contiguous_anchor_ &&
         r.key.publish_sequence != watermark_ + 1) ||
        r.key.publish_sequence <= watermark_)
      return Fault("startup_anchor_requires_post_barrier_safe_stop_zero");
    if (binding_.next_safe_stop_sequence ==
        std::numeric_limits<std::uint64_t>::max())
      return Fault("safe_stop_source_sequence_exhausted");
    anchored_ = true;
    watermark_ = r.key.publish_sequence;
    ++binding_.next_safe_stop_sequence;
    last_receipt_ = r;
    last_source_stamp_ns_ = r.stamp_ns;
    last_accepted_steady_ns_ = item.receive_steady_ns;
    const auto accepted = r;
    replay_history_.push_back(accepted);
    if (replay_history_.size() > kQueueCapacity) replay_history_.pop_front();
    queue_.pop_front();
    return {GateDisposition::Anchored, "safe_stop_anchor", accepted, true};
  }
  if (r.key.publish_sequence != watermark_ + 1)
    return Fault("final_publication_sequence_gap");
  if (r.source == 1)
  {
    const bool valid_policy_source =
        r.source_instance_id == binding_.policy_source_instance_id &&
        r.step_index != 0 && !r.transition_id.empty();
    const bool matches_current =
        valid_policy_source &&
        r.sequence == binding_.next_policy_sequence &&
        r.step_index == binding_.expected_step_index &&
        r.transition_id == binding_.expected_transition_id;
    const bool matches_pending =
        valid_policy_source && pending_policy_ &&
        r.sequence == pending_policy_->source_sequence &&
        r.step_index == pending_policy_->step_index &&
        r.transition_id == pending_policy_->transition_id;
    if (!matches_current && !matches_pending)
      return Fault("policy_issuance_binding_mismatch");
    const auto action_barrier_ns = matches_pending ?
        pending_policy_->action_barrier_ns : current_action_barrier_ns_;
    if (r.stamp_ns <= action_barrier_ns)
    {
      queue_.pop_front();
      return {GateDisposition::Rejected, "not_strictly_post_action_barrier",
              std::nullopt, false};
    }
    if (binding_.require_policy_admission)
    {
      // Một SAFE_STOP hợp lệ đã tới trước apply phải đóng motion, dù còn key POLICY ở đầu queue.
      for (auto it = std::next(queue_.begin()); it != queue_.end(); ++it)
      {
        std::string stop_reason;
        if (it->facts.source == 4 && IsZero(it->facts) &&
            it->facts.source_instance_id == binding_.safe_stop_source_instance_id &&
            it->facts.sequence == binding_.next_safe_stop_sequence &&
            it->facts.step_index == 0 && it->facts.transition_id.empty() &&
            ValidPayload(it->facts, stop_reason) &&
            it->facts.stamp_ns <= now_ros_ns &&
            now_ros_ns - it->facts.stamp_ns <= binding_.max_ros_age_ns &&
            it->receive_steady_ns <= now_steady_ns &&
            now_steady_ns - it->receive_steady_ns <= binding_.max_steady_age_ns)
        {
          RevokePolicyAdmission();
          return Fault("safe_stop_cancelled_queued_policy_before_apply");
        }
      }
      const auto &slot = matches_pending ? pending_policy_ : current_policy_;
      if (!slot || std::all_of(slot->token.begin(), slot->token.end(), [](auto v) { return v == 0; }))
        return Fault("policy_admission_revoked");
      const bool ready = slot->admission &&
          slot->admission->first <= now_ros_ns &&
          now_ros_ns - slot->admission->first <= 250'000'000 &&
          slot->admission->second <= now_steady_ns &&
          now_steady_ns - slot->admission->second <= 250'000'000;
      if (!ready)
      {
        if (now_steady_ns - item.receive_steady_ns >= 40'000'000 || WatchdogExpired(now_steady_ns))
          return Fault("policy_admission_wait_expired");
        return {GateDisposition::Inhibited, "waiting_for_matching_admission", std::nullopt, false};
      }
    }
    if (matches_pending)
    {
      current_policy_ = pending_policy_;
      binding_.next_policy_sequence = pending_policy_->source_sequence;
      binding_.expected_step_index = pending_policy_->step_index;
      binding_.expected_transition_id = pending_policy_->transition_id;
      current_action_barrier_ns_ = pending_policy_->action_barrier_ns;
      pending_policy_.reset();
    }
  }
  else if (r.source == 4)
  {
    if (r.source_instance_id != binding_.safe_stop_source_instance_id ||
        r.sequence != binding_.next_safe_stop_sequence ||
        r.step_index != 0 || !r.transition_id.empty() || !IsZero(r))
      return Fault("safe_stop_identity_mismatch");
    if (binding_.next_safe_stop_sequence ==
        std::numeric_limits<std::uint64_t>::max())
      return Fault("safe_stop_source_sequence_exhausted");
    ++binding_.next_safe_stop_sequence;
    if (binding_.require_policy_admission) RevokePolicyAdmission();
  }
  else return Fault("unsupported_receipt_source");

  watermark_ = r.key.publish_sequence;
  last_receipt_ = r;
  last_source_stamp_ns_ = r.stamp_ns;
  last_accepted_steady_ns_ = item.receive_steady_ns;
  const auto accepted = r;
  replay_history_.push_back(accepted);
  if (replay_history_.size() > kQueueCapacity) replay_history_.pop_front();
  queue_.pop_front();
  return {GateDisposition::Applied, "accepted_once", accepted, true};
}

bool ReceiptGate::WatchdogExpired(std::int64_t now_steady_ns) const
{
  return faulted_ || (anchored_ && (now_steady_ns < last_accepted_steady_ns_ ||
         now_steady_ns - last_accepted_steady_ns_ > kWatchdogNs));
}
bool ReceiptGate::SetExpectedPolicyStep(std::uint64_t step_index,
                                       std::uint64_t source_sequence,
                                       std::string transition_id,
                                       std::int64_t action_barrier_ns,
                                       AdmissionToken token,
                                       std::int64_t bound_ros_ns,
                                       std::int64_t bound_steady_ns)
{
  if (action_barrier_ns == 0) action_barrier_ns = current_action_barrier_ns_;
  if (reset_fence_ || (binding_.require_policy_admission &&
      (bound_ros_ns < binding_.barrier_stamp_ns || bound_steady_ns < 0 ||
       std::all_of(token.begin(), token.end(), [](auto v) { return v == 0; })))) return false;
  if (faulted_ || pending_policy_ || step_index == 0 ||
      source_sequence != step_index || transition_id.empty() ||
      step_index <= binding_.expected_step_index ||
      action_barrier_ns < current_action_barrier_ns_ ||
      action_barrier_ns < binding_.barrier_stamp_ns)
    return false;
  pending_policy_ = PolicyIdentity{
      step_index, source_sequence, std::move(transition_id), action_barrier_ns,
      token, bound_ros_ns, bound_steady_ns, std::nullopt};
  return true;
}
bool ReceiptGate::BindResetContext(
    std::int64_t barrier_stamp_ns, std::uint64_t episode_generation,
    std::uint32_t reset_epoch, std::uint32_t runtime_generation,
    std::uint64_t next_safe_stop_sequence)
{
  const bool newer_generation =
      episode_generation >= binding_.episode_generation &&
      reset_epoch >= binding_.reset_epoch &&
      runtime_generation >= binding_.runtime_generation &&
      (episode_generation > binding_.episode_generation ||
       reset_epoch > binding_.reset_epoch ||
       runtime_generation > binding_.runtime_generation);
  if (barrier_stamp_ns <= binding_.barrier_stamp_ns || !newer_generation ||
      next_safe_stop_sequence != binding_.next_safe_stop_sequence)
    return false;
  binding_.barrier_stamp_ns = barrier_stamp_ns;
  current_action_barrier_ns_ = barrier_stamp_ns;
  binding_.episode_generation = episode_generation;
  binding_.reset_epoch = reset_epoch;
  binding_.runtime_generation = runtime_generation;
  binding_.next_policy_sequence = 0;
  binding_.expected_step_index = 0;
  binding_.next_policy_sequence = 0;
  binding_.expected_transition_id.clear();
  pending_policy_.reset();
  current_policy_.reset();
  reset_fence_.reset();
  queue_.clear();
  anchored_ = false;
  require_contiguous_anchor_ = true;
  faulted_ = false;
  fault_reason_.clear();
  return true;
}
void ReceiptGate::Invalidate(std::string reason) { faulted_ = true; fault_reason_ = std::move(reason); queue_.clear(); }
bool ReceiptGate::Faulted() const { return faulted_; }
std::uint64_t ReceiptGate::Watermark() const { return watermark_; }
std::uint64_t ReceiptGate::ExpectedSafeStopSequence() const
{
  return binding_.next_safe_stop_sequence;
}
bool ReceiptGate::HasPendingPolicyStep() const
{
  return pending_policy_.has_value();
}
std::int64_t ReceiptGate::LastAcceptedSteadyNs() const { return last_accepted_steady_ns_; }
std::string ReceiptGate::FaultReason() const { return fault_reason_; }

bool ReceiptGate::RecordPolicyAdmission(const AdmissionToken &token,
    std::int64_t source_ros_ns, std::int64_t receive_steady_ns)
{
  if (faulted_ || reset_fence_ || std::all_of(token.begin(), token.end(), [](auto v) { return v == 0; }))
    return false;
  for (auto *slot : {&pending_policy_, &current_policy_})
  {
    if (*slot && (*slot)->token == token && source_ros_ns > (*slot)->bound_ros_ns &&
        receive_steady_ns >= (*slot)->bound_steady_ns)
    {
      (*slot)->admission = std::make_pair(source_ros_ns, receive_steady_ns);
      return true;
    }
  }
  return false;
}
void ReceiptGate::RevokePolicyAdmission()
{
  pending_policy_.reset();
  if (current_policy_)
  {
    current_policy_->token.fill(0);
    current_policy_->admission.reset();
  }
}
bool ReceiptGate::PinResetFence(std::uint64_t sequence)
{
  if (faulted_ || reset_fence_ || !anchored_ || !queue_.empty() || pending_policy_ ||
      sequence == 0 || sequence != watermark_ || !last_receipt_ ||
      last_receipt_->source != 4 || !IsZero(*last_receipt_)) return false;
  RevokePolicyAdmission();
  reset_fence_ = sequence;
  return true;
}
bool ReceiptGate::ResetFenceHeld() const { return reset_fence_.has_value(); }
bool ReceiptGate::QueueEmpty() const { return queue_.empty(); }
}  // namespace mecanum_sim_backend
