"""Check saved UI spike evidence without rewriting it or imposing timing gates."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


METRICS = ('full_diff', 'dirty_diff', 'encoding',
           'full_diff_encode', 'dirty_diff_encode')
BASELINE_SOURCES = ('model.py', 'platform_probe.py', 'run.py', 'test_model.py')
DOWNLOAD_SOURCES = ('benchmarks/ui_spikes/download_probe.py',
                    'cereja/transfers/download.py', 'cereja/transfers/models.py',
                    'cereja/transfers/sinks.py', 'cereja/http/sync/client.py')


def source_fingerprint_match(data, expected):
    """Match recorded Python source bytes, allowing only LF/CRLF conversion."""
    if hashlib.sha256(data).hexdigest() == expected:
        return 'exact'
    lf = data.replace(b'\r\n', b'\n')
    for candidate in (lf, lf.replace(b'\n', b'\r\n')):
        if hashlib.sha256(candidate).hexdigest() == expected:
            return 'line_endings_only'
    return None


def verify(root):
    root = Path(root).resolve()
    spikes = root / 'benchmarks' / 'ui_spikes'
    errors = []
    fingerprints = {}

    def check(condition, message):
        if not condition:
            errors.append(message)

    def read(name):
        data = (spikes / name).read_bytes()
        fingerprints[name] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    baseline = read('baseline-windows-py314.json')
    platform = read('platform-windows.json')
    download = read('download-loopback.json')
    matched = []
    newline_variants = []
    for report, prefix, required in ((baseline, spikes, BASELINE_SOURCES),
                                     (download, root, DOWNLOAD_SOURCES)):
        recorded = report['sources_sha256']
        check(set(recorded) == set(required), 'recorded source coverage differs')
        for name in required:
            expected = recorded.get(name)
            path = prefix / name
            match = source_fingerprint_match(path.read_bytes(), expected)
            relative = path.relative_to(root).as_posix()
            check(match is not None, f'source fingerprint mismatch: {name}')
            if match is not None:
                matched.append(relative)
                if match == 'line_endings_only':
                    newline_variants.append(relative)
    check(download['source_sha256'] == download['sources_sha256'][
          'benchmarks/ui_spikes/download_probe.py'], 'download probe hashes disagree')
    check(baseline['revision'] == download['revision'], 'recorded revisions disagree')
    check(baseline['warmup'] == 5 and baseline['repetitions'] == 31,
          'unexpected sampling protocol')
    expected_cases = {(w, h, case) for w, h in ((80, 24), (120, 40), (240, 80))
                      for case in ('unchanged', 'one_cell', 'one_row', 'ten_percent', 'all')}
    rows = baseline['render']
    check(len(rows) == 15 and {(r['width'], r['height'], r['case']) for r in rows}
          == expected_cases, 'renderer workload coverage differs')
    sample_count = 0
    for row in rows:
        label = f"{row['width']}x{row['height']} {row['case']}"
        count = {'unchanged': 0, 'one_cell': 1, 'one_row': row['width'],
                 'ten_percent': row['width'] * row['height'] // 10,
                 'all': row['width'] * row['height']}[row['case']]
        check(row['changed_cells'] == count, f'{label}: changed-cell count differs')
        check(row['planned_stream_write_calls'] == int(count > 0),
              f'{label}: planned stream count differs')
        check((row['encoded_bytes'] == 0) == (count == 0),
              f'{label}: zero-byte contract differs')
        for metric in METRICS:
            data = row[metric]
            samples = data['samples_ns']
            sample_count += len(samples)
            check(len(samples) == baseline['repetitions'], f'{label} {metric}: sample count')
            check(all(type(v) is int and v >= 0 for v in samples),
                  f'{label} {metric}: invalid duration')
            check(data['median_ns'] == statistics.median(samples),
                  f'{label} {metric}: median differs from raw samples')
            check(data['p95_ns'] == sorted(samples)[int(len(samples) * .95)],
                  f'{label} {metric}: p95 differs from recorded estimator')
            check(data['peak_traced_bytes'] >= 0, f'{label} {metric}: negative peak')
    imports = baseline['fresh_import_cereja']
    check(len(imports) == 9, 'root import sample count differs')
    check(all(not r['stdout'] and not r['stderr'] and not r['threads_added']
              and not r['ui_modules'] for r in imports), 'root import side effects recorded')
    check(platform['terminal_mode_changes'] == 0 and platform['input_reads'] == 0,
          'platform report exceeds noninteractive scope')
    check(platform['idle_ready'] == 0 and platform['posted_ready'] == 1
          and platform['posted_payload'] == 'x', 'socket wake evidence differs')
    check(platform['win32_event'] == {'idle_result': 258, 'wakeup_index': 1,
                                    'reset_result': 258}, 'native wait evidence differs')
    check(download['payload_bytes'] == 1536 and download['chunk_size'] == 128,
          'download fixture differs')
    check([case['mode'] for case in download['cases']] ==
          ['known', 'unknown', 'callback_abort_first_chunk'], 'download cases differ')
    for case in download['cases'][:2]:
        expected_total = 1536 if case['mode'] == 'known' else None
        check(case['events'] == [{'bytes_transferred': n, 'total_bytes': expected_total}
                                for n in range(128, 1537, 128)],
              f"{case['mode']}: progress sequence differs")
        check(case['result_bytes'] == 1536 and case['total_bytes'] == expected_total
              and case['remaining_part_files'] == 0, f"{case['mode']}: result differs")
    abort = download['cases'][2]
    check(abort['old_output_preserved'] and abort['remaining_part_files'] == 0
          and abort['events'] == [{'bytes_transferred': 128, 'total_bytes': 1536}],
          'callback-abort evidence differs')
    check(download['server_stopped'] and download['temporary_directory_cleaned'],
          'owned download resources not cleaned')
    return {'scope': 'saved baseline integrity only; no production or timing acceptance',
            'ok': not errors, 'errors': errors, 'recorded_revision': baseline['revision'],
            'artifact_sha256': fingerprints, 'matching_source_entries': matched,
            'source_newline_variants': newline_variants,
            'render_workloads': len(rows), 'render_raw_samples': sample_count,
            'root_import_samples': len(imports),
            'root_import_median_ns': statistics.median(r['elapsed_ns'] for r in imports),
            'sparse_model_comparisons': [
                {'width': r['width'], 'height': r['height'], 'case': r['case'],
                 'lower_median': r['dirty_diff']['median_ns'] < r['full_diff']['median_ns'],
                 'lower_p95': r['dirty_diff']['p95_ns'] < r['full_diff']['p95_ns']}
                for r in rows if r['case'] in ('one_row', 'ten_percent')],
            'platform_provenance': 'original platform report has no embedded source hash'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.root)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as output:
            output.write(rendered)
    print(rendered, end='')
    raise SystemExit(0 if result['ok'] else 1)
