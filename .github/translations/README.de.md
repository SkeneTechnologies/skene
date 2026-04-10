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


Skene ist ein Codebase-Analyse-Toolkit für produktgetriebenes Wachstum. Es scannt deine Codebase, deckt Wachstumschancen auf und erstellt konkrete Implementierungspläne.

## Schnellstart

Installiere und starte die interaktive Terminal-Oberfläche:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Der Assistent führt dich durch Anbieterauswahl, Authentifizierung und Analyse — eine vorherige Konfiguration ist nicht nötig.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Was es kann

- **Tech-Stack-Erkennung** -- identifiziert Frameworks, Datenbanken, Authentifizierung und Deployment
- **Erkennung von Wachstumsfeatures** -- findet bestehende Anmeldeflows, Sharing, Einladungen und Abrechnung
- **Feature-Register** -- verfolgt Features über mehrere Analyseläufe hinweg und verknüpft sie mit Growth Loops
- **Umsatzverlust-Analyse** -- spürt fehlende Monetarisierung und schwache Preisstufen auf
- **Generierung von Wachstumsplänen** -- erstellt priorisierte Growth Loops mit konkreten Roadmaps
- **Implementierungs-Prompts** -- erstellt einsatzbereite Prompts für Cursor, Claude oder andere KI-Tools
- **Telemetrie-Deployment** -- generiert Supabase-Migrationen und pusht sie zum Upstream
- **Loop-Validierung** -- prüft, ob die Anforderungen der Growth Loops umgesetzt wurden
- **Interaktiver Chat** -- stelle Fragen zu deiner Codebase direkt im Terminal

Unterstützt OpenAI, Gemini, Claude, LM Studio, Ollama und jeden OpenAI-kompatiblen Endpoint. Ein kostenloser lokaler Audit ist auch ohne API-Key verfügbar.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

### Terminal-Oberfläche (empfohlen)

Die TUI ist ein interaktiver Assistent, der dich durch den gesamten Workflow führt. Keine Voraussetzungen — der Installer kümmert sich um alles.

```bash
# TUI installieren
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Starten
skene
```

### Python CLI

Wenn du lieber die Kommandozeile nutzt, kannst du Skene direkt mit `uvx` ausführen (ohne Installation) oder global installieren:

```bash
# uv installieren (falls nicht vorhanden)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Direkt ausführen (keine Installation nötig)
uvx skene

# Oder global installieren
pip install skene
```

Details zur CLI-Nutzung findest du in der [Dokumentation](https://www.skene.ai/resources/docs/skene).

## Monorepo-Struktur

| Verzeichnis | Beschreibung | Sprache | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + Analyse-Engine | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktiver Terminal-UI-Assistent | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE-Plugin | — | — |

Die TUI (`tui/`) ist eine Bubble Tea-App, die ein interaktives Assistenten-Erlebnis bietet und die Python CLI über `uvx` orchestriert. Jedes Paket hat eigene CI/CD-Pipelines.

## Mitwirken

Beiträge sind willkommen. [Erstelle ein Issue](https://github.com/SkeneTechnologies/skene/issues) oder reiche einen [Pull Request](https://github.com/SkeneTechnologies/skene/pulls) ein.

## Lizenz

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
