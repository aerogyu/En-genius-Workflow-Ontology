"""V11 홈 폴더가 없는 환경 · V12 UTF-8 모드 꺼짐(cp949)+파이프 출력 — 사내 PC 흉내 (별도 프로세스)."""

from __future__ import annotations

import os
import subprocess
import sys

from engenius_wf.config import REPO_ROOT
from wfhelp import catalogs_or_none, copy_example


def test_build_without_home_folder(tmp_path):
    """홈 폴더가 없어도 빌드는 rc 0 이고 linkml·pystow·curies 를 import 하지 않는다 (linkml SchemaView 는 이 환경에서 실패한다)."""
    d = copy_example(tmp_path, "short")
    env = dict(os.environ, USERPROFILE=r"Z:\nohome", HOME=r"Z:\nohome", HOMEDRIVE="Z:", HOMEPATH=r"\nohome",
               PYTHONPATH=str(REPO_ROOT / "src"), PYTHONUTF8="1")
    code = ("import sys; from engenius_wf.cli import main; "
            f"rc = main(['build', {str(d)!r}, '--out', {str(tmp_path / 'out')!r}]); "
            "print('RC', rc, 'LINKML', sorted({m.split('.')[0] for m in sys.modules} & {'linkml', 'linkml_runtime', 'pystow', 'curies'}))")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp_path, env=env)
    last = [ln for ln in p.stdout.splitlines() if ln.startswith("RC")]
    assert last == ["RC 0 LINKML []"], p.stdout[-800:] + p.stderr[-800:]


def test_build_with_utf8_mode_off_and_cp949_pipe(tmp_path):
    """사내 흉내: PYTHONUTF8=0 + 출력 cp949 + 파이프 — 출력 스트림 errors=replace 로 죽지 않고 결과가 같다."""
    d = copy_example(tmp_path, "textbook")
    cats = catalogs_or_none()
    env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp949", PYTHONPATH=str(REPO_ROOT / "src"))
    p = subprocess.run([sys.executable, "-m", "engenius_wf", "build", str(d), "--out", str(tmp_path / "out")]
                       + (["--catalog", *cats] if cats else []), capture_output=True, cwd=tmp_path, env=env)
    assert p.returncode == 0, p.stderr.decode("cp949", errors="replace")[-800:]
    text = p.stdout.decode("cp949", errors="replace")
    assert "TTL: 작성 427 + 파생 222 트리플" in text
    assert (tmp_path / "out" / "report.txt").read_text(encoding="utf-8").endswith("\n")
