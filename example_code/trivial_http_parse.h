// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#ifndef TRIVIAL_HTTP_PARSE_H
#define TRIVIAL_HTTP_PARSE_H

#include <fstream>
#include <iostream>
#include <stdlib.h>

#include <string>
#include <vector>

using std::cerr;
//using std::cout;
using std::getline;
using std::ifstream;
using std::string;
using std::vector;
using std::istream;
using std::ostream;

struct KVPair {
  string key;
  string val;
  KVPair() {}
  KVPair(string key, string val) : key(key), val(val) {}
  friend ostream& operator<<(ostream& os, const KVPair& kv) {
    os << "\"" << kv.key << "\" \"" << kv.val << "\"";
    return os;
  }
  size_t size() const { return key.size() + val.size(); }
};

typedef vector<KVPair> Lines;

typedef Lines HeaderFrame;

class TrivialHTTPParse {
 private:
  static HeaderFrame* GetHeaderFramePtr(vector<HeaderFrame>* frames,
                                        unsigned int expected_previous_len) {
    if (frames->size() <= expected_previous_len) {
      frames->push_back(HeaderFrame());
    }
    return &(frames->back());
  }

 public:
  static int ParseFile(const string& fn,
                vector<HeaderFrame>* requests,
                vector<HeaderFrame>* responses) {
    ifstream ifs(fn.c_str());
    ParseStream(ifs, requests, responses);
    return 1;
  }
  static int ParseStream(istream& istrm,
                vector<HeaderFrame>* requests,
                vector<HeaderFrame>* responses) {
    int frames_len = 0;
    int frames_idx = 0;
    vector<HeaderFrame>* frames[2] = {requests, responses};
    if (!(requests->empty() && responses->empty())) {
      return -1;
    }
    HeaderFrame* cur_frame = GetHeaderFramePtr(frames[frames_idx], frames_len);

    while (istrm.good()) {
      string line;
      getline(istrm, line);
      size_t colon_pos = line.find_first_of(":", 1);
      if (line.size() == 0) {
        // finished with this frame.
        if (frames_idx == 1) ++frames_len;
        frames_idx = ! frames_idx;
        cur_frame = GetHeaderFramePtr(frames[frames_idx], frames_len);
        continue;
      } else if (colon_pos == string::npos ||
                 colon_pos + 1 > line.size() ||
                 line[colon_pos + 1] != ' ') {
        cerr << "Misformatted line. Was expecting to see a ': ' in there.\n";
        cerr << "Line:\n";
        cerr << line << "\n";
        cerr << "colon_pos: " << colon_pos<< "\n";
        return 0;
      }
      size_t val_start = colon_pos + 2;
      size_t val_size = line.size() - val_start;
      cur_frame->push_back(KVPair(line.substr(0, colon_pos),
                                  line.substr(val_start, val_size)));
    }
    if (requests->back().empty()) {
      requests->pop_back();
    }
    return 1;
  }
};

/*
int main(int argc, char** argv) {
  vector<HeaderFrame> requests;
  vector<HeaderFrame> responses;
  if (!ParseFile(argv[1], &requests, &responses)) {
    cerr << "Failed to parse correctly. Exiting\n";
    return EXIT_FAILURE;
  }
  for (int i = 0; i < requests.size(); ++i) {
    for (HeaderFrame::Lines::const_iterator l_it = requests[i].lines.begin();
         l_it != requests[i].lines.end();
         ++l_it) {
      auto line = *l_it;
      const string& k = line.first;
      const string& v = line.second;
      cout << k << ": " << v << "\n";
    }
    cout << "\n";
    for (HeaderFrame::Lines::const_iterator l_it = responses[i].lines.begin();
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
*/




#endif  // TRIVIAL_HTTP_PARSE_H
