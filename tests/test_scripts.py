"""scripts\\*.bat 과 그 도우미 scripts/bat_helper.py — .bat 의 형식(ASCII·CRLF·env.bat·pause)과 도우미의 인자 고르기·기본 폴더·
selftest 요약(값 없음)을 고정한다. .bat 자체를 cmd 로 돌리는 확인은 Windows 에서 손으로 한다 (docs/03 검증 기록) — query.bat 만은
읽기 전용이라 Windows 에서 cmd.exe 로 실제로 돌린다 (임시 build 출력을 끌어다 놓은 꼴, 저장소 output\\ 은 읽지 않는다)."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from engenius_wf import config
from engenius_wf.config import REPO_ROOT
from wfhelp import copy_example, run_cli

SCRIPTS = REPO_ROOT / "scripts"
BATS = sorted(SCRIPTS.glob("*.bat"))
EXPECTED = {"env", "build", "check", "validate", "release", "link_tools", "schema", "doctor", "selftest", "setup_offline", "query"}


def _helper():
    spec = importlib.util.spec_from_file_location("bat_helper", SCRIPTS / "bat_helper.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _helper()


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """출력·실데이터 폴더를 임시 폴더로 — 저장소 output/·data/real 을 건드리지 않는다. 브라우저는 열지 않는다."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "REAL_WORKFLOWS_DIR", tmp_path / "real_workflows")
    monkeypatch.setenv("WF_NO_OPEN", "1")
    monkeypatch.delenv("WF_CALLER_DIR", raising=False)
    return tmp_path


def test_bat_set_is_complete():
    assert {p.stem for p in BATS} == EXPECTED


@pytest.mark.parametrize("bat", BATS, ids=[p.name for p in BATS])
def test_bat_format(bat):
    """한국어 Windows 의 cmd 는 .bat 을 cp949 로 읽는다 → 영어 ASCII 만. 줄 끝은 CRLF (LF 만이면 goto·label 이 어긋날 수 있다)."""
    raw = bat.read_bytes()
    assert all(c < 128 for c in raw), f"{bat.name}: ASCII 밖 글자"
    assert b"\n" not in raw.replace(b"\r\n", b""), f"{bat.name}: CRLF 아닌 줄 끝"
    text = raw.decode("ascii")
    assert text.startswith("@echo off\r\n")
    if bat.stem == "env":
        assert "set PYTHONUTF8=1" in text and 'set "PYTHONPATH=%~dp0..\\src"' in text
        assert not re.search(r"(?im)^\s*pause\b", text)  # 다른 .bat 이 부르는 파일 — 멈추면 안 된다
    else:
        assert 'call "%~dp0env.bat"' in text and 'cd /d "%~dp0.."' in text
        assert re.search(r"pause\r\nexit /b", text), f"{bat.name}: 끝에 pause"


def test_bat_helper_commands_exist():
    """.bat 이 부르는 도우미 명령은 모두 bat_helper.COMMANDS 에 있다."""
    used = set()
    for bat in BATS:
        used |= set(re.findall(r"bat_helper\.py (\S+)", bat.read_text(encoding="ascii")))
    assert used and used <= set(H.COMMANDS), used - set(H.COMMANDS)


def test_default_folder_example_then_real(sandbox, capsys):
    src, cats, defaulted = H.pick([], "build")
    assert (src, cats, defaulted) == (H.example_default(), [], True)
    (sandbox / "real_workflows").mkdir()
    src, _, _ = H.pick([], "build")
    assert src == sandbox / "real_workflows"
    assert "사내 실데이터 폴더" in capsys.readouterr().out


def test_pick_drag_and_drop(sandbox, tmp_path):
    d = copy_example(tmp_path, "short", name="연습 폴더 (2)")
    cat = config.EXAMPLES_DIR / "catalog" / "tools_synthetic.ttl"
    src, cats, defaulted = H.pick([str(d / "cmp.yaml"), str(cat)], "check")      # YAML 파일 → 그 폴더, .ttl → 카탈로그
    assert (src, cats, defaulted) == (d, [cat], False)
    src, _, _ = H.pick([str(d) + '"'], "check")                                 # cmd 의 '"C:\x\"' 함정 → 끝 따옴표
    assert src == d
    with pytest.raises(H.Stop, match="YAML 폴더가 둘"):
        H.pick([str(d), str(config.EXAMPLES_DIR / "textbook")], "check")
    with pytest.raises(H.Stop, match="찾을 수 없다"):
        H.pick([str(tmp_path / "없는 폴더")], "check")


def test_folder_hints(sandbox, tmp_path, capsys):
    root = tmp_path / "wrap"
    copy_example(root, "short")
    (root / "x.yml").write_text("steps: []\n", encoding="utf-8")
    H.pick([str(root)], "build")
    out = capsys.readouterr().out
    assert "'.yml' 파일은 읽지 않는다" in out and "하위 폴더 short 에 있다" in out


