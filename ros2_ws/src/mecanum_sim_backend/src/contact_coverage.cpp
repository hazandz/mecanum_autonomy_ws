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
}  // namespace mecanum_sim_backend
