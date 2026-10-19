"""V7 계약 판 관리 — release 동결 → 동결 판 내용 변경(V02) → 올림 부족(V03) → MAJOR 올림(V05)·옛 판 스키마 유지 · RDF 동결 기록,
그리고 판 올림 규칙표 (required_bump)."""

from __future__ import annotations

import datetime as dt

import pytest
from rdflib import Graph

from engenius_wf.versioning import BUMP, required_bump
from wfhelp import copy_example, edit, run_cli

ETA = "eta:    {unit: \"1\", label: 단열효율, minimum: 0, maximum: 1}"
MAP_VER = "label: 압축기 특성 맵\n    version: {}"


def test_release_flow(tmp_path):
    d = copy_example(tmp_path, "textbook", "ver", state=False)
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "개념설계 1차 검토 통과 (예시)"])
    assert rc == 0
    assert "[참고 V07] release  if-cmp-map 0.1.0 동결 → _released/if-cmp-map/0.1.0.json (사유: 개념설계 1차 검토 통과 (예시))" in out
    assert run_cli(["release", d, "if-engine-reqs", "--reason", "체계 요구 확정 (예시)"])[0] == 0
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "다시"])
    assert rc == 0 and "이미 동결됨" in out

    edit(d / "cmp.yaml", ETA, ETA.replace("maximum: 1}", "maximum: 0.95}"))          # 동결 판 그대로 범위를 좁힘
    rc, out = run_cli(["check", d])
    assert rc == 1
    assert ("[오류 V02] cmp.yaml 55행  if-cmp-map 0.1.0: 동결된 판의 내용이 바뀌었다 — 판을 올려라 "
            "(필요: MAJOR; if-cmp-map.MapPoint.eta maximum 1.0 → 0.95)") in out

    edit(d / "cmp.yaml", MAP_VER.format("0.1.0"), MAP_VER.format("0.2.0"))           # MINOR 만 올림
    rc, out = run_cli(["check", d])
    assert rc == 1
    assert "[오류 V03] cmp.yaml 55행  if-cmp-map: 0.1.0 → 0.2.0 인데 바뀐 내용은 MAJOR 올림이 필요 (if-cmp-map.MapPoint.eta maximum 1.0 → 0.95)" in out

    edit(d / "cmp.yaml", MAP_VER.format("0.2.0"), MAP_VER.format("1.0.0"))           # MAJOR 로 올림
    out_dir = tmp_path / "ver_out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    assert "[참고 V05] cmp.yaml 55행  if-cmp-map: 0.1.0 → 1.0.0 (if-cmp-map.MapPoint.eta maximum 1.0 → 0.95)" in out
    assert sorted(p.name for p in (out_dir / "contracts" / "if-cmp-map").glob("*.schema.json")) == ["0.1.0.schema.json", "1.0.0.schema.json"]
    assert not (out_dir / "contracts" / "if-cmp-map" / "0.1.0.example.json").exists()       # 골격 예시는 현재 판만

    g = Graph().parse(out_dir / "workflow_derived.ttl", format="turtle")
    rows = sorted(tuple(map(str, r)) for r in g.query(
        "PREFIX wf: <http://en-genius.local/onto/wf/> PREFIX owl: <http://www.w3.org/2002/07/owl#> "
        "SELECT ?v ?at ?why WHERE { ?r a wf:InterfaceRelease ; owl:versionInfo ?v ; wf:releasedAt ?at ; wf:releaseReason ?why }"))
    today = dt.date.today().isoformat()
    assert rows == [("0.1.0", today, "개념설계 1차 검토 통과 (예시)"), ("1.0.0", today, "체계 요구 확정 (예시)")]


def test_release_input_errors(tmp_path):
    d = copy_example(tmp_path, "short", state=False)
    rc, out = run_cli(["release", d, "if-cmp-mpa", "--reason", "x"])
    assert rc == 1 and "[오류 V06] release  계약 'if-cmp-mpa' 없음" in out and "혹시 if-cmp-map" in out
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "  "])
    assert rc == 1 and "동결 사유(--reason)가 필요하다" in out


def test_confirmed_without_release_warns(tmp_path):
    d = copy_example(tmp_path, "textbook", state=False)
    rc, out = run_cli(["check", d])
    assert rc == 0
    assert "[경고 V04] perf.yaml 23행  if-engine-reqs 1.0.0: 상태 '확정' 인데 동결본이 없다" in out


def test_version_regression(tmp_path):
    d = copy_example(tmp_path, "textbook")
    edit(d / "perf.yaml", "version: 1.0.0", "version: 0.9.0")
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V01] perf.yaml 22행  if-engine-reqs: 판 0.9.0 이 동결본 최신 1.0.0 보다 낮다" in out


# --------------------------------------------------------------------------- 판 올림 규칙표
def _d(items, records=(), label="계약"):
    return {"key": "if-x", "label": label, "version": "0.1.0", "items": list(items), "records": list(records)}


A = {"name": "a", "type": "number", "unit": "K", "required": True, "minimum": 0.0, "maximum": 10.0}
E = {"name": "e", "type": "enum", "values": ["p", "q"], "required": True}


@pytest.mark.parametrize("new, want", [
    (_d([A]), None),                                                              # 변화 없음
    (_d([]), "MAJOR"),                                                            # 항목 삭제
    (_d([A, {"name": "b", "type": "number", "unit": "K", "required": True}]), "MAJOR"),    # 필수 추가
    (_d([A, {"name": "b", "type": "number", "unit": "K", "required": False}]), "MINOR"),   # 선택 추가
    (_d([A | {"unit": "dK"}]), "MAJOR"),                                          # 단위 변경
    (_d([A | {"required": False}]), "MINOR"),                                     # 필수 → 선택
    (_d([A | {"maximum": 5.0}]), "MAJOR"),                                        # 범위 좁힘
    (_d([A | {"maximum": 20.0}]), "MINOR"),                                       # 범위 넓힘
    (_d([A | {"label": "새 이름"}]), "PATCH"),                                     # 이름만
    (_d([A], label="새 계약 이름"), "PATCH"),
    (_d([A], records=[{"name": "R", "label": None, "items": [A]}]), "MINOR"),     # 묶음 추가
])
def test_required_bump(new, want):
    level, why = required_bump(_d([A]), new)
    assert level == (BUMP[want] if want else -1), why


def test_required_bump_enum_values():
    assert required_bump(_d([E]), _d([E | {"values": ["p", "q", "r"]}]))[0] == BUMP["MINOR"]     # 선택지 추가
    assert required_bump(_d([E]), _d([E | {"values": ["p"]}]))[0] == BUMP["MAJOR"]               # 선택지 삭제
    assert required_bump(_d([A], records=[{"name": "R", "label": None, "items": [A]}]), _d([A]))[0] == BUMP["MAJOR"]   # 묶음 삭제
