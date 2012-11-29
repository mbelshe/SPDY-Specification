#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string
import struct

from bit_bucket import BitBucket
from collections import defaultdict
from collections import deque
from common_utils import *
from huffman import Huffman
from optparse import OptionParser
from spdy_dictionary import spdy_dict
from word_freak import WordFreak

options = {}

# Performance is a non-goal for this code.

# TODO:try var-int encoding for indices, or use huffman-coding on the indices
# TODO:use a separate huffman encoding for cookies, and possibly for path
# TODO:interpret cookies as binary instead of base-64, does it reduce entropy?
# TODO:make index renumbering useful so things which are often used together
#      have near indices, or remove it as not worth the cost/complexity
# TODO:use other mechanisms other than LRU to perform entry expiry
# TODO:use canonical huffman codes, like the c++ version
# TODO:use huffman coding on the operation type. Clones and toggles are by far
#      the most common operations.
# TODO:use huffman coding on the operation count. Small counts are far more
#      common than large counts. Alternatively, simply use a smaller fixed-size.
# TODO:modify the huffman-coding to always emit a code starting with 1 so that
#      we can differentiate easily between strings that are huffman encoded or
#      strings which are not huffman encoded by examining the first bit.
#      Alternately, define different opcodes for the various variations.

# Note: Huffman coding is used here instead of range-coding or
# arithmetic-coding because of its relative CPU efficiency and because it is
# fairly well known (though the canonical huffman code is a bit less well
# known, it is still better known than most other codings)


###### BEGIN IMPORTANT PARAMS ######
#  THESE PARAMETERS ARE IMPORTANT

# If strings_use_eof is true, then the bitlen is not necessary, and possibly
#  detrimental, as it caps the maximum length of any particular string.
string_length_field_bitlen = 0

# If strings_use_eof is false, however, then string_length_field_bitlen
#  MUST be >0
strings_use_eof = 1

# If strings_padded_to_byte_boundary is true, then it is potentially faster
# (in an optimized implementation) to decode/encode, at the expense of some
# compression efficiency.
strings_padded_to_byte_boundary = 1

# if strings_use_huffman is false, then strings will not be encoded with
# huffman encoding
strings_use_huffman = 1

###### END IMPORTANT PARAMS ######


def UnpackInt(input, bitlen, huff):
  """
  Reads an int from an input BitBucket and returns it.

  'bitlen' is between 1 and 32 (inclusive), and represents the number of bits
  to be read and interpreted as the int.

  'huff' is unused.
  """
  raw_input = input.GetBits(bitlen)[0]
  rshift = 0
  if bitlen <=8:
    arg = '%c%c%c%c' % (0,0, 0,raw_input[0])
    rshift = 8 - bitlen
  elif bitlen <=16:
    arg = '%c%c%c%c' % (0,0, raw_input[0], raw_input[1])
    rshift = 16 - bitlen
  elif bitlen <=24:
    arg = '%c%c%c%c' % (0,raw_input[0], raw_input[1], raw_input[2])
    rshift = 24 - bitlen
  else:
    arg = '%c%c%c%c' % (raw_input[0], raw_input[1], raw_input[2], raw_input[3])
    rshift = 32 - bitlen
  retval = (struct.unpack('>L', arg)[0] >> rshift)
  return retval

