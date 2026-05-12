# ======== Stage 3: Canonical Huffman Coding =========
#
# This stage takes the symbol stream from Stage 2 and assigns each symbol a
# variable-length binary code using Huffman coding. Symbols that appear more
# often get shorter codes; rare symbols get longer codes.
#
# WHY IS THIS NEEDED?
# After Stage 2, we have symbols like literal bytes (0–255), length codes
# (257–285), distance codes (0–29), and the end marker (256). If we stored
# each symbol with a fixed number of bits, common symbols like 'e' (101)
# would use the same space as rare symbols like 'z' (122). Huffman coding
# eliminates this waste by using fewer bits for frequent symbols.
#
# This stage builds TWO separate Huffman trees:
#   1. Literal/Length tree — for literal bytes + length symbols + end marker
#   2. Distance tree — for distance symbols
#
# The output attaches each symbol's Huffman code (as an integer + bit length)
# to the existing token stream. Stage 4 will pack these codes into a bitstream.

import os
from stage1 import stage1compress
from stage2 import stage2_compress
from utilities.util_3 import *

def stage3_compress(s2_compressed):
    """
    Assign Huffman codes to all symbols in the Stage 2 output.

    Steps:
      1. Count the frequency of every symbol (literal/length and distance)
      2. Build canonical Huffman codes from those frequencies
      3. Attach the Huffman code to each token in the stream

    Args:
        s2_compressed: List of tuples from Stage 2. Each is one of:
          ('literal', byte_value)
          ('match', len_sym, len_extra, dist_sym, dist_extra)
          ('end', 256)

    Returns:
        A list of tuples with Huffman codes attached:
          ('literal', symbol, huffman_code, code_bit_length)
          ('match', len_sym, len_extra, dist_sym, dist_extra,
                    len_huff_code, len_huff_len, dist_huff_code, dist_huff_len)
          ('end', 256, huffman_code, code_bit_length)
    """
    # Step 1: Count how often each symbol appears
    lit_freq, dist_freq = get_frequencies(s2_compressed)

    # Step 2: Build canonical Huffman codes for both alphabets
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)

    # Step 3: Walk through the token stream and attach Huffman codes
    s3_compressed = []
    for item in s2_compressed:
        if item[0] == 'literal':

            # Look up this literal byte's Huffman code in the lit/length tree
            code, length = lit_codes[item[1]]
            s3_compressed.append(('literal', item[1], code, length))

        elif item[0] == 'match':
            len_sym, len_extra, dist_sym, dist_extra = item[1], item[2], item[3], item[4]
            # Length symbol (257–285) uses the lit/length Huffman tree
            length_huff_code, length_huff_len = lit_codes[len_sym]
            # Distance symbol (0–29) uses the separate distance Huffman tree
            dist_huff_code, dist_huff_len = dist_codes[dist_sym]
            s3_compressed.append((
                'match',
                len_sym, len_extra,        # Stage 2 length info (symbol + extra bits)
                dist_sym, dist_extra,      # Stage 2 distance info (symbol + extra bits)
                length_huff_code, length_huff_len,   # Huffman code for the length symbol
                dist_huff_code, dist_huff_len        # Huffman code for the distance symbol
            ))

        elif item[0] == 'end':
            # End-of-block (symbol 256) also uses the lit/length Huffman tree
            code, length = lit_codes[item[1]]
            s3_compressed.append(('end', item[1], code, length))

    return s3_compressed


