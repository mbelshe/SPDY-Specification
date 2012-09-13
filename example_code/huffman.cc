#include <stdlib.h>
#include <assert.h>
#include <stdint.h>
#include <float.h>

#include <deque>
#include <utility>
#include <vector>
#include <ostream>
#include <iostream>
#include <algorithm>
#include "pretty_print_tree.cc"
#include "bit_bucket.cc"
#include <array>
#include <limits>
#include <map>
#include <iomanip>

using std::deque;
using std::pair;
using std::vector;
using std::ostream;
using std::cout;
using std::cerr;
using std::hex;
using std::dec;
using std::sort;
using std::array;
using std::ios;
using std::map;
using std::make_pair;
using std::lower_bound;
using std::upper_bound;
using std::setw;

void OutputCharToOstream(ostream& os, unsigned short c) {
  if (c > 256 + 1)
    abort();
  if (c >= 256) {
    os << c;
  } else {
    os << " '";
    if (c < 128 && (isgraph(c) || c == ' ')) {
      os << (char)c;
    } else {
      switch (c) {
        case '\t':
          os << "\\t";
          break;
        case '\n':
          os << "\\n";
          break;
        case '\r':
          os << "\\r";
          break;
        case '\0':
          os << "\\0";
          break;
        default:
          if (c >= 16) {
            os << "\\x" << hex << c << dec;
          } else {
            os << "\\x0" << hex << c << dec;
          }
          break;
      }
    }
    os << "'";
  }
}

string ReadableUShort(uint16_t c) {
  stringstream s;
  OutputCharToOstream(s, c);
  return s.str();
}

class Huffman {
 private:
  struct Node {
    double weight;
    Node* children[2];
    uint32_t depth;
    unsigned short c;
    bool terminal;

    explicit Node() : weight(0), depth(0), c(0), terminal(false) {
      children[0] = children[1] = 0;
    }
    explicit Node(unsigned short c, double weight) :
        weight(weight), depth(0), c(c), terminal(true) {
      children[0] = children[1] = 0;
    }
    friend ostream& operator<<(ostream& os, const Node& leaf) {
      os.setf(ios::scientific,ios::floatfield);
      os << leaf.weight;
      if (leaf.terminal) {
        OutputCharToOstream(os, leaf.c);
      }
      return os;
    }
  };

  struct VecAndLen {
    vector<char> vec;
    int len;
    uint32_t val;
    VecAndLen() : len(0), val(0) {}
    explicit VecAndLen(int len) : len(len), val(0) {}
  };

  typedef array<VecAndLen, 256+1> CodeTable;

  void GetNextNode(Node* current_leaf, int child_idx,
                   deque<Node*> *leaves, deque<Node*> *internals) {
    assert (current_leaf->children[child_idx] == 0);
    if (internals->size() && leaves->size()) {
      if (leaves->front()->weight <= internals->front()->weight) {
        current_leaf->children[child_idx] = leaves->front();
        current_leaf->depth = max(current_leaf->depth,
                                  leaves->front()->depth + 1);
        leaves->pop_front();
      } else {
        current_leaf->children[child_idx] = internals->front();
        current_leaf->depth = max(current_leaf->depth,
                                  internals->front()->depth + 1);
        internals->pop_front();
      }
    } else if (internals->size()) {
      current_leaf->children[child_idx] = internals->front();
      current_leaf->depth = max(current_leaf->depth,
                                internals->front()->depth + 1);
      internals->pop_front();
    } else {
      assert(leaves->size() != 0);
      current_leaf->children[child_idx] = leaves->front();
      current_leaf->depth = max(current_leaf->depth,
                                leaves->front()->depth + 1);
      leaves->pop_front();
    }
    current_leaf->weight += current_leaf->children[child_idx]->weight;
  }

  static bool NodePtrComp(const Node* a,const Node* b) {
    if (a->weight != b->weight) {
      return a->weight < b->weight;
    } else if (a->terminal != b->terminal) {
      return b->terminal;
    } else if (a->terminal) {
      return a->c < b->c;
    }
    return 0;
  }

