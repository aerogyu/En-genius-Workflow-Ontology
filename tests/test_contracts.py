"""V6 계약 데이터 검사 (validate 명령) — 실제 데이터 JSON 이 계약을 지키는지, 한국어 메시지 (문구는 시안 실측 그대로)."""

from __future__ import annotations

import json

import pytest

from engenius_wf.contracts import ci_ext
from wfhelp import run_cli

GOOD = {"contract": "if-cycle-dp", "version": "0.1.0", "produced_by": "perf-cycle-dp", "case": "교과서 예제 DP", "iteration": 0,
        "data": {"OPR": 30.0, "Tt4": 1650.0, "stations": [{"station": "2", "W": 100.0, "Pt": 101.3, "Tt": 288.15}]}}
BAD = {"contract": "if-cycle-dp", "version": "0.1.0",
       "data": {"OPR": "30", "Tt4": 2500, "stations": [{"station": 2, "W": 100.0, "Pt": 101.3}], "BRP": 5}}
OLD = {"contract": "if-cycle-dp", "version": "0.0.9", "data": {}}
MAP = {"contract": "if-cmp-map", "version": "0.1.0", "data": {
    "speed_lines": [{"N_rel": 100, "points": [{"W_corr": 20, "PR": 12, "eta": 0.86}, {"W_corr": 19, "PR": 12.5, "eta": 0.85},
                                              {"W_corr": 18, "PR": 13, "eta": 1.2}]},
                    {"N_rel": 90, "points": [{"W_corr": 17, "PR": 10, "eta": 0.86}]}],
    "surge_margin": 18, "map_file": "HPC_MAP.CSV", "map_source": "추정"}}

EXPECTED = [
    "[오류 J03] bad.json  data: 계약에 없는 칸 'BRP'",
    "[오류 J03] bad.json  data/OPR: 형이 틀림 '30' (number 이어야)",
    "[오류 J03] bad.json  data/Tt4: 범위 밖 2500 (최대 2200.0)",
    "[오류 J03] bad.json  data/stations/0: 필수 칸 없음 — 'Tt'",
    "[오류 J03] bad.json  data/stations/0/station: 형이 틀림 '2' (string 이어야)",
    "[오류 J03] map_bad.json  data/map_source: 선택지 밖 '추정' — 허용: 1D 상관식, 3D CFD, 시험",
    "[오류 J03] map_bad.json  data/speed_lines/0/points/2/eta: 범위 밖 1.2 (최대 1.0)",
    "[오류 J03] map_bad.json  data/speed_lines/1/points: 개수 부족 1 (최소 3)",
    "[오류 J03] map_xlsx.json  data/map_file: 파일 확장자가 계약과 다르다 'hpc_map.xlsx'",
    "[오류 J02] oldver.json  계약 'if-cycle-dp' 판 '0.0.9' 스키마가 없다 — 있는 판: 0.1.0",
    "[참고 J00] good.json  통과 (if-cycle-dp 0.1.0)",
]


@pytest.fixture()
def payloads(tmp_path):
    xlsx = json.loads(json.dumps(MAP))
    xlsx["data"]["map_file"] = "hpc_map.xlsx"
    for n, x in (("good", GOOD), ("bad", BAD), ("oldver", OLD), ("map_bad", MAP), ("map_xlsx", xlsx)):
        (tmp_path / f"{n}.json").write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
    return [tmp_path / f"{n}.json" for n in ("good", "bad", "oldver", "map_bad", "map_xlsx")]


def test_validate_messages(built, payloads):
    rc, out = run_cli(["validate", built["textbook_nocat"].out, *payloads])
    assert rc == 1
    lines = out.splitlines()
    for want in EXPECTED:
        assert want in lines, want
    assert "HPC_MAP.CSV" not in out                     # 확장자 검사는 대소문자 무시
    assert "혹시 BPR ?" in out


def test_validate_good_only(built, payloads):
    rc, out = run_cli(["validate", built["textbook_nocat"].out, payloads[0]])
    assert rc == 0 and "통과 (if-cycle-dp 0.1.0)" in out


def test_skeletons_pass_own_schema(built):
    """골격 예시(.example.json) 7개가 자기 스키마를 통과한다."""
    ex = sorted((built["textbook_nocat"].out / "contracts").glob("*/*.example.json"))
    assert len(ex) == 7
    rc, out = run_cli(["validate", built["textbook_nocat"].out, *ex])
    assert rc == 0, out
    assert out.count("[참고 J00]") == 7


def test_validate_unknown_contract(built, tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"contract": "if-cycle-db", "version": "0.1.0", "data": {}}), encoding="utf-8")
    q = tmp_path / "broken.json"
    q.write_text("{not json", encoding="utf-8")
    rc, out = run_cli(["validate", built["textbook_nocat"].out, p, q])
    assert rc == 1
    assert "[오류 J02] x.json  계약 'if-cycle-db' 의 스키마가 없다" in out and "혹시 if-cycle-dp" in out
    assert "[오류 J01] broken.json  JSON 읽기 실패" in out


def test_ci_ext():
    assert ci_ext("csv") == "[cC][sS][vV]"
    assert ci_ext("cas.h5") == r"[cC][aA][sS]\.[hH]5"
