#
# cbor_lite.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
# Original CBOR-lite: Copyright Isode Limited, MIT License
#

Tag_Major_unsignedInteger = 0
Tag_Major_negativeInteger = 1 << 5
Tag_Major_byteString      = 2 << 5
Tag_Major_textString      = 3 << 5
Tag_Major_array           = 4 << 5
Tag_Major_map             = 5 << 5
Tag_Major_semantic        = 6 << 5
Tag_Major_simple          = 7 << 5
Tag_Major_mask            = 0xe0

Tag_Minor_length1 = 24
Tag_Minor_length2 = 25
Tag_Minor_length4 = 26
Tag_Minor_length8 = 27
Tag_Minor_false   = 20
Tag_Minor_true    = 21
Tag_Minor_mask    = 0x1f

Flag_None = 0


def _byte_length(value):
    if value < 24:
        return 0
    return (value.bit_length() + 7) // 8


class CBOREncoder:
    def __init__(self):
        self.buf = bytearray()

    def get_bytes(self):
        return self.buf

    def _encode_tag_and_additional(self, tag, additional):
        self.buf.append(tag + additional)

    def _encode_tag_and_value(self, tag, value):
        length = _byte_length(value)
        if length >= 5:
            self._encode_tag_and_additional(tag, Tag_Minor_length8)
            self.buf += value.to_bytes(8, 'big')
        elif length in (3, 4):
            self._encode_tag_and_additional(tag, Tag_Minor_length4)
            self.buf += value.to_bytes(4, 'big')
        elif length == 2:
            self._encode_tag_and_additional(tag, Tag_Minor_length2)
            self.buf += value.to_bytes(2, 'big')
        elif length == 1:
            self._encode_tag_and_additional(tag, Tag_Minor_length1)
            self.buf.append(value)
        else:
            self._encode_tag_and_additional(tag, value)

    def encodeInteger(self, value):
        if value >= 0:
            self._encode_tag_and_value(Tag_Major_unsignedInteger, value)
        else:
            self._encode_tag_and_value(Tag_Major_negativeInteger, -1 - value)

    def encodeBytes(self, value):
        self._encode_tag_and_value(Tag_Major_byteString, len(value))
        self.buf += value

    def encodeArraySize(self, value):
        self._encode_tag_and_value(Tag_Major_array, value)


class CBORDecoder:
    def __init__(self, buf):
        self.buf = buf
        self.pos = 0

    def _read_tag_and_value(self):
        if self.pos >= len(self.buf):
            raise Exception("Not enough input")
        octet = self.buf[self.pos]
        self.pos += 1
        tag        = octet & Tag_Major_mask
        additional = octet & Tag_Minor_mask

        if additional < Tag_Minor_length1:
            return tag, additional

        n_bytes = {
            Tag_Minor_length1: 1,
            Tag_Minor_length2: 2,
            Tag_Minor_length4: 4,
            Tag_Minor_length8: 8,
        }.get(additional)
        if n_bytes is None:
            raise Exception(f"Bad additional value {additional}")
        if self.pos + n_bytes > len(self.buf):
            raise Exception("Not enough input")
        value = int.from_bytes(self.buf[self.pos:self.pos + n_bytes], 'big')
        self.pos += n_bytes
        return tag, value

    def decodeUnsigned(self):
        tag, value = self._read_tag_and_value()
        if tag != Tag_Major_unsignedInteger:
            raise Exception(f"Expected unsigned int, got tag {tag}")
        return value, self.pos

    def decodeBytes(self):
        tag, byte_length = self._read_tag_and_value()
        if tag != Tag_Major_byteString:
            raise Exception("Not a byteString")
        if self.pos + byte_length > len(self.buf):
            raise Exception("Not enough input")
        value = bytes(self.buf[self.pos:self.pos + byte_length])
        self.pos += byte_length
        return value, self.pos

    def decodeArraySize(self):
        tag, value = self._read_tag_and_value()
        if tag != Tag_Major_array:
            raise Exception(f"Expected array, got tag {tag}")
        return value, self.pos
