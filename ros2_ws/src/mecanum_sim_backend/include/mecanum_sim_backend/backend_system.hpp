#pragma once

#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <utility>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "mecanum_sim_backend/receipt_gate.hpp"

namespace mecanum_sim_backend
{
struct BodyCommand3D
{
  std::array<double, 3> linear{};
  std::array<double, 3> angular{};
};
struct MeasuredWorldTwist3D
{
  std::array<double, 3> linear{};
  std::array<double, 3> angular{};
};
struct ContactPairClassification
{
  bool tracked{};
  bool exact_floor_pair{};
  bool wheel_floor_ignore{};
  std::string tracked_collision;
};

struct AppliedReceiptFact
{
  std::uint64_t publisher_instance_id{};
  std::uint64_t publish_sequence{};
  std::uint64_t physics_iteration{};
  std::int64_t sim_stamp_ns{};
  bool receipt_valid{};
  bool local_zero_override{};
};

struct ContactHistoryFact
{
  std::uint64_t physics_iteration{};
  std::int64_t sim_stamp_ns{};
  bool coverage_complete{};
  bool healthy{};
  bool contact_active{};
};

struct Observation0ProofResult
{
  bool valid{};
  const char *reason{"observation0_proof_invalid"};
};

inline bool IsZeroSafeStop(const ReceiptFacts &receipt)
{
  return receipt.source == 4 && receipt.step_index == 0 &&
      receipt.transition_id.empty() &&
      std::all_of(receipt.twist.begin(), receipt.twist.end(),
          [](double value) { return std::isfinite(value) && value == 0.0; });
}

inline Observation0ProofResult ValidateObservation0Proof(
    const std::vector<ReceiptFacts> &publications,
    const std::vector<AppliedReceiptFact> &applications,
    const std::vector<ContactHistoryFact> &contacts,
    const std::string &session_id, const std::string &config_hash,
    std::uint64_t publisher_instance_id,
    std::uint64_t safe_stop_source_instance_id,
    std::uint64_t episode_generation, std::uint32_t reset_epoch,
    std::uint32_t runtime_generation, std::int64_t barrier_ns,
    std::uint64_t selected_sequence, std::uint64_t adjacent_sequence,
    std::int64_t cutoff_ns, std::int64_t now_ns)
{
  if (publisher_instance_id == 0 || safe_stop_source_instance_id == 0 ||
      selected_sequence == 0 ||
      selected_sequence == std::numeric_limits<std::uint64_t>::max() ||
      adjacent_sequence != selected_sequence + 1 ||
      cutoff_ns <= barrier_ns || cutoff_ns > now_ns)
    return {false, "observation0_context_or_cutoff_invalid"};

  const ReceiptFacts *selected = nullptr;
  const ReceiptFacts *adjacent = nullptr;
  for (const auto &receipt : publications)
  {
    if (receipt.key.publisher_instance_id != publisher_instance_id ||
        receipt.session_id != session_id || receipt.config_hash != config_hash ||
        receipt.episode_generation != episode_generation ||
        receipt.reset_epoch != reset_epoch ||
        receipt.runtime_generation != runtime_generation ||
        receipt.frame_id != "base_link" || receipt.stamp_ns < 0 ||
        receipt.stamp_ns > now_ns)
      continue;
    if (receipt.key.publish_sequence == selected_sequence) selected = &receipt;
    if (receipt.key.publish_sequence == adjacent_sequence) adjacent = &receipt;
  }
  if (!selected || selected->source_instance_id != safe_stop_source_instance_id ||
      !IsZeroSafeStop(*selected) || selected->stamp_ns <= barrier_ns ||
      selected->stamp_ns > cutoff_ns || now_ns - selected->stamp_ns > 500'000'000)
    return {false, "observation0_selected_zero_receipt_missing_or_invalid"};
  if (!adjacent || adjacent->stamp_ns <= cutoff_ns ||
      adjacent->stamp_ns > now_ns || now_ns - adjacent->stamp_ns > 500'000'000)
    return {false, "observation0_adjacent_boundary_missing_or_invalid"};

  const AppliedReceiptFact *application = nullptr;
  for (const auto &fact : applications)
  {
    if (fact.publisher_instance_id == publisher_instance_id &&
        fact.publish_sequence == selected_sequence && fact.receipt_valid &&
        !fact.local_zero_override)
    {
      application = &fact;
      break;
    }
  }
  if (!application || application->physics_iteration == 0 ||
      application->sim_stamp_ns < selected->stamp_ns ||
      application->sim_stamp_ns > cutoff_ns)
    return {false, "observation0_selected_receipt_not_applied_by_cutoff"};

  bool began = false;
  std::uint64_t previous_iteration = 0;
  std::int64_t previous_stamp = -1;
  bool reached_cutoff = false;
  for (const auto &sample : contacts)
  {
    if (sample.physics_iteration < application->physics_iteration) continue;
    if (!began)
    {
      if (sample.physics_iteration != application->physics_iteration ||
          sample.sim_stamp_ns < application->sim_stamp_ns)
        return {false, "observation0_contact_history_start_missing"};
      began = true;
    }
    else if (sample.physics_iteration != previous_iteration + 1 ||
             sample.sim_stamp_ns < previous_stamp)
    {
      return {false, "observation0_contact_history_gap_or_rollback"};
    }
    if (!sample.coverage_complete || !sample.healthy)
      return {false, "observation0_contact_history_unhealthy"};
    if (sample.sim_stamp_ns <= cutoff_ns && sample.contact_active)
      return {false, "observation0_contact_active_before_cutoff"};
    previous_iteration = sample.physics_iteration;
    previous_stamp = sample.sim_stamp_ns;
    if (sample.sim_stamp_ns >= cutoff_ns)
    {
      reached_cutoff = true;
      break;
    }
  }
  if (!began || !reached_cutoff)
    return {false, "observation0_contact_history_does_not_cover_cutoff"};
  return {true, "observation0_proof_valid"};
}

inline bool IsUniqueWorldModel(
    std::uint64_t expected_model, std::uint64_t expected_world,
    const std::vector<std::pair<std::uint64_t, std::uint64_t>> &same_name_models)
{
  return expected_model != 0 && expected_world != 0 &&
         same_name_models.size() == 1 &&
         same_name_models.front() ==
             std::make_pair(expected_model, expected_world);
}

inline bool IsForwardResetContext(
    std::uint64_t old_lifecycle_sequence,
    std::uint64_t new_lifecycle_sequence,
    std::int64_t old_barrier_stamp_ns,
    std::int64_t new_barrier_stamp_ns,
    std::uint64_t old_episode_generation,
    std::uint64_t new_episode_generation,
    std::uint32_t old_reset_epoch,
    std::uint32_t new_reset_epoch,
    std::uint32_t old_runtime_generation,
    std::uint32_t new_runtime_generation,
    std::uint64_t expected_safe_stop_sequence,
    std::uint64_t requested_safe_stop_sequence)
{
  const bool generations_forward =
      new_episode_generation >= old_episode_generation &&
      new_reset_epoch >= old_reset_epoch &&
      new_runtime_generation >= old_runtime_generation;
  const bool generation_advanced =
      new_episode_generation > old_episode_generation ||
      new_reset_epoch > old_reset_epoch ||
      new_runtime_generation > old_runtime_generation;
  return new_lifecycle_sequence > old_lifecycle_sequence &&
         new_barrier_stamp_ns > old_barrier_stamp_ns &&
         generations_forward && generation_advanced &&
         requested_safe_stop_sequence == expected_safe_stop_sequence;
}

inline ContactPairClassification ClassifyContactPair(
    std::uint64_t collision1, std::uint64_t collision2,
    std::uint64_t exact_floor_collision,
    const std::unordered_map<std::uint64_t, std::string> &tracked_collisions,
    const std::unordered_set<std::string> &wheel_floor_collisions)
{
  const auto first = tracked_collisions.find(collision1);
  const auto second = tracked_collisions.find(collision2);
  const bool first_tracked = first != tracked_collisions.end();
  const bool second_tracked = second != tracked_collisions.end();
  if (!first_tracked && !second_tracked) return {};
  const auto &tracked = first_tracked ? first->second : second->second;
  const bool floor_pair =
      (collision1 == exact_floor_collision && second_tracked) ||
      (collision2 == exact_floor_collision && first_tracked);
  return {
      true, floor_pair,
      floor_pair && wheel_floor_collisions.find(tracked) !=
                        wheel_floor_collisions.end(),
      tracked,
  };
}

inline std::array<double, 3> RotateWorldToBody(
    const std::array<double, 3> &v, const std::array<double, 4> &q)
{
  const double x = -q[0], y = -q[1], z = -q[2], w = q[3];
  const double tx = 2.0 * (y * v[2] - z * v[1]);
  const double ty = 2.0 * (z * v[0] - x * v[2]);
  const double tz = 2.0 * (x * v[1] - y * v[0]);
  return {v[0] + w * tx + (y * tz - z * ty),
          v[1] + w * ty + (z * tx - x * tz),
          v[2] + w * tz + (x * ty - y * tx)};
}

inline std::optional<BodyCommand3D> ComposeBodyPlanarCommand(
    const MeasuredWorldTwist3D &measurement,
    const std::array<double, 4> &world_from_body_xyzw,
    double vx, double vy, double wz, std::string &reason)
{
  const auto finite = [](double v) { return std::isfinite(v); };
  for (double v : measurement.linear) if (!finite(v)) { reason = "missing_or_non_finite_linear_measurement"; return std::nullopt; }
  for (double v : measurement.angular) if (!finite(v)) { reason = "missing_or_non_finite_angular_measurement"; return std::nullopt; }
  for (double v : world_from_body_xyzw) if (!finite(v)) { reason = "non_finite_orientation"; return std::nullopt; }
  if (!finite(vx) || !finite(vy) || !finite(wz)) { reason = "non_finite_command"; return std::nullopt; }
  double norm2 = 0.0;
  for (double v : world_from_body_xyzw) norm2 += v * v;
  if (norm2 < 1e-12) { reason = "invalid_orientation"; return std::nullopt; }
  const double inverse_norm = 1.0 / std::sqrt(norm2);
  std::array<double, 4> q{};
  for (std::size_t i = 0; i < q.size(); ++i) q[i] = world_from_body_xyzw[i] * inverse_norm;
  const auto linear = RotateWorldToBody(measurement.linear, q);
  const auto angular = RotateWorldToBody(measurement.angular, q);
  BodyCommand3D result{{vx, vy, linear[2]}, {angular[0], angular[1], wz}};
  reason.clear();
  return result;
}

inline bool FinitePoseAndTwist(const std::array<double, 7> &pose_xyzw,
                              const MeasuredWorldTwist3D &twist)
{
  for (double value : pose_xyzw) if (!std::isfinite(value)) return false;
  for (double value : twist.linear) if (!std::isfinite(value)) return false;
  for (double value : twist.angular) if (!std::isfinite(value)) return false;
  return pose_xyzw[3]*pose_xyzw[3] + pose_xyzw[4]*pose_xyzw[4] +
         pose_xyzw[5]*pose_xyzw[5] + pose_xyzw[6]*pose_xyzw[6] > 1e-12;
}
}  // namespace mecanum_sim_backend
