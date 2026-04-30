#
# utils.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .crc32 import crc32, crc32n

def crc32_bytes(buf):
    return crc32n(buf)

def crc32_int(buf):
    return crc32(buf)

def data_to_hex(buf):
    return ''.join('{:02x}'.format(x) for x in buf)

def int_to_bytes(n):
    return n.to_bytes(4, 'big')

def bytes_to_int(buf):
    return int.from_bytes(buf, 'big')

def string_to_bytes(s):
    return bytes(s, 'utf8')

def is_ur_type(s):
    for ch in s:
        if 'a' <= ch <= 'z':
            continue
        if '0' <= ch <= '9':
            continue
        if ch == '-':
            continue
        return False
    return len(s) > 0

def partition(s, n):
    return [s[i:i+n] for i in range(0, len(s), n)]

def split(buf, count):
    return (buf[0:count], buf[count:])

def join_lists(lists):
    return sum(lists, [])

def join_bytes(list_of_ba):
    out = bytearray()
    for ba in list_of_ba:
        out.extend(ba)
    return out

def xor_into(target, source):
    assert len(target) == len(source)
    for i in range(len(target)):
        target[i] ^= source[i]

def xor_with(a, b):
    xor_into(a, b)
    return a

def take_first(s, count):
    return s[0:count]

def drop_first(s, count):
    return s[count:]
