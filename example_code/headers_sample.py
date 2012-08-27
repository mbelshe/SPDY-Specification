#!/usr/bin/python
import zlib
import string
import sys
import array
import struct
import re
from optparse import OptionParser
from collections import deque
from bit_bucket import BitBucket
from huffman import Huffman
from spdy_dictionary import spdy_dict
from default_headers import default_requests
from default_headers import default_responses
from harfile import ReadHarFile

request_freq_table = [
  ('e', 3447), ('/', 3366), ('a', 3281), ('s', 3133), ('2', 3072), ('t', 2752),
  ('1', 2743), ('n', 2526), ('i', 2488), ('0', 2419), ('3', 2358), ('c', 2353),
  ('o', 2349), ('.', 2212), ('p', 2016), ('r', 2003), ('m', 1980), ('g', 1917),
  ('4', 1845), ('6', 1796), ('=', 1692), ('8', 1585), ('l', 1571), ('d', 1564),
  ('5', 1528), ('9', 1453), ('7', 1448), ('_', 1442), ('&', 1293), ('%', 1273),
  ('-', 1222), ('b', 1184), ('\x80', 1029), ('h', 988), ('u', 974), (',', 875),
  ('f', 802), ('j', 792), ('A', 771), ('w', 764), ('v', 763), ('F', 709),
  ('D', 651), ('y', 586), ('x', 564), ('k', 529), ('I', 489), ('G', 462),
  ('C', 399), ('S', 396), ('z', 358), ('V', 355), ('B', 354), ('U', 351),
  ('T', 339), ('L', 329), ('R', 315), ('E', 314), ('P', 313), ('q', 312),
  ('N', 306), ('M', 269), ('Z', 257), ('Y', 251), ('X', 250), ('H', 246),
  ('Q', 244), ('W', 243), ('?', 222), ('J', 212), ('O', 210), ('K', 207),
  (':', 147), (';', 122), (' ', 28), ('!', 27), ('(', 23), (')', 23), ('*', 18),
  ('+', 15), ('{', 11), ('}', 11), ('~', 4), ('$', 2), ("'", 2), ('[', 2),
  (']', 2), ('\x00', 0), ('\x01', 0), ('\x02', 0), ('\x03', 0), ('\x04', 0),
  ('\x05', 0), ('\x06', 0), ('\x07', 0), ('\x08', 0), ('\t', 0), ('\n', 0),
  ('\x0b', 0), ('\x0c', 0), ('\r', 0), ('\x0e', 0), ('\x0f', 0), ('\x10', 0),
  ('\x11', 0), ('\x12', 0), ('\x13', 0), ('\x14', 0), ('\x15', 0), ('\x16', 0), 
  ('\x17', 0), ('\x18', 0), ('\x19', 0), ('\x1a', 0), ('\x1b', 0), ('\x1c', 0),
  ('\x1d', 0), ('\x1e', 0), ('\x1f', 0), ('"', 0), ('#', 0), ('<', 0), ('>', 0),
  ('@', 0), ('\\', 0), ('^', 0), ('`', 0), ('|', 0), ('\x7f', 0)
]

response_freq_table = [
  (' ', 6174), ('2', 5697), ('1', 5419), ('0', 5023), ('\x80', 3416),
  ('3', 3138), ('4', 2973), ('e', 2931), ('5', 2624), ('a', 2619), ('8', 2577),
  ('6', 2440), ('9', 2371), ('7', 2361), (':', 2303), ('c', 2209), ('u', 2005),
  ('d', 2001), ('T', 1991), ('M', 1849), ('n', 1770), ('o', 1751), ('b', 1608),
  ('t', 1564), ('G', 1515), ('i', 1458), (',', 1437), ('r', 1405), ('A', 1387),
  ('g', 1352), ('f', 1343), ('l', 1189), ('=', 1147), ('F', 1136), ('p', 1109),
  ('s', 1087), ('m', 1050), ('C', 998), ('/', 975), ('-', 928), ('D', 919),
  ('E', 835), ('h', 834), ('x', 825), ('S', 815), ('J', 781), ('B', 738),
  ('w', 669), ('.', 648), ('v', 641), ('O', 633), ('W', 622), ('y', 617),
  ('"', 580), ('P', 561), ('N', 557), ('U', 554), ('k', 549), ('I', 543),
  ('j', 526), ('R', 508), ('L', 492), ('Z', 488), ('V', 482), ('K', 478),
  ('z', 478), ('Q', 476), ('Y', 476), ('q', 463), ('X', 454), ('H', 446), 
  (';', 278), ('+', 276), ('_', 270), ('(', 156), (')', 156), ('&', 136),
  ('%', 123), ('\x00', 53), ('?', 16), ('|', 11), ('#', 9), ('{', 4), ('}', 4),
  ('*', 2), ('[', 2), (']', 2), ('!', 1), ('\x01', 0), ('\x02', 0),
  ('\x03', 0), ('\x04', 0), ('\x05', 0), ('\x06', 0), ('\x07', 0), ('\x08', 0),
  ('\t', 0), ('\n', 0), ('\x0b', 0), ('\x0c', 0), ('\r', 0), ('\x0e', 0),
  ('\x0f', 0), ('\x10', 0), ('\x11', 0), ('\x12', 0), ('\x13', 0), ('\x14', 0),
  ('\x15', 0), ('\x16', 0), ('\x17', 0), ('\x18', 0), ('\x19', 0), ('\x1a', 0),
  ('\x1b', 0), ('\x1c', 0), ('\x1d', 0), ('\x1e', 0), ('\x1f', 0), ('$', 0),
  ("'", 0), ('<', 0), ('>', 0), ('@', 0), ('\\', 0), ('^', 0), ('`', 0),
  ('~', 0), ('\x7f', 0)
]