def UnpackStr(input, params, huff):
  """
  Reads a string from an input BitBucket and returns it.

  'input' is a BitBucket containing the data to be interpreted as a string.

  'params' is (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman)

  'bitlen_size' indicates the size of the length field. A size of 0 is valid IFF
  'use_eof' is true.

  'use_eof' indicates that an EOF character will be used (for ascii strings,
  this will be a null. For huffman-encoded strings, this will be the specific
  to that huffman encoding).

  If 'pad_to_byte_boundary' is true, then the 'bitlen_size' parameter
  represents bits of size, else 'bitlen_size' represents bytes.


  if 'use_huffman' is false, then the string is not huffman-encoded.

  If 'huff' is None, then the string is not huffman-encoded. If 'huff' is not
  None, then it must be a Huffman compatible object which is used to do huffman
  decoding.
  """
  (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman) = params
  if not use_huffman:
    huff = None
  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  if bitlen_size:
    bitlen = UnpackInt(input, bitlen_size, huff)
    if huff:
      retval = huff.DecodeFromBB(input, use_eof, bitlen)
    else:
      retval = input.GetBits(bitlen)[0]
  else:  # bitlen_size == 0
    if huff:
      retval = huff.DecodeFromBB(input, use_eof, 0)
    else:
      retval = []
      while True:
        c = input.GetBits8()
        retval.append(c)
        if c == 0:
          break
  if pad_to_byte_boundary:
    input.AdvanceToByteBoundary()
  retval = ListToStr(retval)
  return retval

# this assumes the bits are near the LSB, but must be packed to be close to MSB
def PackInt(data, bitlen, val, huff):
  if bitlen <= 0 or bitlen > 32 or val != (val & ~(0x1 << bitlen)):
    print 'bitlen: ', bitlen, ' val: ', val
    raise StandardError()
  if bitlen <= 8:
    tmp_val = struct.pack('>B', val << (8 - bitlen))
  elif bitlen <= 16:
    tmp_val = struct.pack('>H', val << (16 - bitlen))
  elif bitlen <= 24:
    tmp_val = struct.pack('>L', val << (24 - bitlen))[1:]
  else:
    tmp_val = struct.pack('>L', val << (32 - bitlen))
  data.StoreBits( (StrToList(tmp_val), bitlen) )

def PackStr(data, params, val, huff):
  (bitlen_size, use_eof, pad_to_byte_boundary, use_huffman) = params
  # if eof, then don't technically need bitlen at all...
  if not use_huffman:
    huff = None

  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  val_as_list = StrToList(val)
  len_in_bits = len(val) * 8
  if huff:
    (val_as_list, len_in_bits) = huff.Encode(val_as_list, use_eof)
    if pad_to_byte_boundary:
      len_in_bits = len(val_as_list) *8
  if bitlen_size:
    PackInt(data, bitlen_size, len_in_bits, huff)
  data.StoreBits( (val_as_list, len_in_bits) )


str_pack_params = (string_length_field_bitlen, strings_use_eof,
                   strings_padded_to_byte_boundary, strings_use_huffman)
packing_instructions = {
  'opcode'      : (  8,             PackInt, UnpackInt),
  'index'       : ( 16,             PackInt, UnpackInt),
  'index_start' : ( 16,             PackInt, UnpackInt),
  'key_idx'     : ( 16,             PackInt, UnpackInt),
  'val'         : (str_pack_params, PackStr, UnpackStr),
  'key'         : (str_pack_params, PackStr, UnpackStr),
}

def PackOps(data, packing_instructions, ops, huff):
  seder = Spdy4SeDer()
  data.StoreBits(seder.SerializeInstructions(ops, packing_instructions,
                                             huff, 1234, True))

def UnpackOps(data, packing_instructions, huff):
  seder = Spdy4SeDer()
  return seder.DeserializeInstructions(data, packing_instructions, huff)

packing_order = ['opcode',
                 'index',
                 'index_start',
                 'key_idx',
                 'key',
                 'val',
                 ]

opcodes = {
    'toggl': (0x1, 'index'),
    'trang': (0x2, 'index', 'index_start'),
    'clone': (0x3,                         'key_idx', 'val'),
    'kvsto': (0x4,          'key',                    'val'),
    'eref' : (0x5,          'key',                    'val'),
    }

opcode_to_op = {}
for (key, val) in opcodes.iteritems():
  opcode_to_op[val[0]] = [key] + list(val[1:])

