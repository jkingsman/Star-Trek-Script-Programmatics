import json

with open('gb2en.json') as f:
  replacements = json.load(f)
  only_words = replacements.keys()

def replace(line):
  for replacement in replacements.keys():
    line = line.replace(replacement, replacements[replacement])
    line = line.replace(replacement.capitalize(), replacements[replacement].capitalize())
  return line
