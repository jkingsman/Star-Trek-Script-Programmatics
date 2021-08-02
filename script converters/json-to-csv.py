#!/usr/bin/env python3

import csv
import glob
import json

seriesFolder = "voy"
scriptFolder = f"processed/{seriesFolder}"

collectedRows = []
for filepath in glob.iglob(scriptFolder + '/*.json'):
    print(filepath)
    with open(filepath) as scriptFile:
        data = json.load(scriptFile)
        for scene in data['scenes']:
            for line in scene['dialogue']:
                collectedRows.append({
                    'season': data['schedule']['season'],
                    'episode': data['schedule']['episode'],
                    'title': data['title'],
                    'character': line['character'],
                    'line': line['line']})

with open(f"{seriesFolder}.csv", 'w') as csvfile:
    fieldnames = ['season', 'episode', 'title', 'character', 'line']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    writer.writerows(collectedRows)
