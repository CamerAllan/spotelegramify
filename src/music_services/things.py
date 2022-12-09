from typing import List


class Track:
    def __init__(self, name, artist_name) -> None:
        self.name = name
        self.artist_name = artist_name

    @property
    def name() -> str:
        pass

    @property
    def artist_name() -> str:
        pass


class Playlist:
    def __init__(self, name, tracks, link, id) -> None:
        self.name = name
        self.tracks = tracks
        self.link = link
        self.id = id

    @property
    def name() -> str:
        pass

    @property
    def tracks() -> List[str]:
        pass

    @property
    def link() -> str:
        pass

    @property
    def id() -> str:
        pass
