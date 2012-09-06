#!/usr/bin/python

import array
import re
import string
import struct
import sys
import zlib

from bit_bucket import BitBucket
from collections import defaultdict
from collections import deque
from common_utils import *
from common_utils import FormatAsBits
from default_headers import default_requests
from default_headers import default_responses
from harfile import ReadHarFile
from header_freq_tables import request_freq_table
from header_freq_tables import response_freq_table
from huffman import Huffman
from optparse import OptionParser
from spdy_dictionary import spdy_dict
from word_freak import WordFreak


# TODO(eliminate the 'index' parameter in clone and kvsto by
#      adding an index-start to the frame)
# TODO(try var-int encoding for indices)
# TODO(make removals from the LRU implicit-- send no messages about them)
# TODO(use a separate huffman encoding for cookies, and possible path)
# TODO(interpret cookies as binary instead of base-64, does it reduce entropy?)
# TODO(modification to 'toggl' to allow for a list of indices instead
#      of requiring a new operation for each index not in a consecutive range)
# TODO(index renumbering so things which are often used together
#      have near indices. Possibly renumber whever something is referenced)


def UnpackInt(data, params, huff):
  (idx, bitlen) = params
  #print 'AAAAAAAAAAAAAAAAAAAAAAAAA INT(', bitlen, ")"
  #data[idx].DebugFormat()
  raw_data = data[idx].GetBits(bitlen)[0]
  rshift = 0
  if bitlen <=8:
    arg = "%c%c%c%c" % (0,0, 0,raw_data[0])
    rshift = 8 - bitlen
  elif bitlen <=16:
    arg = "%c%c%c%c" % (0,0, raw_data[0], raw_data[1])
    rshift = 16 - bitlen
  elif bitlen <=24:
    arg = "%c%c%c%c" % (0,raw_data[0], raw_data[1], raw_data[2])
    rshift = 24 - bitlen
  else:
    arg = "%c%c%c%c" % (raw_data[0], raw_data[1], raw_data[2], raw_data[3])
    rshift = 32 - bitlen
  retval = (struct.unpack(">L", arg)[0] >> rshift)
  #print FormatAsBits((raw_data, bitlen)), "(", retval, ")"
  #data[idx].DebugFormat(
  #print 'XXXXXXXXXXXXXXXXXXXXXXXXX'
  return retval

def UnpackStr(data, params, huff):
  (bitlen_idx, bitlen_size, data_idx, use_eof, len_as_bits) = params
  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  bitlen = -1
  #print 'AAAAAAAAAAAAAAAAAAAAAAAAA STR'
  if bitlen_size:
    bitlen = UnpackInt(data, (bitlen_idx, bitlen_size), huff)
    if not len_as_bits:
      bitlen *= 8
    #print "unpack strlen_field: ", bitlen
  #data[data_idx].DebugFormat()
  if huff:
    retval = huff.DecodeFromBB(data[data_idx], use_eof, bitlen)
  else:
    retval = data[data_idx].GetBits(bitlen)[0]
  #data[data_idx].DebugFormat()
  retval = ListToStr(retval)
  #print "str_decoded: ", retval
  #print 'XXXXXXXXXXXXXXXXXXXXXXXXX'
  return retval

# this assumes the bits are near the LSB, but must be packed to be close to MSB
def PackInt(data, params, val, huff):
  (idx, bitlen) = params
  if bitlen <= 0 or bitlen > 32 or val  != val & ~(0x1 << bitlen):
    print "bitlen: ", bitlen, " val: ", val
    raise StandardError()
  if bitlen <= 8:
    tmp_val = struct.pack(">B", val << (8 - bitlen))
  elif bitlen <= 16:
    tmp_val = struct.pack(">H", val << (16 - bitlen))
  elif bitlen <= 24:
    tmp_val = struct.pack(">L", val << (24 - bitlen))[1:]
  else:
    tmp_val = struct.pack(">L", val << (32 - bitlen))

  #print FormatAsBits((StrToList(tmp_val), bitlen)), " (", val, ")"
  data[idx].StoreBits( (StrToList(tmp_val), bitlen) )

