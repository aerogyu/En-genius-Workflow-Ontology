"""레지스트리 (결정 Q1) — key → 무의미 일련번호 IRI, 개명은 renamed_from 으로 IRI 유지(G03), 사라진 key 는 폐기(G02),
예시 레지스트리를 실데이터 폴더에 쓰면 G01."""

from __future__ import annotations

import csv

from rdflib import Graph, Literal
from rdflib.namespace import OWL

from engenius_wf.model import EGID
from engenius_wf.registry import origin_of
from wfhelp import copy_example, edit, run_cli


def _ids(d):
    with (d / "_registry" / "ids.csv").open(encoding="utf-8", newline="") as f:
        return {(r["kind"], r["key"]): (r["id"], r["status"]) for r in csv.DictReader(f)}


def test_new_registry_assigns_serials(tmp_path):
    d = copy_example(tmp_path, "short", state=False)
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 0, out
    ids = _ids(d)
    assert ids[("step", "cmp-meanline")] == ("STEP-000001", "활성")
    assert ids[("plan", "concept-design")] == ("PLAN-0001", "활성")
    assert (d / "_registry" / "origin.txt").read_text(encoding="utf-8") == "example\n"


def test_check_does_not_write_registry(tmp_path):
    d = copy_example(tmp_path, "short", state=False)
    assert run_cli(["check", d])[0] == 0
    assert not (d / "_registry").exists()


def test_rename_keeps_iri(tmp_path):
    d = copy_example(tmp_path, "short")
    before = _ids(d)[("step", "cmp-meanline")][0]
    for f in ("cmp.yaml", "perf.yaml"):
        t = (d / f).read_text(encoding="utf-8").replace("cmp-meanline", "cmp-1d-design")
        (d / f).write_text(t, encoding="utf-8", newline="\n")
    edit(d / "cmp.yaml", "    label: 압축기 1D 평균반경 설계", "    label: 압축기 1D 평균반경 설계\n    renamed_from: cmp-meanline")
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 0, out
    assert f"key 개명 cmp-meanline → cmp-1d-design: IRI {before} 유지" in out
    ids = _ids(d)
    assert ids[("step", "cmp-1d-design")] == (before, "활성") and ("step", "cmp-meanline") not in ids


def test_removed_key_is_deprecated(tmp_path):
    d = copy_example(tmp_path, "short")
    edit(d / "_plan.yaml", "  - {key: excel,   label: Excel}\n", "")
    edit(d / "cmp.yaml", "    tools: excel\n", "")
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 0, out
    assert "[경고 G02] 레지스트리  tool 'excel'(TRF-0002) 가 YAML 에서 사라짐 → 폐기 (IRI 재사용 안 함)" in out
    assert _ids(d)[("tool", "excel")] == ("TRF-0002", "폐기")
    g = Graph().parse(tmp_path / "out" / "workflow_derived.ttl", format="turtle")
    assert (EGID["TRF-0002"], OWL.deprecated, Literal(True)) in g


def test_example_registry_in_real_folder_g01(tmp_path):
    real = tmp_path / "data" / "real" / "workflows"
    real.mkdir(parents=True)
    d = copy_example(real, "short")
    assert origin_of(d) == "real"
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 1
    assert "[오류 G01]" in out and "예시 레지스트리를 실데이터에 쓰지 않는다" in out
