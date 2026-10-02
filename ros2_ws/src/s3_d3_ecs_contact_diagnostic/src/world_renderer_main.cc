#include <string>

#include "s3_d3_ecs_contact_diagnostic/run_spec.hh"

int main(int argc, char **argv)
{
  s3_d3::ecs_contact::DiagnosticRunSpec spec;
  std::string reason;
  if (!s3_d3::ecs_contact::ParseWorldRendererCommandLine(argc, argv, &spec, &reason)) {
    return 2;
  }
  s3_d3::ecs_contact::RenderedDiagnosticWorld result;
  return s3_d3::ecs_contact::RenderDiagnosticWorld(spec, &result, &reason) ? 0 : 3;
}
