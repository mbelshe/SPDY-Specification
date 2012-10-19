# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class WordFreak:
  def __init__(self):
    self.code = []
    self.character_freaks = []
    self.length_freaks = {}
    for i in xrange(256 + 1):
      self.character_freaks.append(0)

  def LookAt(self, ops):
    for op in ops:
      for key in ['key', 'val']:
        if key in op:
          self.length_freaks[len(op[key])] = self.length_freaks.get(len(op[key]),0) + 1
          self.character_freaks[256] += 1
          for c in op[key]:
            self.character_freaks[ord(c)] += 1

  def SortedByFreq(self):
    x = [ (chr(i), self.character_freaks[i]) for i in xrange(len(self.character_freaks))]
    return sorted(x, key=lambda x: x[1], reverse=True)

  def GetFrequencies(self):
    return self.character_freaks

  def __repr__(self):
    retval = []
    for i in xrange(len(self.character_freaks)):
      if (i < 256):
        retval.append( (chr(i), self.character_freaks[i]))
      else:
        retval.append( (i, self.character_freaks[i]))

    return repr(retval)

  def __str__(self):
    return self.__repr__()

