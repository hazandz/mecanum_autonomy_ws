#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace mecanum_sim_backend
{
struct ContactSample
{
  std::uint64_t physics_iteration{};
  std::int64_t sim_stamp_ns{};
  std::uint64_t required_mask{};
  std::uint64_t observed_mask{};
  bool component_present{};
  bool capability_valid{};
  bool paused{};
  bool has_robot_external_contact{};
  bool wheel_floor_pair{};
  bool wheel_floor_aggregated{};
  bool wheel_floor_unclassifiable{};
  bool wheel_floor_contact{};
  bool has_normal{};
  double normal_x{};
  double normal_y{};
  double normal_z{};
  bool has_depth{};
  double depth_m{};
};

struct ContactDecision
{
  bool healthy{};
  bool coverage_complete{};
  bool contact_active{};
  bool contact_edge{};
  std::uint64_t observed_mask{};
  std::uint32_t fault_flags{};
  std::string reason;
};

class ContactCoverage
{
public:
  explicit ContactCoverage(std::uint32_t tracked_collision_count);
  ContactDecision Observe(const ContactSample &sample);
  void ResetSegment();
  bool ContactActive() const;
  bool SegmentClosed() const;
  std::uint64_t LastIteration() const;

private:
  std::uint32_t tracked_collision_count_{};
  std::uint64_t expected_mask_{};
  std::optional<std::uint64_t> last_iteration_;
  std::optional<std::uint64_t> empty_start_iteration_;
  std::optional<std::int64_t> empty_start_stamp_ns_;
  std::uint32_t empty_count_{};
  bool contact_active_{};
  bool segment_closed_{};
};
}  // namespace mecanum_sim_backend
