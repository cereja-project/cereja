# UI text and cell metrics

Import the independent module explicitly:

```python
from cereja.ui.text import TextPolicy, clip_text, text_metrics

policy = TextPolicy(ambiguous_width=1, ascii_only=False, source=True)
measured = text_metrics("e\u0301界", policy)
assert measured.boundaries == (0, 2, 3)
assert measured.cell_position(2) == (1, 0)
assert measured.line_widths() == (3,)
assert clip_text("e\u0301界", 2) == "e\u0301 "
```

The [approved policy](../design/cereja-ui.md#4-text-security-and-cells) is frozen
at Unicode 17.0.0, [default extended grapheme boundaries (UAX #29 revision 47)](https://www.unicode.org/reports/tr29/tr29-47.html),
and Emoji 17.0. Runtime behavior does not use Python's `unicodedata` version,
third-party libraries or network downloads. `import cereja`, `import cereja.ui`
and terminal-only imports do not load the Unicode tables.

## Safe input and editing offsets

`normalize_text(text, source=True)` renders ESC, C0/C1 and DEL as visible ASCII
`\xhh` escapes. LF and TAB remain explicit layout tokens. CR is escaped, including
the CR in CRLF. Surrogate code points become U+FFFD. Normalization preserves
composed/decomposed forms; it performs no NFC/NFD conversion.

Source/path bidi formatting controls become visible `\uhhhh` escapes by default.
`source=False` retains them for prose. The renderer uses logical ordering and
does not provide a bidirectional layout engine. No mode permits raw ESC/C0/C1/DEL
in grapheme display units. A terminal emulator can still disagree about shaping,
bidi presentation or glyph width.

`grapheme_spans(text)` yields raw `(start, end)` Python string offsets, and
`graphemes(text)` yields raw clusters without normalization. They implement the
official segmentation boundary and are not safe terminal output functions.
`text_metrics(text, policy)` first normalizes and then measures. Its immutable
`TextMetrics.text` is the normalized editing model. Unit offsets and cursor
boundaries refer to that string, not the original source. Callers sanitizing paste
must store this canonical text before applying those offsets. Escapes consist
of ordinary printable ASCII graphemes. A cluster replaced with `?` retains its
entire normalized input span for editing/deletion.

`next_boundary(offset)` and `previous_boundary(offset)` move over whole clusters
and clamp at the text endpoints. `cell_position(offset)` returns `(column, row)`
and rejects offsets inside a cluster. Units expose `start`, `end`, safe `text`,
`width`, and `kind` (`grapheme`, `tab`, `newline`). Grapheme widths are 1 or 2;
layout tokens have width 0 until resolved at a column. Do not serialize those
tokens as terminal commands.

## Frozen width and layout

After sanitization, width follows this precedence:

1. An exact listed RGI emoji, including listed basic emoji, uses 2 cells.
2. An exact listed text-style emoji variation uses the base's text width.
3. A non-RGI cluster containing an unassigned scalar, U+200C/U+200D, variation
   selector, emoji modifier or regional indicator becomes `?` (1 cell).
4. Ordinary clusters use the maximum non-mark scalar width: East Asian W/F = 2,
   A = `ambiguous_width` (1 by default, explicitly selectable as 2), others = 1.
   Attached Mn/Mc/Me marks add no cells. An all-mark cluster receives a dotted
   circle with fixed width 1.

Emoji property alone does not cause fallback. Bare digits, copyright and bare
text-style heart use ordinary text widths. Bare skin-tone modifiers are listed
in `Basic_Emoji`, so the exact-RGI precedence gives them 2 cells. Invalid modifier
combinations and unlisted flags still use whole-cluster fallback. ASCII mode
preserves only printable ASCII clusters and replaces every other complete
cluster with `?` before layout.

`line_widths(start_column=0, tab_size=4)` returns each line's ending column.
TAB advances to the next multiple of `tab_size`; LF starts the next row at zero.
Cursor positions use the same policy. No automatic wrapping is performed.

`clip_text(text, cells, left=0, tab_size=4, policy=...)` and `TextMetrics.clip`
select a single line's cell interval `[left, left + cells)`. Tabs become spaces.
A wide cluster intersecting either clipping edge becomes blanks for its visible
cells. Clipping preserves whole clusters and adds no padding past actual text.
Multi-line input raises `ValueError`; the caller selects the line explicitly.
Wide-cell replacement and overlapping composition use the
[cell-buffer contracts](ui-buffer.md).

The shared cache includes normalized text, Unicode version and the complete
policy. It retains at most 128 entries, only for strings of at most 1,024 code
points; larger strings bypass it. This bounds retained entries and payloads,
not a caller's total text or layout memory.

## Data, license and regeneration

The [manifest](../../tools/unicode/17.0.0/manifest.json) records every exact official
URL and SHA-256. Its adjacent files retain the original bytes, including the
official test corpus. Generated property ranges and exact sequence sets live
in `cereja/ui/_unicode17.py`. `cereja/ui/UNICODE-LICENSE.txt` ships in the installed
package; regeneration inputs, generator and this guide also ship in the sdist.
These Unicode data are distributed under Unicode License V3; Cereja's
own code retains its repository license. Git attributes preserve pinned bytes
and generated LF output on Windows.

```text
python -B -S tools/generate_ui_unicode.py
python -B -S tools/generate_ui_unicode.py --check
python -B -S -m unittest discover -s tests -p test_ui_text.py -v
```

Generation and `--check` are offline. `--download` explicitly refetches the pinned
official URLs and rejects any changed hash before replacing inputs; it never
updates the dataset or hashes. A Unicode-version upgrade requires a separately
reviewed policy, manifest and generator change. The license URL is not versioned
by Unicode; its exact downloaded notice is frozen with its hash, so later upstream
license changes can make `--download` fail without affecting offline regeneration.

Tests check all 766 official grapheme vectors, all 3,953 RGI sequences, all 371
text-style variations, malformed text, controls/injection, ambiguous/ASCII/fallback
policies, cursor boundaries and clipping. These establish the frozen policy,
not universal agreement with fonts or terminal emulators. Actual emulator, SSH,
ConPTY and disconnect walkthroughs remain platform acceptance work.
