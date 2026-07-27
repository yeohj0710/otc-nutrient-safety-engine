"""초록의 문장 단위 locator 유틸.

문헌 근거 연결은 "초록 어느 문장인가"를 반드시 밝혀야 한다. 이 모듈은 그 문장 분할을
한 곳에서만 정의해, 검색 도구와 빌더가 같은 인덱스를 쓰도록 한다. 분할 규칙이 바뀌면
기존 locator 가 전부 어긋나므로 규칙을 바꿀 때는 링크 검증을 반드시 다시 돌려야 한다.
"""

from __future__ import annotations

import re

# 문장 끝처럼 보이지만 아닌 축약형. 의학 초록에서 실제로 걸리는 것만 넣는다.
_ABBREVIATIONS = (
    "vs.",
    "e.g.",
    "i.e.",
    "etc.",
    "approx.",
    "no.",
    "cf.",
    "Dr.",
    "Fig.",
    "et al.",
    "ca.",
    "min.",
    "max.",
    "wk.",
    "mo.",
)

_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def split_sentences(abstract: str) -> list[str]:
    """초록을 1-기반 인덱스로 참조할 문장 목록으로 자른다."""
    text = " ".join((abstract or "").split())
    if not text:
        return []
    pieces = _SPLIT_PATTERN.split(text)
    merged: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if merged and merged[-1].lower().endswith(_ABBREVIATIONS):
            merged[-1] = f"{merged[-1]} {piece}"
            continue
        merged.append(piece)
    return merged


def sentence_at(abstract: str, index: int) -> str:
    """1-기반 문장 인덱스로 문장을 돌려준다. 범위를 벗어나면 예외를 던진다."""
    sentences = split_sentences(abstract)
    if not 1 <= index <= len(sentences):
        raise IndexError(f"sentence index {index} out of range 1..{len(sentences)}")
    return sentences[index - 1]


def locator_label(index: int) -> str:
    """CSV·산출물에 저장하는 locator 표기."""
    return f"abstract:sentence:{index}"


def parse_locator(locator: str) -> int:
    match = re.fullmatch(r"abstract:sentence:(\d+)", locator.strip())
    if not match:
        raise ValueError(f"invalid locator: {locator!r}")
    return int(match.group(1))
