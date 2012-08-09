#!/usr/bin/python
import zlib
import string
import sys
import array
import struct
import re
from optparse import OptionParser

default_requests = [
  {':method': "get",
    ':path': '/index.html',
    ':version': 'HTTP/1.1',
    'user-agent': 'blah blah browser version blah blah',
    'accept-encoding': 'sdch, bzip, compress',
    ':host': 'www.foo.com',
    'referrer': 'www.foo.com/ILoveBugs',
    'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
    'date': 'Wed Jul 18 11:50:43 2012'},
  {':method': "get",
    ':path': '/index.js',
    ':version': 'HTTP/1.1',
    'user-agent': 'blah blah browser version blah blah',
    'accept-encoding': 'sdch, bzip, compress',
    ':host': 'www.foo.com',
    'referrer': 'www.foo.com/ILoveBugsALot',
    'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
    'date': 'Wed Jul 18 11:50:44 2012'},
  {':method': "get",
    ':path': '/index.css',
    ':version': 'HTTP/1.1',
    'user-agent': 'blah blah',
    'accept-encoding': 'sdch, bzip, compress',
    ':host': 'www.foo.com',
    'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;FOOBLA',
    'date': 'Wed Jul 18 11:50:45 2012'},
  {':method': "get",
    ':path': '/generate_foo.html',
    ':version': 'HTTP/1.1',
    ':host': 'www.foo.com',
    'date': 'Wed Jul 18 11:50:45 2012'},
  {':method': "get",
    ':path': '/index.css',
    ':version': 'HTTP/1.1',
    'user-agent': 'blah blah browser version blah blah',
    'accept-encoding': 'sdch, bzip, compress',
    ':host': 'www.foo.com',
    'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
    'date': 'Wed Jul 18 11:50:46 2012'},
  ]

def ListToStr(val):
  return ''.join(["%c" % c for c in val])

