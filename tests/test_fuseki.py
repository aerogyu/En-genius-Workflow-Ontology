"""V10 Fuseki = rdflib — 예시 2개의 작성·파생 그래프를 named graph 로 올리고, q01~q06 을 FROM 으로 물어 rdflib 결과와 행 단위 비교.

Fuseki 를 메모리 데이터셋(--mem, 127.0.0.1)으로 잠깐 띄운다 (테스트에서만 — 빌드 런타임은 네트워크를 쓰지 않는다).
Java·Fuseki 가 없으면 skip (FUSEKI_HOME/JAVA_HOME, 없으면 개발 PC 배치).
"""

from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.parse
import urllib.request

import pytest

from engenius_wf.query import query_files, run_local, short, union_graph, with_from
from wfhelp import find_jena

pytestmark = pytest.mark.fuseki

LOCAL = [f"q0{i}" for i in range(1, 7)]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def fuseki():
    t = find_jena()
    if not t:
        pytest.skip("Java·Fuseki 없음 (FUSEKI_HOME/JAVA_HOME 설정 시 실행)")
    java, jar = t
    port = _free_port()
    proc = subprocess.Popen([java, "-jar", str(jar), "--mem", "--update", "--localhost", "--ping", "--port", str(port), "/wf"],
                            cwd=jar.parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(base + "/$/ping", timeout=2)
                break
            except OSError:
                if proc.poll() is not None:
                    pytest.fail(f"Fuseki 가 바로 끝났다 (rc {proc.returncode})")
                time.sleep(0.5)
        else:
            pytest.fail("Fuseki 가 60초 안에 뜨지 않았다")
        yield base
    finally:
        proc.terminate()                    # (Windows 에서 os.kill(pid, 0) 은 프로세스를 죽인다 — 상태 확인에 쓰지 않는다)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def _put(base, graph, data: bytes):
    req = urllib.request.Request(f"{base}/wf/data?graph={urllib.parse.quote(graph, safe='')}", data=data, method="PUT",
                                 headers={"Content-Type": "text/turtle; charset=utf-8"})
    urllib.request.urlopen(req, timeout=30)


def _select(base, text):
    body = urllib.parse.urlencode({"query": text}).encode()
    req = urllib.request.Request(f"{base}/wf/sparql", data=body, headers={"Accept": "application/sparql-results+json",
                                                                         "Content-Type": "application/x-www-form-urlencoded"})
    js = json.loads(urllib.request.urlopen(req, timeout=30).read())
    names = js["head"]["vars"]
    return sorted(tuple(short(b.get(v, {}).get("value")) for v in names) for b in js["results"]["bindings"])


@pytest.mark.parametrize("name", ["short", "textbook_nocat"])
def test_fuseki_equals_rdflib(built, fuseki, name):
    out = built[name].out
    ga, gd = f"http://en-genius.local/graph/{name}/workflow", f"http://en-genius.local/graph/{name}/workflow-derived"
    _put(fuseki, ga, (out / "workflow.ttl").read_bytes())
    _put(fuseki, gd, (out / "workflow_derived.ttl").read_bytes())
    g = union_graph(out)
    for q in LOCAL:
        text = query_files()[q].read_text(encoding="utf-8")
        _, local = run_local(g, text)
        assert _select(fuseki, with_from(text, [ga, gd])) == local, q
