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


# --------------------------------------------------------------------------- W1 검토 수리 (validate 가장자리·항목 칸 검사)
@pytest.mark.parametrize("name, text, frag", [
    ("nan", '{"contract": "if-cycle-dp", "version": "0.1.0", "data": {"OPR": 30.0, "Tt4": NaN, "stations": []}}', "NaN 는 JSON 값이 아니다"),
    ("inf", '{"contract": "if-cycle-dp", "version": "0.1.0", "data": {"OPR": 30.0, "Tt4": Infinity, "stations": []}}', "Infinity 는 JSON 값이 아니다"),
    ("dup", '{"contract": "if-cycle-dp", "version": "0.1.0", "data": {"OPR": "bad", "OPR": 30.0, "Tt4": 1650.0, "stations": []}}',
     "같은 칸 'OPR' 가 두 번"),
    ("dup_nested", '{"contract": "if-cycle-dp", "version": "0.1.0", "data": {"OPR": 30.0, "Tt4": 1650.0, '
                   '"stations": [{"station": "2", "W": 1.0, "Pt": 1.0, "Tt": 1.0, "Tt": 2.0}]}}', "같은 칸 'Tt' 가 두 번"),
    ("list", '[1, 2]', "맨 위가 { … } 객체가 아니다"),
])
def test_validate_rejects_non_json_values_and_duplicates(built, tmp_path, name, text, frag):
    """NaN(범위 검사를 지나침)·Infinity·같은 칸 두 번(뒤 값이 이김)·맨 위가 객체 아님 → J01 (지적 25, docs/03 4-1 #6)."""
    p = tmp_path / f"{name}.json"
    p.write_text(text, encoding="utf-8")
    rc, out = run_cli(["validate", built["textbook_nocat"].out, p])
    assert rc == 1 and f"[오류 J01] {name}.json" in out and frag in out and "Traceback" not in out, out


def test_validate_contract_case_and_missing_contracts_dir(built, tmp_path):
    """봉투 contract 가 폴더 이름과 대소문자만 달라도 OS 와 무관하게 J02 + 혹시 안내 (영어 원문 J03 없음) (지적 31)."""
    p = tmp_path / "upper.json"
    p.write_text(json.dumps(GOOD | {"contract": "IF-CYCLE-DP"}), encoding="utf-8")
    rc, out = run_cli(["validate", built["textbook_nocat"].out, p])
    assert rc == 1 and "[오류 J02] upper.json  계약 'IF-CYCLE-DP' 의 스키마가 없다" in out and "혹시 if-cycle-dp ?" in out
    assert "was expected" not in out
    rc, out = run_cli(["validate", tmp_path, p])                             # contracts/ 없는 폴더 (docs/03 4-1 #6)
    assert rc == 1 and "build 출력 폴더가 아니다" in out and "Traceback" not in out


ITEM_EDITS = [
    ("tag: {type: string, minimum: 1, maximum: 5}", "C10", "minimum·maximum 은 숫자 항목"),
    ('cnt: {type: number, unit: "1", values: [1, 2, 3]}', "C10", "values 는 enum 항목에만"),
    ("nm: {type: string, formats: [csv]}", "C10", "formats 는 file 항목에만"),
    ("PR_C: 1 | 압력비 (대문자 C)", "C11", "항목 'PR_C' 와 'PR_c' 는 대소문자만 다르다"),
]


@pytest.mark.parametrize("line, code, frag", ITEM_EDITS)
def test_item_fields_must_fit_type_and_case(tmp_path, line, code, frag):
    """형에 뜻이 없는 칸(C10)·대소문자만 다른 항목 이름(C11)은 오류 — 걸었다고 믿은 제약이 조용히 사라지지 않게 (지적 29·30)."""
    from wfhelp import copy_example, edit

    d = copy_example(tmp_path, "short", state=False)
    edit(d / "perf.yaml", "      BPR:  1    | 바이패스비 | 선택\n", "      BPR:  1    | 바이패스비 | 선택\n      " + line + "\n")
    rc, out = run_cli(["check", d])
    assert rc == 1 and f"[오류 {code}] perf.yaml 19행" in out and frag in out, out


def test_record_names_case_only_c11(tmp_path):
    from wfhelp import copy_example, edit

    d = copy_example(tmp_path, "textbook", state=False)
    edit(d / "cmp.yaml", "      - name: SpeedLine\n", "      - name: Mappoint\n        items:\n          x: 1 | 값\n      - name: SpeedLine\n")
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 C11]" in out and "묶음 'Mappoint' 와 'MapPoint' 는 대소문자만 다르다" in out
