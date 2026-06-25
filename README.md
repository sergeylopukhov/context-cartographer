<div align="center">

![Context Cartographer cover](assets/context-cartographer-cover.png)

# Context Cartographer

**AI-readable project documentation for Codex, Claude Code, Cursor, and other coding agents.**

[English](#english) · [Русский](#russian)

</div>

---

<a id="english"></a>

## English

Context Cartographer is an agent skill that creates compact project documentation for AI agents, not long manuals for people.

It gives an AI a reliable map of the repository: where the important code lives, which docs own which facts, what to read before editing, and how to keep durable project knowledge current. The result is less repeated scanning, fewer wasted tokens, and faster handoff between AI sessions or different AI tools.

### Why Use It

- Your AI does not need to rediscover the same project structure every task.
- Project facts live in small owner docs instead of scattered chat history.
- Any AI that can read Markdown can use the generated docs.
- Existing docs are inspected before changes; the skill asks before rewriting, moving, or deleting them.
- Agent-facing docs stay local-only by default unless you explicitly decide to track or publish them.

### What It Creates

The skill creates only the documentation the project needs:

- Root agent instruction file — `AGENTS.md` for Codex, `CLAUDE.md` for Claude Code, or `.cursor/rules/context-cartographer.mdc` for Cursor.
- `docs/architecture.md` — the documentation map.
- `docs/architecture-overview.md` — stack, layout, and entry points.
- `docs/architecture-quality-risks.md` — tests, checks, risks, and fragile areas.
- `docs/code_rules.md` — optional rules for code edits, created only if you choose it.
- Profile docs such as `PRODUCT.md`, `DESIGN.md`, `DEPLOYMENT.md`, `API.md`, `SECURITY.md`, or `CONTENT-SEO.md` only when the project actually needs them.

### How It Works

1. The agent scans the repository in read-only mode.
2. If decisions are needed, it asks through a local clickable questionnaire.
3. It proposes a documentation map before editing existing docs.
4. It creates or updates the approved docs.
5. Future AI agents use those docs instead of spending context on repeated discovery.

### Updates

When the skill runs, it can check GitHub for a newer version at most once every 7 days. If an update is available, the agent asks before installing it. It never updates itself silently.

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
mkdir -p .cursor/rules
cp adapters/cursor/context-cartographer.mdc .cursor/rules/context-cartographer.mdc
```

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

Context Cartographer — скилл, который создаёт короткую проектную документацию для ИИ-агентов, а не большую инструкцию для человека.

Он даёт ИИ понятную карту репозитория: где лежит важный код, какие файлы отвечают за разные знания о проекте, что читать перед правками и как поддерживать устойчивые проектные правила. В результате ИИ не тратит большой контекст и токены на повторный поиск структуры, файлов и функций.

### Зачем Это Нужно

- ИИ не изучает проект заново перед каждой задачей.
- Важные факты лежат в небольших Markdown-файлах, а не теряются в истории чатов.
- Документацию может читать любой ИИ, который умеет работать с Markdown.
- Существующие docs сначала проверяются; скилл спрашивает перед перезаписью, переносом или удалением.
- Документация для ИИ по умолчанию остаётся локальной, если вы явно не решили хранить её в репозитории.

### Что Создаётся

Скилл создаёт только те файлы, которые нужны проекту:

- Корневой файл инструкций для ИИ: `AGENTS.md` для Codex, `CLAUDE.md` для Claude Code или `.cursor/rules/context-cartographer.mdc` для Cursor.
- `docs/architecture.md` — карта документации.
- `docs/architecture-overview.md` — стек, структура и важные точки входа.
- `docs/architecture-quality-risks.md` — тесты, проверки, риски и хрупкие места.
- `docs/code_rules.md` — необязательные правила для правок кода, только если вы выбрали такой режим.
- Профильные docs вроде `PRODUCT.md`, `DESIGN.md`, `DEPLOYMENT.md`, `API.md`, `SECURITY.md` или `CONTENT-SEO.md` — только когда они действительно нужны проекту.

### Как Это Работает

1. Агент сначала читает проект без изменений.
2. Если нужны решения, он задаёт вопросы через локальную кликабельную анкету.
3. Перед правками показывает карту будущей документации.
4. Создаёт или обновляет только согласованные файлы.
5. Следующие ИИ-агенты читают эту карту и не тратят контекст на повторную разведку проекта.

### Обновления

При запуске скилл может проверить GitHub на новую версию, но не чаще одного раза в 7 дней. Если обновление есть, агент спросит перед установкой. Самостоятельно и незаметно он не обновляется.

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
mkdir -p .cursor/rules
cp adapters/cursor/context-cartographer.mdc .cursor/rules/context-cartographer.mdc
```

### Использование

```text
Используй $context-cartographer и приведи документацию проекта в порядок.
```

Для проекта с уже существующей, но запутанной документацией:

```text
Используй context-cartographer. Проанализируй существующие docs как контекст проекта, реши, что сохранить, перенести или убрать, и покажи карту документации перед правками.
```
