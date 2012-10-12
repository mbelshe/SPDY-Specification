
CXX      = g++
#CXX      = clang++
DEBUG    = -g
OPT      = -O3
WARN     = -Wall -Werror
STD      = -std=c++0x
CXXFLAGS = $(DEBUG) $(OPT) $(WARN) $(STD)

TARGETS  = bit_bucket_test huffman_test headers_sample

SRCS     = *.cc
OBJS     = $(SRCS:%.cc=%.o)

.PHONEY: clean all

all: $(TARGETS)

clean:
	rm -f $(TARGETS) $(OBJS) $(DEPS) *.pyc

.cc.o:
	$(CXX)    $(CXXFLAGS) $< -c -o $@

headers_sample: headers_sample.o spdy4_headers_codec.o header_freq_tables.o
	$(CXX) $(CXXFLAGS) $^ -o $@ -lrt

bit_bucket_test: bit_bucket_test.o
	$(CXX) $(CXXFLAGS) $^ -o $@

huffman_test: huffman_test.o header_freq_tables.o utils.o
	$(CXX) $(CXXFLAGS) $^ -o $@

