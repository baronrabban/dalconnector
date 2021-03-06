import json
import re
import sys

class Instrument(object):
    PPQN = 24 * 4

    def __init__(self, header, body, instrumentname):
        self.header = header
        self.body = body
        self.instrumentname = instrumentname

    ################################################################
    # Section aka scene
    ################################################################
    def section(self):
        section = re.search(r'section="(\d+)"', self.header)
        if not section:
            return 0
        else:
            return int(section.groups()[0])

    def length(self):
        length = re.search(r'length="(\d+)"', self.header)

        if not length:
            return 0
        else:
            return int(length.groups()[0]) / self.PPQN


    def _decodenotes(self, pitch, notedata):
        notes = []

        pos = 2
        while pos < len(notedata):
            notehex = notedata[pos:pos+20]
            starttime = int(notehex[0:8], 16)
            duration = int(notehex[8:16], 16)
            velocity = int(notehex[16:18], 16)
            probability = int(notehex[18:20], 16) & 0x7F

            hsh = {}
            hsh['pitch'] = pitch
            hsh['duration'] = duration / self.PPQN
            hsh['velocity'] = velocity
            hsh['probability'] = (probability * 5) / 100
            hsh['starttime'] = starttime / self.PPQN

            notes.append(hsh)

            pos += 20

        return notes


    def identifier(self):
        identifier = re.search(r'instrumentPresetSlot="(.+?)"', self.header)
        if not identifier:
            return None

        identifier = int(identifier.groups()[0])

        #############################

        subidentifier = re.search(r'instrumentPresetSubSlot="(.+?)"', self.header)
        if not subidentifier:
            return None

        subidentifier = int(subidentifier.groups()[0])

        return f'{self.instrumentname} {identifier}.{subidentifier}'


    @classmethod
    def build(self, header, body):
        if '<kitParams' in body:
            return Kit(header, body)
        elif 'midiChannel="' in header:
            return Midi(header, body)
        elif 'oscAVolume=' in body:
            return Synth(header, body)
        else:
            return None


class Midi(Instrument):
    def __init__(self, header, body):
        super().__init__(header = header, body = body, instrumentname = 'midi')


    def midichannel(self):
        midichannel = re.search(r'midiChannel="(\d+)"', self.header)
        if not midichannel:
            return 0
        else:
            return int(midichannel.groups()[0])

    def identifier(self):
        return f'{self.instrumentname} {self.midichannel()}'


    def notes(self):
        arr = []
        for n in re.findall(r'<noteRow.+?y="(\d+)".+?noteData="(.+?)"', self.body, re.DOTALL):
            notes = self._decodenotes(pitch = int(n[0]), notedata = n[1])
            arr.append(notes)

        return arr



class Synth(Instrument):
    def __init__(self, header, body):
        super().__init__(header = header, body = body, instrumentname = 'synth')


    def notes(self):
        arr = []
        for n in re.findall(r'<noteRow.+?y="(\d+)".+?noteData="(.+?)"', self.body, re.DOTALL):
            notes = self._decodenotes(pitch = int(n[0]), notedata = n[1])
            arr.append(notes)

        return arr

class Kit(Instrument):
    def __init__(self, header, body):
        super().__init__(header = header, body = body, instrumentname = 'kit')


    def notes(self):
        arr = []

        for n in re.findall(r'<noteRow.+?noteData="(.+?)".+?drumIndex="(\d+)"', self.body, re.DOTALL):
            notes = self._decodenotes(pitch = 36 + int(n[1]), notedata = n[0])

            arr.append(notes)

        return arr


class Deluge2Ableton(object):
    DEFAULT_BPM = 120

    def init(self, xml):
        self.xml = xml

    @classmethod
    def convert(self, xml):
        maxsceneid = 0
        clipmap = {}   # Order doesn't matter.  Each clip is a bucket of notes with key of identifier/sceneid

        trackmap = {}  # Figure out the track index based on its identifier

        ordering = []  # Maintain the order in which tracks appeared via their identifier

        # The instruments are in reverse order that you'd expect them in Ableton
        for m in reversed(re.findall(r'<instrumentClip(.+?)>(.+?)</instrumentClip>', xml, re.DOTALL)):
            o = Instrument.build(m[0], m[1])

            if not o:
                continue

            sceneid = o.section()
            maxsceneid = max(maxsceneid, sceneid)
            identifier = o.identifier()

            if not identifier:
                continue

            key = f'{identifier}|{sceneid}'
            if key not in clipmap:
                clipmap[key] = []

            if identifier not in ordering:
                trackmap[identifier] = len(ordering)
                ordering.append(identifier)

            for notedata in o.notes():
                clipmap[key].append({
                    'length': o.length(),
                    'trackidx': trackmap[identifier],
                    'sceneidx': sceneid,
                    'notes': notedata,
                    })

        result = []
        for value in clipmap.values():
            result += value

        bpm = self._extractbpm(xml)

        songhsh = { 'bpm': bpm, 'numscenes': maxsceneid, 'clipmap': list(reversed(result)), 'maxtrackid': len(ordering) }


        return songhsh



    @classmethod
    def _extractbpm(self, xml):
        tptt = re.search(r'timePerTimerTick="(\d+)"', xml)
        if not tptt:
            return self.DEFAULT_BPM
        else:
            tptt = int(tptt.groups()[0])

        ttf = re.search(r'timerTickFraction="(-*\d+)"', xml)
        if not ttf:
            return self.DEFAULT_BPM
        else:
            ttf = int(ttf.groups()[0])

        itm = re.search(r'inputTickMagnitude="(\d+)"', xml)
        if not itm:
            return self.DEFAULT_BPM
        else:
            itm = int(itm.groups()[0])

        ttf /= 0x100000000

        tempo = (551250 / (ttf + tptt)) / (10 * itm)

        if tempo <= 0:
            return self.DEFAULT_BPM

        return int(tempo)


if __name__ == "__main__":
    # with open('./EXAMPLE_SYNTH.XML') as f:
    # with open('./EXAMPLE_MIDI.XML') as f:
    with open('./SONG002.XML') as f:
        readdata = f.read()

    result = Deluge2Ableton.convert(readdata)

    print(json.dumps(result, indent = 4, sort_keys = True))