def PackStr(data, params, val, huff):
  (bitlen_idx, bitlen_size, data_idx, use_eof, len_as_bits) = params
  # if len_as_bits, then don't need eof.
  # if eof, then don't technically need bitlen at all...

  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  if huff:
    formatted_val = huff.Encode(StrToList(val), use_eof)
    if not len_as_bits:
      formatted_val = (formatted_val[0], len(formatted_val[0])*8)
  else:
    formatted_val = ([val], len(val)*8)
  if bitlen_size and len_as_bits:
    #print "strlen_field: ", formatted_val[1], " bits"
    PackInt(data, (bitlen_idx, bitlen_size), formatted_val[1], huff)
  elif bitlen_size:
    #print "strlen_field: ", formatted_val[1]/8, " bytes ", "(", formatted_val[1], " bits)"
    PackInt(data, (bitlen_idx, bitlen_size), formatted_val[1]/8, huff)

  #print FormatAsBits(formatted_val), " (", repr(val), ")", "(", repr(ListToStr(formatted_val[0])), ")"
  data[data_idx].StoreBits(formatted_val)



alt_packing_instructions = {
  'opcode'      : ((0,  8), PackInt, UnpackInt),
  'index'       : ((0, 16), PackInt, UnpackInt),
  'index_start' : ((0, 16), PackInt, UnpackInt),
  'key_idx'     : ((0, 16), PackInt, UnpackInt),
  'val'         : ((0, 16, 0, True, False), PackStr, UnpackStr),
  'key'         : ((0, 16, 0, True, False), PackStr, UnpackStr),
}

alt_packing_instructions = {
  'opcode'      : ((0,  8), PackInt, UnpackInt),
  'index'       : ((0, 16), PackInt, UnpackInt),
  'index_start' : ((0, 16), PackInt, UnpackInt),
  'key_idx'     : ((0, 16), PackInt, UnpackInt),
  'val'         : ((0, 15, 0, False, True), PackStr, UnpackStr),
  'key'         : ((0, 15, 0, False, True), PackStr, UnpackStr),
}

#alt_packing_instructions = {
#  'opcode'      : ((0,  3), PackInt, UnpackInt),
#  'index'       : ((0, 12), PackInt, UnpackInt),
#  'index_start' : ((0, 12), PackInt, UnpackInt),
#  'key_idx'     : ((0, 12), PackInt, UnpackInt),
#  'val'         : ((0, 15, 0, False, True), PackStr, UnpackStr),
#  'key'         : ((0, 15, 0, False, True), PackStr, UnpackStr),
#}
#alt_packing_instructions = {
#  'opcode'      : ((0,  3), PackInt, UnpackInt),
#  'index'       : ((0, 12), PackInt, UnpackInt),
#  'index_start' : ((0, 12), PackInt, UnpackInt),
#  'key_idx'     : ((0, 12), PackInt, UnpackInt),
#  'val'         : ((0, 0, 0, True, True), PackStr, UnpackStr),
#  'key'         : ((0, 0, 0, True, True), PackStr, UnpackStr),
#}

def PackOps(data, packing_instructions, ops, huff):
  #print "==============  PACKOPS"
  for op in ops:
    #print
    #print FormatOp(op)
    fb = 0
    tb = []
    for field_name in packing_order:
      if not field_name in op:
        continue
      (params, pack_fn, _) = packing_instructions[field_name]
      val = op[field_name]

      if field_name == 'opcode':
        val = OpcodeToVal(op[field_name])
        pack_fn(data, params, val, huff)
        #pack_fn(data, (0,5) , 0, huff)
      else:
        pack_fn(data, params, val, huff)
  (params, pack_fn, _) = packing_instructions['opcode']
  pack_fn(data, params, 0, huff)
  #print "operations data: "
  #print  data
  #print

def UnpackOps(data, packing_instructions, huff):
  ops = []
  #print "==============UNPACKOPS"
  while not (data[0].AllConsumed() and data[1].AllConsumed() and data[2].AllConsumed()):
    (params, _, unpack_fn) = packing_instructions['opcode']
    opcode = unpack_fn(data, params, huff)
    if opcode == 0:
      break;
    #_ = unpack_fn(data, (0,5), huff)
    op = {}
    #print "'opcode'",
    try:
      op['opcode'] = opcode_to_op[opcode][0]
    except:
      data[0].DebugFormat()
      raise
    #print op['opcode']

    for field_name in opcode_to_op[opcode][1:]:
      if field_name == 'opcode':
        continue
      #print field_name,
      if not field_name in packing_instructions:
        #print field_name, " is not in instructions"
        raise StandardError();
      (params, _, unpack_fn) = packing_instructions[field_name]
      val = unpack_fn(data, params, huff)
      #print val
      op[field_name] = val
    ops.append(op)
    #print FormatOp(op)
    #print
  return ops


