#ifndef HEADER_FREQ_TABLES
#define HEADER_FREQ_TABLES

#include <vector>
#include <utility>
using std::vector;
using std::pair;

struct FreqTables {
 public:
  static vector<pair<unsigned int, long> > request_freq_table;
  static vector<pair<unsigned int, long> > response_freq_table;
};

#endif
