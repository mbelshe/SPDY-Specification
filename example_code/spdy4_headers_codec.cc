#include <arpa/inet.h>

#include <array>
#include <utility>
#include <set>
#include <list>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <functional>
#include <string>

#include "spdy4_headers_codec.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "utils.h"
#include "trivial_http_parse.h"

using std::string;
using std::array;
using std::vector;
using std::pair;
using std::make_pair;
using std::set;
using std::unordered_set;
using std::unordered_multiset;
using std::unordered_map;
using std::unordered_multimap;
using std::hash;
using std::list;


const char* spdy4_default_dict[][2] = {
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

const LRUIdx kInvalidLRUIdx = 0;
const uint8_t kFrameLengthFieldLengthInBytes = 2;
const uint8_t kFlagFieldOffsetFromFrameStart = kFrameLengthFieldLengthInBytes;
const uint32_t kMaxFrameSize = ~(0xFFFFFFFFU <<
                                 (kFrameLengthFieldLengthInBytes * 8));
const uint8_t kHeaderEndFlag = 0x1;

SPDY4HeadersCodec::SPDY4HeadersCodec(const FreqTable& sft) :
    max_total_header_storage_size(20*1024),
    max_header_groups(1),
    max_table_entries(640),
    frame_count(0),
    current_state_size(0),
    last_used_lru_idx(0)
{
  huff.Init(sft);
  for (unsigned int i = 0;
       i < sizeof(spdy4_default_dict) / sizeof(spdy4_default_dict[0]);
       ++i) {
    ExecuteKVSto(0,
                 KVStoOp(spdy4_default_dict[i][0], spdy4_default_dict[i][1]));
  }
  for (KVLookup::iterator i = kv_lookup.begin();
       i != kv_lookup.end();
       ++i) {

  }
}

LRUIdx  SPDY4HeadersCodec::GetNextLruIdx() {
  return ++last_used_lru_idx;
}

void SPDY4HeadersCodec::OutputCompleteHeaderFrame(OutputStream* os,
                                                  uint32_t stream_id,
                                                  uint32_t group_id,
                                                  const HeaderFrame& headers,
                                                  bool this_ends_the_frame) {
  uint8_t headers_end_flag = 0;
  if (this_ends_the_frame) {
    headers_end_flag = kHeaderEndFlag;
  }
  // We'll want to discover the KVPs to turn off, then
  //   - turn off stream group indices which don't exist in the headers.
  // We'll want to discover the KVPs to turn on,
  //   we'll want to hide/remove these header-lines from further processing.
  // Sort the list of all of the KVP turn-offs and turn-ons
  //   -> this results in an input we can use to do range toggles
  // For the remaining unhidden header-frame KVPs,
  //   discover if the key exists by looking it up in kvlookup map.
  //   if it does, we'll create a clone operation.
  //   if it does not, we'll create a KVP operation.
  //   after the size of the operation has been computed, check to see:
  //     - does it exceed the max frame size?
  //       - then fixup the size for the current frame and emit new frame
  //         headers
  //
  vector<LRUIdx> turn_ons;
  vector<LRUIdx>::iterator first_turn_on;
  vector<LRUIdx> turn_offs;
  vector<LRUIdx>::iterator first_turn_off;
  vector<CloneOp> clones;
  vector<CloneOp>::iterator first_clone;
  vector<KVStoOp> kvstos;
  vector<KVStoOp>::iterator first_kvsto;

  KVEntry* kve = 0;
  size_t size_delta = 0;
  if (header_groups.find(group_id) == header_groups.end()) {
    header_groups[group_id] = HeaderGroup();
  }
  HeaderGroup& header_group = header_groups[group_id];
  for (HeaderFrame::const_iterator hf_i = headers.begin();
       hf_i != headers.end();
       ++hf_i) {
    if ((kve = LookupKeyValue(*hf_i))) {
      //cout << kve->kv << " already exists at: " << kve->lru_idx << "\n";
      // So, the key-value exists, but we don't yet know if it is already
      // on in the header-group.

      HeaderGroup::iterator hg_i = header_group.find(kve->lru_idx);
      if (hg_i == header_group.end()) {
        // The key-value exists, but isn't turned on.
        turn_ons.push_back(kve->lru_idx);
      }
      // Touch the current entry so that we know what to remove from the
      // header group
      TouchHeaderGroupEntry(hg_i);
    } else if ((kve = LookupKey(*hf_i))) {
      // A key exists that matches the one we're doing here.
      // A Clone will result, probably, assuming that the value the clone
      // intends to dereference still exists after any removals have taken
      // place.
      clones.push_back(CloneOp(kve, hf_i->val));
      size_delta += clones.back().DeltaSize();
    } else {
      // Neither the line exists, nor the key exists in the LRU.
      // We'll need to emit a KVSto to store the key and value
      kvstos.push_back(KVStoOp(hf_i->key, hf_i->val));
      size_delta += kvstos.back().DeltaSize();
    }
  }

  // We now need to be sure that this will fit in memory appropriately.
  //
  // This involves calculating the store size for each Clone and KVSto, and
  // adding it to the current size. If that summation exceeds the max size:
  //
  // for each element in clone, set the 'keep-me' bit;
  size_t items_to_delete_from_head = 0;
  if (current_state_size > max_total_header_storage_size) {
    // Since the operations here will cause us to exceed the maximum state
    // size, we must remove elements from the head of the LRU.
    //
    // This potentially means that some of the entries which we had intended to
    // clone could disappear. That in turn means that we may need to change
    // some of the clone operations to something else.
    for (LRUList::iterator lru_i = lru.begin(); lru_i != lru.end(); ++lru_i) {
      if (current_state_size <= max_total_header_storage_size) break;
      (*lru_i)->will_delete = true;
      ++items_to_delete_from_head;
    }
    for (unsigned int i = 0; i < clones.size(); ++i) {
      // mutate the clone if necessary.
    }
  }
  for (size_t i = 0; i < items_to_delete_from_head; ++i) {
    RemoveAndCleanup(lru.front());
    lru.pop_front();
  }

  // Here we discover any elements in the header_group which are referenced
  // but don't exist in the header frame presented to this function.
  // These need to be toggled off.
  // Note that this is done after doing deletions due to exceeding the max
  // buffer size, since some of the deletions may have already cleared some of
  // the elements we must be turning off.
  DiscoverTurnOffs(&turn_offs, stream_id);

  first_turn_on = turn_ons.begin();
  first_turn_off = turn_offs.begin();
  first_clone = clones.begin();
  first_kvsto = kvstos.begin();

  for (vector<LRUIdx>::iterator i = turn_ons.begin();
       i != turn_ons.end();
       ++i) {
    ExecuteToggle(group_id, *i);
  }
  for (vector<LRUIdx>::iterator i = turn_offs.begin();
       i != turn_offs.end();
       ++i) {
    ExecuteToggle(group_id, *i);
  }
  for (vector<CloneOp>::iterator i = clones.begin();
       i != clones.end();
       ++i) {
    ExecuteClone(group_id, *i);
  }
  for (vector<KVStoOp>::iterator i = kvstos.begin();
       i != kvstos.end();
       ++i) {
    ExecuteKVSto(group_id, *i);
  }
  // We first want the toggles (off) serialized, then the toggles on.
  // This will move those elements to the front of the LRU
  // and thus will prevent them from getting removed.
  // We next want to execute remove operations.
  // Then, we do either clones/mutates or KVStos or  (doesn't matter).
  //
  // This ordering will reduce:
  //   1) the amount of data transmitted on the wire since
  //   we will be able to reference state without having to
  //   recreate it more often
  //   2) the amount of state used at any portion of time
  //   while executing the instructions.
  while (!SerializeAllInstructions(os,
                                   &first_turn_on, turn_ons,
                                   &first_turn_off, turn_offs,
                                   &first_clone, clones,
                                   &first_kvsto, kvstos,
                                   headers_end_flag,
                                   stream_id));

  FrameDone();
  cout << "headers.size(): " << headers.size()
    << " header_group.size(): " << header_group.size()
    <<"\n";
  for (HeaderGroup::iterator i = header_group.begin();
       i != header_group.end();
       ++i) {
    cout << "HG[" << group_id << "]: " << i->first << " " << i->second<<"\n";
  }
}

bool SPDY4HeadersCodec::SerializeAllInstructions(
    OutputStream* os,
    vector<LRUIdx>::iterator* first_turn_on,
    const vector<LRUIdx>& turn_ons,
    vector<LRUIdx>::iterator* first_turn_off,
    const vector<LRUIdx>& turn_offs,
    vector<CloneOp>::iterator* first_clone,
    const vector<CloneOp>& clones,
    vector<KVStoOp>::iterator* first_kvsto,
    const vector<KVStoOp>& kvstos,
    uint8_t headers_end_flag,
    uint32_t stream_id) {

  // We need to loop over this until all of the instructions have been
  // serialized

  uint32_t start_of_frame_pos = os->StreamPos();
  // Write the control frame boilerplate. We'll have to come back
  // and write out the length later, and may have to modify the flags
  // later as well...
  WriteControlFrameBoilerplate(os, 0, headers_end_flag, stream_id, 0x8U);
  uint32_t bytes_used = os->StreamPos() - start_of_frame_pos;
  // sanity check again that we're not overflowing the max frame size.
  if (bytes_used > kMaxFrameSize)
    abort();
  for (; *first_turn_on != turn_ons.end(); ++(*first_turn_on)) {
    WriteToggle(os, **first_turn_on);
  }
  for (; *first_turn_off != turn_offs.end(); ++(*first_turn_off)) {
    WriteToggle(os, **first_turn_off);
  }
  for (; *first_clone != clones.end(); ++(*first_clone)) {
    WriteClone(os, **first_clone);
  }
  for (; *first_kvsto != kvstos.end(); ++(*first_kvsto)) {
    WriteKVSto(os, **first_kvsto);
  }


  /*
  {
    uint32_t bytes_used = os->StreamPos() - start_of_frame_pos;
    if (bytes_used > kMaxFrameSize)
      abort();
    uint32_t frame_size_field_pos = start_of_frame_pos;
    os->OverwriteUint16(frame_size_field_pos,
                        static_cast<uint16_t>(kMaxFrameSize - bytes_used));
    if (header_kvs_processed != headers.size() && this_ends_the_frame) {
      // The headers didn't fit into the frame so we need to be sure that
      // we've not indicated that this is the end of the frame.
      uint32_t flags_field_pos = (start_of_frame_pos +
                                  kFlagFieldOffsetFromFrameStart);
      uint8_t new_flags_val = os->GetUint8(flags_field_pos) & ~kHeaderEndFlag;
      os->OverwriteUint8(flags_field_pos, new_flags_val);
    }
  }
  */

  return true;
}

SPDY4HeadersCodec::KVEntry* SPDY4HeadersCodec::LookupKeyValue(const KVPair& kv) {
  //cout << "kv lookup contains: \"" << kv.key << "\" \"" << kv.val << "\"\n";
  KVLookup::iterator kv_i = kv_lookup.find(KVPPair(kv));
  if (kv_i != kv_lookup.end()) {
    //cout << " found: " << kv_i->second << " " << *(kv_i->second) << "\n";
    return kv_i->second;
  }
  //cout << "...Nothing found\n";
  return 0;
}

SPDY4HeadersCodec::KVEntry* SPDY4HeadersCodec::LookupKey(const KVPair& kv) {
  KLookup::iterator k_i = k_lookup.find(const_cast<string*>(&kv.key));
  //cout << "k lookup contains: " << kv.key;
  if (k_i != k_lookup.end()) {
    //cout << " found: " << k_i->second << " " << *(k_i->second) << "\n";
    return k_i->second;
  }
  //cout << "...Nothing found\n";
  return 0;
}

void SPDY4HeadersCodec::TouchHeaderGroupEntry(HeaderGroup::iterator i) {
  i->second = frame_count;
}

bool SPDY4HeadersCodec::HeaderGroupEntryUpToDate(HeaderGroup::iterator i) const {
  return i->second == frame_count;
}

void SPDY4HeadersCodec::FrameDone() {
  ++frame_count;
}

void SPDY4HeadersCodec::DiscoverTurnOffs(vector<LRUIdx>* turn_offs,
                                         uint32_t group_id) {
  HeaderGroup& header_group = header_groups[group_id];
  for (HeaderGroup::iterator i = header_group.begin();
       i != header_group.end();++i) {
    if (!HeaderGroupEntryUpToDate(i)) {
      turn_offs->push_back(i->first);
    }
  }
}

void SPDY4HeadersCodec::WriteControlFrameBoilerplate(OutputStream* os,
                                                     uint32_t frame_len,
                                                     uint8_t flags,
                                                     uint32_t stream_id,
                                                     uint8_t type) {
  os->WriteUint16(frame_len);
  os->WriteUint8(flags);
  WriteControlFrameStreamId(os, stream_id);
  os->WriteUint8(type);
}

void SPDY4HeadersCodec::WriteControlFrameStreamId(OutputStream* os, uint32_t stream_id) {
  if (stream_id & 0x8000U) {
    abort(); // can't have that top-order bit set....
  }
  os->WriteUint32(0x8000U | stream_id);
}
uint32_t SPDY4HeadersCodec::WriteClone(OutputStream* os, const CloneOp& clone) {
  WriteOpcode(os, CLONE);
  WriteLRUIdx(os, clone.kv_entry->GetLRUIdx());
  WriteString(os, clone.val);
  return 0;
}

void SPDY4HeadersCodec::ExecuteClone(uint32_t group_id, const CloneOp& clone) {
  const KVEntry* kve = clone.kv_entry;
  const string& key = kve->kv.key;
  const string& val = clone.val;
  cout << "Executing Clone: \"" << key << "\" \"" << val << "\"\n";
  AddLine(group_id, key, val);
}

uint32_t SPDY4HeadersCodec::WriteKVSto(OutputStream* os, const KVStoOp& kvsto) {
  WriteOpcode(os, KVSTO);
  WriteString(os, kvsto.key);
  WriteString(os, kvsto.val);
  return 0;
}

bool SPDY4HeadersCodec::ToggleHeaderGroupEntry(uint32_t group_id,
                                               LRUIdx lru_idx) {
  assert(group_id > 0);
  HeaderGroups::iterator hgs_i = header_groups.find(group_id);
  if (hgs_i == header_groups.end()) {
    cout << "on (creating HG " << group_id << ")";
    hgs_i = header_groups.insert(make_pair(group_id, HeaderGroup())).first;
    hgs_i->second.insert(make_pair(lru_idx, frame_count));
    return false;
  }

  HeaderGroup& header_group = hgs_i->second;
  HeaderGroup::iterator hg_i = header_group.find(lru_idx);
  bool was_visible = (hg_i != header_group.end());
  if (!was_visible) {
    cout << "on";
    header_group.insert(make_pair(lru_idx, frame_count));
  } else {
    cout << "off";
    header_group.erase(hg_i);
  }
  return was_visible;
}

// return value indicates whether it was visibile before this call.
bool SPDY4HeadersCodec::SetHeaderGroupEntry(uint32_t group_id,
                                            LRUIdx lru_idx,
                                            bool should_be_visible) {
  assert(group_id > 0);
  HeaderGroups::iterator hgs_i = header_groups.find(group_id);
  if (hgs_i == header_groups.end()) {
    if (!should_be_visible) return false;
    hgs_i = header_groups.insert(make_pair(group_id, HeaderGroup())).first;
    hgs_i->second.insert(make_pair(lru_idx, frame_count));
    return false;
  }

  HeaderGroup& header_group = hgs_i->second;
  HeaderGroup::iterator hg_i = header_group.find(lru_idx);
  bool was_visible = (hg_i != header_group.end());
  if (should_be_visible && !was_visible) {
    header_group.insert(make_pair(lru_idx, frame_count));
  } else if (!should_be_visible && was_visible) {
    header_group.erase(hg_i);
  }
  return was_visible;
}

void SPDY4HeadersCodec::AddLine(uint32_t group_id,
                                const string& key, const string& val) {
  KVEntry* kve = new KVEntry;
  kve->kv.key = key;
  kve->kv.val = val;
  kve->lru_idx = GetNextLruIdx();
  k_lookup[&kve->kv.key] = kve;
  KVLookup::iterator kv_i = kv_lookup.insert(make_pair(KVPPair(kve->kv), kve)).first;
  //cout << "Just added: " << kv_i->first << "\n";
  lru_idx_to_kve_map.insert(make_pair(kve->lru_idx, kve));

  if (group_id > 0) {
    // add the entry to that group.
    SetHeaderGroupEntry(group_id, kve->lru_idx, true);
  }
}

void SPDY4HeadersCodec::ExecuteKVSto(uint32_t group_id, const KVStoOp& kvsto) {
  AddLine(group_id, kvsto.key, kvsto.val);
  current_state_size += kvsto.DeltaSize();
  cout << "Executing KVSto: \"" << kvsto.key << "\" \"" << kvsto.val << "\"\n";
}

void SPDY4HeadersCodec::ExecuteToggle(uint32_t group_id, LRUIdx lru_idx) {
  cout << "Executing Toggle: " << lru_idx << " ";
  ToggleHeaderGroupEntry(group_id, lru_idx);
  cout << "\n";
}

uint32_t SPDY4HeadersCodec::WriteToggle(OutputStream* os, LRUIdx lru_idx) {
  WriteOpcode(os, TOGGLE);
  WriteLRUIdx(os, lru_idx);
  return 0;
}

void SPDY4HeadersCodec::ExecuteToggleRange(uint32_t group_id,
                                           LRUIdx lru_idx_start,
                                           LRUIdx lru_idx_end) {
}
uint32_t SPDY4HeadersCodec::WriteToggleRange(OutputStream* os,
                                             LRUIdx lru_idx_first,
                                             LRUIdx lru_idx_last) {
  WriteOpcode(os, TOGGLE);
  WriteLRUIdx(os, lru_idx_first);
  WriteLRUIdx(os, lru_idx_last);
  return 0;
}

void SPDY4HeadersCodec::WriteOpcode(OutputStream* os, int opcode) {
  os->WriteUint8(opcode);
}

void SPDY4HeadersCodec::WriteLRUIdx(OutputStream* os, LRUIdx idx) {
  os->WriteUint16(idx);
}

void SPDY4HeadersCodec::WriteString(OutputStream* os, const string& str) {
  os->WriteBytes(str.begin(), str.end());
}



