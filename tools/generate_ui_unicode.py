"""Regenerate the frozen UI tables offline; downloads require explicit --download.

Inputs are byte-pinned in tools/unicode/17.0.0/manifest.json. This tool never
selects a newer dataset or updates hashes. Review a data-version change separately.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools' / 'unicode' / '17.0.0'
OUTPUT = ROOT / 'cereja' / 'ui' / '_unicode17.py'
LICENSE = ROOT / 'cereja' / 'ui' / 'UNICODE-LICENSE.txt'


def load_sources(download=False):
    manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest['unicode_version'], manifest['emoji_version'], manifest['uax29_revision']) != ('17.0.0', '17.0', 47):
        raise ValueError('this generator implements only Unicode 17.0.0, Emoji 17.0, UAX #29 revision 47')
    sources = {}
    for name, entry in manifest['sources'].items():
        if Path(name).name != name or not entry['url'].startswith('https://www.unicode.org/'):
            raise ValueError(f'invalid source: {name}')
        if download:
            from urllib.request import urlopen
            with urlopen(entry['url'], timeout=30) as response:
                data = response.read()
        else:
            data = (DATA / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError(f'SHA-256 mismatch: {name}')
        sources[name] = data
    # Validate every download before replacing any input.
    if download:
        for name, data in sources.items():
            (DATA / name).write_bytes(data)
    return manifest, sources


def records(sources, name):
    for line in sources[name].decode('utf-8').splitlines():
        content = line.split('#', 1)[0].strip()
        if content:
            yield [field.strip() for field in content.split(';')]


def bounds(codes):
    values = codes.split('..')
    return int(values[0], 16), int(values[-1], 16)


def merged(ranges):
    result = []
    for low, high in sorted(ranges):
        if result and low <= result[-1][1] + 1:
            result[-1] = result[-1][0], max(result[-1][1], high)
        else:
            result.append((low, high))
    return result


def property_ranges(sources, name, properties):
    return merged(bounds(fields[0]) for fields in records(sources, name) if fields[1] in properties)


def valued_ranges(sources, name, properties=None, field=1):
    result = []
    for fields in records(sources, name):
        if properties is None or fields[1] in properties:
            low, high = bounds(fields[0])
            result.append((low, high, fields[field]))
    combined = []
    for low, high, value in sorted(result):
        if combined and low == combined[-1][1] + 1 and value == combined[-1][2]:
            combined[-1] = combined[-1][0], high, value
        else:
            if combined and low <= combined[-1][1]:
                raise ValueError(f'overlapping properties: {name}')
            combined.append((low, high, value))
    return combined


def sequences(sources, name, properties):
    result = set()
    for fields in records(sources, name):
        if fields[1] in properties:
            if '..' in fields[0]:
                low, high = bounds(fields[0])
                result.update(chr(code) for code in range(low, high + 1))
            else:
                result.add(''.join(chr(int(code, 16)) for code in fields[0].split()))
    return result


def generate(manifest, sources):
    lines = [
        '"""Generated Unicode 17.0.0 / Emoji 17.0 data. Do not edit.',
        '',
        'Regenerate: python -B -S tools/generate_ui_unicode.py',
        'Provenance and source hashes: tools/unicode/17.0.0/manifest.json',
        'License: UNICODE-LICENSE.txt (Unicode License V3).',
        'Rules: https://www.unicode.org/reports/tr29/tr29-47.html',
        '"""', '', "UNICODE_VERSION = '17.0.0'", "EMOJI_VERSION = '17.0'", 'UAX29_REVISION = 47', '',
        'SOURCE_HASHES = {',
    ]
    for name, source in sorted(manifest['sources'].items()):
        lines.append(f"    {name!r}: {source['sha256']!r},")
    lines.extend(['}', ''])
    tables = {
        'GCB': valued_ranges(sources, 'GraphemeBreakProperty.txt'),
        'INCB': valued_ranges(sources, 'DerivedCoreProperties.txt', {'InCB'}, field=2),
        'EAW': valued_ranges(sources, 'EastAsianWidth.txt', {'W', 'F', 'A'}),
        'MARK': property_ranges(sources, 'DerivedGeneralCategory.txt', {'Mn', 'Mc', 'Me'}),
        'UNASSIGNED': property_ranges(sources, 'DerivedGeneralCategory.txt', {'Cn'}),
        'EXTENDED_PICTOGRAPHIC': property_ranges(sources, 'emoji-data.txt', {'Extended_Pictographic'}),
        'EMOJI_MODIFIER': property_ranges(sources, 'emoji-data.txt', {'Emoji_Modifier'}),
        'VARIATION_SELECTOR': property_ranges(sources, 'PropList.txt', {'Variation_Selector'}),
        'BIDI_CONTROL': property_ranges(sources, 'PropList.txt', {'Bidi_Control'}),
    }
    for name, table in tables.items():
        lines.append(f'{name} = (')
        for row in table:
            fields = [f'0x{row[0]:X}', f'0x{row[1]:X}']
            if len(row) == 3:
                fields.append(repr(row[2]))
            lines.append('    (' + ', '.join(fields) + '),')
        lines.extend([')', ''])
    types = {'Basic_Emoji', 'Emoji_Keycap_Sequence', 'RGI_Emoji_Flag_Sequence',
             'RGI_Emoji_Tag_Sequence', 'RGI_Emoji_Modifier_Sequence', 'RGI_Emoji_ZWJ_Sequence'}
    rgi = sequences(sources, 'emoji-sequences.txt', types) | sequences(sources, 'emoji-zwj-sequences.txt', types)
    text_style = sequences(sources, 'emoji-variation-sequences.txt', {'text style'})
    for name, table in (('RGI_EMOJI', rgi), ('TEXT_VARIATION', text_style)):
        lines.append(f'{name} = frozenset((')
        for text in sorted(table):
            lines.append(f'    {ascii(text)},')
        lines.extend(['))', ''])
    return '\n'.join(lines).encode('ascii')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='verify hashes and exact generated bytes without writes/network')
    mode.add_argument('--download', action='store_true', help='refetch only pinned official URLs; reject any hash mismatch')
    args = parser.parse_args(argv)
    try:
        manifest, sources = load_sources(args.download)
        outputs = {OUTPUT: generate(manifest, sources), LICENSE: sources['LICENSE.txt']}
        for path, expected in outputs.items():
            if args.check:
                if not path.exists() or path.read_bytes() != expected:
                    raise ValueError(f'generated artifact differs: {path.relative_to(ROOT)}')
            else:
                path.write_bytes(expected)
    except (ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    print('Unicode 17.0.0 hashes and generated artifacts verified.' if args.check else 'Unicode 17.0.0 artifacts generated.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
