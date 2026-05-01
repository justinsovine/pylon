# Pylon -- Pre-Investigation (Zero-Token Analysis)

## Problem

Each investigate phase spawns a Claude Code worker that reads the codebase to map touchpoints, trace data flows, and surface risks. For a 264-file Laravel app, that's thousands of tokens burned on structural discovery that static tools can do for free.

## Solution

Before the Claude worker runs, Pylon executes zero-token static analysis tools that produce structured markdown files. The worker reads these compact summaries instead of scanning raw source files, only drilling into specific files when tracing logic or behavior.

## Tools

| Tool | What it extracts | Output |
|------|-----------------|--------|
| **universal-ctags** | Symbol index: every class, function, method, interface with file + line number | `symbols.md` |
| **ripgrep** | Keyword matches across the codebase, filtered to relevant files | `keyword-matches.md` |
| **tree-sitter-php** | Class hierarchy: names, inheritance, methods, properties | `classes.md` |
| **tree-sitter-php** | Model details: table, fillable, relationships, casts | `models.md` |
| **php artisan / regex** | Route table: method, URI, action, middleware | `routes.md` |
| **phpstan** | Static analysis errors and type issues | `phpstan.md` |

All tools run in parallel. Total time: ~5-15 seconds for a typical Laravel app.

## Output

Written to `notes/{ticket-slug}/.pylon/pre-investigation/`:

```
.pylon/pre-investigation/
  summary.md            # tool status, file index, usage instructions
  symbols.md            # ctags symbol index
  keyword-matches.md    # ripgrep results for ticket-related terms
  classes.md            # tree-sitter class hierarchy
  models.md             # tree-sitter model details (table, fillable, relationships)
  routes.md             # route table
  phpstan.md            # static analysis errors
```

## Token savings estimate

Without pre-investigation (Claude reads raw files):
- Investigation reads ~30-50 PHP files
- Average file: ~200 lines / ~800 tokens
- Total: ~24,000-40,000 input tokens per investigation

With pre-investigation (Claude reads summaries):
- 6 structured markdown files
- Total: ~2,000-5,000 input tokens
- Claude only reads raw files for ~5-10 specific files it needs to trace
- Additional: ~4,000-8,000 input tokens

Estimated savings: **50-80% of investigation phase input tokens**.

At 4 tickets/day x 3 devs = 12 investigations/day, that's significant.

## Installation

### Docker (automatic)

The Dockerfile installs all tools. No manual setup needed.

### Local development

```bash
just install-system-tools    # installs ripgrep, ctags, php-cli, phpstan
just install                 # installs Python deps (tree-sitter)
just check-tools             # verify everything is available
```

### Manual (if just command fails)

```bash
# Ubuntu/Debian
sudo apt-get install ripgrep universal-ctags php-cli php-xml php-mbstring
composer global require phpstan/phpstan

# macOS
brew install ripgrep universal-ctags php
composer global require phpstan/phpstan

# Python deps
uv sync
```

## Usage

### Standalone (test against a repo)

```bash
just pre-investigate ~/code/edoc/onboard ./test-notes WorkerProfile export
```

### In the pipeline (automatic)

Pre-investigation runs automatically before every investigate phase. The pipeline task calls `run_pre_investigation()` before spawning the Claude worker.

### Verify tool availability

```bash
just check-tools
```

```
Tool availability:
  ctags: ok
  rg: ok
  php: ok
  phpstan: ok

All tools available.
```

Missing tools are skipped gracefully. The pipeline still works without them, just with fewer pre-computed summaries.

## How the investigate phase uses pre-investigation

The /pylon investigate phase instructions tell the worker:

1. Read `.pylon/pre-investigation/summary.md` first
2. Use `models.md` for entity relationships instead of reading model files
3. Use `routes.md` for endpoint mapping instead of reading route files
4. Use `symbols.md` to locate functions/methods by name
5. Use `keyword-matches.md` to find relevant code sections
6. Only read raw PHP files when tracing specific logic, validation rules, or complex behavior

## Extending for other stacks

The analyzer architecture is modular. Each tool is a separate file in `src/pylon/harness/analyzers/`. To support a non-PHP repo:

- Add language-specific analyzers (e.g., `tree_sitter_typescript.py`)
- ctags and ripgrep already support all languages
- phpstan/routes are PHP-specific, skip them for other stacks
- `preinvestigate.py` auto-detects available tools and skips unavailable ones