  void DeleteCodeTree() {
    if (!code_tree)
      return;
    deque<Node*> nodes;
    nodes.push_back(code_tree);
    while (!nodes.empty()) {
      Node* node = nodes.front();
      nodes.pop_front();
      for (int i = 0; i < 2; ++i) {
        if (node->children[i]) {
          nodes.push_back(node->children[i]);
        }
      }
      delete node;
    }
    code_tree = 0;
  }

  // returns max depth
  int BuildCodeTree(const vector<pair<uint16_t, uint32_t> >& freq_table,
                     uint32_t divisor=1) {
    cout << "Divisor: " << divisor << "\n";
    deque<Node*> leaves;
    deque<Node*> internals;
    if (freq_table.size() <= 2) {
      // that would be stupid, to say the least.
      abort();
    }
    for (int i = 0; i < freq_table.size(); ++i) {
      double weight = freq_table[i].second / divisor;
      uint16_t sym = freq_table[i].first;
      assert (sym == i);
      if (weight == 0) {
        weight = DBL_EPSILON;
      }
      leaves.push_back(new Node(freq_table[i].first, weight));
    }
    sort(leaves.begin(), leaves.end(), NodePtrComp);

    Node* current_leaf = new Node();
    int total_size = leaves.size();
    while (total_size >= 2) {
      GetNextNode(current_leaf, 0, &leaves, &internals);
      --total_size;
      if (total_size >= 1) {
        GetNextNode(current_leaf, 1, &leaves, &internals);
        --total_size;
      }
      internals.push_back(current_leaf);
      ++total_size;
      current_leaf = new Node();
    }
    // the last 'current_leaf' is extraneous. Delete it.
    delete current_leaf;
    assert(internals.size() == 1);
    assert(leaves.size() == 0);
    code_tree = internals.front();
    //cout << "max tree depth: " << code_tree->depth << "\n";
    return code_tree->depth;
  }

  void BuildCodeTableHelper(Node* current, deque<bool>* state) {
    if (current->terminal) {
      BitBucket bb;
      for (int i = 0; i < state->size(); ++i) {
        bb.StoreBit((*state)[i]);
      }
      unsigned short idx = current->c;
      code_table[idx] = VecAndLen(state->size());
      bb.GetBits(&(code_table[idx].vec), state->size());
    }
    state->push_back(false);
    if (current->children[0]) {
      BuildCodeTableHelper(current->children[0], state);
    }
    state->back() = true;
    if (current->children[1]) {
      BuildCodeTableHelper(current->children[1], state);
    }
    state->pop_back();
  }
  typedef map<int, vector<unsigned short> > DepthToSym;

  void DiscoverDepthAndStoreIt(DepthToSym* depth_to_sym) {
    deque<pair<Node*, int> > stack;
    stack.push_back(make_pair(code_tree, 0));
    while (!stack.empty()) {
      Node* current = stack.back().first;
      int depth = stack.back().second + 1;
      if (current->terminal) {
        DepthToSym::iterator it = depth_to_sym->find(depth - 1);
        vector<unsigned short>* depth_set = 0;
        if (it == depth_to_sym->end()) {
          it = depth_to_sym->insert(make_pair(depth - 1,
                                              vector<unsigned short>())).first;
        }
        it->second.push_back(current->c);
      }
      stack.pop_back();
      if (current->children[0])
        stack.push_back(make_pair(current->children[0], depth));
      if (current->children[1])
        stack.push_back(make_pair(current->children[1], depth));
    }
  }

  uint32_t ComputeNextCode(uint32_t prev_code,
                           int current_code_length,
                           int prev_code_length) {
    uint32_t next_code = (prev_code + 1);
    next_code <<= (current_code_length - prev_code_length);
    cout << "code: " 
         << FormatAsBits(next_code << (32 - current_code_length), current_code_length)
         << "\n";
    return next_code;
  }

  void Uint32ToCharArray(vector<char>* vec, uint32_t val, int bit_len) {
    uint32_t nval = val << (32 - bit_len);
    for (int rshift = 24; rshift >= 0 && bit_len > 0; rshift -= 8, bit_len -=8) {
      unsigned char c = nval >> rshift;
      vec->push_back(nval >> rshift);
    }
  }

