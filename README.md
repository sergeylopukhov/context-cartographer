<div align="center">

![Context Cartographer cover](assets/context-cartographer-cover.png)

# Context Cartographer

**Project documentation that coding agents can actually navigate.**

Turn an idea into a clear project plan, build a documentation system, or untangle an existing one — without creating a second source of truth.

[English](#english) · [Русский](#russian)

</div>

---

<a id="english"></a>

## English

Context Cartographer is a skill for Codex, Claude Code, Cursor, and other coding agents. It helps the agent understand a project, put durable knowledge in the right files, and return to that context later without rereading the whole repository.

Version **0.4.0** is the current release.

### When to use it

| Your situation | What Context Cartographer does |
| --- | --- |
| You have an idea but no project yet | Clarifies the idea, separates decisions from assumptions, and can carry the agreed scope to a first working slice |
| The project has little or no documentation | Creates a small, connected documentation system based on real repository evidence |
| Documentation has become messy | Finds duplicates, contradictions, broken links, missing owners, and outdated routes |
| A future agent needs only one part of the project | Builds a map and local graph so the agent can open the right section instead of loading everything |

An explicit documentation request always stays a documentation task. For example, asking to review a requirements file will not be replaced by a discussion about developing the product idea.

### What you get

- One clear owner document for each durable topic.
- A short project instruction file that points agents to the right context.
- A documentation map with real links, ownership, and reading conditions.
- Optional project documents for architecture, product, design, deployment, API, security, integrations, administration, content, or code rules — only when the project needs them.
- A private offline HTML graph for browsing documents and their relationships.
- A precise section reader that includes the document preamble and parent headings.
- A resumable decision record for longer idea or planning sessions.
- Checks for broken addresses, duplicate owners, missing routes, stale graphs, and incomplete scans.

Context Cartographer does not invent architecture or silently replace existing rules. Unknown facts remain visibly unresolved, and destructive documentation changes still require authorization.

### How it works

1. The agent finds the actual project root and reads the closest instructions, source files, configuration, and existing docs.
2. Repository facts are separated from choices only you can make.
3. The skill proposes the smallest useful documentation structure or next project step.
4. After approved changes, it checks links, ownership, routing, local-only files, and the documentation graph.

Routine edits remain routine: if the project already names the correct owner file, the agent updates it directly without starting a full documentation audit.

### Install for Codex

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

Restart Codex after installation.

### Start using it

From an idea:

```text
Use $context-cartographer. I want to build a service that reminds a family about recurring home tasks. Help me work out the idea first; do not create files yet.
```

For a project without useful docs:

```text
Use $context-cartographer and create a documentation system for this project. Inspect the repository first and do not invent missing facts.
```

For an existing documentation mess:

```text
Use $context-cartographer. Audit the current documentation, show what should stay, move, merge, or be removed, and wait before destructive changes.
```

To inspect the documentation graph:

```text
Use $context-cartographer to check the local documentation graph and explain the problems in plain language.
```

### Files it may create

The exact set follows the project, not a fixed template. A typical documented project contains:

```text
AGENTS.md                         Short routing instructions for later tasks
docs/architecture.md             Map of topics and their owner sections
docs/documentation-rules.md      Rules for keeping docs current
docs/architecture-overview.md    Stack, layout, and entry points
docs/architecture-quality-risks.md
.context-cartographer/documentation-graph.html  Private derived graph
```

Depending on the project and your choices, the root adapter may instead be `CLAUDE.md` or `.cursor/rules/context-cartographer.mdc`, and additional topic files may be added.

<details>
<summary><strong>Install for Claude Code or Cursor</strong></summary>

#### Claude Code

```bash
git clone https://github.com/sergeylopukhov/context-cartographer.git /tmp/context-cartographer
mkdir -p ~/.claude/skills
rsync -a /tmp/context-cartographer/context-cartographer/ ~/.claude/skills/context-cartographer/
```

Optional project pointer:

```bash
cp adapters/claude/CLAUDE.md ./CLAUDE.md
```

#### Cursor

```bash
mkdir -p .cursor/skills
rsync -a context-cartographer/ .cursor/skills/context-cartographer/
```

When invoked, the skill can create or update `.cursor/rules/context-cartographer.mdc` from its bundled template.

</details>

<details>
<summary><strong>Local graph and command-line helpers</strong></summary>

The Markdown documents remain the source of truth. The index, report, and HTML graph are derived and can be rebuilt.

```bash
python3 context-cartographer/scripts/project_probe.py --root /path/to/project --json
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --check
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --write
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --outline docs/architecture.md
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --section docs/architecture.md#topic-map
```

- `project_probe.py` classifies the selected folder as `empty`, `scaffold`, `brief_only`, `existing`, or `unknown` without changing it.
- `--check` verifies documentation without writing files.
- `--write` rebuilds the offline graph only when its inputs changed.
- `--outline` lists headings from one in-scope document.
- `--section` returns one exact section together with its preamble and parent-heading chain.
- `--json` changes the representation, not the result.

The helpers use only the Python standard library. They do not fetch external links or execute text found in documents.

</details>

### Privacy and safety

- The graph stays local at `.context-cartographer/documentation-graph.html` and may contain private project text.
- Project-memory and questionnaire state are local-only by default.
- Sensitive paths such as `.env`, `.ssh`, and `secrets/` are recognized without reading their contents during folder classification.
- Child symlinks are not followed by the folder probe.
- A capped or incomplete scan is reported as incomplete, never as a confident result.
- Publishing, payments, external accounts, keys, and paid services remain separate decisions.

### Quality checks

Release 0.4.0 passes the package validator, behavioral smoke tests, and **420 unit and packaging tests** on Python 3.9.6 and 3.14.6. GitHub Actions repeats the same checks on Python 3.9 and 3.14.

The offline graph was also checked in headless Chromium at 1440×900 for rendering, document relationships, problem filtering, and JavaScript errors. Live end-to-end sessions in every supported client have not been tested.

<details>
<summary><strong>Run the checks yourself</strong></summary>

```bash
python3 context-cartographer/scripts/validate_skill.py
python3 context-cartographer/scripts/smoke_test.py
python3 -m unittest discover -s context-cartographer/tests -v
```

</details>

### Updates

The skill checks GitHub for a newer release at most once per day. Installing an available update always requires confirmation. The installed release is recorded in `context-cartographer/VERSION`.

---

<a id="russian"></a>

## Русский

Context Cartographer — скилл для Codex, Claude Code, Cursor и других программных агентов. Он помогает разобраться в проекте, разложить постоянные знания по правильным файлам и позже загрузить только нужный контекст, не перечитывая весь репозиторий.

Текущая версия — **0.4.0**.

### Когда пригодится

| Ситуация | Что сделает Context Cartographer |
| --- | --- |
| Есть идея, но проекта ещё нет | Поможет уточнить идею, отделит решения от предположений и сможет довести согласованный объём до первого рабочего результата |
| В проекте почти нет документации | Создаст небольшую связанную систему документов на основе файлов репозитория |
| Документы запутались и противоречат друг другу | Найдёт повторы, конфликты, битые ссылки, темы без владельца и устаревшие маршруты |
| Следующему агенту нужна только часть проекта | Построит карту и локальный граф, чтобы открыть нужный раздел, а не загружать всё подряд |

Явный запрос на работу с документацией всегда остаётся таким запросом. Например, проверка файла с требованиями не превратится в обсуждение развития идеи продукта.

### Что вы получите

- Одного понятного владельца для каждой постоянной темы.
- Короткую корневую инструкцию, которая направляет агентов к нужному контексту.
- Карту документации с настоящими ссылками, владельцами тем и условиями чтения.
- При необходимости — отдельные документы об архитектуре, продукте, дизайне, развёртывании, API, безопасности, интеграциях, администрировании, контенте или правилах кода.
- Приватный офлайн-граф документов и связей между ними.
- Точное чтение раздела вместе с преамбулой документа и родительскими заголовками.
- Сохраняемое состояние решений для длинного обсуждения идеи или плана.
- Проверку битых адресов, повторных владельцев, пропущенных маршрутов, устаревшего графа и неполного сканирования.

Context Cartographer не выдумывает архитектуру и не подменяет существующие правила. Неизвестные факты остаются явно неуточнёнными, а разрушительные изменения документации требуют разрешения.

### Как проходит работа

1. Агент находит корень проекта и читает ближайшие инструкции, код, конфигурацию и существующие документы.
2. Факты из репозитория отделяются от решений, которые можете принять только вы.
3. Скилл предлагает минимальную полезную структуру документации или следующий шаг проекта.
4. После согласованных изменений он проверяет ссылки, владельцев, маршруты, локальные файлы и граф документации.

Обычные правки остаются обычными: если в проекте уже указан файл-владелец, агент обновит его напрямую и не станет запускать полный аудит.

### Установка для Codex

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

После установки перезапустите Codex.

### Как пользоваться

Начать с идеи:

```text
Используй $context-cartographer. Я хочу сделать сервис, который напоминает семье о регулярных домашних делах. Сначала помоги проработать идею, файлы пока не создавай.
```

Создать документацию для существующего проекта:

```text
Используй $context-cartographer и создай систему документации для этого проекта. Сначала изучи репозиторий и не выдумывай недостающие факты.
```

Разобрать запутанные документы:

```text
Используй $context-cartographer. Проведи аудит документации, покажи, что сохранить, перенести, объединить или удалить, и не делай разрушительных изменений без моего решения.
```

Проверить граф:

```text
Используй $context-cartographer, проверь локальный граф документации и объясни найденные проблемы простыми словами.
```

### Какие файлы могут появиться

Набор зависит от проекта. Обычно документированный проект выглядит так:

```text
AGENTS.md                         Короткие маршруты для следующих задач
docs/architecture.md             Карта тем и разделов-владельцев
docs/documentation-rules.md      Правила поддержки документации
docs/architecture-overview.md    Стек, структура и точки входа
docs/architecture-quality-risks.md
.context-cartographer/documentation-graph.html  Приватный производный граф
```

В зависимости от выбранного агента корневым файлом может быть `CLAUDE.md` или `.cursor/rules/context-cartographer.mdc`. Дополнительные тематические документы создаются только при реальной необходимости.

<details>
<summary><strong>Установка для Claude Code и Cursor</strong></summary>

#### Claude Code

```bash
git clone https://github.com/sergeylopukhov/context-cartographer.git /tmp/context-cartographer
mkdir -p ~/.claude/skills
rsync -a /tmp/context-cartographer/context-cartographer/ ~/.claude/skills/context-cartographer/
```

Необязательный указатель для проекта:

```bash
cp adapters/claude/CLAUDE.md ./CLAUDE.md
```

#### Cursor

```bash
mkdir -p .cursor/skills
rsync -a context-cartographer/ .cursor/skills/context-cartographer/
```

При запуске скилл может создать или обновить `.cursor/rules/context-cartographer.mdc` по встроенному шаблону.

</details>

<details>
<summary><strong>Локальный граф и команды</strong></summary>

Источник истины — Markdown-документы. Индекс, отчёт и HTML-граф строятся из них, поэтому их можно пересоздать.

```bash
python3 context-cartographer/scripts/project_probe.py --root /path/to/project --json
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --check
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --write
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --outline docs/architecture.md
python3 context-cartographer/scripts/documentation_graph.py --root /path/to/project --section docs/architecture.md#topic-map
```

- `project_probe.py` относит выбранную папку к `empty`, `scaffold`, `brief_only`, `existing` или `unknown`, ничего в ней не меняя.
- `--check` проверяет документацию без записи файлов.
- `--write` пересобирает офлайн-граф, только если изменились входные данные.
- `--outline` выводит заголовки одного документа из области сканирования.
- `--section` возвращает точный раздел вместе с преамбулой и цепочкой родительских заголовков.
- `--json` меняет форму ответа, но не его содержание.

Скриптам достаточно стандартной библиотеки Python. Они не загружают внешние ссылки и не исполняют текст из документов.

</details>

### Приватность и безопасность

- Граф хранится локально в `.context-cartographer/documentation-graph.html` и может содержать приватный текст проекта.
- Память проекта и состояние анкеты по умолчанию не попадают в Git.
- При классификации папки пути `.env`, `.ssh` и `secrets/` распознаются без чтения содержимого.
- Символические ссылки на дочерние файлы и папки не обходятся классификатором.
- Ограниченное или незавершённое сканирование помечается как неполное, а не выдаётся за уверенный результат.
- Публикация, платежи, внешние аккаунты, ключи и платные сервисы остаются отдельными решениями.

### Проверка качества

Версия 0.4.0 проходит валидатор упаковки, smoke-тесты и **420 модульных и упаковочных тестов** на Python 3.9.6 и 3.14.6. GitHub Actions повторяет те же проверки на Python 3.9 и 3.14.

Офлайн-граф также проверен в headless Chromium при разрешении 1440 × 900: отрисовка, связи между документами, фильтр проблем и ошибки JavaScript. Сквозные живые сессии во всех поддерживаемых клиентах не проверялись.

<details>
<summary><strong>Запустить проверки самостоятельно</strong></summary>

```bash
python3 context-cartographer/scripts/validate_skill.py
python3 context-cartographer/scripts/smoke_test.py
python3 -m unittest discover -s context-cartographer/tests -v
```

</details>

### Обновления

Скилл проверяет GitHub не чаще раза в день. Доступное обновление устанавливается только после подтверждения. Номер установленного релиза хранится в `context-cartographer/VERSION`.
