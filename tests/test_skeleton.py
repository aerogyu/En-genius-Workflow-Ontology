"""골격 — 명령행·설정(오버레이)·패키지 import 규칙."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from engenius_wf import __version__
from engenius_wf.cli import COMMANDS, main
from engenius_wf.config import (CONFIG_DIR, REPO_ROOT, ConfigError, default_overlay_dir, load_rules, load_units)
from engenius_wf.pipeline import resolve_overlay, run
from engenius_wf.report import Report
from wfhelp import copy_example, edit, run_cli


def _env(**kw):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src"), "PYTHONUTF8": "1"}   # 자식도 UTF-8 로 쓰게 — 부모가 cp949 콘솔이어도 decode 가 깨지지 않게
    env.update(kw)
    return env


def test_help_subprocess():
    """python -m engenius_wf --help 가 동작하고 명령이 모두 보인다 (W0 완료 기준)."""
    r = subprocess.run([sys.executable, "-m", "engenius_wf", "--help"], capture_output=True, text=True, encoding="utf-8",
                       cwd=REPO_ROOT, env=_env())
    assert r.returncode == 0, r.stderr
    for name in COMMANDS:
        assert name in r.stdout
    for name in ("build", "check", "release", "validate", "link-tools", "schema", "doctor", "query"):
        assert name in COMMANDS


def test_no_command_prints_help(capsys):
    assert main([]) == 0
    assert "build" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_doctor_runs():
    rc, out = run_cli(["doctor"])
    assert "[OK] Python" in out and "terms.json" in out
    assert rc == 0, out


def test_runtime_does_not_import_linkml():
    """빌드 런타임(cli·pipeline)은 linkml 을 import 하지 않는다 — 홈 폴더 없는 사내 환경에서 pystow 부작용 회피 (V11 의 가벼운 판)."""
    code = ("import sys, engenius_wf.cli, engenius_wf.pipeline, engenius_wf.query; "
            "print(sorted({m.split('.')[0] for m in sys.modules} & {'linkml', 'linkml_runtime', 'pystow', 'curies'}))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, env=_env())
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]"


# --------------------------------------------------------------------------- 설정 오버레이
def test_config_defaults():
    rules = load_rules()
    assert rules["transfer_aliases"]["수기"] == "메일·수기 전달"
    assert rules["manual_transfer_values"] == ["메일·수기 전달"]
    units, aliases = load_units()
    assert units["kg/s"]["qudt"] == "KiloGM-PER-SEC" and "1" in units
    assert aliases["퍼센트"] == "%"


def test_overlay_merges_by_key(tmp_path):
    (tmp_path / "rules.yaml").write_text("levels: {R05: 참고}\ntransfer_aliases: {이메일: 메일·수기 전달}\n", encoding="utf-8")
    (tmp_path / "units.yaml").write_text("units:\n  psi: {qudt: PSI, kind: 압력, label: psi}\n", encoding="utf-8")
    rules = load_rules(overlay_dir=tmp_path)
    assert rules["levels"] == {"R05": "참고"}
    assert rules["transfer_aliases"]["이메일"] == "메일·수기 전달" and rules["transfer_aliases"]["수기"] == "메일·수기 전달"
    assert rules["true_words"] == load_rules()["true_words"]
    units, aliases = load_units(overlay_dir=tmp_path)
    assert "psi" in units and "K" in units and aliases["퍼센트"] == "%"


@pytest.mark.parametrize("text, msg", [
    ("levels: [R05]\n", "매핑"),
    ("person_patterns: abc\n", "목록"),
    ("transfer_aliases:\n", "비어"),
    ("levels: {R05: 참고\n", "YAML 문법 오류"),
])
def test_overlay_shape_errors(tmp_path, text, msg):
    (tmp_path / "rules.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match=msg):
        load_rules(overlay_dir=tmp_path)


def test_overlay_applies_to_build(tmp_path):
    """오버레이의 전달 방법 별칭이 빌드에 반영된다 (사내에서 코드 수정 없이 조정)."""
    d = copy_example(tmp_path, "short", state=False)
    edit(d / "cmp.yaml", "transfer: 수기", "transfer: 이메일")
    rep = Report()
    assert run(d, None, [], rep, write=False) is None
    assert any(m.code == "S02" for m in rep.errors)
    ov = tmp_path / "overlay"
    ov.mkdir()
    (ov / "rules.yaml").write_text("transfer_aliases: {이메일: 메일·수기 전달}\n", encoding="utf-8")
    rep = Report()
    ctx = run(d, None, [], rep, write=False, overlay_dir=ov)
    assert ctx is not None and not rep.errors
    assert ctx["m"]["step"]["cmp-meanline"]["inputs"][0]["transfer"] == "메일·수기 전달"


def test_overlay_auto_only_for_real_data(tmp_path):
    """예시 폴더 빌드에는 사내 오버레이를 섞지 않는다 (자동 적용은 data/real/… 폴더만)."""
    assert resolve_overlay(tmp_path) is None
    assert resolve_overlay(tmp_path, None) is None
    assert resolve_overlay(tmp_path, tmp_path) == tmp_path
    assert default_overlay_dir(tmp_path) is None                 # 저장소 config/ 가 아닌 폴더에는 붙이지 않는다
    assert CONFIG_DIR.is_dir()


def test_config_error_is_one_line(tmp_path, monkeypatch):
    """설정 오류는 traceback 없이 '[NG] 설정 오류' 한 줄, rc 2."""
    import engenius_wf.pipeline as pl

    ov = tmp_path / "ov"
    ov.mkdir()
    (ov / "rules.yaml").write_text("levels: [x]\n", encoding="utf-8")
    monkeypatch.setattr(pl, "resolve_overlay", lambda src, overlay_dir=pl.AUTO: ov)
    d = copy_example(tmp_path, "short", state=False)
    rc, out = run_cli(["check", d])
    assert rc == 2 and "[NG] 설정 오류" in out