def test_build_check_validate_flow(sandbox, tmp_path, capsys):
    """끌어다 놓기 흐름: build(출력 폴더는 output/<시각>_<폴더>) → validate(가장 최근 출력의 계약) — 예시 사본으로."""
    d = copy_example(tmp_path, "short")
    assert H.main(["check", str(d)]) == 0
    assert H.main(["build", str(d)]) == 0
    outs = list((sandbox / "output").glob("*_short"))
    assert len(outs) == 1 and (outs[0] / "workflow.html").is_file()
    assert "흐름 그림:" in capsys.readouterr().out
    assert H.latest_out() == outs[0]
    sample = outs[0] / "contracts" / "if-cmp-map" / "0.1.0.example.json"
    assert H.main(["validate", str(sample)]) == 0
    assert "[참고 J00]" in capsys.readouterr().out
    assert H.main(["validate"]) == 2                                            # 검사할 JSON 없음
    assert "[NG] 검사할 데이터 JSON 이 없다" in capsys.readouterr().out


def test_build_error_rc1_no_output(sandbox, tmp_path, capsys):
    d = copy_example(tmp_path, "short", state=False)
    (d / "perf.yaml").write_text((d / "perf.yaml").read_text(encoding="utf-8").replace("Tt4:  K ", "Tt4:  k "), encoding="utf-8")
    assert H.main(["build", str(d)]) == 1
    out = capsys.readouterr().out
    assert "[오류 U02]" in out and "결과 파일을 만들지 않았다" in out
    assert not list((sandbox / "output").glob("*/contracts"))


def test_link_tools_defaults(sandbox, tmp_path, capsys):
    """예시 폴더 + 카탈로그 없음 → 합성 카탈로그. 예시가 아닌 폴더 + 카탈로그 없음 → 멈춤(rc 2)."""
    d = copy_example(tmp_path, "short")
    assert H.main(["link-tools", str(d)]) == 2
    assert "survey.ttl 이 필요하다" in capsys.readouterr().out
    assert H.main(["link-tools"]) == 0                 # 기본 = 저장소 예시 textbook (읽기만 — link-tools 는 레지스트리를 쓰지 않는다)
    csvs = list((sandbox / "output").glob("*_textbook_tool_candidates.csv"))
    assert len(csvs) == 1
    head = csvs[0].read_text(encoding="utf-8-sig").splitlines()[0]
    assert head == "툴 key,적은 이름,지금 tool_id,후보 TOOL ID,후보 이름,근거"


def test_query_double_click_and_drag(sandbox, tmp_path, capsys):
    """query.bat 흉내 — 더블클릭(인자 없음) = 가장 최근 '오류 없이 끝난' build 출력, 끌어다 놓기 = 출력 폴더·그 안의 TTL·카탈로그·질의 이름."""
    assert H.main(["query"]) == 2                                               # build 출력이 아직 없다
    assert "[NG] build 출력이 없다" in capsys.readouterr().out
    d = copy_example(tmp_path, "short")
    assert H.main(["build", str(d)]) == 0
    good = next((sandbox / "output").glob("*_short"))
    bad = copy_example(tmp_path, "short", name="고장", state=False)
    (bad / "perf.yaml").write_text((bad / "perf.yaml").read_text(encoding="utf-8").replace("Tt4:  K ", "Tt4:  k "), encoding="utf-8")
    assert H.main(["build", str(bad)]) == 1                                     # 실패한 build 는 report.txt 만 — 더블클릭이 고르지 않는다
    capsys.readouterr()
    assert H.main(["query"]) == 0
    out = capsys.readouterr().out
    assert f"[query] 출력 = {H.rel(good)} (가장 최근 build 출력" in out
    assert all(f"== q0{i} " in out for i in range(1, 9)) and "-+-" in out
    assert "참고: q07·q08 는 Tool 온톨로지 교차 질의" in out
    cat = config.EXAMPLES_DIR / "catalog" / "tools_synthetic.ttl"
    assert H.main(["query", str(good / "workflow.ttl"), str(cat), "Q07"]) == 0   # 출력 폴더 안의 TTL · 카탈로그 · 질의 하나
    out = capsys.readouterr().out
    assert "== q07 " in out and "== q01 " not in out and "[query] 카탈로그 = " in out and "참고:" not in out
    failed = next(p for p in (sandbox / "output").iterdir() if p.name.endswith("_고장"))
    assert H.main(["query", str(failed)]) == 2
    assert "build 출력 폴더(output\\<실행>)가 아니다" in capsys.readouterr().out
    assert H.main(["query", str(good), str(d)]) == 2                            # YAML 폴더는 build 출력이 아니다
    assert H.main(["query", str(good), "q99"]) == 2                             # 모르는 질의 (cli 가 rc 2)


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe 로 .bat 을 실제로 돌리는 확인 — Windows 에서만")
def test_query_bat_runs_in_cmd(tmp_path):
    """query.bat 을 탐색기 끌어다 놓기와 같은 명령줄로 실제 실행 — env.bat 이 UTF-8 모드를 켜는지까지 (부모 환경의 PYTHONUTF8·PYTHONPATH 를 뺀다).
    출력 폴더는 임시 build — 저장소 output\\ 과 data\\real 은 읽지 않는다. pause 는 stdin 엔터로 넘긴다."""
    d = copy_example(tmp_path, "short")
    out = tmp_path / "out short"                                                # 공백 든 경로 — 탐색기는 따옴표로 감싸 넘긴다
    rc, text = run_cli(["build", d, "--out", out])
    assert rc == 0, text
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING", "PYTHONPATH")}
    r = subprocess.run(f'cmd.exe /d /c ""{SCRIPTS / "query.bat"}" "{out}""', input=b"\r\n", capture_output=True, env=env,
                       cwd=tmp_path, timeout=300)
    stdout = r.stdout.decode("utf-8", errors="replace")
    assert r.returncode == 0, stdout + r.stderr.decode("utf-8", errors="replace")
    assert "== q02 " in stdout and "perf-cycle" in stdout and "-+-" in stdout
    assert "[query] RESULT: OK  (rc=0)" in stdout
    r = subprocess.run(f'cmd.exe /d /c ""{SCRIPTS / "query.bat"}" "{d}""', input=b"\r\n", capture_output=True, env=env,
                       cwd=tmp_path, timeout=300)
    assert r.returncode == 2 and "[query] RESULT: STOPPED  (rc=2)" in r.stdout.decode("utf-8", errors="replace")


