import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List

from .things import Playlist, Track

logger = logging.getLogger(__name__)


class MusicService(ABC):
    def __init__(self):
        self.refresh_auth()

    def find_album_ids(self, message: str) -> List:
        return re.findall(self.album_regex, message)

    def find_track_ids(self, message: str) -> List:
        return re.findall(self.track_regex, message)

    def name(self) -> str:
        pass

    def id(self) -> str:
        pass

    def album_regex(self):
        pass

    def track_regex(self):
        pass

    @abstractmethod
    def refresh_auth(self):
        pass

    @abstractmethod
    def get_service_track_from_album(self, service_album: Dict) -> Dict:
        pass

    @abstractmethod
    def lookup_service_album(self, album_id: str) -> Dict:
        pass

    @abstractmethod
    def lookup_service_track(self, track_id: str) -> Dict:
        pass

    @abstractmethod
    def lookup_service_playlist(self, playlist_id: str) -> Dict:
        pass

    # Do this using track init
    @abstractmethod
    def convert_tracks(self, track: List[any]) -> List[Track]:
        pass

    @abstractmethod
    def convert_playlist(self, playlist: List[any]) -> List[Playlist]:
        pass

    @abstractmethod
    def add_to_playlist(self, playlist, service_track):
        pass

    @abstractmethod
    def search_track(self, track: Track):
        pass

    @abstractmethod
    def playlist_contains_track(self, playlist_id: str, service_track):
        pass


def get_music_service_by_id(services: List[MusicService], id: str) -> MusicService:

    matching_services = [s for s in services if s.id == id.lower()]
    if len(matching_services) < 1:
        logger.info(f"Invalid service {id}.")
        return None

    return matching_services[0]


def get_all_music_services():
    return MusicService.__subclasses__()
