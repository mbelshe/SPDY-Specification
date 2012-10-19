// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
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
#include <algorithm>

#include "spdy4_headers_codec.h"
#include "header_freq_tables.h"
#include "huffman.h"
#include "utils.h"
#include "trivial_http_parse.h"

using std::min;
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

typedef uint32_t GroupId;
typedef uint32_t StreamId;

#ifdef DEBUG
#define DEBUG_PRINT(X) X
#else
#define DEBUG_PRINT(X)
#endif

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

  struct ValEntry;

  typedef multimap<string, ValEntry*> ValMap;

  struct KeyEntry {
    LRUIdx key_idx;
    size_t refcnt;
    ValMap valmap;

    void IncRefcnt() {
      ++refcnt;
    }

    void DecRefcnt() {
      if (refcnt == 0) abort();
      --refcnt;
    }

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
    bool lru_i_valid;
    uint64_t seq_num;
    ValEntry() : lru_idx(0), lru_i_valid(false) {}

    const string& key() const {
      return k_i->first;
    }
    const string& val() const {
      return v_i->first;
    }
  };

  class ValEntryRemovalInterface {
    public:
    virtual void RemoveValEntry(ValEntry* entry) = 0;
    virtual ~ValEntryRemovalInterface() {}
  };

  IDStore<LRUIdx> key_ids;
  IDStore<LRUIdx> lru_ids;

  size_t state_size;
  size_t max_state_size;
  size_t num_vals;
  size_t max_vals;
  KeyMap keymap;
  LRU lru;
  LRU::iterator pin_it;
  bool pinned;
  ValEntryRemovalInterface* remove_val_cb;

  struct LookupCache {
    KeyMap::iterator k_i;
    bool k_i_valid;
    ValMap::iterator v_i;
    bool v_i_valid;
    LookupCache(): k_i_valid(false), v_i_valid(false) {}
    void CopyKey(const LookupCache& lc) {
      k_i_valid = lc.k_i_valid;
      if (k_i_valid) {
        k_i = lc.k_i;
      }
    }
    LookupCache(const LookupCache& lc) {
      *this = lc;
    }

    LookupCache& operator=(const LookupCache& lc) {
      k_i_valid = lc.k_i_valid;
      if (k_i_valid) {
        k_i = lc.k_i;
      }
      v_i_valid = lc.v_i_valid;
      if (v_i_valid) {
        v_i = lc.v_i;
      }
      return *this;
    }
    bool HasKey() const { return k_i_valid; }
    bool HasVal() const { return v_i_valid; }
  };

  LRUIdx FindKeyIdxbyKey(LookupCache* lc, const string& key) {
    lc->k_i = keymap.find(key);
    if (lc->k_i == keymap.end()) return 0;
    lc->k_i_valid = true;
    return lc->k_i->second.key_idx;
  }

  bool FindKey(LookupCache* lc, const string& key) {
    if (lc->k_i_valid) return true;
    lc->k_i = keymap.find(key);
    if (lc->k_i == keymap.end()) return false;
    lc->k_i_valid = true;
    return true;
  }

  void PinLRUEnd() {
    if (pinned) lru.erase(pin_it);
    pin_it = lru.insert(lru.end(), 0);
    pinned = true;
  }

  void UnPinLRUEnd() {
    if (!pinned) return;
    MakeSpace(0, 0);
    lru.erase(pin_it);
    pin_it = lru.end();
    pinned = false;
  }

  bool PopOne() {
    DEBUG_PRINT(cout << "Popping one: ";)
    if (lru.empty()) abort();
    ValEntry* entry = lru.front();
    if (entry == 0) { // we've hit the pin.
      DEBUG_PRINT(cout << " ... or not. Hit the pin.\n";)
      return false;
    }
    DEBUG_PRINT(
    cout << entry->seq_num
         << " \"" << entry->key()
         << "\" \"" << entry->val()
         << "\" (" << entry->k_i->second.key_idx
         << "," << entry->lru_idx
         << ")";
    cout << "\n";
    )

    if (remove_val_cb) {
      remove_val_cb->RemoveValEntry(entry);
    }
    RemoveVal(entry); // that will pop the front entry already.
    delete entry;
    return true;
  }

  void MakeSpace(size_t space_required, size_t adding_val) {
    while (num_vals + adding_val > max_vals) {
      //DEBUG_PRINT(
      //cout << "num_vals(" << num_vals
      //  << ") + 1 > max_vals(" << max_vals << ") ";
      //  )
      PopOne();
    }
    while (state_size + space_required > max_state_size) {
      // DEBUG_PRINT(
      // cout << "state_size(" << state_size
      //     << ") + space_required(" << space_required
      //     << ")  > max_state_size(" << max_state_size << ") ";
      // )
      if (!PopOne()) break;
    }
  }

  ValEntry* FindValEntryByKV(LookupCache* lc,
                             const string& key,
                             const string& val) {
    if (!FindKey(lc, key)) return 0;
    ValMap& valmap = lc->k_i->second.valmap;
    lc->v_i = valmap.find(val);
    if (lc->v_i == valmap.end()) return 0;
    lc->v_i_valid = true;
    return lc->v_i->second;
  }

  void FindOrAddKey(LookupCache* lc, const string& key) {
    if (lc->k_i_valid == false) {
      lc->k_i = keymap.find(key);
      if (lc->k_i == keymap.end()) {
        MakeSpace(key.size(), 1);
        lc->k_i = keymap.insert(make_pair(key,
                                          KeyEntry(key_ids.GetNext()))).first;
        state_size += key.size();
      }
      lc->k_i_valid = true;
    }
  }

  ValEntry* InsertVal(LookupCache* lc, const string& val) {
    assert(lc->k_i_valid);
    assert(lc->k_i != keymap.end());

    lc->k_i->second.refcnt++;
    ValEntry* entry = new ValEntry;
    entry->seq_num = ++seq_num;
    MakeSpace(val.size(), 0);
    lc->k_i->second.refcnt--;

    lc->v_i = lc->k_i->second.valmap.insert(make_pair(val, entry));
    lc->v_i_valid = true;
    ++num_vals;
    state_size += val.size();
    entry->lru_idx = 0;
    entry->k_i = lc->k_i;
    entry->v_i = lc->v_i;

    entry->lru_i_valid = false;
    entry->lru_i = lru.end();
    return entry;
  }

  void AddToHeadOfLRU(ValEntry* entry) {
    if (entry->lru_i_valid) {
      abort();
    }
    entry->lru_i = lru.insert(lru.end(), entry);
    entry->lru_i_valid = true;
    entry->lru_idx = lru_ids.GetNext();
  }

  void MoveToHeadOfLRU(ValEntry* entry) {
    if (!entry->lru_i_valid)
      return;
    assert(lru.size() > 0);
    assert(entry->lru_i_valid);
    assert(entry->lru_i != lru.end());
    lru.splice(lru.end(), lru, entry->lru_i);
    assert(lru.size() > 0);
    entry->lru_i = --(lru.end());
    assert(entry->lru_i != lru.end());
  }

  void RemoveFromLRU(ValEntry* entry) {
    if (!entry->lru_i_valid)
      return;
#ifdef DEBUG
    cout << "Removing from LRU: "
          << " \"" << entry->key()
          << "\" \"" << entry->val()
          << "\" (" << entry->k_i->second.key_idx
          << "," << entry->lru_idx
          << ")\n";
#endif
    lru_ids.DoneWithId(entry->lru_idx);
    if (entry->lru_i_valid) lru.erase(entry->lru_i);
    entry->lru_i = lru.end();
    entry->lru_i_valid = false;
  }

  void RemoveFromValMap(ValEntry* entry) {
    assert(entry->k_i != keymap.end());
#ifdef DEBUG
    cout << "Removing entry: "
      << " \"" << entry->key()
      << "\" \"" << entry->val()
      << "\" (" << entry->k_i->second.key_idx
      << "," << entry->lru_idx
      << ")\n";
#endif
    state_size -= entry->v_i->first.size();
    KeyEntry& keyentry = entry->k_i->second;
    assert(keyentry.valmap.end() != entry->v_i);
    keyentry.valmap.erase(entry->v_i);
    --num_vals;
    entry->v_i = keyentry.valmap.end();
  }

  void MaybeRemoveFromKeyMap(ValEntry* entry) {
    if (entry->k_i == keymap.end())
      return;
    KeyEntry& keyentry = entry->k_i->second;
    if (keyentry.valmap.empty() && (keyentry.refcnt == 0)) {
#ifdef DEBUG
      cout << "Removing key: \"" << entry->k_i->first << "\""
           << " with key_idx: " << entry->k_i->second.key_idx
           << " valmap.size: " << keyentry.valmap.size()
           << " refcnt: " << keyentry.refcnt
           << "\n";
#endif
      key_ids.DoneWithId(keyentry.key_idx);
      keymap.erase(entry->k_i);
      entry->k_i = keymap.end();
    }
  }

  void RemoveVal(ValEntry* entry) {
    RemoveFromLRU(entry);
    RemoveFromValMap(entry);
    MaybeRemoveFromKeyMap(entry);
  }

  void SetRemoveValCB(ValEntryRemovalInterface* vri) { remove_val_cb = vri; }

  uint64_t seq_num;

  Storage() :

     state_size(0),
     max_state_size(10*1024),
     num_vals(0),
     max_vals(1024),
     pin_it(lru.end()),
     pinned(false),
     remove_val_cb(0),
     seq_num(0)
  {
    keymap.insert(make_pair("", KeyEntry(0)));
  }
};

