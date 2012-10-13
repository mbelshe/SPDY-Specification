// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef PRETTY_PRINT_TREE_H
#define PRETTY_PRINT_TREE_H

#include <ostream>
#include <sstream>
#include <string>
#include <vector>

using std::ostream;
using std::string;
using std::stringstream;
using std::vector;

class CharMatrix {
 public:

  void WriteVisible(unsigned int* x_pos, unsigned int y_pos, const string& string_to_write) {
    Write(x_pos, y_pos, string_to_write, true);
  }

  void WriteInvisible(unsigned int* x_pos, unsigned int y_pos, const string& string_to_write) {
    Write(x_pos, y_pos, string_to_write, false);
  }

  void Write(unsigned int* x_pos,
             unsigned int y_pos,
             const string& string_to_write,
             bool visible) {
    if (char_matrix_.size() <= y_pos) {
      unsigned int old_size = char_matrix_.size();
      char_matrix_.resize(y_pos + 1);
      offset_.resize(y_pos + 1);
      for (unsigned int i = old_size; i < y_pos + 1; ++i) {
        offset_[i] = 0;
      }
    }
    unsigned int end_x_pos = *x_pos + string_to_write.size() + 1 + offset_[y_pos];
    if (char_matrix_[y_pos].size() < end_x_pos) {
      unsigned int old_size = char_matrix_[y_pos].size();
      char_matrix_[y_pos].resize(end_x_pos);
      for (unsigned int x = old_size; x < (end_x_pos); ++x) {
        char_matrix_[y_pos][x] = ' ';
      }
    }
    for (unsigned int i = 0; i < string_to_write.size(); ++i, ++(*x_pos)) {
      char_matrix_[y_pos][*x_pos + offset_[y_pos]] = string_to_write[i];
      if (!visible || !isprint(string_to_write[i])) {
        --(*x_pos);
        ++offset_[y_pos];
      }
    }
  }

  friend ostream& operator<<(ostream& os, const CharMatrix& cm) {
    for (unsigned int y = 0; y < cm.char_matrix_.size(); ++y) {
      for (unsigned int x = 0; x < cm.char_matrix_[y].size(); ++x) {
        os << cm.char_matrix_[y][x];
      }
      os << "\n";
    }
    return os;
  }
 private:
  vector<vector<char> > char_matrix_;
  vector<unsigned int> offset_;
};

template <typename Node>
int PrettyPrintHelper(const Node* node,
                      int dist_from_root,
                      unsigned int* x_pos,
                      CharMatrix* char_matrix,
                      int parent_pos,
                      int direction) {
  unsigned int tmp_x_pos;
  unsigned int y_pos = dist_from_root * 3;
  if (node->children[0]) {
    int child_end = PrettyPrintHelper(node->children[0],
                                      dist_from_root + 1,
                                      x_pos,
                                      char_matrix,
                                      *x_pos,
                                      0);
    tmp_x_pos = *x_pos - 1;
    char_matrix->WriteVisible(&tmp_x_pos, y_pos + 1, "/");
    --tmp_x_pos;
    for (unsigned int x = child_end + 1; x < tmp_x_pos;) {
      char_matrix->WriteVisible(&x, y_pos + 1, "_");
    }
  }

  unsigned int original_x_pos = *x_pos;
  {
    stringstream s;
    s << "[" << *node << "]";
    char_matrix->WriteVisible(x_pos, y_pos, s.str());
  }

  unsigned int new_x_pos = *x_pos;

  if (dist_from_root != 0) {
    if (direction == 0) {
      tmp_x_pos = *x_pos;
      char_matrix->WriteVisible(&tmp_x_pos, y_pos - 1, "/");
    } else {
      tmp_x_pos = original_x_pos - 1;
      char_matrix->WriteVisible(&tmp_x_pos, y_pos - 1, "\\");
      --tmp_x_pos;
      for (unsigned int x = parent_pos + 1; x < tmp_x_pos;) {
        char_matrix->WriteVisible(&x, y_pos - 2, "_");
      }
    }
  }
  *x_pos += 2;

  if (node->children[1]) {
    tmp_x_pos = *x_pos - 2;
    char_matrix->WriteVisible(&tmp_x_pos, y_pos + 1, "\\");
    PrettyPrintHelper(node->children[1],
                      dist_from_root + 1,
                      x_pos,
                      char_matrix,
                      *x_pos - 2,
                      1);
  }
  return new_x_pos;
}

template <typename Node>
void PrettyPrintTreeToStream(Node* root, ostream& os) {
  CharMatrix char_matrix;
  if (root == NULL) {
    return;
  }

  int x_pos = 0;
  PrettyPrintHelper(root, 0, &x_pos, &char_matrix, 0, 0);
  os << char_matrix;
};


#endif
