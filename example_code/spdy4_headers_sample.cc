// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <unistd.h>
#include <fcntl.h>
#include <time.h>

#include <zlib.h>

#include <memory>
#include <cstring>

#include "bit_bucket.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"
#include "spdy4_headers_codec.h"
#include "spdy3_dictionary.h"

using std::unique_ptr;
using std::vector;
using std::memset;
using std::fixed;
using std::cout;
using std::cerr;

int ParseHarFiles(int n_files, char** files,
                   vector<HeaderFrame>* requests,
                   vector<HeaderFrame>* responses) {
  int pipe_fds[2];  // read, write
  int pipe_retval = pipe(pipe_fds);
  if (pipe_retval == -1) {
    perror("");
    abort();
  }
  pid_t child_pid;
  if ((child_pid = fork()) == -1) {
    perror("Fork failed");
    abort();
  }
  if (child_pid == 0) {
    dup2(pipe_fds[1], 1);
    char** new_argv = new char*[n_files + 2];
    new_argv[0] =(char*) "./harfile_translator.py";
    for (int i = 0; i < n_files; ++i) {
      new_argv[i + 1] = files[i];
    }
    new_argv[n_files + 1] = 0;
    if (execvp(new_argv[0], new_argv) == -1) {
      perror("Great: ");
      abort();
    }
  } else {
    close(pipe_fds[1]);
  }

  stringstream input;
  char buf[256];
  ssize_t bytes_read = 0;
  while ((bytes_read = read(pipe_fds[0], &buf, sizeof(buf)-1))) {
    if (bytes_read < 0) {
      if (errno == EINTR) {
        continue;
      }
      break;
    } else {
      buf[bytes_read] = 0;
      input << buf;
    }
  }
  if (!TrivialHTTPParse::ParseStream(input, requests, responses)) {
    cerr << "Failed to parse correctly. Exiting\n";
    return 0;
  }
  return 1;
}

class SimpleTimer {
  timespec ts_start;
  timespec ts_end;
  bool running;
 public:
  SimpleTimer() : running (false) { }
  void Start() {
    running = true;
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts_start);
  }
  void Stop() {
    clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts_end);
    running = false;
  }
  double ElapsedTime() {
    if (running) {
      clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &ts_end);
    }

    size_t delta_nsec;
    size_t delta_sec;
    if (ts_end.tv_nsec < ts_start.tv_nsec) {
      delta_nsec = 1000000000 - (ts_start.tv_nsec - ts_end.tv_nsec);
      delta_sec = (ts_end.tv_sec - 1) - ts_start.tv_sec;
    } else {
      delta_nsec = ts_end.tv_nsec - ts_start.tv_nsec;
      delta_sec = ts_end.tv_sec - ts_start.tv_sec;
    }
    double secs = delta_nsec / 1000000000.0L;
    secs += delta_sec;
    return secs;
  }
};

void OutputHeaderFrame(const HeaderFrame& hf) {
  for (HeaderFrame::const_iterator i = hf.begin(); i != hf.end(); ++i) {
    auto line = *i;
    const string& k = line.key;
    const string& v = line.val;
    cout << k << ": " << v << "\n";
  }
}

struct Stats {
  size_t compressed_size;
  double elapsed_time;
  size_t iterations;
  Stats() : compressed_size(0), elapsed_time(0), iterations(0) {}
  Stats(size_t cs, double et, size_t it) :
    compressed_size(cs), elapsed_time(et), iterations(it) {}
};

static const int kCompressorLevel = 9;

// 1 << (kCompressorWindowSizeInBits+ 2) bytes used
static const int kCompressorWindowSizeInBits = 15;

// 1 << (9+kCompressorMemLevel)          bytes used
static const int kCompressorMemLevel = 8;

#define SPDY3
#ifdef SPDY3

class SPDY3Formatter {
  unique_ptr<z_stream> header_compressor_;
  vector<char> output_buffer;
  vector<char> to_be_compressed;
  size_t output_capacity;
 public:

  SPDY3Formatter() : output_capacity(0) {
    InitHeaderCompressor();
  }

  void ResizeOutput(vector<char>* out, size_t required_extra_capacity) {
    out->resize(out->size() + required_extra_capacity);
  }


