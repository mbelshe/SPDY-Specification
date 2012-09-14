#ifndef TRIVIAL_HTTP_PARSE_H
#define TRIVIAL_HTTP_PARSE_H

#include <fstream>
#include <iostream>
#include <stdlib.h>
#include <string>
#include <utility>
#include <vector>

using std::cerr;
using std::cout;
using std::getline;
using std::ifstream;
using std::pair;
using std::string;
using std::vector;

struct Frame {
  Frame(){}
  typedef vector<pair<string, string> > Lines;
  Lines lines;
  bool empty() {
    return lines.empty();
  }
};

class TrivialHTTPParse {
 private:
  static Frame* GetFramePtr(vector<Frame>* frames, unsigned int expected_previous_len) {
    if (frames->size() <= expected_previous_len) {
      frames->push_back(Frame());
    }
    return &(frames->back());
  }

 public:
  static int ParseFile(const string& fn,
                vector<Frame>* requests,
                vector<Frame>* responses) {
    int frames_len = 0;
    int frames_idx = 0;
    vector<Frame>* frames[2] = {requests, responses};
    if (!(requests->empty() && responses->empty())) {
      return -1;
    }
    Frame* cur_frame = GetFramePtr(frames[frames_idx], frames_len);

    ifstream ifs(fn.c_str());
    while (ifs.good()) {
      string line;
      getline(ifs, line);
      size_t colon_pos = line.find_first_of(":", 1);
      if (line.size() == 0) {
        // finished with this frame.
        if (frames_idx == 1) ++frames_len;
        frames_idx = ! frames_idx;
        cur_frame = GetFramePtr(frames[frames_idx], frames_len);
        continue;
      } else if (colon_pos == string::npos ||
                 colon_pos + 1 > line.size() ||
                 line[colon_pos + 1] != ' ') {
        cerr << "Misformatted line. Was expecting to see a ': ' in there.\n";
        cerr << "Line:\n";
        cerr << line << "\n";
        cerr << "colon_pos: " << colon_pos;
        return 0;
      }
      size_t val_start = colon_pos + 2;
      size_t val_size = line.size() - val_start;
      cur_frame->lines.push_back(make_pair(line.substr(0, colon_pos),
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
  vector<Frame> requests;
  vector<Frame> responses;
  if (!ParseFile(argv[1], &requests, &responses)) {
    cerr << "Failed to parse correctly. Exiting\n";
    return EXIT_FAILURE;
  }
  for (int i = 0; i < requests.size(); ++i) {
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
*/




#endif  // TRIVIAL_HTTP_PARSE_H
