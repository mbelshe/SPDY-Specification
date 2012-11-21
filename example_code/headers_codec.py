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
from header_freq_tables import request_freq_table
from header_freq_tables import response_freq_table
from huffman import Huffman
from optparse import OptionParser
from spdy_dictionary import spdy_dict
from word_freak import WordFreak

options = {}

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
  bitlen = params
  #print 'AAAAAAAAAAAAAAAAAAAAAAAAA INT(', bitlen, ')'
  #data[idx].DebugFormat()
  raw_data = data.GetBits(bitlen)[0]
  rshift = 0
  if bitlen <=8:
    arg = '%c%c%c%c' % (0,0, 0,raw_data[0])
    rshift = 8 - bitlen
  elif bitlen <=16:
    arg = '%c%c%c%c' % (0,0, raw_data[0], raw_data[1])
    rshift = 16 - bitlen
  elif bitlen <=24:
    arg = '%c%c%c%c' % (0,raw_data[0], raw_data[1], raw_data[2])
    rshift = 24 - bitlen
  else:
    arg = '%c%c%c%c' % (raw_data[0], raw_data[1], raw_data[2], raw_data[3])
    rshift = 32 - bitlen
  retval = (struct.unpack('>L', arg)[0] >> rshift)
  #print FormatAsBits((raw_data, bitlen)), '(', retval, ')'
  #data[idx].DebugFormat(
  #print 'XXXXXXXXXXXXXXXXXXXXXXXXX'
  return retval

def UnpackStr(data, params, huff):
  (bitlen_size, use_eof, len_as_bits) = params
  if not use_eof and not bitlen_size:
    # without either a bitlen size or an EOF, we can't know when the string ends
    # having both is certainly fine, however.
    raise StandardError()
  bitlen = -1
  #print 'AAAAAAAAAAAAAAAAAAAAAAAAA STR'
  if bitlen_size:
    bitlen = UnpackInt(data, bitlen_size, huff)
    if not len_as_bits:
      bitlen *= 8
    #print 'unpack strlen_field: ', bitlen
  #data[data_idx].DebugFormat()
  if huff:
    retval = huff.DecodeFromBB(data, use_eof, bitlen)
  else:
    retval = data.GetBits(bitlen)[0]
  #data.DebugFormat()
  retval = ListToStr(retval)
  #print 'str_decoded: ', retval
  #print 'XXXXXXXXXXXXXXXXXXXXXXXXX'
  return retval

# this assumes the bits are near the LSB, but must be packed to be close to MSB
def PackInt(data, params, val, huff):
  bitlen = params
  if bitlen <= 0 or bitlen > 32 or val  != val & ~(0x1 << bitlen):
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

  #print FormatAsBits((StrToList(tmp_val), bitlen)), ' (', val, ')'
  data.StoreBits( (StrToList(tmp_val), bitlen) )

def PackStr(data, params, val, huff):
  (bitlen_size, use_eof, len_as_bits) = params
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
    formatted_val = (StrToList(val), len(val)*8)
  if bitlen_size and len_as_bits:
    #print 'strlen_field: ', formatted_val[1], ' bits'
    PackInt(data, bitlen_size, formatted_val[1], huff)
  elif bitlen_size:
    #print 'strlen_field: ', formatted_val[1]/8, ' bytes ', '(', formatted_val[1], ' bits)'
    PackInt(data, bitlen_size, formatted_val[1]/8, huff)

  #print FormatAsBits(formatted_val), ' (', repr(val), ')', '(', repr(ListToStr(formatted_val[0])), ')'
  data.StoreBits(formatted_val)