if __name__ == "__main__":

    # Path to the sample test data
    data_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', 'data_1.txt'
    )

    with open(data_path, 'rb') as f:
        data = f.read()

    print(f"=== Stage 3: Canonical Huffman Coding ===")
    print(f"Input file : {os.path.basename(data_path)}")
    print(f"Input size : {len(data)} bytes")
    print()

    # Run Stage 1
    s1_compressed = stage1compress(data)
    
    # Run Stage 2
    s2_compressed = stage2_compress(s1_compressed)

    # Get frequencies and codes for display
    lit_freq, dist_freq = get_frequencies(s2_compressed)
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)

    # Run Stage 3
    compressed = stage3_compress(s2_compressed)

    # Print each token with its Huffman code
    for idx, item in enumerate(compressed):
        if item[0] == 'literal':
            sym, code, bits = item[1], item[2], item[3]
            char = chr(sym) if 32 <= sym < 127 else f'\\x{sym:02x}'
            code_bin = format(code, f'0{bits}b')
            print(f"  [{idx:4d}] LITERAL   sym={sym:3d} '{char}'  huff={code_bin} ({bits} bits)")

        elif item[0] == 'match':
            len_sym, len_extra = item[1], item[2]
            dist_sym, dist_extra = item[3], item[4]
            lh_code, lh_bits = item[5], item[6]
            dh_code, dh_bits = item[7], item[8]
            lh_bin = format(lh_code, f'0{lh_bits}b')
            dh_bin = format(dh_code, f'0{dh_bits}b')
            extra = ""
            if len_extra:
                extra += f"  len_extra='{len_extra}'"
            if dist_extra:
                extra += f"  dist_extra='{dist_extra}'"
            print(f"  [{idx:4d}] MATCH     len_sym={len_sym:3d} huff={lh_bin} ({lh_bits}b)"
                  f"  dist_sym={dist_sym:2d} huff={dh_bin} ({dh_bits}b){extra}")

        elif item[0] == 'end':
            code, bits = item[2], item[3]
            code_bin = format(code, f'0{bits}b')
            print(f"  [{idx:4d}] END       sym={item[1]}  huff={code_bin} ({bits} bits)")

    # Print the Huffman code table for lit/length symbols
    print()
    print(f"--- Literal/Length Huffman Codes ({len(lit_codes)} symbols) ---")
    for sym in sorted(lit_codes.keys()):
        code, bits = lit_codes[sym]
        code_bin = format(code, f'0{bits}b')
        freq = lit_freq[sym]
        label = ""
        if sym < 256:
            char = chr(sym) if 32 <= sym < 127 else f'\\x{sym:02x}'
            label = f"  literal '{char}'"
        elif sym == 256:
            label = "  end-of-block"
        else:
            label = f"  length code"
        print(f"  sym={sym:3d}{label:20s}  freq={freq:3d}  code={code_bin} ({bits} bits)")

    # Print distance codes if any
    if dist_codes:
        print()
        print(f"--- Distance Huffman Codes ({len(dist_codes)} symbols) ---")
        for sym in sorted(dist_codes.keys()):
            code, bits = dist_codes[sym]
            code_bin = format(code, f'0{bits}b')
            freq = dist_freq[sym]
            print(f"  sym={sym:2d}  freq={freq:3d}  code={code_bin} ({bits} bits)")

    # Summary: total bits with Huffman vs fixed-width
    print()
    print(f"--- Summary ---")
    total_huff_bits = 0
    for item in compressed:
        if item[0] == 'literal':
            total_huff_bits += item[3]
        elif item[0] == 'match':
            total_huff_bits += item[6]  # length Huffman bits
            total_huff_bits += len(item[2]) if item[2] else 0  # length extra
            total_huff_bits += item[8]  # distance Huffman bits
            total_huff_bits += len(item[4]) if item[4] else 0  # distance extra
        elif item[0] == 'end':
            total_huff_bits += item[3]

    total_fixed_bits = len(s2_compressed) * 9  # 9 bits per symbol if fixed-width
    print(f"  Total Huffman bits   : {total_huff_bits} ({(total_huff_bits + 7) // 8} bytes)")
    print(f"  Fixed 9-bit encoding : {total_fixed_bits} ({(total_fixed_bits + 7) // 8} bytes)")
    print(f"  Bit savings          : {total_fixed_bits - total_huff_bits} bits")
    print(f"  Original data        : {len(data)} bytes ({len(data) * 8} bits)")