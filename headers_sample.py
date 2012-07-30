#!/usr/bin/python
import zlib
import string
import sys
import array
import struct

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

def B1ToInt(val):
  arg = "%c%c%c%c" % (0,0,0,val[0])
  return struct.unpack("!L", arg)[0]

def LenIntTo2B(val):
  return IntTo2B(len(val))

def SetBitsInByte(lsb_bw, x):
  (lsb, bw) = lsb_bw
  return (x & ( ~(255 << bw))) << (7 - lsb - (bw - 1))

def GetBitsInByte(least_significant_bit, bit_width):
  def GetIt(x):
    return (x >> (7-least_significant_bit-(bit_width-1))) & (~(255<<bit_width))

def Idem(x):
  return x

def LenPlusStr(x):
  return ''.join([IntTo2B(len(x)), x])


# first byte, top_block, str_block
separate_packing_instructions = {
  'opcode'     : ((0,3),       None, None),
  'k'          : ((3,1),       None, None),
  'dict_level' : ((4,1),       None, None),
  'truncate_to': ( None,    IntTo2B, None),
  'index'      : ( None,    IntTo1B, None),
  'str_val'    : ( None, LenIntTo2B, Idem),
  'key_str'    : ( None, LenIntTo2B, Idem),
  'val_str'    : ( None, LenIntTo2B, Idem),
}

inline_packing_instructions = {
  'opcode'     : ((0,3),       None, None),
  'k'          : ((3,1),       None, None),
  'dict_level' : ((4,1),       None, None),
  'truncate_to': ( None,    IntTo2B, None),
  'index'      : ( None,    IntTo1B, None),
  'str_val'    : ( None, LenPlusStr, None),
  'key_str'    : ( None, LenPlusStr, None),
  'val_str'    : ( None, LenPlusStr, None),
}

#inverse = {
#    None: None,
#    IntTo2B: B2ToInt,
#    IntTo1B: B1ToInt,
#    LenPlusStr: StrAndLen

packing_order = ['opcode',
                 'k',
                 'dict_level',
                 'truncate_to',
                 'index',
                 'str_val',
                 'key_str',
                 'val_str']

opcodes = {
    'ERef' : (0x0, 'key_str', 'val_str'),
    'Store': (0x1, 'k', 'dict_level', 'index', 'str_val'),
    'TaCo' : (0x2, 'k', 'dict_level', 'truncate_to', 'str_val'),
    'KVSto': (0x3, 'index', 'key_str', 'val_str'),
    'Rem'  : (0x4, 'index'),
    'Hide' : (0x5, 'index'),
    'Show' : (0x6, 'index'),
    }

def OpcodeToVal(x):
  return opcodes[x][0]

def UnpackSPDY4Ops(ops):
  out = []

def PackSpdy4Ops(packing_instructions, ops):
  top_block = []
  str_block = []
  for op in ops:
    fb = 0
    tb = []
    sb = []
    for field_name in packing_order:
      if not field_name in op:
        continue
      (fb_func_params, tp_func, sr_func) = packing_instructions[field_name]
      val = op[field_name]
      if field_name == 'opcode':
        val = OpcodeToVal(op[field_name])
      if fb_func_params is not None:
        fb = fb | SetBitsInByte(fb_func_params, val)
      if tp_func is not None:
        tb.append(tp_func(val))
      if sr_func is not None:
        sb.append(sr_func(val))
    top_block.append(chr(fb))
    top_block.extend(tb)
    str_block.extend(sb)
  top_block_str = ''.join(top_block)
  str_block_str = ''.join(str_block)
  return top_block_str + str_block_str

def ParseFB(byte):
  return (((byte >> 5) & 0x7), ((byte >> 4) & 0x1), ((byte >> 3) & 0x1))

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

def MakeHide(dict_level, index):
  op = {'opcode': 'Hide',
        'dict_level': dict_level,
        'index': index}
  return op

