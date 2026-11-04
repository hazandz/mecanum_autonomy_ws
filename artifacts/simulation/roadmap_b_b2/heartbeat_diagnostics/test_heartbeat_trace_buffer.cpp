#include "heartbeat_trace_buffer.hpp"

#include <fcntl.h>
#include <unistd.h>
#include <string>

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  const int fd = open(argv[1], O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (fd < 0) return 3;
  constexpr std::uint32_t capacity = 4;
  if (ftruncate(fd, heartbeat_trace::header_size + capacity * heartbeat_trace::record_size)) {
    close(fd); return 4;
  }
  const std::string mode = argv[2];
  heartbeat_trace::Writer writer(fd, capacity, "collection-1", "session-1", 42,
                                 "config-1", "world-1", "fake-monotonic", "backend",
                                 "fixture-clock-v1");
  writer.append(1, 100, 0, "begin");
  writer.append(2, 200, 7, "status");
  if (mode == "partial") {
    writer.append(2, 300, 8, "partial", false);
    _exit(0);
  }
  writer.append(3, 400, 0, "end");
  if (mode == "overflow") {
    writer.append(2, 500, 9, "extra");
    if (writer.append(2, 600, 10, "overflow")) return 5;
  }
  if (mode == "abrupt") _exit(0);
  if (mode == "reuse") {
    try {
      heartbeat_trace::Writer second(fd, capacity, "collection-1", "session-1", 42,
                                     "config-1", "world-1", "fake-monotonic", "backend",
                                     "fixture-clock-v1");
      return 7;
    } catch (const std::runtime_error &) {
      // Existing bytes must not be overwritten.
    }
  }
  if (mode != "normal" && mode != "overflow" && mode != "reuse") return 6;
  close(fd);
  return 0;
}
