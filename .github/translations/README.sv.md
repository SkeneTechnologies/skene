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


Skene är ett kodbasanalysverktyg för produktledd tillväxt. Det skannar din kodbas, upptäcker tillväxtmöjligheter och genererar handlingsbara implementeringsplaner.

## Snabbstart

Installera och starta det interaktiva terminalgränssnittet:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Guiden leder dig genom val av leverantör, autentisering och analys — ingen konfiguration krävs i förväg.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Vad den gör

- **Identifiering av teknikstack** -- identifierar ramverk, databaser, autentisering, distribution
- **Upptäckt av tillväxtfunktioner** -- hittar befintliga registreringsflöden, delning, inbjudningar, fakturering
- **Funktionsregister** -- spårar funktioner mellan analyskörningar och kopplar dem till tillväxtloopar
- **Analys av intäktsläckage** -- upptäcker saknad monetisering och svaga prisnivåer
- **Generering av tillväxtplaner** -- skapar prioriterade tillväxtloopar med implementeringsfärdplaner
- **Implementeringsprompter** -- bygger färdiga prompter för Cursor, Claude eller andra AI-verktyg
- **Telemetridistribution** -- genererar Supabase-migreringar och skickar till uppströms
- **Validering av loopar** -- verifierar att kraven för tillväxtloopar är implementerade
- **Interaktiv chatt** -- ställ frågor om din kodbas i terminalen

Stöder OpenAI, Gemini, Claude, LM Studio, Ollama och alla OpenAI-kompatibla slutpunkter. Gratis lokal granskning tillgänglig utan API-nyckel.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

### Terminalgränssnitt (rekommenderas)

TUI är en interaktiv guide som leder dig genom hela arbetsflödet. Inga förutsättningar — installationsprogrammet sköter allt.

```bash
# Installera TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Starta det
skene
```

### Python CLI

Om du föredrar kommandoraden kan du köra Skene direkt med `uvx` (ingen installation behövs) eller installera det globalt:

```bash
# Installera uv (om du inte har det)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Kör direkt (ingen installation behövs)
uvx skene

# Eller installera globalt
pip install skene
```

För detaljer om CLI-användning, se [dokumentationen](https://www.skene.ai/resources/docs/skene).

## Monorepo-struktur

| Katalog | Beskrivning | Språk | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analysmotor | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktiv guide för terminal-UI | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE-plugin | — | — |

TUI (`tui/`) är en Bubble Tea-app som ger en interaktiv guideupplevelse och orkestrerar Python CLI via `uvx`. Varje paket har oberoende CI/CD-pipelines.

## Bidra

Bidrag är välkomna. Vänligen [öppna ett ärende](https://github.com/SkeneTechnologies/skene/issues) eller skicka in en [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licens

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
