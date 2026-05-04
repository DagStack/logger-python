# Docs examples — автотесты Python snippets из `dagstack/logger-docs`

Каждый файл `test_<page>.py` содержит **дословно извлечённые**
Python-примеры из соответствующей страницы
[dagstack/logger-docs](https://github.com/dagstack/logger-docs) +
минимальные assertions. Цель — ловить drift между snippets в
документации и реальным API биндинга `dagstack-logger`.

## Правила синхронизации

- Одна страница docs = один `test_<slug>.py`. Slug совпадает с MDX-
  файлом: `docs/intro.mdx` → `test_intro.py`,
  `docs/concepts/severity.mdx` → `test_concepts_severity.py`,
  `docs/guides/testing.mdx` → `test_guides_testing.py`.
- Тело каждого теста между маркерами
  `# --- snippet start (...) ---` / `# --- snippet end ---` —
  дословная копия Python TabItem snippet'а из MDX (комментарии и
  отступы сохранены). Дальше идут `assert`-проверки, воспроизводящие
  поведение, описанное окружающей прозой.
- Substitutions, неизбежные в pytest-окружении (file paths, in-memory
  стримы вместо `/var/log/...`, captured callable вместо реального
  `sentry_sdk.capture_message`) помечены `# NB:` инлайн-комментарием
  для последующего drift-ревью.
- Phase 1 features, ещё не реализованные в биндинге
  (`logger.operation`, `logger.emit_event`), используют документированный
  workaround (`logger.child(attributes=...)`).

## Изоляция

`conftest.py` через autouse-фикстуру вызывает
`_reset_registry_for_tests()` до и после каждого теста — глобальный
Logger registry чистится, побочные эффекты от `configure()` /
`scope_sinks` / `set_sinks` не утекают между тестами.

## Почему в биндинге, а не в docs-репо

- Используется существующая pytest-инфра: одна команда `pytest`
  запускает и unit-тесты API, и docs-примеры.
- Breaking change в API сразу виден как **красный тест с именем
  страницы docs** — автор знает, какую страницу переписывать.
- Не нужно ставить `dagstack-logger` отдельно для docs-тестов —
  тесты живут внутри пакета и используют текущий `src/`.

## Запуск

```bash
uv run pytest tests/docs_examples/ -v
```