request_freq_table = [
  ('\x00', 0), ('\x01', 0), ('\x02', 0), ('\x03', 0), ('\x04', 0), ('\x05', 0),
  ('\x06', 0), ('\x07', 0), ('\x08', 0), ('\t', 0), ('\n', 0), ('\x0b', 0),
  ('\x0c', 0), ('\r', 0), ('\x0e', 0), ('\x0f', 0), ('\x10', 0), ('\x11', 0),
  ('\x12', 0), ('\x13', 0), ('\x14', 0), ('\x15', 0), ('\x16', 0), ('\x17', 0),
  ('\x18', 0), ('\x19', 0), ('\x1a', 0), ('\x1b', 0), ('\x1c', 0), ('\x1d', 0),
  ('\x1e', 0), ('\x1f', 0), (' ', 28), ('!', 27), ('"', 0), ('#', 0),
  ('$', 2), ('%', 1273), ('&', 1293), ("'", 2), ('(', 23), (')', 23),
  ('*', 18), ('+', 15), (',', 875), ('-', 1222), ('.', 2212), ('/', 3366), 
  ('0', 2419), ('1', 2743), ('2', 3072), ('3', 2358), ('4', 1845), ('5', 1528),
  ('6', 1796), ('7', 1448), ('8', 1585), ('9', 1453), (':', 147), (';', 122),
  ('<', 0), ('=', 1692), ('>', 0), ('?', 222), ('@', 0), ('A', 771),
  ('B', 354), ('C', 399), ('D', 651), ('E', 314), ('F', 709), ('G', 462),
  ('H', 246), ('I', 489), ('J', 212), ('K', 207), ('L', 329), ('M', 269),
  ('N', 306), ('O', 210), ('P', 313), ('Q', 244), ('R', 315), ('S', 396),
  ('T', 339), ('U', 351), ('V', 355), ('W', 243), ('X', 250), ('Y', 251),
  ('Z', 257), ('[', 2), ('\\', 0), (']', 2), ('^', 0), ('_', 1442),
  ('`', 0), ('a', 3281), ('b', 1184), ('c', 2353), ('d', 1564), ('e', 3447),
  ('f', 802), ('g', 1917), ('h', 988), ('i', 2488), ('j', 792), ('k', 529),
  ('l', 1571), ('m', 1980), ('n', 2526), ('o', 2349), ('p', 2016), ('q', 312),
  ('r', 2003), ('s', 3133), ('t', 2752), ('u', 974), ('v', 763), ('w', 764),
  ('x', 564), ('y', 586), ('z', 358), ('{', 11), ('|', 0), ('}', 11),
  ('~', 4), ('\x7f', 0), ('\x80', 1029)]


def ListToStr(val):
  return ''.join(["%c" % c for c in val])

def StrToList(val):
  return [ord(c) for c in val]

class WordFreak:
  def __init__(self):
    self.code = []
    self.character_freaks = []
    for i in xrange(128 + 1):
      self.character_freaks.append(0)

  def LookAt(self, ops):
    for op in ops:
      for key in ['key', 'val']:
        if key in op:
          self.character_freaks[128] += 1
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
      retval.append( (chr(i), self.character_freaks[i]))

    return repr(retval)

  def __str__(self):
    return self.__repr__()

def MakeReadableString(val):
  printable = string.digits + string.letters + string.punctuation + ' ' + "\t"
  out = []
  for c in val:
    if c in printable:
      out.append("   %c " % c)
    else:
      out.append("0x%02x " % ord(c))
  return ''.join(out)

def IntTo2B(val):
  if val > 65535:
    raise StandardError()
  return struct.pack("!L", val)[2:]

def IntTo1B(val):
  if val > 255:
    raise StandardError()
  return struct.pack("!L", val)[3:]

def B2ToInt(val):
  arg = "%c%c%c%c" % (0,0, val[0],val[1])
  return struct.unpack("!L", arg)[0]

