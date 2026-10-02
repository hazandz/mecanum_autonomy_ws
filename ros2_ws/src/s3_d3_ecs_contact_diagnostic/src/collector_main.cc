#include <iostream>

#include "s3_d3_ecs_contact_diagnostic/collector.hh"

int main(int argc, char **argv)
{
  s3_d3::ecs_contact::CollectorCommandLine command_line;
  std::string reason;
  // Parsing completes before ReceiptCollector constructs its transport Node.
  if (!s3_d3::ecs_contact::ParseCollectorCommandLine(argc, argv, &command_line, &reason)) {
    std::cerr << reason << '\n';
    return 2;
  }
  s3_d3::ecs_contact::ReceiptCollector collector(
      std::move(command_line.config), std::move(command_line.output_directory));
  if (!collector.Subscribe()) return 3;
  return collector.WaitForTerminal();
}