  void InitHeaderCompressor() {
    header_compressor_.reset(new z_stream);
    memset(header_compressor_.get(), 0, sizeof(z_stream));
    int success = deflateInit2(header_compressor_.get(),
                               kCompressorLevel,
                               Z_DEFLATED,
                               kCompressorWindowSizeInBits,
                               kCompressorMemLevel,
                               Z_DEFAULT_STRATEGY);
    if (success == Z_OK) {
      const unsigned char* dictionary = SPDY_dictionary_txt;
      success = deflateSetDictionary(header_compressor_.get(),
                                     reinterpret_cast<const Bytef*>(dictionary),
                                     sizeof(SPDY_dictionary_txt));
    }
    if (success != Z_OK) {
      cerr << "deflateSetDictionary failure: " << success;
      header_compressor_.reset(NULL);
      abort();
    }
  }

  void Compress(vector<char>* out, const vector<char>& to_be_compressed) {
    z_stream* compressor = header_compressor_.get();
    assert(compressor);

    int payload_length = to_be_compressed.size();
    char* payload = const_cast<char*>(&(to_be_compressed[0]));
    int compressed_max_size = deflateBound(compressor, payload_length);
    size_t output_prev_size = out->size();
    out->resize(out->size() + compressed_max_size);
    char* output_ptr = &((*out)[output_prev_size]);


    compressor->next_in = reinterpret_cast<Bytef*>(payload);
    compressor->avail_in = payload_length;
    compressor->next_out = reinterpret_cast<Bytef*>(output_ptr);
    compressor->avail_out = compressed_max_size;

    int rv = deflate(compressor, Z_SYNC_FLUSH);
    if (rv != Z_OK) {  // How can we know that it compressed everything?
      // This shouldn't happen, right?
      cerr << "deflate failure: " << rv;
      abort();
    }

    out->resize(out->size() - compressor->avail_out);
  }

  static void OverwriteInt24(vector<char>* out,
                             size_t pos,
                             uint32_t val) {
    (*out)[pos+0] = (val >> 16 & 255u);
    (*out)[pos+1] = (val >>  8 & 255u);
    (*out)[pos+2] = (val >>   0& 255u);
  }

  static void AppendInt32(vector<char>* out, uint32_t val) {
    out->push_back((uint8_t)(255u & val >> 24));
    out->push_back((uint8_t)(255u & val >> 16));
    out->push_back((uint8_t)(255u & val >>  8));
    out->push_back((uint8_t)(255u & val >>  0));
  }

  static void AppendInt24(vector<char>* out, uint32_t val) {
    out->push_back((uint8_t)(255u & val >> 16));
    out->push_back((uint8_t)(255u & val >>  8));
    out->push_back((uint8_t)(255u & val >>  0));
  }

  void FormatHeaderBlock(vector<char>* tbc,
                         const HeaderFrame& frame) {
    AppendInt32(tbc, frame.size());
    for (size_t i = 0; i < frame.size(); ++i) {
      AppendInt32(tbc, frame[i].key.size());
      tbc->insert(tbc->end(), frame[i].key.begin(), frame[i].key.end());
      AppendInt32(tbc, frame[i].val.size());
      tbc->insert(tbc->end(), frame[i].val.begin(), frame[i].val.end());
    }
  }

  void FormatHeaders(vector<char>* out, const HeaderFrame& frame) {
    out->push_back(0x1u<<7);  // control-frame
    out->push_back(0x3u);    //  version 3
    out->push_back(0);      // type
    out->push_back(8u);    //  ..
    out->push_back(0);    // flags
    size_t length_pin = out->size(); // we'll ahve to overwrite this later.
    AppendInt24(out, 0); // length, which is bogus here.
    AppendInt32(out, 1); // stream_id
    FormatHeaderBlock(&to_be_compressed, frame);
    Compress(out, to_be_compressed);
    to_be_compressed.clear();
    OverwriteInt24(out, length_pin, out->size() - length_pin);
  }
};


Stats DoSPDY3CoDec(double time_to_iterate,
                   const vector<HeaderFrame>& frames) {
  SPDY3Formatter spdy3_formatter;
  size_t compressed_size = 0;
  SimpleTimer timer;
  timer.Start();
  size_t iterations = 0;
  vector<char> output;
  while (timer.ElapsedTime() < time_to_iterate) {
    ++iterations;
    for (size_t j = 0; j < frames.size(); ++j) {
      const HeaderFrame& request = frames[j];
      size_t prev_size = output.size();
      spdy3_formatter.FormatHeaders(&output, request);
      size_t framesize = output.size() - prev_size;
      compressed_size += framesize;
      output.clear();
    }
  }
  timer.Stop();
  return Stats(compressed_size, timer.ElapsedTime(), iterations);
}
#endif



