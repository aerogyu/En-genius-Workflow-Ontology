"""pytest 공통 설정 — 실행 환경 전제를 한 줄로 알리고, 예시 빌드를 한 번만 해 둔다.

Python UTF-8 모드(PYTHONUTF8=1)가 꺼져 있으면 한국어 Windows(코드 페이지 949)에서 linkml·yaml 이 스키마 YAML 을 cp949 로 읽어
schema 테스트가 UnicodeDecodeError 로 실패한다 (형제 저장소 사내 selftest 2026-10-03 실측). 개발 PC 는 사용자 환경변수 PYTHONUTF8=1 이 있어
드러나지 않는다. 사내는 env.bat 가 켠다 — 그 밖의 방법으로 돌리면 여기서 바로 멈춘다.
예시 빌드는 저장소 예시 폴더를 임시 폴더에 복사해서 한다 (빌드가 YAML 폴더 안 _registry 를 다시 쓰므로 저장소 파일을 건드리지 않게).
"""
import sys

import pytest

from wfhelp import SURVEY, build_copy, catalogs_or_none


def pytest_configure(config):
    if not sys.flags.utf8_mode:
        # cp949 콘솔에서도 깨지지 않게 '—'·'·' 같은 기호는 쓰지 않는다
        pytest.exit("Python UTF-8 모드가 꺼져 있다 - `set PYTHONUTF8=1` (env.bat 를 거쳐 실행) 뒤 다시 돌린다. "
                    "꺼진 채로는 linkml/yaml 이 한국어 YAML 을 cp949 로 읽어 schema 테스트가 실패한다.", returncode=3)


@pytest.fixture(scope="session")
def survey_cats():
    """교차 확인 카탈로그 [합성 카탈로그, 형제 저장소 합성 survey.ttl] — survey.ttl 이 없으면 skip."""
    cats = catalogs_or_none()
    if cats is None:
        pytest.skip(f"형제 저장소 합성 survey.ttl 없음 ({SURVEY}) — WF_SURVEY_TTL 로 지정 가능")
    return cats


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """예시 빌드 — {'short', 'textbook_nocat', 'textbook'(survey.ttl 있을 때만)} → Built(src, out, rc, stdout)."""
    base = tmp_path_factory.mktemp("built")
    out = {"short": build_copy(base, "short"), "textbook_nocat": build_copy(base, "textbook", name="textbook_nocat")}
    cats = catalogs_or_none()
    if cats is not None:
        out["textbook"] = build_copy(base, "textbook", catalogs=cats)
    return out
