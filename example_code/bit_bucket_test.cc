// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#include "bit_bucket.h"
#include "utils.h"

struct Testcase {
  vector<char> v;
  int num_bits;
  string expected_state;

  friend ostream& operator<<(ostream& os, const Testcase& tc) {
    os << "Testcase: \"" << tc.expected_state << "\","
       << "\"" << FormatAsBits(tc.v, tc.num_bits) << "\"";
    return os;
  }
};

void TestStoreBits(BitBucket* bb, const Testcase& test) {
  cout << test << " ..." << flush;
  bb->StoreBits(test.v, test.num_bits);
  if (test.expected_state != bb->AsString()) {
    cerr << "\n";
    cerr << "       --- FAILED ---\n";
    cerr << "   Expected: \"" << test.expected_state << "\"\n";
    cerr << "        Got: \"" << bb << "\"\n";
    cerr << "       DEBUG: " << bb->DebugStr() << "\n";
    abort();
  }
}

void TestGetBits(BitBucket*bb, const Testcase& test) {
  bb->Seek(0);
  vector<char> storage;
  int num_bits = bb->NumBits();
  bb->GetBits(&storage, num_bits);
  stringstream formatted_bits;
  formatted_bits << FormatAsBits(storage, num_bits);
  formatted_bits << " [" << num_bits << "," << num_bits % 8 << "]";
  if (formatted_bits.str() != test.expected_state) {
    cerr << "\n";
    cerr << "       --- FAILED ---\n";
    cerr << "   Expected: \"" << test.expected_state << "\"\n";
    cerr << "        Got: \"" << formatted_bits.str() << "\"\n";
    cerr << "       DEBUG: " << bb->DebugStr() << "\n";
    abort();
  }
  // Now, do it again, starting from bit offsets other than 0
  for (int i = 1; i < min(8, num_bits); ++i) {
    bb->Seek(0);
    formatted_bits.str("");
    for (int j = 0; j < i; ++j) {
      if (j % 8 == 0) {
        formatted_bits << "|";
      }
      formatted_bits << bb->GetBit();
    }
    storage.clear();
    bb->GetBits(&storage, num_bits - i);
    string storage_str = FormatAsBits(storage, num_bits - i, i);
    formatted_bits << FormatAsBits(storage, num_bits - i, i);
    formatted_bits << " [" << num_bits << "," << num_bits % 8 << "]";
    if (formatted_bits.str() != test.expected_state) {
      cerr << "\n";
      cerr << "       --- FAILED ---\n";
      cerr << "     Offset: " << i << "\n";
      cerr << "   Expected: \"" << test.expected_state << "\"\n";
      cerr << "        Got: \"" << formatted_bits.str() << "\"\n";
      cerr << "       DEBUG: " << bb->DebugStr() << "\n";
      //abort();
    }
  }
}

void RunTests(const vector<Testcase>& tests) {
  BitBucket bb;
  cout << "\n\nNew test\n";
  for (unsigned int i = 0; i < tests.size(); ++i) {
    const Testcase& test = tests[i];
    TestStoreBits(&bb, test);
    TestGetBits(&bb, test);
    cout << "  Passed\n" << flush;
  }
}

int main(int argc, char** argv) {
  {
    vector<Testcase> tests = {
      {{'\xff', '\x00' }, 8+6, "|11111111|000000 [14,6]"},
      {{'\xff', '\x00' }, 8+6, "|11111111|00000011|11111100|0000 [28,4]"},
      {{'\xff', '\x00' }, 8+6, "|11111111|00000011|11111100|00001111|11110000"
                               "|00 [42,2]"},
      {{'\xff', '\x00' }, 8+6, "|11111111|00000011|11111100|00001111|11110000"
                               "|00111111|11000000 [56,0]"},
      {{'\xff', '\x00' }, 8+6, "|11111111|00000011|11111100|00001111|11110000"
                               "|00111111|11000000|11111111|000000 [70,6]"},
    };
    RunTests(tests);
  }
  {
    vector<Testcase> tests = {
      {{'\xff', '\x00' }, 8+6, "|11111111|000000 [14,6]"},
      {{'\xff'         }, 3  , "|11111111|00000011|1 [17,1]"},
      {{'\x00'         }, 3  , "|11111111|00000011|1000 [20,4]"},
      {{'\xff', '\x00' }, 8+6, "|11111111|00000011|10001111|11110000"
                               "|00 [34,2]"},
      {{'\xff'         }, 4  , "|11111111|00000011|10001111|11110000"
                               "|001111 [38,6]"},
      {{'\x00'         }, 4  , "|11111111|00000011|10001111|11110000"
                               "|00111100|00 [42,2]"},
    };
    RunTests(tests);
  }
  {
    vector<Testcase> tests = {
      {{'\xF0'}, 5, "|11110 [5,5]"},
      {{'\x0F'}, 5, "|11110000|01 [10,2]"},
      {{'\xF0'}, 5, "|11110000|0111110 [15,7]"},
      {{'\x0F'}, 5, "|11110000|01111100|0001 [20,4]"},
      {{'\xF0'}, 5, "|11110000|01111100|00011111|0 [25,1]"},
      {{'\x0F'}, 5, "|11110000|01111100|00011111|000001 [30,6]"},
      {{'\xF0'}, 5, "|11110000|01111100|00011111|00000111|110 [35,3]"},
      {{'\x0F'}, 5, "|11110000|01111100|00011111|00000111|11000001 [40,0]"},
      {{'\xF0'}, 5, "|11110000|01111100|00011111|00000111|11000001|11110 [45,5]"},
    };
    RunTests(tests);
  }
  {
    vector<Testcase> tests = {
      {{'\xF0'},         1,  "|1 [1,1]"},
      {{'\x0F'},         1,  "|10 [2,2]"},
      {{'\xF0'},         1,  "|101 [3,3]"},
      {{'\x0F'},         1,  "|1010 [4,4]"},
      {{'\xF0'},         1,  "|10101 [5,5]"},
      {{'\x0F'},         1,  "|101010 [6,6]"},
      {{'\xF0'},         1,  "|1010101 [7,7]"},
      {{'\x0F'},         1,  "|10101010 [8,0]"},
      {{'\xF0'},         1,  "|10101010|1 [9,1]"},
      {{'\x00','\xFF'}, 8+7, "|10101010|10000000|01111111 [24,0]"},
    };
    RunTests(tests);
  }
  {
    vector<Testcase> tests = {
      {{'\xF0'}, 8, "|11110000 [8,0]"},
      {{'\xF0'}, 8, "|11110000|11110000 [16,0]"},
      {{'\xF0'}, 1, "|11110000|11110000|1 [17,1]"},
      {{'\x0F'}, 8, "|11110000|11110000|10000111|1 [25,1]"},
    };
    RunTests(tests);
  }
}
