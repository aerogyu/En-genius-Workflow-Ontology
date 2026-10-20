"""명령행 진입점: python -m engenius_wf <명령> (코드는 설치하지 않고 PYTHONPATH=src 로 실행한다).

  build <YAML 폴더> [--out 폴더] [--catalog survey.ttl ...]   검사 + 생성 전부 (오류가 있으면 결과 파일을 만들지 않는다, rc 1)
  check <YAML 폴더> [--catalog ...]                           검사만 (출력 없음 — 작성 중에 자주)
  release <YAML 폴더> <계약 key> --reason "사유"               확정 판 동결 (HITL 기록: 일자·사유, 인명 없음)
  validate <빌드 출력 폴더> <데이터.json ...>                  실제 데이터가 계약을 지키는지
  link-tools <YAML 폴더> --catalog ... --csv <파일>           TOOL ID 후보 CSV (사람이 확정)
  query <빌드 출력 폴더> [q01 ...] [--catalog ...] [--table]  queries/*.rq 를 rdflib 로 (--table: 칸을 맞춘 표)
  schema [--check]                                            LinkML → schema/generated/ (linkml 은 이 명령에서만 import)
  doctor · licenses                                           실행 환경 점검 · 설치 패키지 라이선스 표
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from engenius_wf import __version__

COMMANDS = {
    "build": "검사 + 생성 전부 (TTL 2그래프·trig·Protégé 보기용 합본·계약 JSON Schema·골격·흐름 그림 HTML·report.txt·canonical.json)",
    "check": "검사만 (결과 파일 없음 — 작성 중에 자주)",
    "release": "계약의 확정 판 동결 (_released/<계약>/<판>.json — 일자·사유, 인명 없음)",
    "validate": "실제 데이터(JSON)가 계약을 지키는지 검사",
    "link-tools": "Tool 온톨로지 TOOL ID 후보 CSV (사람이 보고 _plan.yaml 에 적는다)",
    "query": "역량 질의(queries/*.rq)를 빌드 출력에 실행 (rdflib, --table: 표 — query.bat)",
    "schema": "LinkML 스키마 → schema/generated/ 재생성 (VS Code 작성용 스키마 포함, --check: 드리프트만 확인)",
    "doctor": "실행 환경 점검 (Python·UTF-8 모드·Java·패키지·생성물·설정)",
    "licenses": "설치 패키지 라이선스 표 (금지 항목 있으면 rc 1)",
}


def _config_error(e: Exception) -> int:
    """설정 파일 오류(ConfigError)는 traceback 없이 한 줄로 — 사내에서 오버레이를 손으로 고치다 생기는 것."""
    print(f"[NG] 설정 오류: {e}", file=sys.stderr)
    return 2


def _overlay_note(ctx) -> None:
    if ctx and ctx.get("overlay"):
        from engenius_wf.config import config_where

        print(f"설정 오버레이: {config_where(ctx['overlay'])}")


def default_out(src: Path) -> Path:
    """기본 출력 폴더 — output/<실행 시각>_<YAML 폴더 이름>/ (git 제외)."""
    from engenius_wf.config import OUTPUT_DIR

    return OUTPUT_DIR / f"{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}_{Path(src).resolve().name}"


def cmd_build(a: argparse.Namespace) -> int:
    from engenius_wf.config import ConfigError
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report

    src = Path(a.src)
    out = Path(a.out) if a.out else default_out(src)
    rep = Report()
    try:
        ctx = run(src, out, a.catalog, rep)
    except ConfigError as e:
        return _config_error(e)
    text = rep.render()
    print(text)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
    _overlay_note(ctx)
    if ctx:
        m = ctx["m"]
        print(f"TTL: 작성 {len(ctx['A'])} + 파생 {len(ctx['D'])} 트리플 · 단계 {len(m['step'])} · 계약 {len(m['interface'])} "
              f"(JSON Schema {ctx['n_schema']}) · 루프 {len(m['loop'])} → {out}")
        n = ctx["protege"]
        print(f"Protégé 보기용: workflow_protege.ttl (트리플 {n['total']} = 스키마 {n['schema']} + 작성 {n['authored']} + "
              f"파생 {n['derived']} + 머리 {n['header']} + 외부 어휘 선언 {n['declared']}) — 보기 전용, 고쳐도 YAML 로 돌아가지 않는다")
    return 0 if ctx else 1


def cmd_check(a: argparse.Namespace) -> int:
    from engenius_wf.config import ConfigError
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report

    rep = Report()
    try:
        ctx = run(Path(a.src), None, a.catalog, rep, write=False)
    except ConfigError as e:
        return _config_error(e)
    print(rep.render())
    _overlay_note(ctx)
    return 0 if ctx else 1


def cmd_release(a: argparse.Namespace) -> int:
    from engenius_wf.config import ConfigError
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report
    from engenius_wf.versioning import do_release

    src = Path(a.src)
    rep = Report()
    try:
        ctx = run(src, None, [], rep, write=False)
    except ConfigError as e:
        return _config_error(e)
    if ctx:
        do_release(ctx["m"], src, a.key, a.reason, rep, rules=ctx["rules"], renames=ctx["registry"].renames)
    print(rep.render())
    return 1 if rep.errors else 0


def cmd_validate(a: argparse.Namespace) -> int:
    from engenius_wf.contracts import validate_payloads
    from engenius_wf.report import Report

    rep = Report()
    validate_payloads(Path(a.out), a.files, rep)
    print(rep.render())
    return 1 if rep.errors else 0


def cmd_link_tools(a: argparse.Namespace) -> int:
    from engenius_wf.config import ConfigError
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report
    from engenius_wf.tools import link_tools, load_catalog

    rep = Report()
    try:
        ctx = run(Path(a.src), None, [], rep, write=False)
    except ConfigError as e:
        return _config_error(e)
    if not ctx:
        print(rep.render())
        return 1
    rows = link_tools(ctx["m"], load_catalog(a.catalog), Path(a.csv))
    for row in rows:
        print(" | ".join(row.values()))
    return 0


def cmd_query(a: argparse.Namespace) -> int:
    from engenius_wf.query import is_cross, query_files, query_title, render_table, run_local, union_graph
    from engenius_wf.report import suggest

    out = Path(a.out)
    if not (out / "workflow.ttl").is_file() or not (out / "workflow_derived.ttl").is_file():
        print(f"{out} 에 workflow.ttl·workflow_derived.ttl 이 없다 — 먼저 build 를 실행한다.", file=sys.stderr)
        return 1
    files = query_files()
    names = a.names or list(files)
    bad = [n for n in names if n not in files]
    if bad:
        print(f"모르는 질의: {', '.join(bad)} — 있는 질의: {', '.join(files)} {suggest(bad[0], files)}".rstrip(), file=sys.stderr)
        return 2
    g = union_graph(out, a.catalog)
    cross_without_catalog = []
    for n in names:
        text = files[n].read_text(encoding="utf-8")
        cols, rows = run_local(g, text)
        print(f"== {n} {query_title(files[n])} — {len(rows)}행")
        if a.table:
            for line in render_table(cols, rows):
                print("  " + line)
            print()
            if is_cross(text) and not a.catalog:
                cross_without_catalog.append(n)
        else:
            print("\t".join(cols))
            for r in rows:
                print("\t".join(r))
    if cross_without_catalog:
        print(f"참고: {'·'.join(cross_without_catalog)} 는 Tool 온톨로지 교차 질의 — survey.ttl 을 --catalog 로 같이 주면 "
              "(query.bat 에는 출력 폴더와 함께 끌어다 놓으면) 조사 쪽 열이 채워진다.")
    return 0


def _java_version() -> str | None:
    """JAVA_HOME 을 먼저 보고, 없으면 PATH 의 java — 사내 PC 는 JDK zip 만 풀어 PATH 에 java 가 없다."""
    java = None
    home = os.environ.get("JAVA_HOME")
    if home:
        cand = Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        java = str(cand) if cand.is_file() else None
    java = java or shutil.which("java")
    if not java:
        return None
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = (out.stderr or out.stdout).strip().splitlines()
    return lines[0] if lines else None


def cmd_doctor(_a: argparse.Namespace) -> int:
    """실행 환경 점검 — 사내 반입 후 첫 확인용."""
    from importlib.metadata import PackageNotFoundError, version

    from engenius_wf.config import GEN_DIR, REAL_CONFIG_DIR, ConfigError, config_where, load_rules, load_units
    from engenius_wf.licenses import DENYLIST, audit, denylisted

    ok = True
    py_ok = sys.version_info >= (3, 10)
    ok &= py_ok
    print(f"[{'OK' if py_ok else 'NG'}] Python {platform.python_version()} (3.10 이상 필요)")
    utf8 = bool(sys.flags.utf8_mode)
    utf8_msg = "켜짐" if utf8 else "꺼짐 - set PYTHONUTF8=1 (env.bat 를 거쳐 실행); 아니면 linkml·yaml 이 cp949 로 읽어 schema 명령이 실패"
    print(f"[{'OK' if utf8 else 'NG'}] Python UTF-8 모드 {utf8_msg}")
    jv = _java_version()
    print(f"[{'OK' if jv else '--'}] Java: {jv or '없음 (SHACL·Fuseki 에만 필요)'}")
    for dist in ("rdflib", "PyYAML", "jsonschema", "linkml", "rfc3986-validator"):
        try:
            print(f"[OK] {dist} {version(dist)}")
        except PackageNotFoundError:
            ok = False
            print(f"[NG] {dist} 없음")
    bad = denylisted(audit())
    for r in bad:
        ok = False
        print(f"[NG] {r.name} 설치돼 있음 — {DENYLIST[r.name.lower()]}")
    if not bad:
        print("[OK] 금지 패키지 없음 (rfc3987 등)")
    for name in ("terms.json", "wfo_file.schema.json"):
        p = GEN_DIR / name
        ok &= p.is_file()
        print(f"[{'OK' if p.is_file() else 'NG'}] 생성물 {config_where(p)}" + ("" if p.is_file() else " 없음 - schema 명령으로 만든다"))
    try:
        load_rules(overlay_dir=REAL_CONFIG_DIR if REAL_CONFIG_DIR.is_dir() else None)
        load_units(overlay_dir=REAL_CONFIG_DIR if REAL_CONFIG_DIR.is_dir() else None)
        print("[OK] 설정 config/rules.yaml·units.yaml" + (f" + 오버레이 {config_where(REAL_CONFIG_DIR)}" if REAL_CONFIG_DIR.is_dir() else ""))
    except ConfigError as e:
        ok = False
        print(f"[NG] 설정 오류: {e}")
    return 0 if ok else 1


def cmd_licenses(_a: argparse.Namespace) -> int:
    """설치 패키지 라이선스 표. 금지(GPL) 항목이 있으면 rc=1 — 반입 심사 자료."""
    from engenius_wf.licenses import FORBIDDEN, MULTI, UNKNOWN, WEAK, audit, to_markdown

    rows = audit()
    print(to_markdown(rows))
    counts = {c: sum(r.cls == c for r in rows) for c in (FORBIDDEN, MULTI, WEAK, UNKNOWN)}
    print(f"\n전체 {len(rows)}개 — " + ", ".join(f"{c} {n}" for c, n in counts.items()))
    return 1 if counts[FORBIDDEN] else 0


def cmd_schema(a: argparse.Namespace) -> int:
    from engenius_wf import schema_gen          # linkml 은 여기서만 (지연 import)

    return schema_gen.run(check=a.check)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="engenius_wf", description="En-Genius 개념설계 워크플로 온톨로지 — YAML → 검사·RDF·계약·그림")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<명령>")
    sp = sub.add_parser("build", help=COMMANDS["build"])
    sp.add_argument("src", help="YAML 폴더 (예 workflows/examples/textbook)")
    sp.add_argument("--out", help="출력 폴더 (기본 output/<실행 시각>_<폴더 이름>/)")
    sp.add_argument("--catalog", nargs="*", default=[], help="Tool 온톨로지 survey.ttl·카탈로그 TTL (주면 TOOL ID 교차 확인)")
    sp.set_defaults(func=cmd_build)
    sp = sub.add_parser("check", help=COMMANDS["check"])
    sp.add_argument("src")
    sp.add_argument("--catalog", nargs="*", default=[])
    sp.set_defaults(func=cmd_check)
    sp = sub.add_parser("release", help=COMMANDS["release"])
    sp.add_argument("src")
    sp.add_argument("key", help="계약 key")
    sp.add_argument("--reason", required=True, help="동결 사유 (인명 금지)")
    sp.set_defaults(func=cmd_release)
    sp = sub.add_parser("validate", help=COMMANDS["validate"])
    sp.add_argument("out", help="build 출력 폴더 (contracts/ 가 있는 곳)")
    sp.add_argument("files", nargs="+", help="검사할 데이터 JSON (봉투: contract·version·data)")
    sp.set_defaults(func=cmd_validate)
    sp = sub.add_parser("link-tools", help=COMMANDS["link-tools"])
    sp.add_argument("src")
    sp.add_argument("--catalog", nargs="+", required=True)
    sp.add_argument("--csv", required=True, help="후보 CSV 를 쓸 파일")
    sp.set_defaults(func=cmd_link_tools)
    sp = sub.add_parser("query", help=COMMANDS["query"])
    sp.add_argument("out", help="build 출력 폴더")
    sp.add_argument("names", nargs="*", help="질의 이름 (q01 …, 기본: 전부)")
    sp.add_argument("--catalog", nargs="*", default=[], help="교차 질의(q07·q08)용 Tool 온톨로지 TTL")
    sp.add_argument("--table", action="store_true", help="칸을 맞춘 표로 (기본: 탭으로 나눈 줄 — query.bat 은 표)")
    sp.set_defaults(func=cmd_query)
    sp = sub.add_parser("schema", help=COMMANDS["schema"])
    sp.add_argument("--check", action="store_true", help="생성하지 않고 커밋된 생성물이 스키마와 일치하는지만 확인")
    sp.set_defaults(func=cmd_schema)
    sp = sub.add_parser("doctor", help=COMMANDS["doctor"])
    sp.set_defaults(func=cmd_doctor)
    sp = sub.add_parser("licenses", help=COMMANDS["licenses"])
    sp.set_defaults(func=cmd_licenses)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # 한글 Windows 기본 콘솔(cp949)·파이프에서도 출력 문자 때문에 죽지 않도록 (사내 UTF-8 모드 함정)
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)
