import json

import os

JSON_FILENAME = os.path.join(os.path.dirname(__file__), 'gb2en.json')
with open(JSON_FILENAME) as f:
    replacements = json.load(f)
    only_words = replacements.keys()


def replace(line):
    for replacement in replacements.keys():
        line = line.replace(replacement, replacements[replacement])
        line = line.replace(replacement.capitalize(), replacements[replacement].capitalize())
    return line