def LB2ToInt(val):
  return (2, B2ToInt(val))

def B1ToInt(val):
  arg = "%c%c%c%c" % (0,0,0,val[0])
  return struct.unpack("!L", arg)[0]

def LB1ToInt(val):
  return (1, B1ToInt(val))

def LenIntTo2B(val):
  return IntTo2B(len(val))

def SetBitsInByte(lsb_bw, x):
  (lsb, bw) = lsb_bw
  return (x & ( ~(255 << bw))) << (7 - lsb - (bw - 1))

def GetBitsInByte(lsb_bw, x):
  (lsb, bw) = lsb_bw
  return (x >> (7 - lsb - (bw - 1))) & (~(255 << bw))

def PackB2LenPlusStr(x):
  return ''.join([IntTo2B(len(x)), x])

def XtrtB2LenPlusStr(x):
  len = B2ToInt(x)
  return (2 + len, ''.join([chr(i) for i in x[2:len+2]]))

inline_packing_instructions = {
  'opcode'     : ((0,3),             None),
  'index'      : ( None,          IntTo2B),
  'index_start': ( None,          IntTo2B),
  'key_idx'    : ( None,          IntTo2B),
  'val'        : ( None, PackB2LenPlusStr),
  'key'        : ( None, PackB2LenPlusStr),
}

inline_unpacking_instructions = {
  'opcode'     : ((0,3),             None),
  'index'      : ( None,         LB2ToInt),
  'index_start': ( None,         LB2ToInt),
  'key_idx'    : ( None,         LB2ToInt),
  'val'        : ( None, XtrtB2LenPlusStr),
  'key'        : ( None, XtrtB2LenPlusStr),
}

packing_order = ['opcode',
                 'index',
                 'index_start',
                 'key_idx',
                 'key',
                 'val',
                 ]

opcodes = {
    'toggl': (0x0, 'index'),
    'clone': (0x1, 'index',                'key_idx', 'val'),
    'kvsto': (0x2, 'index', 'key',                    'val'),
    'trang': (0x3, 'index', 'index_start'),
    'rem'  : (0x4, 'index'),
    'eref' : (0x5,          'key',                    'val'),

    }

def OpcodeSize(unpacking_instructions, opcode):
  retval = 1
  instructions = opcodes[opcode][1:]
  fake_data = [0,0,0,0,0,0,0,0,0,0,0,0]  # should be larger than any field.
  for field_name in instructions:
    (_, tp_func) = unpacking_instructions[field_name]
    if tp_func:
      (advance, _) = tp_func(fake_data)
      retval += advance
  return retval

def OpcodeToVal(x):
  return opcodes[x][0]

def UnpackSPDY4Ops(unpacking_instructions, real_ops):
  opcode_to_op = {}
  for (key, val) in opcodes.iteritems():
    opcode_to_op[val[0]] = [key] + list(val[1:])

  ops = []
  while len(real_ops):
    opcode = GetBitsInByte(unpacking_instructions['opcode'][0], real_ops[0])
    op = {}
    op['opcode'] = opcode_to_op[opcode][0]
    fb = real_ops[0]
    real_ops = real_ops[1:]
    for field_name in opcode_to_op[opcode][1:]:
      if field_name == 'opcode':
        continue
      if not field_name in unpacking_instructions:
        print field_name, " is not in instructions"
        raise StandardError();
      (fb_func_params, tp_func) = unpacking_instructions[field_name]
      if fb_func_params is not None:
        op[field_name] = GetBitsInByte(fb_func_params, fb)
      if tp_func is not None:
        (advance, result) = tp_func(real_ops)
        op[field_name] = result
        real_ops = real_ops[advance:]
    ops.append(op)
  return ops

def PackSpdy4Ops(packing_instructions, ops):
  top_block = []
  str_block = []
  for op in ops:
    fb = 0
    tb = []
    for field_name in packing_order:
      if not field_name in op:
        continue
      (fb_func_params, tp_func) = packing_instructions[field_name]
      val = op[field_name]
      if field_name == 'opcode':
        val = OpcodeToVal(op[field_name])
      if fb_func_params is not None:
        fb = fb | SetBitsInByte(fb_func_params, val)
      if tp_func is not None:
        tb.append(tp_func(val))
    top_block.append(chr(fb))
    top_block.extend(tb)
  top_block_str = ''.join(top_block)
  return top_block_str


def RealOpsToOps(realops):
  return UnpackSPDY4Ops(inline_unpacking_instructions, ListToStr(realop))

def FormatOp(op):
  order = packing_order
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key is not 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key])))
    if key in op and key is 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key]).ljust(7)))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': %s" % (key, repr(op[key])))
  outp.append(', '.join(inp))
  outp.append('}')
  return ''.join(outp)