def OpcodeToVal(x):
  return opcodes[x][0]

def FormatOp(op):
  order = packing_order
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key != 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key])))
    if key in op and key == 'opcode':
      inp.append("'%s': % 5s" % (key, repr(op[key]).ljust(7)))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': %s" % (key, repr(op[key])))
  outp.append(', '.join(inp))
  outp.append('}')
  return ''.join(outp)

def FormatOps(ops, prefix=None):
  if prefix is None:
    prefix = ''
  if isinstance(ops, list):
    for op in ops:
      print prefix,
      print FormatOp(op)
    return
  for optype in ops.iterkeys():
    for op in ops[optype]:
      print prefix,
      print FormatOp(op)


class Spdy4SeDer(object):  # serializer deserializer
  def PreProcessToggles(self, instructions):
    toggles = instructions['toggl']
    toggles.sort()
    ot = []
    otr = []
    for toggle in toggles:
      idx = toggle['index']
      if otr and idx - otr[-1]['index'] == 1:
        otr[-1]['index'] = idx
      elif ot and idx - ot[-1]['index'] == 1:
        otr.append(ot.pop())
        otr[-1]['index_start'] = otr[-1]['index']
        otr[-1]['index'] = idx
        otr[-1]['opcode'] = 'trang'
      else:
        ot.append(toggle)
    return [ot, otr]

  def OutputOps(self, packing_instructions, huff, data, ops, opcode):
    if not ops:
      return;
    ops_idx = 0
    ops_len = len(ops)
    while ops_len > ops_idx:
      ops_to_go = ops_len - ops_idx
      iteration_end = min(ops_to_go, 256) + ops_idx
      data.StoreBits8(OpcodeToVal(opcode))
      data.StoreBits8(min(256, ops_to_go) - 1)
      orig_idx = ops_idx
      for i in xrange(ops_to_go):
        self.WriteOpData(data, ops[orig_idx + i], huff)
        ops_idx += 1


  def WriteOpData(self, data, op, huff):
    for field_name in packing_order:
      if not field_name in op:
        continue
      if field_name == 'opcode':
        continue
      (params, pack_fn, _) = packing_instructions[field_name]
      val = op[field_name]
      pack_fn(data, params, val, huff)

  def WriteControlFrameStreamId(self, data, stream_id):
    if (stream_id & 0x80000000):
      abort()
    data.StoreBits32(0x80000000 | stream_id)

  def WriteControlFrameBoilerplate(self,
      data,
      frame_len,
      flags,
      stream_id,
      frame_type):
    data.StoreBits16(frame_len)
    data.StoreBits8(flags)
    #data.StoreBits32(stream_id)
    self.WriteControlFrameStreamId(data, stream_id)
    data.StoreBits8(frame_type)

  def SerializeInstructions(self,
      ops,
      packing_instructions,
      huff,
      stream_id,
      end_of_frame):
    #print 'SerializeInstructions\n', ops
    (ot, otr) = self.PreProcessToggles(ops)

    payload_bb = BitBucket()
    self.OutputOps(packing_instructions, huff, payload_bb, ot, 'toggl')
    self.OutputOps(packing_instructions, huff, payload_bb, otr, 'trang')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['clone'],'clone')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['kvsto'],'kvsto')
    self.OutputOps(packing_instructions, huff, payload_bb, ops['eref'], 'eref')

    (payload, payload_len) = payload_bb.GetAllBits()
    payload_len = (payload_len + 7) / 8  # partial bytes are counted as full
    frame_bb = BitBucket()
    self.WriteControlFrameBoilerplate(frame_bb, 0, 0, 0, 0)
    boilerplate_length = frame_bb.BytesOfStorage()
    frame_bb = BitBucket()
    overall_bb = BitBucket()
    bytes_allowed = 2**16 - boilerplate_length
    while True:
      #print 'payload_len: ', payload_len
      bytes_to_consume = min(payload_len, bytes_allowed)
      #print 'bytes_to_consume: ', bytes_to_consume
      end_of_frame = (bytes_to_consume <= payload_len)
      #print 'end_of_Frame: ', end_of_frame
      self.WriteControlFrameBoilerplate(overall_bb, bytes_to_consume,
                                        end_of_frame, stream_id, 0x8)
      overall_bb.StoreBits( (payload, bytes_to_consume*8))
      payload = payload[bytes_to_consume:]
      payload_len -= bytes_allowed
      if payload_len <= 0:
        break
    return overall_bb.GetAllBits()

  def DeserializeInstructions(self, frame, packing_instructions, huff):
    ops = []
    bb = BitBucket()
    bb.StoreBits(frame.GetAllBits())
    flags = 0
    #print 'DeserializeInstructions'
    while flags == 0:
      frame_len = bb.GetBits16() * 8
      #print 'frame_len: ', frame_len
      flags = bb.GetBits8()
      #print 'flags: ', flags
      stream_id = bb.GetBits32()
      #print 'stream_id: ', stream_id
      frame_type = bb.GetBits8()
      #print 'frame_type: ', frame_type
      while frame_len > 16:  # 16 bits minimum for the opcode + count...
        bits_remaining_at_start = bb.BitsRemaining()
        opcode_val = bb.GetBits8()
        #print 'opcode_val: ', opcode_val
        op_count = bb.GetBits8() + 1
        #print 'op_count: ', op_count
        opcode_description = opcode_to_op[opcode_val]
        opcode = opcode_description[0]
        fields = opcode_description[1:]
        for i in xrange(op_count):
          op = {'opcode': opcode}
          for field_name in packing_order:
            if not field_name in fields:
              continue
            (params, _, unpack_fn) = packing_instructions[field_name]
            val = unpack_fn(bb, params, huff)
            #print val
            op[field_name] = val
            #print "BitsRemaining: %d (%d)" % (bb.BitsRemaining(), bb.BitsRemaining() % 8)
          #print "Deser %d" % (bb.NumBits() - bb.BitsRemaining())
          #print op
          ops.append(op)
        bits_consumed = (bits_remaining_at_start - bb.BitsRemaining())
        #if not bits_consumed % 8 == 0:
        #  print "somehow didn't consume whole bytes..."
        #  print "Bits consumed: %d (%d)" % (bits_consumed, bits_consumed % 8)
        #  raise StandardError()
        frame_len -= bits_consumed
    #print 'ops: ', ops
    return ops

