from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

from reportgen import __version__, analyze, build, capture, doctor, lint, onboarding, overlap, project, settings, style, workflows, writer
from reportgen.document import load_sections
from reportgen.llm import LLM, LLMError
from reportgen.readers import prose_paragraphs, read_paragraphs


def _reference(args) -> Path | None:
    candidate = getattr(args, "reference", None) or os.environ.get("REPORTGEN_REFERENCE")
    if candidate:
        return Path(candidate)
    default = settings.home() / "reference"
    return default if default.is_dir() else None


def cmd_start(args) -> int:
    onboarding.run()
    return 0


def cmd_doctor(args) -> int:
    failed = 0
    for name, ok, hint in doctor.checks():
        print(f"[{'+' if ok else '-'}] {name}" + (f"  ({hint})" if not ok and hint else ""))
        failed += not ok
    return 1 if failed and args.strict else 0


def cmd_models(args) -> int:
    provider = settings.get_provider(args.provider)
    print(f"Провайдер: {provider.name} — {provider.description}\nАдрес: {provider.base_url}")
    for role, models in provider.roles.items():
        print(f"  {role:9} {' → '.join(models)}")
    if args.check:
        print("\nПроверка доступности:")
        for role, model, ok, info in LLM(provider).check():
            print(f"  [{'+' if ok else '-'}] {role:9} {model}  {'' if ok else info}")
    return 0


def cmd_use(args) -> int:
    settings.set_default_provider(args.provider)
    print(f"Провайдер по умолчанию: {args.provider}")
    return 0


def cmd_init(args) -> int:
    path = project.init(Path(args.directory), args.type, args.title or "")
    print(f"Создана работа: {path}\nЗаполните meta.yaml и brief.md, затем: report-gen make {path} --code <папка проекта>")
    return 0


def cmd_style(args) -> int:
    if args.action == "learn":
        profile = style.learn(Path(args.path))
        print(f"Документов: {len(profile['documents'])}, абзацев: {profile['paragraphs']}, "
              f"средняя длина предложения: {profile['avg_sentence_words']} слов")
    else:
        profile = style.load()
        print(yaml.safe_dump(profile, allow_unicode=True) if profile else "Профиль стиля ещё не создан: report-gen style learn <папка>")
    return 0


def cmd_analyze(args) -> int:
    print(analyze.summary_text(analyze.analyze(Path(args.code))))
    return 0


def cmd_shots(args) -> int:
    for item in capture.run(Path(args.project)):
        print(f"[{'+' if item['ok'] else '-'}] {item['file']}" + ("" if item["ok"] else f"  {item.get('error', '')}"))
    return 0


def _structure(args, kind: str) -> dict:
    proj = Path(args.project)
    custom = proj / "structure.yaml"
    return writer.load_structure(kind, custom)


def cmd_write(args) -> int:
    proj = Path(args.project)
    code = Path(args.code) if args.code else None
    ctx = writer.build_context(proj, code)
    writer.write_all(LLM(), _structure(args, "coursework"), ctx, _reference(args), args.section, args.force)
    return 0


def cmd_lab(args) -> int:
    proj = Path(args.project)
    task = workflows.read_task(Path(args.task))
    ctx = writer.build_context(proj, Path(args.code) if args.code else None, task)
    writer.write_all(LLM(), writer.load_structure("lab"), ctx, _reference(args), args.section, args.force)
    return 0


def cmd_from_sample(args) -> int:
    proj = Path(args.project)
    structure = workflows.structure_from_sample(Path(args.sample))
    target = workflows.save_structure(structure, proj)
    print(f"Структура извлечена: {len(structure['sections'])} разделов → {target}")
    return 0


def cmd_lint(args) -> int:
    if args.docx:
        issues = lint.audit_docx(Path(args.docx))
    else:
        issues = lint.check_blocks(load_sections(Path(args.project) / "content"))
    for issue in issues:
        print(issue)
    errors = sum(i.level == "error" for i in issues)
    print(f"\nОшибок: {errors}, предупреждений: {len(issues) - errors}")
    return 1 if errors else 0


def cmd_overlap(args) -> int:
    reference = _reference(args)
    if not reference:
        print("Укажите эталонные работы: --reference <папка>")
        return 2
    target = Path(args.target)
    paragraphs = [p for _, p in prose_paragraphs(target, min_chars=60)] if target.is_dir() else read_paragraphs(target)
    matches = overlap.scan(paragraphs, reference, args.threshold)
    for match in matches:
        print(f"{match.score:.0%}  {match.source}\n    {match.text[:160]}…")
    print(f"\nСовпадающих абзацев: {len(matches)}. Общая доля совпавших фрагментов: {overlap.overall(paragraphs, reference):.1%}")
    return 1 if matches else 0


