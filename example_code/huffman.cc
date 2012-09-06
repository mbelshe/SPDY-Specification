#include <stdlib.h>
#include <assert.h>

#include <deque>
#include <utility>
#include <vector>
#include <ostream>
#include <iostream>
#include <algorithm>
#include "pretty_print_tree.cc"
#include "bit_bucket.cc"
#include <array>

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

void OutputCharToOstream(ostream& os, unsigned int c) {
  if (c > 256 + 1)
    abort();
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
        if (c < 256) {
          if (c >= 16) {
            os << "\\x" << hex << c << dec;
          } else {
            os << "\\x0" << hex << c << dec;
          }
        } else {
          os << c;
        }
        break;
    }
  }
  os << "'";
}

class Huffman {

  struct Node {
    double weight;
    Node* children[2];
    Node* parent;
    unsigned int c;
    bool terminal;

    explicit Node() : weight(0), parent(0), c(0), terminal(false) {
      children[0] = children[1] = 0;
    }
    explicit Node(unsigned int c, double weight) :
        weight(weight + 1.0/256.0), parent(0), c(c), terminal(true) {
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

  void GetNextNode(Node* current_leaf, int child_idx,
                   deque<Node*> *leaves, deque<Node*> *internals) {
    assert (current_leaf->children[child_idx] == 0);
    if (internals->size() && leaves->size()) {
      if (leaves->front()->weight <= internals->front()->weight) {
        current_leaf->children[child_idx] = leaves->front();
        leaves->pop_front();
      } else {
        current_leaf->children[child_idx] = internals->front();
        internals->pop_front();
      }
    } else if (internals->size()) {
      current_leaf->children[child_idx] = internals->front();
      internals->pop_front();
    } else {
      assert(leaves->size() != 0);
      current_leaf->children[child_idx] = leaves->front();
      leaves->pop_front();
    }
    current_leaf->weight += current_leaf->children[child_idx]->weight;
  }

  static bool NodePtrComp(const Node* a,const Node* b) {
    if (a->weight != b->weight) {
      return a->weight < b->weight;
    } else if (a->terminal != b->terminal) {
      return !a->terminal;
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

  void BuildCodeTree(const vector<pair<unsigned int, long> >& freq_table) {
    deque<Node*> leaves;
    deque<Node*> internals;
    if (freq_table.size() <= 2) {
      // that would be stupid, to say the least.
      abort();
    }
    for (int i = 0; i < freq_table.size(); ++i) {
      leaves.push_back(new Node(freq_table[i].first, freq_table[i].second));
    }
    sort(leaves.begin(), leaves.end(), NodePtrComp);

    Node* current_leaf = new Node();
    leaves.pop_front();
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
    code_tree = internals.front();
  }

  void BuildCodeTableHelper(Node* current, deque<bool>* state) {
    if (current->terminal) {

      OutputCharToOstream(cout, current->c);
      cout << "\n";

      BitBucket bb;
      for (int i = 0; i < state->size(); ++i) {
        bb.StoreBit((*state)[i]);
        cout << (*state)[i];
      }
      cout << "\n";

      cout << bb << "\n";
      cout << bb.DebugStr() << "\n";
      unsigned int idx = current->c;
      code_table[idx] = make_pair(vector<char>(), state->size());
      bb.GetBits(&(code_table[idx].first), state->size());
      cout << FormatAsBits(code_table[idx].first, code_table[idx].second) << "\n";
    }

    state->push_back(false);
    if (current->children[0]) {
      BuildCodeTableHelper(current->children[0], state);
    }
    state->pop_back();

    state->push_back(true);
    if (current->children[1]) {
      BuildCodeTableHelper(current->children[1], state);
    }
    state->pop_back();
  }

  void BuildCodeTable() {
    deque<bool> state;
    if (!code_tree)
      return;
    BuildCodeTableHelper(code_tree, &state);
  }

  Node* code_tree;
  array<pair<vector<char>, int>, 256+1> code_table;

 public:
  Huffman() : code_tree(0) { }
  ~Huffman() { DeleteCodeTree(); }

  void Init(const vector<pair<unsigned int, long> >& freq_table) {
    BuildCodeTree(freq_table);
    BuildCodeTable();
  }

  friend ostream& operator<<(ostream &os, const Huffman& huff) {
    for (int i = 0; i < huff.code_table.size(); ++i) {
      OutputCharToOstream(os, i);
      os << "\t" << FormatAsBits(huff.code_table[i].first,
                                 huff.code_table[i].second);
      os << "\n";
    }
    PrettyPrintTreeToStream<Huffman::Node>(huff.code_tree, os);
    return os;
  }
};


