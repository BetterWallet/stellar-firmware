#
# crc32.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .constants import MAX_UINT32

TABLE = None

def crc32(buf):
    global TABLE
    if TABLE is None:
        TABLE = [None] * 256
        for i in range(256):
            c = i
            for j in range(8):
                c = (c >> 1) if (c % 2 == 0) else (0xEDB88320 ^ (c >> 1))
            TABLE[i] = c

    crc = MAX_UINT32 & ~0
    for byte in buf:
        crc = (crc >> 8) ^ TABLE[(crc ^ byte) & 0xFF]
    return MAX_UINT32 & ~crc

def crc32n(buf):
    return crc32(buf).to_bytes(4, 'big')
