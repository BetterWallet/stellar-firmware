#
# bytewords.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

from .utils import crc32_bytes, partition

BYTEWORDS = 'ableacidalsoapexaquaarchatomauntawayaxisbackbaldbarnbeltbetabiasbluebodybragbrewbulbbuzzcalmcashcatschefcityclawcodecolacookcostcruxcurlcuspcyandarkdatadaysdelidicedietdoordowndrawdropdrumdulldutyeacheasyechoedgeepicevenexamexiteyesfactfairfernfigsfilmfishfizzflapflewfluxfoxyfreefrogfuelfundgalagamegeargemsgiftgirlglowgoodgraygrimgurugushgyrohalfhanghardhawkheathelphighhillholyhopehornhutsicedideaidleinchinkyintoirisironitemjadejazzjoinjoltjowljudojugsjumpjunkjurykeepkenokeptkeyskickkilnkingkitekiwiknoblamblavalazyleaflegsliarlimplionlistlogoloudloveluaulucklungmainmanymathmazememomenumeowmildmintmissmonknailnavyneednewsnextnoonnotenumbobeyoboeomitonyxopenovalowlspaidpartpeckplaypluspoempoolposepuffpumapurrquadquizraceramprealredorichroadrockroofrubyruinrunsrustsafesagascarsetssilkskewslotsoapsolosongstubsurfswantacotasktaxitenttiedtimetinytoiltombtoystriptunatwinuglyundouniturgeuservastveryvetovialvibeviewvisavoidvowswallwandwarmwaspwavewaxywebswhatwhenwhizwolfworkyankyawnyellyogayurtzapszerozestzinczonezoom'

WORD_ARRAY = None

def decode_word(word, word_len):
    global WORD_ARRAY
    if len(word) != word_len:
        raise ValueError('Invalid Bytewords.')

    dim = 26
    if WORD_ARRAY is None:
        WORD_ARRAY = [-1] * (dim * dim)
        for i in range(256):
            byteword_offset = i * 4
            x = ord(BYTEWORDS[byteword_offset]) - ord('a')
            y = ord(BYTEWORDS[byteword_offset + 3]) - ord('a')
            WORD_ARRAY[y * dim + x] = i

    x = ord(word[0].lower()) - ord('a')
    y = ord((word[3 if len(word) == 4 else 1]).lower()) - ord('a')
    if not (0 <= x < dim and 0 <= y < dim):
        raise ValueError('Invalid Bytewords.')

    value = WORD_ARRAY[y * dim + x]
    if value == -1:
        raise ValueError('Invalid Bytewords.')

    if len(word) == 4:
        byteword_offset = value * 4
        if word[1].lower() != BYTEWORDS[byteword_offset + 1] or word[2].lower() != BYTEWORDS[byteword_offset + 2]:
            raise ValueError('Invalid Bytewords.')

    return value

def get_word(index):
    byteword_offset = index * 4
    return BYTEWORDS[byteword_offset:byteword_offset + 4]

def get_minimal_word(index):
    byteword_offset = index * 4
    return BYTEWORDS[byteword_offset] + BYTEWORDS[byteword_offset + 3]

def encode_with_separator(buf, separator):
    crc_buf = buf + crc32_bytes(buf)
    return separator.join(get_word(b) for b in crc_buf)

def encode_minimal(buf):
    crc_buf = buf + crc32_bytes(buf)
    return ''.join(get_minimal_word(b) for b in crc_buf)

def decode(s, separator, word_len):
    buf = bytearray()
    words = s.split(separator) if word_len == 4 else partition(s, 2)
    for word in words:
        buf.append(decode_word(word, word_len))

    if len(buf) < 5:
        raise ValueError('Invalid Bytewords.')

    body = buf[0:-4]
    if crc32_bytes(bytes(body)) != bytes(buf[-4:]):
        raise ValueError('Invalid Bytewords.')

    return bytes(body)

Bytewords_Style_standard = 1
Bytewords_Style_uri      = 2
Bytewords_Style_minimal  = 3

class Bytewords:
    @staticmethod
    def encode(style, data):
        if style == Bytewords_Style_standard:
            return encode_with_separator(data, ' ')
        elif style == Bytewords_Style_uri:
            return encode_with_separator(data, '-')
        elif style == Bytewords_Style_minimal:
            return encode_minimal(data)
        else:
            raise ValueError(f"unknown style {style}")

    @staticmethod
    def decode(style, s):
        if style == Bytewords_Style_standard:
            return decode(s, ' ', 4)
        elif style == Bytewords_Style_uri:
            return decode(s, '-', 4)
        elif style == Bytewords_Style_minimal:
            return decode(s, 0, 2)
        else:
            raise ValueError(f"unknown style {style}")
