"""Warpath wire-format helpers: protobuf varint/tag encoding, AES-CBC framing,
and a generic fallback protobuf decoder.

Moved unchanged from the original warpath_bot.py — this module has no
account/credential state at all, so there was nothing to refactor here
beyond giving it a home. Do not change the encoding, framing, or AES
parameters; they must match the Warpath client exactly.
"""

from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.wire_format import (
    WIRETYPE_LENGTH_DELIMITED,
    WIRETYPE_VARINT,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Fixed transport-obfuscation key/IV used by the Warpath client itself for
# every account. This is the game's own (weak) protocol framing, extracted
# from the client — it is not a per-account or per-deployment secret, so it
# stays a plain module constant rather than living on WarpathCredentials.
AES_KEY = b'wgame138821^@#~!'
AES_IV = b'wgame155231^@#~!'


# ---------------------------------------------------------------------------
# Protobuf wire-format encoding
# ---------------------------------------------------------------------------
def encode_varint(value):
    bits = value & 0x7f
    value >>= 7
    result = b''
    while value:
        result += bytes([0x80 | bits])
        bits = value & 0x7f
        value >>= 7
    result += bytes([bits])
    return result


def make_tag(field_num, wire_type):
    return encode_varint((field_num << 3) | wire_type)


def encode_string_field(field_num, s):
    encoded = s.encode('utf-8')
    return make_tag(field_num, WIRETYPE_LENGTH_DELIMITED) + encode_varint(len(encoded)) + encoded


def encode_bytes_field(field_num, data):
    return make_tag(field_num, WIRETYPE_LENGTH_DELIMITED) + encode_varint(len(data)) + data


def encode_varint_field(field_num, value):
    return make_tag(field_num, WIRETYPE_VARINT) + encode_varint(value)


# ---------------------------------------------------------------------------
# AES-CBC helpers
# ---------------------------------------------------------------------------
def aes_encrypt_zero_padded(data):
    pad_len = (-len(data)) % 16
    if pad_len:
        data += bytes(pad_len)
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    enc = cipher.encryptor()
    return enc.update(data) + enc.finalize()


def aes_decrypt(data):
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    dec = cipher.decryptor()
    return dec.update(data) + dec.finalize()


# ---------------------------------------------------------------------------
# Protobuf recursive parser (generic — no generated classes needed)
# ---------------------------------------------------------------------------
def parse_pb(data, depth=0, max_depth=4):
    result = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _DecodeVarint32(data, pos)
            fn = tag >> 3
            wt = tag & 7
            if wt == WIRETYPE_VARINT:
                val, pos = _DecodeVarint32(data, pos)
                result.setdefault(fn, []).append(('v', val))
            elif wt == WIRETYPE_LENGTH_DELIMITED:
                ln, pos = _DecodeVarint32(data, pos)
                if pos + ln > len(data):
                    break
                sub = data[pos:pos + ln]
                pos += ln
                try:
                    s = sub.decode('utf-8')
                    if all(32 <= ord(c) < 127 for c in s) and len(s) > 0:
                        result.setdefault(fn, []).append(('s', s))
                    else:
                        if depth < max_depth:
                            result.setdefault(fn, []).append(('d', parse_pb(sub, depth + 1, max_depth)))
                        else:
                            result.setdefault(fn, []).append(('b', sub))
                except Exception:
                    if depth < max_depth:
                        result.setdefault(fn, []).append(('d', parse_pb(sub, depth + 1, max_depth)))
                    else:
                        result.setdefault(fn, []).append(('b', sub))
            elif wt == 5:
                pos += 4
            elif wt == 1:
                pos += 8
            else:
                break
        except Exception:
            break
    return result


def dump_pb(msg, indent=0):
    p = '  ' * indent
    lines = []
    for fn in sorted(msg.keys()):
        for wt, val in msg[fn]:
            if wt == 'v':
                lines.append(f'{p}f{fn} = {val}')
            elif wt == 's':
                lines.append(f'{p}f{fn} = "{val[:80]}"')
            elif wt == 'd':
                lines.append(f'{p}f{fn}:')
                lines.extend(dump_pb(val, indent + 1).split('\n'))
            elif wt == 'b':
                if isinstance(val, bytes):
                    lines.append(f'{p}f{fn} (bytes {len(val)}): {val[:20].hex()}')
                elif isinstance(val, dict):
                    lines.extend(dump_pb(val, indent).split('\n'))
    return '\n'.join(lines)
