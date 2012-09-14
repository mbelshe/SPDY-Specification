#include "bit_bucket.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"

int main(int argc, char** argv) {
  vector<Frame> requests;
  vector<Frame> responses;
  if (!TrivialHTTPParse::ParseFile(argv[1], &requests, &responses)) {
    cerr << "Failed to parse correctly. Exiting\n";
    return EXIT_FAILURE;
  }
  for (unsigned int i = 0; i < requests.size(); ++i) {
    for (Frame::Lines::const_iterator l_it = requests[i].lines.begin();
         l_it != requests[i].lines.end();
         ++l_it) {
      auto line = *l_it;
      const string& k = line.first;
      const string& v = line.second;
      cout << k << ": " << v << "\n";
    }
    cout << "\n";
    for (Frame::Lines::const_iterator l_it = responses[i].lines.begin();
         l_it != responses[i].lines.end();
         ++l_it) {
      auto line = *l_it;
      const string& k = line.first;
      const string& v = line.second;
      cout << k << ": " << v << "\n";
    }
    cout << "\n";
  }
}
