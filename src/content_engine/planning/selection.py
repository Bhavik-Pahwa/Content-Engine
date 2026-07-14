"""Deterministic selection helpers for planning variety."""

from __future__ import annotations

from hashlib import sha256


def choose_rotating(options: tuple[str, ...], *, seed: str, offset: int = 0) -> str:
    if not options:
        raise ValueError("options cannot be empty")
    digest = sha256(seed.encode("utf-8")).hexdigest()
    index = (int(digest[:8], 16) + offset) % len(options)
    return options[index]


def choose_persona(options: tuple[str, ...], *, category: str, difficulty_level: str, seed: str, offset: int = 0) -> str:
    preferred = _preferred_personas(category, difficulty_level)
    for persona in preferred:
        if persona in options:
            return persona
    return choose_rotating(options, seed=seed, offset=offset)


def _preferred_personas(category: str, difficulty_level: str) -> tuple[str, ...]:
    if difficulty_level == "introductory":
        return ("Educator", "Minimalist")
    if category in {"Artificial Intelligence", "Software Engineering", "Cloud Infrastructure", "Cybersecurity"}:
        return ("Engineer", "Researcher")
    if category == "Startups":
        return ("Founder", "Educator")
    return ("Engineer", "Educator")