enum {CLONE, KVSTO, TOGGLE, TOGGLE_RANGE, EREF};

class SPDY4HeadersCodecImpl : public Storage::ValEntryRemovalInterface {
 public:


  typedef Storage::ValEntry ValEntry;
  typedef Storage::LookupCache LookupCache;
  typedef uint32_t GenerationIdx;


  typedef map<ValEntry*, GenerationIdx> HeaderGroup;
  typedef map<GroupId, HeaderGroup> HeaderGroups;

  struct ERefOp {
    const string* key_p;
    const string* val_p;
   public:
    ERefOp(const string* key, const string* val) : key_p(key), val_p(val) { }
    ERefOp() : key_p(0), val_p(0) {}
    const string& key() const { return *key_p; }
    const string& val() const { return *val_p; }
  };

  struct KVStoOp {
    const string* key_p;
    const string* val_p;
   public:
    KVStoOp(const string* key, const string* val) : key_p(key), val_p(val) { }
    KVStoOp() : key_p(0), val_p(0) {}
    const string& key() const { return *key_p; }
    const string& val() const { return *val_p; }
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
  };

  struct ToggleOp {
    ValEntry* entry;
   public:
    explicit ToggleOp(ValEntry* kv) : entry(kv) {
DEBUG_PRINT(
      cout << "ToggleOp(" << entry->seq_num << ")" <<"\n";
      )
    }
    ToggleOp() : entry(0) {}
    LRUIdx idx() const { return entry->lru_idx; }
    bool operator<(const ToggleOp& ob_b) const {
      return idx() < ob_b.idx();
    }
  };

