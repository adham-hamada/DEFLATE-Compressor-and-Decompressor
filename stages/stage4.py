# ======== Stage 4: Custom Header and Bitstream Packing =========
#
# This is the FINAL stage of the DEFLATE compressor. It takes the Huffman-coded
# token stream from Stage 3 and packs everything into a compact byte sequence —
# the actual compressed file.
#
# The output has two sections:
#
#   1. HEADER — Contains the Huffman code lengths so the decompressor can
#      rebuild the same Huffman trees without seeing the original data.
#
#   2. PAYLOAD — The compressed data: a stream of Huffman codes and extra bits,
#      packed tightly bit-by-bit with no wasted space between codes.
#
# HEADER FORMAT:
#   ┌───────────┬───────────┬─────────────────────┬──────────────────────┐
#   │ LIT_BW    │ DIST_BW   │ LIT_TABLE           │ DIST_TABLE           │
#   │ (4 bits)  │ (4 bits)  │ (286 × LIT_BW bits) │ (30 × DIST_BW bits) │
#   └───────────┴───────────┴─────────────────────┴──────────────────────┘
#
#   - LIT_BW: how many bits each literal/length code length uses
#   - DIST_BW: how many bits each distance code length uses
#   - LIT_TABLE: 286 code lengths (one per possible literal/length symbol)
#   - DIST_TABLE: 30 code lengths (one per possible distance symbol)
#     (omitted entirely if DIST_BW = 0, meaning no matches in the data)
#
# PAYLOAD FORMAT:
#   Literals:  [Huffman code]
#   Matches:   [Huffman(len_sym)] [len_extra] [Huffman(dist_sym)] [dist_extra]
#   End:       [Huffman(256)]

import os
import math

from stage1 import stage1compress
from stage2 import stage2_compress
from stage3 import stage3_compress
from utilities.util_3 import *
from utilities.util_4 import *


def stage4_compress(s3_compressed, lit_codes, dist_codes):
    """
    Produce the final compressed byte string.

    This function does two things:
      1. Writes a HEADER containing the Huffman code lengths (so the
         decompressor can rebuild the Huffman trees)
      2. Writes the PAYLOAD — each token's Huffman code and extra bits
         packed into a tight bitstream

    Parameters
    ----------
    s3_compressed : list
        Output of stage3_compress().
        Each element is one of:
          ('literal', symbol, huff_code, huff_len)
          ('match',   len_sym, len_extra_str,
                      dist_sym, dist_extra_str,
                      len_huff_code,  len_huff_len,
                      dist_huff_code, dist_huff_len)
          ('end',     256, huff_code, huff_len)
    lit_codes  : dict  { symbol -> (code_int, length) }
    dist_codes : dict  { symbol -> (code_int, length) }

    Returns
    -------
    bytes
        The final compressed byte sequence (header + payload).
    """
    # Convert the code dicts into flat arrays of code lengths for the header
    lit_lengths, dist_lengths = get_code_length_tables(lit_codes, dist_codes)

    # Compute how many bits each code length needs in the header
    lit_bw  = compute_bit_width(lit_lengths)
    dist_bw = compute_bit_width(dist_lengths)

    bw = BitWriter()

    # ── HEADER ────────────────────────────────────────────────
    # First 4 bits: LIT_BW (tells the decompressor the width of each lit length entry)
    bw.write_bits(lit_bw, 4)
    # Next 4 bits: DIST_BW (width of each distance length entry)
    bw.write_bits(dist_bw, 4)

    # Write 286 literal/length code lengths, each using lit_bw bits.
    for length in lit_lengths:
        bw.write_bits(length, lit_bw)

    # Write 30 distance code lengths, each using dist_bw bits.
    if dist_bw > 0:
        for length in dist_lengths:
            bw.write_bits(length, dist_bw)

    # ── PAYLOAD ───────────────────────────────────────────────
    # Write each token's Huffman code (and extra bits for matches) one after another.
    for item in s3_compressed:
        if item[0] == 'literal':
            _, symbol, huff_code, huff_len = item
            # Write the Huffman code for this literal byte
            bw.write_bits(huff_code, huff_len)

        elif item[0] == 'match':
            (_, len_sym,  len_extra_str,
                dist_sym, dist_extra_str,
                len_huff_code,  len_huff_len,
                dist_huff_code, dist_huff_len) = item

            # A match is written as 4 parts in sequence:
            # 1. Huffman code for the length symbol (from lit/length tree)
            bw.write_bits(len_huff_code, len_huff_len)
            # 2. Extra bits for the length (raw, not Huffman-coded)
            bw.write_bit_string(len_extra_str)
            # 3. Huffman code for the distance symbol (from distance tree)
            bw.write_bits(dist_huff_code, dist_huff_len)
            # 4. Extra bits for the distance (raw, not Huffman-coded)
            bw.write_bit_string(dist_extra_str)

        elif item[0] == 'end':
            _, symbol, huff_code, huff_len = item
            # Write the end-of-block Huffman code (symbol 256)
            bw.write_bits(huff_code, huff_len)

    # Pad the last byte with trailing zeros to make a complete byte
    bw.flush()

    return bw.get_bytes()


if __name__ == "__main__":

    # Path to the sample test data
    data_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', 'data_1.txt'
    )

    with open(data_path, 'rb') as f:
        data = f.read()

    print(f"=== Stage 4: Custom Header and Bitstream Packing ===")
    print(f"Input file : {os.path.basename(data_path)}")
    print(f"Input size : {len(data)} bytes")
    print()

    # Run Stage 1
    s1_compressed = stage1compress(data)
    
    # Run Stage 2 
    s2_compressed = stage2_compress(s1_compressed)

    # Get frequencies and codes
    lit_freq, dist_freq = get_frequencies(s2_compressed)
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)

    # Run Stage 3
    s3_compressed = stage3_compress(s2_compressed)

    # Run Stage 4
    compressed = stage4_compress(s3_compressed, lit_codes, dist_codes)

    # Header info
    lit_lengths, dist_lengths = get_code_length_tables(lit_codes, dist_codes)
    lit_bw = compute_bit_width(lit_lengths)
    dist_bw = compute_bit_width(dist_lengths)

    header_bits = 4 + 4 + (286 * lit_bw) + (30 * dist_bw if dist_bw > 0 else 0)
    payload_bits = len(compressed) * 8 - header_bits  # approximate (includes padding)

    print(f"--- Header ---")
    print(f"  LIT_BW             : {lit_bw} bits per code length")
    print(f"  DIST_BW            : {dist_bw} bits per code length")
    print(f"  LIT_TABLE entries  : 286 × {lit_bw} = {286 * lit_bw} bits")
    print(f"  DIST_TABLE entries : 30 × {dist_bw} = {30 * dist_bw} bits")
    print(f"  Total header       : {header_bits} bits ({(header_bits + 7) // 8} bytes)")
    print()
    print(f"--- Output ---")
    print(f"  Compressed bytes   : {len(compressed)}")
    print(f"  Hex dump           : {compressed.hex()}")
    print()
    print(f"--- Compression Summary ---")
    print(f"  Original           : {len(data)} bytes")
    print(f"  Compressed         : {len(compressed)} bytes")
    ratio = len(compressed) / len(data) * 100
    print(f"  Ratio              : {ratio:.1f}%")
    print(f"  Space saved        : {len(data) - len(compressed)} bytes ({100 - ratio:.1f}%)")