# Stage 3: Canonical Huffman Coding

## Table of Contents

1. [What Problem Does This Solve?](#what-problem-does-this-solve)
2. [The Core Idea of Huffman Coding](#the-core-idea-of-huffman-coding)
3. [Why Canonical Huffman Codes?](#why-canonical-huffman-codes)
4. [Worked Example — Canonical Code Generation](#worked-example--canonical-code-generation)
5. [The Two Huffman Trees in DEFLATE](#the-two-huffman-trees-in-deflate)
6. [How the Code Works — Line by Line](#how-the-code-works--line-by-line)
7. [Output Format](#output-format)
8. [Why Huffman Coding Achieves Compression](#why-huffman-coding-achieves-compression)
9. [Where This Fits in DEFLATE](#where-this-fits-in-deflate)

---

## What Problem Does This Solve?

After Stage 2, we have a stream of symbols: literal bytes (0–255), length codes (257–285), distance codes (0–29), and the end marker (256). But how do we store these symbols as bits in a file?

**The naive approach:** Use a fixed number of bits per symbol. With 286 possible literal/length symbols, we'd need 9 bits each (since 2⁸ = 256 < 286 ≤ 512 = 2⁹). Every symbol costs exactly 9 bits, whether it appears once or a thousand times.

**The problem:** In real data, some symbols are far more common than others. The letter `'e'` might appear 50 times while `'z'` appears twice. Under fixed-width encoding, both cost 9 bits — that's wasteful.

**Huffman coding solves this** by assigning:
- **Short codes** to frequent symbols (e.g., `'e'` → `0010`, just 4 bits)
- **Long codes** to rare symbols (e.g., `'z'` → `110111`, 6 bits)

The result: the total number of bits is minimized. Huffman coding is provably optimal among prefix-free codes — no other variable-length code can produce a shorter output for the same frequency distribution.

---

## The Core Idea of Huffman Coding

Huffman coding builds a **binary tree** from the bottom up, based on symbol frequencies:

1. Start with each symbol as a standalone leaf node, weighted by its frequency
2. Repeatedly merge the **two lightest** nodes into a parent node
3. The parent's weight = sum of its children's weights
4. Left branch = `0`, right branch = `1`
5. Each symbol's code = the path from root to its leaf

This guarantees the **prefix-free property**: no code is the start of another code. The decompressor can read bits one-by-one and know exactly when each symbol ends — no ambiguity, no separators needed.

### Why This Works

The key insight is that we merge the **least frequent** symbols first. This pushes them deeper into the tree (longer codes), while frequent symbols stay near the root (shorter codes). The math works out so that this greedy strategy is globally optimal.

---

## Why Canonical Huffman Codes?

The tree above gives us **one valid** set of codes, but there are many others. We could swap left and right at any node and get equally valid codes. For example, A could be `111` instead of `000`.

This is a problem for compression: the decompressor needs to know **which exact codes** we used. If we stored the full tree, that would waste space in the file header.

**Canonical Huffman coding** solves this by adding constraints:

> Given the same set of code **lengths**, there is exactly **one** valid canonical code assignment.

The rules are:
1. **Shorter codes** are numerically smaller than longer codes
2. **Within the same length**, codes are assigned in **ascending symbol order**
3. The starting code for each length is deterministically computed

This means we only need to transmit the **lengths** (e.g., "A=3, B=3, C=2, D=2, E=2") and both sides can independently reconstruct the exact same codes. Lengths are much cheaper to store than a full tree.

---

## Worked Example — Canonical Code Generation

Using the lengths from our tree: A=3, B=3, C=2, D=2, E=2

### Step 1: Count symbols at each length

| Length | Count | Symbols |
|---|---|---|
| 2 | 3 | C, D, E |
| 3 | 2 | A, B |

### Step 2: Compute starting codes

The algorithm from RFC 1951:

```
next_code[1] = 0
next_code[2] = (next_code[1] + count[1]) << 1 = (0 + 0) << 1 = 0
next_code[3] = (next_code[2] + count[2]) << 1 = (0 + 3) << 1 = 6
```

So: 2-bit codes start at `0` (binary `00`), 3-bit codes start at `6` (binary `110`).

### Step 3: Assign codes in symbol order

| Symbol | Length | Code (decimal) | Code (binary) |
|---|---|---|---|
| C | 2 | 0 | `00` |
| D | 2 | 1 | `01` |
| E | 2 | 2 | `10` |
| A | 3 | 6 | `110` |
| B | 3 | 7 | `111` |

### Verify prefix-free property

No code is a prefix of another:
- `00`, `01`, `10` are all distinct 2-bit codes
- `110`, `111` start with `11`, which isn't any 2-bit code ✓

The codes are different from the non-canonical tree, but produce the **same compression ratio** because the **lengths** are the same.

---

## The Two Huffman Trees in DEFLATE

DEFLATE builds **two separate** Huffman trees from the Stage 2 token stream:

### 1. Literal/Length Tree (286 possible symbols)

Covers three types of symbols from a single shared alphabet:

| Symbol Range | Meaning |
|---|---|
| 0–255 | Literal byte values (raw data) |
| 256 | End-of-block marker |
| 257–285 | Length codes (from Stage 2) |

All share one tree, so the Huffman code for `'e'` (symbol 101) and the code for "length 3" (symbol 257) come from the same tree. This is efficient because it lets the decompressor read a single Huffman code and immediately know whether it's a literal, a match, or the end of the block.

### 2. Distance Tree (30 possible symbols)

| Symbol Range | Meaning |
|---|---|
| 0–29 | Distance codes (from Stage 2) |

Distances have their own separate tree because they only appear after a length code. The decompressor knows to switch to the distance tree right after reading a length symbol (257–285).

### Why Two Trees Instead of One?

Literal/length symbols and distance symbols have very different frequency distributions. Merging them into one tree would produce suboptimal codes. Keeping them separate lets each tree adapt to its own frequency pattern.

---

## How the Code Works — Line by Line

### Counting Frequencies: `get_frequencies()` in `utilities/util_3.py`

```python
lit_freq = [0] * 286    # One counter for each possible literal/length symbol
dist_freq = [0] * 30    # One counter for each possible distance symbol
```

Walks through the Stage 2 output and increments the appropriate counter:
- `'literal'` → `lit_freq[byte_value] += 1`
- `'match'` → `lit_freq[length_symbol] += 1` and `dist_freq[distance_symbol] += 1`
- `'end'` → `lit_freq[256] += 1`

### Building the Huffman Tree: `build_huffman_tree()` in `utilities/util_3.py`

Uses Python's `heapq` (min-heap) as a priority queue:

```python
heap = [(weight, symbol, [[symbol, ""]]) for symbol, weight in enumerate(freq) if weight > 0]
```

Each heap entry holds: `(weight, min_symbol_tiebreaker, list_of_[symbol, code_string]_pairs)`.

The merge loop:
```python
while len(heap) > 1:
    w1, m1, p1 = heapq.heappop(heap)     # Pop lightest
    w2, m2, p2 = heapq.heappop(heap)     # Pop second lightest
    for pair in p1: pair[1] = '0' + pair[1]   # Left branch = '0'
    for pair in p2: pair[1] = '1' + pair[1]   # Right branch = '1'
    heapq.heappush(heap, (w1 + w2, min(m1, m2), p1 + p2))  # Push merged
```

After the loop, `heap[0][2]` contains all `[symbol, code_string]` pairs.

### Extracting Lengths: `get_huffman_lengths()` in `utilities/util_3.py`

```python
lengths[symbol] = max(len(code), 1)
```

Takes the code strings from `build_huffman_tree()` and records just their lengths. Uses `max(..., 1)` to ensure every present symbol gets at least 1 bit.

### Generating Canonical Codes: `get_huffman_codes()` in `utilities/util_3.py`

This is the RFC 1951 algorithm in three steps:

**Step 1 — Count lengths:**
```python
count = [0] * 16           # DEFLATE limits codes to 15 bits max
for length in lengths:
    count[length] += 1
count[0] = 0               # Don't count absent symbols
```

**Step 2 — Compute starting codes:**
```python
code = 0
for bits in range(1, 16):
    code = (code + count[bits - 1]) << 1
    next_code[bits] = code
```

The left-shift (`<< 1`) ensures that moving from length N to length N+1 doubles the code space, maintaining the prefix-free property.

**Step 3 — Assign codes:**
```python
for symbol in range(len(lengths)):
    if lengths[symbol] != 0:
        symbol_code[symbol] = (next_code[lengths[symbol]], lengths[symbol])
        next_code[lengths[symbol]] += 1
```

Symbols with the same length get consecutive codes, assigned in ascending symbol order.

### The Main Function: `stage3_compress()` in `stage3.py`

```python
lit_freq, dist_freq = get_frequencies(s2_compressed)    # Count
lit_codes = get_huffman_codes(lit_freq)                  # Build lit/length codes
dist_codes = get_huffman_codes(dist_freq)                # Build distance codes
```

Then walks through each token and attaches the Huffman code:
- **Literals:** Look up `lit_codes[byte_value]` → append `(code, bit_length)`
- **Matches:** Look up `lit_codes[length_symbol]` and `dist_codes[distance_symbol]` → append both
- **End:** Look up `lit_codes[256]` → append `(code, bit_length)`

---

## Output Format

Stage 3 produces a list of tuples with Huffman codes attached:

```python
[
    ('literal', 101, 0b0010, 4),
    #  symbol='e', Huffman code=0010, 4 bits long

    ('match', 257, '', 3, '',
             0b0101, 4,      # length symbol 257 → Huffman code 0101 (4 bits)
             0b1100, 4),     # distance symbol 3 → Huffman code 1100 (4 bits)

    ('end', 256, 0b1111000, 7),
    #  end-of-block, Huffman code=1111000, 7 bits long
]
```

| Tuple Type | Fields |
|---|---|
| `('literal', sym, code, bits)` | sym = byte value, code = Huffman code integer, bits = code length |
| `('match', len_sym, len_extra, dist_sym, dist_extra, lh_code, lh_bits, dh_code, dh_bits)` | Stage 2 fields + Huffman codes for both length and distance symbols |
| `('end', 256, code, bits)` | End marker + its Huffman code |

This output feeds into **Stage 4**, which reads the Huffman codes and extra bits and packs them into a compact bitstream.

---

## Why Huffman Coding Achieves Compression

### The Information Theory Perspective

Claude Shannon proved in 1948 that the minimum average bits per symbol is the **entropy**:

```
H = -Σ p(x) × log₂(p(x))
```

where `p(x)` is the probability of symbol `x`. Huffman coding gets very close to this theoretical minimum — within 1 bit per symbol of the entropy.

### A Concrete Example

Consider a file where `' '` (space) appears 14 times and `'T'` appears once out of 141 tokens:

| Symbol | Frequency | Probability | Fixed (9 bits) | Huffman |
|---|---|---|---|---|
| `' '` | 14 | 9.9% | 9 bits | 3 bits |
| `'T'` | 1 | 0.7% | 9 bits | 7 bits |

Space saves 6 bits per occurrence × 14 occurrences = **84 bits saved** just from spaces. `'T'` costs 2 bits more per occurrence × 1 occurrence = **2 bits lost**. Net: **82 bits saved** from just two symbols.

Multiply this across all symbols and you get significant compression.

### What Huffman Cannot Compress

- **Uniform distribution:** If all symbols are equally frequent, Huffman codes are all the same length — no savings over fixed-width
- **Already compressed data:** The symbol frequencies are already flat — Huffman can't improve them
- **Very small files:** The overhead of storing the code lengths in the header can exceed the savings

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

- **Stage 1 (LZ77):** Removes sequential redundancy — replaces repeated sequences with back-references
- **Stage 2 (Symbols):** Converts raw lengths/distances into compact symbol codes + extra bits
- **Stage 3 (this stage):** Removes statistical redundancy — assigns shorter codes to frequent symbols
- **Stage 4:** Packs the Huffman codes and extra bits into a compact bitstream, adding a header with the code lengths so the decompressor can rebuild the Huffman trees

Together, Stages 1 and 3 are complementary:
- **LZ77** handles patterns (sequences that repeat verbatim)
- **Huffman** handles statistics (symbols that appear more or less often)

Neither alone achieves great compression, but combined they are very effective — which is why DEFLATE (and by extension gzip, PNG, ZIP) is one of the most widely used compression formats in the world.

---