  void AltBuildCodeTable() {
    DepthToSym depth_to_sym;
    DiscoverDepthAndStoreIt(&depth_to_sym);
    uint32_t code = 0xFFFFFFFF; // adding 1 will make this 0.

    int prev_code_length = 0;
    for (DepthToSym::iterator i = depth_to_sym.begin();
         i != depth_to_sym.end();
         ++i) {
      int current_code_length = i->first;
      sort(i->second.begin(), i->second.end());
      const vector<unsigned short> &syms = i->second;
      for (int j = 0; j < syms.size(); ++j) {
        unsigned short c = syms[j];
        code = ComputeNextCode(code, current_code_length, prev_code_length);
        prev_code_length = current_code_length;
        code_table[c] = VecAndLen(current_code_length);
        code_table[c].val = code << (32 - current_code_length);
        Uint32ToCharArray(&(code_table[c].vec), code, current_code_length);
      }
    }
  }

  struct BitPatternCmp {
    int bit_len;

    explicit BitPatternCmp(int bit_len) : bit_len(bit_len) {}

    bool operator()(const VecAndLen& a, uint32_t b) const{
      cout << "a.val(" << a.val << ")";
      if (a.val < b) cout << " < ";
      else cout << " >= ";
      cout << "b(" << b <<")\n";
      return a.val < b;
    }
    bool operator()(uint32_t a, const VecAndLen& b) const{
      cout << "a(" << a << ")";
      if (a < b.val) cout << " < ";
      else cout << " >= ";
      cout << "b.val(" << b.val <<")\n";
      return a < b.val;
    }
  };

  bool Equivalent(const vector<pair<uint32_t, int> >& sorted_by_code,
                  uint32_t idx_1,
                  uint32_t idx_2,
                  uint32_t msb,
                  uint32_t bw) {
      uint32_t cur_code = sorted_by_code[idx_1].first;
      uint32_t nxt_code = sorted_by_code[idx_2].first;
      uint32_t cur_idx = (cur_code << msb) >> (32 - bw);
      uint32_t nxt_idx = (nxt_code << msb) >> (32 - bw);
      return cur_idx == nxt_idx;
  }

  struct DecodeEntry {
    uint16_t sym;
    uint8_t next_table;
    bool valid;
    DecodeEntry() : sym(0), next_table(0), valid(0) {}

    DecodeEntry(uint16_t sym, uint8_t next_table) :
        sym(sym), next_table(next_table), valid(1) {};

    friend ostream& operator<<(ostream& os, const DecodeEntry& de) {
      if (de.valid) {
        os << "[DE " << static_cast<uint32_t>(de.next_table)
          << " " << ReadableUShort(de.sym) << "]";
      } else {
        os << "[DE INVALID]";
      }
      return os;
    }
  };

  struct BranchEntry {
    uint32_t base_idx;
    uint32_t ref;
    uint32_t mask;
    uint8_t shift;
    BranchEntry() : base_idx(0), ref(0), mask(0), shift(0) {}
    BranchEntry(uint32_t base_idx, uint32_t ref, uint8_t msb, uint8_t bw)
      : base_idx(base_idx), ref(ref) {
      mask = (0XFFFFFFFFU << (32 - bw)) >> msb;
      shift = 32 - min(msb+bw, 32);
    }
    friend ostream& operator<<(ostream& os, const BranchEntry& be) {
      os << "[BE base_idx " << be.base_idx
         << " ref: " << be.ref
         << " mask: " << FormatAsBits(be.mask, 32)
         << " shift: " << static_cast<uint32_t>(be.shift)
         << "]";
      return os;
    }
  };

  typedef vector<DecodeEntry> DecodeTable;
  typedef vector<BranchEntry> Branches;

