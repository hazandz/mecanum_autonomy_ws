#include <gtest/gtest.h>
#include "mecanum_sim_backend/contact_coverage.hpp"
using namespace mecanum_sim_backend;
namespace { ContactSample Empty(std::uint64_t i, std::int64_t t, std::uint64_t mask=7) { return {i,t,mask,mask,true,true,false,false,false,false,0,0,1,false,0}; } }

TEST(ContactCoverage, RequiresCompleteCoverageAndConsecutiveTwentyMillisecondClear)
{
  ContactCoverage coverage(3); auto contact=Empty(1,0); contact.has_robot_external_contact=true;
  auto first=coverage.Observe(contact); EXPECT_TRUE(first.contact_edge); EXPECT_TRUE(first.contact_active);
  EXPECT_TRUE(coverage.Observe(Empty(2,10'000'000)).contact_active);
  EXPECT_TRUE(coverage.Observe(Empty(3,20'000'000)).contact_active);
  EXPECT_FALSE(coverage.Observe(Empty(4,30'000'000)).contact_active);
}

TEST(ContactCoverage, PauseDoesNotAdvanceClearOrCoverage)
{
  ContactCoverage coverage(1); auto c=Empty(10,0,1); c.has_robot_external_contact=true;
  EXPECT_TRUE(coverage.Observe(c).contact_active);
  auto paused=Empty(11,20'000'000,1); paused.paused=true;
  EXPECT_FALSE(coverage.Observe(paused).healthy); EXPECT_TRUE(coverage.ContactActive());
  EXPECT_TRUE(coverage.Observe(Empty(11,10'000'000,1)).contact_active);
}

TEST(ContactCoverage, MissingNormalOrDepthIsUnhealthyWithoutInventedPulse)
{
  for (bool normal : {false,true}) for (bool depth : {false,true}) if (!normal || !depth)
  {
    ContactCoverage coverage(1); auto c=Empty(1,0,1); c.wheel_floor_pair=true;
    c.has_normal=normal; c.has_depth=depth; c.depth_m=0.001;
    const auto d=coverage.Observe(c); EXPECT_FALSE(d.healthy); EXPECT_FALSE(d.contact_active);
    EXPECT_NE(d.fault_flags & 32U, 0U);
  }
}

TEST(ContactCoverage, WheelFloorOnlyFilteredWithinApprovedNormalAndDepth)
{
  ContactCoverage coverage(1); auto c=Empty(1,0,1); c.wheel_floor_pair=true;
  c.has_normal=true; c.has_depth=true; c.depth_m=0.005; c.normal_z=1.0;
  EXPECT_FALSE(coverage.Observe(c).contact_active);
  coverage.ResetSegment(); c.physics_iteration=2; c.normal_x=0.5; c.normal_z=0.8660254038;
  EXPECT_TRUE(coverage.Observe(c).contact_active);
}

TEST(ContactCoverage, AggregatedContactsNeverHideAnUnclassifiableWheelFloorPair)
{
  ContactCoverage coverage(1); auto c=Empty(1,0,1); c.wheel_floor_pair=true;
  c.wheel_floor_contact=true; c.wheel_floor_unclassifiable=true;
  const auto d=coverage.Observe(c);
  EXPECT_FALSE(d.healthy); EXPECT_FALSE(d.contact_active);
  EXPECT_NE(d.fault_flags & 32U, 0U);
}

TEST(ContactCoverage, AggregatedNonIgnorableWheelFloorPairIsContact)
{
  ContactCoverage coverage(1); auto c=Empty(1,0,1); c.wheel_floor_pair=true;
  c.wheel_floor_contact=true;
  const auto d=coverage.Observe(c);
  EXPECT_TRUE(d.healthy); EXPECT_TRUE(d.contact_active); EXPECT_TRUE(d.contact_edge);
}

TEST(ContactCoverage, GapAndOverflowInputsCloseSegmentUntilReset)
{
  ContactCoverage coverage(65); auto d=coverage.Observe(Empty(1,0));
  EXPECT_FALSE(d.healthy); EXPECT_TRUE(coverage.SegmentClosed());
  coverage.ResetSegment(); ContactCoverage next(1); (void)next.Observe(Empty(1,0,1));
  d=next.Observe(Empty(3,20'000'000,1)); EXPECT_NE(d.fault_flags & 16U, 0U);
  EXPECT_TRUE(next.SegmentClosed());
}

TEST(ContactCoverage, RequiredMaskMustMatchManifestExactly)
{
  ContactCoverage coverage(2);
  const auto result=coverage.Observe(Empty(1,0,1));
  EXPECT_FALSE(result.healthy);
  EXPECT_EQ(result.reason,"required_collision_mask_mismatch");
}

TEST(ContactCoverage, ConfirmedPulseSurvivesConcurrentHealthFault)
{
  ContactCoverage coverage(1); auto c=Empty(1,0,1); c.has_robot_external_contact=true;
  EXPECT_TRUE(coverage.Observe(c).contact_active);
  c.physics_iteration=3; c.component_present=false;
  const auto d=coverage.Observe(c); EXPECT_FALSE(d.healthy); EXPECT_TRUE(d.contact_active);
}