packing_instructions = {
  'opcode'      : (8, PackInt, UnpackInt),
  'index'       : (16, PackInt, UnpackInt),
  'index_start' : (16, PackInt, UnpackInt),
  'key_idx'     : (16, PackInt, UnpackInt),
  'val'         : ((16, True, False), PackStr, UnpackStr),
  'key'         : ((16, True, False), PackStr, UnpackStr),

  #'frame_len'   : ((0, 16), PackInt, UnpackInt),
  #'stream_id'   : ((0, 32), PackInt, UnpackInt),
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

def FormatOps(ops):
  for op in ops:
    print FormatOp(op)


class Spdy4SeDer(object):  # serializer deserializer
  def __init__(self):
    pass

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
    #print 'LENGTHS:',len(toggles),len(ot), len(otr)
    #print "(%r)(%r)(%r)" % (toggles, ot, otr)
    return [ot, otr]

  def OutputOps(self, packing_instructions, huff, data, ops, opcode):
    #print ops
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
    pass

  def WriteOpData(self, data, op, huff):
    for field_name in packing_order:
      if not field_name in op:
        continue
      if field_name == 'opcode':
        continue
      (params, pack_fn, _) = packing_instructions[field_name]
      val = op[field_name]
      pack_fn(data, params, val, huff)
    pass


  def WriteControlFrameStreamId(self, data, stream_id):
    if (stream_id & 0x8000):
      abort()
    data.StoreBits32(0x800 | stream_id)

  def WriteControlFrameBoilerplate(self,
      data,
      frame_len,
      flags,
      stream_id,
      frame_type):
    data.StoreBits16(frame_len)
    data.StoreBits8(flags)
    data.StoreBits32(stream_id)
    #self.WriteControlFrameStreamId(data, stream_id)
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
      #print 'paylaod_len: ', payload_len
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
      frame_len = bb.GetBits16()
      #print 'frame_len: ', frame_len
      flags = bb.GetBits8()
      #print 'flags: ', flags
      stream_id = bb.GetBits32()
      #print 'stream_id: ', stream_id
      frame_type = bb.GetBits8()
      #print 'frame_type: ', frame_type
      while frame_len:
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
          #print op
          ops.append(op)
        bits_consumed = (bits_remaining_at_start - bb.BitsRemaining())
        if not bits_consumed % 8 == 0:
          print "somehow didn't consume whole bytes..."
          raise StandardError()
        frame_len -= bits_consumed / 8
    #print 'ops: ', ops
    return ops


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
    pass

  def PopOne(self):  ####
    if not self.lru:
      return
    if self.lru[0] is None:
      # hit the pin.
      return
    ve = self.lru[0]
    if self.remove_val_cb:
      self.remove_val_cb(ve['lru_idx'])
    self.RemoveVal(ve)
    pass

  def MakeSpace(self, space_required, adding_val):  ####
    while self.num_vals + adding_val > self.max_vals:
      if not self.PopOne():
        return
    while self.state_size + space_required > self.max_state_size:
      if not PopOne():
        return
    pass

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
    #print ' InsertVal (%s, %s)' % (key, val)
    ke = self.FindOrAddKey(key)
    if ke['val_map'].get(val, None) is not None:
      print "Hmm. This (%s) shouldn't have existed already" % val
      raise StandardError()
    #print "InsertVal: ke: ", repr(ke)
    self.IncrementRefCnt(ke)
    self.MakeSpace(len(val), 1)
    self.num_vals += 1
    ke['val_map'][val] = ve = self.NewVE(key, val, ke)
    #print "InsertVal: ve: ", ve['lru_idx'], ve['key'], ve['val']
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
    self.RemoveFromLRU(ve)
    ve['lru_idx'] = self.lru_ids.GetNext()
    self.lru.append(ve)

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

    self.generation = 1
    def RemoveIndexFromAllHeaderGroups(x):
      for k,hg in self.header_groups.iteritems():
        if x in hg:
          del hg[x]
    self.storage.SetRemoveValCB(RemoveIndexFromAllHeaderGroups)

    default_dict = {
        ':host': '',
        ':method': 'get',
        ':path': '/',
        ':scheme': 'https',
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
        'cookie': '',
        'date': '',
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
        # Common stuff not in the HTTP spec.
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

  def DiscoverTurnOffs(self, group_id, instructions):
    header_group = self.FindOrMakeHeaderGroup(group_id)
    nhg = {}
    toggles_off = []
    for k,v in header_group.iteritems():
      if v == self.generation:
        nhg[k] = v
      else:
        toggles_off.append(self.MakeToggl(k))
    self.header_groups[group_id] = nhg
    return toggles_off

  def ExecuteInstructionsExceptERefs(self, header_group, instructions):
    for op in instructions['toggl']:
      self.ExecuteOp(header_group, op)
    for op in instructions['clone']:
      self.ExecuteOp(header_group, op)
    for op in instructions['kvsto']:
      self.ExecuteOp(header_group, op)
    pass

  def TouchHeaderGroupEntry(self, header_group, index):
    #print "THGE: ", header_group, index
    header_group[index] = self.generation
    pass

  def ProcessKV(self, key, val, header_group, instructions):
    ke = self.storage.FindKeyEntry(key)
    ve = self.storage.FindValEntry(ke, val)
    if ve is not None:
      lru_idx = ve['lru_idx']
      if lru_idx is not None:
        if not lru_idx in header_group:
          instructions['toggl'].append(self.MakeToggl(lru_idx))
        else:
          self.TouchHeaderGroupEntry(header_group, lru_idx)
    elif ke is not None:
      key_idx = ke['key_idx']
      instructions['clone'].append(self.MakeClone(key_idx, val))
    else:
      instructions['kvsto'].append(self.MakeKvsto(key, val))
    pass

  def FindOrMakeHeaderGroup(self, group_id):
    if group_id in self.header_groups:
      return self.header_groups[group_id]
    self.header_groups[group_id] = {}
    return self.header_groups[group_id]

  def MakeOperations(self, headers, group_id):
    instructions = {'toggl': [], 'clone': [], 'kvsto': [], 'eref': []}
    incremented_keys = []
    self.storage.PinLRU()
    header_group = self.FindOrMakeHeaderGroup(group_id)
    for k in headers.keys():
      ke = self.storage.FindKeyEntry(k)
      if ke:
        self.storage.IncrementRefCnt(ke)
        incremented_keys.append(ke)
    for k,v in headers.iteritems():
      if k == 'cookie':
        splitvals = [x.lstrip(' ') for x in v.split(';')]
        splitvals.sort()
        for splitval in splitvals:
          self.ProcessKV(k, splitval, header_group, instructions)
      else:
        self.ProcessKV(k, v, header_group, instructions)

    turn_offs = self.DiscoverTurnOffs(group_id, instructions)
    instructions['toggl'].extend(turn_offs)
    self.ExecuteInstructionsExceptERefs(header_group, instructions)
    for i,_ in header_group.iteritems():
      ve = self.storage.GetVEFromLRUIdx(i)
      print "\tMO:  %d: (%s, %s)" % (i, ve["key"], ve["val"])

    for ke in incremented_keys:
      self.storage.DecrementRefCnt(ke)
    # SerializeInstructions()
    self.storage.UnPinLRU()
    self.generation += 1
    return instructions

  def RealOpsToOpAndExecute(self, realops, group_id):
    ops = self.RealOpsToOps(realops)
    header_group = self.FindOrMakeHeaderGroup(group_id)
    self.ExecuteOps(ops, header_group)
    return ops

  def ExecuteOps(self, ops, header_group, ephemereal_headers=None):
    if ephemereal_headers is None:
      ephemereal_headers = {}
    #print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
    for op in ops:
      self.ExecuteOp(header_group, op, ephemereal_headers)
    #print 'DONE'

  def ExecuteOp(self, header_group, op, ephemereal_headers=None):
    #print 'Executing: ', FormatOp(op)
    if ephemereal_headers is None:
      ephemereal_headers = {}
    opcode = op['opcode']
    if opcode == 'toggl':
      index = op['index']
      # Toggl - toggle visibility
      if index in header_group:
        del header_group[index]
      else:
        self.TouchHeaderGroupEntry(header_group, index)
    elif opcode == 'trang':
      # Trang - toggles visibility for a range of indices
      index = op['index']
      for i in xrange(op['index_start'], op['index']+1):
        if i in header_group:
          ve = self.storage.GetVEFromLRUIdx(i)
          #print "removing ", i," from header_group (%s %s)" % (ve["key"], ve["val"])
          del header_group[i]
        else:
          #print "  adding %d into header_group" % i
          self.TouchHeaderGroupEntry(header_group, index)
    elif opcode == 'clone':
      key_idx = op['key_idx']
      # Clone - copies key and stores new value
      ke = self.storage.FindKeyByKeyIdx(key_idx)
      if ke is None:
        raise StandardError()
      ve = self.storage.InsertVal(ke['key'], op['val'])
      if header_group is not None:
        self.storage.AddToHeadOfLRU(ve)
        self.TouchHeaderGroupEntry(header_group, ve['lru_idx'])
      else:
        self.TouchHeaderGroupEntry(header_group, ve['lru_idx'])
    elif opcode == 'kvsto':
      # kvsto - store key,value
      ve = self.storage.InsertVal(op['key'], op['val'])
      if header_group is not None:
        self.storage.AddToHeadOfLRU(ve)
        self.TouchHeaderGroupEntry(header_group, ve['lru_idx'])
    elif opcode == 'eref':
      ephemereal_headers[op['key']] = op['val']

  def GetDictSize(self):
    return self.total_storage

  def GenerateAllHeaders(self, group_id):
    headers = {}
    header_group = self.header_groups[group_id]
    for i,_ in header_group.iteritems():
      ve = self.storage.GetVEFromLRUIdx(i)
      print "\tGAE: %d: (%s, %s)" % (i, ve["key"], ve["val"])
    for index,_ in header_group.iteritems():
      ve = self.storage.GetVEFromLRUIdx(index)
      if ve is None:
        print header_group
        print "index: ", index
        print ve
        print self.storage.lru_idx_to_ve.keys()
        raise StandardError()
      key = ve['key']
      val = ve['val']
      if key in headers:
        headers[key] = headers[key] + '\0' + val
      else:
        headers[key] = val
    if 'cookie' in headers:
      headers['cookie'] = headers['cookie'].replace('\0', '; ')
    return headers