spdy_dictionary = ListToStr([
        0x00, 0x00, 0x00, 0x07, 0x6f, 0x70, 0x74, 0x69,   # - - - - o p t i
        0x6f, 0x6e, 0x73, 0x00, 0x00, 0x00, 0x04, 0x68,   # o n s - - - - h
        0x65, 0x61, 0x64, 0x00, 0x00, 0x00, 0x04, 0x70,   # e a d - - - - p
        0x6f, 0x73, 0x74, 0x00, 0x00, 0x00, 0x03, 0x70,   # o s t - - - - p
        0x75, 0x74, 0x00, 0x00, 0x00, 0x06, 0x64, 0x65,   # u t - - - - d e
        0x6c, 0x65, 0x74, 0x65, 0x00, 0x00, 0x00, 0x05,   # l e t e - - - -
        0x74, 0x72, 0x61, 0x63, 0x65, 0x00, 0x00, 0x00,   # t r a c e - - -
        0x06, 0x61, 0x63, 0x63, 0x65, 0x70, 0x74, 0x00,   # - a c c e p t -
        0x00, 0x00, 0x0e, 0x61, 0x63, 0x63, 0x65, 0x70,   # - - - a c c e p
        0x74, 0x2d, 0x63, 0x68, 0x61, 0x72, 0x73, 0x65,   # t - c h a r s e
        0x74, 0x00, 0x00, 0x00, 0x0f, 0x61, 0x63, 0x63,   # t - - - - a c c
        0x65, 0x70, 0x74, 0x2d, 0x65, 0x6e, 0x63, 0x6f,   # e p t - e n c o
        0x64, 0x69, 0x6e, 0x67, 0x00, 0x00, 0x00, 0x0f,   # d i n g - - - -
        0x61, 0x63, 0x63, 0x65, 0x70, 0x74, 0x2d, 0x6c,   # a c c e p t - l
        0x61, 0x6e, 0x67, 0x75, 0x61, 0x67, 0x65, 0x00,   # a n g u a g e -
        0x00, 0x00, 0x0d, 0x61, 0x63, 0x63, 0x65, 0x70,   # - - - a c c e p
        0x74, 0x2d, 0x72, 0x61, 0x6e, 0x67, 0x65, 0x73,   # t - r a n g e s
        0x00, 0x00, 0x00, 0x03, 0x61, 0x67, 0x65, 0x00,   # - - - - a g e -
        0x00, 0x00, 0x05, 0x61, 0x6c, 0x6c, 0x6f, 0x77,   # - - - a l l o w
        0x00, 0x00, 0x00, 0x0d, 0x61, 0x75, 0x74, 0x68,   # - - - - a u t h
        0x6f, 0x72, 0x69, 0x7a, 0x61, 0x74, 0x69, 0x6f,   # o r i z a t i o
        0x6e, 0x00, 0x00, 0x00, 0x0d, 0x63, 0x61, 0x63,   # n - - - - c a c
        0x68, 0x65, 0x2d, 0x63, 0x6f, 0x6e, 0x74, 0x72,   # h e - c o n t r
        0x6f, 0x6c, 0x00, 0x00, 0x00, 0x0a, 0x63, 0x6f,   # o l - - - - c o
        0x6e, 0x6e, 0x65, 0x63, 0x74, 0x69, 0x6f, 0x6e,   # n n e c t i o n
        0x00, 0x00, 0x00, 0x0c, 0x63, 0x6f, 0x6e, 0x74,   # - - - - c o n t
        0x65, 0x6e, 0x74, 0x2d, 0x62, 0x61, 0x73, 0x65,   # e n t - b a s e
        0x00, 0x00, 0x00, 0x10, 0x63, 0x6f, 0x6e, 0x74,   # - - - - c o n t
        0x65, 0x6e, 0x74, 0x2d, 0x65, 0x6e, 0x63, 0x6f,   # e n t - e n c o
        0x64, 0x69, 0x6e, 0x67, 0x00, 0x00, 0x00, 0x10,   # d i n g - - - -
        0x63, 0x6f, 0x6e, 0x74, 0x65, 0x6e, 0x74, 0x2d,   # c o n t e n t -
        0x6c, 0x61, 0x6e, 0x67, 0x75, 0x61, 0x67, 0x65,   # l a n g u a g e
        0x00, 0x00, 0x00, 0x0e, 0x63, 0x6f, 0x6e, 0x74,   # - - - - c o n t
        0x65, 0x6e, 0x74, 0x2d, 0x6c, 0x65, 0x6e, 0x67,   # e n t - l e n g
        0x74, 0x68, 0x00, 0x00, 0x00, 0x10, 0x63, 0x6f,   # t h - - - - c o
        0x6e, 0x74, 0x65, 0x6e, 0x74, 0x2d, 0x6c, 0x6f,   # n t e n t - l o
        0x63, 0x61, 0x74, 0x69, 0x6f, 0x6e, 0x00, 0x00,   # c a t i o n - -
        0x00, 0x0b, 0x63, 0x6f, 0x6e, 0x74, 0x65, 0x6e,   # - - c o n t e n
        0x74, 0x2d, 0x6d, 0x64, 0x35, 0x00, 0x00, 0x00,   # t - m d 5 - - -
        0x0d, 0x63, 0x6f, 0x6e, 0x74, 0x65, 0x6e, 0x74,   # - c o n t e n t
        0x2d, 0x72, 0x61, 0x6e, 0x67, 0x65, 0x00, 0x00,   # - r a n g e - -
        0x00, 0x0c, 0x63, 0x6f, 0x6e, 0x74, 0x65, 0x6e,   # - - c o n t e n
        0x74, 0x2d, 0x74, 0x79, 0x70, 0x65, 0x00, 0x00,   # t - t y p e - -
        0x00, 0x04, 0x64, 0x61, 0x74, 0x65, 0x00, 0x00,   # - - d a t e - -
        0x00, 0x04, 0x65, 0x74, 0x61, 0x67, 0x00, 0x00,   # - - e t a g - -
        0x00, 0x06, 0x65, 0x78, 0x70, 0x65, 0x63, 0x74,   # - - e x p e c t
        0x00, 0x00, 0x00, 0x07, 0x65, 0x78, 0x70, 0x69,   # - - - - e x p i
        0x72, 0x65, 0x73, 0x00, 0x00, 0x00, 0x04, 0x66,   # r e s - - - - f
        0x72, 0x6f, 0x6d, 0x00, 0x00, 0x00, 0x04, 0x68,   # r o m - - - - h
        0x6f, 0x73, 0x74, 0x00, 0x00, 0x00, 0x08, 0x69,   # o s t - - - - i
        0x66, 0x2d, 0x6d, 0x61, 0x74, 0x63, 0x68, 0x00,   # f - m a t c h -
        0x00, 0x00, 0x11, 0x69, 0x66, 0x2d, 0x6d, 0x6f,   # - - - i f - m o
        0x64, 0x69, 0x66, 0x69, 0x65, 0x64, 0x2d, 0x73,   # d i f i e d - s
        0x69, 0x6e, 0x63, 0x65, 0x00, 0x00, 0x00, 0x0d,   # i n c e - - - -
        0x69, 0x66, 0x2d, 0x6e, 0x6f, 0x6e, 0x65, 0x2d,   # i f - n o n e -
        0x6d, 0x61, 0x74, 0x63, 0x68, 0x00, 0x00, 0x00,   # m a t c h - - -
        0x08, 0x69, 0x66, 0x2d, 0x72, 0x61, 0x6e, 0x67,   # - i f - r a n g
        0x65, 0x00, 0x00, 0x00, 0x13, 0x69, 0x66, 0x2d,   # e - - - - i f -
        0x75, 0x6e, 0x6d, 0x6f, 0x64, 0x69, 0x66, 0x69,   # u n m o d i f i
        0x65, 0x64, 0x2d, 0x73, 0x69, 0x6e, 0x63, 0x65,   # e d - s i n c e
        0x00, 0x00, 0x00, 0x0d, 0x6c, 0x61, 0x73, 0x74,   # - - - - l a s t
        0x2d, 0x6d, 0x6f, 0x64, 0x69, 0x66, 0x69, 0x65,   # - m o d i f i e
        0x64, 0x00, 0x00, 0x00, 0x08, 0x6c, 0x6f, 0x63,   # d - - - - l o c
        0x61, 0x74, 0x69, 0x6f, 0x6e, 0x00, 0x00, 0x00,   # a t i o n - - -
        0x0c, 0x6d, 0x61, 0x78, 0x2d, 0x66, 0x6f, 0x72,   # - m a x - f o r
        0x77, 0x61, 0x72, 0x64, 0x73, 0x00, 0x00, 0x00,   # w a r d s - - -
        0x06, 0x70, 0x72, 0x61, 0x67, 0x6d, 0x61, 0x00,   # - p r a g m a -
        0x00, 0x00, 0x12, 0x70, 0x72, 0x6f, 0x78, 0x79,   # - - - p r o x y
        0x2d, 0x61, 0x75, 0x74, 0x68, 0x65, 0x6e, 0x74,   # - a u t h e n t
        0x69, 0x63, 0x61, 0x74, 0x65, 0x00, 0x00, 0x00,   # i c a t e - - -
        0x13, 0x70, 0x72, 0x6f, 0x78, 0x79, 0x2d, 0x61,   # - p r o x y - a
        0x75, 0x74, 0x68, 0x6f, 0x72, 0x69, 0x7a, 0x61,   # u t h o r i z a
        0x74, 0x69, 0x6f, 0x6e, 0x00, 0x00, 0x00, 0x05,   # t i o n - - - -
        0x72, 0x61, 0x6e, 0x67, 0x65, 0x00, 0x00, 0x00,   # r a n g e - - -
        0x07, 0x72, 0x65, 0x66, 0x65, 0x72, 0x65, 0x72,   # - r e f e r e r
        0x00, 0x00, 0x00, 0x0b, 0x72, 0x65, 0x74, 0x72,   # - - - - r e t r
        0x79, 0x2d, 0x61, 0x66, 0x74, 0x65, 0x72, 0x00,   # y - a f t e r -
        0x00, 0x00, 0x06, 0x73, 0x65, 0x72, 0x76, 0x65,   # - - - s e r v e
        0x72, 0x00, 0x00, 0x00, 0x02, 0x74, 0x65, 0x00,   # r - - - - t e -
        0x00, 0x00, 0x07, 0x74, 0x72, 0x61, 0x69, 0x6c,   # - - - t r a i l
        0x65, 0x72, 0x00, 0x00, 0x00, 0x11, 0x74, 0x72,   # e r - - - - t r
        0x61, 0x6e, 0x73, 0x66, 0x65, 0x72, 0x2d, 0x65,   # a n s f e r - e
        0x6e, 0x63, 0x6f, 0x64, 0x69, 0x6e, 0x67, 0x00,   # n c o d i n g -
        0x00, 0x00, 0x07, 0x75, 0x70, 0x67, 0x72, 0x61,   # - - - u p g r a
        0x64, 0x65, 0x00, 0x00, 0x00, 0x0a, 0x75, 0x73,   # d e - - - - u s
        0x65, 0x72, 0x2d, 0x61, 0x67, 0x65, 0x6e, 0x74,   # e r - a g e n t
        0x00, 0x00, 0x00, 0x04, 0x76, 0x61, 0x72, 0x79,   # - - - - v a r y
        0x00, 0x00, 0x00, 0x03, 0x76, 0x69, 0x61, 0x00,   # - - - - v i a -
        0x00, 0x00, 0x07, 0x77, 0x61, 0x72, 0x6e, 0x69,   # - - - w a r n i
        0x6e, 0x67, 0x00, 0x00, 0x00, 0x10, 0x77, 0x77,   # n g - - - - w w
        0x77, 0x2d, 0x61, 0x75, 0x74, 0x68, 0x65, 0x6e,   # w - a u t h e n
        0x74, 0x69, 0x63, 0x61, 0x74, 0x65, 0x00, 0x00,   # t i c a t e - -
        0x00, 0x06, 0x6d, 0x65, 0x74, 0x68, 0x6f, 0x64,   # - - m e t h o d
        0x00, 0x00, 0x00, 0x03, 0x67, 0x65, 0x74, 0x00,   # - - - - g e t -
        0x00, 0x00, 0x06, 0x73, 0x74, 0x61, 0x74, 0x75,   # - - - s t a t u
        0x73, 0x00, 0x00, 0x00, 0x06, 0x32, 0x30, 0x30,   # s - - - - 2 0 0
        0x20, 0x4f, 0x4b, 0x00, 0x00, 0x00, 0x07, 0x76,   # - O K - - - - v
        0x65, 0x72, 0x73, 0x69, 0x6f, 0x6e, 0x00, 0x00,   # e r s i o n - -
        0x00, 0x08, 0x48, 0x54, 0x54, 0x50, 0x2f, 0x31,   # - - H T T P - 1
        0x2e, 0x31, 0x00, 0x00, 0x00, 0x03, 0x75, 0x72,   # - 1 - - - - u r
        0x6c, 0x00, 0x00, 0x00, 0x06, 0x70, 0x75, 0x62,   # l - - - - p u b
        0x6c, 0x69, 0x63, 0x00, 0x00, 0x00, 0x0a, 0x73,   # l i c - - - - s
        0x65, 0x74, 0x2d, 0x63, 0x6f, 0x6f, 0x6b, 0x69,   # e t - c o o k i
        0x65, 0x00, 0x00, 0x00, 0x0a, 0x6b, 0x65, 0x65,   # e - - - - k e e
        0x70, 0x2d, 0x61, 0x6c, 0x69, 0x76, 0x65, 0x00,   # p - a l i v e -
        0x00, 0x00, 0x06, 0x6f, 0x72, 0x69, 0x67, 0x69,   # - - - o r i g i
        0x6e, 0x31, 0x30, 0x30, 0x31, 0x30, 0x31, 0x32,   # n 1 0 0 1 0 1 2
        0x30, 0x31, 0x32, 0x30, 0x32, 0x32, 0x30, 0x35,   # 0 1 2 0 2 2 0 5
        0x32, 0x30, 0x36, 0x33, 0x30, 0x30, 0x33, 0x30,   # 2 0 6 3 0 0 3 0
        0x32, 0x33, 0x30, 0x33, 0x33, 0x30, 0x34, 0x33,   # 2 3 0 3 3 0 4 3
        0x30, 0x35, 0x33, 0x30, 0x36, 0x33, 0x30, 0x37,   # 0 5 3 0 6 3 0 7
        0x34, 0x30, 0x32, 0x34, 0x30, 0x35, 0x34, 0x30,   # 4 0 2 4 0 5 4 0
        0x36, 0x34, 0x30, 0x37, 0x34, 0x30, 0x38, 0x34,   # 6 4 0 7 4 0 8 4
        0x30, 0x39, 0x34, 0x31, 0x30, 0x34, 0x31, 0x31,   # 0 9 4 1 0 4 1 1
        0x34, 0x31, 0x32, 0x34, 0x31, 0x33, 0x34, 0x31,   # 4 1 2 4 1 3 4 1
        0x34, 0x34, 0x31, 0x35, 0x34, 0x31, 0x36, 0x34,   # 4 4 1 5 4 1 6 4
        0x31, 0x37, 0x35, 0x30, 0x32, 0x35, 0x30, 0x34,   # 1 7 5 0 2 5 0 4
        0x35, 0x30, 0x35, 0x32, 0x30, 0x33, 0x20, 0x4e,   # 5 0 5 2 0 3 - N
        0x6f, 0x6e, 0x2d, 0x41, 0x75, 0x74, 0x68, 0x6f,   # o n - A u t h o
        0x72, 0x69, 0x74, 0x61, 0x74, 0x69, 0x76, 0x65,   # r i t a t i v e
        0x20, 0x49, 0x6e, 0x66, 0x6f, 0x72, 0x6d, 0x61,   # - I n f o r m a
        0x74, 0x69, 0x6f, 0x6e, 0x32, 0x30, 0x34, 0x20,   # t i o n 2 0 4 -
        0x4e, 0x6f, 0x20, 0x43, 0x6f, 0x6e, 0x74, 0x65,   # N o - C o n t e
        0x6e, 0x74, 0x33, 0x30, 0x31, 0x20, 0x4d, 0x6f,   # n t 3 0 1 - M o
        0x76, 0x65, 0x64, 0x20, 0x50, 0x65, 0x72, 0x6d,   # v e d - P e r m
        0x61, 0x6e, 0x65, 0x6e, 0x74, 0x6c, 0x79, 0x34,   # a n e n t l y 4
        0x30, 0x30, 0x20, 0x42, 0x61, 0x64, 0x20, 0x52,   # 0 0 - B a d - R
        0x65, 0x71, 0x75, 0x65, 0x73, 0x74, 0x34, 0x30,   # e q u e s t 4 0
        0x31, 0x20, 0x55, 0x6e, 0x61, 0x75, 0x74, 0x68,   # 1 - U n a u t h
        0x6f, 0x72, 0x69, 0x7a, 0x65, 0x64, 0x34, 0x30,   # o r i z e d 4 0
        0x33, 0x20, 0x46, 0x6f, 0x72, 0x62, 0x69, 0x64,   # 3 - F o r b i d
        0x64, 0x65, 0x6e, 0x34, 0x30, 0x34, 0x20, 0x4e,   # d e n 4 0 4 - N
        0x6f, 0x74, 0x20, 0x46, 0x6f, 0x75, 0x6e, 0x64,   # o t - F o u n d
        0x35, 0x30, 0x30, 0x20, 0x49, 0x6e, 0x74, 0x65,   # 5 0 0 - I n t e
        0x72, 0x6e, 0x61, 0x6c, 0x20, 0x53, 0x65, 0x72,   # r n a l - S e r
        0x76, 0x65, 0x72, 0x20, 0x45, 0x72, 0x72, 0x6f,   # v e r - E r r o
        0x72, 0x35, 0x30, 0x31, 0x20, 0x4e, 0x6f, 0x74,   # r 5 0 1 - N o t
        0x20, 0x49, 0x6d, 0x70, 0x6c, 0x65, 0x6d, 0x65,   # - I m p l e m e
        0x6e, 0x74, 0x65, 0x64, 0x35, 0x30, 0x33, 0x20,   # n t e d 5 0 3 -
        0x53, 0x65, 0x72, 0x76, 0x69, 0x63, 0x65, 0x20,   # S e r v i c e -
        0x55, 0x6e, 0x61, 0x76, 0x61, 0x69, 0x6c, 0x61,   # U n a v a i l a
        0x62, 0x6c, 0x65, 0x4a, 0x61, 0x6e, 0x20, 0x46,   # b l e J a n - F
        0x65, 0x62, 0x20, 0x4d, 0x61, 0x72, 0x20, 0x41,   # e b - M a r - A
        0x70, 0x72, 0x20, 0x4d, 0x61, 0x79, 0x20, 0x4a,   # p r - M a y - J
        0x75, 0x6e, 0x20, 0x4a, 0x75, 0x6c, 0x20, 0x41,   # u n - J u l - A
        0x75, 0x67, 0x20, 0x53, 0x65, 0x70, 0x74, 0x20,   # u g - S e p t -
        0x4f, 0x63, 0x74, 0x20, 0x4e, 0x6f, 0x76, 0x20,   # O c t - N o v -
        0x44, 0x65, 0x63, 0x20, 0x30, 0x30, 0x3a, 0x30,   # D e c - 0 0 - 0
        0x30, 0x3a, 0x30, 0x30, 0x20, 0x4d, 0x6f, 0x6e,   # 0 - 0 0 - M o n
        0x2c, 0x20, 0x54, 0x75, 0x65, 0x2c, 0x20, 0x57,   # - - T u e - - W
        0x65, 0x64, 0x2c, 0x20, 0x54, 0x68, 0x75, 0x2c,   # e d - - T h u -
        0x20, 0x46, 0x72, 0x69, 0x2c, 0x20, 0x53, 0x61,   # - F r i - - S a
        0x74, 0x2c, 0x20, 0x53, 0x75, 0x6e, 0x2c, 0x20,   # t - - S u n - -
        0x47, 0x4d, 0x54, 0x63, 0x68, 0x75, 0x6e, 0x6b,   # G M T c h u n k
        0x65, 0x64, 0x2c, 0x74, 0x65, 0x78, 0x74, 0x2f,   # e d - t e x t -
        0x68, 0x74, 0x6d, 0x6c, 0x2c, 0x69, 0x6d, 0x61,   # h t m l - i m a
        0x67, 0x65, 0x2f, 0x70, 0x6e, 0x67, 0x2c, 0x69,   # g e - p n g - i
        0x6d, 0x61, 0x67, 0x65, 0x2f, 0x6a, 0x70, 0x67,   # m a g e - j p g
        0x2c, 0x69, 0x6d, 0x61, 0x67, 0x65, 0x2f, 0x67,   # - i m a g e - g
        0x69, 0x66, 0x2c, 0x61, 0x70, 0x70, 0x6c, 0x69,   # i f - a p p l i
        0x63, 0x61, 0x74, 0x69, 0x6f, 0x6e, 0x2f, 0x78,   # c a t i o n - x
        0x6d, 0x6c, 0x2c, 0x61, 0x70, 0x70, 0x6c, 0x69,   # m l - a p p l i
        0x63, 0x61, 0x74, 0x69, 0x6f, 0x6e, 0x2f, 0x78,   # c a t i o n - x
        0x68, 0x74, 0x6d, 0x6c, 0x2b, 0x78, 0x6d, 0x6c,   # h t m l - x m l
        0x2c, 0x74, 0x65, 0x78, 0x74, 0x2f, 0x70, 0x6c,   # - t e x t - p l
        0x61, 0x69, 0x6e, 0x2c, 0x74, 0x65, 0x78, 0x74,   # a i n - t e x t
        0x2f, 0x6a, 0x61, 0x76, 0x61, 0x73, 0x63, 0x72,   # - j a v a s c r
        0x69, 0x70, 0x74, 0x2c, 0x70, 0x75, 0x62, 0x6c,   # i p t - p u b l
        0x69, 0x63, 0x70, 0x72, 0x69, 0x76, 0x61, 0x74,   # i c p r i v a t
        0x65, 0x6d, 0x61, 0x78, 0x2d, 0x61, 0x67, 0x65,   # e m a x - a g e
        0x3d, 0x67, 0x7a, 0x69, 0x70, 0x2c, 0x64, 0x65,   # - g z i p - d e
        0x66, 0x6c, 0x61, 0x74, 0x65, 0x2c, 0x73, 0x64,   # f l a t e - s d
        0x63, 0x68, 0x63, 0x68, 0x61, 0x72, 0x73, 0x65,   # c h c h a r s e
        0x74, 0x3d, 0x75, 0x74, 0x66, 0x2d, 0x38, 0x63,   # t - u t f - 8 c
        0x68, 0x61, 0x72, 0x73, 0x65, 0x74, 0x3d, 0x69,   # h a r s e t - i
        0x73, 0x6f, 0x2d, 0x38, 0x38, 0x35, 0x39, 0x2d,   # s o - 8 8 5 9 -
        0x31, 0x2c, 0x75, 0x74, 0x66, 0x2d, 0x2c, 0x2a,   # 1 - u t f - - -
        0x2c, 0x65, 0x6e, 0x71, 0x3d, 0x30, 0x2e          # - e n q - 0 -
    ])

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
  'k'          : ((3,1),             None),
  'dict_level' : ((4,1),             None),
  'truncate_to': ( None,          IntTo2B),
  'index'      : ( None,          IntTo1B),
  'str_val'    : ( None, PackB2LenPlusStr),
  'key_str'    : ( None, PackB2LenPlusStr),
  'val_str'    : ( None, PackB2LenPlusStr),
}

