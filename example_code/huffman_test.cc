#include <stdlib.h>
#include "huffman.cc"
#include "header_freq_tables.cc"

int main(int argc, char**argv) {
  Huffman huff;
  huff.Init(FreqTables::request_freq_table);
  cout << huff << "\n";
  return EXIT_SUCCESS;
}
