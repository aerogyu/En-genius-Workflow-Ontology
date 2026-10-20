"""역량 질의 — queries/q01~q08.rq (SPARQL 1.1 표준만, rdflib 와 Fuseki 가 같은 결과).

로컬(rdflib): 빌드 출력의 workflow.ttl ∪ workflow_derived.ttl (+ --catalog 로 Tool 온톨로지 survey.ttl) 을 한 그래프로 묻는다.
Fuseki: named graph 2개(작성·파생)로 올린 뒤 질의 앞에 FROM <작성> FROM <파생> 을 넣어 같은 기본 그래프를 만든다 (with_from).
q07·q08 은 교차 질의 — Tool 온톨로지 그래프가 함께 있어야 의미가 있다.
화면: 기본은 탭으로 나눈 줄(다른 프로그램에 붙여 넣기 쉽게), --table 은 칸을 맞춘 표 (scripts\\query.bat).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from rdflib import Graph

from engenius_wf.config import QUERIES_DIR

SHORT_IRIS = (("http://en-genius.local/id/", "egid:"), ("http://qudt.org/vocab/unit/", "unit:"))


def query_files(queries_dir: Path | None = None) -> dict[str, Path]:
    """{'q01': 경로, ...} — 파일 이름 앞부분(qNN)이 질의 이름."""
    return {p.name.split("_", 1)[0]: p for p in sorted(Path(queries_dir or QUERIES_DIR).glob("q*.rq"))}


def query_title(path: Path) -> str:
    """질의 파일 첫 주석 줄 (# 뒤) — 화면 제목."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return path.stem


def with_from(text: str, graphs) -> str:
    """질의의 첫 WHERE 앞에 FROM <g> 를 넣는다 (주석·PREFIX 줄은 건너뛴다) — Fuseki 에서 named graph 들을 기본 그래프로 묻기."""
    lines = text.splitlines()
    clause = " ".join(f"FROM <{g}>" for g in graphs) + " "
    for i, line in enumerate(lines):
        s = line.lstrip()
        if s.startswith("#") or s.upper().startswith("PREFIX"):
            continue
        mt = re.search(r"\bWHERE\b", line, flags=re.I)
        if mt:
            lines[i] = line[:mt.start()] + clause + line[mt.start():]
            return "\n".join(lines) + "\n"
    raise ValueError("질의에 WHERE 가 없다 — FROM 을 넣을 자리를 못 찾음")


def union_graph(out_dir: Path, catalogs=()) -> Graph:
    """빌드 출력(작성 ∪ 파생) + 카탈로그 — rdflib 로컬 질의용 한 그래프."""
    g = Graph()
    g.parse(Path(out_dir) / "workflow.ttl", format="turtle")
    g.parse(Path(out_dir) / "workflow_derived.ttl", format="turtle")
    for c in catalogs:
        g.parse(c, format="turtle")
    return g


def short(v) -> str:
    s = "" if v is None else str(v)
    for full, pfx in SHORT_IRIS:
        s = s.replace(full, pfx)
    return s


def run_local(g: Graph, text: str) -> tuple[list[str], list[tuple[str, ...]]]:
    """(변수 이름, 정렬한 행) — IRI 는 egid:·unit: 로 줄인다 (Fuseki 결과와 행 단위로 비교하는 꼴)."""
    res = g.query(text)
    names = [str(v) for v in res.vars]
    return names, sorted(tuple(short(x) for x in r) for r in res)


def is_cross(text: str) -> bool:
    """Tool 온톨로지 어휘(eg:)를 읽는 교차 질의인가 (q07·q08) — --catalog 없이는 그 열이 빈다."""
    return re.search(r"(?im)^\s*PREFIX\s+eg:", text) is not None


def cell_width(s: str) -> int:
    """화면 칸 수 — 한글 등 전각(East Asian Wide·Fullwidth)은 2칸, 결합 문자는 0칸 (Windows Terminal·VS Code 터미널 기준)."""
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def render_table(cols, rows) -> list[str]:
    """질의 결과 → 칸을 맞춘 글자 표 (query --table, query.bat). 빈 결과는 '(결과 없음)' 한 줄."""
    clean = [[str(c).replace("\r", " ").replace("\n", " ").replace("\t", " ") for c in r] for r in rows]
    widths = [max([cell_width(c)] + [cell_width(r[i]) for r in clean]) for i, c in enumerate(cols)]

    def line(cells):
        return " | ".join(c + " " * (w - cell_width(c)) for c, w in zip(cells, widths)).rstrip()

    out = [line(list(cols)), "-+-".join("-" * w for w in widths)] + [line(r) for r in clean]
    return out + (["(결과 없음)"] if not rows else [])
