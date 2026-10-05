from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import yaml

from reportgen import __version__
from reportgen.application.build_report import ALL_FORMATS, EmptyReportError, build_report
from reportgen.application.check_report import check_overlap, lint_report
from reportgen.application.fix_report import ReportFixer
from reportgen.application.learn_style import learn_style
from reportgen.application.write_report import WritingContext
from reportgen.domain.outline import structure_from_outline
from reportgen.domain.personal import PersonalProfile
from reportgen.domain.structure import Structure
from reportgen.infrastructure import settings
from reportgen.infrastructure.code_inspector import ProjectCodeInspector
from reportgen.infrastructure.docx_format import DocxFormatService
from reportgen.infrastructure.file_project import FileProjectRepository
from reportgen.infrastructure.file_stores import FileStyleStore
from reportgen.infrastructure.latex_compiler import LatexError, XelatexCompiler
from reportgen.infrastructure.llm_client import LLMError, OpenAICompatibleModel
from reportgen.infrastructure.outline_reader import read_outline
from reportgen.infrastructure.profile_vault import EXPORT_FILE, LocalProfileStore, export_encrypted, import_encrypted
from reportgen.infrastructure.prompt_library import load_prompt_catalog
from reportgen.infrastructure.readers import DocumentProseSource, read_paragraphs
from reportgen.infrastructure.scaffold import scaffold_project
from reportgen.infrastructure.screen_capture import CaptureError, capture_project
from reportgen.infrastructure.secret_store import KeyringSecretStore, SecretStoreUnavailable, migrate_env_file
from reportgen.infrastructure.settings import read_data
from reportgen.interface import container, doctor, onboarding

EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2
SETUP_COMMANDS = {"start", "doctor"}


def _mark(ok: bool) -> str:
    return "+" if ok else "-"


def _structure(repository: FileProjectRepository, builtin: str) -> Structure:
    custom = repository.custom_structure_path()
    text = custom.read_text(encoding="utf-8") if custom.is_file() else read_data(f"{builtin}.yaml")
    return Structure.from_dict(yaml.safe_load(text))


def _context(repository: FileProjectRepository, code: str | None, task: str = "") -> WritingContext:
    parts = []
    brief = repository.read_brief()
    if brief:
        parts.append("Сведения от автора:\n" + brief)
    if code:
        parts.append("Анализ проекта:\n" + ProjectCodeInspector().summarize(Path(code))[:3000])
    return WritingContext(facts="\n\n".join(parts), task=task)


def cmd_start(args) -> int:
    onboarding.run()
    return EXIT_OK


def cmd_doctor(args) -> int:
    results = doctor.checks()
    for name, ok, hint in results:
        print(f"[{_mark(ok)}] {name}" + (f"  ({hint})" if not ok and hint else ""))
    return EXIT_PROBLEMS if args.strict and not all(ok for _, ok, _ in results) else EXIT_OK


def cmd_models(args) -> int:
    provider = settings.get_provider(args.provider)
    print(f"Провайдер: {provider.name} — {provider.description}\nАдрес: {provider.base_url}")
    for role, models in provider.roles.items():
        print(f"  {role:9} {' → '.join(models)}")
    if args.check:
        print("\nПроверка доступности:")
        for role, model, ok, info in OpenAICompatibleModel(provider).check():
            print(f"  [{_mark(ok)}] {role:9} {model}  {'' if ok else info}")
    return EXIT_OK


def cmd_use(args) -> int:
    settings.set_default_provider(args.provider)
    print(f"Провайдер по умолчанию: {args.provider}")
    return EXIT_OK


def _key_names() -> dict[str, str]:
    """Имена переменных ключей по провайдерам, у которых ключ вообще нужен."""
    providers = settings.load_models_config()["providers"]
    return {name: raw["api_key_env"] for name, raw in providers.items() if raw.get("api_key_env")}


def cmd_key(args) -> int:
    store = KeyringSecretStore()
    if args.action == "import-env":
        names = migrate_env_file(Path.cwd() / settings.ENV_FILE, store)
        print("Перенесено в защищённое хранилище: " + (", ".join(names) if names else "ничего") + ". Значения в .env очищены.")
    elif args.action == "set":
        name = settings.get_provider(args.provider).api_key_env
        if not name:
            print("Этому провайдеру ключ не нужен")
            return EXIT_USAGE
        value = getpass.getpass(f"Ключ {name} (ввод скрыт): ").strip()
        if not value:
            return EXIT_USAGE
        store.set(name, value)
        print(f"Ключ {name} сохранён в защищённом хранилище.")
    elif args.action == "delete":
        store.delete(settings.get_provider(args.provider).api_key_env)
        print("Ключ удалён из хранилища.")
    else:
        for provider, name in _key_names().items():
            print(f"{provider:8} {name:20} {'задан' if settings.get_provider(provider).api_key else 'не задан'}")
    return EXIT_OK


def _saved_profile() -> PersonalProfile | None:
    """Личные данные автора с этого компьютера; без них на титульном листе остаются заглушки."""
    return LocalProfileStore().load()