inline_unpacking_instructions = {
  'opcode'     : ((0,3),             None),
  'k'          : ((3,1),             None),
  'dict_level' : ((4,1),             None),
  'truncate_to': ( None,         LB2ToInt),
  'index'      : ( None,         LB1ToInt),
  'str_val'    : ( None, XtrtB2LenPlusStr),
  'key_str'    : ( None, XtrtB2LenPlusStr),
  'val_str'    : ( None, XtrtB2LenPlusStr),
}

packing_order = ['opcode',
                 'k',
                 'dict_level',
                 'truncate_to',
                 'pos',
                 'len',
                 'npos',
                 'index',
                 'str_val',
                 'key_str',
                 'val_str']

opcodes = {
    'Store': (0x0, 'k', 'dict_level', 'index', 'str_val'),
    'TaCo' : (0x1, 'k', 'dict_level', 'index', 'truncate_to', 'str_val'),
    'Rem'  : (0x2,      'dict_level', 'index'),
    'Tggl' : (0x3,      'dict_level', 'index'),
    'KVSto': (0x5,      'dict_level', 'index', 'key_str', 'val_str'),
    'ERef' : (0x6,                             'key_str', 'val_str'),
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

def MakeERef(key, value):
  op = {'opcode': 'ERef',
        'key_str': key,
        'val_str': value}
  return op

def MakeTaCo(is_key, dict_level, index, truncate_to, str_val):
  op = {'opcode': 'TaCo',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'truncate_to': truncate_to,
        'str_val': str_val}
  return op

def MakeRem(dict_level, index):
  op = {'opcode': 'Rem',
        'dict_level': dict_level,
        'index': index}
  return op

def MakeTggl(dict_level, index):
  op = {'opcode': 'Tggl',
        'dict_level': dict_level,
        'index': index}
  return op

def MakeStore(is_key, dict_level, index, str_val):
  op = {'opcode': 'Store',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'str_val': str_val}
  return op

def MakeKVSto(dict_level, index, key, val):
  op = {'opcode': 'KVSto',
        'dict_level': dict_level,
        'index': index,
        'key_str': key,
        'val_str': val}
  return op

def RealOpsToOps(realops):
  realop = [ord(c) for c in realops]
  return UnpackSPDY4Ops(inline_unpacking_instructions, realop)

def FormatOp(op):
  order = ['opcode', 'k', 'dict_level', 'index', 'truncate_to', 'str_len',
      'str_val', 'key_str_len', 'key_str', 'val_str_len', 'val_str']
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key is not 'opcode':
      inp.append("'%s': %s" % (key, repr(op[key])))
    if key in op and key is 'opcode':
      inp.append("'%s': %s" % (key, repr(op[key]).ljust(7)))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': %s" % (key, repr(op[key])))
  outp.append(', '.join(inp))
  outp.append('}')
  return ''.join(outp)

def KtoV(dict):
  retval = {}
  for (k, v) in dict.iteritems():
    retval[v] = k
  return retval

def NextIndex(dict):
  indices = [idx for (idx, val) in dict.iteritems()]
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

def CommonPrefixLen(str1, str2):
  prefix_match_len = 0
  for i in xrange(0, min(len(str1),len(str2))):
    if str1[i] != str2[i]:
      break;
    prefix_match_len += 1
  return prefix_match_len

def KeyIndexInDict(dict, key):
  for (index, dict_entry) in dict.iteritems():
    if dict_entry[1] == key:
      return index
  return -1

class CompressorDecompressor:
  def __init__(self):
    self.use_zlib = 1
    self.ephemereal_headers = {}
    self.compressor = zlib.compressobj(9, zlib.DEFLATED, -11)
    self.decompressor = zlib.decompressobj(-11)
    self.decompressor.decompress(self.compressor.compress(spdy_dictionary) +
                                 self.compressor.flush(zlib.Z_SYNC_FLUSH))
    self.generation = 0
    self.connection_dict = {}
    self.stream_group_indices = {}
    self.stream_group_dicts = {0: {}}


    connection_dict = { ":method": "get",
          ":version": "1.1",
          "user-agent": "",
          "accept-language": "",
          "accept": "",
          "accept-encoding": "",
          "accept-charset": "",
          "accept-ranges": "",
          "allow": "",
          }
    self.connection_headers = [k for (k,v) in connection_dict.iteritems()]
    self.limits = {'TotalHeaderStorageSize': 16*1024,
                   'MaxHeaderGroups': 1,
                   'MaxEntriesInTable': 64}
    self.total_storage = 0
    self.SetDictKVsAndMakeInvisible(self.connection_dict, connection_dict)
    self.SeedStreamGroup(self.stream_group_dicts[0])
  def GetDictSize(self):
    return self.total_storage

  def SetDictKVsAndMakeInvisible(self, dict, kv_pairs):
    for (key, val) in kv_pairs.iteritems():
      index = NextIndex(dict)
      self.ModifyDictEntry(dict, index, 1, key)
      self.ModifyDictEntry(dict, index, 0, val)
      self.SetVisibility(dict, index, 0)

  def GetHostnameForStreamGroup(self, stream_group):
    if stream_group == 0:
      return "<default>"
    try:
      dict = KtoV(self.stream_group_indices)
      retval = dict[stream_group]
    except:
      retval = "<unknown>"
    return retval

  def GetStreamGroupDict(self, stream_group):
    if stream_group in self.stream_group_dicts:
      return self.stream_group_dicts[stream_group]
    self.stream_group_dicts[stream_group] = {}
    self.SeedStreamGroup(self.stream_group_dicts[stream_group])
    return self.stream_group_dicts[stream_group]

  def FindAppropriateEntry(self, key, stream_group):
    dict = self.connection_dict
    dict_level = 1
    key_idx = KeyIndexInDict(dict, key)
    if key_idx == -1:  # if not in connection headers, try stream-group
      dict = self.GetStreamGroupDict(stream_group)
      dict_level = 0
      key_idx = KeyIndexInDict(dict, key)
      if key_idx == -1: # also not in stream-group. Add to appropriate level.
        if key in self.connection_headers:
          dict = self.connection_dict
          dict_level = 1
        # otherwise it'll get added to the group level
    return (dict, dict_level, key_idx)

  def MakeOpsForHeaderLine(self, key, value, stream_group):
    ops = []
    (dict, dict_level, key_idx) = self.FindAppropriateEntry(key, stream_group)
    op = None

    if key_idx == -1:  # store a new one.
      key_idx = NextIndex(dict)
      op = MakeKVSto(dict_level, key_idx, key, value)
    else:
      dict_value = ''
      if key_idx in dict:
        dict_value = dict[key_idx][0]
      prefix_match_len = CommonPrefixLen(dict_value, value)
      if prefix_match_len == len(value) and prefix_match_len == len(dict_value):
        self.Touch(dict, key_idx)
        if not self.IsVisible(dict[key_idx]):
          op = MakeTggl(dict_level, key_idx)
      #elif prefix_match_len > 2:  # 2 == trunc_to len
      #  op = MakeTaCo(0, dict_level, key_idx, prefix_match_len,
      #                      value[prefix_match_len:])
      else:
        op = MakeStore(0, dict_level, key_idx, value)
    if op is not None:
      self.ExecuteOp(op, stream_group, {})
      ops.append(op)
    return ops

  def GenerateAllHeaders(self, stream_group):
    headers = {}
    for (idx, item) in self.connection_dict.iteritems():
      if item[3]:
        headers[item[1]] = item[0]
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      if item[3]:
        headers[item[1]] = item[0]
    for (key, value) in self.ephemereal_headers.iteritems():
      headers[key] = value
    return headers

  def Touch(self, dict, index):
    dict[index][2] = self.generation

  def NotCurrent(self, item):
    return item[2] != self.generation

  def IsVisible(self, item):
    return item[3] == 1

  def RemoveDictEntry(self, dict, index):
    self.total_storage -= len(dict[index][not is_key])
    del dict[index]
    return

  def CleanupDict(self, dict):
    pass

  def PossiblyCleanupState(self):
    if self.total_storage > self.limits["TotalHeaderStorageSize"]:
      pass

  def ModifyDictEntry(self, dict, index, is_key, str_val):
    if index not in dict:
      if len(dict) > self.limits["MaxEntriesInTable"]:
        self.CleanupDict(dict)
      dict[index] = ['', '', 0, 1]  # v, k, gen, visible?

    self.total_storage -= len(dict[index][is_key])
    self.total_storage += len(str_val)
    dict[index][is_key] = str_val
    self.Touch(dict, index);
    if dict[index][1] == '':
      print "ERROR: ", dict, index, is_key, str_val
      raise StandardError()
    self.PossiblyCleanupState()

  def ToggleVisibility(self, dict, index):
    dict[index][3] = not dict[index][3]

  def SetVisibility(self, dict, index, visible):
    dict[index][3] = visible

  def Decompress(self, op_blob):
    if not self.use_zlib:
      return op_blob
    return self.decompressor.decompress(op_blob)

  def DeTokenify(self, realops, stream_group):
    ops = RealOpsToOps(realops)
    self.ephemereal_headers = {}
    self.ExecuteOps(ops, stream_group, self.ephemereal_headers)

  def ExecuteOps(self, ops, stream_group, ephemereal_headers):
    for op in ops:
      self.ExecuteOp(op, stream_group, ephemereal_headers)

  def ExecuteOp(self, op, stream_group, ephemereal_headers):
    opcode = op['opcode']
    if opcode == 'ERef':
      key_str_len = op['key_str_len']
      key_str = op['key_str']
      val_str_len = op['val_str_len']
      val_str = op['val_str']
      if key_str_len == 0 or val_str_len == 0:
        raise StandardError()
      if key_str in ephemereal_headers:
        raise StandardError()
      ephemereal_headers[key_str] = val_str
      return

    dict = self.connection_dict
    dict_level = op['dict_level']
    index = op['index']

    if dict_level != 1:
      dict = self.GetStreamGroupDict(stream_group)
    if opcode == 'Store':
      is_key = op['k']
      str_val = op['str_val']
      str_len = len(str_val)
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key, str_val)
      self.SetVisibility(dict, index, 1)
    elif opcode == 'TaCo':
      is_key = op['k']
      str_val = op['str_val']
      str_len = len(str_val)
      truncate_to = op['truncate_to']
      if str_len == 0 and truncate_to == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key,
          dict[index][is_key][:truncate_to] + str_val)
      self.SetVisibility(dict, index, 1)
    elif opcode == 'KVSto':
      self.ModifyDictEntry(dict, index, 1, op['key_str'])
      self.ModifyDictEntry(dict, index, 0, op['val_str'])
      self.SetVisibility(dict, index, 1)
    elif opcode == 'Rem':
      self.RemoveDictEntry(dict, index)
    elif opcode == 'Tggl':
      self.ToggleVisibility(dict, index)
    else:
      # unknown opcode
      raise StandardError()

  def MakeRemovalOps(self, stream_group):
    remove_ops = []
    for (idx, item) in self.connection_dict.iteritems():
      if self.NotCurrent(item) and self.IsVisible(item):
        remove_ops.append(MakeTggl(1, idx))
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      if self.NotCurrent(item) and self.IsVisible(item):
        remove_ops.append(MakeTggl(0, idx))
    for op in remove_ops:
      self.ExecuteOp(op, stream_group, {})
    return remove_ops

  def Compress(self, ops):
    realops = PackSpdy4Ops(inline_packing_instructions, ops)
    ba = ''.join(realops)
    if not self.use_zlib:
      return ba
    retval = self.compressor.compress(ba)
    retval += self.compressor.flush(zlib.Z_SYNC_FLUSH)
    return retval

  def SetDictKVsAndMakeInvisible(self, dict, kv_pairs):
    for (key, val) in kv_pairs.iteritems():
      index = NextIndex(dict)
      self.ModifyDictEntry(dict, index, 1, key)
      self.ModifyDictEntry(dict, index, 0, val)
      self.SetVisibility(dict, index, 0)

  def SeedStreamGroup(self, dict):
    self.SetDictKVsAndMakeInvisible(dict,
      {
        ":host": "",
        ":path": "/",
        ":scheme": "https",
        ":status": "200",
        ":status-text": "OK",
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
        })

  # returns a list of operations
  def FindStreamGroup(self, headers):
    stream_group = 0
    if headers[":host"] in self.stream_group_indices:
      stream_group = self.stream_group_indices[headers[":host"]]
    else:
      stream_group = NextIndex(KtoV(self.stream_group_indices))
      self.stream_group_indices[headers[":host"]] = stream_group
      self.stream_group_dicts[stream_group] = {}
      self.SeedStreamGroup(self.stream_group_dicts[stream_group])
    return stream_group

  def Tokenify(self, headers, stream_group):
    self.generation += 1
    ops = []
    for (key, value) in headers.iteritems():
      if not stream_group in self.stream_group_dicts:
        self.stream_group_dicts[stream_group] = {}
        self.SeedStreamGroup(self.stream_group_dicts[stream_group])
      ops.extend(self.MakeOpsForHeaderLine(key, value, stream_group))
    remove_ops = self.MakeRemovalOps(stream_group)
    return remove_ops + ops

