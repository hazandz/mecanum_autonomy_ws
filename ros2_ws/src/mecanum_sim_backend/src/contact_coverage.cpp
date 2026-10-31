#include "mecanum_sim_backend/contact_coverage.hpp"

#include <cmath>

namespace mecanum_sim_backend
{
namespace
{
constexpr std::uint32_t kFaultContactCoverage = 16;
constexpr std::uint32_t kFaultContactClassification = 32;
constexpr double kCos15 = 0.9659258262890683;
}

ContactCoverage::ContactCoverage(std::uint32_t count) : tracked_collision_count_(count)
{
  if (count == 0 || count > 64) segment_closed_ = true;
  else expected_mask_ = count == 64 ? ~std::uint64_t{0} :
      ((std::uint64_t{1} << count) - 1);
}

ContactDecision ContactCoverage::Observe(const ContactSample &s)
{
  ContactDecision out;
  out.contact_active = contact_active_;
  out.observed_mask = s.observed_mask;
  if (s.has_robot_external_contact)
  {
    out.contact_edge = !contact_active_;
    contact_active_ = true;
    empty_count_ = 0;
    empty_start_iteration_.reset();
    empty_start_stamp_ns_.reset();
    out.contact_active = true;
  }
  if (segment_closed_) { out.fault_flags = kFaultContactCoverage; out.reason = "segment_closed_requires_reset"; return out; }
  if (s.paused) { out.reason = "paused_no_coverage_progress"; return out; }
  if (s.required_mask != expected_mask_)
  {
    segment_closed_ = true;
    out.fault_flags = kFaultContactCoverage;
    out.reason = "required_collision_mask_mismatch";
    out.contact_active = contact_active_;
    return out;
  }
  if (!s.component_present || !s.capability_valid ||
      (s.observed_mask & expected_mask_) != expected_mask_ || s.sim_stamp_ns < 0)
  {
    if (s.component_present && !s.capability_valid &&
        (s.observed_mask & expected_mask_) == expected_mask_ && s.sim_stamp_ns >= 0)
    {
      out.fault_flags = kFaultContactCoverage;
      out.reason = "contact_capability_unverified";
      out.contact_active = contact_active_;
      return out;
    }
    segment_closed_ = true;
    out.fault_flags = kFaultContactCoverage;
    out.reason = !s.component_present ? "missing_contact_component" :
                 !s.capability_valid ? "contact_capability_unverified" : "incomplete_contact_coverage";
    out.contact_active = contact_active_;
    return out;
  }
  if (last_iteration_ && s.physics_iteration != *last_iteration_ + 1)
  {
    segment_closed_ = true;
    out.fault_flags = kFaultContactCoverage;
    out.reason = "physics_iteration_gap";
    out.contact_active = contact_active_;
    return out;
  }
  last_iteration_ = s.physics_iteration;
  bool collision = s.has_robot_external_contact;
  if (s.wheel_floor_pair)
  {
    if (s.wheel_floor_unclassifiable)
    {
      segment_closed_ = true;
      out.fault_flags = kFaultContactClassification | kFaultContactCoverage;
      out.reason = "wheel_floor_unclassifiable";
      out.contact_active = contact_active_;
      return out;
    }
    if (s.wheel_floor_contact)
      collision = true;
    else if (!s.wheel_floor_aggregated)
    {
    const bool finite_normal = std::isfinite(s.normal_x) && std::isfinite(s.normal_y) && std::isfinite(s.normal_z);
    const double norm = std::sqrt(s.normal_x*s.normal_x+s.normal_y*s.normal_y+s.normal_z*s.normal_z);
    if (!s.has_normal || !s.has_depth || !finite_normal || !std::isfinite(s.depth_m) ||
        norm <= 0.0 || s.depth_m < 0.0)
    {
      segment_closed_ = true;
      out.fault_flags = kFaultContactClassification | kFaultContactCoverage;
      out.reason = "wheel_floor_unclassifiable";
      out.contact_active = contact_active_;
      return out;
    }
    const double vertical_alignment = std::abs(s.normal_z) / norm;
    collision = collision || vertical_alignment < kCos15 || s.depth_m > 0.005;
    }
  }
  if (collision)
  {
    out.contact_edge = out.contact_edge || !contact_active_;
    contact_active_ = true;
    empty_count_ = 0;
    empty_start_iteration_.reset();
    empty_start_stamp_ns_.reset();
  }
  else if (contact_active_)
  {
    if (empty_count_ == 0)
    {
      empty_start_iteration_ = s.physics_iteration;
      empty_start_stamp_ns_ = s.sim_stamp_ns;
    }
    ++empty_count_;
    if (empty_count_ >= 3 && empty_start_iteration_ && empty_start_stamp_ns_ &&
        s.physics_iteration == *empty_start_iteration_ + 2 &&
        s.sim_stamp_ns - *empty_start_stamp_ns_ >= 20'000'000)
      contact_active_ = false;
  }
  out.healthy = true;
  out.coverage_complete = true;
  out.contact_active = contact_active_;
  out.reason = collision ? "covered_contact" : "covered_empty";
  return out;
}

void ContactCoverage::ResetSegment()
{
  last_iteration_.reset(); empty_start_iteration_.reset(); empty_start_stamp_ns_.reset();
  empty_count_ = 0; contact_active_ = false; segment_closed_ = false;
}
bool ContactCoverage::ContactActive() const { return contact_active_; }
bool ContactCoverage::SegmentClosed() const { return segment_closed_; }
std::uint64_t ContactCoverage::LastIteration() const { return last_iteration_.value_or(0); }

bool ContactProbeMachine::Start(
    std::uint64_t sequence, std::int64_t steady_now_ns)
{
  if (sequence == 0 || steady_now_ns < 0 || Running() || cleanup_needed_ ||
      phase_ == ProbePhase::Verified)
    return false;
  phase_ = ProbePhase::AwaitSpawn;
  start_sequence_ = sequence;
  deadline_ns_ = steady_now_ns + kDeadlineNs;
  model_entity_ = collision_entity_ = floor_entity_ = 0;
  contact_first_iteration_ = contact_last_iteration_ = 0;
  contact_first_stamp_ns_ = contact_last_stamp_ns_ = 0;
  empty_first_iteration_ = empty_last_iteration_ = 0;
  empty_first_stamp_ns_ = empty_last_stamp_ns_ = 0;
  contact_samples_ = empty_samples_ = 0;
  cleanup_needed_ = false;
  cancelled_ = false;
  proof_ready_for_teardown_ = false;
  deadline_expired_ = false;
  last_observed_iteration_ = 0;
  last_observed_stamp_ns_ = -1;
  return true;
}

bool ContactProbeMachine::SpawnRequested()
{
  return phase_ == ProbePhase::AwaitSpawn;
}

bool ContactProbeMachine::SpawnCompleted(bool success)
{
  if (phase_ != ProbePhase::AwaitSpawn) return false;
  if (!success) { Fail(); return false; }
  phase_ = ProbePhase::AwaitFixture;
  return true;
}

bool ContactProbeMachine::BindFixture(
    std::uint64_t model, std::uint64_t collision, std::uint64_t floor)
{
  if (phase_ != ProbePhase::AwaitFixture || model == 0 || collision == 0 ||
      floor == 0 || model == collision || collision == floor || model == floor)
  {
    Fail();
    return false;
  }
  model_entity_ = model;
  collision_entity_ = collision;
  floor_entity_ = floor;
  phase_ = ProbePhase::AwaitContact;
  return true;
}

bool ContactProbeMachine::Contiguous(
    std::uint64_t iteration, std::int64_t stamp_ns) const
{
  const auto last_iteration = phase_ == ProbePhase::AwaitContact ?
      contact_last_iteration_ : empty_last_iteration_;
  const auto last_stamp = phase_ == ProbePhase::AwaitContact ?
      contact_last_stamp_ns_ : empty_last_stamp_ns_;
  return iteration != 0 && stamp_ns >= 0 &&
      (last_iteration == 0 ||
       (iteration == last_iteration + 1 && stamp_ns > last_stamp));
}

bool ContactProbeMachine::Observe(const ProbeObservation &sample)
{
  if (sample.paused) return Running();
  if (phase_ != ProbePhase::AwaitContact &&
      phase_ != ProbePhase::AwaitSeparation &&
      phase_ != ProbePhase::AwaitEmpty)
    return false;
  if (sample.exact_fixture_robot_pair)
  {
    Fail();
    return false;
  }
  if (!sample.component_present || !sample.coverage_complete ||
      sample.iteration == 0 || sample.sim_stamp_ns < 0)
  {
    Fail();
    return false;
  }
  if ((last_observed_iteration_ != 0 &&
       sample.iteration != last_observed_iteration_ + 1) ||
      sample.sim_stamp_ns < last_observed_stamp_ns_)
  {
    Fail();
    return false;
  }
  last_observed_iteration_ = sample.iteration;
  last_observed_stamp_ns_ = sample.sim_stamp_ns;
  if (phase_ == ProbePhase::AwaitContact)
  {
    if (sample.exact_fixture_floor_pair)
    {
      if (!sample.normal_depth_valid ||
          !Contiguous(sample.iteration, sample.sim_stamp_ns))
      {
        Fail();
        return false;
      }
      if (contact_samples_ == 0)
      {
        contact_first_iteration_ = sample.iteration;
        contact_first_stamp_ns_ = sample.sim_stamp_ns;
      }
      ++contact_samples_;
      contact_last_iteration_ = sample.iteration;
      contact_last_stamp_ns_ = sample.sim_stamp_ns;
      if (contact_samples_ >= 3 &&
          contact_last_stamp_ns_ - contact_first_stamp_ns_ >= 20'000'000)
        phase_ = ProbePhase::AwaitLift;
    }
    else
    {
      contact_samples_ = 0;
      contact_first_iteration_ = contact_last_iteration_ = 0;
      contact_first_stamp_ns_ = contact_last_stamp_ns_ = 0;
    }
    return true;
  }
  if (phase_ == ProbePhase::AwaitSeparation)
  {
    if (sample.fixture_measured_separated)
      phase_ = ProbePhase::AwaitEmpty;
    return true;
  }
  if (sample.exact_fixture_floor_pair)
  {
    empty_samples_ = 0;
    empty_first_iteration_ = empty_last_iteration_ = 0;
    empty_first_stamp_ns_ = empty_last_stamp_ns_ = 0;
    return true;
  }
  if (!Contiguous(sample.iteration, sample.sim_stamp_ns))
  {
    Fail();
    return false;
  }
  if (empty_samples_ == 0)
  {
    empty_first_iteration_ = sample.iteration;
    empty_first_stamp_ns_ = sample.sim_stamp_ns;
  }
  ++empty_samples_;
  empty_last_iteration_ = sample.iteration;
  empty_last_stamp_ns_ = sample.sim_stamp_ns;
  if (empty_samples_ >= 3 &&
      empty_last_stamp_ns_ - empty_first_stamp_ns_ >= 20'000'000)
  {
    proof_ready_for_teardown_ = true;
    cleanup_needed_ = true;
    phase_ = ProbePhase::AwaitRemove;
  }
  return true;
}

bool ContactProbeMachine::LiftRequested()
{
  if (phase_ != ProbePhase::AwaitLift) return false;
  phase_ = ProbePhase::AwaitSeparation;
  return true;
}

bool ContactProbeMachine::LiftCompleted(bool service_success)
{
  if (phase_ != ProbePhase::AwaitSeparation) return false;
  if (!service_success) { Fail(); return false; }
  return true;
}

bool ContactProbeMachine::RemoveRequested()
{
  if (!cleanup_needed_ || model_entity_ == 0 ||
      (phase_ != ProbePhase::AwaitRemove && phase_ != ProbePhase::Failed &&
       phase_ != ProbePhase::Cancelled))
    return false;
  phase_ = ProbePhase::AwaitRemoval;
  return true;
}

bool ContactProbeMachine::RemoveCompleted(bool service_success)
{
  if (phase_ != ProbePhase::AwaitRemoval) return false;
  if (!service_success) { Fail(); return false; }
  return true;
}

bool ContactProbeMachine::ObserveRemoval(bool fixture_absent)
{
  if (phase_ != ProbePhase::AwaitRemoval || !fixture_absent) return false;
  cleanup_needed_ = false;
  phase_ = proof_ready_for_teardown_ && !cancelled_ && !deadline_expired_ ?
      ProbePhase::Verified : (cancelled_ ? ProbePhase::Cancelled : ProbePhase::Failed);
  return phase_ == ProbePhase::Verified;
}

void ContactProbeMachine::Fail(bool cancelled)
{
  cancelled_ = cancelled_ || cancelled;
  proof_ready_for_teardown_ = false;
  cleanup_needed_ = model_entity_ != 0;
  phase_ = cancelled_ ? ProbePhase::Cancelled : ProbePhase::Failed;
}

void ContactProbeMachine::Abort()
{
  if (phase_ == ProbePhase::AwaitRemoval)
  {
    cancelled_ = true;
    proof_ready_for_teardown_ = false;
    return;
  }
  Fail(true);
}

void ContactProbeMachine::Invalidate()
{
  if (phase_ == ProbePhase::Verified) phase_ = ProbePhase::Failed;
  else if (phase_ == ProbePhase::AwaitRemoval)
  {
    proof_ready_for_teardown_ = false;
    deadline_expired_ = true;
  }
  else if (Running()) Fail();
}

bool ContactProbeMachine::Expire(std::int64_t steady_now_ns)
{
  if (!Running())
    return false;
  const bool cleanup_in_flight = phase_ == ProbePhase::AwaitRemoval;
  const auto cutoff = cleanup_in_flight ? deadline_ns_ :
      deadline_ns_ - kCleanupReserveNs;
  if (steady_now_ns < cutoff) return false;
  if (cleanup_in_flight)
  {
    deadline_expired_ = true;
    proof_ready_for_teardown_ = false;
    return true;
  }
  Fail();
  return true;
}

ProbePhase ContactProbeMachine::Phase() const { return phase_; }
bool ContactProbeMachine::Running() const
{
  return phase_ == ProbePhase::AwaitSpawn || phase_ == ProbePhase::AwaitFixture ||
      phase_ == ProbePhase::AwaitContact || phase_ == ProbePhase::AwaitLift ||
      phase_ == ProbePhase::AwaitSeparation || phase_ == ProbePhase::AwaitEmpty ||
      phase_ == ProbePhase::AwaitRemove || phase_ == ProbePhase::AwaitRemoval;
}
bool ContactProbeMachine::NeedsCleanup() const { return cleanup_needed_; }
bool ContactProbeMachine::IsVerified() const { return phase_ == ProbePhase::Verified; }
std::uint64_t ContactProbeMachine::StartSequence() const { return start_sequence_; }
std::int64_t ContactProbeMachine::DeadlineNs() const { return deadline_ns_; }
std::uint16_t ContactProbeMachine::ContactSampleCount() const { return contact_samples_; }
std::uint16_t ContactProbeMachine::EmptySampleCount() const { return empty_samples_; }
std::uint64_t ContactProbeMachine::ModelEntity() const { return model_entity_; }
std::uint64_t ContactProbeMachine::CollisionEntity() const { return collision_entity_; }
std::uint64_t ContactProbeMachine::FloorEntity() const { return floor_entity_; }
std::uint64_t ContactProbeMachine::FirstContactIteration() const { return contact_first_iteration_; }
std::uint64_t ContactProbeMachine::LastContactIteration() const { return contact_last_iteration_; }
std::int64_t ContactProbeMachine::FirstContactStampNs() const { return contact_first_stamp_ns_; }
std::int64_t ContactProbeMachine::LastContactStampNs() const { return contact_last_stamp_ns_; }
std::uint64_t ContactProbeMachine::FirstEmptyIteration() const { return empty_first_iteration_; }
std::uint64_t ContactProbeMachine::LastEmptyIteration() const { return empty_last_iteration_; }
std::int64_t ContactProbeMachine::FirstEmptyStampNs() const { return empty_first_stamp_ns_; }
std::int64_t ContactProbeMachine::LastEmptyStampNs() const { return empty_last_stamp_ns_; }
}  // namespace mecanum_sim_backend
