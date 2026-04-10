<p align="center">
  <a href="../../README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a> |
  <a href="README.gr.md">Ελληνικά</a> |
  <a href="README.vi.md">Tiếng Việt</a> |
  <a href="README.fi.md">Suomi</a> |
  <a href="README.sv.md">Svenska</a>
</p>

<p align="center">
  <img width="4000" height="800" alt="Skene_git" src="https://github.com/user-attachments/assets/2be11c04-6b98-4e26-8905-bf3250c4addb" />
  <a href="https://www.skene.ai"><img width="120" height="42" alt="website" src="https://github.com/user-attachments/assets/8ae8c68f-eeb5-411f-832f-6b6818bd2c34"></a>
  <a href="https://www.skene.ai/resources/docs/skene"><img width="120" height="42" alt="docs" src="https://github.com/user-attachments/assets/f847af52-0f6f-4570-9a48-1b7c8f4f0d7a"></a>
  <a href="https://www.skene.ai/resources/blog"><img width="100" height="42" alt="blog" src="https://github.com/user-attachments/assets/8c62e3b8-39a8-43f6-bb0b-f00b118aff82"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img width="153" height="42" alt="reddit" src="https://github.com/user-attachments/assets/b420ea50-26e3-40fe-ab34-ac179f748357"></a>
</p>


Skene — це набір інструментів для аналізу кодової бази, орієнтований на продуктове зростання. Він сканує вашу кодову базу, знаходить можливості для зростання й генерує конкретні плани впровадження.

## Швидкий старт

Встановіть та запустіть інтерактивний термінальний інтерфейс:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Майстер проведе вас через вибір провайдера, автентифікацію та аналіз — попереднє налаштування не потрібне.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Що він робить

- **Визначення технологічного стеку** — ідентифікує фреймворки, бази даних, автентифікацію, розгортання
- **Виявлення функцій зростання** — знаходить існуючі потоки реєстрації, спільний доступ, запрошення, білінг
- **Реєстр функцій** — відстежує функції між запусками аналізу, пов'язує їх із циклами зростання
- **Аналіз втрати доходу** — виявляє відсутню монетизацію та слабкі цінові рівні
- **Генерація плану зростання** — створює пріоритетні цикли зростання з дорожніми картами впровадження
- **Промпти для впровадження** — створює готові до використання промпти для Cursor, Claude або інших ШІ-інструментів
- **Розгортання телеметрії** — генерує міграції Supabase та відправляє їх у upstream
- **Валідація циклів** — перевіряє, що вимоги циклу зростання впроваджені
- **Інтерактивний чат** — ставте запитання про вашу кодову базу в терміналі

Підтримує OpenAI, Gemini, Claude, LM Studio, Ollama та будь-яку OpenAI-сумісну кінцеву точку. Доступний безкоштовний локальний аудит без необхідності API-ключа.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Встановлення

### Термінальний інтерфейс (рекомендовано)

TUI — це інтерактивний майстер, який проведе вас через весь робочий процес. Передумов немає — інсталятор подбає про все.

```bash
# Встановити TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Запустити
skene
```

### Python CLI

Якщо ви надаєте перевагу командному рядку, ви можете запустити Skene безпосередньо через `uvx` (встановлення не потрібне) або встановити глобально:

```bash
# Встановити uv (якщо у вас його немає)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Запустити безпосередньо (встановлення не потрібне)
uvx skene

# Або встановити глобально
pip install skene
```

Для деталей використання CLI дивіться [документацію](https://www.skene.ai/resources/docs/skene).

## Структура монорепозиторію

| Директорія | Опис | Мова | Дистрибуція |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + аналітичний рушій | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Інтерактивний термінальний майстер | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Плагін для Cursor IDE | — | — |

TUI (`tui/`) — це додаток Bubble Tea, який забезпечує інтерактивний досвід майстра та керує Python CLI через `uvx`. Кожен пакет має незалежні CI/CD конвеєри.

## Внесок

Внески вітаються. Будь ласка, [створіть issue](https://github.com/SkeneTechnologies/skene/issues) або надішліть [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Ліцензія

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
