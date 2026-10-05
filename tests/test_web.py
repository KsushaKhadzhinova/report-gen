import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from reportgen.interface import cli, web

TOKEN = "test-token"


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv(web.PROJECTS_ENV, str(tmp_path / "projects"))
    monkeypatch.setenv("REPORTGEN_HOME", str(tmp_path / "home"))
    monkeypatch.setenv(cli.NONINTERACTIVE_ENV, "1")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(TOKEN, web.JobRunner()))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def call(base, path, body=None, token=TOKEN, host=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-CSRF-Token"] = token
    if host:
        headers["Host"] = host
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(base + path, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def test_page_is_served_with_a_token(server):
    status, body = call(server, "/", token=None)
    assert status == 200 and TOKEN in body.decode("utf-8")


def test_actions_require_the_csrf_token(server):
    assert call(server, "/api/run", {"action": "doctor"}, token=None)[0] == 403
    assert call(server, "/api/run", {"action": "doctor"}, token="wrong")[0] == 403
    assert call(server, "/api/state", token=None)[0] == 403


def test_foreign_host_header_is_rejected(server):
    assert call(server, "/api/state", host="evil.example")[0] == 403
    assert call(server, "/", token=None, host="evil.example:8765")[0] == 403


def test_unknown_actions_and_unsafe_names_are_refused(server):
    assert call(server, "/api/run", {"action": "rm -rf"})[0] == 400
    assert call(server, "/api/run", {"action": "init", "name": "../escape", "title": "x"})[0] == 400
    assert call(server, "/api/run", {"action": "build", "project": "../../etc"})[0] == 400


def test_create_project_button_runs_the_real_command(server, tmp_path):
    status, body = call(server, "/api/run", {"action": "init", "name": "kursach", "title": "Тема", "type": "coursework"})
    assert status == 200
    job_id = json.loads(body)["id"]
    for _ in range(50):
        job = json.loads(call(server, f"/api/job?id={job_id}")[1])
        if job["status"] != "running":
            break
        time.sleep(0.1)
    assert job["status"] == "done"
    assert (tmp_path / "projects" / "kursach" / "meta.yaml").is_file()
    state = json.loads(call(server, "/api/state")[1])
    assert [p["name"] for p in state["projects"]] == ["kursach"]
    assert all(set(key) == {"provider", "set"} for key in state["keys"])


def test_download_is_limited_to_known_output_files(server, tmp_path):
    output = tmp_path / "projects" / "kursach" / "output"
    output.mkdir(parents=True)
    (output / "note.docx").write_bytes(b"docx")
    (tmp_path / "projects" / "secret.txt").write_text("secret", encoding="utf-8")
    assert call(server, "/download?project=kursach&file=docx", token=None) == (200, b"docx")
    assert call(server, "/download?project=kursach&file=pdf", token=None)[0] == 404
    assert call(server, "/download?project=..&file=docx", token=None)[0] == 404
    assert call(server, "/download?project=kursach&file=../../secret.txt", token=None)[0] == 404


def test_hostname_parsing():
    assert web.hostname("localhost:8765") == "localhost"
    assert web.hostname("127.0.0.1") == "127.0.0.1"
    assert web.hostname("[::1]:8765") == "[::1]"
