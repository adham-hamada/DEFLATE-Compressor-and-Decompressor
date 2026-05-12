# ======== Stage 4 Utilities: Bit-Level Writing & Header Helpers =========
#
# This file provides the tools needed by Stage 4 to pack everything into
# a final byte stream. The main component is the BitWriter class, which
# handles the tricky job of writing variable-length bit sequences into
# fixed 8-bit bytes.
#
# It also includes helper functions for computing the compressed file's
# header — specifically, how many bits are needed to store each Huffman
# code length in the header tables.

import math


class BitWriter:
    """
    Accumulates individual bits and packs them into bytes (MSB-first).

    Problem: Huffman codes and extra bits have variable lengths (3 bits,
    7 bits, etc.), but files are made of 8-bit bytes. This class bridges
    that gap — you write any number of bits, and it assembles them into
    complete bytes automatically.

    Bit order: Most Significant Bit (MSB) first. For example, writing
    the value 5 (binary 101) with num_bits=3 writes bits 1, 0, 1 in
    that order into the output stream.

    Example usage:
        bw = BitWriter()
        bw.write_bits(0b101, 3)    # Write 3 bits: 1, 0, 1
        bw.write_bits(0b11, 2)     # Write 2 bits: 1, 1
        bw.write_bits(0b010, 3)    # Write 3 bits: 0, 1, 0
        bw.flush()                 # Pad remaining bits and finalize
        result = bw.get_bytes()    # b'\\xba' (binary: 10111010)
    """

    def __init__(self):
        self.buffer = bytearray()
        self.current_byte = 0
        self.bits_in_byte = 0

    def write_bits(self, value, num_bits):
        """
        Write `num_bits` bits of `value` into the stream, MSB first.

        Extracts bits from left to right (most significant first) and
        shifts them into current_byte. When current_byte fills up to
        8 bits, it's flushed to the buffer and a new byte begins.

        Args:
            value: An integer whose lowest `num_bits` bits will be written.
            num_bits: How many bits to write (e.g., 4 for a Huffman code of length 4).
        """
        for i in range(num_bits - 1, -1, -1):
            bit = (value >> i) & 1
            self.current_byte = (self.current_byte << 1) | bit
            self.bits_in_byte += 1
            # When we've accumulated a full byte (8 bits), flush it
            if self.bits_in_byte == 8:
                self.buffer.append(self.current_byte)
                self.current_byte = 0
                self.bits_in_byte = 0

    def write_bit_string(self, bit_string):
        """
        Write a string of '0' and '1' characters as individual bits.

        Args:
            bit_string: A string like '0110' — each character becomes one bit.
        """
        for ch in bit_string:
            self.write_bits(int(ch), 1)

    def flush(self):
        """Pad the current partial byte with zeros on the right and flush it."""
        if self.bits_in_byte > 0:
            self.current_byte <<= (8 - self.bits_in_byte)
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bits_in_byte = 0

    def get_bytes(self):
        """Return the accumulated bytes as an immutable bytes object."""
        return bytes(self.buffer)


def compute_bit_width(code_lengths):
    """
    Compute how many bits are needed to store each code length in the header.

    The bit width (BW) is the minimum number of bits to represent the largest
    code length: BW = floor(log2(max_length)) + 1.

    Args:
        code_lengths: A list of Huffman code lengths (e.g., [0, 0, 4, 3, 0, 5, ...]).

    Returns:
        An integer: the bit width needed to encode each length value.
    """
    M = max(code_lengths) if code_lengths else 0
    if M == 0:
        return 0
    return math.floor(math.log2(M)) + 1


def get_code_length_tables(lit_codes, dist_codes):
    """
    Convert the Huffman code dictionaries into flat arrays of code lengths.

    Args:
        lit_codes: Dict mapping literal/length symbol → (code_int, code_length).
        dist_codes: Dict mapping distance symbol → (code_int, code_length).

    Returns:
        (lit_lengths, dist_lengths): Two lists.
          - lit_lengths[i] = Huffman code length for literal/length symbol i (0 if absent)
          - dist_lengths[i] = Huffman code length for distance symbol i (0 if absent)
    """
    # Build a flat array of 286 entries for the literal/length alphabet
    lit_lengths = [0] * 286
    for symbol, (code, length) in lit_codes.items():
        lit_lengths[symbol] = length

    # Build a flat array of 30 entries for the distance alphabet
    dist_lengths = [0] * 30
    for symbol, (code, length) in dist_codes.items():
        dist_lengths[symbol] = length

    return lit_lengths, dist_lengths