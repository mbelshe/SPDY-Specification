#include <arpa/inet.h>

#include <array>
#include <utility>

#include "bit_bucket.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"

using std::array;
using std::pair;
using std::make_pair;


const char* spdy4_default_dict[64][2] = {
  {":host", ""},
  {":method", "get"},
  {":path", "/"},
  {":scheme", "https"},
  {":status", "200"},
  {":status-text", "OK"},
  {":version", "1.1"},
  {"accept", ""},
  {"accept-charset", ""},
  {"accept-encoding", ""},
  {"accept-language", ""},
  {"accept-ranges", ""},
  {"allow", ""},
  {"authorizations", ""},
  {"cache-control", ""},
  {"content-base", ""},
  {"content-encoding", ""},
  {"content-length", ""},
  {"content-location", ""},
  {"content-md5", ""},
  {"content-range", ""},
  {"content-type", ""},
  {"cookie", ""},
  {"date", ""},
  {"etag", ""},
  {"expect", ""},
  {"expires", ""},
  {"from", ""},
  {"if-match", ""},
  {"if-modified-since", ""},
  {"if-none-match", ""},
  {"if-range", ""},
  {"if-unmodified-since", ""},
  {"last-modified", ""},
  {"location", ""},
  {"max-forwards", ""},
  {"origin", ""},
  {"pragma", ""},
  {"proxy-authenticate", ""},
  {"proxy-authorization", ""},
  {"range", ""},
  {"referer", ""},
  {"retry-after", ""},
  {"server", ""},
  {"set-cookie", ""},
  {"status", ""},
  {"te", ""},
  {"trailer", ""},
  {"transfer-encoding", ""},
  {"upgrade", ""},
  {"user-agent", ""},
  {"user-agent", ""},
  {"vary", ""},
  {"via", ""},
  {"warning", ""},
  {"www-authenticate", ""},
  {"access-control-allow-origin", ""},
  {"content-disposition", ""},
  {"get-dictionary", ""},
  {"p3p", ""},
  {"x-content-type-options", ""},
  {"x-frame-options", ""},
  {"x-powered-by", ""},
  {"x-xss-protection", ""},
};


const uint8_t kFrameLengthFieldLengthInBytes = 2;
const uint32_t kMaxFrameSize = ~(0xFFFFFFFFU <<
                                 (kFrameLengthFieldLengthInBytes * 8));
const uint8_t kHeaderEndFlag = 0x1;

class OutputStream {
 public:
  vector<char> storage;

  uint32_t StreamPos() {
    return storage.size();
  }
  uint8_t GetUint8(uint32_t pos) {
    return static_cast<uint8_t>(storage[pos]);
  }
  void WriteUint8(uint8_t byte) {
    storage.push_back(static_cast<char>(byte));
  }
  void WriteUint16(uint16_t shrt) {
    //shrt = htons(shrt);
    storage.insert(storage.end(), &shrt, &shrt + 2);
  }
  void WriteUint32(uint32_t word) {
    //wrd = htonl(word);
    storage.insert(storage.end(), &word, &word + 4);
  }
  template <typename T>
  void WriteBytes(const T begin, const T end) {
    storage.insert(storage.end(), begin, end);
  }
  void OverwriteUint16(uint32_t pos, uint16_t arg) {
    //shrt = htons(shrt);
    uint8_t byte = arg >> 8;
    OverwriteUint8(pos, byte);
    byte = arg & 0xFF;
    OverwriteUint8(pos + 1, byte);
  }
  void OverwriteUint8(uint32_t pos, uint8_t byte) {
    storage[pos] = static_cast<char>(byte);
  }
};

class SPDY4HeadersCodec {
 private:
  Huffman huff;
  uint32_t total_header_storage_size;
  uint32_t max_header_groups;
  uint32_t max_table_entries;

 public:
  SPDY4HeadersCodec(const FreqTable& sft) :
      total_header_storage_size(20*1024),
      max_header_groups(1),
      max_table_entries(640) {
    huff.Init(sft);
  }

  void OutputCompleteHeaderFrame(OutputStream* os,
                         uint32_t stream_id,
                         const Frame& headers,
                         bool this_ends_the_frame) {
    uint32_t start_of_frame_pos = 0;
    uint32_t bytes_remaining = 1; // this is a lie, but it gets us in the loop.
    uint8_t headers_end_flag = 0;
    if (this_ends_the_frame) headers_end_flag = kHeaderEndFlag;
    while (bytes_remaining) {
      start_of_frame_pos = os->StreamPos();
      // Write the control frame boilerplate. We'll have to come back
      // and write out the length later, and may have to modify the flags
      // later as well...
      WriteControlFrameBoilerplate(os, 0, headers_end_flag, stream_id, 0x8U);
      uint32_t bytes_used = os->StreamPos() - start_of_frame_pos;
      // sanity check again that we're not overflowing the max frame size.
      if (bytes_used > kMaxFrameSize) abort();
      // fill in the frame-size (we said it was 0 before, which was a lie)

      // Need a header iterator for this too...
      bytes_remaining = WriteNameHeaderBlock(os, stream_id, headers,
                                             kMaxFrameSize - bytes_used);
      uint32_t frame_size_field_pos = start_of_frame_pos;
      os->OverwriteUint16(frame_size_field_pos,
                          static_cast<uint16_t>(kMaxFrameSize - bytes_remaining));
      if (bytes_remaining && this_ends_the_frame) {
        // The headers didn't fit into the frame.
        uint32_t flags_field_pos = (start_of_frame_pos +
                                    kFrameLengthFieldLengthInBytes);
        uint8_t new_flags_val = os->GetUint8(flags_field_pos) & ~kHeaderEndFlag;
        os->OverwriteUint8(flags_field_pos, new_flags_val);
      }
    }
  }

  void WriteControlFrameBoilerplate(OutputStream* os,
                                    uint32_t frame_len,
                                    uint8_t flags,
                                    uint32_t stream_id,
                                    uint8_t type) {
    os->WriteUint16(frame_len);
    os->WriteUint8(flags);
    WriteControlFrameStreamId(os, stream_id);
    os->WriteUint8(type);
  }

  void WriteControlFrameStreamId(OutputStream* os, uint32_t stream_id) {
    if (stream_id & 0x8000U) {
      abort(); // can't have that top-order bit set....
    }
    os->WriteUint32(0x8000U | stream_id);
  }
  uint32_t WriteNameHeaderBlock(OutputStream* os, uint32_t stream_id,
                               const Frame& headers,
                               uint32_t max_bytes) {
    return 0;
  }


};
