\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{bsuir_stp}[2026/03/01 BSUIR STP 01-2022 Class]

% Наследуемся от базового класса report
\LoadClass[14pt,a4paper,oneside]{report}

% --- Поля страницы по СТП (п. 3.1.2.2) ---
\RequirePackage[left=30mm,right=10mm,top=20mm,bottom=20mm]{geometry}

% --- Язык и шрифты ---
\RequirePackage[T2A]{fontenc}
\RequirePackage[utf8]{inputenc}
\RequirePackage[english,russian]{babel}
\RequirePackage{tempora} % Аналог Times New Roman

% --- Интервалы ---
\RequirePackage[nodisplayskipstretch]{setspace}
\onehalfspacing % Полуторный интервал (п. 3.1.2.3)
\RequirePackage{indentfirst} % Абзацный отступ в первом параграфе
\setlength{\parindent}{12.5mm} % Величина отступа (п. 3.1.2.5)

% --- Заголовки (п. 3.1.3) ---
\RequirePackage{titlesec}
\RequirePackage{tocloft}

% Настройка заголовков глав (SECTION в терминах СТП)
\titleformat{\chapter}[display]
    {\filcenter\bfseries\hyphenpenalty=10000}
    {\MakeUppercase{\chaptertitlename}\ \thechapter}
    {8pt}
    {\MakeUppercase}
\titlespacing*{\chapter}{0pt}{-20pt}{15pt}

% Настройка подразделов
\titleformat{\section}
    {\normalsize\bfseries}
    {\thesection}
    {1em}
    {}
\titlespacing*{\section}{\parindent}{15pt}{15pt}

% --- Таблицы и подписи ---
\RequirePackage{caption}
\DeclareCaptionLabelFormat{tablelabel}{Таблица #2}
\captionsetup[table]{labelsep=endash, justification=raggedright, singlelinecheck=off, labelformat=tablelabel}
\captionsetup[figure]{labelsep=endash, justification=centering, name={Рисунок}}

% --- Нумерация страниц (п. 3.1.2.7) ---
\RequirePackage{fancyhdr}
\fancypagestyle{plain}{
    \fancyhf{}
    \fancyhead[R]{\thepage} % Номер страницы справа сверху
    \renewcommand{\headrulewidth}{0pt}
}
\pagestyle{plain}

% --- Содержание ---
\renewcommand{\cftchapfont}{\normalfont}
\renewcommand{\cftchappagefont}{\normalfont}
\renewcommand{\cftchapleader}{\cftdotfill{\cftdotsep}}

% --- Списки (п. 3.1.5) ---
\RequirePackage{enumitem}
\setlist[itemize]{leftmargin=\parindent, label=--, nosep}
\setlist[enumerate]{leftmargin=\parindent, nosep}

% --- Математика ---
\RequirePackage{amsmath, amsfonts, amssymb}

\endinput