  struct Instructions {
    typedef vector<ToggleOp> Toggles;
    typedef vector<CloneOp> Clones;
    typedef vector<KVStoOp> KVStos;
    typedef vector<ERefOp> ERefs;

    Toggles toggle_ons;
    Toggles toggle_offs;
    Clones clones;
    KVStos kvstos;
    ERefs erefs;

    void clear() {
      toggle_ons.clear();
      toggle_offs.clear();
      clones.clear();
      kvstos.clear();
      erefs.clear();
    }
  };

  class SerializationInterface {
    public:
    virtual size_t SerializeInstructions(OutputStream* os,
                                         Instructions* instrs,
                                         StreamId stream_id,
                                         bool end_of_frame) = 0;
    virtual ~SerializationInterface(){}
  };

 private:

  HeaderGroups header_groups;
  Huffman huff;
  Storage storage;
  GenerationIdx frame_count;

 public:

  SPDY4HeadersCodecImpl(const FreqTable& sft) : frame_count(0) {
    storage.SetRemoveValCB(this);
    huff.Init(sft);
    for (unsigned int i = 0;
         i < sizeof(spdy4_default_dict) / sizeof(spdy4_default_dict[0]);
         ++i) {
      ExecuteKVSto(0,
                   KVStoOp(&spdy4_default_dict[i][0],
                           &spdy4_default_dict[i][1]));
    }
  }

  virtual void RemoveValEntry(ValEntry* entry) {
    for(HeaderGroups::iterator hgs_i = header_groups.begin();
        hgs_i != header_groups.end();
        ++hgs_i) {
      hgs_i->second.erase(entry);
    }
  };

