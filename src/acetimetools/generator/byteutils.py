# Copyright 2023 Brian T. Park
#
# MIT License
"""
Utils for writing unsigned ints to byte arrays in little endian format.
For negative integers, use 2's complement.
"""

from typing import List


def write_u8(data: bytearray, x: int) -> None:
    if x > 255:
        raise ValueError(f"x={x} > 255, cannot write into uint8")
    if x < 0:
        raise ValueError(f"x={x} < 0, cannot write into uint8")
    b0 = x & 0xff
    data.append(b0)


def write_i8(data: bytearray, x: int) -> None:
    if x > 127:
        raise ValueError(f"x={x} > 127, cannot write into int8")
    if x < -128:
        raise ValueError(f"x={x} < -128, cannot write into int8")
    if x < 0:
        x += 256
    write_u8(data, x)


def write_u16(data: bytearray, x: int) -> None:
    if x > 65535:
        raise ValueError(f"x={x} > 65535, cannot write into uint16")
    if x < 0:
        raise ValueError(f"x={x} < 0, cannot write into uint16")

    b0 = x & 0xff
    x >>= 8
    b1 = x & 0xff
    data.append(b0)
    data.append(b1)


def write_i16(data: bytearray, x: int) -> None:
    if x > 32767:
        raise ValueError(f"x={x} > 32767, cannot write into int16")
    if x < -32768:
        raise ValueError(f"x={x} < -32768, cannot write into int16")
    if x < 0:
        x += 65536
    write_u16(data, x)


def write_u32(data: bytearray, x: int) -> None:
    if x > 4294967295:
        raise ValueError(f"x={x} > 4294967295, cannot write into uint32")
    if x < 0:
        raise ValueError(f"x={x} < 0, cannot write into uint32")

    b0 = x & 0xff
    x >>= 8
    b1 = x & 0xff
    x >>= 8
    b2 = x & 0xff
    x >>= 8
    b3 = x & 0xff
    data.append(b0)
    data.append(b1)
    data.append(b2)
    data.append(b3)


def write_i32(data: bytearray, x: int) -> None:
    if x > (1 << 31 - 1):
        raise ValueError(f"x={x} > {1<<31-1}, cannot write into int32")
    if x < -(1 << 31):
        raise ValueError(f"x={x} < {-(1<<31)}, cannot write into int32")
    if x < 0:
        x += (1 << 32)
    write_u32(data, x)


def hex_encode(data: bytearray) -> str:
    """Convert byte array to hex escape (\\xhh) string. Even printable ASCII
    characters [32,127] are converted to hex escape for consistency.
    """
    s = ''
    for b in data:
        s += f'\\x{b:02x}'
    return s


def convert_to_go_string(data: bytearray, chunk_size: int, prefix: str) -> str:
    """Convert hex encoded data into a hex-encoded Golang string, broken up into
    chunks of size chunk_size. For example, in chunks of 5 bytes:
        "\x32\xbc\xdf\x9a\x42" +
        "\x32\xbc\xdf\x9a\x42"
    """
    sarray: List[str] = []
    count = 0
    while count + chunk_size <= len(data):
        s = hex_encode(data[count:count + chunk_size])
        sarray.append(s)
        count += chunk_size

    # Handle trailing chunk that should be < chunk_size
    if count < len(data):
        s = hex_encode(data[count:])
        sarray.append(s)
    return '"' + f'" +\n{prefix}"'.join(sarray) + '"'
