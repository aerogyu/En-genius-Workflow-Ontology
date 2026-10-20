"""scripts\\*.bat 의 도우미 — 끌어다 놓은 인자 고르기·기본 폴더·출력 폴더·결과 열기·selftest 요약을 파이썬으로 한다.

.bat 은 한국어 Windows 의 cmd 가 cp949 로 읽으므로 영어 ASCII 만 쓰고 이 파일을 부르기만 한다. 경로를 cmd 변수로 되받지
않는다 — for /f 는 파이썬 출력을 코드 페이지(cp949)로 읽어 한글 폴더 이름이 깨진다. 판단과 실행을 여기서 끝낸다.
실제 일은 python -m engenius_wf 와 같은 CLI(engenius_wf.cli.main)가 한다. 이 파일은 인자와 기본값만 정한다.

  build      [YAML 폴더|YAML 파일] [카탈로그.ttl …]   인자 없으면 data/real/workflows(있으면), 없으면 workflows/examples/textbook.
                                                    성공하면 workflow.html 을 연다 (WF_NO_OPEN=1 이면 열지 않는다)
  check      [YAML 폴더|YAML 파일] [카탈로그.ttl …]   기본 폴더는 build 와 같다
  link-tools [YAML 폴더] [카탈로그.ttl …]            카탈로그가 없으면 예시 폴더일 때만 예시 합성 카탈로그, 아니면 멈춤 (rc 2).
                                                    CSV → output/<시각>_<폴더 이름>_tool_candidates.csv
  validate   [build 출력 폴더] <데이터.json …>        출력 폴더를 안 주면 가장 최근 build 출력 (contracts/ 가 있는 것)
  query      [build 출력 폴더|그 안의 .ttl] [survey.ttl …] [q01 …]
                                                    출력 폴더를 안 주면 가장 최근 build 출력 (workflow.ttl 이 있는 것).
                                                    q01~q08 을 표로 (query --table). 다른 .ttl = Tool 온톨로지 카탈로그 (q07·q08)
  release    [YAML 폴더] [계약 key] [사유 …]          빠진 것은 묻는다. 폴더 기본은 data/real/workflows — 없으면 멈춤
                                                    (예시 폴더는 저장소 파일이라 기본으로 동결하지 않는다)
  selftest                                         doctor → pytest → offline/selftest_<커밋>.txt (값 없음) + .log (사내에만)
  commit                                           설치 판 7자리 (offline/installed_commit.txt 1행 → git → unknown)

상대 경로 인자는 .bat 을 부른 폴더(WF_CALLER_DIR) → 저장소 루트 순으로 찾는다. 인자 문제는 '[NG] …' 한 줄과 rc 2.
"""

from __future__ import annotations

import codecs
import datetime as dt
import locale
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:          # env.bat 이 PYTHONPATH=src 를 잡지만, 직접 불러도 돌게
    sys.path.insert(0, str(REPO / "src"))

from engenius_wf import cli, config  # noqa: E402

YAML_SUFFIX = ".yaml"                          # 빌드는 *.yaml 만 읽는다 (.yml 은 읽지 않음 — 안내만)


class Stop(Exception):
    """인자·기본 폴더 문제 — '[NG] …' 한 줄로 알리고 rc 2 (아무것도 바꾸지 않았다)."""


def example_default() -> Path:
    return config.EXAMPLES_DIR / "textbook"


def synthetic_catalog() -> Path:
    return config.EXAMPLES_DIR / "catalog" / "tools_synthetic.ttl"


