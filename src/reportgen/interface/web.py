from __future__ import annotations

import contextlib
import hmac
import io
import json
import os
import re
import secrets
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from reportgen.domain.personal import PersonalProfile
from reportgen.infrastructure import settings
from reportgen.infrastructure.profile_vault import LocalProfileStore
from reportgen.infrastructure.settings import read_data
from reportgen.interface import cli

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PROJECTS_ENV = "REPORTGEN_PROJECTS"
DEFAULT_PROJECTS_DIR = "projects"
SAFE_NAME_RE = re.compile(r"^[\w][\w .\-]{0,63}$", re.UNICODE)
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
DOWNLOADS = {"docx": "note.docx", "pdf": "note.pdf", "tex": "tex/note.tex"}
MAX_BODY_BYTES = 64 * 1024
PROVIDERS = {"cloud", "gemini", "local", "custom"}
JOB_OUTPUT_LIMIT = 60_000


def hostname(header: str) -> str:
    """Имя узла из заголовка Host без порта; защита от подмены адреса (DNS rebinding)."""
    if header.startswith("["):
        return header.split("]")[0] + "]"
    return header.rsplit(":", 1)[0] if ":" in header else header


def projects_root() -> Path:
    root = Path(os.environ.get(PROJECTS_ENV, DEFAULT_PROJECTS_DIR)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_project(name: str) -> Path | None:
    """Папка работы внутри каталога проектов или None, если имя недопустимо."""
    if not SAFE_NAME_RE.match(name or ""):
        return None
    root = projects_root()
    path = (root / name).resolve()
    return path if path.is_relative_to(root) else None


def list_projects() -> list[dict]:
    root = projects_root()
    entries = []
    for path in sorted(p for p in root.iterdir() if p.is_dir() and SAFE_NAME_RE.match(p.name)):
        files = [kind for kind, relative in DOWNLOADS.items() if (path / "output" / relative).is_file()]
        entries.append({"name": path.name, "files": files})
    return entries


def key_status() -> list[dict]:
    providers = settings.load_models_config()["providers"]
    return [
        {"provider": name, "set": bool(settings.get_provider(name).api_key)}
        for name, raw in providers.items()
        if raw.get("api_key_env")
    ]


def build_arguments(request: dict) -> list[str] | None:
    """Строит аргументы CLI только для разрешённых действий; произвольные команды отсюда не выполняются."""
    action = request.get("action")
    project = safe_project(request.get("project", "")) if action in {"shots", "make", "lint", "build"} else None
    code = request.get("code") or ""
    code_args = ["--code", code] if code and Path(code).is_dir() else []
    if action == "init":
        target = safe_project(request.get("name", ""))
        if target is None:
            return None
        kind = "lab" if request.get("type") == "lab" else "coursework"
        title = str(request.get("title", ""))[:200]
        return ["init", str(target), "--type", kind, "--title", title]
    if action in {"shots", "build", "lint"} and project:
        return [action, str(project)]
    if action == "make" and project:
        return ["make", str(project), *code_args]
    if action == "use" and request.get("provider") in PROVIDERS:
        return ["use", request["provider"]]
    if action in {"doctor"}:
        return ["doctor"]
    if action == "models":
        return ["models", "--check"]
    return None


class Job:
    def __init__(self) -> None:
        self.status = "running"
        self.buffer = io.StringIO()

    def snapshot(self) -> dict:
        return {"status": self.status, "output": self.buffer.getvalue()[-JOB_OUTPUT_LIMIT:]}


class JobRunner:
    """Выполняет одну команду за раз; вывод доступен странице по мере выполнения."""

    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def start(self, argv: list[str]) -> str | None:
        with self.lock:
            if any(job.status == "running" for job in self.jobs.values()):
                return None
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = Job()
        threading.Thread(target=self._run, args=(self.jobs[job_id], argv), daemon=True).start()
        return job_id

    def finished(self, message: str) -> str:
        job = Job()
        job.status = "done"
        job.buffer.write(message)
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = job
        return job_id

    @staticmethod
    def _run(job: Job, argv: list[str]) -> None:
        try:
            with contextlib.redirect_stdout(job.buffer), contextlib.redirect_stderr(job.buffer):
                code = cli.main(argv)
            job.status = "done" if code == 0 else "failed"
        except SystemExit as exit_request:
            job.status = "done" if exit_request.code in (0, None) else "failed"
        except Exception as error:  # любая ошибка команды должна дойти до страницы, а не остановить сервер
            job.buffer.write(f"\nОшибка: {error}")
            job.status = "failed"

    def snapshot(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        return job.snapshot() if job else {"status": "failed", "output": "Задача не найдена"}


def make_handler(token: str, runner: JobRunner) -> type[BaseHTTPRequestHandler]:
    page = read_data("ui/index.html").replace("{{TOKEN}}", token)

    class Handler(BaseHTTPRequestHandler):
        server_version = "report-gen"

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            return

        def _host_allowed(self) -> bool:
            return hostname(self.headers.get("Host") or "") in ALLOWED_HOSTS

        def _token_valid(self) -> bool:
            return hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), token)

        def _send(self, status: HTTPStatus, body: bytes, content_type: str, extra: dict | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_allowed():
                return self._json({"error": "Недопустимый адрес"}, HTTPStatus.FORBIDDEN)
            url = urlparse(self.path)
            if url.path == "/":
                return self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
            if url.path == "/download":
                return self._download(parse_qs(url.query))
            if not self._token_valid():
                return self._json({"error": "Нет доступа"}, HTTPStatus.FORBIDDEN)
            if url.path == "/api/state":
                provider = settings.active_provider_name()
                return self._json({"projects": list_projects(), "provider": provider, "keys": key_status()})
            if url.path == "/api/job":
                job_id = parse_qs(url.query).get("id", [""])[0]
                return self._json(runner.snapshot(job_id))
            return self._json({"error": "Не найдено"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_allowed() or not self._token_valid():
                return self._json({"error": "Нет доступа"}, HTTPStatus.FORBIDDEN)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                return self._json({"error": "Слишком большой запрос"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            try:
                request = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "Некорректный запрос"}, HTTPStatus.BAD_REQUEST)
            if self.path != "/api/run":
                return self._json({"error": "Не найдено"}, HTTPStatus.NOT_FOUND)
            if request.get("action") == "profile":
                return self._save_profile(request)
            argv = build_arguments(request)
            if argv is None:
                return self._json({"error": "Выберите работу и проверьте введённые данные"}, HTTPStatus.BAD_REQUEST)
            job_id = runner.start(argv)
            if job_id is None:
                return self._json({"error": "Уже выполняется другая задача"}, HTTPStatus.CONFLICT)
            return self._json({"id": job_id})

        def _save_profile(self, request: dict) -> None:
            fields = {key: str(request.get(key, "")).strip()[:120] for key in ("student", "supervisor", "faculty", "department")}
            LocalProfileStore().save(PersonalProfile(**fields))
            self._json({"id": runner.finished("Данные сохранены на этом компьютере.")})

        def _download(self, query: dict) -> None:
            project = safe_project(query.get("project", [""])[0])
            relative = DOWNLOADS.get(query.get("file", [""])[0])
            target = project / "output" / relative if project and relative else None
            if target is None or not target.is_file():
                return self._json({"error": "Файл не найден"}, HTTPStatus.NOT_FOUND)
            disposition = f'attachment; filename="{target.name}"'
            self._send(HTTPStatus.OK, target.read_bytes(), "application/octet-stream", {"Content-Disposition": disposition})

    return Handler


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    os.environ[cli.NONINTERACTIVE_ENV] = "1"
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((host, port), make_handler(token, JobRunner()))
    print(f"Интерфейс: http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}  (остановить: Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.server_close()
