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


Skene to zestaw narzędzi do analizy bazy kodu ukierunkowany na wzrost oparty na produkcie. Skanuje Twoją bazę kodu, wykrywa możliwości wzrostu i generuje praktyczne plany wdrożeniowe.

## Szybki start

Zainstaluj i uruchom interaktywny interfejs terminalowy:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Kreator przeprowadzi Cię przez wybór dostawcy, uwierzytelnianie i analizę — bez konieczności wcześniejszej konfiguracji.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Co potrafi

- **Wykrywanie stosu technologicznego** -- identyfikuje frameworki, bazy danych, uwierzytelnianie, wdrażanie
- **Wykrywanie funkcji wzrostu** -- znajduje istniejące przepływy rejestracji, udostępnianie, zaproszenia, rozliczenia
- **Rejestr funkcji** -- śledzi funkcje w różnych uruchomieniach analizy i łączy je z pętlami wzrostu
- **Analiza wycieków przychodów** -- wykrywa brakującą monetyzację i słabe poziomy cenowe
- **Generowanie planów wzrostu** -- tworzy priorytetowe pętle wzrostu z planami wdrożeniowymi
- **Prompty wdrożeniowe** -- buduje gotowe do użycia prompty dla Cursor, Claude lub innych narzędzi AI
- **Wdrażanie telemetrii** -- generuje migracje Supabase i wypycha je do upstreamu
- **Walidacja pętli** -- weryfikuje, czy wymagania pętli wzrostu zostały zaimplementowane
- **Czat interaktywny** -- zadawaj pytania o swoją bazę kodu w terminalu

Obsługuje OpenAI, Gemini, Claude, LM Studio, Ollama i każdy punkt końcowy zgodny z OpenAI. Bezpłatny lokalny audyt dostępny bez klucza API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Instalacja

### Interfejs terminalowy (zalecany)

TUI to interaktywny kreator, który prowadzi Cię przez cały przepływ pracy. Brak wymagań wstępnych — instalator zajmie się wszystkim.

```bash
# Zainstaluj TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Uruchom go
skene
```

### Python CLI

Jeśli wolisz wiersz poleceń, możesz uruchomić Skene bezpośrednio za pomocą `uvx` (bez instalacji) lub zainstalować go globalnie:

```bash
# Zainstaluj uv (jeśli go nie masz)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Uruchom bezpośrednio (bez instalacji)
uvx skene

# Lub zainstaluj globalnie
pip install skene
```

Szczegóły dotyczące korzystania z CLI znajdziesz w [dokumentacji](https://www.skene.ai/resources/docs/skene).

## Struktura monorepo

| Katalog | Opis | Język | Dystrybucja |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + silnik analizy | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktywny kreator interfejsu terminalowego | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Wtyczka Cursor IDE | — | — |

TUI (`tui/`) to aplikacja Bubble Tea, która zapewnia interaktywne doświadczenie kreatora i orkiestruje Python CLI za pośrednictwem `uvx`. Każdy pakiet ma niezależne potoki CI/CD.

## Współpraca

Wkład jest mile widziany. Prosimy [otworzyć zgłoszenie](https://github.com/SkeneTechnologies/skene/issues) lub przesłać [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licencja

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