def _ask_profile() -> PersonalProfile:
    return PersonalProfile(
        student=input("ФИО: ").strip(),
        group=input("Группа: ").strip(),
        supervisor=input("Руководитель: ").strip(),
    )


def cmd_profile(args) -> int:
    store = LocalProfileStore()
    if args.action == "set":
        store.save(_ask_profile())
        print("Данные сохранены на этом компьютере и в git не попадают.")
    elif args.action == "export":
        profile = store.load()
        if profile is None:
            print("Сначала задайте данные: report-gen profile set")
            return EXIT_USAGE
        password = getpass.getpass("Пароль для выгрузки (не короче 8 символов, ввод скрыт): ")
        export_encrypted(profile, password, Path(EXPORT_FILE))
        print(f"Зашифрованная выгрузка: {EXPORT_FILE}")
    elif args.action == "import":
        profile = import_encrypted(Path(EXPORT_FILE), getpass.getpass("Пароль выгрузки (ввод скрыт): "))
        if profile is None:
            print("Не удалось расшифровать выгрузку")
            return EXIT_USAGE
        store.save(profile)
        print("Данные восстановлены.")
    else:
        profile = store.load()
        print("Данные не заданы: report-gen profile set" if profile is None else yaml.safe_dump(profile.to_dict(), allow_unicode=True))
    return EXIT_OK


def cmd_init(args) -> int:
    path = scaffold_project(Path(args.directory), lab=args.type == "lab", title=args.title or "")
    print(f"Создана работа: {path}\nЗаполните meta.yaml и brief.md, затем: report-gen make {path} --code <папка проекта>")
    return EXIT_OK


def cmd_style(args) -> int:
    store = FileStyleStore()
    if args.action == "learn":
        if not args.path:
            print("Укажите папку с вашими работами")
            return EXIT_USAGE
        profile = learn_style(DocumentProseSource(), Path(args.path), store)
        print(f"Документов: {len(profile.documents)}, абзацев: {profile.paragraphs}, средняя длина предложения: {profile.avg_sentence_words} слов")
        return EXIT_OK
    profile = store.load()
    print(yaml.safe_dump(profile.to_dict(), allow_unicode=True) if profile else "Профиль стиля ещё не создан: report-gen style learn <папка>")
    return EXIT_OK


def cmd_analyze(args) -> int:
    print(ProjectCodeInspector().summarize(Path(args.code)))
    return EXIT_OK


def cmd_shots(args) -> int:
    results = capture_project(Path(args.project))
    for result in results:
        print(f"[{_mark(result.ok)}] {result.file}" + ("" if result.ok else f"  {result.error}"))
    return EXIT_OK if all(r.ok for r in results) else EXIT_PROBLEMS


def _write(args, builtin: str, task: str = "") -> int:
    repository = FileProjectRepository(Path(args.project))
    writer = container.report_writer(args.reference)
    writer.write(_structure(repository, builtin), repository, _context(repository, args.code, task), args.section, args.force)
    return EXIT_OK


def cmd_write(args) -> int:
    return _write(args, "coursework")


def cmd_lab(args) -> int:
    task = "\n".join(read_paragraphs(Path(args.task)))[:5000]
    return _write(args, "lab", task)


