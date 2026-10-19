"""계약 판 관리 W1 검토 수리 — 품은 계약 스냅샷·개명 승계·동결 현재 판 스키마·기본값 명시·V04·손상 동결본·사유 인명·다음 판 안내.

예시(short·textbook)를 임시 폴더에 복사해 한 곳만 고친다. 데이터는 공개 교과서 수준 예시.
"""

from __future__ import annotations

import json

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from engenius_wf.versioning import BUMP, next_version, required_bump
from wfhelp import copy_example, edit, run_cli

WF = "http://en-genius.local/onto/wf/"
BPR = "      BPR:  1    | 바이패스비 | 선택\n"
AMB = ("      amb:  struct:if-amb | 대기 조건\n\n"
       "  - key: if-amb\n    label: 대기 조건\n    version: 0.1.0\n    items:\n      alt: m | 고도\n")
CYCLE_VER = "    label: 설계점 사이클 결과\n    version: {}"


def _json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _with_amb(tmp_path, state=False):
    """short 사본 + 계약 if-amb 를 if-cycle-dp 가 struct 로 품는다."""
    d = copy_example(tmp_path, "short", state=state)
    edit(d / "perf.yaml", BPR, BPR + AMB)
    return d


def test_struct_ref_contract_is_snapshotted(tmp_path):
    """품은 계약이 바뀌어도 동결 판 스키마는 그대로이고, 바뀐 내용은 품는 쪽의 올림 요구(V02·V03)로 전해진다 (지적 22)."""
    d = _with_amb(tmp_path)
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    frozen = _json(d / "_released" / "if-cycle-dp" / "0.1.0.json")
    assert [x["name"] for x in frozen["def"]["refs"]["if-amb"]["items"]] == ["alt"]

    edit(d / "perf.yaml", "      alt: m | 고도\n", "      alt: m | 고도\n      Tamb: K | 대기 온도\n")    # 품은 계약만 바꿈
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V02]" in out and "if-cycle-dp→if-amb.Tamb 추가(필수)" in out
    assert "→ version: 1.0.0 로 올린다 (MAJOR = 첫 자리 +1" in out
    edit(d / "perf.yaml", CYCLE_VER.format("0.1.0"), CYCLE_VER.format("0.2.0"))
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V03]" in out and "→ version: 1.0.0 로 올린다" in out
    edit(d / "perf.yaml", CYCLE_VER.format("0.2.0"), CYCLE_VER.format("1.0.0"))
    out_dir = tmp_path / "out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    s0 = _json(out_dir / "contracts" / "if-cycle-dp" / "0.1.0.schema.json")
    s1 = _json(out_dir / "contracts" / "if-cycle-dp" / "1.0.0.schema.json")
    assert s0["$defs"]["if-amb"]["required"] == ["alt"] and s0["$defs"]["if-amb"]["x-interface"] == {"key": "if-amb", "version": "0.1.0"}
    assert s1["$defs"]["if-amb"]["required"] == ["alt", "Tamb"]
    old = tmp_path / "old.json"                            # 동결 당시 모양의 데이터는 그 판으로 계속 통과
    old.write_text(json.dumps({"contract": "if-cycle-dp", "version": "0.1.0",
                               "data": {"W2": 100.0, "PR_c": 30.0, "Tt4": 1600.0, "amb": {"alt": 0.0}}}), encoding="utf-8")
    rc, out = run_cli(["validate", out_dir, old])
    assert rc == 0, out


