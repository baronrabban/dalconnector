from .config import WIFI_CARD_ADDRESS, WEB_PATH_PREFIX, SOCKET_TIMEOUT
from .config import WATCH_FOR_NEW_SAVES, NEW_SAVE_SLEEP_TIMER
from .deluge2ableton import Deluge2Ableton
from .local import propername, displayname

import _thread
import socket
import logging
import re
import time

from time import sleep

logger = logging.getLogger(__name__)


class Fetcher(object):
    MAX_RECURSION = 250

    SLEEPTIME = 1.0

    KNOWN_CACHE = {}           # What's the last known song in a series...  2, 2a, 2b, 2c...

    def start(self, ts):
        self.ts = ts
        self.nextsong = None
        self.scanstarttime = None

        # logger.info(f' FETCHER THREAD STARTING')

        try:
            self.loop()
        except Exception as e:
            logger.info(f'MAJOR THREAD EXCEPTION!  {e}')

    def loop(self):
        while True:
            if self.ts.isfinished():
                logger.info(u'THREAD EXIT')
                return

            delugesong = self.ts.targetsong()
            if delugesong is not None:
                self.nextsong = None
                self._mainfetch(delugesong)

            if self.nextsong is not None:
                self._nextsongfetch()

            sleep(self.SLEEPTIME)

    def _mainfetch(self, delugesong):
        # logger.info(f'Expected song fetch: {delugesong}')

        for i in range(0, 5):
            try:
                xml = self.fetch(delugesong)

                if xml is None:
                    continue

                break
            except Exception as e:
                self.ts.setresult(delugesong = delugesong, xml = None, error = True)
                logger.info(f'DAL Connector - wait for song - ERROR! - {e}')
                return

        if not xml:
            self.ts.setresult(delugesong = None, xml = None, error = True)
            return

        self.ts.setresult(delugesong = delugesong, xml = xml, error = False)
        self.nextsong = self._findunusedname(delugesong)

        # logger.info(f'Fetcher complete')


    def _nextsongfetch(self):
        if self.scanstarttime and time.time() - self.scanstarttime > NEW_SAVE_SLEEP_TIMER:
            self.nextsong = None
            self.ts.setwatchmsg('sleep')
            logger.info(f'! Going to sleep !')
            return

        # logger.info(f'Checking for next song: {self.nextsong}')

        try:
            xml = self.fetch(self.nextsong)

            if not xml:
                # logger.info(f'Next song isnt there yet...')
                return

        except Exception as e:
            logger.info(f'DAL Connector - next song - ERROR! - {e}')
            return

        # logger.info(f'NEXT SONG IS THERE!!!')

        self.ts.setnextsongdata(delugesong = self.nextsong, xml = xml, error = False)

        self.nextsong = self._nextsongname(self.nextsong)
        self.ts.setwatchmsg(displayname(self.nextsong))


    # If they load 017 but have 017A and 017B and 017C we need to find the first one which isn't there
    def _findunusedname(self, delugesong):
        self.scanstarttime = time.time()

        self.ts.setwatchmsg('scanning...')

        ######################################################
        # CACHE LOOKUP
        if delugesong in self.KNOWN_CACHE:
            blankname = self.KNOWN_CACHE[delugesong]
        else:
            blankname = delugesong
        ######################################################

        for i in range(0, self.MAX_RECURSION):
            self.KNOWN_CACHE[delugesong] = blankname

            prev = blankname
            blankname = self._nextsongname(blankname)

            # logger.info(f'TRYING: {blankname}')
            xml = self.fetch(blankname)

            if xml is None:
                # logger.info(f'RETRY SOCKET')
                blankname = prev
                continue

            if len(xml) > 0:
                logger.info(f'{len(xml)}')
                continue

            # logger.info(f'FOUND BLANK NAME!  {blankname}')
            self.ts.setwatchmsg(displayname(blankname))
            return blankname

        logger.info(f'ERROR!  MAX RECURSION')
        self.ts.setwatchmsg('error')
        return None


    def fetch(self, delugesong):
        if not delugesong:
            return ''

        url = f'/{WEB_PATH_PREFIX}/SONG{delugesong}.XML'

        request = f"GET {url} HTTP/1.0\r\nHost: {WIFI_CARD_ADDRESS}\r\n\r\n"

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((WIFI_CARD_ADDRESS, 80))
            s.send(request.encode('utf-8'))

            body = ""

            while True:
                part = s.recv(999999)

                if not part:
                    break

                body += part.decode('utf-8')

            s.close()
        except Exception as e:
            logger.info(f'ERROR: Socket Exception {e}')
            return None


        if "\r\n\r\n" in body:
            return body.split("\r\n\r\n", 2)[1]

        return ''



    def _nextsongname(self, name):
        def nextletter(letter):
           return chr((ord(letter) - 64) % 26 + 65)

        if not name:
            return None

        name = propername(name)

        if name.isdecimal():
            return f"{name}A"

        if name.endswith('Z'):
            return propername(f"{str(int(name[0:-1]) + 1)}")

        return f"{name[0:-1]}{nextletter(name[-1])}"




class ThreadShare(object):
    def __init__(self):
        self.watchmsg = None
        self.finished = False
        self.reset()

        try:
            self.fetcher = Fetcher()
            _thread.start_new_thread(self.fetcher.start, (self, ) )
        except Exception as e:
            logger.info(f'Error: unable to start thread {e}')

    def reset(self):
        self.delugesong = None
        self.currentsongdata = None
        self.nextsongdata = None


    ############################################
    # CURRENT SONG
    def targetsong(self):
        return self.delugesong

    def fetchsong(self, delugesong):
        self.currentsongdata = None

        self.delugesong = delugesong

    def setresult(self, delugesong, xml, error):
        self.delugesong = None

        if not xml:
            self.currentsongdata = { 'songhsh': None, 'error': True }
        else:
            songhsh = Deluge2Ableton.convert(xml)
            self.currentsongdata = { 'songhsh': songhsh, 'error': error }

    def getresult(self, delugesong):
        # delugesong should never be None
        if delugesong is None:
            return { 'xml': None, 'error': True }

        if self.currentsongdata is None:
            return None

        value = self.currentsongdata
        self.currentsongdata = None

        return value


    ############################################
    # NEXT SONG
    def getnextsongdata(self):
        if not self.nextsongdata:
            return None

        value = self.nextsongdata
        self.nextsongdata = None
        return value

    def setnextsongdata(self, delugesong, xml, error):
        songhsh = Deluge2Ableton.convert(xml)

        self.nextsongdata = { 'songhsh': songhsh, 'error': error, 'delugesong': delugesong }

    ############################################
    # SCANNING
    def setwatchmsg(self, msg):
        self.watchmsg = msg

    def getwatchmsg(self):
        if self.watchmsg is None:
            return self.watchmsg

        value = self.watchmsg
        self.watchmsg = None
        return value

    ############################################

    def isfinished(self):
        return self.finished

    def disconnect(self):
        self.reset()
        # logger.info(u'Tracker knows we are done....')
        self.finished = True


