#!/usr/bin/env python3

import glob
import json


def _fuzzyListContains(haystack, needles):
    for needle in needles:
        needleFound = False
        for parent in haystack:
            if needle.lower() in parent.lower():
                needleFound = True
        if not needleFound:
            return False

    return True


def _fuzzyListMatches(haystack, needles):
    if len(haystack) != len(needles):
        return False

    for needle in needles:
        needleFound = False
        for parent in haystack:
            if needle.lower() in parent.lower():
                needleFound = True
        if not needleFound:
            return False

    return True


class ScriptMechanic:
    def __init__(self, script):
        if not isinstance(script, dict):
            raise TypeError('Please load json into dict before initializing')

        self.scriptObj = script

    def getBriefEpisodeInfo(self):
        return f"s{str(self.scriptObj['schedule']['season']).zfill(2)}e{str(self.scriptObj['schedule']['episode']).zfill(2)} \"{self.scriptObj['title']}\""

    def printEpisode(self):
        print(f"Season {self.scriptObj['schedule']['season']} Episode {self.scriptObj['schedule']['episode']} (#{self.scriptObj['schedule']['number']})")
        print(f"\"{self.scriptObj['title']}\"")
        print(f"Stardate {self.scriptObj['stardate']}")
        print()
        for scene in self.scriptObj['scenes']:
            print(f"{scene['location'].upper()}")
            for line in scene['dialogue']:
                modifier = f" ({line['modifier']})" if 'modifier' in line else ""
                print(f"{line['character'].upper()}{modifier}: {line['line']}")
            print()

    def getSceneCharacters(self, scene):
        characters = set()
        for line in scene['dialogue']:
            characters.add(line['character'].upper())
        return characters

    def getEpisodeCharacters(self):
        characters = set()
        for scene in self.scriptObj['scenes']:
            characters.update(self.getSceneCharacters(scene))
        return characters

    def getScenesIncluding(self, characterList):
        if len(characterList) == 0:
            raise ValueError("Cannot process empty list of characters.")

        results = []
        for scene in self.scriptObj['scenes']:
            sceneChars = self.getSceneCharacters(scene)
            if _fuzzyListContains(sceneChars, characterList):
                results.append(scene)
        return results

    def getScenesWithOnly(self, characterList):
        if len(characterList) == 0:
            raise ValueError("Cannot process empty list of characters.")

        results = []
        for scene in self.scriptObj['scenes']:
            sceneChars = self.getSceneCharacters(scene)
            if _fuzzyListMatches(sceneChars, characterList):
                results.append(scene)
        return results

    def getScenesWithKeyword(self, line):
        results = []
        for scene in self.scriptObj['scenes']:
            for dialogue in scene['dialogue']:
                if line.lower() in dialogue['line'].lower():
                    results.append(scene)
        return results

    def getScenesInLocation(self, location):
        results = []
        for scene in self.scriptObj['scenes']:
            if scene['location'].lower() == location.lower():
                results.append(scene)
        return results

    def dump(self, chars = None):
        for scene in self.scriptObj['scenes']:
            for line in scene['dialogue']:
                if not chars or line['character'] in chars:
                    print(f"{line['character'].upper()}: {line['line']}")


class ScriptMechanicFlock:
    def __init__(self, scriptFolder):
        self.scripts = []

        for filepath in glob.iglob(scriptFolder + '/*.json'):
            with open(filepath) as scriptFile:
                data = json.load(scriptFile)
                self.scripts.append(ScriptMechanic(data))

        if len(self.scripts) == 0:
            print("WARNING! No scripts loaded. Must be pointed at flat folder containing JSON blobs")

    def dumpEpisodeBriefs(self):
        for episode in self.scripts:
            print(episode.getBriefEpisodeInfo())

    def getScenesWithKeyword(self, line):
        results = {}
        for episode in self.scripts:
            singleResults = episode.getScenesWithKeyword(line)
            if singleResults:
                results[episode.getBriefEpisodeInfo()] = singleResults
        return results

    def getScenesIncluding(self, characterList):
        results = {}
        for episode in self.scripts:
            singleResults = episode.getScenesIncluding(characterList)
            if singleResults:
                results[episode.getBriefEpisodeInfo()] = singleResults
        return results

    def getScenesWithOnly(self, characterList):
        results = {}
        for episode in self.scripts:
            singleResults = episode.getScenesWithOnly(characterList)
            if singleResults:
                results[episode.getBriefEpisodeInfo()] = singleResults
        return results

    def getScenesInLocation(self, location):
        results = {}
        for episode in self.scripts:
            singleResults = episode.getScenesInLocation(location)
            if singleResults:
                results[episode.getBriefEpisodeInfo()] = singleResults
        return results

    def _intersection(self, scenesA, scenesB):
        scenes = {}
        for episode_name in list(set(scenesA.keys())):
            if episode_name not in scenesB.keys():
                continue

            episode_scenes_A = [json.dumps(scene, sort_keys=True) for scene in scenesA[episode_name]]
            episode_scenes_B = [json.dumps(scene, sort_keys=True) for scene in scenesB[episode_name]]

            # I don't know why duplicates crop up but I'm too tired to debug it, so this will do.
            common_scenes = [json.loads(scene) for scene in list(set([scene for scene in episode_scenes_A if scene in episode_scenes_B]))]

            if common_scenes:
                scenes[episode_name] = common_scenes
        return scenes

    def intersection(self, predicate_results):
        if len(predicate_results) == 1:
            return predicate_results

        result = predicate_results.pop()

        while predicate_results:
            result = self._intersection(result, predicate_results.pop())

        return result

    def printScenes(self, scenes):
        for episode_name in scenes.keys():
            for scene in scenes[episode_name]:
                print(f"{episode_name}, {scene['location']}")
                for line in scene['dialogue']:
                    modifier = f" ({line['modifier']})" if 'modifier' in line else ""
                    print(f"{line['character'].upper()}{modifier}: {line['line']}")
                print()

    def prettySearch(self, scenes):
        self.printScenes(self.intersection(scenes))

    def dump(self, chars = None):
        for episode in self.scripts:
            episode.dump(chars)


flock = ScriptMechanicFlock('processed/tng')
flock.dump(['VASH'])
# flock.prettySearch([flock.getScenesWithOnly(['worf', 'picard']),
#                     flock.getScenesInLocation('observation lounge'),
#                     flock.getScenesWithKeyword('did not see')])

# flock.prettySearch([flock.getScenesIncluding(['tasha', 'wesley']),
#                     flock.getScenesInLocation('bridge'),
#                     flock.getScenesWithKeyword('on top of the world')])

# flock.prettySearch([flock.getScenesIncluding(['troi', 'lwaxana']),
#                    flock.getScenesWithKeyword('little one')])
