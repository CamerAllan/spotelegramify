from typing import List
from music_services.music_service import MusicService


class Track:
    @property
    def name() -> str:
        pass

    @property
    def artist_name() -> str:
        pass

    @property
    def service() -> MusicService:
        pass


class Playlist:
    @property
    def name() -> str:
        pass

    @property
    def tracks() -> List(Track):
        pass

    @property
    def link() -> str:
        pass

    def id() -> str:
        pass
