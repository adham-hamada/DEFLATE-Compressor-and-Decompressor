# Stage 1: LZ77 Compression

## Table of Contents

1. [What Problem Does This Solve?](#what-problem-does-this-solve)
2. [The Core Idea of LZ77](#the-core-idea-of-lz77)
3. [Worked Example — Step by Step](#worked-example--step-by-step)
4. [Key Parameters and Why They Matter](#key-parameters-and-why-they-matter)
5. [Data Structures Used](#data-structures-used)
6. [How the Code Works — Line by Line](#how-the-code-works--line-by-line)
7. [Output Format](#output-format)
8. [Why LZ77 Achieves Compression](#why-lz77-achieves-compression)
9. [Limitations and Trade-offs](#limitations-and-trade-offs)
10. [Where This Fits in DEFLATE](#where-this-fits-in-deflate)

---

## What Problem Does This Solve?

Real-world data is full of repetition. A text file might repeat the word "the" hundreds of times. An image might have large areas of the same color. Storing every single byte as-is wastes space.

**LZ77** (named after its inventors Abraham Lempel and Jacob Ziv, published in 1977) is a **lossless compression algorithm** that eliminates this redundancy. "Lossless" means we can perfectly reconstruct the original data — not a single byte is lost.

The fundamental insight is:

> **If you've already seen a sequence of bytes before, don't store it again. Instead, store a short note saying "go back X bytes and copy Y bytes from there."**

This "short note" is called a **back-reference**, and it's typically much smaller than the data it replaces.

---

## The Core Idea of LZ77

LZ77 slides a window over the input data from left to right. At every position, it asks:

1. **"Have I seen the bytes starting here before?"**
2. If yes → emit a **match**: `(length, distance)` meaning *"copy `length` bytes from `distance` bytes ago"*
3. If no → emit a **literal**: just store the raw byte as-is

That's the entire algorithm. Everything else is optimization.

### The Two Types of Output Tokens

| Token Type | Meaning | Example |
|---|---|---|
| **Literal** | A single byte, stored as-is | `('literal', 65)` → the byte `A` |
| **Match** | A back-reference to earlier data | `('match', 6, 3)` → go back 3, copy 6 bytes |

---

## Worked Example — Step by Step

Let's compress the string: **`ABCABCABC`**

We process it byte by byte:

### Pass 1: Position 0 → `A`
- We look in our history for a match. History is empty.
- **Emit:** `('literal', A)`

### Pass 2: Position 1 → `B`
- History: `A`. No match for `B...`.
- **Emit:** `('literal', B)`

### Pass 3: Position 2 → `C`
- History: `AB`. No 3-byte match starting with `C`.
- **Emit:** `('literal', C)`

### Pass 4: Position 3 → `A`
- We look at the 3 bytes starting here: `ABC`.
- We search our history and find `ABC` starting at position 0!
- Distance = 3 − 0 = **3** (go back 3 bytes)
- We try to extend: position 0 has `ABCABC...` and position 3 has `ABCABC...`
- The match extends for **6 bytes** (all remaining data matches)
- **Emit:** `('match', length=6, distance=3)`

### Final Output

```
Input:  A  B  C  A  B  C  A  B  C     (9 bytes)
Output: L  L  L  M(6,3)               (3 literals + 1 match = 4 tokens)
```

Instead of storing 9 bytes, we store 3 literals and one compact pointer. The decompressor reads those 4 tokens and perfectly reconstructs the original 9 bytes.

> **Note:** A match of `(length=6, distance=3)` means "go back 3 and copy 6." But wait — 6 > 3, so we're copying more bytes than the distance! This is valid and common. The decompressor copies byte-by-byte: it copies positions 0,1,2, then 3,4,5 (which are the bytes it just wrote). This naturally handles repeating patterns.

---

## Key Parameters and Why They Matter

These constants are defined in `utilities/util_1.py`:

| Constant | Value | Purpose |
|---|---|---|
| `WINDOW_SIZE` | 32,768 (32 KB) | Maximum distance we can look back. Matches farther away than this are not allowed. |
| `MIN_MATCH` | 3 | Minimum match length. Matches shorter than 3 bytes aren't worth encoding (the pointer itself costs space). |
| `MAX_MATCH` | 258 | Maximum match length. This is a DEFLATE specification limit. |
| `MAX_CANDIDATES` | 64 | Maximum number of hash table candidates to check per position. Limits search time. |

### Why MIN_MATCH = 3?

A back-reference needs to store two numbers: length and distance. In the DEFLATE format, this costs at least ~2-3 bytes. If we allowed matches of length 1 or 2, the pointer would be *bigger* than just storing the raw bytes. So matches shorter than 3 bytes are not worth it.

### Why WINDOW_SIZE = 32,768?

This is defined by the DEFLATE specification (RFC 1951). A larger window means:
- ✅ More opportunities to find matches (better compression)
- ❌ More memory needed
- ❌ Larger distance values to encode

32 KB is the standard trade-off chosen by DEFLATE.

### Why MAX_MATCH = 258?

Also a DEFLATE specification limit. The length is encoded using specific symbol codes (in Stage 2), and the encoding scheme supports lengths from 3 to 258.

### Why MAX_CANDIDATES = 64?

This is a **performance optimization**. Many positions in a file might start with the same 3 bytes (e.g., `the` in English text). Checking all of them would be slow. We only check the 64 most recent ones because:
- Recent matches are more likely to still be within the sliding window
- Recent matches tend to have shorter distances (which compress better)

---

## Data Structures Used

### 1. The Hash Table (`table`)

```python
table = {}
# Example contents:
# {
#     (65, 66, 67): [0, 3, 6],    # "ABC" was seen at positions 0, 3, 6
#     (32, 116, 104): [15, 60],   # " th" was seen at positions 15, 60
# }
```

**What it is:** A Python dictionary mapping a **3-byte tuple** (the first 3 bytes of a potential match) to a **list of positions** where that 3-byte sequence was seen.

**Why we need it:** Without this, finding matches would require scanning the entire 32 KB window byte-by-byte at every position — O(n × window_size) which is extremely slow. The hash table makes lookups O(1) on average.

**How it works:**
1. Take 3 consecutive bytes, e.g., `data[i], data[i+1], data[i+2]`
2. Form a tuple: `(65, 66, 67)` for "ABC"
3. Look it up in the table to get all positions where "ABC" appeared before
4. After processing a position, add it to the table for future lookups

### 2. The Sliding Window (`sliding_window` in utilities/util_1.py)

```python
sliding_window = np.zeros(WINDOW_SIZE, dtype=np.uint8)  # 32,768 bytes
current_pos = 0
```

**What it is:** A circular buffer (ring buffer) of 32,768 bytes that tracks the most recently processed bytes. Managed in `utilities/util_1.py`.

**Why it's circular:** When `current_pos` reaches 32,768, it wraps back to 0 using modulo: `current_pos = (current_pos + 1) % WINDOW_SIZE`. Old data gets overwritten, which is fine because we only look back up to `WINDOW_SIZE` bytes.

**Why we need it:** The sliding window is primarily used during **decompression**. When the decompressor encounters a match token `(length=5, distance=10)`, it needs to look back 10 bytes in the window and copy 5 bytes. During compression, we feed bytes into it via `literal()` to keep it synchronized with what the decompressor will have.

---

## How the Code Works — Line by Line

### Initialization (lines 26–42)

```python
reset_state()    # Zero out the sliding window and reset position to 0
table = {}       # Empty hash table — no patterns seen yet
compressed_data = []  # Output list we'll build up
i = 0            # Start at the beginning of the input
```

### The Main Loop (lines 44–88)

For every position `i` in the input data:

#### Step 1: Search for matches (lines 48–70)

```python
if i + MIN_MATCH <= len(data):          # Need at least 3 bytes remaining
    key = (data[i], data[i+1], data[i+2])  # Hash key = next 3 bytes
    candidates = table.get(key, [])     # Where was this 3-byte sequence seen before?
```

Then for each candidate position (up to the 64 most recent):

```python
distance = i - candidate               # How far back is this candidate?
if distance <= 0 or distance > WINDOW_SIZE:
    continue                            # Skip if invalid
```

Extend the match as far as possible:

```python
length = 0
max_len = min(MAX_MATCH, len(data) - i)
while length < max_len and data[candidate + length] == data[i + length]:
    length += 1                         # Keep going while bytes match
```

Keep the best match (longest, or same length but closer):

```python
if length > best_length or (length == best_length and distance < best_distance):
    best_length = length
    best_distance = distance
```

#### Step 2: Emit output (lines 72–88)

**If a good match was found** (length ≥ 3):
```python
compressed_data.append(('match', best_length, best_distance))
for j in range(best_length):
    add_to_table(i + j)   # Register all positions within the match
    literal(data[i + j])  # Feed bytes into sliding window
i += best_length           # Skip ahead past the entire match
```

**If no match** (or match too short):
```python
compressed_data.append(('literal', data[i]))
add_to_table(i)        # Register this position in hash table
literal(data[i])       # Feed byte into sliding window
i += 1                 # Move to next byte
```

### Why We Call `add_to_table()` Inside Matches

Even when we emit a match, we still register every position within that match in the hash table. This is important because **future bytes might want to match against something that appeared inside this match region**. If we skipped it, we'd miss compression opportunities.

### Why We Call `literal()` Inside Matches

Even though we emitted a match (not a literal), we still feed every byte into the sliding window via `literal()`. This keeps the sliding window synchronized — the decompressor will process these bytes too, and both sides must agree on the window contents.

---

## Output Format

The function returns a Python list of tuples:

```python
[
    ('literal', 84),            # Raw byte: 'T'
    ('literal', 104),           # Raw byte: 'h'
    ('literal', 101),           # Raw byte: 'e'
    ('match', 44, 45),          # Copy 44 bytes from 45 bytes ago
    ('literal', 10),            # Raw byte: newline
    ...
]
```

This output is **not the final compressed file**. It's an intermediate representation that gets passed to **Stage 2** (DEFLATE symbol encoding), which converts lengths and distances into standardized symbol codes, then to **Stage 3** (Huffman coding) and **Stage 4** (bitstream packing).

---

## Why LZ77 Achieves Compression

LZ77 works because of a property of real-world data called **statistical redundancy**:

1. **Natural language** repeats words, phrases, and structures constantly
2. **Source code** repeats keywords, variable names, and patterns
3. **Binary files** often have repeated byte sequences (headers, padding, etc.)

The compression ratio depends on how repetitive the data is:

| Input Type | Expected Ratio | Why |
|---|---|---|
| Repeated text (`ABCABCABC...`) | Very high (>80%) | Almost everything becomes matches |
| English prose | Good (40-60%) | Common words and phrases repeat |
| Random bytes | None (0%) | No patterns to exploit |
| Already compressed data | None or negative | Patterns already removed |

---

## Limitations and Trade-offs

### 1. Cannot Compress Random Data
If the input has no repeated sequences, every byte becomes a literal. The output is the same size as the input (or slightly larger due to token overhead).

### 2. Greedy Algorithm
Our implementation is **greedy** — it always takes the best match at the current position. This isn't always globally optimal. Consider:

```
Position 0: could match 3 bytes
Position 1: could match 20 bytes (but we won't check if we took the match at 0)
```

A more sophisticated compressor might use **lazy matching** (look ahead one position before deciding), but our implementation prioritizes simplicity.

### 3. Window Size Limits Long-Range Matches
If a pattern last appeared 40,000 bytes ago, we can't reference it (window is only 32,768). The pattern must be stored again as literals.

### 4. Minimum Match Length Overhead
Sequences of 1-2 repeated bytes can't be compressed, even if they repeat thousands of times. They must be stored as literals.

---

## Where This Fits in DEFLATE

DEFLATE is a multi-stage compression pipeline. LZ77 is just the first step:

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

- **Stage 1 (this file):** Finds repeated sequences → outputs literals and back-references
- **Stage 2:** Converts lengths/distances into DEFLATE symbol codes with extra bits
- **Stage 3:** Builds Huffman trees to assign shorter codes to more frequent symbols
- **Stage 4:** Packs everything into a compact bitstream (the final compressed file)

LZ77 eliminates **sequential redundancy** (repeated patterns). Huffman coding (Stage 3) then eliminates **statistical redundancy** (some symbols appear more often than others). Together, they achieve much better compression than either alone.

---