def test_struct_ref_records_are_scoped(tmp_path):
    """품은 계약에 같은 이름의 묶음이 있어도 섞이지 않는다 — $defs '계약key.묶음' (docs/03 4-1 #3, 스냅샷 수리와 같은 곳)."""
    d = copy_example(tmp_path, "textbook", state=False)
    st = "      stations: struct:Station[] | 스테이션 표\n"
    edit(d / "perf.yaml", st, st + "      amb: struct:if-amb | 대기 조건\n\n"
         "  - key: if-amb\n    label: 대기 조건\n    version: 0.1.0\n    records:\n      - name: Station\n        label: 대기 점\n"
         "        items:\n          z: m | 높이\n    items:\n      pts: struct:Station[] | 점 목록\n")
    out_dir = tmp_path / "out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    s = _json(out_dir / "contracts" / "if-cycle-dp" / "0.1.0.schema.json")
    assert list(s["$defs"]["Station"]["properties"]) == ["station", "W", "Pt", "Tt"]
    assert list(s["$defs"]["if-amb.Station"]["properties"]) == ["z"]
    assert s["$defs"]["if-amb"]["properties"]["pts"]["items"] == {"$ref": "#/$defs/if-amb.Station"}
    rc, out = run_cli(["validate", out_dir, out_dir / "contracts" / "if-cycle-dp" / "0.1.0.example.json"])
    assert rc == 0, out


def _rename(d, old, new):
    for f in d.glob("*.yaml"):
        f.write_text(f.read_text(encoding="utf-8").replace(old, new), encoding="utf-8", newline="\n")


def test_renaming_struct_ref_contract_does_not_crash_build(tmp_path):
    """동결본이 품은 계약을 개명(renamed_from)해도 build 가 죽지 않는다 — 동결 판은 스냅샷으로 만든다 (지적 23)."""
    d = _with_amb(tmp_path)
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    _rename(d, "if-amb", "if-ambient")
    edit(d / "perf.yaml", "    label: 대기 조건\n", "    label: 대기 조건\n    renamed_from: if-amb\n")
    edit(d / "perf.yaml", CYCLE_VER.format("0.1.0"), CYCLE_VER.format("1.0.0"))
    out_dir = tmp_path / "out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    s0 = _json(out_dir / "contracts" / "if-cycle-dp" / "0.1.0.schema.json")
    assert s0["$defs"]["if-amb"]["required"] == ["alt"]


def test_legacy_frozen_def_without_snapshot_is_v10(tmp_path):
    """스냅샷 없는 옛 동결본이 품은 계약이 사라지면 traceback 대신 V10 오류 (파일을 가리킨다)."""
    d = _with_amb(tmp_path)
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    p = d / "_released" / "if-cycle-dp" / "0.1.0.json"
    data = _json(p)
    del data["def"]["refs"]
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    _rename(d, "if-amb", "if-ambient")
    edit(d / "perf.yaml", CYCLE_VER.format("0.1.0"), CYCLE_VER.format("1.0.0"))
    rc, out = run_cli(["build", d, "--out", tmp_path / "out"])
    assert rc == 1 and "[오류 V10]" in out and "품은 계약 'if-amb' 를 찾을 수 없다" in out and "Traceback" not in out
    assert not (d / "_registry").exists()                  # 오류면 레지스트리도 쓰지 않는다


def test_renamed_frozen_contract_keeps_release_history(tmp_path):
    """동결된 계약을 renamed_from 으로 개명해도 동결 이력·V02 보호·RDF 동결 기록이 이어진다 (지적 24)."""
    d = copy_example(tmp_path, "short")
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    _rename(d, "if-cycle-dp", "if-cycle-design")
    edit(d / "perf.yaml", "    label: 설계점 사이클 결과\n", "    label: 설계점 사이클 결과\n    renamed_from: if-cycle-dp\n")
    tt3 = "      Tt4:  K    | 터빈 입구 전온도\n"
    edit(d / "perf.yaml", tt3, tt3 + "      Tt3:  K    | 압축기 출구 전온도\n")
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V02]" in out and "if-cycle-design 0.1.0: 동결된 판의 내용이 바뀌었다" in out
    edit(d / "perf.yaml", "      Tt3:  K    | 압축기 출구 전온도\n", "")
    out_dir = tmp_path / "out"
    rc, out = run_cli(["build", d, "--out", out_dir])
    assert rc == 0, out
    assert "key 개명 if-cycle-dp → if-cycle-design: IRI IFC-000002 유지" in out
    assert (d / "_released" / "if-cycle-design" / "0.1.0.json").is_file() and not (d / "_released" / "if-cycle-dp").exists()
    assert _json(out_dir / "contracts" / "if-cycle-design" / "0.1.0.schema.json")["properties"]["contract"] == {"const": "if-cycle-design"}
    g = Graph().parse(out_dir / "workflow_derived.ttl", format="turtle")
    rels = list(g.subjects(RDF.type, URIRef(WF + "InterfaceRelease")))
    assert len(rels) == 1
    edit(d / "perf.yaml", tt3, tt3 + "      Tt3:  K    | 압축기 출구 전온도\n")    # 옮긴 뒤에도 보호
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V02]" in out