def KtoV(d):
  retval = {}
  for (k, v) in d.iteritems():
    retval[v] = k
  return retval

def NextIndex(d):
  indices = [idx for (idx, val) in d.iteritems()]
  if len(indices) == 0:
    return 1
  indices.sort()
  prev_idx = 0
  idx = 0
  for idx in indices:
    if idx - prev_idx > 1:
      # jumped up by more than one.
      return prev_idx + 1
    prev_idx = idx
  return idx + 1

def GetHostname(request):
  if ":host" in request:
    return request[":host"]
  elif "host" in request:
    return request["host"]
  return "<unknown>"


class Line:
  def __init__(self, k="", v=""):
    self.k = k
    self.v = v
    self.RecomputeHash()

  def __repr__(self):
    return '[Line k: %s, v: %s]' % (repr(self.k), repr(self.v))

  def __str__(self):
    return self.__repr__()

  def RecomputeHash(self):
    self.kvhash = hash(self.k + self.v)

class Spdy4CoDe:
  def __init__(self):
    self.huffman_table = None
    self.wf = WordFreak()
    default_dict = {
        ":host": "",
        ":method": "get",
        ":path": "/",
        ":scheme": "https",
        ":status": "200",
        ":status-text": "OK",
        ":version": "1.1",
        "accept": "",
        "accept-charset": "",
        "accept-encoding": "",
        "accept-language": "",
        "accept-ranges": "",
        "allow": "",
        "authorizations": "",
        "cache-control": "",
        "content-base": "",
        "content-encoding": "",
        "content-length": "",
        "content-location": "",
        "content-md5": "",
        "content-range": "",
        "content-type": "",
        "cookie": "",
        "date": "",
        "etag": "",
        "expect": "",
        "expires": "",
        "from": "",
        "if-match": "",
        "if-modified-since": "",
        "if-none-match": "",
        "if-range": "",
        "if-unmodified-since": "",
        "last-modified": "",
        "location": "",
        "max-forwards": "",
        "origin": "",
        "pragma": "",
        "proxy-authenticate": "",
        "proxy-authorization": "",
        "range": "",
        "referer": "",
        "retry-after": "",
        "server": "",
        "set-cookie": "",
        "status": "",
        "te": "",
        "trailer": "",
        "transfer-encoding": "",
        "upgrade": "",
        "user-agent": "",
        "user-agent": "",
        "vary": "",
        "via": "",
        "warning": "",
        "www-authenticate": "",
        'access-control-allow-origin': "",
        'content-disposition': "",
        'get-dictionary': "",
        'p3p': "",
        'x-content-type-options': "",
        'x-frame-options': "",
        'x-powered-by': "",
        'x-xss-protection': "",
        }
    self.compressor = zlib.compressobj(9, zlib.DEFLATED, -11)
    self.decompressor = zlib.decompressobj(-11)
    self.decompressor.decompress(self.compressor.compress(spdy_dict) +
                                 self.compressor.flush(zlib.Z_SYNC_FLUSH))
    self.limits = {'TotalHeaderStorageSize': 20*1024,
                   'MaxHeaderGroups': 1,
                   'MaxEntriesInTable': 640}
    self.total_storage = 0

    # dict_index -> key, val
    self.index_to_line = {}

    # hash-of-key-val -> dict_index
    self.kvhash_to_index = {}

    # key -> dict_indices
    self.key_to_indices = {}

    # LRU of dict_index
    self.lru_of_index = deque()

    # stream_group -> list-of-dict-indices
    self.stream_groups = {0:[]}

    self.largest_index = 0
    self.unused_indices = deque()

    for (k, v) in default_dict.iteritems():
      self.ExecuteOp(-1, self.MakeKvsto(self.GetAnUnusedIndex(), k, v))

  def FindIndex(self, key, val):
    kvhash = hash(key + val)
    possible_indices = []
    #if kvhash in self.kvhash_to_index:
    #  possible_indices = list(self.kvhash_to_index[kvhash])
    if key in self.key_to_indices:
      possible_indices.extend(list(self.key_to_indices[key]))
    for index in possible_indices:
      if (self.index_to_line[index].kvhash == kvhash and
         self.index_to_line[index].k == key and
         self.index_to_line[index].v == val):
        return (index, [])
    return (-1, possible_indices)

  def NewLine(self, key, val):
    return Line(key, val)

  def GetAnUnusedIndex(self):
    if self.unused_indices:  # if we can reuse an index..
      index = self.unused_indices.popleft()
    else:
      index = self.largest_index + 1
      self.largest_index = index
    return index

  def UpdateIndexes(self, index, key, val):
    self.index_to_line[index] = line = self.NewLine(key, val)
    self.total_storage += (len(line.k) + len(line.v))
    key_to_indices = self.key_to_indices.get(key, set())
    key_to_indices.add(index)
    self.key_to_indices[key] = key_to_indices
    kvhash_to_line  = self.kvhash_to_index.get(line.kvhash, set())
    kvhash_to_line.add(index)
    self.kvhash_to_index[line.kvhash] = kvhash_to_line

  def RemoveIndex(self, index):
    # this assumes the LRU has already been taken care of.

    # cleanup index_to_line
    line = self.index_to_line[index]
    self.total_storage -= (len(line.k) + len(line.v))
    del self.index_to_line[index]
    # cleanup key_to_indices
    self.key_to_indices[line.k].remove(index)
    if not self.key_to_indices[line.k]:
      del self.key_to_indices[line.k]
    key_to_index_entry = self.key_to_indices.get(line.k, None)
    # cleanup kvhash_to_index
    self.kvhash_to_index[line.kvhash].remove(index)
    if not self.kvhash_to_index[line.kvhash]:
      del self.kvhash_to_index[line.kvhash]
    # cleanup stream_groups
    for (id, v) in self.stream_groups.iteritems():
      self.stream_groups[id][:] = [x for x in self.stream_groups[id] if x != index]
      if not self.stream_groups[id]:
        del self.stream_groups[id]

  def MoveToFrontOfLRU(self, index):
    new_lru = [x for x in list(self.lru_of_index) if x != index]
    self.lru_of_index = deque(new_lru)
    self.lru_of_index.append(index)

  def Touch(self, index):
    self.MoveToFrontOfLRU(index)

  def MakeRemovalsIfNecessary(self, stream_group, in_ops):
    return []
    num_removed = 0
    ops = []
    indices_removed = []
    while (self.limits['TotalHeaderStorageSize'] < self.total_storage or
           self.limits['MaxEntriesInTable'] < len(self.lru_of_index)):
      oldest_index = self.lru_of_index.popleft()
      line = self.index_to_line[oldest_index]
      if oldest_index in self.stream_groups[stream_group]:
        ops.append(self.MakeERef(line.k, line.v))
      self.RemoveIndex(oldest_index)
      indices_removed.append(oldest_index)
      num_removed += 1
    if num_removed > 0:
      ops.append(self.MakeRem(num_removed))
    return ops

  def OpsToRealOps(self, in_ops):
    ops = []
    if self.huffman_table is None:
      ops = in_ops
    else:
      for op in in_ops:
        new_op = dict(op)
        for k in ['key', 'val']:
          if k in new_op:
            val = new_op[k]
            (e_bytes, e_bits) = self.huffman_table.Encode(StrToList(val), True)
            new_op[k] = ''.join(ListToStr(e_bytes))
        ops.append(new_op)
    return PackSpdy4Ops(inline_packing_instructions, ops)

  def RealOpsToOps(self, realops):
    ops = []
    in_ops = UnpackSPDY4Ops(inline_unpacking_instructions, StrToList(realops))
    if self.huffman_table is None:
      ops = in_ops
    else:
      for op in in_ops:
        new_op = dict(op)
        for k in ['key', 'val']:
          if k in new_op:
            val = new_op[k]
            new_op[k] = ListToStr(self.huffman_table.Decode(StrToList(val), True, -1))
        ops.append(new_op)
    return ops


  def Compress(self, realops):
    ba = ''.join(realops)
    retval = self.compressor.compress(ba)
    retval += self.compressor.flush(zlib.Z_SYNC_FLUSH)
    return retval

  def Decompress(self, op_blob):
    return self.decompressor.decompress(op_blob)

  def MakeToggl(self, index):
    return {'opcode': 'toggl', 'index': index}

  def MakeKvsto(self, index, key, val):
    return {'opcode': 'kvsto', 'index': index, 'val': val, 'key': key}

  def MakeClone(self, index, key_idx, val):
    return {'opcode': 'clone', 'index': index, 'val': val, 'key_idx': key_idx}

  def MakeRem(self, index):
    return {'opcode': 'rem', 'index': index}

  def MakeERef(self, key, value):
    op = {'opcode': 'eref',
          'key': key,
          'val': value}
    return op

  def MakeOperations(self, headers, stream_group):
    ops = []
    headers = dict(headers)
    self.active_stream_group = stream_group
    if not stream_group in self.stream_groups:
      self.stream_groups[stream_group] = []
    for index in list(self.stream_groups[stream_group]):
      key = self.index_to_line[index].k
      val = self.index_to_line[index].v
      if key in headers and headers[key] == val:
        # Awesome, this line is already present!
        del headers[key]
      else:
        # the headers don't have this line in 'em.
        op = self.MakeToggl(index)
        self.ExecuteOp(stream_group, op)
        ops.append(op)
    out_ops = ops
    out_ops.sort()
    ops = []
    for op in out_ops:  # these will ALL be Toggl (off) ops..
      if ops and op['index'] - ops[-1]['index'] == 1:
        if ops[-1]['opcode'] == 'trang':
          ops[-1]['index'] = op['index']
        else:
          ops[-1]['opcode'] = 'trang'
          ops[-1]['index_start'] = ops[-1]['index']
          ops[-1]['index'] = op['index']
      else:
        ops.append(op)
    for (key, vals) in headers.iteritems():
      splitvals = [vals]
      if key == 'cookie': # treat cookie specially...
        splitvals = vals.split(';')
      for val in splitvals:
        (index, possible_indices) = self.FindIndex(key, val)
        if index >= 0 and index not in self.stream_groups[stream_group]:
          # we have a key+value that exists in the dictinary already,
          # but isn't yet in the stream group. Toggle it ON.
          op = self.MakeToggl(index)
          self.ExecuteOp(stream_group, op)
          ops.append(op)
        elif index >= 0 and index in self.stream_groups[stream_group]:
          # this means that something was repeated verbatim.
          # Nah. We don't do that.
          pass
        elif index == -1 and possible_indices:
          # The key exists, but the value is different.
          # Clone the key with a new val.
          op = self.MakeClone(self.GetAnUnusedIndex(), max(possible_indices), val)
          self.ExecuteOp(stream_group, op)
          ops.append(op)
          if not key == "cookie":
            self.wf.LookAt([op])
        elif index == -1 and not possible_indices:
          # The key doesn't exist. Install an entirely new line.
          op = self.MakeKvsto(self.GetAnUnusedIndex(), key, val)
          self.ExecuteOp(stream_group, op)
          ops.append(op)
          if not key == "cookie":
            self.wf.LookAt([op])
    removal_ops = self.MakeRemovalsIfNecessary(stream_group, ops)
    for index in self.stream_groups[stream_group]:
      self.Touch(index)
    return removal_ops + ops

  def RealOpsToOpAndExecute(self, realops, stream_group):
    ops = self.RealOpsToOps(realops)
    self.ExecuteOps(ops, stream_group, {})
    return ops

  def ExecuteOps(self, ops, stream_group, ephemereal_headers={}):
    if not stream_group in self.stream_groups:
      self.stream_groups[stream_group] = []
    for op in ops:
      self.ExecuteOp(stream_group, op, ephemereal_headers)

  def ExecuteOp(self, stream_group, op, ephemereal_headers={}):
    opcode = op["opcode"]
    index = op["index"]
    if opcode == 'trang':
      for i in xrange(op['index_start'], op['index']+1):
        self.ExecuteOp(stream_group, self.MakeToggl(i))
    elif opcode == 'clone':
      key_idx = op["key_idx"]
      # Clone - copies key and stores new value
      # [modifies both stream-group and header_dict]
      self.UpdateIndexes(index, self.index_to_line[key_idx].k, op["val"])
      self.stream_groups[stream_group].append(index)
    elif opcode == 'toggl':
      # Toggl - toggle visibility
      # [applies to stream-group entry only]
      if index in self.stream_groups[stream_group]:
        self.stream_groups[stream_group].remove(index)
      else:
        self.stream_groups[stream_group].append(index)
    elif opcode == 'rem':
      for i in xrange(op['index']):
        self.RemoveIndex(self.lru_of_index.popleft())
    elif opcode == 'eref':
      ephemereal_headers[opcode['key']] = opcode['val']
    elif opcode == 'kvsto':
      # kvsto - store key,value
      # [modifies both stream-group and header_dict]
      self.UpdateIndexes(index, op["key"], op["val"])
      if stream_group >= 0:
        self.stream_groups[stream_group].append(index)

  def GetDictSize(self):
    return self.total_storage

  def GenerateAllHeaders(self, stream_group):
    headers = {}
    for index in self.stream_groups[stream_group]:
      self.Touch(index)
      line = self.index_to_line[index]
      if line.k in headers:
        headers[line.k] = headers[line.k] + '\0' + line.v
      else:
        headers[line.k] = line.v
    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', ';')
    return headers

