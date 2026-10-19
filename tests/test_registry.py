"""레지스트리 (결정 Q1) — key → 무의미 일련번호 IRI, 개명은 renamed_from 으로 IRI 유지(G03), 사라진 key 는 폐기(G02),
예시 레지스트리를 실데이터 폴더에 쓰면 G01."""

from __future__ import annotations

import csv

import pytest
from rdflib import Graph, Literal, URIRef
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
    assert "_registry·_released 폴더를 빼고 복사한다" in out


# --------------------------------------------------------------------------- W1 검토 수리 (renamed_from 무결성·폐기 행·사후 기입·G01 방향)
def _rename(d, old, new):
    """모든 YAML 에서 key 를 바꾼다 (renamed_from 없이 — 사람이 key 만 고친 것)."""
    for f in d.glob("*.yaml"):
        t = f.read_text(encoding="utf-8")
        f.write_text(t.replace(old, new), encoding="utf-8", newline="\n")


def _ids_rows(d):
    with (d / "_registry" / "ids.csv").open(encoding="utf-8", newline="") as f:
        return sorted((r["kind"], r["key"], r["id"], r["status"]) for r in csv.DictReader(f))


COPY_STEP = "\n  - key: cmp-meanline-copy\n    label: 복사한 단계\n    renamed_from: cmp-meanline\n"


def test_renamed_from_old_key_still_in_yaml_g04(tmp_path):
    """옛 key 를 남긴 채 복사본에 renamed_from 을 적으면 두 단계가 한 IRI 를 받는다 → G04 오류, 레지스트리 그대로."""
    d = copy_example(tmp_path, "short")
    before = (d / "_registry" / "ids.csv").read_text(encoding="utf-8")
    edit(d / "cmp.yaml", "    outputs: if-cmp-map\n", "    outputs: if-cmp-map\n" + COPY_STEP)
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 G04]" in out and "renamed_from 'cmp-meanline' 의 옛 key 가 아직 YAML 에 있다" in out
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 1 and (d / "_registry" / "ids.csv").read_text(encoding="utf-8") == before


def test_same_old_key_claimed_twice_g04(tmp_path):
    d = copy_example(tmp_path, "short")
    _rename(d, "cmp-meanline", "cmp-1d")
    edit(d / "cmp.yaml", "    label: 압축기 1D 평균반경 설계", "    label: 압축기 1D 평균반경 설계\n    renamed_from: cmp-meanline")
    edit(d / "cmp.yaml", "    outputs: if-cmp-map\n", "    outputs: if-cmp-map\n\n  - key: cmp-1d-b\n    label: 둘째\n    renamed_from: cmp-meanline\n")
    rc, out = run_cli(["check", d])
    assert rc == 1 and out.count("[오류 G04]") == 2 and "같은 옛 key 'cmp-meanline' 를 여럿(cmp-1d, cmp-1d-b)이" in out


def test_renamed_from_wins_over_deprecated_row(tmp_path):
    """폐기된 key 로 되돌리며 renamed_from 을 적으면 renamed_from 이 이긴다 (조용히 폐기 IRI 를 되살리지 않는다), 폐기 행은 기록으로 남는다."""
    d = copy_example(tmp_path, "short")
    _rename(d, "perf-cycle", "perf-cycle-old")
    assert run_cli(["build", d, "--out", tmp_path / "o1"])[0] == 0
    assert _ids(d)[("step", "perf-cycle-old")] == ("STEP-000003", "활성")
    _rename(d, "perf-cycle-old", "perf-cycle")
    edit(d / "perf.yaml", "    label: 설계점 사이클 해석", "    label: 설계점 사이클 해석\n    renamed_from: perf-cycle-old")
    rc, out = run_cli(["build", d, "--out", tmp_path / "o2"])
    assert rc == 0, out
    assert "key 개명 perf-cycle-old → perf-cycle: IRI STEP-000003 유지" in out and "G02" not in out and "G05" not in out
    rows = _ids_rows(d)
    assert ("step", "perf-cycle", "STEP-000002", "폐기") in rows and ("step", "perf-cycle", "STEP-000003", "활성") in rows
    g = Graph().parse(tmp_path / "o2" / "workflow.ttl", format="turtle")
    g.parse(tmp_path / "o2" / "workflow_derived.ttl", format="turtle")
    wf = "http://en-genius.local/onto/wf/"
    assert (EGID["STEP-000003"], URIRef(wf + "renamedFrom"), Literal("perf-cycle-old")) in g
    assert (EGID["STEP-000002"], OWL.deprecated, Literal(True)) in g
    assert run_cli(["build", d, "--out", tmp_path / "o3"])[0] == 0                         # 다시 빌드해도 그대로
    assert _ids_rows(d) == rows


