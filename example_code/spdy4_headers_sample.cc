// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#include <unistd.h>
#include <fcntl.h>
#include <time.h>

#include "bit_bucket.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"
#include "spdy4_headers_codec.h"

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
      delta_nsec = 1000000000 + ts_end.tv_nsec - ts_start.tv_nsec;
      delta_sec = ts_end.tv_sec - (ts_start.tv_sec - 1);
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

pair<size_t,double> DoSPDY3CoDec(size_t iterations, const vector<HeaderFrame>& frames) {
  size_t compressed_size = 0;
  double d = 0;
  SimpleTimer timer;
  timer.Start();
  for (size_t i = 0; i < iterations; ++i) {
    for (size_t j = 0; j < frames.size(); ++j) {
      for (size_t k = 0; k < frames[j].size(); ++k) {
        compressed_size += frames[j][k].key.size();
        compressed_size += frames[j][k].val.size();
        d += i+j+k;
      }
    }
  }
  timer.Stop();
  return make_pair(compressed_size, timer.ElapsedTime());;
}

pair<size_t,double> DoSPDY4CoDec(size_t desired_iterations, const vector<HeaderFrame>& frames) { 
  size_t compressed_size = 0;
  const int header_group = 1;
  const int stream_id = 1;

  SPDY4HeadersCodec req_in(FreqTables::request_freq_table);

  SimpleTimer timer;
  timer.Start();
  for (size_t iterations = 0; iterations < desired_iterations; ++iterations) {
    for (unsigned int i = 0; i < frames.size(); ++i) {
      OutputStream os;
      const HeaderFrame& request = frames[i];
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
    }
  }
  timer.Stop();
  return make_pair(compressed_size, timer.ElapsedTime());
}

void PrintSummary(const string& protocol_name,
                  pair<size_t, double> stats,
                  size_t iterations,
                  size_t uncompressed_size,
                  size_t header_count) {
  double secs = stats.second;
  size_t total_compressed_size = stats.first;
  double compression_ratio = (double)total_compressed_size / (double) uncompressed_size;
  compression_ratio /= iterations;
  cout << "\n\n";
  cout << "################# " << protocol_name << " ################\n";
  cout << "Compression took: " << secs << " seconds"
       << " for: " << iterations << "*" << header_count << " header frames"
       << " (" << (iterations * header_count) << " total header frames)"
       << " or " << (header_count * iterations) / secs << " headers/sec"
       << " or " << (uncompressed_size * iterations) / secs << " bytes/sec"
       << "\n";
  cout << "Compression ratio: " << compression_ratio << "\n";
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
  const size_t iterations = 100;

  pair<size_t, double> spdy3_stats = DoSPDY3CoDec(iterations, requests);
  pair<size_t, double> spdy4_stats = DoSPDY4CoDec(iterations, requests);
  PrintSummary("spdy3", spdy3_stats, iterations, request_header_bytes, header_count);
  PrintSummary("spdy4", spdy4_stats, iterations, request_header_bytes, header_count);
}


