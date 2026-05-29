#!/usr/bin/env python3
"""
Compare SRT subtitle files against processed JSON transcripts to find:
- Dropped lines (dialogue in SRT but missing from JSON)
- Extra lines (dialogue in JSON but not in SRT)
- Word-level errors within matched dialogue

Usage: python3 srt_compare.py [series] [episode]
  e.g. python3 srt_compare.py tos
       python3 srt_compare.py tng s03e15
       python3 srt_compare.py movies movie05
"""

import json
import glob
import os
import re
import sys
from difflib import SequenceMatcher


# ── SRT / JSON text extraction ──────────────────────────────────────────────

def srt_to_text(srt_path):
    """Parse SRT into a single normalized text string."""
    with open(srt_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    lines = []
    for block in re.split(r'\n\n+', content.strip()):
        parts = block.strip().split('\n')
        if len(parts) >= 3:
            text = ' '.join(parts[2:])
        elif len(parts) == 2 and '-->' not in parts[0] and '-->' in parts[1]:
            continue
        elif len(parts) == 2 and '-->' not in parts[1]:
            text = parts[1]
        else:
            continue
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Skip junk lines (YTS ads, etc.)
        if any(skip in text for skip in ['YTS.MX', 'YIFY', 'Downloaded from', 'Official YIFY',
                                          'OpenSubtitles', 'Subtitles by', 'Synced by']):
            continue
        text = text.strip()
        if text:
            lines.append(text)
    return ' '.join(lines)


def json_to_lines(json_path):
    """Extract dialogue lines from JSON, preserving character attribution."""
    with open(json_path) as f:
        data = json.load(f)
    lines = []
    for scene in data['scenes']:
        for d in scene['dialogue']:
            if d['character'] != 'unknown' and len(d['line'].strip()) > 0:
                lines.append({
                    'character': d['character'],
                    'line': d['line'],
                    'location': scene['location']
                })
    return data, lines


def normalize(text):
    """Normalize text for comparison."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Comparison engine ────────────────────────────────────────────────────────

def make_ngrams(words, n=4):
    """Generate n-grams from a word list."""
    return [' '.join(words[i:i+n]) for i in range(len(words) - n + 1)]


def find_drops_and_extras(json_lines, srt_text):
    """Compare JSON dialogue against SRT text to find drops and extras.

    Returns (drops, extras, word_errors):
      drops:  list of SRT phrases not matched in JSON
      extras: list of JSON lines not matched in SRT
      word_errors: list of (json_phrase, srt_phrase) near-matches
    """
    srt_norm = normalize(srt_text)
    srt_words = srt_norm.split()

    # Build set of SRT n-grams for fast lookup
    srt_4grams = set(make_ngrams(srt_words, 4))
    srt_5grams = set(make_ngrams(srt_words, 5))

    extras = []
    word_errors = []

    for entry in json_lines:
        line_norm = normalize(entry['line'])
        line_words = line_norm.split()
        if len(line_words) < 4:
            continue

        # Check if any 5-gram from this line appears in SRT
        line_5grams = make_ngrams(line_words, 5)
        line_4grams = make_ngrams(line_words, 4)

        matched_5 = sum(1 for g in line_5grams if g in srt_5grams) if line_5grams else 0
        matched_4 = sum(1 for g in line_4grams if g in srt_4grams) if line_4grams else 0

        total_grams = len(line_5grams) if line_5grams else len(line_4grams)
        matched = matched_5 if line_5grams else matched_4

        if total_grams > 0:
            coverage = matched / total_grams
        else:
            coverage = 0

        if coverage < 0.15 and len(line_words) >= 6:
            # This line has very little overlap with SRT - might be extra/wrong
            # Try to find the closest matching region in SRT
            best_ratio = 0
            best_srt_segment = ''
            # Slide a window of similar size across SRT
            window = len(line_words)
            for i in range(0, len(srt_words) - window, max(1, window // 2)):
                segment = ' '.join(srt_words[i:i + window])
                ratio = SequenceMatcher(None, line_norm, segment).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_srt_segment = segment

            if best_ratio > 0.55:
                # Close match but with word differences
                word_errors.append({
                    'character': entry['character'],
                    'location': entry['location'],
                    'json_line': entry['line'],
                    'srt_match': best_srt_segment,
                    'ratio': best_ratio
                })
            else:
                extras.append({
                    'character': entry['character'],
                    'location': entry['location'],
                    'line': entry['line'],
                    'best_ratio': best_ratio
                })

    # Now check for drops: SRT content not in JSON
    # Build JSON text and check SRT segments against it
    json_full = normalize(' '.join(e['line'] for e in json_lines))
    json_words = json_full.split()
    json_5grams = set(make_ngrams(json_words, 5))

    drops = []
    # Check 10-word windows of SRT for regions with no JSON match
    window = 10
    i = 0
    while i < len(srt_words) - window:
        segment_grams = make_ngrams(srt_words[i:i + window], 5)
        matched = sum(1 for g in segment_grams if g in json_5grams)
        if len(segment_grams) > 0 and matched / len(segment_grams) < 0.1:
            # Found a region of SRT with no JSON coverage
            # Extend to find full unmatched region
            end = i + window
            while end < len(srt_words) - 5:
                next_grams = make_ngrams(srt_words[end:end + 5], 5)
                if next_grams and any(g in json_5grams for g in next_grams):
                    break
                end += 3
            dropped_text = ' '.join(srt_words[i:end])
            if len(dropped_text.split()) >= 6:
                drops.append(dropped_text)
            i = end
        else:
            i += 3

    return drops, extras, word_errors


# ── Episode matching ─────────────────────────────────────────────────────────

def title_key(title):
    return re.sub(r'[^a-z0-9]', '', title.lower())


def build_tos_title_map():
    """TOS uses different episode ordering, so match by title."""
    srt_by_title = {}
    for srt_file in glob.glob('srt_dumps/tos/*.srt'):
        # Read corresponding MKV filename from the srt filename
        # We extracted from MKVs which use airdate order
        srt_by_title[os.path.basename(srt_file)] = srt_file

    # Build mapping from MKV titles
    mkv_map = {}
    for season in ['01', '02', '03']:
        mkvdir = f"/mnt/e/TV Shows/Star Trek (1966)/Season {season}"
        if not os.path.isdir(mkvdir):
            continue
        for f in os.listdir(mkvdir):
            if not f.endswith('.mkv'):
                continue
            m = re.search(r's(\d+)e(\d+) - (.+)\.mkv', f)
            if m:
                ep_code = f"s{m.group(1)}e{m.group(2)}"
                title = m.group(3).strip()
                mkv_map[title_key(title)] = f"srt_dumps/tos/{ep_code}.srt"

    # Map JSON files to SRT files by title
    result = {}
    for jf in glob.glob('processed/tos/*.json'):
        data = json.load(open(jf))
        tkey = title_key(data['title'])
        srt = mkv_map.get(tkey)
        if not srt:
            # Fuzzy match
            best_ratio = 0
            best_key = None
            for k in mkv_map:
                r = SequenceMatcher(None, tkey, k).ratio()
                if r > best_ratio:
                    best_ratio = r
                    best_key = k
            if best_ratio > 0.7:
                srt = mkv_map[best_key]
        if srt and os.path.exists(srt):
            result[jf] = srt
    return result


def get_episode_pairs(series):
    """Return list of (json_path, srt_path) pairs for a series."""
    if series == 'tos':
        return list(build_tos_title_map().items())

    if series == 'movies':
        pairs = []
        for jf in sorted(glob.glob('processed/movies/*.json')):
            fn = os.path.basename(jf).replace('.json', '.srt')
            srt = f'srt_dumps/movies/{fn}'
            if os.path.exists(srt):
                pairs.append((jf, srt))
        return pairs

    # TNG, DS9 - direct filename match
    pairs = []
    for jf in sorted(glob.glob(f'processed/{series}/*.json')):
        fn = os.path.basename(jf).replace('.json', '.srt')
        srt = f'srt_dumps/{series}/{fn}'
        if os.path.exists(srt):
            pairs.append((jf, srt))
    return pairs


# ── Main ─────────────────────────────────────────────────────────────────────

def run_comparison(series, episode_filter=None):
    pairs = get_episode_pairs(series)
    if not pairs:
        print(f"No SRT files found for {series}")
        return

    if episode_filter:
        pairs = [(j, s) for j, s in pairs if episode_filter in j]
        if not pairs:
            print(f"No match for filter '{episode_filter}' in {series}")
            return

    total_drops = 0
    total_extras = 0
    total_word_errors = 0
    episodes_with_issues = 0

    for json_path, srt_path in sorted(pairs):
        data, json_lines = json_to_lines(json_path)
        srt_text = srt_to_text(srt_path)

        if not srt_text or not json_lines:
            continue

        drops, extras, word_errors = find_drops_and_extras(json_lines, srt_text)

        if drops or extras or word_errors:
            episodes_with_issues += 1
            fn = os.path.basename(json_path)
            print(f"\n{'='*70}")
            print(f"{series.upper()} {fn} ({data.get('title', '?')})")
            print(f"{'='*70}")

            if word_errors:
                print(f"\n  WORD DIFFERENCES ({len(word_errors)}):")
                for we in word_errors[:15]:
                    print(f"    [{we['location']}] {we['character']}:")
                    print(f"      JSON: {we['json_line'][:100]}")
                    print(f"      SRT:  {we['srt_match'][:100]}")
                    print(f"      (similarity: {we['ratio']:.0%})")
                if len(word_errors) > 15:
                    print(f"    ... and {len(word_errors) - 15} more")

            if extras:
                print(f"\n  LINES NOT IN SRT ({len(extras)}):")
                for ex in extras[:10]:
                    print(f"    [{ex['location']}] {ex['character']}: {ex['line'][:100]}")
                if len(extras) > 10:
                    print(f"    ... and {len(extras) - 10} more")

            if drops:
                print(f"\n  SRT CONTENT NOT IN JSON ({len(drops)}):")
                for dr in drops[:10]:
                    print(f"    \"{dr[:120]}\"")
                if len(drops) > 10:
                    print(f"    ... and {len(drops) - 10} more")

            total_drops += len(drops)
            total_extras += len(extras)
            total_word_errors += len(word_errors)

    print(f"\n{'='*70}")
    print(f"SUMMARY: {series.upper()}")
    print(f"{'='*70}")
    print(f"  Episodes checked: {len(pairs)}")
    print(f"  Episodes with issues: {episodes_with_issues}")
    print(f"  Total word differences: {total_word_errors}")
    print(f"  Total lines not in SRT: {total_extras}")
    print(f"  Total SRT drops: {total_drops}")


if __name__ == '__main__':
    series_list = sys.argv[1:] if len(sys.argv) > 1 else ['tos', 'ds9', 'tng', 'movies']
    episode_filter = None

    # Check if second arg is an episode filter
    if len(sys.argv) > 2 and sys.argv[2].startswith('s'):
        episode_filter = sys.argv[2]
        series_list = [sys.argv[1]]

    for series in series_list:
        run_comparison(series, episode_filter)
