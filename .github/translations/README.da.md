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


Skene er et kodebaseanalyseværktøj til produktdrevet vækst. Det scanner din kodebase, opdager vækstmuligheder og genererer handlingsorienterede implementeringsplaner.

## Hurtig start

Installer og start den interaktive terminal-brugerflade:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Guiden fører dig gennem valg af udbyder, autentificering og analyse — ingen konfiguration nødvendig på forhånd.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Hvad den gør

- **Detektering af tech-stack** -- identificerer frameworks, databaser, autentificering, deployment
- **Opdagelse af vækstfunktioner** -- finder eksisterende tilmeldingsflows, deling, invitationer, fakturering
- **Funktionsregister** -- sporer funktioner på tværs af analysekørsler og kobler dem til vækstloops
- **Analyse af indtægtstab** -- finder manglende monetarisering og svage prisniveauer
- **Generering af vækstplaner** -- producerer prioriterede vækstloops med implementeringsplaner
- **Implementeringsprompts** -- bygger klar-til-brug prompts til Cursor, Claude eller andre AI-værktøjer
- **Telemetri-deployment** -- genererer Supabase-migreringer og pusher til upstream
- **Loop-validering** -- verificerer at vækstloop-krav er implementeret
- **Interaktiv chat** -- stil spørgsmål om din kodebase i terminalen

Understøtter OpenAI, Gemini, Claude, LM Studio, Ollama og ethvert OpenAI-kompatibelt endpoint. Gratis lokal revision tilgængelig uden API-nøgle.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

### Terminal-brugerflade (anbefales)

TUI er en interaktiv guide, der fører dig gennem hele arbejdsgangen. Ingen forudsætninger — installationsprogrammet håndterer alt.

```bash
# Installer TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Start det
skene
```

### Python CLI

Hvis du foretrækker kommandolinjen, kan du køre Skene direkte med `uvx` (ingen installation nødvendig) eller installere det globalt:

```bash
# Installer uv (hvis du ikke har det)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Kør direkte (ingen installation nødvendig)
uvx skene

# Eller installer globalt
pip install skene
```

For detaljer om CLI-brug, se [dokumentationen](https://www.skene.ai/resources/docs/skene).

## Monorepo-struktur

| Mappe | Beskrivelse | Sprog | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analyse-engine | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktiv terminal-UI-guide | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE-plugin | — | — |

TUI (`tui/`) er en Bubble Tea-app, der giver en interaktiv guideoplevelse og orkestrerer Python CLI via `uvx`. Hver pakke har uafhængige CI/CD-pipelines.

## Bidrag

Bidrag er velkomne. Venligst [opret et issue](https://github.com/SkeneTechnologies/skene/issues) eller indsend en [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licens

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
