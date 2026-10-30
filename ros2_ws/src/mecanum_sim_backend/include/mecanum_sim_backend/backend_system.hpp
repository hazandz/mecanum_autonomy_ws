#pragma once

#include <array>
#include <cmath>
#include <optional>
#include <string>

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