def HTTPHeadersFormat(request):
  out_frame = []
  fl = ""
  avoid_list = []
  if ":method" in request:
    fl = "%s %s HTTP/%s\r\n" % (
        request[":method"],request[":path"],request[":version"])
    avoid_list = [":method", ":path", ":version"]
  else:
    fl = "HTTP/%s %s %s\r\n" % (
        request[":version"],request[":status"],request[":status-text"])
    avoid_list = [":version", ":status", ":status-text"]
  out_frame.append(fl)
  for (key, val) in request.iteritems():
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

def Spdy3HeadersFormat(request):
  out_frame = []
  for (key, val) in request.iteritems():
    out_frame.append(struct.pack("!L", len(key)))
    out_frame.append(key)
    out_frame.append(struct.pack("!L", len(val)))
    out_frame.append(val)
  return ''.join(out_frame)

def MakeDefaultHeaders(list_o_dicts, items_to_ignore=[]):
  retval = {}
  for kvdict in list_o_dicts:
    key = kvdict["name"].lower()
    val = kvdict["value"]
    if key == "host":
      key = ":host"
    if key in items_to_ignore:
      continue
    if key in retval:
      retval[key] = retval[key] + '\0' + val
    else:
      retval[key] = val
  return retval

def ReadHarFile(filename):
  f = open(filename)
  null = None
  true = 1
  false = 0
  s = f.read()
  o = eval(s)
  request_headers = []
  response_headers = []
  for entry in o["log"]["entries"]:
    request = entry["request"]
    header = MakeDefaultHeaders(request["headers"], ["connection"])
    header[":method"] = request["method"].lower()
    header[":path"] = re.sub("^[^:]*://[^/]*/","/", request["url"])
    header[":version"] = re.sub("^[^/]*/","", request["httpVersion"])
    header[":scheme"] = re.sub("^([^:]*):.*$", '\\1', request["url"]).lower()
    if not ":host" in request_headers:
      header[":host"] = re.sub("^[^:]*://([^/]*)/.*$","\\1", request["url"])
    if not header[":scheme"] in ["http", "https"]:
      continue
    request_headers.append(header)

    response = entry["response"]
    header = MakeDefaultHeaders(response["headers"],
        ["connection", "status", "status-text", "version"])
    header[":status"] = re.sub("^([0-9]*).*","\\1", str(response["status"]))
    header[":status-text"] = response["statusText"]
    header[":version"] = re.sub("^[^/]*/","", response["httpVersion"])
    response_headers.append(header)
  return (request_headers, response_headers)

