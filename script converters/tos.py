#!/usr/bin/env python3

import json
import os
import re
import time

from bs4 import BeautifulSoup

from gb2en import replace


def extractDate(datestring):
    date_formats = ['%d %b, %Y', '%b %d %Y', '%b %d, %Y', '%d %B, %Y', '%d %b %Y', '%d %B %Y', '%B %d, %Y', '%B %d %Y']

    while date_formats:
        try:
            return int(time.mktime(time.strptime(datestring.strip(), date_formats.pop())))
        except Exception as e:
            if len(date_formats) > 0:
                pass
            else:
                raise e

    raise Exception


def scrubList(list):
    scrubbedList = []

    for item in list:
        cleaned = item.strip()
        cleaned = cleaned.replace("Captain's log", "KIRK [OC]: Captain's log")  # replace log entries
        # clear line breaks in the middle of lines (last char is a-z.,;?! and then break and then not two capitals)
        cleaned = re.sub(r'(?<=[a-zI\.\,\;\?\!])\n(?![A-Z][A-Z])', ' ', cleaned)
        cleaned = re.sub(' \n', '\n', cleaned)
        cleaned = re.sub('\n\n', '\n', cleaned)
        cleaned = re.sub(r'\(.*?\)', ' ', cleaned)  # remove parentheticals
        cleaned = cleaned.replace('  ', ' ').replace('   ', ' ').replace('    ', ' ')
        if len(cleaned) == 0:
            continue
        scrubbedList.append(cleaned.strip())
    return scrubbedList


def getSeasonDataFromEpisode(ep_num):
    if ep_num <= 29:
        return {"season": 1, "episode": ep_num, "number": ep_num}
    elif ep_num <= 55:
        return {"season": 2, "episode": ep_num - 29, "number": ep_num}
    elif ep_num <= 79:
        return {"season": 3, "episode": ep_num - 55, "number": ep_num}

    print("BAD EP NUM")
    print(ep_num)
    exit()


def getLinesFromStringBlock(block):
    split_scene_text = re.split(r'([A-Z0-9\' ]+(?:[ \n]\[.*?\])?):', block)
    if len(split_scene_text) == 1:
        # who knows what happened here
        return [{'character': 'unknown', 'line': block}]

    split_scene_text.pop(0)  # first is always blank?
    lines = []
    for j in range(int(len(split_scene_text) / 2)):
        line = {}
        character_block = split_scene_text.pop(0).strip()
        line['line'] = split_scene_text.pop(0).strip().replace('\n', ' ').replace('  ', ' ').replace('  ', ' ')

        if len(line['line']) == 0:
            continue

        if "[" in character_block:
            char_and_modifier = character_block.split('[')
            line['character'] = char_and_modifier[0].strip()
            modifier = char_and_modifier[1].replace(']', '')

            if modifier in ["OC", "CO", "IC", "Kirk's voice", "Andrea's voice", "Chapel's voice", "Christine's voice", "over images", "through macroscope"]:
                line['modifier'] = "voiceover"
            elif modifier in ["on monitor", "on viewscreen", "On viewscreen", "on screen", "on PADD", "on viewer"]:
                line['modifier'] = "screen"
            else:
                print("WARNING!!! UNKNOWN LINE MODIFIER")
                print(modifier)
                print("for")
                print(line['character'])
                print(character_block)
                exit()
        else:
            line['character'] = character_block.strip()
        lines.append(line)
    return lines

directory = 'www.chakoteya.net/StarTrek'
for entry in os.scandir(directory):
    if not entry.name.endswith('.htm'):
        continue
    basename = entry.name[:-4]
    if basename.startswith('TAS'):
        continue

    is_part_b = basename.endswith('b')
    num_part = basename[:-1] if is_part_b else basename
    if not num_part.isdigit():
        continue

    episode = {}
    ep_num = int(num_part)

    soup = BeautifulSoup(open(entry.path, encoding='utf-8').read(), 'html.parser')

    title_tag = soup.find('font', {'color': '#2867d0'})
    title = re.sub(r'[\t\r\n]', ' ', title_tag.getText()).strip()
    title = re.sub(r'  +', ' ', title)
    episode['title'] = title

    metadata_text = title_tag.find_parent('p').getText()

    stardate_match = re.search(r'Stardate:\s*(\S+)', metadata_text)
    episode['stardate'] = stardate_match[1] if stardate_match else 'Unknown'

    airdate_match = re.search(r'Original Airdate:\s*(.*?)(?:[\r\n]|$)', metadata_text)
    if airdate_match:
        episode['airdate'] = extractDate(airdate_match[1].strip())
    else:
        episode['airdate'] = 0

    episode['schedule'] = getSeasonDataFromEpisode(ep_num)

    full_script = soup.find('td', {'width': '85%'}).getText()

    # split on scenes
    cleaned_script = re.sub(r'](?=[A-Z])', ']\n', full_script.strip().replace('\n\n\n', '\n\n').replace(u'\xa0', ' '))
    cleaned_script = re.sub(r'\)(?=[A-Z])', ') ', cleaned_script)
    scenes = re.split(r'((?<!\w )\[[^:]*?\] *\n)', cleaned_script, flags=re.DOTALL)
    cleaned_scenes = scrubList(scenes)

    episode['scenes'] = []
    while len(cleaned_scenes) != 0:
        scene = {}
        data = cleaned_scenes.pop(0).strip()
        if len(data) == 0:
            continue

        if data[0] == '[':
            scene['location'] = data.replace('[', '').replace(']', '').strip()
            if len(cleaned_scenes) == 0:
                continue
            possible_lines = cleaned_scenes.pop(0).strip()
            if len(possible_lines) > 0:
                scene['dialogue'] = getLinesFromStringBlock(possible_lines)
            else:
                continue
        else:
            scene['location'] = 'unknown'
            scene['dialogue'] = getLinesFromStringBlock(data)

        episode['scenes'].append(scene)

    suffix = 'b' if is_part_b else ''
    with open("processed/tos/s%se%s%s - %s.json" % (str(episode['schedule']['season']).zfill(2), str(episode['schedule']['episode']).zfill(2), suffix, safe_filename(episode['title'])), 'w') as outfile:
        string_script = replace(json.dumps(episode))
        json.dump(json.loads(string_script), outfile, indent=2, sort_keys=True)