def rel(p) -> str:
    """화면용 경로 — 저장소 안이면 저장소 기준 상대 경로, 밖이면 절대 경로."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(REPO.resolve()))
    except ValueError:
        return str(p)


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def resolve_arg(a: str) -> Path:
    """인자 → 경로. 끝의 '\\"' 가 따옴표로 남는 cmd 함정('"C:\\x\\"' → 'C:\\x"')도 걷어 낸다."""
    p = Path(a.strip().strip('"'))
    if p.is_absolute():
        return p
    caller = os.environ.get("WF_CALLER_DIR")
    bases = ([Path(caller)] if caller else []) + [Path.cwd(), REPO]
    for base in bases:
        if (base / p).exists():
            return base / p
    return bases[0] / p


def is_example(src: Path) -> bool:
    try:
        Path(src).resolve().relative_to(config.EXAMPLES_DIR.resolve())
        return True
    except ValueError:
        return False


def default_folder(cmd: str) -> Path:
    real = config.REAL_WORKFLOWS_DIR
    if real.is_dir():
        print(f"[{cmd}] 폴더 = {rel(real)} (사내 실데이터 폴더)")
        return real
    ex = example_default()
    print(f"[{cmd}] 폴더 = {rel(ex)} (data\\real\\workflows 가 없어 교과서 예시 — 연습)")
    return ex


def folder_hints(cmd: str, src: Path) -> None:
    """빌드가 못 읽는 것을 미리 알린다 — .yml 확장자, YAML 이 하위 폴더에만 있음."""
    if not src.is_dir():
        return
    yml = sorted(p.name for p in src.glob("*.yml"))
    if yml:
        print(f"[{cmd}] 주의: '.yml' 파일은 읽지 않는다 — 확장자를 .yaml 로 바꾼다: {', '.join(yml)}")
    if not any(src.glob("*" + YAML_SUFFIX)):
        subs = sorted(d.name for d in src.iterdir() if d.is_dir() and any(d.glob("*" + YAML_SUFFIX)))
        if subs:
            print(f"[{cmd}] 주의: 이 폴더에는 YAML 이 없고 하위 폴더 {', '.join(subs)} 에 있다 — 그 폴더를 끌어다 놓는다")


def pick(args, cmd: str):
    """끌어다 놓은 인자 고르기 → (YAML 폴더, 카탈로그 목록, 기본 폴더를 썼는지). .ttl = 카탈로그, 폴더·YAML 파일 = YAML 폴더."""
    src, cats = None, []
    for a in args:
        p = resolve_arg(a)
        if p.suffix.lower() == ".ttl":
            if not p.is_file():
                raise Stop(f"카탈로그 파일이 없다: {a}")
            cats.append(p)
        elif p.is_dir() or (p.is_file() and p.suffix.lower() in (YAML_SUFFIX, ".yml")):
            d = p if p.is_dir() else p.parent
            if src is not None and d.resolve() != src.resolve():
                raise Stop(f"YAML 폴더가 둘이다: {rel(src)} · {rel(d)} — 한 번에 한 폴더만")
            src = d
        elif p.exists():
            raise Stop(f"YAML 폴더·YAML 파일·카탈로그(.ttl)가 아니다: {a}")
        else:
            raise Stop(f"찾을 수 없다: {a}")
    defaulted = src is None
    if defaulted:
        src = default_folder(cmd)
    else:
        print(f"[{cmd}] 폴더 = {rel(src)}")
    folder_hints(cmd, src)
    for c in cats:
        print(f"[{cmd}] 카탈로그 = {rel(c)}")
    return src, cats, defaulted


def open_file(path: Path, cmd: str) -> None:
    print(f"[{cmd}] 흐름 그림: {path}")
    if os.environ.get("WF_NO_OPEN") or not hasattr(os, "startfile"):
        return
    try:
        os.startfile(str(path))                # 기본 브라우저로 (로컬 파일 — 외부 호출 없음)
    except OSError as e:
        print(f"[{cmd}] 브라우저로 열지 못했다 ({e.__class__.__name__}) — 위 파일을 직접 연다")


def cat_args(cats) -> list[str]:
    return ["--catalog", *map(str, cats)] if cats else []


# --------------------------------------------------------------------------- 명령
def do_build(args) -> int:
    src, cats, _ = pick(args, "build")
    out = cli.default_out(src)
    rc = cli.main(["build", str(src), "--out", str(out)] + cat_args(cats))
    if rc == 0:
        open_file(out / "workflow.html", "build")
    elif rc == 1:
        print("[build] 오류가 있어 결과 파일을 만들지 않았다 — 각 줄의 '→' 안내대로 고친 뒤 다시 (docs\\02_작성안내.md 6장 실수 표)")
    return rc


def do_check(args) -> int:
    src, cats, _ = pick(args, "check")
    rc = cli.main(["check", str(src)] + cat_args(cats))
    if rc == 0:
        print("[check] 오류 없음 — build.bat 으로 결과 파일(TTL·계약·그림)을 만든다")
    return rc


def do_link_tools(args) -> int:
    src, cats, _ = pick(args, "link-tools")
    if not cats:
        if not is_example(src):
            raise Stop("Tool 온톨로지 survey.ttl 이 필요하다 — YAML 폴더와 survey.ttl"
                       "(...\\engenius-tool-ontology\\output\\<실행ID>\\survey.ttl)을 함께 끌어다 놓는다")
        cats = [synthetic_catalog()]
        print(f"[link-tools] 카탈로그 = {rel(cats[0])} (예시 폴더라 합성 카탈로그)")
    out_dir = config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stamp()}_{Path(src).resolve().name}_tool_candidates.csv"
    rc = cli.main(["link-tools", str(src), "--catalog", *map(str, cats), "--csv", str(csv_path)])
    if rc == 0:
        print(f"[link-tools] 후보 CSV: {csv_path}")
        print("[link-tools] 엑셀로 열어 보고, 맞는 TOOL ID 를 _plan.yaml tools 의 tool_id·label_at_link 에 사람이 적는다 (빌드는 채우지 않는다)")
    return rc


def latest_out(need=("contracts",)):
    """가장 최근 build 출력 — need(기본 contracts/)와 report.txt 가 있는 output/* 중 report.txt 가 가장 새것
    (실패한 빌드는 contracts/·TTL 이 없다)."""
    base = config.OUTPUT_DIR
    if not base.is_dir():
        return None
    cands = [p for p in base.iterdir() if p.is_dir() and all((p / n).exists() for n in need) and (p / "report.txt").is_file()]
    return max(cands, key=lambda p: (p / "report.txt").stat().st_mtime) if cands else None


def do_validate(args) -> int:
    out, files = None, []
    for a in args:
        p = resolve_arg(a)
        if p.is_dir() and (p / "contracts").is_dir():
            if out is not None and p.resolve() != out.resolve():
                raise Stop(f"build 출력 폴더가 둘이다: {rel(out)} · {rel(p)}")
            out = p
        elif p.is_file() and p.suffix.lower() == ".json":
            files.append(p)
        elif p.is_dir():
            raise Stop(f"contracts 폴더가 없다 — build 출력 폴더(output\\<실행>)가 아니다: {a}")
        elif p.exists():
            raise Stop(f"JSON 파일이 아니다: {a}")
        else:
            raise Stop(f"찾을 수 없다: {a}")
    if not files:
        raise Stop("검사할 데이터 JSON 이 없다 — JSON 파일을 validate.bat 위에 끌어다 놓는다 "
                   "(본보기: build 출력 contracts\\<계약>\\<판>.example.json)")
    if out is None:
        out = latest_out()
        if out is None:
            raise Stop("build 출력이 없다 — 먼저 build.bat")
        print(f"[validate] 계약 = {rel(out)} (가장 최근 build 출력 — 다른 빌드면 그 출력 폴더도 함께 끌어다 놓는다)")
    else:
        print(f"[validate] 계약 = {rel(out)}")
    return cli.main(["validate", str(out), *map(str, files)])


BUILD_TTL = ("workflow.ttl", "workflow_derived.ttl")
QUERY_NAME = re.compile(r"[qQ]\d\d")


def is_build_out(p: Path) -> bool:
    return p.is_dir() and all((p / n).is_file() for n in BUILD_TTL)


def do_query(args) -> int:
    """질의 q01~q08 을 표로 — 끌어다 놓은 build 출력 폴더(또는 그 안의 workflow*.ttl), 없으면 가장 최근 build 출력. 읽기만 한다."""
    out, cats, names = None, [], []
    for a in args:
        if QUERY_NAME.fullmatch(a.strip()):
            names.append(a.strip().lower())
            continue
        p = resolve_arg(a)
        if p.is_file() and p.suffix.lower() == ".ttl" and p.name.startswith("workflow") and is_build_out(p.parent):
            p = p.parent                                     # 출력 폴더 안의 workflow.ttl·workflow_protege.ttl 을 끌어다 놓음
        if p.is_dir():
            if not is_build_out(p):
                raise Stop(f"build 출력 폴더(output\\<실행>)가 아니다 — workflow.ttl·workflow_derived.ttl 이 없다 "
                           f"(오류가 있던 build 는 결과 파일이 없다): {a}")
            if out is not None and p.resolve() != out.resolve():
                raise Stop(f"build 출력 폴더가 둘이다: {rel(out)} · {rel(p)} — 한 번에 하나만")
            out = p
        elif p.is_file() and p.suffix.lower() == ".ttl":
            cats.append(p)
        elif p.exists():
            raise Stop(f"build 출력 폴더·Tool 온톨로지 카탈로그(.ttl)·질의 이름(q01 …)이 아니다: {a}")
        else:
            raise Stop(f"찾을 수 없다: {a}")
    if out is None:
        out = latest_out(need=BUILD_TTL)
        if out is None:
            raise Stop("build 출력이 없다 — 먼저 build.bat (오류 없이 끝난 build 의 출력 폴더를 쓴다)")
        print(f"[query] 출력 = {rel(out)} (가장 최근 build 출력 — 다른 빌드면 그 출력 폴더를 query.bat 위에 끌어다 놓는다)")
    else:
        print(f"[query] 출력 = {rel(out)}")
    for c in cats:
        print(f"[query] 카탈로그 = {rel(c)}")
    print()
    return cli.main(["query", str(out), *names, "--table"] + cat_args(cats))


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def show_contracts(src: Path) -> bool:
    """동결할 계약을 고르기 쉽게 목록을 보인다 (key · 지금 판 · 상태 · 동결된 판). 폴더에 오류가 있으면 보고서를 보이고 False."""
    from engenius_wf.pipeline import run
    from engenius_wf.report import Report

    rep = Report()
    try:
        ctx = run(src, None, [], rep, write=False)
    except config.ConfigError as e:
        print(f"[NG] 설정 오류: {e}")
        return False
    if not ctx:
        print(rep.render())
        print("[release] 폴더에 오류가 있어 동결하지 않는다 — check.bat 으로 먼저 고친다")
        return False
    print("[release] 계약 (key · 지금 판 · 상태 · 이미 동결된 판):")
    for k, i in ctx["m"]["interface"].items():
        frozen = ", ".join(ctx["rel_all"].get(k, {})) or "없음"
        print(f"    {k}  {i['version']}  {i.get('status', '-')}  (동결: {frozen})")
    return True


def do_release(args) -> int:
    src, rest = None, []
    for a in args:
        p = resolve_arg(a)
        if src is None and not rest and p.is_dir():
            src = p
        else:
            rest.append(a)
    if src is None:
        real = config.REAL_WORKFLOWS_DIR
        if not real.is_dir():
            raise Stop("동결할 YAML 폴더를 release.bat 위에 끌어다 놓는다 — data\\real\\workflows 가 없다 "
                       "(예시 폴더는 저장소 파일이라 기본으로 쓰지 않는다. 연습은 예시 폴더 사본으로)")
        src = real
    print(f"[release] 폴더 = {rel(src)}")
    key = rest[0].strip() if rest else ""
    reason = " ".join(rest[1:]).strip()
    if not key:
        if not show_contracts(src):
            return 1
        key = ask("동결할 계약 key: ")
        if not key:
            raise Stop("계약 key 가 비었다 — 아무것도 바꾸지 않았다")
    if not reason:
        from engenius_wf.checks import person_hit
        from engenius_wf.pipeline import resolve_overlay

        rules = config.load_rules(overlay_dir=resolve_overlay(src))
        prompt = "동결 사유 (일자는 자동으로 남는다. 인명·직급은 적지 않는다): "
        reason = ask(prompt)
        for _ in range(3):                     # 인명 유사 표기면 다시 묻는다 (값은 되비추지 않는다) — 끝내 그러면 release 가 V06 으로 거절
            if not reason or not person_hit(reason, rules):
                break
            print("[release] 사유에 인명으로 보이는 표기가 있다 — 무엇을 확인했는지만 다시 적는다 (예: 개념설계 1차 검토 통과)")
            reason = ask(prompt)
        if not reason:
            raise Stop("동결 사유가 비었다 — 아무것도 바꾸지 않았다 (사유가 HITL 기록이다)")
    return cli.main(["release", str(src), key, "--reason", reason])


# --------------------------------------------------------------------------- selftest
HEX = re.compile(r"[0-9a-fA-F]{7,40}")
COUNT_LINE = re.compile(r"^(\d+ (passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)\b.*|no tests ran.*)$")


def installed_commit(repo: Path | None = None) -> str:
    """설치 판 7자리 — offline/installed_commit.txt 1행(메모장 BOM·CRLF 무관) → (개발 PC) git → unknown."""
    repo = Path(repo or REPO)
    marker = repo / "offline" / "installed_commit.txt"
    if marker.is_file():
        tok = marker.read_text(encoding="utf-8-sig", errors="replace").split()
        if tok and HEX.fullmatch(tok[0]):
            return tok[0][:7].lower()
    if (repo / ".git").exists():
        try:
            r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"],
                               capture_output=True, text=True, timeout=20)
            c = r.stdout.strip()
            if r.returncode == 0 and HEX.fullmatch(c):
                return c[:7].lower()
        except (OSError, subprocess.SubprocessError):
            pass
    return "unknown"


def summarize(log_text: str, commit: str, doctor_rc: int, pytest_rc: int, when: str | None = None) -> str:
    """selftest 결과 파일 — 밖으로 가져가도 되는 것만: 판정·설치 판·doctor 의 [OK]/[NG]/[--] 줄·건수·Exit 줄·실패 테스트 이름.
    실패 줄은 ' - ' 앞(테스트 이름)까지만 — 뒤의 메시지에는 값이 섞일 수 있다."""
    lines = log_text.splitlines()
    when = when or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    verdict = "PASS" if pytest_rc == 0 else "FAIL"
    out = [f"selftest {verdict}  commit {commit}  {when}  doctor rc={doctor_rc}  pytest rc={pytest_rc}"]
    out += [ln.rstrip() for ln in lines if ln.startswith(("[OK]", "[NG]", "[--]"))]
    for ln in lines:
        s = ln.strip().strip("=").strip()
        if COUNT_LINE.match(s):
            out.append(s)
    for ln in lines:
        if "Exit:" in ln:
            out.append(ln[ln.index("Exit:"):].strip().rstrip("!").strip())
    out += [ln.split(" - ")[0].rstrip() for ln in lines if ln.startswith(("FAILED ", "ERROR "))]
    return "\n".join(out) + "\n"


def tee(cmd, log) -> int:
    """자식 프로세스 출력을 화면과 로그에 같이 (pytest 진행 점이 바로 보이게 조각 단위로)."""
    enc = "utf-8" if sys.flags.utf8_mode else locale.getpreferredencoding(False)
    dec = codecs.getincrementaldecoder(enc)(errors="replace")
    p = subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for chunk in iter(lambda: p.stdout.read1(4096), b""):
        text = dec.decode(chunk).replace("\r\n", "\n")
        sys.stdout.write(text)
        sys.stdout.flush()
        log.write(text)
    tail = dec.decode(b"", final=True)
    sys.stdout.write(tail)
    log.write(tail)
    return p.wait()


def do_selftest(args) -> int:
    commit = installed_commit()
    off = REPO / "offline"
    off.mkdir(exist_ok=True)
    txt, log_path = off / f"selftest_{commit}.txt", off / f"selftest_{commit}.log"
    print(f"[selftest] 설치 판 {commit}")
    with log_path.open("w", encoding="utf-8", newline="\n") as log:
        print("[selftest] 1/2 doctor")
        doctor_rc = tee([sys.executable, "-m", "engenius_wf", "doctor"], log)
        print("[selftest] 2/2 pytest (1분 남짓 — Java·Fuseki·형제 저장소 합성 survey.ttl 이 없으면 그 테스트만 건너뛴다)")
        pytest_rc = tee([sys.executable, "-m", "pytest", "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider", "-p", "no:warnings", "tests"], log)
    text = summarize(log_path.read_text(encoding="utf-8", errors="replace"), commit, doctor_rc, pytest_rc)
    txt.write_text(text, encoding="utf-8", newline="\n")
    print()
    print(text, end="")
    print(f"[selftest] 결과 파일 (밖으로 가져가도 된다 — 값 없음): {rel(txt)}")
    print(f"[selftest] 전체 기록 (사내에만 — 값이 섞일 수 있다): {rel(log_path)}")
    return 0 if pytest_rc == 0 else 1


def do_commit(args) -> int:
    print(installed_commit())
    return 0


COMMANDS = {"build": do_build, "check": do_check, "link-tools": do_link_tools, "validate": do_validate, "query": do_query,
            "release": do_release, "selftest": do_selftest, "commit": do_commit}


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):    # cp949 콘솔·파이프에서도 출력 문자 때문에 죽지 않게 (cli.main 과 같은 처리)
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print(f"[NG] 사용법: bat_helper.py <{'|'.join(COMMANDS)}> [인자 …]")
        return 2
    try:
        return COMMANDS[argv[0]](argv[1:])
    except Stop as e:
        print(f"[NG] {e}")
        return 2
    except config.ConfigError as e:
        print(f"[NG] 설정 오류: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
