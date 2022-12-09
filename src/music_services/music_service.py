import logging
import re
from abc import ABC, abstractmethod, abstractproperty
from typing import Dict, List

from .things import Track

logger = logging.getLogger(__name__)


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
    def convert_tracks(self, track: List[Dict]) -> List[Track]:
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


def get_music_service_by_name(services: List[MusicService], name: str):

    matching_services = [s for s in services if s.name.lower() == name]
    if len(matching_services < 1):
        logger.info(f"Invalid service {name}.")
        return None

    return matching_services[0]


def get_all_music_services():
    return MusicService.__subclasses__()
