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


Skene est une boîte à outils d'analyse de code dédiée à la croissance produit. Il analyse votre code, repère les opportunités de croissance et génère des plans d'implémentation concrets.

## Démarrage rapide

Installez et lancez l'interface utilisateur de terminal interactive :

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

L'assistant vous guide à travers la sélection du fournisseur, l'authentification et l'analyse — aucune configuration préalable n'est nécessaire.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Ce qu'il fait

- **Détection de la stack technique** -- identifie frameworks, bases de données, authentification et déploiement
- **Découverte des fonctionnalités de croissance** -- repère les flux d'inscription, le partage, les invitations et la facturation déjà en place
- **Registre des fonctionnalités** -- suit les fonctionnalités d'une analyse à l'autre et les relie aux growth loops
- **Analyse des fuites de revenus** -- détecte la monétisation manquante et les paliers tarifaires faibles
- **Génération de plans de croissance** -- produit des growth loops priorisés avec leur feuille de route d'implémentation
- **Prompts d'implémentation** -- prépare des prompts prêts à l'emploi pour Cursor, Claude ou d'autres outils d'IA
- **Déploiement de la télémétrie** -- génère les migrations Supabase et les pousse en upstream
- **Validation des boucles** -- vérifie que les exigences des growth loops sont bien implémentées
- **Chat interactif** -- posez des questions sur votre code directement dans le terminal

Compatible avec OpenAI, Gemini, Claude, LM Studio, Ollama et tout endpoint compatible OpenAI. Un audit local gratuit est disponible, sans clé API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Installation

### Interface en terminal (recommandée)

La TUI est un assistant interactif qui vous accompagne tout au long du workflow. Aucun prérequis — le script d'installation s'occupe de tout.

```bash
# Installer la TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# La lancer
skene
```

### CLI Python

Si vous préférez la ligne de commande, vous pouvez lancer Skene directement avec `uvx` (sans rien installer) ou l'installer globalement :

```bash
# Installer uv (si vous ne l'avez pas)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Exécuter directement (aucune installation nécessaire)
uvx skene

# Ou installer globalement
pip install skene
```

Pour les détails d'utilisation de la CLI, voir la [documentation](https://www.skene.ai/resources/docs/skene).

## Structure du monorepo

| Répertoire | Description | Langage | Distribution |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + moteur d'analyse | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Assistant interactif en terminal | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin Cursor IDE | — | — |

La TUI (`tui/`) est une application Bubble Tea qui offre une expérience guidée interactive et orchestre la CLI Python via `uvx`. Chaque package dispose de ses propres pipelines CI/CD.

## Contribuer

Les contributions sont les bienvenues. [Ouvrez une issue](https://github.com/SkeneTechnologies/skene/issues) ou envoyez une [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licence

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
