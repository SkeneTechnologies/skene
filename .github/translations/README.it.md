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


Skene è un toolkit di analisi del codice per la crescita product-led. Analizza il tuo codice, individua opportunità di crescita e genera piani di implementazione concreti.

## Avvio rapido

Installa e avvia l'interfaccia interattiva da terminale:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

La procedura guidata ti accompagna nella scelta del provider, nell'autenticazione e nell'analisi — nessuna configurazione preliminare richiesta.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Cosa fa

- **Rilevamento dello stack tecnologico** -- identifica framework, database, autenticazione, deployment
- **Scoperta delle funzionalità di crescita** -- individua flussi di registrazione, condivisione, inviti e fatturazione già presenti
- **Registro delle funzionalità** -- traccia le funzionalità tra un'analisi e l'altra, collegandole ai growth loop
- **Analisi delle perdite di ricavi** -- segnala monetizzazioni mancanti e fasce di prezzo deboli
- **Generazione di piani di crescita** -- produce growth loop prioritizzati con roadmap di implementazione
- **Prompt di implementazione** -- prepara prompt pronti all'uso per Cursor, Claude o altri strumenti AI
- **Deployment della telemetria** -- genera migrazioni Supabase e le pubblica upstream
- **Validazione dei loop** -- verifica che i requisiti dei growth loop siano implementati
- **Chat interattiva** -- fai domande sul tuo codice direttamente dal terminale

Supporta OpenAI, Gemini, Claude, LM Studio, Ollama e qualsiasi endpoint compatibile con OpenAI. È disponibile un audit locale gratuito, senza chiave API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installazione

### Interfaccia da terminale (consigliata)

La TUI è una procedura guidata interattiva che ti accompagna lungo l'intero flusso di lavoro. Nessun prerequisito — all'installazione pensa lo script.

```bash
# Installa la TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Avviala
skene
```

### Python CLI

Se preferisci la riga di comando, puoi eseguire Skene direttamente con `uvx` (senza installare nulla) oppure installarlo globalmente:

```bash
# Installa uv (se non lo hai)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Esegui direttamente (nessuna installazione necessaria)
uvx skene

# Oppure installa globalmente
pip install skene
```

Per i dettagli sull'uso da CLI, consulta la [documentazione](https://www.skene.ai/resources/docs/skene).

## Struttura del monorepo

| Directory | Descrizione | Linguaggio | Distribuzione |
|-----------|-------------|------------|---------------|
| `src/skene/` | CLI + motore di analisi | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Procedura guidata interattiva da terminale | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin per Cursor IDE | — | — |

La TUI (`tui/`) è un'app Bubble Tea che offre un'esperienza guidata interattiva e orchestra la CLI Python tramite `uvx`. Ogni pacchetto ha pipeline CI/CD indipendenti.

## Contribuire

I contributi sono benvenuti. [Apri una issue](https://github.com/SkeneTechnologies/skene/issues) o invia una [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licenza

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
