<div align="center">

![Context Cartographer cover](assets/context-cartographer-cover.png)

# Context Cartographer

**AI-readable project documentation for Codex, Claude Code, Cursor, and other coding agents.**

[English](#english) · [Русский](#russian)

</div>

---

<a id="english"></a>

## English

Context Cartographer sets up project documentation for coding agents. During a run, the agent inspects the repository, assigns each durable topic to one owner file, and writes a short root instruction file that points later tasks to the right context.

Version 0.2.0 separates repository facts from user decisions. Code, configuration, and existing docs answer factual questions. The user is asked only about choices that the repository cannot settle.

### What it handles

- Creates a documentation system for a new or undocumented project.
- Audits and restructures an existing set of docs.
- Finds duplicate ownership, contradictions, stale links, and topics without an owner.
- Chooses the question interface to fit the task: direct conversation, the host agent's structured input, or the bundled local questionnaire.
- Resolves dependent decisions in order and can save long-running interview state in `decision-state.json`.
- Rejects dependency cycles and incomplete decision sets before documentation changes begin.
- Produces Markdown instructions for Codex, Claude Code, Cursor, and other coding agents.

Routine edits to a known owner file do not load the full skill. Root instructions route the agent directly to that file. Context Cartographer is used for initial setup, audits, migrations, cleanup, restructuring, and cases where ownership is unclear.

### Files it may create

The exact set depends on the repository:

- Root agent instruction file — `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, or `.cursor/rules/context-cartographer.mdc` for Cursor.
- `docs/architecture.md` — the documentation map.
- `docs/architecture-overview.md` — stack, layout, and entry points.
- `docs/architecture-quality-risks.md` — tests, checks, risks, and fragile areas.
- `docs/code_rules.md` — optional rules for code changes.
- Profile docs such as `PRODUCT.md`, `DESIGN.md`, `DEPLOYMENT.md`, `API.md`, `SECURITY.md`, `INTEGRATIONS.md`, `ADMIN.md`, or `CONTENT-SEO.md` when repository evidence supports them.

The local `.project-questionnaire/` directory holds questionnaire answers and temporary decision state. It is ignored by Git by default and never acts as the source of truth for project facts.

### Workflow

1. Inspect the nearest project instructions, code, configuration, and docs without changing them.
2. Separate verified facts from decisions that belong to the user.
3. Collect independent choices through the most suitable interface. Ask dependent questions only after their prerequisites are resolved.
4. Validate saved decision state, references between decisions, and open conflicts when the task needs an extended interview.
5. Before editing existing docs, show the proposed ownership map and list every file to keep, change, create, or remove.
6. Apply the approved scope, then check owners, links, old filenames, Git ignore rules, and routing for future tasks.

The generated system does not add a parallel `CONTEXT.md` or another competing source of truth. Each durable topic has one owner document.

### Requirements

- Python 3.
- Git when working inside a repository.
- No third-party Python packages for the questionnaire or decision-state validator.

### Install

#### Codex

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

Restart Codex after installation.

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

When you run the skill, it can create or update the project-specific `.cursor/rules/context-cartographer.mdc` router from its bundled templates.

### Updates

The skill checks GitHub for a newer version at most once per day. Installing an update always requires confirmation. The installed version is recorded in `context-cartographer/VERSION`.

### Use

```text
Use $context-cartographer and bring this project's documentation into shape.
```

For an existing messy project:

```text
Use context-cartographer. Analyze existing documentation as project context, decide what to keep, move, or delete, and show a proposed docs map before editing.
```

---

<a id="russian"></a>

## Русский

Context Cartographer настраивает проектную документацию для ИИ-агентов. Во время запуска агент изучает репозиторий, назначает каждой постоянной теме один файл-владелец и создаёт в корне короткую инструкцию со ссылками на нужный контекст.

В версии 0.2.0 агент различает факты репозитория и решения пользователя. Фактические вопросы проверяются по коду, конфигурации и существующим документам. Пользователю остаются решения, для которых в проекте нет ответа.

### Что умеет скилл

- создаёт документационную систему для нового проекта или проекта без документации;
- проверяет и перестраивает существующие документы;
- находит дубли, противоречия, устаревшие ссылки и темы без владельца;
- выбирает способ опроса по задаче: один вопрос в чате, встроенная форма агента или локальная анкета;
- разбирает зависимые решения по порядку и сохраняет состояние длинной сессии в `decision-state.json`;
- отклоняет циклы зависимостей и неполные наборы решений до начала правок;
- поддерживает Codex, Claude Code, Cursor и других агентов, которые читают Markdown.

Для обычного обновления известного документа полный запуск не нужен. Корневая инструкция направляет агента сразу в нужный файл. Context Cartographer используется при первой настройке, аудите, миграции, очистке, перестройке и в случаях, когда владелец темы неясен.

### Какие файлы создаются

Точный набор зависит от репозитория:

- `AGENTS.md` для Codex, `CLAUDE.md` для Claude Code или `.cursor/rules/context-cartographer.mdc` для Cursor;
- `docs/architecture.md` с картой владельцев;
- `docs/architecture-overview.md` со стеком, структурой и точками входа;
- `docs/architecture-quality-risks.md` с проверками, рисками и техническим долгом;
- `docs/code_rules.md` с необязательными правилами для правок кода.

Профильные документы `PRODUCT.md`, `DESIGN.md`, `DEPLOYMENT.md`, `API.md`, `SECURITY.md`, `INTEGRATIONS.md`, `ADMIN.md` и `CONTENT-SEO.md` создаются, если их необходимость подтверждают файлы проекта.

Локальная папка `.project-questionnaire/` хранит анкету, ответы и временное состояние решений. По умолчанию она исключена из Git и не считается источником проектных фактов.

### Как проходит работа

1. Агент определяет корень проекта и без правок изучает ближайшие инструкции, код, конфигурацию и документы.
2. Проверенные факты отделяются от решений, которые должен принять пользователь.
3. Для независимых решений выбирается подходящий способ опроса. Зависимые вопросы задаются после решения их предпосылок.
4. При длинном интервью валидатор проверяет состояние сессии, связи между решениями и открытые противоречия.
5. Перед изменением существующих документов агент показывает будущую карту: что останется, что изменится, что появится и что будет удалено.
6. После правок агент проверяет владельцев, ссылки, старые имена файлов, правила исключения из Git и маршрутизацию следующих задач.

Параллельные `CONTEXT.md` и другие конкурирующие источники истины не создаются. У каждой постоянной темы есть один документ-владелец.

### Требования

- Python 3;
- Git при работе внутри репозитория;
- анкета и валидатор состояния работают без сторонних библиотек Python.

### Установка

#### Codex

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo sergeylopukhov/context-cartographer \
  --path context-cartographer
```

После установки перезапустите Codex.

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

При запуске скилл может создать или обновить проектный роутер `.cursor/rules/context-cartographer.mdc` по встроенному шаблону.

### Обновления

Скилл проверяет наличие новой версии не чаще одного раза в день. Установка обновления всегда требует подтверждения. Текущая версия указана в `context-cartographer/VERSION`.

### Использование

```text
Используй $context-cartographer и приведи документацию проекта в порядок.
```

Для проекта с уже существующей, но запутанной документацией:

```text
Используй context-cartographer. Проанализируй существующие docs как контекст проекта, реши, что сохранить, перенести или убрать, и покажи карту документации перед правками.
```
