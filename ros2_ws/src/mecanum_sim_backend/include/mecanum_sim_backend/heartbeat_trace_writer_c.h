#ifndef MECANUM_SIM_BACKEND_HEARTBEAT_TRACE_WRITER_C_H_
#define MECANUM_SIM_BACKEND_HEARTBEAT_TRACE_WRITER_C_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hbtrace_writer hbtrace_writer;
hbtrace_writer *hbtrace_open_path(const char *path, uint64_t device, uint64_t inode,
                                  uint32_t capacity, const char *collection,
                                  const char *session, uint64_t backend,
                                  const char *config, const char *world,
                                  const char *clock, const char *role,
                                  const char *provenance);
int hbtrace_append(hbtrace_writer *writer, uint32_t kind, uint64_t timestamp_ns,
                   uint64_t status_sequence, const unsigned char *payload,
                   size_t payload_size);
void hbtrace_close(hbtrace_writer *writer);
uint64_t hbtrace_clock_monotonic_ns(void);

#ifdef __cplusplus
}
#endif
#endif