class HeaderGroup(object):
  def __init__(self):
    self.storage = dict()
    self.generation = 0

  def Empty(self):
    return not self.storage

  def IncrementGeneration(self):
    self.generation += 1

  def HasEntry(self, ve):
    retval = id(ve) in self.storage
    #if retval:
    #  print "Has Entry for %s: %s" % (ve['key'], ve['val'])
    #else:
    #  print " NO Entry for %s: %s" % (ve['key'], ve['val'])
    return retval

  def TouchEntry(self, ve):
    #print "TE:touched: %s: %s (%d)" % (ve['key'], ve['val'], self.generation)
    self.storage[id(ve)] = (ve, self.generation)

  def AddEntry(self, ve):
    if id(ve) in self.storage:
      raise StandardError()
    self.storage[id(ve)] = (ve, self.generation)
    #print "AE:  added: %s: %s (%d)", (ve['key'], ve['val'], self.generation)

  def RemoveEntry(self, ve):
    try:
      del self.storage[id(ve)]
    except KeyError:
      pass

  def FindOldEntries(self):
    def NotCurrent(x):
      return x != self.generation
    retval = [e for he,(e,g) in self.storage.iteritems() if NotCurrent(g)]
    return retval

  def GetEntries(self):
    return [e for he,(e, g) in self.storage.iteritems()]

  def Toggle(self, ve):
    try:
      #g = self.storage[id(ve)][1]
      del self.storage[id(ve)]
      #print "TG: removed: %s: %s (%d)" % (ve['key'], ve['val'], g)
    except KeyError:
      if id(ve) in self.storage:
        raise StandardError()
      self.storage[id(ve)] = (ve, self.generation)
      #print "TG:  added: %s: %s (%d)" % (ve['key'], ve['val'], self.generation)

