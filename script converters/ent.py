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
        cleaned = cleaned.replace("Captain's log", "ARCHER [OC]: Captain's log")  # replace log entries
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
    if ep_num <= 26:
        return {"season": 1, "episode": ep_num, "number": ep_num}
    elif ep_num <= 52:
        return {"season": 2, "episode": ep_num - 26, "number": ep_num}
    elif ep_num <= 76:
        return {"season": 3, "episode": ep_num - 52, "number": ep_num}
    elif ep_num <= 98:
        return {"season": 4, "episode": ep_num - 76, "number": ep_num}

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

            if modifier in ["on monitor", "on viewscreen", "On viewscreen", "on screen", "on PADD", "text"]:
                line['modifier'] = "screen"
            else:
                # Enterprise uses OC, CO, and location names as modifiers
                # (e.g., [Bridge], [Sickbay], [Florida]) for off-camera dialogue
                line['modifier'] = "voiceover"
        else:
            line['character'] = character_block.strip()
        lines.append(line)
    return lines

directory = 'www.chakoteya.net/Enterprise'
for entry in os.scandir(directory):
    if not entry.name.endswith('.htm'):
        continue
    basename = entry.name[:-4]
    if not basename.isdigit():
        continue

    episode = {}

    try:
        soup = BeautifulSoup(open(entry.path, encoding='utf-8').read(), 'html.parser')
    except UnicodeDecodeError:
        soup = BeautifulSoup(open(entry.path, encoding='cp1252').read(), 'html.parser')

    title_tag = soup.find('font', {'size': '5'})
    title = re.sub(r'[\t\r\n]', ' ', title_tag.getText()).strip()
    title = re.sub(r'  +', ' ', title)
    episode['title'] = title

    episode['stardate'] = 'Unknown'

    metadata_text = title_tag.find_parent('p').getText()
    airdate_match = re.search(r'Original Airdate:\s*(.*?)(?:[\r\n]|$)', metadata_text)
    if airdate_match:
        episode['airdate'] = extractDate(airdate_match[1].strip())
    else:
        episode['airdate'] = 0

    ep_num = int(basename)
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

    with open("processed/ent/s%se%s - %s.json" % (str(episode['schedule']['season']).zfill(2), str(episode['schedule']['episode']).zfill(2), safe_filename(episode['title'])), 'w') as outfile:
        string_script = replace(json.dumps(episode))
        json.dump(json.loads(string_script), outfile, indent=2, sort_keys=True)
