"""경로와 설정 파일 읽기. 경로는 저장소 루트 기준 (코드는 설치하지 않고 PYTHONPATH=src 로 실행한다).

설정 오버레이 (형제 저장소 Tool 온톨로지 config.py 와 같은 규칙): data/real/config/<이름>.yaml 이 있으면 config/<이름>.yaml
위에 덮는다. 저장소의 config/ 는 공개 값만 두고, 사내에서 조정한 값(메시지 수준·단위·전달 방법 별칭·인명 패턴)은 오버레이에
쌓는다 (git 제외, 업데이트 파일이 덮어쓰지 않는다). 합치는 방식은 키 단위 덮어쓰기 — 중첩 매핑은 키별로 내려가고 목록·스칼라는
통째로 바꾼다 (units.yaml 의 units·aliases 는 단위 하나씩 더하거나 바꾼다). 오버레이는 실데이터 폴더(data/real/…)를 빌드할 때만
자동으로 쓴다 — 예시 빌드에는 섞지 않는다 (pipeline.run).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
REAL_DIR = REPO_ROOT / "data" / "real"                    # 사내 실데이터 (git 제외 — .gitignore data/real/)
REAL_CONFIG_DIR = REAL_DIR / "config"                     # 사내 설정 오버레이
REAL_WORKFLOWS_DIR = REAL_DIR / "workflows"               # 사내 실 YAML·_registry·_released
SCHEMA_DIR = REPO_ROOT / "schema"
SCHEMA_FILE = SCHEMA_DIR / "wfo.yaml"                     # LinkML 마스터
ALIGN_FILE = SCHEMA_DIR / "alignment.ttl"                 # 표준 정렬 (손으로)
GEN_DIR = SCHEMA_DIR / "generated"                        # schema 명령의 생성물 — 빌드 런타임은 여기만 읽는다 (linkml import 0)
QUERIES_DIR = REPO_ROOT / "queries"
OUTPUT_DIR = REPO_ROOT / "output"
EXAMPLES_DIR = REPO_ROOT / "workflows" / "examples"


class ConfigError(ValueError):
    """설정 파일(config/·오버레이)의 형식·값 오류 — CLI 는 '[NG] 설정 오류: …' 한 줄로 보여 주고 rc 2 (traceback 없이)."""


def config_where(path: Path) -> str:
    """오류 문구에 쓰는 설정 파일 경로 — 저장소 안이면 저장소 기준 상대 경로('/' 구분), 밖이면 절대 경로."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(p)


def read_yaml(path: Path, where: str | None = None) -> dict:
    """설정 YAML 하나 읽기 (UTF-8 고정 — 사내 cp949 콘솔에서도 같은 결과). 문법 오류는 traceback 대신 ConfigError —
    '<파일> <행>행 <열>열: YAML 문법 오류' 로 자리만 알리고 줄 내용은 넣지 않는다 (오버레이에는 사내 값이 들 수 있다)."""
    path = Path(path)
    where = where or config_where(path)
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        at = f" {mark.line + 1}행 {mark.column + 1}열" if mark is not None else ""
        raise ConfigError(f"{where}{at}: YAML 문법 오류 — 들여쓰기·괄호·콜론 뒤 공백을 확인") from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{where} (파일 전체): 형식은 매핑(키: 값) 이어야 한다 (지금: {type(data).__name__})")
    return data


def default_overlay_dir(config_dir: Path | None = None) -> Path | None:
    """기본 오버레이 폴더 — 저장소 config/ 를 쓸 때만 data/real/config (있을 때). 다른 config 폴더(테스트 사본)에는 붙이지 않는다."""
    base = Path(config_dir or CONFIG_DIR).resolve()
    if base == CONFIG_DIR.resolve() and REAL_CONFIG_DIR.is_dir():
        return REAL_CONFIG_DIR
    return None


def _merge_dict_keys(base: dict, over: dict, where: str = "", path: str = "") -> dict:
    """키 단위 덮어쓰기 — 중첩 dict 는 키별로 내려가고, 목록·스칼라는 통째 바꾼다 (형제 저장소 rules.yaml 방식).
    기본값이 매핑·목록인 키에 다른 형식을 덮으면 ConfigError (where = 오버레이 파일 이름).
    값 없는 키(`levels:` 처럼 YAML 에서 None)로 매핑·목록 기본값을 지우는 것도 오류 — 조용히 None 으로 덮지 않는다."""
    out = dict(base or {})
    for k, v in (over or {}).items():
        cur = out.get(k)
        name = f"{path}.{k}" if path else str(k)
        if v is None and isinstance(cur, (dict, list)):
            raise ConfigError(f"{where} {name}: 값이 비어 있다 — 키를 지우거나 값을 적는다")
        if isinstance(v, dict) and isinstance(cur, dict):
            out[k] = _merge_dict_keys(cur, v, where, name)
        elif v is not None and isinstance(cur, dict) and not isinstance(v, dict):
            raise ConfigError(f"{where} {name}: 형식은 매핑(키: 값) 이어야 한다 (지금: {type(v).__name__})")
        elif v is not None and isinstance(cur, list) and not isinstance(v, list):
            raise ConfigError(f"{where} {name}: 형식은 목록 이어야 한다 (지금: {type(v).__name__})")
        else:
            out[k] = v
    return out


def load_config(name: str, config_dir: Path | None = None, overlay_dir: Path | None = None) -> tuple[dict, bool]:
    """(합친 설정, 오버레이 파일을 썼는지). overlay_dir 가 None 이면 오버레이 없음 — 호출자가 default_overlay_dir() 로 정한다."""
    base_path = Path(config_dir or CONFIG_DIR) / name
    base = read_yaml(base_path)
    over_path = Path(overlay_dir) / name if overlay_dir else None
    if over_path is None or not over_path.is_file():
        return base, False
    over = read_yaml(over_path)
    return _merge_dict_keys(base, over, config_where(over_path)), True


def load_rules(config_dir: Path | None = None, overlay_dir: Path | None = None) -> dict:
    """config/rules.yaml (+ 오버레이) — 전달 방법 별칭·수기 값·참거짓 글자·메시지 수준(levels)·인명 패턴."""
    return load_config("rules.yaml", config_dir, overlay_dir)[0]


def load_units(config_dir: Path | None = None, overlay_dir: Path | None = None) -> tuple[dict, dict]:
    """config/units.yaml (+ 오버레이) → (단위 표기 → {qudt, kind, label, factor, offset}, 별칭 표기 → 정식 표기). 키는 글자로."""
    raw = load_config("units.yaml", config_dir, overlay_dir)[0]
    return {str(k): v for k, v in raw["units"].items()}, {str(k): str(v) for k, v in (raw.get("aliases") or {}).items()}
