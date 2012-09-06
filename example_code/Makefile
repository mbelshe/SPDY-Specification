
CXX      = g++
DEBUG    = -g
OPT      = -O0
CXXFLAGS = $(DEBUG) $(OPT) -std=c++0x
TARGETS  = bit_bucket_test huffman_test

#.cc.o:
#	$(CXX) $(CXXFLAGS) $< -o $@

bit_bucket_test: bit_bucket.cc bit_bucket_test.cc
	 $(CXX) $(CXXFLAGS) bit_bucket_test.cc -o $@


huffman_test: huffman.cc huffman_test.cc
	 $(CXX) $(CXXFLAGS) huffman_test.cc -o $@

all: $(TARGETS)


clean:
	rm -f *.o $(TARGETS)