def test_explicit_list_false_is_not_a_change(tmp_path):
    """list: false 를 적었다 지워도(또는 그 반대) 내용 변화가 아니다 (지적 26)."""
    d = copy_example(tmp_path, "short", state=False)
    long = '      BPR:  {unit: "1", label: 바이패스비, required: false, list: false}\n'
    edit(d / "perf.yaml", BPR, long)
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    edit(d / "perf.yaml", long, BPR)
    rc, out = run_cli(["check", d])
    assert rc == 0 and "V02" not in out
    a = {"name": "a", "type": "number", "unit": "K", "required": True}
    d0 = {"key": "if-x", "label": "x", "version": "0.1.0", "items": [a], "records": []}
    assert required_bump(d0 | {"items": [a | {"list": False}]}, d0)[0] == -1
    assert required_bump(d0, d0 | {"items": [a | {"list": False}]})[0] == -1


def test_confirmed_without_release_of_this_version_warns(tmp_path):
    """옛 판만 동결돼 있고 지금 판은 '확정' 인데 동결본이 없으면 V04 (지적 27)."""
    d = copy_example(tmp_path, "textbook")
    edit(d / "perf.yaml", "    version: 1.0.0\n    status: 확정", "    version: 1.1.0\n    status: 확정")
    mach = "      Mach:  1  | 설계점 비행 마하수\n"
    edit(d / "perf.yaml", mach, mach + "      dISA:  dK | 표준 대기 온도 차 | 선택\n")
    rc, out = run_cli(["check", d])
    assert rc == 0
    assert "[경고 V04] perf.yaml 23행  if-engine-reqs 1.1.0: 상태 '확정' 인데 동결본이 없다 (동결된 판: 1.0.0)" in out
    assert "[참고 V05]" in out


MP_LABEL = "        label: 맵 한 점\n"
MP_ORDER = "          W_corr: kg/s | 수정 유량\n          PR:     1    | 압력비\n"


def test_check_and_release_agree_on_record_label_and_order(tmp_path):
    """묶음 이름 변경 = PATCH (check·release 둘 다 V02), 항목 순서만 바꿈 = 변화 아님 (둘 다 조용) (지적 28)."""
    d = copy_example(tmp_path, "textbook", state=False)
    assert run_cli(["release", d, "if-cmp-map", "--reason", "예시 동결"])[0] == 0
    edit(d / "cmp.yaml", MP_LABEL, "        label: 맵 점\n")
    rc, out = run_cli(["check", d])
    assert rc == 1 and "[오류 V02]" in out and "MapPoint 묶음 이름 변경" in out and "필요: PATCH" in out
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "다시"])
    assert rc == 1 and "[오류 V02]" in out                                               # release 도 같은 판정 (먼저 검사에서 멈춤)
    edit(d / "cmp.yaml", "        label: 맵 점\n", MP_LABEL)
    edit(d / "cmp.yaml", MP_ORDER, "          PR:     1    | 압력비\n          W_corr: kg/s | 수정 유량\n")
    rc, out = run_cli(["check", d])
    assert rc == 0 and "V02" not in out
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "다시"])
    assert rc == 0 and "이미 동결됨" in out
    out_dir = tmp_path / "out"
    assert run_cli(["build", d, "--out", out_dir])[0] == 0
    s = _json(out_dir / "contracts" / "if-cmp-map" / "0.1.0.schema.json")
    assert list(s["$defs"]["MapPoint"]["properties"]) == ["W_corr", "PR", "eta"]          # 동결 판 = 동결본 그대로


