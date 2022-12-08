import logging
import re
from abc import ABC, abstractmethod, abstractproperty
from typing import Dict, List

from music_services.spotify import SpotifyMusicService
from music_services.things import Playlist, Track
from music_services.tidal import TidalMusicService

logger = logging.getLogger(__name__)

MUSIC_SERVICES = {"spotify": SpotifyMusicService, "tidal": TidalMusicService}


class MusicService(ABC):
    def __init__(self):
        self.refresh_auth()

    def find_track_ids(self, message) -> List:
        return re.findall(self.regex, message)

    @abstractproperty
    def name(self) -> str:
        pass

    @abstractproperty
    def id(self) -> str:
        pass

    @abstractproperty
    def regex(self):
        pass

    @abstractmethod
    def refresh_auth(self):
        pass

    @abstractmethod
    def lookup_service_track(self, track_id) -> Dict:
        pass

    @abstractmethod
    def lookup_service_playlist(self, playlist_id) -> Dict:
        pass

    # Do this using track init
    @abstractmethod
    def convert_tracks(self, track: List()) -> List(Track):
        pass

    @abstractmethod
    def convert_playlist(self, track) -> Playlist:
        pass

    @abstractmethod
    def add_to_playlist(self, playlist: Dict, service_track: Dict):
        pass

    @abstractmethod
    def search_track(self, track: Track):
        pass

    @abstractmethod
    def playlist_contains_track(self, playlist_id: str, service_track: Dict):
        pass


def get_available_music_services() -> List(MusicService):
    return MUSIC_SERVICES.values()


def get_music_service_by_name(name):
    return MUSIC_SERVICES.get(name, None)