def test_reusing_deprecated_key_revives_with_notice_g05(tmp_path):
    d = copy_example(tmp_path, "short")
    _rename(d, "perf-cycle", "perf-cycle-old")
    assert run_cli(["build", d, "--out", tmp_path / "o1"])[0] == 0
    _rename(d, "perf-cycle-old", "perf-cycle")
    rc, out = run_cli(["build", d, "--out", tmp_path / "o2"])
    assert rc == 0, out
    assert "[참고 G05]" in out and "폐기됐던 IRI STEP-000002 를 다시 쓴다" in out
    assert _ids(d)[("step", "perf-cycle")] == ("STEP-000002", "활성")
    assert _ids(d)[("step", "perf-cycle-old")] == ("STEP-000003", "폐기")


def test_renamed_from_after_build_warns_g06(tmp_path):
    """key 를 바꿔 build 한 뒤(G02) 에 renamed_from 을 적으면 잇지 못한다 — 조용히 무시하지 않고 G06 경고 (되살려 잇기는 Leo 결정)."""
    d = copy_example(tmp_path, "short")
    _rename(d, "perf-cycle", "perf-cycle-new")
    rc, out = run_cli(["check", d])
    assert rc == 0 and "새 key 'perf-cycle-new' 로 개명한 것이면 거기에 renamed_from: perf-cycle — build 하기 전에" in out
    assert run_cli(["build", d, "--out", tmp_path / "o1"])[0] == 0
    rows = _ids_rows(d)
    edit(d / "perf.yaml", "    label: 설계점 사이클 해석", "    label: 설계점 사이클 해석\n    renamed_from: perf-cycle")
    rc, out = run_cli(["build", d, "--out", tmp_path / "o2"])
    assert rc == 0, out
    assert "[경고 G06]" in out and "'perf-cycle-new' 는 이미 STEP-000003 를 받았다 (옛 key 는 STEP-000002, 이미 폐기)" in out
    assert _ids_rows(d) == rows


def test_real_registry_outside_real_folder_g01(tmp_path):
    """실데이터 레지스트리 폴더를 data/real 밖으로 복사해 빌드 — 방향에 맞는 안내 (예시 레지스트리 문구가 아니다)."""
    import shutil

    real = tmp_path / "data" / "real" / "workflows"
    real.mkdir(parents=True)
    d = copy_example(real, "short", state=False)
    assert run_cli(["build", d, "--out", tmp_path / "o1"])[0] == 0
    desk = tmp_path / "desk"
    shutil.copytree(d, desk)
    rc, out = run_cli(["build", desk, "--out", tmp_path / "o2"])
    assert rc == 1 and "[오류 G01]" in out
    assert r"실데이터 레지스트리가 든 폴더는 data\real\ 아래에서만 빌드한다" in out and "_registry 를 빼고 복사한다" in out
    assert "예시 레지스트리를 실데이터에 쓰지 않는다" not in out


def test_registry_written_only_after_outputs(tmp_path, monkeypatch):
    """산출 중간에 실패하면 YAML 폴더의 레지스트리는 쓰지 않는다 (docs/03 4-1 #9)."""
    import engenius_wf.pipeline as pl
    from engenius_wf.report import Report

    d = copy_example(tmp_path, "short", state=False)

    def boom(*a, **k):
        raise RuntimeError("산출 실패 흉내")
    monkeypatch.setattr(pl, "write_html", boom)
    with pytest.raises(RuntimeError):
        pl.run(d, tmp_path / "out", [], Report())
    assert not (d / "_registry").exists()
