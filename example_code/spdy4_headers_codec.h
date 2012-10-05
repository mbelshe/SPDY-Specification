#include <utility>
#include <set>
#include <list>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <functional>
#include <string>

#include "header_freq_tables.h"
#include "huffman.h"
#include "trivial_http_parse.h"

using std::string;
using std::vector;
using std::set;
using std::unordered_set;
using std::unordered_multiset;
using std::unordered_map;
using std::unordered_multimap;
using std::hash;
using std::list;


typedef uint16_t LRUIdx;

// Map of LRUIdx to generation number.
typedef map<LRUIdx, uint32_t> HeaderGroup;

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
  enum {CLONE, KVSTO, TOGGLE, TOGGLE_RANGE};
 private:
  struct KVEntry;

  struct KVEntryKHash {
    size_t operator()(const KVEntry* const kve) {
      return std::hash<const string>()(kve->kv.key);
    }
  };

  struct KVEntryKCmp {
    bool operator()(const KVEntry* a, const KVEntry* b) {
      return LessThan(a->kv.key, b->kv.key);
    }
    bool operator()(const KVPair& a, const KVEntry* b) {
      return LessThan(a.key, b->kv.key);
    }
    bool operator()(const KVEntry* a, const KVPair& b) {
      return LessThan(a->kv.key, b.key);
    }
    bool operator()(const string* a, const string* b) {
      return LessThan(*a, *b);
    }
    bool LessThan(const string& a, const string& b) {
      return a < b;
    }
  };

  struct KVEntryKVHash {
    size_t operator()(const KVEntry* kve) {
      return (std::hash<string>()(kve->kv.key) +
              std::hash<string>()(kve->kv.val));
    }
  };

  struct KVPPair {
    const string& key;
    const string& val;
    KVPPair(const string& key, const string& val) : key(key), val(val) {}
    explicit KVPPair(const KVPair& kv)  : key(kv.key), val(kv.val) {}

    friend ostream& operator<<(ostream& os, const KVPPair& kp) {
      os << "key: \"" << kp.key << "\" val: \"" << kp.val << "\"";
      return os;
    }
  };

  struct KVEntryKVCmp {
    bool operator()(const KVPPair& a, const KVPPair& b) {
      int k_cmp = a.key.compare(b.key);
      if (k_cmp != 0) { // a < b
        return k_cmp < 0;
      }
      k_cmp = a.val.compare(b.val);
      return k_cmp < 0;
    }
  };

  // The KLookup set maintains the most recent use of a key.
  // Each time something is moved to the front of the LRU,
  // we ensure that the KVEntry* here points to that element
  // in the LRU, overriding any previous assignment.
  //typedef unordered_map<string, KVEntry*, KVEntryKHash, KVEntryKCmp> KLookup;

  typedef map<KVPPair, KVEntry*, KVEntryKVCmp> KVLookup;
  typedef map<string*, KVEntry*, KVEntryKCmp> KLookup;

  typedef size_t KVHashVal;

  struct KVEntry {
    typedef list<KVEntry> KVEntryList;

    // The key and val.
    KVPair kv;

    // Pointer to own place in the list.
    KVEntryList::iterator lru_i;

    // iterator to the kv entry that points to this KVEntry.
    KVLookup::iterator kvlookup_it;

    //the hash.
    KVHashVal kvhash;

    LRUIdx lru_idx;
    bool will_delete;

    LRUIdx GetLRUIdx() const {
      return lru_idx;
    }

    KVEntry() : kvhash(0), lru_idx(0), will_delete(0) {}
    friend ostream& operator<<(ostream& os, const KVEntry& kve) {
      os << "kv(" << kve.kv << ") "
        // << "lru_i(" << kve.lru_i << ") "
        // << "kvlookup_it(" << "kve.kvlookup_it << ") "
        << "kvhash(" << kve.kvhash << ") "
        << "lru_idx(" << kve.lru_idx << ") "
        << "will_delete(" << kve.will_delete << ")";
      return os;
    }
  };

  typedef KVEntry::KVEntryList KVEntryList;

 private:
  Huffman huff;
  uint32_t max_total_header_storage_size;
  uint32_t max_header_groups;
  uint32_t max_table_entries;
  // ideally, you'd use a ring-buffer to store the text data.
  uint32_t frame_count;
  uint32_t current_state_size;
  LRUIdx last_used_lru_idx;

  typedef list<KVEntry*> LRUList;
  LRUList lru;  // refers to the KV_pairs entries.
  typedef map<uint32_t,HeaderGroup> HeaderGroups;
  KVLookup kv_lookup;
  KLookup k_lookup;
  HeaderGroups header_groups;
  typedef map<LRUIdx, KVEntry*> LRUIdxToKveMap;
  LRUIdxToKveMap lru_idx_to_kve_map;

  struct KVStoOp {
    string key;
    string val;
   public:
    KVStoOp(const string& key, const string& val) : key(key), val(val) { }
    KVStoOp() {}
    size_t DeltaSize() const{
      return key.size() + val.size();
    }
  };

  struct CloneOp {
    KVEntry* kv_entry;
    string val;
   public:
    CloneOp(KVEntry* kv, const string& val) : kv_entry(kv), val(val) {}
    CloneOp() : kv_entry(0) {}
    size_t DeltaSize() const{
      return kv_entry->kv.key.size() + val.size();
    }
  };

 public:
  SPDY4HeadersCodec(const FreqTable& sft);

  LRUIdx GetNextLruIdx();

  void OutputCompleteHeaderFrame(OutputStream* os,
                                 uint32_t stream_id,
                                 uint32_t group_id,
                                 const HeaderFrame& headers,
                                 bool this_ends_the_frame);

  KVEntry* LookupKeyValue(const KVPair& kv);

  KVEntry* LookupKey(const KVPair& kv);

  void TouchHeaderGroupEntry(HeaderGroup::iterator i);

  bool HeaderGroupEntryUpToDate(HeaderGroup::iterator i) const ;
  void FrameDone();

  void DiscoverTurnOffs(vector<LRUIdx>* turn_offs,
                        uint32_t group_id);

  void WriteControlFrameBoilerplate(OutputStream* os,
                                    uint32_t frame_len,
                                    uint8_t flags,
                                    uint32_t stream_id,
                                    uint8_t type);

  void WriteControlFrameStreamId(OutputStream* os, uint32_t stream_id);
  uint32_t WriteClone(OutputStream* os, const CloneOp& clone);
  void ExecuteClone(uint32_t group_id, const CloneOp& clone);
  uint32_t WriteKVSto(OutputStream* os, const KVStoOp& kvsto);

  bool ToggleHeaderGroupEntry(uint32_t group_id, LRUIdx lru_idx);
  bool SetHeaderGroupEntry(uint32_t group_id, LRUIdx lru_idx, bool visible);
  void AddLine(uint32_t group_id, const string& key, const string& val);

  void ExecuteKVSto(uint32_t group_id, const KVStoOp& kvsto);
  uint32_t WriteToggle(OutputStream* os, LRUIdx lru_idx);
  void ExecuteToggle(uint32_t group_id, LRUIdx lru_idx);
  uint32_t WriteToggleRange(OutputStream* os,
                            LRUIdx lru_idx_start, LRUIdx lru_idx_end);
  void ExecuteToggleRange(uint32_t group_id,
                          LRUIdx lru_idx_start, LRUIdx lru_idx_end);

  void WriteOpcode(OutputStream* os, int opcode);
  void WriteLRUIdx(OutputStream* os, LRUIdx idx);
  void WriteString(OutputStream* os, const string& str);

  void ProcessInput(OutputStream* os) {}
  void ReconsituteFrame(HeaderFrame* hf) {}

  void RemoveAndCleanup(KVEntry* kv) {}
  bool SerializeAllInstructions(OutputStream* os,
                                vector<LRUIdx>::iterator* first_turn_on,
                                const vector<LRUIdx>& turn_ons,
                                vector<LRUIdx>::iterator* first_turn_off,
                                const vector<LRUIdx>& turn_offs,
                                vector<CloneOp>::iterator* first_clone,
                                const vector<CloneOp>& clones,
                                vector<KVStoOp>::iterator* first_kvsto,
                                const vector<KVStoOp>& kvstos,
                                uint8_t headers_end_flag,
                                uint32_t stream_id);

};



