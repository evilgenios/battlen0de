"""The wire-format/AES helpers moved unchanged into protocol.py. These are
pure functions with no credential/account state, so the only thing worth
testing here is that the move didn't break them."""

from app.core.warpath.protocol import (
    aes_decrypt,
    aes_encrypt_zero_padded,
    dump_pb,
    encode_bytes_field,
    encode_string_field,
    encode_varint,
    encode_varint_field,
    make_tag,
    parse_pb,
)


def test_encode_varint_matches_protobuf_spec_examples():
    # Values taken from the protobuf varint encoding spec.
    assert encode_varint(1) == b'\x01'
    assert encode_varint(150) == b'\x96\x01'


def test_string_field_roundtrips_through_parse_pb():
    encoded = encode_string_field(5, 'hello')
    parsed = parse_pb(encoded)
    assert parsed[5][0] == ('s', 'hello')


def test_varint_field_roundtrips_through_parse_pb():
    encoded = encode_varint_field(3, 42)
    parsed = parse_pb(encoded)
    assert parsed[3][0] == ('v', 42)


def test_bytes_field_with_nested_structure_roundtrips():
    inner = encode_varint_field(1, 7)
    outer = encode_bytes_field(9, inner)
    parsed = parse_pb(outer)
    wire_type, value = parsed[9][0]
    assert wire_type == 'd'
    assert value[1][0] == ('v', 7)


def test_dump_pb_does_not_raise_on_parsed_structure():
    encoded = encode_string_field(1, 'x') + encode_varint_field(2, 99)
    text = dump_pb(parse_pb(encoded))
    assert 'f1' in text
    assert 'f2' in text


def test_aes_roundtrip():
    plaintext = b'warpath test payload 1234567890'
    ciphertext = aes_encrypt_zero_padded(plaintext)
    assert ciphertext != plaintext
    assert aes_decrypt(ciphertext)[: len(plaintext)] == plaintext


def test_aes_encrypt_zero_pads_to_block_size():
    ciphertext = aes_encrypt_zero_padded(b'short')
    assert len(ciphertext) % 16 == 0


def test_make_tag_combines_field_number_and_wire_type():
    # field 1, wire type 0 (varint) -> tag byte 0x08
    assert make_tag(1, 0) == encode_varint(0x08)
