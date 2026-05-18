# ────────────────────────────────────────────────────────
# LENGTH TABLES (for match lengths 3–258)
# ────────────────────────────────────────────────────────
#
# length_base[i] = the smallest length that maps to symbol (i + 257).
# length_extra[i] = how many extra bits are needed for symbol (i + 257).
#
# The range covered by symbol (i + 257) is:
#   [length_base[i], length_base[i] + 2^length_extra[i] - 1]
#
# For example:
#   Symbol 257: base=3,  extra=0 → only length 3
#   Symbol 265: base=11, extra=1 → lengths 11–12  (extra bit picks which one)
#   Symbol 269: base=19, extra=2 → lengths 19–22  (2 extra bits pick which one)
#   Symbol 285: base=258, extra=0 → only length 258 (the maximum)

length_base = [
    3, 4, 5, 6, 7, 8, 9, 10,
    11, 13, 15, 17,
    19, 23, 27, 31,
    35, 43, 51, 59,
    67, 83, 99, 115,
    131, 163, 195, 227,
    258
]

length_extra = [
    0, 0, 0, 0, 0, 0, 0, 0,
    1, 1, 1, 1,
    2, 2, 2, 2,
    3, 3, 3, 3,
    4, 4, 4, 4,
    5, 5, 5, 5,
    0
]

# ────────────────────────────────────────────────────────
# DISTANCE TABLES (for back-reference distances 1–32768)
# ────────────────────────────────────────────────────────
#
# Same idea as length tables but for the distance part of a match.
#
# distance_base[i] = the smallest distance that maps to symbol i.
# distance_extra[i] = how many extra bits are needed for symbol i.
#
# For example:
#   Symbol 0: base=1,  extra=0  → only distance 1
#   Symbol 4: base=5,  extra=1  → distances 5–6
#   Symbol 10: base=33, extra=4 → distances 33–48

distance_base = [
    1, 2, 3, 4,
    5, 7,
    9, 13,
    17, 25,
    33, 49,
    65, 97,
    129, 193,
    257, 385,
    513, 769,
    1025, 1537,
    2049, 3073,
    4097, 6145,
    8193, 12289,
    16385, 24577
]

distance_extra = [
    0, 0, 0, 0,
    1, 1,
    2, 2,
    3, 3, 
    4, 4,
    5, 5, 
    6, 6,
    7, 7, 
    8, 8,
    9, 9, 
    10, 10,
    11, 11, 
    12, 12,
    13, 13
]


def get_length_symbol(length):
    """
    Convert a raw match length (3–258) into a DEFLATE symbol + extra bits.

    Args:
        length: The actual match length from LZ77 (between 3 and 258).

    Returns:
        A tuple (symbol, extra_bits_string):
          - symbol: An integer 257–285 (the DEFLATE length symbol code)
          - extra_bits_string: A binary string like "01" or "" (empty if 0 extra bits)
    """
    for i in range(len(length_base)):
        # Check if 'length' falls within the range of symbol (i + 257)
        if length >= length_base[i] and length <= length_base[i] + pow(2,length_extra[i]) - 1:
            length_symbol = i + 257  # DEFLATE length symbols start at 257
            # The extra bits encode the offset from the base value
            return length_symbol, encode_extra_bits(length - length_base[i], length_extra[i])


def get_distance_symbol(distance):
    """
    Convert a raw back-reference distance (1–32768) into a DEFLATE symbol + extra bits.

    Args:
        distance: The actual distance from LZ77 (between 1 and 32768).

    Returns:
        A tuple (symbol, extra_bits_string):
          - symbol: An integer 0–29 (the DEFLATE distance symbol code)
          - extra_bits_string: A binary string or "" if no extra bits needed
    """
    for i in range(len(distance_base)):
        # Check if 'distance' falls within the range of symbol i
        if distance <= (distance_base[i] + pow(2,distance_extra[i]) - 1) and distance >= distance_base[i]:
            distance_symbol = i  # Distance symbols start at 0
            # The extra bits encode the offset from the base value
            return distance_symbol, encode_extra_bits(distance - distance_base[i], distance_extra[i])


def encode_extra_bits(bits, num_bits):
    """
    Convert an integer offset into a fixed-width binary string.

    Args:
        bits: The integer value to encode (the offset from the base).
        num_bits: How many bits to use (from the length_extra or distance_extra table).

    Returns:
        A string of '0's and '1's, or '' if num_bits is 0.
    """
    if num_bits == 0:
        return ''
    return format(bits, '0' + str(num_bits) + 'b')