def MakeShow(dict_level, index):
  op = {'opcode': 'Show',
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
  input_size = len(realops)
  idx = 0
  ops = []
  realop = [ord(c) for c in realops]
  #print "input_size: ", input_size
  while input_size > idx:
    (opcode, k, l) = ParseFB(realop[idx])
    idx += 1

    if opcode == 0x0:  # ERef
      key_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      key = ListToStr(realop[idx:idx+key_len])
      idx += key_len
      val_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      val = ListToStr(realop[idx:idx+val_len])
      idx += val_len
      ops.append(MakeERef(key, val))
      continue
    if opcode == 0x1:  # Store
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      str_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      str_val = ListToStr(realop[idx:idx+str_len])
      idx += str_len
      ops.append(MakeStore(k, l, index, str_val))
      continue
    if opcode == 0x2:  # TaCo
      truncto = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      str_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      str_val = ListToStr(realop[idx:idx+str_len])
      idx += str_len
      ops.append(MakeTaCo(k, l, index, truncto, str_val))
      continue
    if opcode == 0x3:  # KVSto
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      key_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      key = ListToStr(realop[idx:idx+key_len])
      idx += key_len
      val_len = B2ToInt(realop[idx+0:idx+2])
      idx += 2#
      val = ListToStr(realop[idx:idx+val_len])
      idx += val_len
      ops.append(MakeKVSto(l, index, key, val))
      continue
    if opcode == 0x4:  # Rem
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      ops.append(MakeRem(l, index))
      continue
    if opcode == 0x5:
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      ops.append(MakeHide(l, index))
      continue
    if opcode == 0x6:
      index   = B1ToInt(realop[idx+0:idx+1])
      idx += 1#
      ops.append(MakeShow(l, index))
      continue

    print "unknown opcode: ", hex(opcode)
    raise StandardError()  # unknown opcode.
  return ops

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
      #print "ni: ", prev_idx + 1
      return prev_idx + 1
    prev_idx = idx
  #print "ni: ", idx + 1
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
    self.stream_group_dicts = {0: {}}

    self.connection_headers = [":method", ":version", "user-agent" ]
    self.limits = {'TotalHeaderStorageSize': 16*1024,
                   'MaxHeaderGroups': 1,
                   'MaxEntriesInTable': 64}
    self.total_storage = 0

  def FindAppropriateEntry(self, key, stream_group):
    dict = self.connection_dict
    dict_level = 1
    key_idx = KeyIndexInDict(dict, key)
    if key_idx == -1:  # if not in connection headers, try stream-group
      dict = self.stream_group_dicts[stream_group]
      dict_level = 0
      key_idx = KeyIndexInDict(dict, key)
      if key_idx == -1: # also not in stream-group. Add to appropriate level.
        if key in self.connection_headers:
          dict = self.connection_dict
          dict_level = 1
        # otherwise it'll get added to the group level
    return (dict, dict_level, key_idx)

  def MakeOps(self, key, value, stream_group):
    ops = []
    # ops.append(MakeERef(key, value))
    # return ops
    (dict, dict_level, key_idx) = self.FindAppropriateEntry(key, stream_group)

    if key_idx == -1:  # store a new one.
      key_idx = NextIndex(dict)
      ops.append(MakeKVSto(dict_level, key_idx, key, value))
      #ops.extend([MakeStore(1, dict_level, key_idx, key),
      #            MakeStore(0, dict_level, key_idx, value)])
    else:
      dict_value = ''
      if key_idx in dict:
        dict_value = dict[key_idx][0]
      prefix_match_len = CommonPrefixLen(dict_value, value)
      if prefix_match_len == len(value):
        self.Touch(dict, key_idx)
        if not dict[key_idx][3]:
          ops.append(MakeShow(dict_level, key_idx))
          self.MakeVisible(dict, key_idx)
      elif prefix_match_len > 3:  # 3 == trunc_to len
        ops.append(MakeTaCo(0, dict_level, key_idx, prefix_match_len,
                            value[prefix_match_len:]))
      else:
        ops.append(MakeStore(0, dict_level, key_idx, value))


    for op in ops: # gotta keep our state up-to-date.
      #print "executing: ", FormatOp(op)
      self.ExecuteOp(op, stream_group, {})
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

  def ModifyDictEntry(self, dict, index, is_key, str_val):
    if index not in dict:
      dict[index] = ['', '', 0, 1]  # v, k, gen, visible?
    self.total_storage -= len(dict[index][is_key])
    if str_val == '':
      self.total_storage -= len(dict[index][not is_key])
      del dict[index]
      return
    self.total_storage += len(str_val)
    dict[index][is_key] = str_val
    self.Touch(dict, index);
    if dict[index][1] == '':
      raise StandardError()
    #print self.total_storage

  def MakeInvisible(self, dict, index):
    dict[index][3] = 0

  def MakeVisible(self, dict, index):
    dict[index][3] = 1

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
      dict = self.stream_group_dicts[stream_group]
    if opcode == 'Store':
      is_key = op['k']
      str_val = op['str_val']
      str_len = len(str_val)
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key, str_val)
      self.MakeVisible(dict, index)
    elif opcode == 'TaCo':
      is_key = op['k']
      str_val = op['str_val']
      str_len = len(str_val)
      truncate_to = op['truncate_to']
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key,
          dict[index][is_key][:truncate_to] + str_val)
      self.MakeVisible(dict, index)
    elif opcode == 'KVSto':
      self.ModifyDictEntry(dict, index, 1, op['key_str'])
      self.ModifyDictEntry(dict, index, 0, op['val_str'])
      self.MakeVisible(dict, index)
    elif opcode == 'Rem':
      self.ModifyDictEntry(dict, index, 0, '')
    elif opcode == 'Hide':
      self.MakeInvisible(dict, index)
    elif opcode == 'Show':
      self.MakeVisible(dict, index)
    else:
      # unknown opcode
      raise StandardError()

  def MakeRemovalOps(self, stream_group):
    remove_ops = []
    for (idx, item) in self.connection_dict.iteritems():
      if self.NotCurrent(item):
        #remove_ops.append(MakeRem(1, idx))
        remove_ops.append(MakeHide(1, idx))
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      if self.NotCurrent(item):
        #remove_ops.append(MakeRem(0, idx))
        remove_ops.append(MakeHide(0, idx))
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

  # returns a list of operations
  def Tokenify(self, headers, stream_group):
    self.generation += 1
    ops = []
    for (key, value) in headers.iteritems():
      if not stream_group in self.stream_group_dicts:
        self.stream_group_dict[stream_group] = {}
      ops.extend(self.MakeOps(key, value, stream_group))
    remove_ops = self.MakeRemovalOps(stream_group)
    return remove_ops + ops

