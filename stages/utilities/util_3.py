# ======== Stage 3 Utilities: Huffman Tree Building & Canonical Codes =========
#
# The process has three steps:
#   1. Count frequencies    → get_frequencies()
#   2. Build a Huffman tree → build_huffman_tree() → get_huffman_lengths()
#   3. Generate canonical codes from the lengths → get_huffman_codes()
#
# WHY CANONICAL CODES?
# A regular Huffman tree can produce many valid code assignments for the same
# set of frequencies. Canonical Huffman coding constrains the codes so that
# they can be reconstructed from just the code LENGTHS (not the full tree).
# This means we only need to store the lengths in the compressed file header,
# saving significant space.

import heapq

def get_frequencies(s2_compressed):
    """
    Count how often each symbol appears in the Stage 2 output.

    DEFLATE uses TWO separate Huffman trees:
      - Literal/Length tree: covers symbols 0–285
        (0–255 = literal bytes, 256 = end-of-block, 257–285 = length codes)
      - Distance tree: covers symbols 0–29

    Args:
        s2_compressed: List of tuples from Stage 2.

    Returns:
        (lit_freq, dist_freq): Two frequency arrays.
          - lit_freq[i] = how many times literal/length symbol i appears
          - dist_freq[i] = how many times distance symbol i appears
    """
    lit_freq = [0] * 286   # 286 possible literal/length symbols
    dist_freq = [0] * 30   # 30 possible distance symbols
    for item in s2_compressed:
        if item[0] == 'literal':
            lit_freq[item[1]] += 1
        elif item[0] == 'match':
            lit_freq[item[1]] += 1
            dist_freq[item[3]] += 1
        elif item[0] == 'end':
            lit_freq[item[1]] += 1

    return lit_freq, dist_freq


def build_huffman_tree(freq):
    """
    Build a Huffman tree from a frequency array and return symbol-code pairs.

    Algorithm (standard Huffman construction):
      1. Create a leaf node for each symbol with frequency > 0
      2. Repeatedly merge the two lowest-frequency nodes into a parent node
      3. Left branches get '0', right branches get '1'
      4. The code for each symbol is the path from root to its leaf

    Implementation:
      Uses a min-heap (priority queue) where each entry is:
        (weight, min_symbol, code_pairs)
      - weight: total frequency of this subtree
      - min_symbol: smallest symbol in this subtree (used as tiebreaker so
                    Python doesn't try to compare the code_pairs lists)
      - code_pairs: list of [symbol, code_string] for all leaves in this subtree

    Args:
        freq: A list where freq[i] = frequency of symbol i.

    Returns:
        A sorted list of [symbol, code_string] pairs, sorted by
        (code length, symbol) — shortest codes first, ties broken by symbol.
    """

    # Create a leaf for each symbol that actually appears (frequency > 0)
    # Each leaf is (weight, symbol, [[symbol, ""]])
    heap = [(w, s, [[s, ""]]) for s, w in enumerate(freq) if w > 0]
    if not heap:
        return []
    heapq.heapify(heap)

    # Merge nodes until only one remains (the root of the Huffman tree)
    while len(heap) > 1:
        # Pop the two nodes with the smallest frequencies
        w1, m1, p1 = heapq.heappop(heap)
        w2, m2, p2 = heapq.heappop(heap)
        # Prepend '0' to all codes in the left subtree
        for pair in p1: pair[1] = '0' + pair[1]
        # Prepend '1' to all codes in the right subtree
        for pair in p2: pair[1] = '1' + pair[1]
        # Push the merged node back onto the heap
        heapq.heappush(heap, (w1 + w2, min(m1, m2), p1 + p2))

    # Return all symbol-code pairs, sorted by (code length, symbol number)
    return sorted(heap[0][2], key=lambda x: (len(x[1]), x[0]))


def get_huffman_lengths(freq):
    """
    Build a Huffman tree and extract just the code lengths (not the codes themselves).

    Args:
        freq: A list where freq[i] = frequency of symbol i.

    Returns:
        A list where lengths[i] = the Huffman code length for symbol i.
    """
    tree = build_huffman_tree(freq)
    if not tree:
        return [0] * len(freq)
    lengths = [0] * len(freq)
    for symbol, code in tree:
        lengths[symbol] = max(len(code), 1)
    return lengths


def get_huffman_codes(freq):
    """
    Generate CANONICAL Huffman codes from a frequency array.

    Canonical Huffman coding generates codes deterministically from just the
    code lengths. The rules are:
      1. Shorter codes come before longer codes
      2. Within the same length, codes are assigned in symbol order
      3. The first code of each length is derived from the previous length

    This means two important things:
      - The compressor and decompressor only need to agree on the LENGTHS
        (not the full tree) to reconstruct the same codes
      - We only need to store the lengths in the file header, not the codes

    Algorithm (from RFC 1951):
      Step 1: Count how many symbols have each code length
      Step 2: Compute the starting code for each length using:
              next_code[bits] = (next_code[bits-1] + count[bits-1]) << 1
      Step 3: Assign codes sequentially within each length group

    Args:
        freq: A list where freq[i] = frequency of symbol i.

    Returns:
        A dict mapping symbol → (code_integer, code_length).
        Only symbols with frequency > 0 are included.

        Example: {65: (0b10, 2), 66: (0b110, 3)} means
          symbol 65 → code '10' (2 bits)
          symbol 66 → code '110' (3 bits)
    """
    lengths = get_huffman_lengths(freq)

    # Step 1: Count how many symbols have each code length (max 15 bits in DEFLATE)
    count = [0] * 16
    for length in lengths:
        count[length] += 1
    count[0] = 0  # Length 0 means "symbol not present" — don't count these

    # Step 2: Compute the starting code value for each bit length.
    # The formula ensures no code is a prefix of another (prefix-free property).
    # Each length's starting code = (previous length's start + its count) << 1
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + count[bits - 1]) << 1
        next_code[bits] = code

    # Step 3: Assign codes to symbols in order.
    # Symbols with the same code length get consecutive codes.
    symbol_code = {}
    for symbol in range(len(lengths)):
        length = lengths[symbol]
        if length != 0:
            symbol_code[symbol] = (next_code[length], length)
            next_code[length] += 1
    return symbol_code