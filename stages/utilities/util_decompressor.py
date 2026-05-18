# ── Decompressor utilities ──
# BitReader:          reads bits one-at-a-time from a byte string (mirror of BitWriter)
# build_decode_table: rebuilds canonical Huffman lookup from code lengths
# decode_symbol:      reads bits from the stream until a valid Huffman code is matched

class BitReader:
    """
    Reads bits one at a time from a byte string, MSB first.
    This is the exact mirror of BitWriter.
    """

    def __init__(self, data):
        self.data         = data  # the full compressed bytes
        self.byte_pos     = 0     # index of the next byte to load
        self.bits_in_byte = 0     # unread bits left in current_byte
        self.current_byte = 0     # the byte we are currently pulling bits from

    def read_bit(self):
        """Read and return exactly one bit (0 or 1)."""
        # If the current byte is exhausted, load the next one
        if self.bits_in_byte == 0:
            self.current_byte = self.data[self.byte_pos]
            self.byte_pos    += 1
            self.bits_in_byte = 8
        # Pull the most-significant remaining bit
        self.bits_in_byte -= 1
        return (self.current_byte >> self.bits_in_byte) & 1

    def read_bits(self, n):
        """Read n bits and return them as an integer (MSB first)."""
        value = 0
        for _ in range(n):
            value = (value << 1) | self.read_bit()
        return value


def build_decode_table(lengths):
    """
    Given lengths[symbol] = code_length for every symbol,
    rebuild the canonical Huffman codes and return a lookup dict:

        (code_integer, num_bits)  ->  symbol

    This uses the identical algorithm as get_huffman_codes() in the
    compressor, so the codes produced here are guaranteed to match.
    """
    # Step 1: count symbols at each length
    count = [0] * 16
    for length in lengths:
        count[length] += 1
    count[0] = 0

    # Step 2: first code for each length
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + count[bits - 1]) << 1
        next_code[bits] = code

    # Step 3: assign codes in symbol order, store reversed for decoding
    code_to_symbol = {}
    for symbol in range(len(lengths)):
        length = lengths[symbol]
        if length != 0:
            code_to_symbol[(next_code[length], length)] = symbol
            next_code[length] += 1

    return code_to_symbol


def decode_symbol(reader, code_to_symbol):
    """
    Read bits one at a time, accumulating them into `code`.
    After each new bit check whether (code, bits_read) is a known entry.
    The first hit is our symbol — prefix-free codes guarantee no valid
    code is a prefix of another, so the first match is always correct.
    """
    code      = 0
    bits_read = 0
    while True:
        code       = (code << 1) | reader.read_bit()
        bits_read += 1
        symbol = code_to_symbol.get((code, bits_read))
        if symbol is not None:
            return symbol