  void AltBuildDecodeHelper(const vector<pair<uint32_t, int> >& sorted_by_code,
                            DecodeTable* decode_table,
                            Branches* branches,
                            uint32_t begin,
                            uint32_t end,
                            uint32_t msb,
                            uint32_t bw) {
    uint32_t branch_idx = branches->size();
    branches->push_back(BranchEntry(decode_table->size(),
                                    branch_idx,
                                    msb,
                                    bw));
    uint32_t decode_table_idx = decode_table->size();
    decode_table->resize(decode_table->size() + (0x1U << bw));
    uint32_t run_start = begin;
    uint32_t run_end = begin;
    while (run_end < end) {
      while (Equivalent(sorted_by_code, run_start, run_end, msb, bw)) {
        ++run_end;
        if (run_end == end) {
          break;
        }
      }
      // run_start != run_end.
      // implies, that run_start -> (run_end - 1) is equivalent.
      uint32_t dist = run_end - run_start;
      uint32_t cur_code = sorted_by_code[run_start].first;
      uint32_t cur_idx = (cur_code << msb) >> (32 - bw);
      for (int i = 0; i < msb; ++i) cout << " ";
      if (dist == 1) {
        uint16_t sym = sorted_by_code[run_start].second;
        cout << "Terminal: " << setw(6) << cur_idx
              << " " << setw(6) << (cur_idx + decode_table_idx)
              << " " << ReadableUShort(sym);
        uint32_t code_len = code_table[sorted_by_code[run_start].second].len;
        cout << "\t" <<  FormatAsBits(cur_code, code_len) << "\n";

        //cout << "storing [L] entry into: " << decode_table_idx << "\n";
        (*decode_table)[decode_table_idx + cur_idx] = DecodeEntry(sym, branch_idx);
      } else {
        uint32_t sym = sorted_by_code[run_end - 1].second;
        uint32_t nxt_code_len = code_table[sym].len;
        uint32_t nxt_code = sorted_by_code[run_end - 1].first;
        uint32_t nxt_bit_len = nxt_code_len - (msb + bw);
        cout << " Recurse: " << setw(6) << cur_idx
             << " " << setw(6) << (cur_idx + decode_table_idx)
             << "\t" <<  FormatAsBits(cur_code, msb + bw)
             << " " << run_start << "->" << run_end
             << " (" << (run_end - run_start) << ")"
             << " (" << min(nxt_bit_len, bw) << ")"
             <<"\n";
        //cout << "storing [R] entry into: " << decode_table_idx << "\n";
        (*decode_table)[decode_table_idx + cur_idx] =
          DecodeEntry(0, branches->size());
        AltBuildDecodeHelper(sorted_by_code, decode_table, branches,
                             run_start, run_end,
                             msb + bw, min(bw, nxt_bit_len));
      }
      run_start = run_end;
    }
  }

  Branches branches;
  DecodeTable decode_table;

  void AltBuildDecodeTable() {
    const int lookup_bits = 8;
    const uint32_t max_val = (0x1U << lookup_bits);

    vector<pair<uint32_t, int> > sorted_by_code; // code->symbol
    for (int i = 0; i < code_table.size(); ++i) {
      pair<uint32_t, int> insert_val;
      insert_val.first = code_table[i].val;
      insert_val.second = i;
      sorted_by_code.push_back(insert_val);
    }
    sort(sorted_by_code.begin(), sorted_by_code.end());

    AltBuildDecodeHelper(sorted_by_code, &decode_table, &branches,
                         0, sorted_by_code.size(),
                         0, lookup_bits);
    cout << "Done building tables. Displayin' 'em now\n";
    for (uint32_t i = 0; i < decode_table.size(); ++i) {
      if (!decode_table[i].valid)
        decode_table[i] = decode_table[i-1];
      cout << setw(6) << i << " " << decode_table[i] << "\n";
    }
    for (int i = 0; i < branches.size(); ++i) {
      cout << i << " " << branches[i] << "\n";
    }
  }

  void BuildCodeTable() {
    deque<bool> state;
    if (!code_tree)
      return;
    AltBuildCodeTable();
    AltBuildDecodeTable();
    //BuildCodeTableHelper(code_tree, &state);
  }

  Node* code_tree;
  CodeTable code_table;
  unsigned short eof_value;

  // for each possible prefix in the first 9 bits:
  // lookup prefix. If it matches a terminal, 

 public:
  Huffman() : code_tree(0), eof_value(256) { }
  ~Huffman() { DeleteCodeTree(); }

  void Init(const vector<pair<uint16_t, uint32_t> >& freq_table) {
    for (uint32_t divisor = 1;
         BuildCodeTree(freq_table, divisor) > 32;
         divisor *= 2){}
    // And now that we know that all the codes are <= 32 bits long...
    BuildCodeTable();
  }