class SPDY4:
  def __init__(self, options):
    self.compressor   = Spdy4CoDe()
    self.decompressor = Spdy4CoDe()
    self.options = options
    self.hosts = {}
    self.wf = self.compressor.wf

  def ProcessFrame(self, inp_headers, request_headers):
    normalized_host = re.sub("[0-1a-zA-Z-\.]*\.([^.]*\.[^.]*)", "\\1",
                             request_headers[":host"])
    if normalized_host in self.hosts:
      stream_group = self.hosts[normalized_host]
    else:
      stream_group = NextIndex(KtoV(self.hosts))
      self.hosts[normalized_host] = stream_group
    if self.options.f:
      stream_group = 0
    inp_ops = self.compressor.MakeOperations(inp_headers, stream_group)

    inp_real_ops = self.compressor.OpsToRealOps(inp_ops)
    compressed_blob = self.compressor.Compress(inp_real_ops)
    out_real_ops = self.decompressor.Decompress(compressed_blob)
    out_ops = self.decompressor.RealOpsToOpAndExecute(out_real_ops, stream_group)
    out_headers = self.decompressor.GenerateAllHeaders(stream_group)
    return (compressed_blob,
            inp_real_ops, out_real_ops,
            inp_headers,  out_headers,
            inp_ops,      out_ops,
            stream_group)

