"""Movie identity: lookup by title/year/alias/TMDb id, creation and trait storage."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from mris.models import Movie, MovieAlias, MovieTrait
from mris.text import normalize_title


class MovieRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, movie_id: int) -> Movie | None:
        return self.s.get(Movie, movie_id)

    def by_tmdb(self, tmdb_id: int) -> Movie | None:
        return self.s.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))

    def find(self, title: str, year: int | None = None) -> Movie | None:
        """Find a movie by title (or alias). With a year the match is exact; a stored row
        without a year still matches (the user often names movies without years)."""
        key = normalize_title(title)
        if not key:
            return None
        rows = list(self.s.scalars(select(Movie).where(Movie.normalized_title == key)))
        alias_rows = self.s.scalars(select(Movie).join(MovieAlias).where(MovieAlias.normalized_alias == key))
        rows += [m for m in alias_rows if m not in rows]
        if not rows:
            return None
        if year is not None:
            exact = [m for m in rows if m.year == year]
            if exact:
                return exact[0]
            undated = [m for m in rows if m.year is None]
            return undated[0] if undated else None
        return max(rows, key=lambda m: (m.year or 0, m.id))

    def find_all(self, title: str) -> list[Movie]:
        key = normalize_title(title)
        return list(self.s.scalars(select(Movie).where(Movie.normalized_title == key)))

    def get_or_create(self, title: str, year: int | None = None, **fields: Any) -> tuple[Movie, bool]:
        movie = self.find(title, year)
        if movie is not None:
            if year is not None and movie.year is None:
                movie.year = year  # the user mentioned it without a year; now we know it
            for key, value in fields.items():
                if value is not None and getattr(movie, key, None) in (None, [], {}, ""):
                    setattr(movie, key, value)
            return movie, False
        movie = Movie(title=title.strip(), normalized_title=normalize_title(title), year=year, **fields)
        self.s.add(movie)
        self.s.flush()
        return movie, True

    def add_alias(self, movie: Movie, alias: str, language: str | None = None) -> None:
        key = normalize_title(alias)
        if not key or key == movie.normalized_title:
            return
        exists = self.s.scalar(
            select(MovieAlias).where(MovieAlias.movie_id == movie.id, MovieAlias.normalized_alias == key)
        )
        if exists is None:
            self.s.add(MovieAlias(movie_id=movie.id, alias=alias, normalized_alias=key, language=language))

    def set_traits(self, movie: Movie, traits: dict[str, float] | Iterable[str], source: str) -> None:
        values = traits if isinstance(traits, dict) else {t: 1.0 for t in traits}
        existing = {
            t.trait: t
            for t in self.s.scalars(
                select(MovieTrait).where(MovieTrait.movie_id == movie.id, MovieTrait.source == source)
            )
        }
        for trait, value in values.items():
            value = max(0.0, min(1.0, float(value)))
            if trait in existing:
                existing[trait].value = value
            else:
                self.s.add(MovieTrait(movie_id=movie.id, trait=trait, value=value, source=source))
        self.s.flush()

    def traits(self, movie_id: int) -> dict[str, float]:
        """Merged trait vector; user/seed statements win over research-derived values."""
        priority = {"research": 0, "metadata": 1, "seed": 2, "user": 3}
        merged: dict[str, tuple[int, float]] = {}
        for t in self.s.scalars(select(MovieTrait).where(MovieTrait.movie_id == movie_id)):
            p = priority.get(t.source, 0)
            if t.trait not in merged or p >= merged[t.trait][0]:
                merged[t.trait] = (p, t.value)
        return {k: v for k, (_, v) in merged.items()}

    def list(self, limit: int = 200, offset: int = 0, query: str | None = None) -> list[Movie]:
        stmt = select(Movie).order_by(Movie.year.desc().nulls_last(), Movie.title)
        if query:
            stmt = stmt.where(Movie.normalized_title.contains(normalize_title(query)))
        return list(self.s.scalars(stmt.limit(limit).offset(offset)))

    def known_titles(self) -> list[tuple[str, Movie]]:
        """(normalized title or alias, movie) pairs, longest first - used to spot titles in free text."""
        pairs: list[tuple[str, Movie]] = [(m.normalized_title, m) for m in self.s.scalars(select(Movie))]
        for alias in self.s.scalars(select(MovieAlias)):
            pairs.append((alias.normalized_alias, alias.movie))
        return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
