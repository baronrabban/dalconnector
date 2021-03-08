

# You have a WiFi sdcard.  What is the address you use to connect to it
# Make sure you can visit it in your web browser.  If you can load it in a web browser it's very likely it will work here.
# Enter just the address part.  For instance, if you visit it via "http://flashair/" just enter "flashair" here:
WIFI_CARD_ADDRESS = "flashaircard"  # an IP address or a hostname such as flashair




# Once you've loaded a song, do you want DAL Connector to periodically check for new saves?
# I.e., you've loaded song 8.  Now it will watch for 8b.  Then 8c.  Then 8d.
# If it finds one, it will try to load it
WATCH_FOR_NEW_SAVES =  True   # True or False


# If we're watching for new saves, when do we give up?  If one doesn't appear in X seconds, assume one isn't coming
# so we don't have to poll the wifi sdcard forever.
NEW_SAVE_SLEEP_TIMER = 600  # Integer seconds




# You should not need to change this at all
WEB_PATH_PREFIX = '/SONGS'


# You should not need to change this at all
SOCKET_TIMEOUT = 5