def HTTPHeadersFormat(request):
  out_frame = []
  for (key, val) in request.iteritems():
    out_frame.append(key)
    out_frame.append(": ")
    out_frame.append(val)
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

def main():
  requests = [ {':method': "get",
                ':path': '/index.html',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
                'date': 'Wed Jul 18 11:50:43 2012'},
               {':method': "get",
                ':path': '/index.js',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
                'date': 'Wed Jul 18 11:50:44 2012'},
               {':method': "get",
                ':path': '/index.css',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
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
  spdy4a_frame_list = []
  spdy4_frame_list = []
  spdy3_frame_list = []
  http1_frame_list = []
  spdy4a_compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 11)
  spdy4a_compressor.compress(spdy_dictionary); spdy4a_compressor.flush(zlib.Z_SYNC_FLUSH)
  spdy4_compressor = CompressorDecompressor()
  spdy4_decompressor = CompressorDecompressor()
  use_zlib = 1
  spdy4_compressor.use_zlib = use_zlib
  spdy4_decompressor.use_zlib = use_zlib
  spdy3_compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 11)
  spdy3_compressor.compress(spdy_dictionary); spdy3_compressor.flush(zlib.Z_SYNC_FLUSH)
  http1_compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, 11)
  http1_compressor.compress(spdy_dictionary); http1_compressor.flush(zlib.Z_SYNC_FLUSH)
  for request in requests:
    print "request: ", request
    http1_frame = HTTPHeadersFormat(request)
    http1_frame_list.append((http1_frame,
                             http1_compressor.compress(http1_frame) +
                             http1_compressor.flush(zlib.Z_SYNC_FLUSH)))
    spdy3_frame = Spdy3HeadersFormat(request)
    spdy3_frame_list.append((spdy3_frame,
                             spdy3_compressor.compress(spdy3_frame) +
                             spdy3_compressor.flush(zlib.Z_SYNC_FLUSH)))

    in_ops = spdy4_compressor.Tokenify(request, 0)
    in_frame = spdy4_compressor.Compress(in_ops)
    spdy4_frame = PackSpdy4Ops(inline_packing_instructions, in_ops)

    spdy4_frame_list.append((spdy4_frame,in_frame))

    spdy4a_frame = PackSpdy4Ops(separate_packing_instructions, in_ops)
    spdy4a_frame_list.append((spdy4a_frame,
                              spdy4a_compressor.compress(spdy4a_frame) +
                              spdy4a_compressor.flush(zlib.Z_SYNC_FLUSH)))
  print "                    UC  |  CM  |  RH  | CH  "
  for i in xrange(len(http1_frame_list)):
    (uncom, com) = map(len, http1_frame_list[i])
    httplen = len(http1_frame_list[i][0])
    fmtarg = (uncom, com, 1.0*uncom/httplen, 1.0*com/httplen)
    print "http1  frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
  print
  for i in xrange(len(spdy3_frame_list)):
    (uncom, com) = map(len, spdy3_frame_list[i])
    httplen = len(http1_frame_list[i][0])
    fmtarg = (uncom+11, com+11, (11.+uncom)/httplen, (11.+com)/httplen)
    print "spdy3  frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
  print
  for i in xrange(len(spdy4_frame_list)):
    (uncom, com) = map(len, spdy4_frame_list[i])
    httplen = len(http1_frame_list[i][0])
    fmtarg = (uncom+11, com+11, (11.+uncom)/httplen, (11.+com)/httplen)
    print "spdy4  frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
  print
  for i in xrange(len(spdy4a_frame_list)):
    (uncom, com) = map(len, spdy4a_frame_list[i])
    httplen = len(http1_frame_list[i][0])
    fmtarg = (uncom+11, com+11, (11.+uncom)/httplen, (11.+com)/httplen)
    print "spdy4a frame size: %4d | %4d | %2.2f | %2.2f" % fmtarg
  print

  out_requests = []
  for (tokens, frame) in spdy4_frame_list:
    out_ops = spdy4_decompressor.Decompress(frame)
    for op in RealOpsToOps(out_ops):
      print FormatOp(op)
    print
    out_frame = spdy4_decompressor.DeTokenify(out_ops, 0)
    out_request = spdy4_decompressor.GenerateAllHeaders(0)
    out_requests.append(out_request)
    print "request: ", out_request

  if requests == out_requests:
    print "Original requests == output"
  else:
    print "Something is wrong."
    for i in xrange(len(requests)):
      if requests[i] != out_requests[i]:
        print requests[i]
        print "   !="
        print out_requests[i]
        print

main()