packing_order = ['opcode',
                 'index',
                 'index_start',
                 'key_idx',
                 'key',
                 'val',
                 ]

opcodes = {
    'toggl': (0x1, 'index'),
    'clone': (0x2, 'index',                'key_idx', 'val'),
    'kvsto': (0x3, 'index', 'key',                    'val'),
    'trang': (0x4, 'index', 'index_start'),
    'rem'  : (0x5, 'index'),
    'eref' : (0x6,          'key',                    'val'),
    }
opcode_to_op = {}  # ugly, I know :)
for (key, val) in opcodes.iteritems():
  opcode_to_op[val[0]] = [key] + list(val[1:])

def OpcodeToVal(x):
  return opcodes[x][0]

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
    self.stream_groups = defaultdict(list)

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

  def RemoveIndex(self, idx):
    ########
    # this procedure assumes the LRU has already been taken care of.
    ########
    #print "Removing(", idx, ")"
    line = self.index_to_line[idx]
    self.total_storage -= (len(line.k) + len(line.v))
    del self.index_to_line[idx]
    # cleanup hvhash_to_index
    self.kvhash_to_index[line.kvhash].remove(idx)
    if not self.kvhash_to_index[line.kvhash]:
      del self.kvhash_to_index[line.kvhash]
    # cleanup key_to_indices
    self.key_to_indices[line.k].remove(idx)
    if not self.key_to_indices[line.k]:
      del self.key_to_indices[line.k]
    key_to_idx_entry = self.key_to_indices.get(line.k, None)
    # cleanup stream_groups
    groups_to_remove = []
    for (id, v) in self.stream_groups.iteritems():
      self.stream_groups[id][:] = [x for x in self.stream_groups[id] if x !=idx]
      if not self.stream_groups[id]:
        groups_to_remove.append(id)
    for id in groups_to_remove:
      del self.stream_groups[id]

  def MoveToFrontOfLRU(self, index):
    #print "MOveToFront(", index, ")"
    new_lru = [x for x in list(self.lru_of_index) if x != index]
    self.lru_of_index = deque(new_lru)
    self.lru_of_index.append(index)

  def Touch(self, index):
    self.MoveToFrontOfLRU(index)

  def MakeRemovalsIfNecessary(self, stream_group, in_ops):
    #return []
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
    #if indices_removed:
      #print "Removed: ", indices_removed
    return ops

  def OpsToRealOps(self, in_ops):
    data = [BitBucket(), BitBucket(), BitBucket()]
    PackOps(data, alt_packing_instructions, in_ops, self.huffman_table)
    overall  = BitBucket()
    overall.StoreBits(data[0].GetAllBits())
    overall.StoreBits(data[1].GetAllBits())
    overall.StoreBits(data[2].GetAllBits())
    return ListToStr(overall.GetAllBits()[0])

  def RealOpsToOps(self, realops):
    bb = BitBucket()
    bb.StoreBits((StrToList(realops), len(realops)*8))
    return UnpackOps([bb, BitBucket(), BitBucket()], alt_packing_instructions, self.huffman_table)

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
    toggles = []
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
        # the headers don't have this line in 'em, so toggle it off.
        self.ExecuteOp(stream_group, self.MakeToggl(index))
        toggles.append(index)

    for (key, vals) in headers.iteritems():
      splitvals = [vals]
      if key == 'cookie': # treat cookie specially...
        splitvals = [x.lstrip(' ') for x in vals.split(';')]
        splitvals.sort()
      for val in splitvals:
        (index, possible_indices) = self.FindIndex(key, val)
        if index >= 0 and index not in self.stream_groups[stream_group]:
          # we have a key+value that exists in the dictinary already,
          # but isn't yet in the stream group. Toggle it ON.
          self.ExecuteOp(stream_group, self.MakeToggl(index))
          toggles.append(index)
        elif index >= 0 and index in self.stream_groups[stream_group]:
          # this means that something was repeated verbatim.
          # Nah. We don't do that.
          pass
        elif index == -1 and possible_indices:
          # The key exists, but the value is different.
          # Clone the key with a new val.
          op = self.MakeClone(self.GetAnUnusedIndex(),
                              max(possible_indices), val)
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
    toggles.sort()
    #print "toggles: ", toggles
    toggle_ops = []
    prev_index = -2
    for index in toggles:  # these will ALL be Toggl (off) ops..
      if index - prev_index == 1:
        if toggle_ops[-1]['opcode'] == 'trang':
          toggle_ops[-1]['index'] = index
        else:
          toggle_ops[-1]['opcode'] = 'trang'
          toggle_ops[-1]['index_start'] = toggle_ops[-1]['index']
          toggle_ops[-1]['index'] = index
      else:
        toggle_ops.append(self.MakeToggl(index))
      prev_index = index
    for index in self.stream_groups[stream_group]:
      self.Touch(index)
    removal_ops = self.MakeRemovalsIfNecessary(stream_group, ops)
    return toggle_ops + ops + removal_ops

  def RealOpsToOpAndExecute(self, realops, stream_group):
    ops = self.RealOpsToOps(realops)
    self.ExecuteOps(ops, stream_group, {})
    return ops

  def ExecuteOps(self, ops, stream_group, ephemereal_headers={}):
    #print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    if not stream_group in self.stream_groups:
      self.stream_groups[stream_group] = []
    for op in ops:
      self.ExecuteOp(stream_group, op, ephemereal_headers)
    #print "DONE"

  def ExecuteOp(self, stream_group, op, ephemereal_headers={}):
    opcode = op["opcode"]
    #print "Executing: ", FormatOp(op)
    if opcode == 'trang':
      index = op["index"]
      for i in xrange(op['index_start'], op['index']+1):
        if i in self.stream_groups[stream_group]:
          self.stream_groups[stream_group].remove(i)
        else:
          self.stream_groups[stream_group].append(i)
          self.Touch(i)
    elif opcode == 'clone':
      index = op["index"]
      key_idx = op["key_idx"]
      # Clone - copies key and stores new value
      # [modifies both stream-group and header_dict]
      self.UpdateIndexes(index, self.index_to_line[key_idx].k, op["val"])
      self.stream_groups[stream_group].append(index)
    elif opcode == 'toggl':
      index = op["index"]
      # Toggl - toggle visibility
      # [applies to stream-group entry only]
      if index in self.stream_groups[stream_group]:
        self.stream_groups[stream_group].remove(index)
      else:
        self.stream_groups[stream_group].append(index)
        self.Touch(index)
    elif opcode == 'rem':
      index = op["index"]
      for i in xrange(op['index']):
        self.RemoveIndex(self.lru_of_index.popleft())
    elif opcode == 'eref':
      ephemereal_headers[op['key']] = op['val']
    elif opcode == 'kvsto':
      index = op["index"]
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
      try:
        self.Touch(index)
        line = self.index_to_line[index]
      except:
        print index
        print self.index_to_line
        print self.stream_groups[stream_group]
        raise
      if line.k in headers:
        headers[line.k] = headers[line.k] + '\0' + line.v
      else:
        headers[line.k] = line.v
    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', '; ')
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
                                       zlib.DEFLATED, 15)
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
                                       zlib.DEFLATED, 15)
    self.compressor.compress(spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    http1_frame = self.HTTP1HeadersFormat(inp_headers)
    return ((self.compressor.compress(http1_frame) +
             self.compressor.flush(zlib.Z_SYNC_FLUSH)),
             http1_frame)

  def HTTP1HeadersFormat(self, frame):
    return FormatAsHTTP1(frame)

def CompareHeaders(a, b):
  a = dict(a)
  b = dict(b)
  output = []
  if 'cookie' in a:
    splitvals = a['cookie'].split(';')
    a['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  if 'cookie' in b:
    splitvals = b['cookie'].split(';')
    b['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  for (k,v) in a.iteritems():
    if not k in b:
      output.append('key: %s present in only one (A)' % k)
      continue
    if v != b[k]:
      output.append('key: %s has mismatched values:' % k)
      output.append('  -> %s' % v)
      output.append('  -> %s' % b[k])
    del b[k]
  for (k, v) in b:
      output.append('key: %s present in only one (B)' % k)
  return ''.join(output)


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
        print "rq_op: ", FormatOp(op)

      print "\n## response ##\n", rqh[1]
      if options.v >= 4:
        print "response header: ", response
      for op in rs4[6]:
        print "rs_op: ", FormatOp(op)
      print
    message = CompareHeaders(request, rq4[4])
    if message:
      print "Something is wrong with the request."
      if options.v >= 1:
        print message
    message = CompareHeaders(response, rs4[4])
    if message:
      print "Something is wrong with the response."
      if options.v >= 1:
        print message

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

  print spdy4_rq.wf
  print
  print spdy4_rq.wf.length_freaks
  print

  print spdy4_rs.wf
  print
  print spdy4_rs.wf.length_freaks
  print
  #print spdy4_rs.wf

main()