  void Encode(BitBucket* bb, const string& str, bool use_eof) const {
    for (int i = 0; i < str.size(); ++i) {
      unsigned short idx = str[i];
      bb->StoreBits(code_table[idx].vec, code_table[idx].len);
    }
    if (use_eof) {
      bb->StoreBits(code_table[eof_value].vec, code_table[eof_value].len);
    }
  }

  void AltDecode(string* output, BitBucket* bb,
              bool use_eof, int bits_to_decode) const{
    int total_bits = 0;
    if (!use_eof && bits_to_decode < 0) {
      cerr << "Invalid parameters for Decode\n";
      abort();
    }
    while (bits_to_decode < 0 || total_bits < bits_to_decode) {
      Node* root = code_tree;
      while (! root->terminal) {
        bool bit = bb->GetBit();
        root = root->children[bit];
        total_bits += 1;
      }
      if (use_eof && root->terminal && root->c == eof_value) {
        break;
      } else if (root->terminal) {
        output->push_back((char)root->c);
      } else {
        cerr << "This shouldn't ever happen..\n";
        abort();
      }
    }
    if (bits_to_decode > 0 && total_bits < bits_to_decode) {
      bb->SeekDelta(bits_to_decode - total_bits);
    }
  }
  void Decode(string* output, BitBucket* bb,
              bool use_eof, int bits_to_decode) const {
    uint32_t word = 0;
    uint16_t sym = 0;
    int bits_to_shift = 32;
    if (use_eof && bits_to_decode <= 0) {
      while (true) {
        bb->ShiftBitsIntoWord(&word, bits_to_shift);
        bb->ConsumeBits(bits_to_shift);
        //cout << *bb << "\n";
        bits_to_shift = AltDecodeFromWord(word, &sym);
        //cout << bb->DebugStr(-32, bits_to_shift) << "\n";
        if (sym == eof_value)
          return;
        output->push_back(sym);
      }
    } else if (use_eof) { // limited by both eof and bits.
      while (bits_to_decode > 0) {
        bb->ShiftBitsIntoWord(&word, bits_to_shift);
        bb->ConsumeBits(bits_to_shift);
        //cout << *bb << "\n";
        bits_to_shift = AltDecodeFromWord(word, &sym);
        //cout << bb->DebugStr(-32, bits_to_shift) << "\n";
        if (sym == eof_value)
          return;
        output->push_back(sym);
        bits_to_decode -= bits_to_shift;
      }
    } else if (bits_to_decode > 0) { // limited by bits
      while (bits_to_decode > 0) {
        bb->ShiftBitsIntoWord(&word, bits_to_shift);
        bb->ConsumeBits(bits_to_shift);
        //cout << *bb << "\n";
        bits_to_shift = AltDecodeFromWord(word, &sym);
        //cout << bb->DebugStr(-32, bits_to_shift) << "\n";
        output->push_back(sym);
        bits_to_decode -= bits_to_shift;
      }
    } else {  // not limited by anything. Not tenable.
      abort();
    }
  }

  // returns bits-consumed.
  uint8_t AltDecodeFromWord(uint32_t word, uint16_t* c) const {
    uint32_t b_idx = 0;
    uint32_t d_idx = 0;
    //cout << "(b_idx: " << b_idx << " ";
    for (int i = 0; i < 4; ++i) {
      d_idx = branches[b_idx].base_idx;
      d_idx += (word & branches[b_idx].mask) >> branches[b_idx].shift;
      b_idx = decode_table[d_idx].next_table;
      //cout << "d_idx: " << d_idx << ")";
      //cout << "(b_idx: " << b_idx << " ";
    }
    *c = decode_table[d_idx].sym;
    //cout << " -> sym: " << ReadableUShort(*c) << ", " << code_table[*c].len << ")\n";

    return code_table[*c].len;
  }

  friend ostream& operator<<(ostream &os, const Huffman& huff) {
    for (int i = 0; i < huff.code_table.size(); ++i) {
      os << FormatAsBits(huff.code_table[i].vec, huff.code_table[i].len);
      os << " ";
      OutputCharToOstream(os, i);
      os << "\n";
    }
    //PrettyPrintTreeToStream<Huffman::Node>(huff.code_tree, os);
    return os;
  }
};


