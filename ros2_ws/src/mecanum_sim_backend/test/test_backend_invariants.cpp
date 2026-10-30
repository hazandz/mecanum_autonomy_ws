#include <gtest/gtest.h>
#include <limits>
#include "mecanum_sim_backend/backend_system.hpp"
using namespace mecanum_sim_backend;

TEST(BackendInvariants, BodyFrameConversionPreservesVyAndMeasuredVerticalComponents)
{
  const double h=0.7071067811865476;
  MeasuredWorldTwist3D measured{{0,1,0.2},{0.1,0.2,0.3}}; std::string reason;
  auto body=ComposeBodyPlanarCommand(measured,{0,0,h,h},0.2,-0.1,0.4,reason);
  ASSERT_TRUE(body.has_value()) << reason;
  EXPECT_NEAR(body->linear[0],0.2,1e-12); EXPECT_NEAR(body->linear[1],-0.1,1e-12);
  EXPECT_NEAR(body->linear[2],0.2,1e-12); EXPECT_NEAR(body->angular[0],0.2,1e-12);
  EXPECT_NEAR(body->angular[1],-0.1,1e-12); EXPECT_NEAR(body->angular[2],0.4,1e-12);
}

TEST(BackendInvariants, ConvertsYawPlusMinusNinetyWithoutDoubleRotation)
{
  std::string reason; MeasuredWorldTwist3D m{{0,1,0},{0,0,0}};
  auto positive=ComposeBodyPlanarCommand(m,{0,0,0.7071067811865476,0.7071067811865476},0.25,-0.20,0.80,reason);
  ASSERT_TRUE(positive); EXPECT_DOUBLE_EQ(positive->linear[0],0.25); EXPECT_DOUBLE_EQ(positive->linear[1],-0.20);
  auto negative=ComposeBodyPlanarCommand(m,{0,0,-0.7071067811865476,0.7071067811865476},0.25,-0.20,0.80,reason);
  ASSERT_TRUE(negative); EXPECT_DOUBLE_EQ(negative->linear[0],0.25); EXPECT_DOUBLE_EQ(negative->linear[1],-0.20);
}

TEST(BackendInvariants, RollPitchOrientationAndMissingMeasurementFailClosed)
{
  std::string reason; MeasuredWorldTwist3D m{{0.2,0.3,0.4},{0.1,0.2,0.3}};
  auto body=ComposeBodyPlanarCommand(m,{0.2,0.3,0.1,0.9},0.25,0.2,0.8,reason);
  ASSERT_TRUE(body); EXPECT_DOUBLE_EQ(body->linear[0],0.25); EXPECT_DOUBLE_EQ(body->linear[1],0.2);
  m.linear[2]=std::numeric_limits<double>::quiet_NaN();
  EXPECT_FALSE(ComposeBodyPlanarCommand(m,{0,0,0,1},0.1,0.1,0.1,reason));
  EXPECT_EQ(reason,"missing_or_non_finite_linear_measurement");
}

TEST(BackendInvariants, ZeroCommandIsNotAZeroMeasurement)
{
  MeasuredWorldTwist3D missing{{NAN,0,0},{0,0,0}}; std::string reason;
  EXPECT_FALSE(ComposeBodyPlanarCommand(missing,{0,0,0,1},0,0,0,reason));
}
