#ifndef HEADER_FREQ_TABLES
#define HEADER_FREQ_TABLES

#include <stdint.h>

#include <vector>
#include <utility>

using std::vector;
using std::pair;

struct FreqTables {
 public:
  static vector<pair<uint16_t, uint32_t> > request_freq_table;
  static vector<pair<uint16_t, uint32_t> > response_freq_table;
};

#endif