def cmd_fix(args) -> int:
    source = Path(args.file)
    output = Path(args.output) if args.output else source.with_name(f"{source.stem}.fixed.docx")
    needs_llm = args.remarks or _reference(args)
    report = workflows.fix_report(LLM() if needs_llm else None, source, output, _reference(args), Path(args.remarks) if args.remarks else None)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    print(f"Результат: {output}")
    return 0


def cmd_build(args) -> int:
    formats = tuple(f.strip() for f in args.formats.split(","))
    for fmt, path in build.build(Path(args.project), formats).items():
        print(f"{fmt:5} {path}")
    return 0


def cmd_make(args) -> int:
    proj = Path(args.project)
    screens = proj / "screens.yaml"
    if screens.is_file() and (yaml.safe_load(screens.read_text(encoding="utf-8")) or {}).get("items"):
        print("Скриншоты:")
        cmd_shots(args)
    print("Текст:")
    cmd_write(args)
    print("Проверка:")
    cmd_lint(argparse.Namespace(docx=None, project=args.project))
    print("Сборка:")
    return cmd_build(argparse.Namespace(project=args.project, formats=args.formats))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="report-gen", description="Генератор записок и отчётов по СТП БГУИР")
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command")

    def add(name: str, func, help_text: str):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        return p

    add("start", cmd_start, "Знакомство с программой и первая настройка")
    p = add("doctor", cmd_doctor, "Проверить окружение")
    p.add_argument("--strict", action="store_true")
    p = add("models", cmd_models, "Показать модели по ролям")
    p.add_argument("--provider")
    p.add_argument("--check", action="store_true", help="проверить доступность моделей")
    p = add("use", cmd_use, "Переключить провайдера: cloud, local или custom")
    p.add_argument("provider")
    p = add("init", cmd_init, "Создать папку работы")
    p.add_argument("directory")
    p.add_argument("--type", choices=["coursework", "lab"], default="coursework")
    p.add_argument("--title")
    p = add("style", cmd_style, "Профиль стиля по вашим работам")
    p.add_argument("action", choices=["learn", "show"])
    p.add_argument("path", nargs="?")
    p = add("analyze", cmd_analyze, "Разобрать код проекта")
    p.add_argument("code")
    p = add("shots", cmd_shots, "Снять скриншоты по screens.yaml")
    p.add_argument("project")

    for name, func, text in (("write", cmd_write, "Написать разделы курсовой"), ("lab", cmd_lab, "Написать отчёт по заданию лабораторной")):
        p = add(name, func, text)
        p.add_argument("project")
        p.add_argument("--code")
        p.add_argument("--section")
        p.add_argument("--force", action="store_true")
        p.add_argument("--reference")
        if name == "lab":
            p.add_argument("--task", required=True, help="файл задания: docx, pdf, tex, md, txt")

    p = add("from-sample", cmd_from_sample, "Взять структуру из образца отчёта")
    p.add_argument("project")
    p.add_argument("--sample", required=True)
    p = add("lint", cmd_lint, "Проверить соответствие СТП")
    p.add_argument("project", nargs="?")
    p.add_argument("--docx")
    p = add("overlap", cmd_overlap, "Найти совпадения с эталонными работами")
    p.add_argument("target")
    p.add_argument("--reference")
    p.add_argument("--threshold", type=float, default=0.25)
    p = add("fix", cmd_fix, "Исправить готовый DOCX")
    p.add_argument("file")
    p.add_argument("--output")
    p.add_argument("--remarks")
    p.add_argument("--reference")
    p = add("build", cmd_build, "Собрать DOCX, TEX и PDF")
    p.add_argument("project")
    p.add_argument("--formats", default="docx,tex,pdf")
    p = add("make", cmd_make, "Скриншоты, текст, проверка и сборка за один запуск")
    p.add_argument("project")
    p.add_argument("--code")
    p.add_argument("--section")
    p.add_argument("--force", action="store_true")
    p.add_argument("--reference")
    p.add_argument("--formats", default="docx,tex,pdf")
    return root


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    settings.load_env()
    args = parser().parse_args(argv)
    if not args.command:
        if onboarding.is_first_run():
            onboarding.run()
            return 0
        parser().print_help()
        return 0
    if onboarding.is_first_run() and args.command not in {"start", "doctor"} and sys.stdin.isatty():
        onboarding.run()
    try:
        return args.func(args)
    except (LLMError, build.BuildError, capture.CaptureError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
