"""테스트 도우미 — 경로·예시 복사·실수 주입 편집·Jena(SHACL·Fuseki) 찾기. 데이터는 전부 공개 교과서 수준 예시·합성."""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

from engenius_wf.cli import main
from engenius_wf.config import EXAMPLES_DIR, GEN_DIR, REPO_ROOT

GOLDEN = Path(__file__).resolve().parent / "golden"
SYN_CATALOG = EXAMPLES_DIR / "catalog" / "tools_synthetic.ttl"
# 형제 저장소(Tool 온톨로지)의 합성 적재본 — 읽기만. 없으면(사내 등) 교차 테스트는 skip
SURVEY = Path(os.environ.get("WF_SURVEY_TTL")
              or REPO_ROOT.parent / "engenius-tool-ontology" / "output" / "20260930T230632" / "survey.ttl")
CODE_RE = re.compile(r"\[(오류|경고|참고) ([A-Z]\d\d)\]")


def catalogs_or_none() -> list[str] | None:
    return [str(SYN_CATALOG), str(SURVEY)] if SURVEY.is_file() else None


def copy_example(dst_root: Path, src: str, name: str | None = None, state: bool = True) -> Path:
    """예시 폴더 사본 — state=False 면 _registry·_released 없이 (새로 쓰는 사람 흉내)."""
    d = Path(dst_root) / (name or src)
    ignore = None if state else shutil.ignore_patterns("_registry", "_released")
    shutil.copytree(EXAMPLES_DIR / src, d, ignore=ignore)
    return d


def run_cli(args) -> tuple[int, str]:
    """python -m engenius_wf 를 프로세스 안에서 — (rc, 화면 출력)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = main([str(a) for a in args])
    return rc, buf.getvalue()


def codes(text: str) -> list[tuple[str, str]]:
    return CODE_RE.findall(text)


@dataclass
class Built:
    src: Path
    out: Path
    rc: int
    stdout: str

    @property
    def report(self) -> str:
        return (self.out / "report.txt").read_text(encoding="utf-8")

    def union(self) -> Graph:
        g = Graph()
        g.parse(self.out / "workflow.ttl", format="turtle")
        g.parse(self.out / "workflow_derived.ttl", format="turtle")
        return g


def build_copy(base: Path, src: str, name: str | None = None, catalogs=None) -> Built:
    d = copy_example(base, src, name)
    out = Path(base) / f"out_{name or src}"
    rc, text = run_cli(["build", d, "--out", out] + (["--catalog", *catalogs] if catalogs else []))
    return Built(d, out, rc, text)


def edit(path: Path, old: str, new: str | None):
    """실수 주입 — old 의 첫 자리를 new 로 (new=None: 그 자리부터 파일 끝까지 지움)."""
    t = path.read_text(encoding="utf-8")
    assert old in t, (path.name, old)
    t = t[: t.index(old)] if new is None else t.replace(old, new, 1)
    path.write_text(t, encoding="utf-8", newline="\n")


def acyclic(edges) -> bool:
    adj = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
    color = {}

    def dfs(u):
        color[u] = 1
        for v in adj.get(u, ()):
            if color.get(v) == 1 or (not color.get(v) and not dfs(v)):
                return False
        color[u] = 2
        return True
    return all(color.get(u) or dfs(u) for u in list(adj))


# --------------------------------------------------------------------------- Jena (SHACL · Fuseki)
def find_jena() -> tuple[str, Path] | None:
    """(java 실행파일, fuseki-server.jar) — FUSEKI_HOME·JAVA_HOME 환경변수, 없으면 개발 PC 배치(<저장소 상위>/tools/…)."""
    home = os.environ.get("FUSEKI_HOME")
    jar = Path(home) / "fuseki-server.jar" if home else None
    java = None
    jh = os.environ.get("JAVA_HOME")
    if jh:
        cand = Path(jh) / "bin" / ("java.exe" if os.name == "nt" else "java")
        java = str(cand) if cand.is_file() else None
    if not jar or not jar.is_file():
        dev = REPO_ROOT.parent / "tools"
        fus = sorted(dev.glob("apache-jena-fuseki-6.*")) + sorted(dev.glob("apache-jena-fuseki-5.*"))
        jar = fus[0] / "fuseki-server.jar" if fus else None
    if not java:
        dev_jdk = sorted((REPO_ROOT.parent / "tools").glob("jdk-*"))
        cand = dev_jdk[-1] / "bin" / ("java.exe" if os.name == "nt" else "java") if dev_jdk else None
        java = str(cand) if cand and cand.is_file() else shutil.which("java")
    if jar and jar.is_file() and java:
        return java, jar
    return None


def shacl(data: Graph, java: str, jar: Path) -> tuple[list[bool], list[tuple[str, str]]]:
    """Jena SHACL (생성 shape) — (sh:conforms 값들, [(속성 꼬리, 제약 컴포넌트 꼬리)]).
    Jena 는 Windows 절대경로를 IRI 로 받지 못하므로 임시 폴더에 복사해 상대경로로 넘긴다."""
    from rdflib import URIRef
    from rdflib.namespace import RDF

    with tempfile.TemporaryDirectory() as t:
        shutil.copyfile(GEN_DIR / "wfo.shacl.ttl", Path(t) / "s.ttl")
        data.serialize(Path(t) / "d.ttl", format="turtle")
        p = subprocess.run([java, "-cp", str(jar), "shacl.shacl", "validate", "--shapes", "s.ttl", "--data", "d.ttl"],
                           cwd=t, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    assert "conforms" in p.stdout, p.stderr[-800:]
    rep = Graph().parse(data=p.stdout, format="turtle")
    sh = "http://www.w3.org/ns/shacl#"
    conf = [bool(x.toPython()) for x in rep.objects(None, URIRef(sh + "conforms"))]
    res = [(str(rep.value(r, URIRef(sh + "resultPath"))).rsplit("/", 1)[-1].rsplit("#", 1)[-1],
            str(rep.value(r, URIRef(sh + "sourceConstraintComponent"))).rsplit("#", 1)[-1])
           for r in rep.subjects(RDF.type, URIRef(sh + "ValidationResult"))]
    return conf, res
