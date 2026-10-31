#include "mecanum_sim_backend/receipt_gate.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
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

ReceiptGate::ReceiptGate(GateBinding binding) : binding_(std::move(binding)) {}

bool ReceiptGate::Enqueue(ReceiptFacts receipt, std::int64_t receive_steady_ns)
{
  if (faulted_) return false;
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
  auto item = std::move(queue_.front());
  queue_.pop_front();
  const auto &r = item.facts;
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
    return {GateDisposition::Duplicate, "exact_duplicate", std::nullopt, false};
  }
  if (r.key.publish_sequence <= watermark_)
    return {GateDisposition::Rejected, "replay_or_old_sequence", std::nullopt, false};

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
    return {GateDisposition::Anchored, "safe_stop_anchor", r, true};
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
    if (matches_pending)
    {
      binding_.next_policy_sequence = pending_policy_->source_sequence;
      binding_.expected_step_index = pending_policy_->step_index;
      binding_.expected_transition_id = pending_policy_->transition_id;
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
  }
  else return Fault("unsupported_receipt_source");

  watermark_ = r.key.publish_sequence;
  last_receipt_ = r;
  last_source_stamp_ns_ = r.stamp_ns;
  last_accepted_steady_ns_ = item.receive_steady_ns;
  return {GateDisposition::Applied, "accepted_once", r, true};
}

bool ReceiptGate::WatchdogExpired(std::int64_t now_steady_ns) const
{
  return faulted_ || (anchored_ && (now_steady_ns < last_accepted_steady_ns_ ||
         now_steady_ns - last_accepted_steady_ns_ > kWatchdogNs));
}
bool ReceiptGate::SetExpectedPolicyStep(std::uint64_t step_index,
                                       std::uint64_t source_sequence,
                                       std::string transition_id)
{
  if (faulted_ || pending_policy_ || step_index == 0 ||
      source_sequence != step_index || transition_id.empty() ||
      step_index <= binding_.expected_step_index)
    return false;
  pending_policy_ = PolicyIdentity{
      step_index, source_sequence, std::move(transition_id)};
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
  binding_.episode_generation = episode_generation;
  binding_.reset_epoch = reset_epoch;
  binding_.runtime_generation = runtime_generation;
  binding_.next_policy_sequence = 0;
  binding_.expected_step_index = 0;
  binding_.next_policy_sequence = 0;
  binding_.expected_transition_id.clear();
  pending_policy_.reset();
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
}  // namespace mecanum_sim_backend
