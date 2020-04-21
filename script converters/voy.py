#!/usr/bin/env python3

import json
import os
import pprint
import re
import time

from bs4 import BeautifulSoup

from gb2en import replace


def extractDate(datestring):
    result = None
    date_formats = ['%d %b, %Y', '%b %d %Y', '%b %d, %Y', '%d %B, %Y', '%d %b %Y', '%d %B %Y', '%B %d, %Y', '%B %d %Y']

    while not result:
        try:
            return int(time.mktime(time.strptime(matches[2].strip(), date_formats.pop())))
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
        cleaned = cleaned.replace("Captain's log", "JANEWAY [OC]: Captain's log")  # replace log entries
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
    if ep_num <= 16:
        return {"season": 1, "episode": ep_num, "number": ep_num}
    elif ep_num <= 42:
        return {"season": 2, "episode": ep_num - 16, "number": ep_num}
    elif ep_num <= 68:
        return {"season": 3, "episode": ep_num - 42, "number": ep_num}
    elif ep_num <= 94:
        return {"season": 4, "episode": ep_num - 68, "number": ep_num}
    elif ep_num <= 120:
        return {"season": 5, "episode": ep_num - 94, "number": ep_num}
    elif ep_num <= 146:
        return {"season": 6, "episode": ep_num - 120, "number": ep_num}
    elif ep_num <= 172:
        return {"season": 7, "episode": ep_num - 146, "number": ep_num}

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

            if modifier in ["OC", "CO", "telepath", "Stargazer log", "telepathically", "outside"]:
                line['modifier'] = "voiceover"
            elif modifier in ["on monitor", "on viewscreen", "On viewscreen", "on screen", "on PADD", "on bathroom monitor", "on imagiser", "on TV"]:
                line['modifier'] = "screen"
            elif modifier in ["singing", "both", "Naomi's voice", "as corpse", "memory", "in his mind"]:
                # line['modifier'] = "modifier"
                pass
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

directory = 'www.chakoteya.net/Voyager'
for entry in os.scandir(directory):
    episode = {}
    # if entry.name != '718.htm':
    #     continue

    soup = BeautifulSoup(open(entry.path, encoding='cp1252').read(), 'html.parser')

    title = re.sub(r'[\t\r\n]', ' ', soup.find('font', {'color': '#2867d0'}).getText())
    episode['title'] = title

    stardate_airdate = re.sub(r'[\t\r\n]', ' ', soup.find('font', {'size': '2'}).getText())
    matches = re.search(r'Stardate:[ \xa0](\d+\.?\d+?|Unknown)[\s \xa0]+Original[\s \xa0]+Airdate:[ \xa0](.*)', stardate_airdate.replace('  ', ' '), re.IGNORECASE)

    episode['stardate'] = matches[1]
    episode['airdate'] = extractDate(matches[2].strip())
    episode['schedule'] = getSeasonDataFromEpisode(int(entry.name[:-4]))

    full_script = soup.find('td', {'width': '85%'}).getText()

    # split on scenes
    cleaned_script = re.sub(r'](?=[A-Z])', ']\n', full_script.strip().replace('\n\n\n', '\n\n').replace(u'\xa0', ' '))
    cleaned_script = re.sub(r'\)(?=[A-Z])', ') ', cleaned_script)
    scenes = re.split(r'((?<!\w )\[[^:]*?\] *\n)', cleaned_script, flags=re.DOTALL)
    cleaned_scenes = scrubList(scenes)
    # print(cleaned_scenes)

    episode['scenes'] = []
    while len(cleaned_scenes) != 0:
        scene = {}
        data = cleaned_scenes.pop(0).strip()
        if len(data) == 0:
            continue

        if data[0] == '[':
            scene['location'] = data.replace('[', '').replace(']', '').strip()
            possible_lines = cleaned_scenes.pop(0).strip()
            if len(possible_lines) > 0:
                scene['dialogue'] = getLinesFromStringBlock(possible_lines)
            else:
                continue
        else:
            scene['location'] = 'unknown'
            scene['dialogue'] = getLinesFromStringBlock(data)

        episode['scenes'].append(scene)

    # for scene in episode['scenes']:
    #     if "." in scene['location'] or ":" in scene['location'] or "[" in scene['location'] or "]" in scene['location']:
    #         print("Bad loc:")
    #         print(scene['location'])
    #     for dialogue in scene['dialogue']:
    #         if len(dialogue['character']) > 40 or "." in dialogue['character'] or ":" in dialogue['character'] or "[" in dialogue['character'] or "]" in dialogue['character']:
    #             print("Bad char:")
    #             print(dialogue['character'])
    #         if "[" in dialogue['line'] or "]" in dialogue['line']:
    #             print("Bad line:")
    #             print(dialogue['line'])

    # print("processed/voy/s%se%s.json" % (str(episode['schedule']['season']).zfill(2), str(episode['schedule']['episode']).zfill(2)))
    with open("processed/voy/s%se%s.json" % (str(episode['schedule']['season']).zfill(2), str(episode['schedule']['episode']).zfill(2)), 'w') as outfile:
        string_script = replace(json.dumps(episode))
        json.dump(json.loads(string_script), outfile, indent=2, sort_keys=True)