Stats DoSPDY4CoDec(double time_to_iterate,
                   const vector<HeaderFrame>& frames) {
  size_t compressed_size = 0;
  const int header_group = 1;
  const int stream_id = 1;

  SPDY4HeadersCodec req_in(FreqTables::request_freq_table);
  size_t max_state_size = 1u << (kCompressorWindowSizeInBits + 2);
  size_t max_vals = (1u << (kCompressorMemLevel + 9)) / (8*(3+3+2+3));
  req_in.SetMaxStateSize(max_state_size);
  req_in.SetMaxVals(max_vals);

  cout << "\n\n";
  cout <<  "Max state size: " << max_state_size << "\n";
  cout <<  "Max max vals: " << max_vals << "\n";

  SimpleTimer timer;
  timer.Start();
  size_t iterations = 0;
  OutputStream os;
  while (timer.ElapsedTime() < time_to_iterate) {
    ++iterations;
    for (unsigned int j = 0; j < frames.size(); ++j) {
      const HeaderFrame& request = frames[j];
#ifdef DEBUG
      cout << "++++++++++++++++++++++\n";
      OutputHeaderFrame(request);
      cout << "||||||||||||||||||||||\n";
#endif
      size_t prev_size = os.BytesRequired();
      req_in.OutputCompleteHeaderFrame(&os, stream_id,
                                       header_group, request,
                                       true /* end of frame*/);
      size_t framesize = os.BytesRequired() - prev_size;
      compressed_size += framesize;
      //req_out.ProcessInput(&os);
      // examine the size of the OutputStream vs the original size.
      //HeaderFrame out_frame;
      //req_out.ReconsituteFrame(&out_frame);
      // test that they're the same.

#ifdef DEBUG
      cout << "\n########### FRAME DONE ############## "
           << req_in.CurrentStateSize();
      cout << "\n";
#endif
      os.Clear();
    }
  }
  timer.Stop();
  return Stats(compressed_size, timer.ElapsedTime(), iterations);
}

void PrintSummary(const string& protocol_name,
                  Stats stats,
                  size_t uncompressed_size,
                  size_t header_count) {
  double secs = stats.elapsed_time;
  size_t total_compressed_size = stats.compressed_size;
  size_t iterations = stats.iterations;
  double compression_ratio = ((double)total_compressed_size /
                              (double) uncompressed_size);
  compression_ratio /= iterations;
  cout << "\n\n";
  cout << "################# " << protocol_name << " ################\n";
  cout << "Compression took: " << secs << " seconds"
       << " for: " << iterations << "*" << header_count << " header frames"
       << " (" << (iterations * header_count) << " total header frames)"
       << " or " << (header_count * iterations) / secs << " headers/sec"
       << " or " << fixed << (uncompressed_size * iterations) / secs << " bytes/sec"
       << "\n";
  cout << "Compression ratio: " << compression_ratio << " = "
       << "compressed bytes(" << total_compressed_size << ")"
       << " / "
       << "uncompressed_bytes(" << (uncompressed_size * iterations) << ")"
       << "\n";
}

int main(int argc, char** argv) {
  vector<HeaderFrame> requests;
  vector<HeaderFrame> responses;
  ParseHarFiles(argc-1, argv+1, &requests, &responses);

  size_t request_header_bytes = 0;
  size_t header_count = 0;
  for (unsigned int i = 0; i < requests.size(); ++i) {
    ++header_count;
    for (unsigned int j = 0; j < requests[i].size(); ++j) {
      request_header_bytes += requests[i][j].key.size();
      request_header_bytes += requests[i][j].val.size();
    }
  }
  const double time_to_iterate = 10.0;

  Stats spdy4_stats = DoSPDY4CoDec(time_to_iterate, requests);
  PrintSummary("spdy4", spdy4_stats,
               request_header_bytes, header_count);

#ifdef SPDY3
  Stats spdy3_stats = DoSPDY3CoDec(time_to_iterate, requests);
  PrintSummary("spdy3", spdy3_stats,
               request_header_bytes, header_count);
#endif

}