def cmd_from_sample(args) -> int:
    sample = Path(args.sample)
    structure = structure_from_outline(read_outline(sample))
    container.register_reference(sample)
    target = FileProjectRepository(Path(args.project)).custom_structure_path()
    target.write_text(yaml.safe_dump(structure.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Структура извлечена: {len(structure.sections)} разделов → {target}")
    return EXIT_OK


def cmd_lint(args) -> int:
    if args.docx:
        issues = DocxFormatService().audit(Path(args.docx))
    else:
        issues = lint_report(FileProjectRepository(Path(args.project)))
    for issue in issues:
        print(issue)
    errors = sum(issue.is_error for issue in issues)
    print(f"\nОшибок: {errors}, предупреждений: {len(issues) - errors}")
    return EXIT_PROBLEMS if errors else EXIT_OK


def cmd_overlap(args) -> int:
    library = container.reference_library(args.reference)
    if library is None:
        print("Укажите эталонные работы: --reference <папка>")
        return EXIT_USAGE
    target = Path(args.target)
    paragraphs = [text for _, text in DocumentProseSource(60).paragraphs(target)] if target.is_dir() else read_paragraphs(target)
    report = check_overlap(paragraphs, library, args.threshold)
    for match in report.matches:
        print(f"{match.score:.0%}  {match.source}\n    {match.text[:160]}…")
    print(f"\nСовпадающих абзацев: {len(report.matches)}. Общая доля совпавших фрагментов: {report.share:.1%}")
    return EXIT_PROBLEMS if report.matches else EXIT_OK


def cmd_fix(args) -> int:
    source = Path(args.file)
    output = Path(args.output) if args.output else source.with_name(f"{source.stem}.fixed.docx")
    library = container.reference_library(args.reference) if args.reference else None
    remarks = Path(args.remarks).read_text(encoding="utf-8") if args.remarks else ""
    model = OpenAICompatibleModel() if (library or remarks) else None
    result = ReportFixer(DocxFormatService(), load_prompt_catalog(), model, FileStyleStore(), library).fix(source, output, remarks)
    if result.review:
        output.with_suffix(".review.md").write_text(result.review, encoding="utf-8")
    summary = {k: v for k, v in result.__dict__.items() if k != "review"}
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
    print(f"Результат: {output}")
    return EXIT_OK


def cmd_build(args) -> int:
    formats = tuple(f.strip() for f in args.formats.split(","))
    repository = FileProjectRepository(Path(args.project))
    profile = _saved_profile()
    for fmt, path in build_report(repository, container.renderers(), XelatexCompiler(), formats, profile).items():
        print(f"{fmt:5} {path}")
    return EXIT_OK


def cmd_make(args) -> int:
    screens = Path(args.project) / "screens.yaml"
    if screens.is_file() and (yaml.safe_load(screens.read_text(encoding="utf-8")) or {}).get("items"):
        print("Скриншоты:")
        cmd_shots(args)
    print("Текст:")
    cmd_write(args)
    print("Проверка:")
    cmd_lint(argparse.Namespace(docx=None, project=args.project))
    print("Сборка:")
    return cmd_build(argparse.Namespace(project=args.project, formats=args.formats))


def _add_work_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project")
    parser.add_argument("--code")
    parser.add_argument("--section")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reference")


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="report-gen", description="Генератор записок и отчётов по СТП БГУИР")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command")

    def add(name: str, handler, help_text: str) -> argparse.ArgumentParser:
        parser = commands.add_parser(name, help=help_text)
        parser.set_defaults(handler=handler)
        return parser

    add("start", cmd_start, "Знакомство с программой и первая настройка")
    add("doctor", cmd_doctor, "Проверить окружение").add_argument("--strict", action="store_true")
    models = add("models", cmd_models, "Показать модели по ролям")
    models.add_argument("--provider")
    models.add_argument("--check", action="store_true", help="проверить доступность моделей")
    add("use", cmd_use, "Переключить провайдера: cloud, local или custom").add_argument("provider")
    key = add("key", cmd_key, "Ключи доступа: хранятся зашифрованными в хранилище системы")
    key.add_argument("action", choices=["import-env", "set", "status", "delete"])
    key.add_argument("provider", nargs="?")
    profile = add("profile", cmd_profile, "Личные данные для титульного листа (хранятся только на этом компьютере)")
    profile.add_argument("action", choices=["set", "show", "export", "import"])
    init = add("init", cmd_init, "Создать папку работы")
    init.add_argument("directory")
    init.add_argument("--type", choices=["coursework", "lab"], default="coursework")
    init.add_argument("--title")
    style = add("style", cmd_style, "Профиль стиля по вашим работам")
    style.add_argument("action", choices=["learn", "show"])
    style.add_argument("path", nargs="?")
    add("analyze", cmd_analyze, "Разобрать код проекта").add_argument("code")
    add("shots", cmd_shots, "Снять скриншоты по screens.yaml").add_argument("project")
    _add_work_options(add("write", cmd_write, "Написать разделы курсовой"))
    lab = add("lab", cmd_lab, "Написать отчёт по заданию лабораторной")
    _add_work_options(lab)
    lab.add_argument("--task", required=True, help="файл задания: docx, pdf, tex, md, txt")
    sample = add("from-sample", cmd_from_sample, "Взять структуру из образца отчёта")
    sample.add_argument("project")
    sample.add_argument("--sample", required=True)
    lint = add("lint", cmd_lint, "Проверить соответствие СТП")
    lint.add_argument("project", nargs="?")
    lint.add_argument("--docx")
    overlap = add("overlap", cmd_overlap, "Найти совпадения с эталонными работами")
    overlap.add_argument("target")
    overlap.add_argument("--reference")
    overlap.add_argument("--threshold", type=float, default=0.25)
    fix = add("fix", cmd_fix, "Исправить готовый DOCX")
    fix.add_argument("file")
    fix.add_argument("--output")
    fix.add_argument("--remarks")
    fix.add_argument("--reference")
    build = add("build", cmd_build, "Собрать DOCX, TEX и PDF")
    build.add_argument("project")
    build.add_argument("--formats", default=",".join(ALL_FORMATS))
    make = add("make", cmd_make, "Скриншоты, текст, проверка и сборка за один запуск")
    _add_work_options(make)
    make.add_argument("--formats", default=",".join(ALL_FORMATS))
    return root


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    settings.load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    interactive = sys.stdin.isatty()
    if not args.command:
        if onboarding.is_first_run():
            onboarding.run()
        else:
            parser.print_help()
        return EXIT_OK
    if interactive and onboarding.is_first_run() and args.command not in SETUP_COMMANDS:
        onboarding.run()
    try:
        return args.handler(args)
    except (LLMError, LatexError, CaptureError, EmptyReportError, FileNotFoundError, ValueError, SecretStoreUnavailable) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_PROBLEMS
