from typing import List


class Track:
    def __init__(self, name, artist_name) -> None:
        self.name = name
        self.artist_name = artist_name

    def name() -> str:
        pass

    def artist_name() -> str:
        pass


class Playlist:
    def __init__(self, name, tracks, link, id) -> None:
        self.name = name
        self.tracks = tracks
        self.link = link
        self.id = id

    def name() -> str:
        pass

    def tracks() -> List[Track]:
        pass

    def link() -> str:
        pass

    def id() -> str:
        pass
