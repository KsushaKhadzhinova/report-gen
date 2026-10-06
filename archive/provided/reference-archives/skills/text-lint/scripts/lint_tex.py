#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автопроверка текста пояснительной записки (.tex) на правила оформления и стиля.

    lint_tex.py <файл или папка> [...] [--allow-orm] [--quiet-review]

Вывод: «файл:строка: [УРОВЕНЬ ПРАВИЛО] пояснение | фрагмент».
  ОШИБКА  -- нарушение, которое нужно исправить (код возврата 1);
  ПРОВЕРЬ -- место, где решение принимает человек (на код возврата не влияет).
В конце печатается сводка и частоты слов-тиков.

Файлы только читаются. Строки-комментарии и листинги пропускаются.
"""
import re
import sys
from pathlib import Path

CYR = 'а-яёА-ЯЁ'
W = rf'(?<![{CYR}A-Za-z])'      # граница слова слева
E = rf'(?![{CYR}A-Za-z])'       # граница слова справа

CLICHES = [
    'таким образом', 'необходимо отметить', 'стоит подчеркнуть', 'следует сказать',
    'следует отметить', 'важно понимать', 'не является исключением',
    'играет важную роль', 'играет ключевую роль', 'занимает особое место',
    'занимает важное место', 'на сегодняшний день', 'в современных условиях',
    'в заключение можно сказать', 'подводя итог', 'вышеупомянут',
]
TICS = {'являться': r'явля[ею]тся', 'позволяет': r'позволя[ею]т',
        'представляет собой': r'представля[ею]т собой', 'данный': r'данн(?:ый|ая|ое|ого|ой|ому|ую)'}       # формы «данных/данные/данным» -- это существительное

SKIP_ENV = ('lstlisting', 'verbatim')
FLOAT_ENV = ('table', 'tabular', 'longtable', 'figure', 'equation', 'align', 'explanation')


def strip_comment(line):
    out, i = [], 0
    while i < len(line):
        ch = line[i]
        if ch == '\\' and i + 1 < len(line):
            out.append(line[i:i + 2]); i += 2; continue
        if ch == '%':
            break
        out.append(ch); i += 1
    return ''.join(out)


def collect(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(p.rglob('*.tex'))
        elif p.suffix == '.tex':
            files.append(p)
    return files


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    allow_orm = '--allow-orm' in sys.argv
    quiet_review = '--quiet-review' in sys.argv
    if not args:
        sys.exit(__doc__)
    files = collect(args)
    if not files:
        sys.exit('не найдено ни одного .tex файла')

    errors = reviews = 0
    tic_count = {k: 0 for k in TICS}
    words_total = 0

    def report(f, n, level, rule, msg, frag):
        nonlocal errors, reviews
        if level == 'ОШИБКА':
            errors += 1
        else:
            reviews += 1
            if quiet_review:
                return
        frag = frag.strip()
        if len(frag) > 90:
            frag = frag[:87] + '...'
        print(f'{f}:{n}: [{level} {rule}] {msg} | {frag}')

    for f in files:
        name = f.name.lower()
        is_refs = 'reference' in name
        is_conclusion = 'conclusion' in name
        is_frontmatter = name in ('title.tex', 'task.tex', 'preamble.tex', 'macros.tex',
                                  'table_of_contents.tex', 'fonts_linux.tex')
        if is_frontmatter:
            continue
        lines = f.read_text(encoding='utf-8', errors='replace').splitlines()
        env_stack, in_center = [], False
        para, para_start = [], 0

        def flush_para():
            nonlocal para
            if not para or is_refs:
                para = []
                return
            text = ' '.join(para)
            cites = list(re.finditer(r'\[\d+(?:\s*[,–-]\s*\d+)*\]', text))
            if cites:
                if len(cites) > 2:
                    report(f, para_start, 'ОШИБКА', 'ССЫЛКИ', 'в абзаце больше двух ссылок на источники', text)
                tail = text[cites[-1].end():].strip(' .~')
                not_at_end = [c for c in cites[:-1]
                              if text[c.end():cites[cites.index(c) + 1].start()].strip(' ,;~')]
                if tail or not_at_end:
                    report(f, para_start, 'ПРОВЕРЬ', 'ССЫЛКИ', 'ссылка на источник не в конце абзаца', text[max(0, cites[0].start() - 40):])
            para = []

        for n, raw in enumerate(lines, 1):
            line = strip_comment(raw)
            for m in re.finditer(r'\\(begin|end)\{(\w+)\*?\}', line):
                kind, env = m.groups()
                if kind == 'begin':
                    env_stack.append(env)
                    in_center = in_center or env == 'center'
                elif env_stack and env in env_stack:
                    while env_stack and env_stack.pop() != env:
                        pass
                    in_center = 'center' in env_stack
            if any(e in SKIP_ENV for e in env_stack) or '\\lstinputlisting' in line:
                continue
            if not line.strip():
                flush_para()
                continue
            in_float = any(e in FLOAT_ENV for e in env_stack)
            if not in_float and not line.lstrip().startswith('\\'):
                if not para:
                    para_start = n
                para.append(line.strip())

            low = line.lower()
            unquoted = re.sub(r'«[^»]*»', '«»', low)
            words_total += len(re.findall(rf'[{CYR}]+', line))

            if '---' in line:
                report(f, n, 'ОШИБКА', 'ТИРЕ', 'длинное тире «---»: нужно короткое «--»', line)
            if '—' in line:
                report(f, n, 'ОШИБКА', 'ТИРЕ', 'символ длинного тире: нужно «--»', line)
            if '\\textbf' in line and not in_center and not re.search(r'\\(sub)*section', line):
                report(f, n, 'ОШИБКА', 'ЖИРНЫЙ', 'жирное выделение в тексте или таблице', line)
            if re.match(rf'\s*(\\item\s*)?[а-е]\)\s', line):
                report(f, n, 'ОШИБКА', 'ПЕРЕЧЕНЬ', 'перечисление «а)», «б)»: нужно тире или нумерация', line)
            if not is_refs and re.search(rf'{W}(?:1|[MМNmn])\s*:\s*(?:1|[MМNmn]){E}', line) \
                    and 'caption' not in line and 'figure' not in env_stack:
                report(f, n, 'ОШИБКА', 'СВЯЗЬ', 'мощность связи символами: в тексте писать словами', line)
            if not allow_orm and re.search(rf'{W}(ORM|SQLAlchemy|Hibernate|Django ORM|объектно-реляционн\w*){E}', line, re.I):
                report(f, n, 'ОШИБКА', 'ORM', 'упоминание ORM: описывать работу через SQL', line)
            for c in CLICHES:
                if c in low:
                    report(f, n, 'ОШИБКА', 'ШТАМП', f'оборот «{c}»', line)
            if re.search(rf'{W}также{E}', low):
                report(f, n, 'ПРОВЕРЬ', 'ТАКЖЕ', '«также»: убрать, если это связка между предложениями', line)
            if not is_refs and re.search(rf'{W}(я|мы|нас|нам|нами|наш(?:а|е|и|у|его|ей|ему|им|ими|их|ем)?|мой|моя|моё|мои){E}', unquoted):
                report(f, n, 'ОШИБКА', 'ЛИЦО', 'личное местоимение: писать безлично', line)
            if not is_refs and re.search(rf'{W}(он|она|они){E}', unquoted):
                report(f, n, 'ПРОВЕРЬ', 'ЛИЦО', 'местоимение третьего лица: заменить существительным, если речь о человеке', line)
            if is_conclusion and re.search(rf'{W}(был|была|было|были){E}', low):
                report(f, n, 'ОШИБКА', 'ВРЕМЯ', 'заключение пишется в настоящем времени, без «был/была/было»', line)
            if '"' in line.replace('\\"', '') or '“' in line or '”' in line:
                report(f, n, 'ПРОВЕРЬ', 'КАВЫЧКИ', 'прямые или английские кавычки: в тексте нужны «ёлочки»', line)
            if not in_float and not is_refs and not re.search(r'\\(caption|label|includegraphics|item\s*\[|hline|setlength|input)', line) \
                    and '&' not in line:
                bare = re.sub(r'\\(ref|cite|label|pageref)\{[^}]*\}', '', line)
                bare = re.sub(r'\[\d+(?:\s*[,–-]\s*\d+)*\]', '', bare)
                for m in re.finditer(r'(?<![\w.,/:\\{}\[\]~^_=+-])[1-9](?![\w.,:/%)}\]^_=+\\-])', bare):
                    after = bare[m.end():m.end() + 14]
                    if re.match(r'[~\s]*(?:(?:пт|мм|см|с|мс|мин|ч|ГБ|МБ|КБ|Гц|%|\\%)(?![а-яё])|(?:секунд|минут|час|сут|дн|день|дня|недел|месяц|лет|год|рубл|байт|пиксел|пункт)[а-яё]*)', after):
                        continue
                    report(f, n, 'ПРОВЕРЬ', 'ЧИСЛО', f'число «{m.group()}»: от одного до девяти без единиц измерения пишется словами', bare[max(0, m.start() - 35):m.end() + 35])
            for k, pat in TICS.items():
                tic_count[k] += len(re.findall(rf'{W}{pat}{E}', low))
        flush_para()

    pages = max(words_total / 300, 1)            # около 300 слов на страницу 14 пт
    print('\n--- сводка ---')
    print(f'файлов: {len(files)}, ошибок: {errors}, мест для ручной проверки: {reviews}')
    print(f'объём текста: около {pages:.0f} стр.')
    for k, v in tic_count.items():
        per10 = v / pages * 10
        mark = '  <- много, заменить часть' if per10 > 4 else ''
        print(f'  «{k}»: {v} (на 10 стр.: {per10:.1f}){mark}')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
