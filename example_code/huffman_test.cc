#include <stdlib.h>
#include "huffman.cc"
#include "header_freq_tables.cc"
#include <iostream>

using std::string;
using std::cerr;

struct Testcase {
  string input;
};

template <typename T>
void Test(const T& expected, const T& actual) {
  if (expected != actual) {
    cerr << "\n";
    cerr << "       --- FAILED ---\n";
    cerr << "   Expected: \"" << expected << "\"\n";
    cerr << "        Got: \"" << actual << "\"\n";
    abort();
  }
}

void TestEncodeDecode(const Huffman& huff,
                      const string& input,
                      bool use_eof,
                      bool use_length,
                      int length_delta) {
  string decoded;
  int num_bits = 0;

  BitBucket bb;
  huff.Encode(&bb, input, use_eof);

  if (use_length)
    num_bits = bb.NumBits() + length_delta;
  huff.Decode(&decoded, &bb, use_eof, bb.NumBits());
  Test(input, decoded);
}

int main(int argc, char**argv) {
  Huffman huff;
  huff.Init(FreqTables::request_freq_table);
  array<string,6> tests = {
    "dabbcccddddeeeee",
    "foobarbaz",
    "0-2rklnsvkl;-23kDFSi01k0=",
    "-9083480-12hjkadsgf8912345kl;hjajkl;       `123890",
    "\0\0-3;jsdf",
    "\xFF\xE0\0\0\t\ne\0\x81\x82",
  };
  for (int i = 0; i < tests.size(); ++i) {
    const string& test = tests[i];
    cerr << "TEST: " << test << "...";
    cerr << "\n";
    TestEncodeDecode(huff, test,  true, false, 0);
    TestEncodeDecode(huff, test, false,  true, 0);
    TestEncodeDecode(huff, test,  true,  true, 8);
    cerr << "PASSED!\n";
  }
  //cout << huff;
  return EXIT_SUCCESS;
}
