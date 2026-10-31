#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <cstddef>

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

enum class ProbePhase
{
  Idle,
  AwaitSpawn,
  AwaitFixture,
  AwaitContact,
  AwaitLift,
  AwaitSeparation,
  AwaitEmpty,
  AwaitRemove,
  AwaitRemoval,
  Verified,
  Failed,
  Cancelled,
};

enum class ProbeAdmission
{
  Ready,
  NotReady,
  FixtureConflict,
};

inline ProbeAdmission EvaluateProbeAdmission(
    bool lifecycle_matches, bool inhibited, bool world_paused,
    bool faulted, bool observation0_authorized, bool pending_policy,
    bool probe_busy, bool capability_verified, bool fixture_conflict,
    bool services_ready)
{
  if (fixture_conflict) return ProbeAdmission::FixtureConflict;
  if (!lifecycle_matches || !inhibited || world_paused || faulted ||
      observation0_authorized || pending_policy || probe_busy ||
      capability_verified || !services_ready)
    return ProbeAdmission::NotReady;
  return ProbeAdmission::Ready;
}

struct ProbeObservation
{
  std::uint64_t iteration{};
  std::int64_t sim_stamp_ns{};
  bool component_present{};
  bool coverage_complete{};
  bool paused{};
  bool exact_fixture_floor_pair{};
  bool exact_fixture_robot_pair{};
  bool normal_depth_valid{};
  bool fixture_measured_separated{};
};

class ContactProbeMachine
{
public:
  static constexpr std::int64_t kDeadlineNs = 5'000'000'000;
  static constexpr std::int64_t kCleanupReserveNs = 1'000'000'000;

  bool Start(std::uint64_t start_sequence, std::int64_t steady_now_ns);
  bool SpawnRequested();
  bool SpawnCompleted(bool success);
  bool BindFixture(std::uint64_t model_entity, std::uint64_t collision_entity,
                   std::uint64_t floor_entity);
  bool Observe(const ProbeObservation &sample);
  bool LiftRequested();
  bool LiftCompleted(bool service_success);
  bool RemoveRequested();
  bool RemoveCompleted(bool service_success);
  bool ObserveRemoval(bool fixture_absent);
  void Abort();
  void Invalidate();
  bool Expire(std::int64_t steady_now_ns);

  ProbePhase Phase() const;
  bool Running() const;
  bool NeedsCleanup() const;
  bool IsVerified() const;
  std::uint64_t StartSequence() const;
  std::int64_t DeadlineNs() const;
  std::uint16_t ContactSampleCount() const;
  std::uint16_t EmptySampleCount() const;
  std::uint64_t ModelEntity() const;
  std::uint64_t CollisionEntity() const;
  std::uint64_t FloorEntity() const;
  std::uint64_t FirstContactIteration() const;
  std::uint64_t LastContactIteration() const;
  std::int64_t FirstContactStampNs() const;
  std::int64_t LastContactStampNs() const;
  std::uint64_t FirstEmptyIteration() const;
  std::uint64_t LastEmptyIteration() const;
  std::int64_t FirstEmptyStampNs() const;
  std::int64_t LastEmptyStampNs() const;

private:
  void Fail(bool cancelled = false);
  bool Contiguous(std::uint64_t iteration, std::int64_t stamp_ns) const;

  ProbePhase phase_{ProbePhase::Idle};
  std::uint64_t start_sequence_{};
  std::int64_t deadline_ns_{};
  std::uint64_t model_entity_{};
  std::uint64_t collision_entity_{};
  std::uint64_t floor_entity_{};
  std::uint64_t contact_first_iteration_{};
  std::uint64_t contact_last_iteration_{};
  std::int64_t contact_first_stamp_ns_{};
  std::int64_t contact_last_stamp_ns_{};
  std::uint64_t empty_first_iteration_{};
  std::uint64_t empty_last_iteration_{};
  std::int64_t empty_first_stamp_ns_{};
  std::int64_t empty_last_stamp_ns_{};
  std::uint16_t contact_samples_{};
  std::uint16_t empty_samples_{};
  bool cleanup_needed_{};
  bool cancelled_{};
  bool proof_ready_for_teardown_{};
  bool deadline_expired_{};
  std::uint64_t last_observed_iteration_{};
  std::int64_t last_observed_stamp_ns_{-1};
};
}  // namespace mecanum_sim_backend