class SPDY3:
  def __init__(self, options):
    self.options = options
    self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                       zlib.DEFLATED, 11)
    self.compressor.compress(spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    spdy3_frame = self.Spdy3HeadersFormat(inp_headers)
    return ((self.compressor.compress(spdy3_frame) +
             self.compressor.flush(zlib.Z_SYNC_FLUSH)),
             spdy3_frame)

  def Spdy3HeadersFormat(self, request):
    out_frame = []
    for (key, val) in request.iteritems():
      out_frame.append(struct.pack("!L", len(key)))
      out_frame.append(key)
      out_frame.append(struct.pack("!L", len(val)))
      out_frame.append(val)
    return ''.join(out_frame)


class HTTP1:
  def __init__(self, options):
    self.options = options
    self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                       zlib.DEFLATED, 11)
    self.compressor.compress(spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    http1_frame = self.HTTP1HeadersFormat(inp_headers)
    return ((self.compressor.compress(http1_frame) +
             self.compressor.flush(zlib.Z_SYNC_FLUSH)),
             http1_frame)

  def HTTP1HeadersFormat(self, frame):
    out_frame = []
    fl = ""
    avoid_list = []
    if ":method" in frame:
      fl = "%s %s HTTP/%s\r\n" % (
          frame[":method"],frame[":path"],frame[":version"])
      avoid_list = [":method", ":path", ":version"]
    else:
      fl = "HTTP/%s %s %s\r\n" % (
          frame[":version"],frame[":status"],frame[":status-text"])
      avoid_list = [":version", ":status", ":status-text"]
    out_frame.append(fl)
    for (key, val) in frame.iteritems():
      if key in avoid_list:
        continue
      if key == ":host":
        key = "host"
      for individual_val in val.split('\x00'):
        out_frame.append(key)
        out_frame.append(": ")
        out_frame.append(individual_val)
        out_frame.append("\r\n")
    return ''.join(out_frame)

def main():
  parser = OptionParser()
  parser.add_option("-v", "--verbose",
                    type="int",
                    dest="v",
                    help="Sets verbosity. At v=1, the opcodes will be printed. "
                    "At v=2, so will the headers [default: %default]",
                    default=0,
                    metavar="VERBOSITY")
  parser.add_option("-f", "--force_streamgroup",
                    dest="f",
                    help="If set, everything will use stream-group 0. "
                    "[default: %default]",
                    default=0)
  (options, args) = parser.parse_args()

  print options
  for (opcode, _) in opcodes.iteritems():
    print "opcode: % 7s size: % 3d" % ("'" + opcode + "'",
        OpcodeSize(inline_unpacking_instructions, opcode))
  requests = default_requests
  responses = default_responses
  if args >= 1:
    requests = []
    responses = []
    for filename in args:
      (har_requests, har_responses) = ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)

  spdy4_rq = SPDY4(options)
  spdy4_rq.compressor.huffman_table = Huffman(request_freq_table)
  spdy4_rq.decompressor.huffman_table = spdy4_rq.compressor.huffman_table
  spdy3_rq = SPDY3(options)
  http1_rq = HTTP1(options)
  spdy4_rs = SPDY4(options)
  spdy4_rs.compressor.huffman_table = Huffman(response_freq_table)
  spdy4_rs.decompressor.huffman_table = spdy4_rs.compressor.huffman_table
  spdy3_rs = SPDY3(options)
  http1_rs = HTTP1(options)

  print "        UC: UnCompressed frame size"
  print "        CM: CoMpressed frame size"
  print "        UR: Uncompressed / Http uncompressed"
  print "        CR:   Compressed / Http compressed"
  def framelen(x):
    return  len(x) + 10
  h1usrq = 0
  h1csrq = 0
  s3usrq = 0
  s3csrq = 0
  s4usrq = 0
  s4csrq = 0
  h1usrs = 0
  h1csrs = 0
  s3usrs = 0
  s3csrs = 0
  s4usrs = 0
  s4csrs = 0
  for i in xrange(len(requests)):
    request = requests[i]
    response = responses[i]
    rq4 = spdy4_rq.ProcessFrame(request, request)
    rs4 = spdy4_rs.ProcessFrame(response, request)
    rq3 = spdy3_rq.ProcessFrame(request, request)
    rs3 = spdy3_rs.ProcessFrame(response, request)
    rqh = http1_rq.ProcessFrame(request, request)
    rsh = http1_rs.ProcessFrame(response, request)
    if options.v >= 2:
      print '##################################################################'
      print '####### request-path: "%s"' % requests[i][":path"][:80]
      print "####### stream group: %2d, %s" % (rq4[7], GetHostname(request))
      print "####### dict size: %3d" % spdy4_rs.decompressor.GetDictSize()
      print

      print "## request ##\n", rqh[1]
      if options.v >= 4:
        print "request  header: ", request
      for op in rq4[6]:
        print FormatOp(op)

      print "\n## response ##\n", rqh[1]
      if options.v >= 4:
        print "response header: ", response
      for op in rs4[6]:
        print FormatOp(op)
      print
    if not request == rq4[4]:
      print "Something is wrong with the request."
      if options.v >= 1:
        print sorted([(k,v) for k,v in request.iteritems()])
        print "   !="
        print sorted([(k,v) for k,v in rq4[4].iteritems()])
        print
    if not response == rs4[4]:
      print "Something is wrong with the response."
      if options.v >= 1:
        print sorted([(k,v) for k,v in response.iteritems()])
        print "   !="
        print sorted([(k,v) for k,v in rs4[4].iteritems()])
        print

    (h1comrq, h1uncomrq) = map(len, rqh)
    h1usrq += h1uncomrq; h1csrq += h1comrq
    (s3comrq, s3uncomrq) = map(framelen, rq3)
    s3usrq += s3uncomrq; s3csrq += s3comrq
    (s4comrq, s4uncomrq) = map(framelen, rq4[:2])
    s4usrq += s4uncomrq; s4csrq += s4comrq

    (h1comrs, h1uncomrs) = map(len, rsh)
    h1usrs += h1uncomrs; h1csrs += h1comrs
    (s3comrs, s3uncomrs) = map(framelen, rs3)
    s3usrs += s3uncomrs; s3csrs += s3comrs
    (s4comrs, s4uncomrs) = map(framelen, rs4[:2])
    s4usrs += s4uncomrs; s4csrs += s4comrs

    lines= [
    ("http1 req", h1uncomrq, h1comrq, 1.0*h1uncomrq/h1uncomrq, 1.0*h1comrq/h1comrq),
    ("spdy3 req", s3uncomrq, s3comrq, 1.0*s3uncomrq/h1uncomrq, 1.0*s3comrq/h1comrq),
    ("spdy4 req", s4uncomrq, s4comrq, 1.0*s4uncomrq/h1uncomrq, 1.0*s4comrq/h1comrq),
    ("http1 res", h1uncomrs, h1comrs, 1.0*h1uncomrs/h1uncomrs, 1.0*h1comrs/h1comrs),
    ("spdy3 res", s3uncomrs, s3comrs, 1.0*s3uncomrs/h1uncomrs, 1.0*s3comrs/h1comrs),
    ("spdy4 res", s4uncomrs, s4comrs, 1.0*s4uncomrs/h1uncomrs, 1.0*s4comrs/h1comrs),
    ]
    if options.v >= 1:
      print "                            UC  |  CM  |  UR  |  CR"
      for fmtarg in lines:
        print "     %s frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
      print
  print "Thats all folks. If you see this, everything worked OK"

  print "######################################################################"
  print "######################################################################"
  print
  print "                                       http1   |   spdy3   |   spdy4 "
  fmtarg = (h1usrq, s3usrq, s4usrq)
  print "Req              Uncompressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg
  fmtarg = (h1csrq,  s3csrq, s4csrq)
  print "Req                Compressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg

  if h1usrq:
    fmtarg = (h1usrq*1./h1usrq,  s3usrq*1./h1usrq, s4usrq*1./h1usrq)
    print "Req Uncompressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
    fmtarg = (h1csrq*1./h1usrq,  s3csrq*1./h1usrq, s4csrq*1./h1usrq)
    print "Req   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
    print
  fmtarg = (h1usrs, s3usrs, s4usrs)
  print "Res              Uncompressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg
  fmtarg = (h1csrs,  s3csrs, s4csrs)
  print "Res                Compressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg
  if h1usrs:
    fmtarg = (h1usrs*1./h1usrs,  s3usrs*1./h1usrs, s4usrs*1./h1usrs)
    print "Res Uncompressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
    fmtarg = (h1csrs*1./h1usrs,  s3csrs*1./h1usrs, s4csrs*1./h1usrs)
    print "Res   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
  print


  #print spdy4_rq.wf
  #rq_huff = Huffman(spdy4_rq.wf.GetFrequencies())
  #print rq_huff.FormatCodeTable()

  #print spdy4_rs.wf
  #rs_huff = Huffman(spdy4_rs.wf.GetFrequencies())
  #print rs_huff.FormatCodeTable()

  #hrt = Huffman(request_freq_table)
  #print
  print spdy4_rq.wf

main()