class IDStore(object):
  def __init__(self):
    self.ids = set()
    self.next_idx = 0

  def GetNext(self):
    if self.ids:
      return self.ids.pop()
    self.next_idx += 1
    return self.next_idx

  def DoneWithId(self, id):
    self.ids.add(id)


class Storage(object):
  def __init__(self):  ####
    self.key_map = {}
    self.key_ids = IDStore()
    self.lru_ids = IDStore()
    self.state_size = 0
    self.num_vals = 0
    self.max_vals = 1024
    self.max_state_size = 64*1024
    self.pinned = None
    self.remove_val_cb = None
    self.lru = deque()
    self.lru_idx_to_ve = {}
    self.key_idx_to_ke = {}

  def PopOne(self):  ####
    if not self.lru:
      return
    if self.lru[0] is None:
      # hit the pin.
      return
    ve = self.lru[0]
    if self.remove_val_cb:
      self.remove_val_cb(ve)
    self.RemoveVal(ve)

  def MakeSpace(self, space_required, adding_val):  ####
    while self.num_vals + adding_val > self.max_vals:
      if not self.PopOne():
        return
    while self.state_size + space_required > self.max_state_size:
      if not PopOne():
        return

  def FindKeyEntry(self, key): ####
    if key in self.key_map:
      return self.key_map[key]
    return None

  def FindKeyIdxByKey(self, key): ####
    ke = self.FindKeyEntry(key)
    if ke:
      return ke['key_idx']
    return -1

  def FindKeyByKeyIdx(self, key_idx):
    return self.key_idx_to_ke.get(key_idx, None)

  def IncrementRefCnt(self, ke): ####
    ke['ref_cnt'] += 1

  def DecrementRefCnt(self, ke): ####
    ke['ref_cnt'] -= 1

  def NewKE(self, key): ####
    return {'key_idx': self.key_ids.GetNext(),
            'ref_cnt': 0,
            'val_map': {},
            'key': key,
            }

  def NewVE(self, key, val, ke):  ####
    return {'lru_idx': None,
            'key': key,
            'val': val,
            'ke': ke,
            }

  def FindOrAddKey(self, key): ####
    ke = self.FindKeyEntry(key)
    if ke:
      return ke
    self.MakeSpace(len(key), 0)
    self.key_map[key] = ke = self.NewKE(key)
    key_idx = ke['key_idx']
    if key_idx in self.key_idx_to_ke:
      raise StandardError()
    self.key_idx_to_ke[key_idx] = ke
    self.state_size += len(key)
    return ke

  def InsertVal(self, key, val): ####
    ke = self.FindOrAddKey(key)
    if ke['val_map'].get(val, None) is not None:
      print "Hmm. This (%s) shouldn't have existed already" % val
      raise StandardError()
    self.IncrementRefCnt(ke)
    self.MakeSpace(len(val), 1)
    self.num_vals += 1
    ke['val_map'][val] = ve = self.NewVE(key, val, ke)
    self.DecrementRefCnt(ke)
    return ve

  def AddToHeadOfLRU(self, ve): ####
    if ve['lru_idx'] >= 0:
      raise StandardError()
    if ve is not None:
      lru_idx = self.lru_ids.GetNext()
      ve['lru_idx'] = lru_idx
      self.lru_idx_to_ve[lru_idx] = ve
      self.lru.append(ve)

  def GetVEFromLRUIdx(self, lru_idx):
    return self.lru_idx_to_ve.get(lru_idx, None)

  def MoveToHeadOfLRU(self, ve):  ####
    try:
      self.lru.remove(ve)
      self.lru.append(ve)
    except:
      pass

  def RemoveFromLRU(self, ve): ####
    # print "removing from LRU: (%r,%r, %d)" % (ve['key'], ve['val'], ve['lru_idx'])
    self.lru.remove(ve)
    lru_idx = ve['lru_idx']
    del self.lru_idx_to_ve[lru_idx]
    ve['lru_idx'] = None

  def RemoveFromValMap(self, ve): ####
    self.state_size -= len(ve['val'])
    self.num_vals -= 1
    del ve['ke']['val_map'][ve['val']]

  def MaybeRemoveFromKeyMap(self, ke): ####
    if not ke or len(ke['val_map']) > 0 or ke['ref_cnt'] > 0:
      return
    self.state_size -= len(ke['key'])

  def RemoveVal(self, ve): ####
    self.RemoveFromLRU(ve)
    self.RemoveFromValMap(ve)
    self.MaybeRemoveFromKeyMap(ve['ke'])

  def SetRemoveValCB(self, cb): ####
    self.remove_val_cb = cb

  def FindValEntry(self, ke, val): ####
    if ke is None:
      return None
    return ke['val_map'].get(val, None)

  def PinLRU(self):
    if self.pinned:
      raise StandardError()
    self.pinned = True
    self.lru.append(None)

  def UnPinLRU(self):
    if not self.pinned:
      raise StandardError()
    self.pinned = False
    self.lru = deque([x for x in self.lru if x is not None])


