from __future__ import absolute_import, print_function, unicode_literals

from ableton.v2.base import const, inject, listens
from ableton.v2.control_surface import ControlSurface

from .config import WATCH_FOR_NEW_SAVES
from .fetcher import ThreadShare
from .local import propername, displayname

from time import sleep
import Live
import logging
import time
import re

logger = logging.getLogger(__name__)


class DALConnector(ControlSurface):
    WATCH_INTERVAL_SLEEP = 10  # Wait time between polling, 20 is 2 seconds

    def __init__(self, *a, **k):
        super(DALConnector, self).__init__(*a, **k)
        with self.component_guard():
            self.finished = False
            self.eventloopstarted = False

            self.ts = None
            logger.info(u'--- DAL Connector Started ---')

            self.__on_selected_track_name_changed.subject = self.song.view

            self._resetvars()


    def disconnect(self):
        self.finished = True

        if self.ts:
            self.ts.disconnect()

        self._resetvars()


    @listens(u'selected_track.name')
    def __on_selected_track_name_changed(self):
        track = self.song.view.selected_track

        if self.targettrack and track != self.targettrack:
            return

        if not track.name.lower().startswith('dc:'):
            if self.targettrack and track == self.targettrack:
                self._resetvars()

            return

        if track.name.endswith(']'):
            return

        self.targettrack = track

        self.schedule_message(1, self.handletrackchange)

    def handletrackchange(self):
        view = self.song.view
        track = view.selected_track

        num = re.search(r'^dc: *(\d+[a-z]*)', track.name, re.IGNORECASE)
        if not num:
            # logger.info(u'ERR!  Invalid song number specified')
            return
        else:
            self.delugesong = propername(num.groups()[0])

        # logger.info(f'Deluge song is {self.delugesong}')

        if self.ts is None:
            self.ts = ThreadShare()


        self.ts.fetchsong(self.delugesong)

        self._addtrackmsg(f'[fetching...]')

        self.expectsong = self.delugesong

        if not self.eventloopstarted:
            self.eventloopstarted = True
            self.schedule_message(10, self.eventloop)


    def eventloop(self):
        if self.finished:
            return

        try:
            if self.ts is None:
                return

            if self.expectsong is None:
                if not WATCH_FOR_NEW_SAVES:
                    return

                nextsongdata = self.ts.getnextsongdata()

                if nextsongdata is not None:
                    self.delugesong = nextsongdata['delugesong']
                    # logger.info(f'[EVENT LOOP]: LOADING NEXT SONG!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                    self.loadsong(nextsongdata['songhsh'])

                value = self.ts.getwatchmsg()
                if value:
                    self._addtrackmsg(f'[{value}]')

                return

            value = self.ts.getwatchmsg()
            if value:
                self._addtrackmsg(f'[{value}]')

            self.expecttries += 1

            if self.expecttries > 60:
                self.expecttries = 0
                self.expectsong = None

                self._addtrackmsg('[error 5]')
                logger.info(f'Expected song never showed up!')
                return

            result = self.ts.getresult(self.expectsong)

            if result is not None:
                self.expecttries = 0
                self.expectsong = None

                if result['error']:
                    self._addtrackmsg('[error 2]')
                    return

                self.loadsong(result['songhsh'])

                if not WATCH_FOR_NEW_SAVES:
                    self._addtrackmsg('[synced]')

                return

        finally:
            self.schedule_message(10, self.eventloop)

    def _addtrackmsg(self, msg):
        if self.targettrack is None:
            return

        name = f'dc: {displayname(self.delugesong)} {msg.strip()}'

        self.targettrack.name = name


    def _ensureenoughscenes(self, numscenes):
        numscenes += 1

        if len(self.song.scenes) >= numscenes:
            return

        for i in range(0, numscenes - len(self.song.scenes)):
            self.song.create_scene(-1)


    def _ensureenoughtracks(self, numtracks):
        tracks = self.song.visible_tracks

        index = list(tracks).index(self.targettrack)

        allslots = []
        count = 0
        for i in range(index, len(tracks)):
            track = tracks[i]

            if track.has_midi_input:
                count += 1

                # CLEAR THE SLOTS
                for s in range(0, len(self.song.scenes)):
                    slot = track.clip_slots[s]

                    if not slot.has_clip:
                        continue

                    allslots.append(slot)
                    slot.clip.remove_notes_extended(from_time = 0, from_pitch = 0, time_span = slot.clip.loop_end, pitch_span = 128)
            else:
                break

        if count < numtracks:
            for i in range(0, numtracks - count):
                self.song.create_midi_track()

        return allslots


    def loadsong(self, songhsh):
        bpm = songhsh['bpm']
        numscenes = songhsh['numscenes']
        maxtrackid = songhsh['maxtrackid']
        clipmap = songhsh['clipmap']

        self.song.tempo = bpm

        self._ensureenoughscenes(numscenes)              # We need this many scenes
        allslots = self._ensureenoughtracks(maxtrackid)  # We need this many midi tracks

        tracks = self._addressabletracks()

        for cliphsh in clipmap:

            trackidx = cliphsh['trackidx']
            track = tracks[trackidx]

            sceneidx = cliphsh['sceneidx']
            length = cliphsh['length']

            # logger.info(f'CREATE CLIP: SCENEIDX: {sceneidx}  TrackIDX: {trackidx}')

            slot = track.clip_slots[sceneidx]
            if slot.has_clip:
                if slot.clip.length != length:
                    slot.delete_clip()
                    slot.create_clip(length)
            else:
                slot.create_clip(length)

            notes = cliphsh['notes']

            result = []
            for hsh in notes:

                result.append(Live.Clip.MidiNoteSpecification(
                    pitch = hsh['pitch'],
                    start_time = hsh['starttime'],
                    duration = hsh['duration'],
                    velocity = hsh['velocity'],
                    mute = 0,
                    probability = hsh['probability']
                    ))

            slot.clip.add_new_notes(result)

            # We used the clip
            if slot in allslots:
                allslots.remove(slot)


        # If we didn't use the clip, remove it
        for slot in allslots:
            slot.delete_clip()


    def _addressabletracks(self):
        tracks = self.song.visible_tracks

        index = list(tracks).index(self.targettrack)

        result = []
        for i in range(index, len(tracks)):
            if not tracks[i].has_midi_input:
                continue

            result.append(tracks[i])

        return result


    def _resetvars(self):
        self.delugesong = None      # SONG000.XML
        self.targettrack = None     # Which track is titled dc:
        self.watchfor = None        # The name of the new save we're watching for

        self.expecttries = 0
        self.expectsong = None