def test_frozen_current_version_schema_comes_from_release(tmp_path):
    """levels 로 V02 를 낮춰도 동결된 현재 판의 스키마는 동결본으로 만든다 (YAML 의 바뀐 내용이 동결 판 이름으로 나가지 않는다)."""
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report

    d = copy_example(tmp_path, "short", state=False)
    assert run_cli(["release", d, "if-cycle-dp", "--reason", "예시 동결"])[0] == 0
    tt3 = "      Tt4:  K    | 터빈 입구 전온도\n"
    edit(d / "perf.yaml", tt3, tt3 + "      Tt3:  K    | 압축기 출구 전온도\n")
    ov = tmp_path / "ov"
    ov.mkdir()
    (ov / "rules.yaml").write_text("levels: {V02: 경고}\n", encoding="utf-8")
    rep = Report()
    ctx = run(d, tmp_path / "out", [], rep, overlay_dir=ov)
    assert ctx is not None and any(m.code == "V02" and m.level == "경고" for m in rep.items)
    s = _json(tmp_path / "out" / "contracts" / "if-cycle-dp" / "0.1.0.schema.json")
    assert s["$defs"]["_data"]["required"] == ["W2", "PR_c", "Tt4"]


def test_corrupt_or_odd_release_files(tmp_path):
    """빈·손상 동결본은 V08 오류로 파일을 가리킨다 (traceback 없음), 판 이름이 아닌 파일은 V09 경고로 건너뛴다 (지적 37·docs/03 4-1 #8)."""
    d = copy_example(tmp_path, "short", state=False)
    rel = d / "_released" / "if-cmp-map"
    rel.mkdir(parents=True)
    (rel / "0.1.0.json").write_bytes(b"")
    for cmd in (["check", d], ["build", d, "--out", tmp_path / "o"], ["release", d, "if-cmp-map", "--reason", "예시"]):
        rc, out = run_cli(cmd)
        assert rc == 1 and "[오류 V08] _released/if-cmp-map/0.1.0.json" in out and "Traceback" not in out, out
    (rel / "0.1.0.json").unlink()
    (rel / "0.1.0 - 복사본.json").write_text("{}", encoding="utf-8")
    rc, out = run_cli(["check", d])
    assert rc == 0 and "[경고 V09] _released/if-cmp-map/0.1.0 - 복사본.json" in out


def test_release_write_is_atomic(tmp_path, monkeypatch):
    """동결본 쓰기 도중 실패해도 빈 동결본이 남지 않는다 (임시 파일 + 바꿔 끼우기)."""
    import engenius_wf.versioning as V

    d = copy_example(tmp_path, "short", state=False)

    def fail(a, b):
        raise OSError("쓰기 실패 흉내")
    monkeypatch.setattr(V.os, "replace", fail)
    with pytest.raises(OSError):
        run_cli(["release", d, "if-cmp-map", "--reason", "예시"])
    assert list((d / "_released" / "if-cmp-map").iterdir()) == []


def test_release_reason_with_person_name_is_refused(tmp_path):
    """동결 사유도 인명 검사 — 맞으면 V06 으로 거절하고 값은 옮기지 않는다 (지적 12·38, 절대 규칙 5)."""
    d = copy_example(tmp_path, "short", state=False)
    rc, out = run_cli(["release", d, "if-cmp-map", "--reason", "홍길동 책임 확인"])
    assert rc == 1 and "[오류 V06]" in out and "인명으로 보이는 표기" in out and "홍길동" not in out
    assert not (d / "_released").exists()


@pytest.mark.parametrize("base, level, want", [("0.1.0", 2, "1.0.0"), ("0.1.0", 1, "0.2.0"), ("0.1.0", 0, "0.1.1"), ("1.2.3", 2, "2.0.0")])
def test_next_version(base, level, want):
    assert next_version(base, level) == want
    assert BUMP["MAJOR"] == 2