class Spdy4CoDe(object):
  def __init__(self):
    self.header_groups = {}
    self.huffman_table = None
    self.wf = WordFreak()
    self.storage = Storage()
    def RemoveVEFromAllHeaderGroups(ve):
      to_be_removed = []
      for group_id, header_group in self.header_groups.iteritems():
        #print "Removing %d from hg %d" % (ve['lru_idx'], group_id)
        header_group.RemoveEntry(ve)
        if header_group.Empty():
          to_be_removed.append(group_id)
      for group_id in to_be_removed:
        #print "Deleted group_id: %d" % group_id
        del header_group[group_id]

    self.storage.SetRemoveValCB(RemoveVEFromAllHeaderGroups)

    default_dict = {
        ':scheme': 'https',
        ':method': 'get',

        'date': '',
        ':host': '',
        ':path': '/',
        'cookie': '',

        ':status': '200',
        ':status-text': 'OK',
        ':version': '1.1',
        'accept': '',
        'accept-charset': '',
        'accept-encoding': '',
        'accept-language': '',
        'accept-ranges': '',
        'allow': '',
        'authorizations': '',
        'cache-control': '',
        'content-base': '',
        'content-encoding': '',
        'content-length': '',
        'content-location': '',
        'content-md5': '',
        'content-range': '',
        'content-type': '',
        'etag': '',
        'expect': '',
        'expires': '',
        'from': '',
        'if-match': '',
        'if-modified-since': '',
        'if-none-match': '',
        'if-range': '',
        'if-unmodified-since': '',
        'last-modified': '',
        'location': '',
        'max-forwards': '',
        'origin': '',
        'pragma': '',
        'proxy-authenticate': '',
        'proxy-authorization': '',
        'range': '',
        'referer': '',
        'retry-after': '',
        'server': '',
        'set-cookie': '',
        'status': '',
        'te': '',
        'trailer': '',
        'transfer-encoding': '',
        'upgrade': '',
        'user-agent': '',
        'user-agent': '',
        'vary': '',
        'via': '',
        'warning': '',
        'www-authenticate': '',
        'access-control-allow-origin': '',
        'content-disposition': '',
        'get-dictionary': '',
        'p3p': '',
        'x-content-type-options': '',
        'x-frame-options': '',
        'x-powered-by': '',
        'x-xss-protection': '',
        }
    for (k, v) in default_dict.iteritems():
      self.ExecuteOp(None, self.MakeKvsto(k, v))
      ke = self.storage.FindKeyEntry(k)
      ve = self.storage.FindValEntry(ke, v)
      ve['lru_idx'] = lru_idx = self.storage.lru_ids.GetNext()
      self.storage.lru_idx_to_ve[lru_idx] = ve

  def OpsToRealOps(self, in_ops):
    data = BitBucket()
    PackOps(data, packing_instructions, in_ops, self.huffman_table)
    return ListToStr(data.GetAllBits()[0])

  def RealOpsToOps(self, realops):
    bb = BitBucket()
    bb.StoreBits((StrToList(realops), len(realops)*8))
    return UnpackOps(bb, packing_instructions, self.huffman_table)

  def Compress(self, realops):
    ba = ''.join(realops)
    return ba

  def Decompress(self, op_blob):
    return op_blob
    return self.decompressor.decompress(op_blob)

  def MakeToggl(self, index):
    return {'opcode': 'toggl', 'index': index}

  def MakeKvsto(self, key, val):
    return {'opcode': 'kvsto', 'val': val, 'key': key}

  def MakeClone(self, key_idx, val):
    return {'opcode': 'clone', 'val': val, 'key_idx': key_idx}

  def MakeERef(self, key, value):
    return {'opcode': 'eref', 'key': key, 'val': value}

  def FindOrMakeHeaderGroup(self, group_id):
    try:
      return self.header_groups[group_id]
    except KeyError:
      self.header_groups[group_id] = HeaderGroup()
      return self.header_groups[group_id]

  def TouchHeaderGroupEntry(self, group_id, ve):
    self.header_groups[group_id].TouchEntry(ve)

  def VEInHeaderGroup(self, group_id, ve):
    return self.header_groups[group_id].HasEntry(ve)

  def IdxToVE(self, idx):
    return self.storage.lru_idx_to_ve[idx]

  def DiscoverTurnOffs(self, group_id, instructions):
    toggles_off = []
    header_group = self.FindOrMakeHeaderGroup(group_id)
    for ve in header_group.FindOldEntries():
      toggles_off.append(self.MakeToggl(ve['lru_idx']))
    return toggles_off

  def RenumberVELruIdx(self, ve):
    lru_idx = ve['lru_idx']
    new_lru_idx = ve['lru_idx'] = self.storage.lru_ids.GetNext()
    del self.storage.lru_idx_to_ve[lru_idx]
    self.storage.lru_idx_to_ve[new_lru_idx] = ve

  def AdjustHeaderGroupEntries(self, group_id):
    header_group = self.header_groups[group_id]
    for ve in sorted(header_group.GetEntries(),key=lambda x: x['lru_idx']):
      self.storage.MoveToHeadOfLRU(ve)
      self.RenumberVELruIdx(ve)

  def ExecuteInstructionsExceptERefs(self, group_id, instructions):
    if 'trang' in instructions:
      raise StandardError()
    for op in instructions['toggl']:
      self.ExecuteOp(group_id, op)
    for op in instructions['clone']:
      self.ExecuteOp(group_id, op)
    for op in instructions['kvsto']:
      self.ExecuteOp(group_id, op)

  def ProcessKV(self, key, val, group_id, instructions):
    ke = self.storage.FindKeyEntry(key)
    ve = self.storage.FindValEntry(ke, val)
    if ve is not None:
      if not self.VEInHeaderGroup(group_id, ve):
        instructions['toggl'].append(self.MakeToggl(ve['lru_idx']))
      else:
        self.TouchHeaderGroupEntry(group_id, ve)
    elif ke is not None:
      instructions['clone'].append(self.MakeClone(ke['key_idx'], val))
    else:
      instructions['kvsto'].append(self.MakeKvsto(key, val))

  def MakeOperations(self, headers, group_id):
    instructions = {'toggl': [], 'clone': [], 'kvsto': [], 'eref': []}
    incremented_keys = []
    self.storage.PinLRU()
    self.FindOrMakeHeaderGroup(group_id)  # make the header group if necessary
    for k in headers.iterkeys():
      ke = self.storage.FindKeyEntry(k)
      if ke:
        self.storage.IncrementRefCnt(ke)
        incremented_keys.append(ke)
    for k,v in headers.iteritems():
      if k == 'cookie':
        splitvals = [x.lstrip(' ') for x in v.split(';')]
        splitvals.sort()
        for splitval in splitvals:
          self.ProcessKV(k, splitval, group_id, instructions)
      else:
        self.ProcessKV(k, v, group_id, instructions)

    turn_offs = self.DiscoverTurnOffs(group_id, instructions)
    instructions['toggl'].extend(turn_offs)
    self.ExecuteInstructionsExceptERefs(group_id, instructions)

    for ke in incremented_keys:
      self.storage.DecrementRefCnt(ke)
    # SerializeInstructions()
    self.storage.UnPinLRU()
    self.header_groups[group_id].IncrementGeneration()
    self.AdjustHeaderGroupEntries(group_id)
    #FormatOps(instructions, 'MO\t')
    return instructions

  def RealOpsToOpAndExecute(self, realops, group_id):
    ops = self.RealOpsToOps(realops)
    #FormatOps(ops,'ROTOAE\t')
    self.storage.PinLRU()
    self.ExecuteOps(ops, group_id)
    self.storage.UnPinLRU()
    return ops

  def ExecuteOps(self, ops, group_id, ephemereal_headers=None):
    self.FindOrMakeHeaderGroup(group_id)  # make the header group if necessary
    if ephemereal_headers is None:
      ephemereal_headers = {}
    #print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
    for op in ops:
      self.ExecuteOp(group_id, op, ephemereal_headers)
    #print 'DONE'

  def ExecuteToggle(self, group_id, idx):
    self.header_groups[group_id].Toggle(self.IdxToVE(idx))

  def ExecuteOp(self, group_id, op, ephemereal_headers=None):
    #print 'Executing: ', FormatOp(op)
    opcode = op['opcode']
    if opcode == 'toggl':
      # Toggl - toggle visibility
      idx = op['index']
      self.ExecuteToggle(group_id, idx)
    elif opcode == 'trang':
      # Trang - toggles visibility for a range of indices
      for idx in xrange(op['index_start'], op['index']+1):
        self.ExecuteToggle(group_id, idx)
    elif opcode == 'clone':
      key_idx = op['key_idx']
      # Clone - copies key and stores new value
      ke = self.storage.FindKeyByKeyIdx(key_idx)
      if ke is None:
        raise StandardError()
      ve = self.storage.InsertVal(ke['key'], op['val'])
      self.storage.AddToHeadOfLRU(ve)
      self.TouchHeaderGroupEntry(group_id, ve)
    elif opcode == 'kvsto':
      # kvsto - store key,value
      ve = self.storage.InsertVal(op['key'], op['val'])
      if group_id is not None:
        self.storage.AddToHeadOfLRU(ve)
        self.TouchHeaderGroupEntry(group_id, ve)
    elif opcode == 'eref' and ephemereal_headers is not None:
      ephemereal_headers[op['key']] = op['val']

  def GetDictSize(self):
    return self.total_storage



  def GenerateAllHeaders(self, group_id):
    headers = {}
    header_group = self.header_groups[group_id]

    for ve in sorted(header_group.GetEntries(),key=lambda x: x['lru_idx']):
      key = ve['key']
      val = ve['val']
      if key in headers:
        headers[key] = headers[key] + '\0' + val
      else:
        headers[key] = val
    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', '; ')
    self.AdjustHeaderGroupEntries(group_id)
    return headers

