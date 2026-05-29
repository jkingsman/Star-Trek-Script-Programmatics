#!/usr/bin/env python3
"""
Generate text and CSV dumps for all series from processed JSON files.
"""

import csv
import glob
import json
import os


def generate_dumps(series, json_dir, csv_path, txt_path, schedule_key='season'):
    """Generate CSV and text dumps for a series."""
    collected_rows = []
    txt_lines = []

    for filepath in sorted(glob.iglob(json_dir + '/*.json')):
        with open(filepath) as f:
            data = json.load(f)

        schedule = data.get('schedule', {})

        for scene in data['scenes']:
            if scene['location'] != 'unknown':
                txt_lines.append('')
                txt_lines.append(f"[{scene['location']}]")
            for line in scene['dialogue']:
                if line['character'].upper() != 'UNKNOWN':
                    modifier = f" ({line['modifier']})" if 'modifier' in line else ""
                    txt_lines.append(f"{line['character'].upper()}{modifier}: {line['line']}")

                    row = {
                        'title': data['title'],
                        'character': line['character'],
                        'line': line['line'],
                    }
                    if schedule_key == 'season':
                        row['season'] = schedule.get('season', '')
                        row['episode'] = schedule.get('episode', '')
                    else:
                        row['number'] = schedule.get('number', '')
                    collected_rows.append(row)

    # Write CSV
    if schedule_key == 'season':
        fieldnames = ['season', 'episode', 'title', 'character', 'line']
    else:
        fieldnames = ['number', 'title', 'character', 'line']

    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(collected_rows)

    # Write text dump
    with open(txt_path, 'w') as f:
        f.write('\n'.join(txt_lines))

    print(f"  {series}: {len(collected_rows)} lines -> {os.path.basename(csv_path)}, {os.path.basename(txt_path)}")


# Series with season/episode structure
series_list = [
    ('tng', 'json_transcripts/tng', 'per_show_csv_dumps/tng.csv', 'per_show_text_dumps/tng_dumped.txt'),
    ('ds9', 'json_transcripts/ds9', 'per_show_csv_dumps/ds9.csv', 'per_show_text_dumps/ds9_dumped.txt'),
    ('voy', 'json_transcripts/voy', 'per_show_csv_dumps/voy.csv', 'per_show_text_dumps/voy_dumped.txt'),
    ('ent', 'json_transcripts/ent', 'per_show_csv_dumps/ent.csv', 'per_show_text_dumps/ent_dumped.txt'),
    ('tos', 'json_transcripts/tos', 'per_show_csv_dumps/tos.csv', 'per_show_text_dumps/tos_dumped.txt'),
    ('tas', 'json_transcripts/tas', 'per_show_csv_dumps/tas.csv', 'per_show_text_dumps/tas_dumped.txt'),
    ('ld', 'json_transcripts/ld', 'per_show_csv_dumps/ld.csv', 'per_show_text_dumps/ld_dumped.txt'),
]

for series, json_dir, csv_path, txt_path in series_list:
    generate_dumps(series, json_dir, csv_path, txt_path, schedule_key='season')

# Movies - individual dumps per movie + combined
print()
movie_rows = []
movie_txt_lines = []

for filepath in sorted(glob.iglob('json_transcripts/movies/*.json')):
    with open(filepath) as f:
        data = json.load(f)

    movie_num = data['schedule']['number']
    base = os.path.basename(filepath).replace('.json', '')
    ep_rows = []
    ep_txt = []

    for scene in data['scenes']:
        if scene['location'] != 'unknown':
            ep_txt.append('')
            ep_txt.append(f"[{scene['location']}]")
        for line in scene['dialogue']:
            if line['character'].upper() != 'UNKNOWN':
                modifier = f" ({line['modifier']})" if 'modifier' in line else ""
                ep_txt.append(f"{line['character'].upper()}{modifier}: {line['line']}")
                row = {
                    'number': movie_num,
                    'title': data['title'],
                    'character': line['character'],
                    'line': line['line'],
                }
                ep_rows.append(row)

    # Individual movie dumps
    with open(f'per_show_csv_dumps/{base}.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['number', 'title', 'character', 'line'])
        writer.writeheader()
        writer.writerows(ep_rows)

    with open(f'per_show_text_dumps/{base}_dumped.txt', 'w') as f:
        f.write('\n'.join(ep_txt))

    print(f"  movie{movie_num:02d}: {len(ep_rows)} lines -> {base}.csv, {base}_dumped.txt")

    movie_rows.extend(ep_rows)
    movie_txt_lines.extend(ep_txt)

# Combined movies dump
with open('per_show_csv_dumps/movies.csv', 'w', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['number', 'title', 'character', 'line'])
    writer.writeheader()
    writer.writerows(movie_rows)

with open('per_show_text_dumps/movies_dumped.txt', 'w') as f:
    f.write('\n'.join(movie_txt_lines))

print(f"  movies (combined): {len(movie_rows)} lines -> movies.csv, movies_dumped.txt")