  void ProcessKV(const LookupCache& key_lc,
                 const string& key,
                 const string& val,
                 HeaderGroup* header_group,
                 GroupId group_id,
                 Instructions* instrs) {
    LookupCache lc = key_lc;
    ValEntry* entry = storage.FindValEntryByKV(&lc, key, val);
    if (entry) {
      // So, the key-value exists, but we don't yet know if it is already
      // turned-on in the header-group.

      HeaderGroup::iterator hg_i = header_group->find(entry);
      if (hg_i == header_group->end()) {
        // The key-value exists, but isn't turned on.
        instrs->toggle_ons.push_back(ToggleOp(entry));
      } else {
        // Touch the current entry so that we don't prune this entry when we
        // prune the header-group for items that aren't in the current set of
        // headers.
        TouchHeaderGroupEntry(hg_i);
      }
    } else if (lc.HasKey()) {
      instrs->clones.push_back(CloneOp(lc, &val));
    } else {
      if (key != ":path") {
        instrs->kvstos.push_back(KVStoOp(&key, &val));
      } else {
        instrs->erefs.push_back(ERefOp(&key, &val));
      }
    }
  }

  void ExecuteInstructionsExceptERefs(GroupId group_id,
                                      const Instructions& instrs) {
    for (vector<ToggleOp>::const_iterator i = instrs.toggle_ons.begin();
         i != instrs.toggle_ons.end();
         ++i) {
      ExecuteToggle(group_id, *i);
    }
    for (vector<ToggleOp>::const_iterator i = instrs.toggle_offs.begin();
         i != instrs.toggle_offs.end();
         ++i) {
      ExecuteToggle(group_id, *i);
    }
    ExecuteClones(group_id, instrs.clones);
    for (vector<KVStoOp>::const_iterator i = instrs.kvstos.begin();
         i != instrs.kvstos.end();
         ++i) {
      ExecuteKVSto(group_id, *i);
    }
    // not executing erefs here.
  }

