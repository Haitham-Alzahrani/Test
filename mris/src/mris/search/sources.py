"""Source classification: professional vs audience, and a reliability weight per domain."""

from __future__ import annotations

from urllib.parse import urlparse

PROFESSIONAL: dict[str, tuple[str, float]] = {
    "rottentomatoes.com": ("Rotten Tomatoes", 0.9),
    "metacritic.com": ("Metacritic", 0.9),
    "variety.com": ("Variety", 1.0),
    "hollywoodreporter.com": ("The Hollywood Reporter", 1.0),
    "deadline.com": ("Deadline", 0.95),
    "indiewire.com": ("IndieWire", 0.95),
    "theguardian.com": ("The Guardian", 1.0),
    "apnews.com": ("AP", 1.0),
    "nytimes.com": ("The New York Times", 1.0),
    "latimes.com": ("Los Angeles Times", 1.0),
    "washingtonpost.com": ("The Washington Post", 1.0),
    "rogerebert.com": ("RogerEbert.com", 0.95),
    "empireonline.com": ("Empire", 0.9),
    "vulture.com": ("Vulture", 0.9),
    "slashfilm.com": ("/Film", 0.8),
    "ign.com": ("IGN", 0.8),
    "polygon.com": ("Polygon", 0.8),
    "theverge.com": ("The Verge", 0.75),
    "avclub.com": ("The A.V. Club", 0.85),
    "independent.co.uk": ("The Independent", 0.9),
    "telegraph.co.uk": ("The Telegraph", 0.9),
    "time.com": ("TIME", 0.9),
    "usatoday.com": ("USA Today", 0.85),
    "chicagotribune.com": ("Chicago Tribune", 0.85),
    "bbc.com": ("BBC", 0.9),
    "bbc.co.uk": ("BBC", 0.9),
    "collider.com": ("Collider", 0.7),
    "screenrant.com": ("Screen Rant", 0.6),
    "slantmagazine.com": ("Slant", 0.85),
    "theplaylist.net": ("The Playlist", 0.8),
    "thewrap.com": ("TheWrap", 0.85),
    "screendaily.com": ("Screen Daily", 0.9),
    "rollingstone.com": ("Rolling Stone", 0.9),
    "decider.com": ("Decider", 0.7),
}

AUDIENCE: dict[str, tuple[str, float]] = {
    "reddit.com": ("Reddit", 0.6),
    "imdb.com": ("IMDb", 0.7),
    "letterboxd.com": ("Letterboxd", 0.65),
    "themoviedb.org": ("TMDb", 0.6),
    "boxd.it": ("Letterboxd", 0.65),
}

LOW_VALUE = {
    "youtube.com",
    "tiktok.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
}


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _match(domain: str, table: dict[str, tuple[str, float]]) -> tuple[str, float] | None:
    for key, value in table.items():
        if domain == key or domain.endswith("." + key):
            return value
    return None


def classify_source(url: str) -> tuple[str, str, float]:
    """Return (source_type, publisher, reliability)."""
    domain = domain_of(url)
    if hit := _match(domain, PROFESSIONAL):
        return "professional", hit[0], hit[1]
    if hit := _match(domain, AUDIENCE):
        return "audience", hit[0], hit[1]
    if any(domain == d or domain.endswith("." + d) for d in LOW_VALUE):
        return "other", domain, 0.2
    return "other", domain, 0.45