def test_release_defaults_and_prompts(sandbox, tmp_path, monkeypatch, capsys):
    assert H.main(["release"]) == 2                                             # data/real/workflows 없음 → 예시를 바꾸지 않는다
    assert "끌어다 놓는다" in capsys.readouterr().out
    d = copy_example(tmp_path, "short")
    answers = iter(["if-cmp-map", "개념설계 1차 검토 확정"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert H.main(["release", str(d)]) == 0
    out = capsys.readouterr().out
    assert "if-cmp-map  0.1.0" in out and "[참고 V07]" in out
    assert (d / "_released" / "if-cmp-map" / "0.1.0.json").is_file()
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert H.main(["release", str(d), "if-cycle-dp"]) == 2                      # 사유 없음 → 아무것도 바꾸지 않는다
    assert not (d / "_released" / "if-cycle-dp").exists()


def test_release_reasks_when_reason_has_person_name(sandbox, tmp_path, monkeypatch, capsys):
    """사유에 인명 유사 표기 → 값을 되비추지 않고 다시 묻는다 (W1 검토 수리, 절대 규칙 5)."""
    d = copy_example(tmp_path, "short", state=False)
    answers = iter(["홍길동 책임 확인", "개념설계 1차 검토 통과 (예시)"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert H.main(["release", str(d), "if-cycle-dp"]) == 0
    out = capsys.readouterr().out
    assert "사유에 인명으로 보이는 표기가 있다" in out and "홍길동" not in out
    rel = json.loads((d / "_released" / "if-cycle-dp" / "0.1.0.json").read_text(encoding="utf-8"))
    assert rel["reason"] == "개념설계 1차 검토 통과 (예시)"


def test_installed_commit(tmp_path):
    assert H.installed_commit(tmp_path) == "unknown"                            # 표식도 .git 도 없음
    (tmp_path / "offline").mkdir()
    full = "0123456789abcdef0123456789abcdef01234567"
    (tmp_path / "offline" / "installed_commit.txt").write_bytes(b"\xef\xbb\xbf" + f"{full}\r\n12\r\n".encode("utf-8"))  # 메모장 BOM + CRLF
    assert H.installed_commit(tmp_path) == "0123456"


def test_selftest_summary_has_no_values():
    log = "\n".join([
        "[OK] Python 3.10.2 (3.10 이상 필요)", "[--] Java: 없음 (SHACL·Fuseki 에만 필요)", "[NG] linkml 없음", "그 밖의 줄 값=비밀",
        "....F...s [100%]", "=========================== short test summary info ===========================",
        "FAILED tests/test_x.py::test_y[이름 있는 경우] - AssertionError: 비밀 값 1234",
        "ERROR tests/test_z.py::test_w - FileNotFoundError: C:\\사내\\경로",
        "1 failed, 130 passed, 3 skipped, 1 error in 21.5s",
        "Exit: Python UTF-8 모드가 꺼져 있다 - `set PYTHONUTF8=1` !!!",
    ])
    text = H.summarize(log, "abc1234", 1, 1, when="2026-10-19 09:00")
    assert text.splitlines() == [
        "selftest FAIL  commit abc1234  2026-10-19 09:00  doctor rc=1  pytest rc=1",
        "[OK] Python 3.10.2 (3.10 이상 필요)", "[--] Java: 없음 (SHACL·Fuseki 에만 필요)", "[NG] linkml 없음",
        "1 failed, 130 passed, 3 skipped, 1 error in 21.5s",
        "Exit: Python UTF-8 모드가 꺼져 있다 - `set PYTHONUTF8=1`",
        "FAILED tests/test_x.py::test_y[이름 있는 경우]", "ERROR tests/test_z.py::test_w",
    ]
    assert "비밀" not in text and "사내" not in text
    assert H.summarize("135 passed in 22.4s", "unknown", 0, 0, when="t").startswith("selftest PASS")
