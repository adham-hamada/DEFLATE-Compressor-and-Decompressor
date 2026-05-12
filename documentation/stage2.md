# Stage 2: DEFLATE Symbols and Extra Bits

## Table of Contents

1. [What Problem Does This Solve?](#what-problem-does-this-solve)
2. [The Core Idea — Symbol + Extra Bits](#the-core-idea--symbol--extra-bits)
3. [Worked Example — Step by Step](#worked-example--step-by-step)
4. [The DEFLATE Symbol Space](#the-deflate-symbol-space)
5. [Length Lookup Tables](#length-lookup-tables)
6. [Distance Lookup Tables](#distance-lookup-tables)
7. [How the Code Works — Line by Line](#how-the-code-works--line-by-line)
8. [Output Format](#output-format)
9. [Why This Encoding Is Efficient](#why-this-encoding-is-efficient)
10. [Where This Fits in DEFLATE](#where-this-fits-in-deflate)

---

## What Problem Does This Solve?

Stage 1 (LZ77) gave us a stream of **literals** and **matches**. A match looks like `('match', length=44, distance=45)` — meaning "go back 45 bytes and copy 44 bytes."

But there's a problem: **how do we store these numbers efficiently?**

- Lengths range from 3 to 258 — that's 256 possible values
- Distances range from 1 to 32,768 — that's 32,768 possible values

If we gave every possible length its own symbol, we'd need 256 length symbols. If we gave every distance its own symbol, we'd need 32,768 distance symbols. That's way too many symbols — Huffman coding (Stage 3) works best with a smaller, manageable set.

**Stage 2 solves this** by grouping similar values into **ranges**. Each range gets one small symbol code, and a few **extra bits** pinpoint the exact value within that range.

> **Think of it like street addresses:** Instead of giving every house a unique name, we give each street a name (the **symbol**) and each house a number (the **extra bits**). The street name is short and memorable; the house number provides the precision.

---

## The Core Idea — Symbol + Extra Bits

DEFLATE uses a two-part encoding for lengths and distances:

```
┌─────────────────────────────────────────────────┐
│         DEFLATE Two-Part Encoding               │
│                                                 │
│   Raw Value ──▶ SYMBOL + EXTRA BITS             │
│                                                 │
│   • SYMBOL:     Identifies a range of values    │
│                 (gets Huffman-coded in Stage 3) │
│                                                 │
│   • EXTRA BITS: Pinpoints the exact value       │
│                 within that range               │
│                (stored as-is, NOT Huffman-coded)│
└─────────────────────────────────────────────────┘
```

**Why split it this way?**

- The **symbol** goes through Huffman coding, so frequently-used ranges get shorter codes
- The **extra bits** are raw binary — no overhead, just the minimum bits needed
- Small, common values (like length=3 or distance=1) need **zero** extra bits — just the symbol
- Large, rare values (like length=200 or distance=20,000) need more extra bits — but they rarely occur, so it doesn't matter

This is a clever trade-off: we use a small number of symbols (29 for lengths, 30 for distances) that Huffman can compress well, plus a handful of raw bits for precision.

---

## Worked Example — Step by Step

Let's trace what happens to the LZ77 output from our `ABCABCABC` example:

### Stage 1 output (what we receive):

```
('literal', 65)       ← 'A'
('literal', 66)       ← 'B'
('literal', 67)       ← 'C'
('match', 6, 3)       ← length=6, distance=3
```

### Processing each token:

#### Token 1: `('literal', 65)` → 'A'

Literals pass through unchanged. The byte value 65 is already a valid DEFLATE symbol (symbols 0–255 are reserved for literal bytes).

**Output:** `('literal', 65)`

#### Token 2: `('literal', 66)` → 'B'

Same — pass through.

**Output:** `('literal', 66)`

#### Token 3: `('literal', 67)` → 'C'

Same — pass through.

**Output:** `('literal', 67)`

#### Token 4: `('match', 6, 3)` → length=6, distance=3

This is where the conversion happens. We need to encode **two** values:

**Encoding the length (6):**

1. Look through the `length_base` table: `[3, 4, 5, 6, 7, 8, ...]`
2. Length 6 matches index 3 (base=6, extra bits=0)
3. Symbol = 3 + 257 = **260**
4. Extra bits needed: **0** (the symbol covers exactly one value)
5. Extra bits string: `''` (empty)

**Encoding the distance (3):**

1. Look through the `distance_base` table: `[1, 2, 3, 4, ...]`
2. Distance 3 matches index 2 (base=3, extra bits=0)
3. Symbol = **2**
4. Extra bits needed: **0**
5. Extra bits string: `''` (empty)

**Output:** `('match', 260, '', 2, '')`

#### End of block:

After processing all tokens, we append the end-of-block marker.

**Output:** `('end', 256)`

### Complete Stage 2 Output:

```python
[
    ('literal', 65),            # 'A' — symbol 65
    ('literal', 66),            # 'B' — symbol 66
    ('literal', 67),            # 'C' — symbol 67
    ('match', 260, '', 2, ''),  # length symbol 260, distance symbol 2, no extra bits
    ('end', 256)                # end-of-block marker
]
```

### A More Complex Example: length=15, distance=100

**Encoding the length (15):**

1. Scan `length_base`: at index 6, base=9? No. At index 8, base=11, extra=1. Range = [11, 12]. No. At index 9, base=13, extra=1. Range = [13, 14]. No. At index 10, base=15, extra=1. Range = [15, 16]. **Yes!**
2. Symbol = 10 + 257 = **267**
3. Extra bits = 1 bit needed
4. Offset from base = 15 − 15 = 0
5. Extra bits string: `'0'`

**Encoding the distance (100):**

1. Scan `distance_base`: at index 13, base=97, extra=5. Range = [97, 128]. **Yes!**
2. Symbol = **13**
3. Extra bits = 5 bits needed
4. Offset from base = 100 − 97 = 3
5. Extra bits string: `'00011'` (3 in 5-bit binary)

**Output:** `('match', 267, '0', 13, '00011')`

---

## The DEFLATE Symbol Space

DEFLATE combines literals, lengths, and the end marker into a **single unified symbol space** called the "literal/length alphabet":

```
┌───────────────────────────────────────────────────┐
│           DEFLATE Literal/Length Alphabet         │
│                                                   │
│   Symbols 0–255:     Literal byte values          │
│                      (raw data, no compression)   │
│                                                   │
│   Symbol 256:        End-of-block marker          │
│                      (signals "stop decoding")    │
│                                                   │
│   Symbols 257–285:   Length codes                 │
│                      (match lengths 3–258)        │
│                                                   │
│   Total: 286 symbols in one alphabet              │
└───────────────────────────────────────────────────┘
```

Distances have their own **separate alphabet** with symbols 0–29 (30 symbols total).

This unified alphabet is important because in Stage 3, all these symbols (literals, end marker, and length codes) share a **single Huffman tree**. This means if a file has very few matches, the length symbols get long Huffman codes (they're rare = more bits), and if a file has many matches, literal symbols might get longer codes. The tree adapts automatically.

---

## Length Lookup Tables

These tables live in `utilities/util_2.py` and define how raw lengths (3–258) map to symbols (257–285).

| Index (i) | Symbol (i+257) | Base Length | Extra Bits | Range Covered |
|---|---|---|---|---|
| 0 | 257 | 3 | 0 | 3 |
| 1 | 258 | 4 | 0 | 4 |
| 2 | 259 | 5 | 0 | 5 |
| 3 | 260 | 6 | 0 | 6 |
| 4 | 261 | 7 | 0 | 7 |
| 5 | 262 | 8 | 0 | 8 |
| 6 | 263 | 9 | 0 | 9 |
| 7 | 264 | 10 | 0 | 10 |
| 8 | 265 | 11 | 1 | 11–12 |
| 9 | 266 | 13 | 1 | 13–14 |
| 10 | 267 | 15 | 1 | 15–16 |
| 11 | 268 | 17 | 1 | 17–18 |
| 12 | 269 | 19 | 2 | 19–22 |
| 13 | 270 | 23 | 2 | 23–26 |
| 14 | 271 | 27 | 2 | 27–30 |
| 15 | 272 | 31 | 2 | 31–34 |
| 16 | 273 | 35 | 3 | 35–42 |
| 17 | 274 | 43 | 3 | 43–50 |
| 18 | 275 | 51 | 3 | 51–58 |
| 19 | 276 | 59 | 3 | 59–66 |
| 20 | 277 | 67 | 4 | 67–82 |
| 21 | 278 | 83 | 4 | 83–98 |
| 22 | 279 | 99 | 4 | 99–114 |
| 23 | 280 | 115 | 4 | 115–130 |
| 24 | 281 | 131 | 5 | 131–162 |
| 25 | 282 | 163 | 5 | 163–194 |
| 26 | 283 | 195 | 5 | 195–226 |
| 27 | 284 | 227 | 5 | 227–257 |
| 28 | 285 | 258 | 0 | 258 |

**Notice the pattern:** Small lengths (3–10) each get their own symbol with 0 extra bits — they're very precise. As lengths get larger, each symbol covers a wider range and needs more extra bits. This is intentional — small lengths are far more common, so they get the most efficient encoding.

---

## Distance Lookup Tables

Same concept, but for distances (1–32,768) mapping to symbols (0–29).

| Index/Symbol | Base Distance | Extra Bits | Range Covered |
|---|---|---|---|
| 0 | 1 | 0 | 1 |
| 1 | 2 | 0 | 2 |
| 2 | 3 | 0 | 3 |
| 3 | 4 | 0 | 4 |
| 4 | 5 | 1 | 5–6 |
| 5 | 7 | 1 | 7–8 |
| 6 | 9 | 2 | 9–12 |
| 7 | 13 | 2 | 13–16 |
| 8 | 17 | 3 | 17–24 |
| 9 | 25 | 3 | 25–32 |
| 10 | 33 | 4 | 33–48 |
| 11 | 49 | 4 | 49–64 |
| 12 | 65 | 5 | 65–96 |
| 13 | 97 | 5 | 97–128 |
| 14 | 129 | 6 | 129–192 |
| 15 | 193 | 6 | 193–256 |
| 16 | 257 | 7 | 257–384 |
| 17 | 385 | 7 | 385–512 |
| 18 | 513 | 8 | 513–768 |
| 19 | 769 | 8 | 769–1024 |
| 20 | 1025 | 9 | 1025–1536 |
| 21 | 1537 | 9 | 1537–2048 |
| 22 | 2049 | 10 | 2049–3072 |
| 23 | 3073 | 10 | 3073–4096 |
| 24 | 4097 | 11 | 4097–6144 |
| 25 | 6145 | 11 | 6145–8192 |
| 26 | 8193 | 12 | 8193–12288 |
| 27 | 12289 | 12 | 12289–16384 |
| 28 | 16385 | 13 | 16385–24576 |
| 29 | 24577 | 13 | 24577–32768 |

**Same pattern as lengths:** Small distances (1–4) have dedicated symbols with 0 extra bits. The ranges double in size every 2 symbols, and the extra bits increase by 1. The largest distances need 13 extra bits.

---

## How the Code Works — Line by Line

### The Main Function: `stage2_compress(data)` in `stage2.py`

```python
s1_compressed = stage1compress(data)   # Run LZ77 first to get literals/matches
s2_compressed = []                     # Build the output list
```

#### Processing Literals

```python
if item[0] == 'literal':
    s2_compressed.append(('literal', item[1]))
```

Literals need no conversion. A byte value like 65 (`'A'`) is already a valid DEFLATE symbol (symbols 0–255 are literal bytes). We just pass it through.

#### Processing Matches

```python
elif item[0] == 'match':
    length_symbol, length_extra_bits = get_length_symbol(item[1])
    distance_symbol, distance_extra_bits = get_distance_symbol(item[2])
    s2_compressed.append(('match', length_symbol, length_extra_bits,
                                   distance_symbol, distance_extra_bits))
```

Each match has a raw length and raw distance. We convert each using the lookup tables:

1. `get_length_symbol(length)` → scans `length_base` to find which symbol covers this length, computes the extra bits as the offset from the base
2. `get_distance_symbol(distance)` → same for distances using `distance_base`

#### The End-of-Block Marker

```python
s2_compressed.append(('end', 256))
```

Symbol 256 is the **end-of-block marker**. It tells the decompressor: "this block of compressed data is finished, stop decoding." Without this, the decompressor wouldn't know when the data ends.

### The Lookup Functions in `utilities/util_2.py`

#### `get_length_symbol(length)`

```python
for i in range(len(length_base)):
    if length >= length_base[i] and length <= length_base[i] + pow(2, length_extra[i]) - 1:
        length_symbol = i + 257
        return length_symbol, encode_extra_bits(length - length_base[i], length_extra[i])
```

1. Scan through the `length_base` array
2. For each entry, check if `length` falls within its range: `[base, base + 2^extra - 1]`
3. When found: symbol = index + 257, extra bits = offset from base encoded in binary
4. The `+ 257` offset is because DEFLATE length symbols start at 257 (0–255 are literals, 256 is end)

#### `get_distance_symbol(distance)`

Same logic but for distances. Distance symbols start at 0 (they use a separate alphabet from literals/lengths).

#### `encode_extra_bits(bits, num_bits)`

```python
if num_bits == 0:
    return ''
return format(bits, '0' + str(num_bits) + 'b')
```

Converts an integer offset into a fixed-width binary string. For example:
- `encode_extra_bits(0, 0)` → `''` (no extra bits needed)
- `encode_extra_bits(1, 1)` → `'1'`
- `encode_extra_bits(3, 5)` → `'00011'`

---

## Output Format

Stage 2 produces a list of tuples with three possible types:

```python
[
    ('literal', 84),                           # 'T' — symbol 84, no conversion needed
    ('literal', 104),                          # 'h' — symbol 104
    ('match', 274, '001', 10, '1100'),         # len_sym=274, 3 extra bits, dist_sym=10, 4 extra bits
    ('literal', 10),                           # newline
    ('match', 267, '0', 2, ''),                # len_sym=267, 1 extra bit, dist_sym=2, no extra bits
    ('end', 256)                               # end-of-block marker
]
```

| Tuple Type | Fields | Meaning |
|---|---|---|
| `('literal', V)` | V = byte value (0–255) | Raw byte, also used as symbol 0–255 |
| `('match', LS, LE, DS, DE)` | LS = length symbol (257–285), LE = length extra bits string, DS = distance symbol (0–29), DE = distance extra bits string | Back-reference with DEFLATE-encoded length and distance |
| `('end', 256)` | Always 256 | End-of-block marker |

This output feeds directly into **Stage 3** (Huffman coding), which will assign variable-length binary codes to each symbol based on how frequently it appears.

---

## Why This Encoding Is Efficient

### 1. Fewer Symbols = Better Huffman Compression

Without this stage, we'd need 256 length symbols and 32,768 distance symbols. That's too many for Huffman to work well — it can't distinguish "common" from "rare" when there are tens of thousands of symbols.

With this stage, we reduce to **29 length symbols** and **30 distance symbols**. Huffman can now give short codes to common symbols and long codes to rare ones, achieving much better compression.

### 2. Common Values Are Cheapest

Small lengths (3–10) and small distances (1–4) are the most common in real-world data. These get:
- Their own dedicated symbol (0 extra bits)
- Short Huffman codes (because they're frequent)

A length of 3 might cost only 2–3 bits total. A length of 200 might cost 10+ bits — but it almost never occurs.

### 3. Extra Bits Are "Free" of Huffman Overhead

The extra bits are stored as raw binary, not Huffman-coded. This is efficient because they represent uniform randomness within a range — Huffman coding wouldn't help compress them anyway. Mixing Huffman (for the symbol) with raw bits (for the offset) gives the best of both worlds.

### 4. Logarithmic Growth

The number of extra bits grows **logarithmically** with the value:
- Distances 1–4: 0 extra bits
- Distances 5–8: 1 extra bit
- Distances 9–16: 2 extra bits
- ...
- Distances 16385–32768: 13 extra bits

This means even the largest distance (32,768) needs only 13 extra bits — not 15 (which log₂(32768) would require if we encoded it directly). The symbol absorbs part of the information.

---

## Where This Fits in DEFLATE

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DEFLATE Pipeline                              │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│  │ Stage 1  │───▶│ Stage 2  │───▶│ Stage 3  │───▶│ Stage 4  │        │
│  │  LZ77    │    │ DEFLATE  │    │ Huffman  │    │ Bitstream│        │
│  │          │    │ Symbols  │    │ Coding   │    │ Packing  │        │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                      │
│  Raw bytes ──▶ Literals/Matches ──▶ Symbol codes ──▶ Huffman ──▶     │
│                                     + extra bits    codes     bits   │
└──────────────────────────────────────────────────────────────────────┘
```

- **Stage 1 (LZ77):** Finds repeated sequences → outputs literals and back-references
- **Stage 2 (this stage):** Converts raw lengths/distances into compact symbol codes + extra bits
- **Stage 3:** Builds Huffman trees to assign shorter binary codes to more frequent symbols
- **Stage 4:** Packs everything into a compact bitstream (the final compressed file)

Stage 2 is the bridge between the **pattern-finding** world of LZ77 and the **entropy-coding** world of Huffman. It restructures the data so that Huffman can work on a manageable set of symbols, while the extra bits carry the remaining precision without any overhead.

---