  void ExecuteInstructions(GroupId group_id,
                           const Instructions& instrs,
                           HeaderFrame* ephemereal_headers) {
    ExecuteInstructionsExceptERefs(group_id, instrs);
    for (vector<ERefOp>::const_iterator i = instrs.erefs.begin();
         i != instrs.erefs.end();
         ++i) {
      ExecuteERef(group_id, *i, ephemereal_headers);
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
  vector<LookupCache> key_lookups;  // we want this outside of the function
                                    // to minimize allocations.
  Instructions instrs;              // As above, this is kept outside
                                    // to help minimize allocations.
  void OutputCompleteHeaderFrame(OutputStream* os,
                                 StreamId stream_id,
                                 GroupId group_id,
                                 const HeaderFrame& headers,
                                 bool this_ends_the_frame) {
    storage.PinLRUEnd();
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
    vector<ToggleOp>::iterator first_toggle_on;
    vector<ToggleOp>::iterator first_toggle_off;
    vector<CloneOp>::iterator first_clone;
    vector<KVStoOp>::iterator first_kvsto;

    if (header_groups.find(group_id) == header_groups.end()) {
      header_groups[group_id] = HeaderGroup();
    }
    HeaderGroup& header_group = header_groups[group_id];
    list<string> cookie_strs;  // Yes, this must exist for the func scope.



    // First we construct (and possibly emit) toggles. That is guaranteed
    // to be safe because it will remove no entries.
    //
    //
    // We then emit all the indices for all the clone entries (but not the val
    // yet). This is also guaranteed to be safe because it removes no entries.
    // ( the mechanism for doing this is actually just ensuring we don't remove
    // any of the keys that we may otherwise be using in the encoder.  In the
    // decoder, the mechanism would be to step through all of the clone
    // operations twice-- once to increment a refcnt to ensure the entries are
    // not removed, and then another time to execute adding the values, at
    // which point entries may be removed.


    // Since we'll be going eliminating entries as we construct operations,
    // we'll need to go through and ensure that the key for each of the things
    // which are referenced by this set of headers is not eliminated.
    // We do this by incrementing a refcnt for every key that exists which
    // matches a key in the current HeaderFrame.
    for (HeaderFrame::const_iterator hf_i = headers.begin();
         hf_i != headers.end();
         ++hf_i) {
      const string& key = hf_i->key;
      LookupCache lc;
      storage.FindKey(&lc, key);
      key_lookups.push_back(lc);
      if (lc.HasKey()) {
        lc.k_i->second.IncRefcnt();
        assert(lc.k_i->second.refcnt == 1);
      }
    }

    vector<LookupCache>::iterator key_lu_it = key_lookups.begin();
    for (HeaderFrame::const_iterator hf_i = headers.begin();
         hf_i != headers.end();
         ++hf_i, ++key_lu_it) {
      const string& key = hf_i->key;
      const string& val = hf_i->val;
      LookupCache lc = *key_lu_it;
      //storage.FindOrAddKey(&lc, key);

       // this is buggy.
      size_t crumb_end;

      if (key == "cookie" &&
          (crumb_end = val.find_first_of(';')) != string::npos) {
        size_t crumb_begin = 0;
        LookupCache clc;
        clc.CopyKey(lc);

        while (crumb_begin < val.size()) {
          cookie_strs.push_back(val.substr(crumb_begin,
                                           crumb_end - crumb_begin));
          const string& crumb = cookie_strs.back();
          //cout << "cookie key: " << key << " val : " << crumb << "\n";
          ProcessKV(clc, key, crumb, &header_group, group_id, &instrs);
          if (crumb_end == string::npos) break;
          crumb_begin = val.find_first_not_of(' ', crumb_end + 1);
          crumb_end = val.find_first_of(';', crumb_begin);
        }
      } else {
        ProcessKV(lc, key, val, &header_group, group_id, &instrs);
      }
    }

    // Here we discover any elements in the header_group which are referenced
    // but don't exist in the header frame presented to this function.
    // These need to be toggled off.
    // Note that this is done after doing deletions due to exceeding the max
    // buffer size, since some of the deletions may have already cleared some of
    // the elements we must be turning off.
    DiscoverTurnOffs(&(instrs.toggle_offs), stream_id);

    first_toggle_on = instrs.toggle_ons.begin();
    first_toggle_off = instrs.toggle_offs.begin();
    first_clone = instrs.clones.begin();
    first_kvsto = instrs.kvstos.begin();

    ExecuteInstructionsExceptERefs(group_id, instrs);

    for (vector<LookupCache>::iterator key_lu_it = key_lookups.begin();
         key_lu_it != key_lookups.end();
         ++key_lu_it) {
      // As we're proceeding through, we reduce the refcnt by one
      // if we had incremented it before.
      if (key_lu_it->HasKey()) {
        assert(key_lu_it->k_i->second.refcnt == 1);
        key_lu_it->k_i->second.DecRefcnt();
      }
    }

    //serializer->SerializeInstructions(os, &instrs, headers_end_flag);
    FrameDone();
#ifdef DEBUG
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
#endif

    storage.UnPinLRUEnd();
    key_lookups.clear();
    instrs.clear();
  }

  void PreProcessForSerialization(Instructions* instrs) {
    return;
    // in particular, we need to manage the toggles.
    vector<LRUIdx> all_toggles;
    for (unsigned int i = 0; i < instrs->toggle_ons.size(); ++i) {
      all_toggles.push_back(instrs->toggle_ons[i].idx());
    }
    for (unsigned int i = 0; i < instrs->toggle_offs.size(); ++i) {
      all_toggles.push_back(instrs->toggle_offs[i].idx());
    }
    sort(all_toggles.begin(), all_toggles.end());
    for (unsigned int i = 1; i < all_toggles.size(); ++i) {
      if ((all_toggles[i] - all_toggles[i-1]) == 1) {
        // these belong in a range.
      }
    }
    vector<pair<LRUIdx, LRUIdx> > toggle_ranges;
    vector<LRUIdx> toggles;
  }

  void TouchHeaderGroupEntry(HeaderGroup::iterator i) {
    i->second = frame_count;
    DEBUG_PRINT(cout << "Touching: " << i->first->lru_idx;)
    MoveToHeadOfLRU(i->first);
    DEBUG_PRINT(cout << " new idx: " << i->first->lru_idx;)
    DEBUG_PRINT(cout << "\n";)
  }

  bool HeaderGroupEntryUpToDate(HeaderGroup::iterator i) const {
    return i->second == frame_count;
  }

  void FrameDone() {
    ++frame_count;
  }

  void DiscoverTurnOffs(vector<ToggleOp>* toggle_offs,
                        GroupId group_id) {
    HeaderGroup& header_group = header_groups[group_id];
    for (HeaderGroup::iterator i = header_group.begin();
         i != header_group.end();++i) {
      if (!HeaderGroupEntryUpToDate(i)) {
        toggle_offs->push_back(ToggleOp(i->first));
      }
    }
  }

  void ExecuteClones(GroupId group_id, const Instructions::Clones& clones) {
    typedef Instructions::Clones Clones;
    for (Clones::const_iterator i = clones.begin(); i != clones.end(); ++i) {
      assert(i->lc.HasKey());
      i->lc.k_i->second.IncRefcnt();
    }
    for (Clones::const_iterator i = clones.begin(); i != clones.end(); ++i) {
      ExecuteClone(group_id, *i);
      i->lc.k_i->second.DecRefcnt();
    }
  }

  void ExecuteClone(GroupId group_id, const CloneOp& clone) {
    const string& val = clone.val();
#ifdef DEBUG
    const string& key = clone.key();
    cout << "Executing Clone: \"" << key << "\" \"" << val << "\"\n";
#endif
    AddLine(group_id, clone.lc, val);
  }


  bool ToggleHeaderGroupEntry(GroupId group_id,
                              ValEntry* entry) {
    assert(group_id > 0);
    HeaderGroups::iterator hgs_i = header_groups.find(group_id);
    if (hgs_i == header_groups.end()) {
      DEBUG_PRINT(cout << "on (creating HG " << group_id << ")";)
      hgs_i = header_groups.insert(make_pair(group_id, HeaderGroup())).first;
      hgs_i->second.insert(make_pair(entry, frame_count));
      return false;
    }

    HeaderGroup& header_group = hgs_i->second;
    HeaderGroup::iterator hg_i = header_group.find(entry);
    bool was_visible = (hg_i != header_group.end());
    if (!was_visible) {
      DEBUG_PRINT(cout << "on";)
      header_group.insert(make_pair(entry, frame_count));
    } else {
      DEBUG_PRINT(cout << "off";)
      header_group.erase(hg_i);
    }
    return was_visible;
  }

  // return value indicates whether it was visibile before this call.
  bool SetHeaderGroupEntry(GroupId group_id,
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

  void AddLine(GroupId group_id, const LookupCache& lc, const string& val) {
    LookupCache tlc = lc;
    ValEntry* entry = storage.InsertVal(&tlc, val);

    if (group_id > 0) {
      storage.AddToHeadOfLRU(entry);
      // add the entry to that group.
      SetHeaderGroupEntry(group_id, entry, true);
    }
  }

  void ExecuteKVSto(GroupId group_id, const KVStoOp& kvsto) {
    LookupCache lc;
    storage.FindOrAddKey(&lc, kvsto.key());

    AddLine(group_id, lc, kvsto.val());
    DEBUG_PRINT(
        cout << "Executing KVSto: \"" << kvsto.key()
             << "\" \"" << kvsto.val() << "\"\n";
             )
  }

  void ExecuteERef(GroupId group_id, const ERefOp& eref,
                    HeaderFrame* ephemereal_headers) {
    ephemereal_headers->push_back(KVPair(eref.key(), eref.val()));
  }


  void ExecuteToggle(GroupId group_id, const ToggleOp& to) {
    ValEntry* entry = to.entry;
    DEBUG_PRINT(cout << "Executing Toggle: "
                << "(" << entry->seq_num << ") "
                << entry->lru_idx << " ";)
    if (!ToggleHeaderGroupEntry(group_id, entry)) {
      MoveToHeadOfLRU(entry);
      DEBUG_PRINT(cout << " new id: " << entry->lru_idx;)
    }
    DEBUG_PRINT(cout << " key: " << entry->key();)
    DEBUG_PRINT(cout << " val: " << entry->val();)
    DEBUG_PRINT(cout << "\n";)
  }

  void MoveToHeadOfLRU(ValEntry* entry) {
    storage.MoveToHeadOfLRU(entry);
  }

  size_t CurrentStateSize() const {
    return storage.state_size;
  }
};

////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////


typedef SPDY4HeadersCodecImpl::Instructions Instructions;
// In this serialization implementation, all data is serialized ignoring
// byte offsets, inline, with mention of the opcode for each operation.
// As noted in the 'Other serialization...' section below this class,
// there are other (likely better) ways of doing this.
class InlineSerialization : SPDY4HeadersCodecImpl::SerializationInterface {
  public:
    // Order of serialization:
    //   1) toggles
    //   2) clone
    //   3) kvsto
    // We first want to serialize the toggles-on.
    // Then we want to serialize the toggles-off.
    // Then, we do either clones/mutates or KVStos or  (doesn't matter).
    //
    // This ordering will reduce:
    //   1) the amount of data transmitted on the wire since
    //   we will be able to reference state without having to
    //   recreate it more often
    //   2) the amount of state used at any portion of time
    //   while executing the instructions.
  typedef vector<LRUIdx> OutputToggles;
  typedef vector<pair<LRUIdx, LRUIdx> > OutputToggleRanges;


  void PreProcessToggles(Instructions* instrs,
                         OutputToggles* ot,
                         OutputToggleRanges* otr) {
    sort(instrs->toggle_ons.begin(), instrs->toggle_ons.begin());
    sort(instrs->toggle_offs.begin(), instrs->toggle_offs.begin());

    Instructions::Toggles::iterator ons_it = instrs->toggle_ons.begin();
    Instructions::Toggles::iterator offs_it = instrs->toggle_offs.begin();

    while (true) {
      LRUIdx idx = 0;
      if (ons_it != instrs->toggle_ons.end()) {
        if (offs_it != instrs->toggle_offs.end()) {
          if (ons_it->idx() < offs_it->idx()) {
            idx = ons_it->idx();
            ++ons_it;
          } else {
            idx = offs_it->idx();
            ++offs_it;
          }
        } else {
          idx = ons_it->idx();
          ++ons_it;
        }
      } else if (offs_it != instrs->toggle_offs.end()){
        idx = offs_it->idx();
        ++offs_it;
      } else {
        break;
      }

      if (!ot->empty()) {
        if ((idx - ot->back()) == 1) {
          ot->pop_back();
          otr->push_back(make_pair(ot->back(), idx));
          continue;
        }
      }
      if (!otr->empty()) {
        if ((idx - otr->back().second) == 1) {
          otr->back().second = idx;
        }
      }
    }
  }

  static void WriteLRUIdx(OutputStream* os, LRUIdx idx) {
    os->WriteUint16(idx);
  }

  static void WriteString(OutputStream* os, const string& str) {
    os->WriteBytes(str.begin(), str.end());
    os->WriteUint8(0);
  }

  static void WriteOpcode(OutputStream* os, uint8_t opcode) {
    os->WriteUint8(opcode);
  }

  struct LRUIdxWriter {
    void Write(OutputStream* os, const LRUIdx& idx) {
      WriteLRUIdx(os, idx);
    }
  };

  struct LRUIdxPairWriter {
    void Write(OutputStream* os, const pair<LRUIdx, LRUIdx>& idx_pair) {
      WriteLRUIdx(os, idx_pair.first);
      WriteLRUIdx(os, idx_pair.second);
    }
  };

  struct CloneWriter {
    void Write(OutputStream* os, const SPDY4HeadersCodecImpl::CloneOp& clone) {
      WriteLRUIdx(os, clone.idx());
      WriteString(os, clone.val());
    }
  };

  struct KVStoWriter {
    void Write(OutputStream* os, const SPDY4HeadersCodecImpl::KVStoOp& kvsto) {
      WriteString(os, kvsto.key());
      WriteString(os, kvsto.val());
    }
  };

  struct ERefWriter {
    void Write(OutputStream* os, const SPDY4HeadersCodecImpl::ERefOp& eref) {
      WriteString(os, eref.key());
      WriteString(os, eref.val());
    }
  };

  template <typename T, typename Opwriter>
  void OutputOps(OutputStream* os, uint8_t opcode,
                 const vector<T>& opvec, Opwriter opwriter) {
    if (!opvec.empty()) {
      unsigned int ops_idx = 0;
      while (opvec.size() > ops_idx) {
        unsigned int ops_to_go = opvec.size() - ops_idx;
        unsigned int iteration_end = min(ops_to_go, 255u) + ops_idx;
        os->WriteUint8(opcode);
        if (ops_to_go <= 255) {
          os->WriteUint8((uint8_t)ops_to_go);
        } else {
          os->WriteUint8((uint8_t)255);
        }
        for (; ops_idx < iteration_end; ++ops_idx) {
          opwriter.Write(os, opvec[ops_idx]);
        }
      }
    }
  }

  size_t SerializeInstructions(OutputStream* os,
                               Instructions* instrs,
                               StreamId stream_id,
                               bool this_ends_the_frame) {
    OutputStream los;
    // for each instruction
    // serialize opcode
    // serialize arguments
    //uint32_t start_of_frame_pos = os->StreamPos();
    OutputToggles output_toggles;
    OutputToggleRanges output_toggle_ranges;
    PreProcessToggles(instrs, &output_toggles, &output_toggle_ranges);

    WriteControlFrameBoilerplate(os, 0, this_ends_the_frame, stream_id, 0x8U);
    while (true) {
      //uint32_t bytes_used = os->StreamPos() - start_of_frame_pos;

      OutputOps(os, TOGGLE, output_toggles, LRUIdxWriter());
      OutputOps(os, CLONE , instrs->clones,  CloneWriter());
      OutputOps(os, KVSTO , instrs->kvstos,  KVStoWriter());
      OutputOps(os, EREF  , instrs->erefs ,   ERefWriter());

      //FixupFrameBoilerplate(os, start_of_frame_pos, bytes_used, new_flags_val);
    }
    return 0;
  };

  void FixupFrameBoilerplate(OutputStream* os,
                             uint32_t start_of_frame_pos,
                             uint32_t frame_length,
                             uint32_t frame_flags) {
    uint32_t frame_size_field_pos = start_of_frame_pos;
    uint32_t flags_field_pos = (start_of_frame_pos +
                                kFlagFieldOffsetFromFrameStart);
    os->OverwriteUint16(frame_size_field_pos,
                        static_cast<uint16_t>(frame_length));
    os->OverwriteUint8(flags_field_pos, frame_flags);
  }

  void WriteControlFrameBoilerplate(OutputStream* os,
                                    uint32_t frame_len,
                                    uint8_t flags,
                                    StreamId stream_id,
                                    uint8_t type) {
    os->WriteUint16(frame_len);
    os->WriteUint8(flags);
    WriteControlFrameStreamId(os, stream_id);
    os->WriteUint8(type);
  }

  void WriteControlFrameStreamId(OutputStream* os, StreamId stream_id) {
    if (stream_id & 0x8000U) {
      abort(); // can't have that top-order bit set....
    }
    os->WriteUint32(0x8000U | stream_id);
  }

};

// Other serializations/variations/ideas:
//  1) fixed-width fields are all serialized together.
//     variable-width fields are also serialized together (and thus separately
//     from fixed-width fields). This implies that something exist which
//     demarks the end of the fixed-width section, whether that be a sentinel
//     or a size-of-bytes, or opcount.
//  2) No mention of opcodes is made, rather, it is implicit that all operations
//     before a sentry are of type A, after that sentry type B, after the
//     next sentry type C, etc.
//  3) As in #2, but instead a count of fields, operations, or byte-length is
//     used for demarcation.
//  4) The opcode for the sequence of operations is mentioned
//     explicitly at the beginning of the sequence exactly once. Either
//     sentinel based demarcation or count-based demarcation is used to
//     indicate the end of each section
//  5) all huffman-coded strings are padded to the next byte-boundary.
//     This is potentially particularly interesting to proxies, as they'll
//     potentially not have to do any bit-twiddling in the deserialization.
//  5) huffman-encoded strings use an EOF symbol is used to indicate the end of
//     the string
//  6) a bit-width or token-count is used to indicate the end of the string.
//  7) var-int length fields instead of fixed-width length fields
//  8) huffman-coding over the opcodes and fixed-width values.
// this list is not exhaustive, but I'm exhausted, so I'll stop here. This should
// be plenty to play around with.


////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////


SPDY4HeadersCodec::SPDY4HeadersCodec(const FreqTable& sft) {
  impl = new SPDY4HeadersCodecImpl(sft);
}

size_t SPDY4HeadersCodec::CurrentStateSize() const {
  return impl->CurrentStateSize();
}

void SPDY4HeadersCodec::OutputCompleteHeaderFrame(OutputStream* os,
                                              StreamId stream_id,
                                              GroupId group_id,
                                              const HeaderFrame& headers,
                                              bool this_ends_the_frame) {
  impl->OutputCompleteHeaderFrame(os, stream_id, group_id,
                                   headers, this_ends_the_frame);
}

