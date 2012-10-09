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
using std::hash;
using std::list;
using std::map;
using std::multimap;


string spdy4_default_dict[][2] = {
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

template <typename T>
class IDStore {
  set<T> ids;
  T next_idx;
 public:
  IDStore() : next_idx(0) {}

  T GetNext() {
    if (!ids.empty()) {
      T retval = *ids.begin();
      ids.erase(ids.begin());
      return retval;
    }
    return ++next_idx;
  }

  void DoneWithId(T id) {
    ids.insert(id);
  }
};

class Storage {
 public:
  IDStore<LRUIdx> key_ids;
  IDStore<LRUIdx> lru_ids;
  size_t state_size;

  Storage() : state_size(0) {}

  struct ValEntry;

  typedef map<string, ValEntry*> ValMap;

  struct KeyEntry {
    LRUIdx key_idx;
    size_t refcnt;
    ValMap valmap;

    KeyEntry(): key_idx(0), refcnt(0) {}
    KeyEntry(LRUIdx key_idx): key_idx(key_idx), refcnt(0) {}
  };

  typedef map<string, KeyEntry> KeyMap;
  typedef list<ValEntry*> LRU;

  struct ValEntry {
    KeyMap::iterator k_i;
    ValMap::iterator v_i;
    LRU::iterator lru_i;
    LRUIdx lru_idx;

    const string& key() const {
      return k_i->first;
    }
    const string& val() const {
      return v_i->first;
    }
  };

  KeyMap keymap;
  LRU lru;

  struct LookupCache {
    KeyMap::iterator k_i;
    ValMap::iterator v_i;
    LookupCache(KeyMap::iterator k_i) : k_i(k_i) {}
  };

  LookupCache DefaultLookupCache() {
    return LookupCache(keymap.end());
  }

  bool HasKey(const LookupCache& lc) const {
    return lc.k_i != keymap.end();
  }

  bool HasKeyVal(const LookupCache& lc) const {
    return HasKey(lc) && (lc.v_i != lc.k_i->second.valmap.end());
  }

  LRUIdx FindKeyIdxbyKey(LookupCache* lc, const string& key) {
    lc->k_i = keymap.find(key);
    if (lc->k_i == keymap.end()) return 0;
    return lc->k_i->second.key_idx;
  }

  bool FindKey(LookupCache* lc, const string& key) {
    if (lc->k_i != keymap.end()) return false;
    lc->k_i = keymap.find(key);
    if (lc->k_i == keymap.end()) return false;
    return true;
  }

  ValEntry* FindValEntryByKV(LookupCache* lc,
                             const string& key, const string& val) {
    if (!FindKey(lc, key)) return 0;
    ValMap& valmap = lc->k_i->second.valmap;
    lc->v_i = valmap.find(val);
    if (lc->v_i == valmap.end());
    return lc->v_i->second;
  }

  void FindOrAddKey(LookupCache* lc, const string& key) {
    if (lc->k_i == keymap.end()) {
      lc->k_i = keymap.find(key);
      if (lc->k_i == keymap.end()) {
        lc->k_i = keymap.insert(make_pair(key,
                                          KeyEntry(key_ids.GetNext()))).first;
      }
    }
  }

  ValEntry* InsertVal(LookupCache* lc, const string& val) {
    assert(lc->k_i != keymap.end());
    ValEntry* entry = new ValEntry;
    lc->v_i = lc->k_i->second.valmap.insert(make_pair(val, entry)).first;
    entry->lru_idx = 0;
    entry->k_i = lc->k_i;
    entry->v_i = lc->v_i;
    entry->lru_i = lru.end();
    return entry;
  }

  void AddKV(LookupCache* lc, const string& key, const string& val) {
    FindOrAddKey(lc, key);
    InsertVal(lc, val);
  }

  void AddToBackOfLRU(ValEntry* entry) {
    if (entry->lru_i != lru.end()) {
      abort();
    }
    lru.insert(lru.end(), entry);
    entry->lru_idx = lru_ids.GetNext();
    entry->lru_i = --(lru.end());
  }

  void MoveToHeadOfLRU(ValEntry* entry) {
    if (entry->lru_i == lru.end()) {
      abort();
    }
    lru.splice(lru.end(), lru, entry->lru_i);
    entry->lru_i = --(lru.end());
  }

  void RemoveFromLRU(ValEntry* entry) {
    if (entry->lru_i == lru.end())
      return;
    lru_ids.DoneWithId(entry->lru_idx);
    lru.erase(entry->lru_i);
    entry->lru_i = lru.end();
  }

  void RemoveFromValMap(ValEntry* entry) {
    RemoveFromLRU(entry);
    assert(entry->k_i != keymap.end());
    KeyEntry& keyentry = entry->k_i->second;
    if (keyentry.valmap.end() != entry->v_i)
      keyentry.valmap.erase(entry->v_i);
    entry->v_i = keyentry.valmap.end();
  }

  void MaybeRemoveFromKeyMap(ValEntry* entry) {
    if (entry->k_i == keymap.end())
      return;
    KeyEntry& keyentry = entry->k_i->second;
    if (keyentry.valmap.empty() && keyentry.refcnt == 0) {
      key_ids.DoneWithId(keyentry.key_idx);
      keymap.erase(entry->k_i);
      entry->k_i = keymap.end();
    }
  }

  void RemoveVal(ValEntry* entry) {
    RemoveFromValMap(entry); // this will remove it from the LRU if necessary.
    MaybeRemoveFromKeyMap(entry);
    delete entry;
  }
};

class SPDY4HeadersCodecImpl {
 public:
  enum {CLONE, KVSTO, TOGGLE, TOGGLE_RANGE};

  Huffman huff;
  Storage storage;
  typedef Storage::ValEntry ValEntry;
  typedef Storage::LookupCache LookupCache;

  uint32_t max_total_header_storage_size;
  uint32_t max_header_groups;
  uint32_t max_table_entries;
  // ideally, you'd use a ring-buffer to store the text data.
  uint32_t frame_count;
  uint32_t current_state_size;

  typedef map<Storage::ValEntry*, uint32_t> HeaderGroup;
  typedef map<uint32_t, HeaderGroup> HeaderGroups;
  HeaderGroups header_groups;

  struct KVStoOp {
    const string* key_p;
    const string* val_p;
   public:
    KVStoOp(const string* key, const string* val) : key_p(key), val_p(val) { }
    KVStoOp() : key_p(0), val_p(0) {}
    const string& key() const { return *key_p; }
    const string& val() const { return *val_p; }
    size_t DeltaSize() const{
      return key().size() + val().size();
    }
  };

  struct CloneOp {
    LookupCache lc;
    const string* val_p;
   public:
    CloneOp(const LookupCache& lc, const string* val) :
        lc(lc), val_p(val) {}

    LRUIdx idx() const { return lc.k_i->second.key_idx; }
    const string& key() const { return lc.k_i->first; }
    const string& val() const { return *val_p; }

    size_t DeltaSize() const{
      return key().size() + val().size();
    }
  };

  struct ToggleOp {
    Storage::ValEntry* entry;
   public:
    explicit ToggleOp(Storage::ValEntry* kv) : entry(kv) {}
    ToggleOp() : entry(0) {}
  };


  SPDY4HeadersCodecImpl(const FreqTable& sft) :
      max_total_header_storage_size(10*1024),
      max_header_groups(1),
      max_table_entries(640),
      frame_count(0),
      current_state_size(0)
  {
    huff.Init(sft);
    for (unsigned int i = 0;
         i < sizeof(spdy4_default_dict) / sizeof(spdy4_default_dict[0]);
         ++i) {
      ExecuteKVSto(0,
                   KVStoOp(&spdy4_default_dict[i][0],
                           &spdy4_default_dict[i][1]));
    }
  }

  struct Instructions {
    vector<ToggleOp> turn_ons;
    vector<ToggleOp> turn_offs;
    vector<CloneOp> clones;
    vector<KVStoOp> kvstos;
  };

  void ProcessLine(Storage::LookupCache* key_lc,
                   const string& val,
                   bool can_clone,
                   HeaderGroup* header_group,
                   uint32_t group_id,
                   size_t* size_delta,
                   Instructions* instrs) {
    const string& key = key_lc->k_i->first;
    LookupCache lc = *key_lc;
    ValEntry* entry = storage.FindValEntryByKV(&lc, key, val);
    if (entry) {
      // So, the key-value exists, but we don't yet know if it is already
      // turned-on in the header-group.

      HeaderGroup::iterator hg_i = header_group->find(entry);
      if (hg_i == header_group->end()) {
        // The key-value exists, but isn't turned on.
        instrs->turn_ons.push_back(ToggleOp(entry));
        ExecuteToggle(group_id, instrs->turn_ons.back());
      } else {
        // Touch the current entry so that we don't prune this entry when we
        // prune the header-group for items that aren't in the current set of
        // headers.
        TouchHeaderGroupEntry(hg_i);
      }
    } else if (can_clone) {
      instrs->clones.push_back(CloneOp(lc, &val));
    } else {
      // Neither the line exists, nor the key exists in the LRU.
      // We'll need to emit a KVSto to store the key and value
      instrs->kvstos.push_back(KVStoOp(&key, &val));
      *size_delta += instrs->kvstos.back().DeltaSize();
    }
  }

  void ExecuteInstructions(uint32_t group_id, const Instructions& instrs) {
    // No need to execute the turn-ons-- they've already been executed.
    for (vector<ToggleOp>::const_iterator i = instrs.turn_offs.begin();
         i != instrs.turn_offs.end();
         ++i) {
      ExecuteToggle(group_id, *i);
    }
    for (vector<CloneOp>::const_iterator i = instrs.clones.begin();
         i != instrs.clones.end();
         ++i) {
      ExecuteClone(group_id, *i);
    }
    for (vector<KVStoOp>::const_iterator i = instrs.kvstos.begin();
         i != instrs.kvstos.end();
         ++i) {
      ExecuteKVSto(group_id, *i);
    }
  }

  // There are a number of ways to accomplish this.
  // The way that is used here is probably not one of the most efficient ways.
  // Mechanisms that could be used instead to improve performance,
  // whether by increasing compression efficiency, or by decreasing
  // encoding/decoding time are:
  // 1) Use an actual tree to store the key and key-value index.
  //    Since the comparison for Key-Vals is key-major val-minor,
  //    this could work using just one tree.
  // 2) Use a ring buffer for the text for keys (byte aligned)
  //    Use a ring buffer for the text of vals (byte aligned)
  //    use a ring buffer for the LRUs, which contains a pair of indices to the
  //    ring buffer
  //    Every time a key or val is referenced move its data to the front of the
  //    ring buffer
  //    This would take up more state space, but it would decrease the number of
  //    gaps in the 'toggles' that need to be sent, and thus reduce bytes-on-wire.
  // 3) Renumber every referenced element when it is referenced.
  //    This is similar #2, but could be done with the current implementation.
  void OutputCompleteHeaderFrame(OutputStream* os,
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
    Instructions instrs;
    vector<ToggleOp>::iterator first_turn_on;
    vector<ToggleOp>::iterator first_turn_off;
    vector<CloneOp>::iterator first_clone;
    vector<KVStoOp>::iterator first_kvsto;

    size_t size_delta = 0;
    if (header_groups.find(group_id) == header_groups.end()) {
      header_groups[group_id] = HeaderGroup();
    }
    HeaderGroup& header_group = header_groups[group_id];
    list<string> cookie_strs;  // Yes, this must exist for the func scope.
    vector<Storage::LookupCache> key_lookups;
    vector<Storage::LookupCache>::iterator key_lu_it;

    // Since we'll be going eliminating entries as we construct operations,
    // we'll need to go through and ensure that the key for each of the things
    // which are referenced by this set of headers is not eliminated.
    // We do this by incrementing a refcnt for every key that exists which
    // matches a key in the current HeaderFrame.
    for (HeaderFrame::const_iterator hf_i = headers.begin();
         hf_i != headers.end();
         ++hf_i) {
      const string& key = hf_i->key;
      Storage::LookupCache lc = storage.DefaultLookupCache();
      storage.FindKey(&lc, key);
      key_lookups.push_back(lc);
      if (storage.HasKey(lc)) lc.k_i->second.refcnt++;
    }

    key_lu_it = key_lookups.begin();
    for (HeaderFrame::const_iterator hf_i = headers.begin();
         hf_i != headers.end();
         ++hf_i, ++key_lu_it) {
      const string& key = hf_i->key;
      const string& val = hf_i->val;
      bool can_clone = storage.HasKey(*key_lu_it);
      Storage::LookupCache lc = *key_lu_it;
      storage.FindOrAddKey(&lc, key);

      size_t crumb_end;
      if (key == "cookie" &&
          (crumb_end = val.find_first_of(';')) != string::npos) {
        bool can_clone_cookie = can_clone;
        size_t crumb_begin = 0;
        Storage::LookupCache clc = lc;

        while (crumb_begin < val.size()) {
          crumb_end = val.find_first_of(';', crumb_begin);
          cookie_strs.push_back(val.substr(crumb_begin,
                                           crumb_end - crumb_begin));
          const string& crumb = cookie_strs.back();
          cout << "cookie key: " << key << " val : " << crumb << "\n";
          ProcessLine(&clc, crumb, can_clone_cookie, &header_group,
                      group_id, &size_delta, &instrs);
          can_clone_cookie = true;
          if (crumb_end == string::npos) break;
          crumb_begin = val.find_first_not_of(' ', crumb_end + 1);
        }
      } else {
        ProcessLine(&lc, val, can_clone, &header_group,
                    group_id, &size_delta, &instrs);
      }
      if (storage.HasKey(lc)) lc.k_i->second.refcnt--;
    }

    // Here we discover any elements in the header_group which are referenced
    // but don't exist in the header frame presented to this function.
    // These need to be toggled off.
    // Note that this is done after doing deletions due to exceeding the max
    // buffer size, since some of the deletions may have already cleared some of
    // the elements we must be turning off.
    DiscoverTurnOffs(&(instrs.turn_offs), stream_id);

    first_turn_on = instrs.turn_ons.begin();
    first_turn_off = instrs.turn_offs.begin();
    first_clone = instrs.clones.begin();
    first_kvsto = instrs.kvstos.begin();

    ExecuteInstructions(group_id, instrs);
    // We now need to be sure that this will fit in memory appropriately.
    //
    // This involves calculating the store size for each Clone and KVSto, and
    // adding it to the current size. If that summation exceeds the max size:
    //
    // for each element in clone, set the 'keep-me' bit;
    // size_t items_to_delete_from_head = 0;
    // size_t state_size = storage.state_size;
    // if ((current_state_size + size_delta) > max_total_header_storage_size) {
    //   // Since the operations here will cause us to exceed the maximum state
    //   // size, we must remove elements from the head of the LRU.
    //   size_t delta = 0;
    //   size_t target_delta = ((size_delta + state_size) -
    //                          max_total_header_storage_size);
    //   for (LRUList::iterator lru_i = lru.begin(); lru_i != lru.end(); ++lru_i) {
    //     cout << "Will remove: " << (*lru_i)->lru_idx << "\n";
    //     delta += (*lru_i)->kv.size();
    //     ++items_to_delete_from_head;
    //     if (delta >= target_delta) break;
    //   }
    // }
    // for (size_t i = 0; i < items_to_delete_from_head; ++i) {
    //   ValEntry *entry = lru.front();
    //   RemoveAndCleanupLine(entry);
    // }
    // cout << "lru size: " << lru.size() << "\n";

    // Order of serialization:
    //   1) toggles
    //   2) remove
    //   3) clone
    //   4) kvsto
    // We first want to serialize the toggles-on.
    // Then we want to serialize the remove operations.
    // Then we want to serialize the toggles-off.
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
                                     instrs,
                                     &first_turn_on,
                                     &first_turn_off,
                                     &first_clone,
                                     &first_kvsto,
                                     headers_end_flag,
                                     stream_id));

    FrameDone();
    cout << "headers.size(): " << headers.size()
                                  << " header_group.size(): " << header_group.size()
                                                                 <<"\n";



    for (HeaderGroup::iterator i = header_group.begin();
         i != header_group.end();
         ++i) {
      cout << "HG[" << group_id << "]: "
        << "(" << i->first->k_i->second.key_idx  << "," << i->first->lru_idx << ")"
        << "(" << i->first->k_i->first << "," << i->first->v_i->first << ")"
        << "(Generation: " << i->second << ")"
        <<"\n";
    }
  }

  bool SerializeAllInstructions(
      OutputStream* os,
      const Instructions& instrs,
      vector<ToggleOp>::iterator* first_turn_on,
      vector<ToggleOp>::iterator* first_turn_off,
      vector<CloneOp>::iterator* first_clone,
      vector<KVStoOp>::iterator* first_kvsto,
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
    for (; *first_turn_on != instrs.turn_ons.end(); ++(*first_turn_on)) {
      WriteToggle(os, (*first_turn_on)->entry->lru_idx);
    }
    for (; *first_turn_off != instrs.turn_offs.end(); ++(*first_turn_off)) {
      WriteToggle(os, (*first_turn_off)->entry->lru_idx);
    }
    for (; *first_clone != instrs.clones.end(); ++(*first_clone)) {
      WriteClone(os, **first_clone);
    }
    for (; *first_kvsto != instrs.kvstos.end(); ++(*first_kvsto)) {
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

  void TouchHeaderGroupEntry(HeaderGroup::iterator i) {
    i->second = frame_count;
    cout << "Touching: " << i->first->lru_idx;
    MoveToHeadOfLRU(i->first);
    cout << " new idx: " << i->first->lru_idx;
    cout << "\n";
  }

  bool HeaderGroupEntryUpToDate(HeaderGroup::iterator i) const {
    return i->second == frame_count;
  }

  void FrameDone() {
    ++frame_count;
  }

  void DiscoverTurnOffs(vector<ToggleOp>* turn_offs,
                        uint32_t group_id) {
    HeaderGroup& header_group = header_groups[group_id];
    for (HeaderGroup::iterator i = header_group.begin();
         i != header_group.end();++i) {
      if (!HeaderGroupEntryUpToDate(i)) {
        turn_offs->push_back(ToggleOp(i->first));
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
  uint32_t WriteClone(OutputStream* os, const CloneOp& clone) {
    WriteOpcode(os, CLONE);
    WriteLRUIdx(os, clone.idx());
    WriteString(os, clone.val());
    return 0;
  }

  void ExecuteClone(uint32_t group_id, const CloneOp& clone) {
    const string& key = clone.key();
    const string& val = clone.val();
    cout << "Executing Clone: \"" << key << "\" \"" << val << "\"\n";
    AddLine(group_id, clone.lc, val);
    // If we knew for certain that this meant that the previous header line was
    // being supplanted, we'd also set visibility of the thing which we're
    // cloning to false.
    // SetHeaderGroupEntry(group_id, clone.entry, false);
  }

  uint32_t WriteKVSto(OutputStream* os, const KVStoOp& kvsto) {
    WriteOpcode(os, KVSTO);
    WriteString(os, kvsto.key());
    WriteString(os, kvsto.val());
    return 0;
  }

  bool ToggleHeaderGroupEntry(uint32_t group_id,
                              ValEntry* entry) {
    assert(group_id > 0);
    HeaderGroups::iterator hgs_i = header_groups.find(group_id);
    if (hgs_i == header_groups.end()) {
      cout << "on (creating HG " << group_id << ")";
      hgs_i = header_groups.insert(make_pair(group_id, HeaderGroup())).first;
      hgs_i->second.insert(make_pair(entry, frame_count));
      return false;
    }

    HeaderGroup& header_group = hgs_i->second;
    HeaderGroup::iterator hg_i = header_group.find(entry);
    bool was_visible = (hg_i != header_group.end());
    if (!was_visible) {
      cout << "on";
      header_group.insert(make_pair(entry, frame_count));
    } else {
      cout << "off";
      header_group.erase(hg_i);
    }
    return was_visible;
  }

  // return value indicates whether it was visibile before this call.
  bool SetHeaderGroupEntry(uint32_t group_id,
                           ValEntry* entry,
                           bool should_be_visible) {
    assert(group_id > 0);
    HeaderGroups::iterator hgs_i = header_groups.find(group_id);
    if (hgs_i == header_groups.end()) {
      if (!should_be_visible) return false;
      hgs_i = header_groups.insert(make_pair(group_id, HeaderGroup())).first;
      hgs_i->second.insert(make_pair(entry, frame_count));
      return false;
    }

    HeaderGroup& header_group = hgs_i->second;
    HeaderGroup::iterator hg_i = header_group.find(entry);
    bool was_visible = (hg_i != header_group.end());
    if (should_be_visible && !was_visible) {
      header_group.insert(make_pair(entry, frame_count));
    } else if (!should_be_visible && was_visible) {
      header_group.erase(hg_i);
    }
    return was_visible;
  }

  void AddLine(uint32_t group_id, const LookupCache& lc, const string& val) {
    LookupCache tlc = lc;
    ValEntry* entry = storage.InsertVal(&tlc, val);

    if (group_id > 0) {
      storage.AddToBackOfLRU(entry);
      // add the entry to that group.
      SetHeaderGroupEntry(group_id, entry, true);
    }
  }

  void RemoveAndCleanupLine(ValEntry* entry) {
    for(HeaderGroups::iterator hgs_i = header_groups.begin();
        hgs_i != header_groups.end();
        ++hgs_i) {
      hgs_i->second.erase(entry);
    }
    storage.RemoveVal(entry);
  }

  void ExecuteKVSto(uint32_t group_id, const KVStoOp& kvsto) {
    LookupCache lc = storage.DefaultLookupCache();
    storage.FindOrAddKey(&lc, kvsto.key());
    AddLine(group_id, lc, kvsto.val());
    cout << "Executing KVSto: \"" << kvsto.key() << "\" \"" << kvsto.val() << "\"\n";
  }

  void ExecuteToggle(uint32_t group_id, const ToggleOp& to) {
    ValEntry* entry = to.entry;
    cout << "Executing Toggle: " << entry->lru_idx << " ";
    if (!ToggleHeaderGroupEntry(group_id, entry)) {
      MoveToHeadOfLRU(entry);
      cout << " new id: " << entry->lru_idx;
    }
    //cout << " key: " << entry->kv.key();
    cout << "\n";
  }

  void MoveToHeadOfLRU(ValEntry* entry) {
    storage.MoveToHeadOfLRU(entry);
  }

  uint32_t WriteToggle(OutputStream* os, LRUIdx lru_idx) {
    WriteOpcode(os, TOGGLE);
    WriteLRUIdx(os, lru_idx);
    return 0;
  }

  uint32_t WriteToggleRange(OutputStream* os,
                            LRUIdx lru_idx_first,
                            LRUIdx lru_idx_last) {
    WriteOpcode(os, TOGGLE);
    WriteLRUIdx(os, lru_idx_first);
    WriteLRUIdx(os, lru_idx_last);
    return 0;
  }

  void WriteOpcode(OutputStream* os, int opcode) {
    os->WriteUint8(opcode);
  }

  void WriteLRUIdx(OutputStream* os, LRUIdx idx) {
    os->WriteUint16(idx);
  }

  void WriteString(OutputStream* os, const string& str) {
    os->WriteBytes(str.begin(), str.end());
  }

  size_t CurrentStateSize() const {
    return current_state_size;
  }

  bool StorageRemaining(size_t additional_size) {
    return ((CurrentStateSize() + additional_size) <
            max_total_header_storage_size);
  }

};

////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////


SPDY4HeadersCodec::SPDY4HeadersCodec(const FreqTable& sft) {
  impl = new SPDY4HeadersCodecImpl(sft);
}

size_t SPDY4HeadersCodec::CurrentStateSize() const {
  return impl->CurrentStateSize();
}

void SPDY4HeadersCodec::OutputCompleteHeaderFrame(OutputStream* os,
                                              uint32_t stream_id,
                                              uint32_t group_id,
                                              const HeaderFrame& headers,
                                              bool this_ends_the_frame) {
  impl->OutputCompleteHeaderFrame(os, stream_id, group_id,
                                   headers, this_ends_the_frame);
}

