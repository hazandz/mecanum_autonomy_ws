#ifndef S3_D3_ECS_CONTACT_DIAGNOSTIC_RUN_SPEC_HH_
#define S3_D3_ECS_CONTACT_DIAGNOSTIC_RUN_SPEC_HH_

#include <filesystem>
#include <string>

#include "s3_d3_ecs_contact_diagnostic/core.hh"

namespace s3_d3::ecs_contact
{
// Immutable caller-owned inputs for rendering one dedicated diagnostic world.
// Construction and rendering are filesystem-only; neither operation launches
// Gazebo, creates a transport node, or acquires any execution authority.
struct DiagnosticRunSpec {
  DiagnosticConfig config;
  std::filesystem::path base_world_template;
  std::filesystem::path rendered_world;
  std::filesystem::path result_receipt;
};

struct RenderedDiagnosticWorld {
  std::string base_world_template_sha256;
  std::string rendered_world_sha256;
};

// Strict argv parser shared by the executable and offline unit tests.
// It accepts no defaults, unknown options, duplicate options, or relative paths.
bool ParseWorldRendererCommandLine(int _argc, char **_argv,
                                   DiagnosticRunSpec *_spec,
                                   std::string *_reason);

bool ValidateDiagnosticRunSpec(const DiagnosticRunSpec &_spec, std::string *_reason);
bool RenderDiagnosticWorld(const DiagnosticRunSpec &_spec,
                           RenderedDiagnosticWorld *_result,
                           std::string *_reason);
}  // namespace s3_d3::ecs_contact

#endif
