#
# xoshiro256.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
# Algorithm by David Blackman and Sebastiano Vigna (public domain)
#

import hashlib

from .utils import string_to_bytes, int_to_bytes
from .constants import MAX_UINT64

JUMP      = [0x180ec6d33cfd0aba, 0xd5a61266f0c9392c, 0xa9582618e03fc9aa, 0x39abdc4529b1661c]
LONG_JUMP = [0x76e15d3efefdcbbf, 0xc5004e441c522fb3, 0x77710069854ee241, 0x39109bb02acbe635]


def _rotl(x, k):
    return ((x << k) | (x >> (64 - k))) & MAX_UINT64


class Xoshiro256:
    def __init__(self, arr=None):
        self.s = [0] * 4
        if arr is not None:
            self.s[:] = arr

    def _set_s(self, arr):
        for i in range(4):
            o = i * 8
            self.s[i] = int.from_bytes(arr[o:o+8], 'big')

    def _hash_then_set_s(self, buf):
        digest = hashlib.sha256(buf).digest()
        self._set_s(digest)

    @classmethod
    def from_bytes(cls, buf):
        x = cls()
        x._hash_then_set_s(buf)
        return x

    @classmethod
    def from_crc32(cls, crc32):
        x = cls()
        x._hash_then_set_s(int_to_bytes(crc32))
        return x

    @classmethod
    def from_string(cls, s):
        x = cls()
        x._hash_then_set_s(string_to_bytes(s))
        return x

    def next(self):
        result = (_rotl((self.s[1] * 5) & MAX_UINT64, 7) * 9) & MAX_UINT64
        t = (self.s[1] << 17) & MAX_UINT64
        self.s[2] ^= self.s[0]
        self.s[3] ^= self.s[1]
        self.s[1] ^= self.s[2]
        self.s[0] ^= self.s[3]
        self.s[2] ^= t
        self.s[3] = _rotl(self.s[3], 45) & MAX_UINT64
        return result

    def next_double(self):
        return self.next() / (float(MAX_UINT64) + 1)

    def next_int(self, low, high):
        return int(self.next_double() * (high - low + 1) + low) & MAX_UINT64

    def next_byte(self):
        return self.next_int(0, 255)
