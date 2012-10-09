#include <unistd.h>
#include <fcntl.h>

#include "bit_bucket.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"
#include "spdy4_headers_codec.h"

int ParseHarFiles(int n_files, char** files,
                   vector<HeaderFrame>* requests,
                   vector<HeaderFrame>* responses) {
  int pipe_fds[2];  // read, write
  pipe(pipe_fds);
  pid_t child_pid;
  if ((child_pid = fork()) == -1) {
    perror("Fork failed");
    abort();
  }
  if (child_pid == 0) {
    dup2(pipe_fds[1], 1);
    char** new_argv = new char*[n_files + 2];
    new_argv[0] =(char*) "harfile_translator.py";
    for (int i = 0; i < n_files; ++i) {
      new_argv[i + 1] = files[i];
    }
    new_argv[n_files + 1] = 0;
    if (execvp("harfile_translator.py", new_argv) == -1) {
      perror("Great.");
      abort();
    }
  } else {
    close(pipe_fds[1]);
  }

  stringstream input;
  char buf[256];
  size_t bytes_read = 0;
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

void OutputHeaderFrame(const HeaderFrame& hf) {
  for (HeaderFrame::const_iterator i = hf.begin(); i != hf.end(); ++i) {
    auto line = *i;
    const string& k = line.key;
    const string& v = line.val;
    cout << k << ": " << v << "\n";
  }
}

int main(int argc, char** argv) {
  vector<HeaderFrame> requests;
  vector<HeaderFrame> responses;
  ParseHarFiles(argc-1, argv+1, &requests, &responses);

  // for (unsigned int i = 0; i < requests.size(); ++i) {
  //   OutputHeaderFrame(requests[i]);
  //   cout << "\n";
  //   OutputHeaderFrame(responses[i]);
  //   cout << "\n";
  // }

  SPDY4HeadersCodec req_in(FreqTables::request_freq_table);
  //SPDY4HeadersCodec res_in(FreqTables::response_freq_table);
  //SPDY4HeadersCodec req_out(FreqTables::request_freq_table);
  //SPDY4HeadersCodec res_out(FreqTables::response_freq_table);


  cout << "\n\n\nBeginning processing now\n\n\n\n";
  int header_group = 1;
  int stream_id = 1;
  for (unsigned int i = 0; i < requests.size(); ++i) {
    OutputStream os;
    const HeaderFrame& request = requests[i];
    OutputHeaderFrame(request);
    cout << "======================\n";
    req_in.OutputCompleteHeaderFrame(&os, stream_id,
                                     header_group, request,
                                     true /* end of frame*/);
    //req_out.ProcessInput(&os);
    // examine the size of the OutputStream vs the original size.
    //HeaderFrame out_frame;
    //req_out.ReconsituteFrame(&out_frame);
    // test that they're the same.
    cout << "\n########### FRAME DONE ############## "
         << req_in.CurrentStateSize();
    cout << "\n";
  }
}