def main():
  parser = OptionParser()
  parser.add_option("-v", "--verbose",
                    dest="v",
                    help="Sets verbosity. At v=1, the opcodes will be printed. "
                    "At v=2, so will the headers [default: %default]",
                    default=0,
                    metavar="VERBOSITY")
  parser.add_option("-t", "--type",
                    dest="header_type",
                    help="Selects if examining request or response headers. "
                    "Valid values are 'request' or 'response'"
                    " [default: %default]",
                    default='request',
                    metavar="HEADER_TYPE")
  (options, args) = parser.parse_args()
  requests = default_requests
  responses = []
  if args >= 1:
    requests = []
    responses = []
    for filename in args:
      (har_requests, har_responses) = ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)
  spdy4_frame_list = []
  spdy3_frame_list = []
  http1_frame_list = []
  spdy4_compressor = CompressorDecompressor()
  spdy4_decompressor = CompressorDecompressor()
  use_zlib = 1
  spdy4_compressor.use_zlib = use_zlib
  spdy4_decompressor.use_zlib = use_zlib
  spdy3_compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
      zlib.DEFLATED, 11)
  spdy3_compressor.compress(spdy_dictionary);
  spdy3_compressor.flush(zlib.Z_SYNC_FLUSH)
  http1_compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
      zlib.DEFLATED, 11)
  http1_compressor.compress(spdy_dictionary);
  http1_compressor.flush(zlib.Z_SYNC_FLUSH)

  if options.header_type == 'request':
    headers_to_compress = requests
  elif options.header_type == 'response':
    headers_to_compress = responses
  else:
    raise StandardError("Unknown type argument."
                        "It must be one of 'request' or 'response'")
  for i in xrange(len(requests)):
    request = requests[i]
    obj_to_compress = headers_to_compress[i]
    #print "request: ", request
    http1_frame = HTTPHeadersFormat(obj_to_compress)
    http1_frame_list.append((http1_frame,
                             http1_compressor.compress(http1_frame) +
                             http1_compressor.flush(zlib.Z_SYNC_FLUSH)))
    spdy3_frame = Spdy3HeadersFormat(obj_to_compress)
    spdy3_frame_list.append((spdy3_frame,
                             spdy3_compressor.compress(spdy3_frame) +
                             spdy3_compressor.flush(zlib.Z_SYNC_FLUSH)))

    spdy_4_stream_group = spdy4_compressor.FindStreamGroup(request)
    spdy_4_stream_group = 0
    in_ops = spdy4_compressor.Tokenify(obj_to_compress, spdy_4_stream_group)
    in_frame = spdy4_compressor.Compress(in_ops)
    spdy4_frame = PackSpdy4Ops(inline_packing_instructions, in_ops)

    spdy4_frame_list.append((spdy4_frame,in_frame, spdy_4_stream_group))

  print "        UC: UnCompressed frame size"
  print "        CM: CoMpressed frame size"
  print "        UR: Uncompressed / Http uncompressed"
  print "        CR:   Compressed / Http compressed"
  out_headers = []
  def framelen(x):
    return  len(x) + 8

  h1us = 0
  h1cs = 0
  s3us = 0
  s3cs = 0
  s4us = 0
  s4cs = 0
  for i in xrange(len(http1_frame_list)):
    out_ops = spdy4_decompressor.Decompress(spdy4_frame_list[i][1])
    out_frame = spdy4_decompressor.DeTokenify(out_ops, spdy4_frame_list[i][2])
    out_header = spdy4_decompressor.GenerateAllHeaders(spdy4_frame_list[i][2])
    out_headers.append(out_header)
    if options.v >= 2:
      print '##################################################################'
      print '####### request-path: "%s"' % requests[i][":path"][:80]
      print "####### stream group: %2d, %s" % (spdy4_frame_list[i][2],
          spdy4_compressor.GetHostnameForStreamGroup(spdy4_frame_list[i][2]))
      print "####### dict size: %3d" % spdy4_decompressor.GetDictSize()
      print
      if options.v >= 3:
        print "header: ", out_header
      print http1_frame_list[i][0]
      for op in RealOpsToOps(out_ops):
        print FormatOp(op)
      print

    (h1uncom, h1com) = map(len, http1_frame_list[i])
    h1us += h1uncom; h1cs += h1com
    (s3uncom, s3com) = map(framelen, spdy3_frame_list[i])
    s3us += s3uncom; s3cs += s3com
    (s4uncom, s4com) = map(framelen, spdy4_frame_list[i][:2])
    s4us += s4uncom; s4cs += s4com
    lines= [
    ("http1 ", h1uncom, h1com, 1.0*h1uncom/h1uncom, 1.0*h1com/h1com),
    ("spdy3 ", s3uncom, s3com, 1.0*s3uncom/h1uncom, 1.0*s3com/h1com),
    ("spdy4 ", s4uncom, s4com, 1.0*s4uncom/h1uncom, 1.0*s4com/h1com),
    ]
    if options.v >= 1:
      print "                                 UC  |  CM  |  UR  |  CR"
      for fmtarg in lines:
        print "             %s frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
      print
  fmtarg = (h1us, s3us, s4us)
  print "######################################################################"
  print "######################################################################"
  print
  print "                                   http1   |   spdy3   |   spdy4 "
  print "             Uncompressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg
  fmtarg = (h1cs,  s3cs, s4cs)
  print "               Compressed Sums:  % 8d  | % 8d  | % 8d  " % fmtarg
  fmtarg = (h1us*1./h1us,  s3us*1./h1us, s4us*1./h1us)
  print "Uncompressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
  fmtarg = (h1cs*1./h1us,  s3cs*1./h1us, s4cs*1./h1us)
  print "  Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  " % fmtarg
  print

  if headers_to_compress == out_headers:
    print "Original headers == output"
  else:
    print "Something is wrong."
    if options.v >= 1:
      for i in xrange(len(headers_to_compress)):
        if headers_to_compress[i] != out_headers[i]:
          print headers_to_compress[i]
          print "   !="
          print out_headers[i]
          print
  print
  for (opcode, ignore) in opcodes.iteritems():
    print "opcode: % 7s size: % 3d" % ("'" + opcode + "'",
        OpcodeSize(inline_unpacking_instructions, opcode))

main()



