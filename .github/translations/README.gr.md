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


Το Skene είναι ένα toolkit ανάλυσης κώδικα για product-led growth. Σαρώνει τον κώδικά σας, εντοπίζει ευκαιρίες ανάπτυξης και δημιουργεί συγκεκριμένα σχέδια υλοποίησης.

## Γρήγορη εκκίνηση

Εγκαταστήστε και εκκινήστε το διαδραστικό περιβάλλον τερματικού:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Ο οδηγός σας καθοδηγεί στην επιλογή παρόχου, τον έλεγχο ταυτότητας και την ανάλυση — δεν χρειάζεται καμία ρύθμιση από πριν.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Τι κάνει

- **Ανίχνευση τεχνολογικής στοίβας** -- αναγνωρίζει frameworks, βάσεις δεδομένων, αυθεντικοποίηση και deployment
- **Ανακάλυψη λειτουργιών ανάπτυξης** -- βρίσκει υπάρχουσες ροές εγγραφής, κοινοποίηση, προσκλήσεις και χρέωση
- **Μητρώο λειτουργιών** -- παρακολουθεί λειτουργίες ανάμεσα στις εκτελέσεις της ανάλυσης και τις συνδέει με growth loops
- **Ανάλυση απώλειας εσόδων** -- εντοπίζει χαμένη μονετοποίηση και αδύναμα επίπεδα τιμολόγησης
- **Δημιουργία σχεδίου ανάπτυξης** -- παράγει growth loops με προτεραιότητα και οδικούς χάρτες υλοποίησης
- **Prompts υλοποίησης** -- ετοιμάζει έτοιμα prompts για Cursor, Claude και άλλα εργαλεία AI
- **Deployment τηλεμετρίας** -- δημιουργεί migrations για Supabase και τα στέλνει στο upstream
- **Επικύρωση loops** -- επαληθεύει ότι οι απαιτήσεις των growth loops έχουν υλοποιηθεί
- **Διαδραστική συνομιλία** -- κάντε ερωτήσεις για τον κώδικά σας μέσα από το τερματικό

Υποστηρίζει OpenAI, Gemini, Claude, LM Studio, Ollama και οποιοδήποτε endpoint συμβατό με OpenAI. Διατίθεται δωρεάν τοπικός έλεγχος, χωρίς κλειδί API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Εγκατάσταση

### Περιβάλλον τερματικού (συνιστάται)

Το TUI είναι ένας διαδραστικός οδηγός που σας καθοδηγεί σε ολόκληρη τη ροή εργασίας. Χωρίς προαπαιτούμενα — το πρόγραμμα εγκατάστασης τα διαχειρίζεται όλα.

```bash
# Εγκατάσταση του TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Εκκίνηση
skene
```

### Python CLI

Αν προτιμάτε τη γραμμή εντολών, μπορείτε να εκτελέσετε το Skene απευθείας με `uvx` (δεν απαιτείται εγκατάσταση) ή να το εγκαταστήσετε καθολικά:

```bash
# Εγκατάσταση του uv (αν δεν το έχετε)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Άμεση εκτέλεση (δεν απαιτείται εγκατάσταση)
uvx skene

# Ή καθολική εγκατάσταση
pip install skene
```

Για λεπτομέρειες χρήσης του CLI, ανατρέξτε στην [τεκμηρίωση](https://www.skene.ai/resources/docs/skene).

## Δομή monorepo

| Κατάλογος | Περιγραφή | Γλώσσα | Διανομή |
|-----------|-----------|--------|---------|
| `src/skene/` | CLI + μηχανή ανάλυσης | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Διαδραστικός οδηγός τερματικού | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin για Cursor IDE | — | — |

Το TUI (`tui/`) είναι μια εφαρμογή Bubble Tea που παρέχει μια διαδραστική εμπειρία οδηγού και ενορχηστρώνει το Python CLI μέσω `uvx`. Κάθε πακέτο έχει ανεξάρτητα CI/CD pipelines.

## Συνεισφορά

Οι συνεισφορές είναι ευπρόσδεκτες. Παρακαλούμε [ανοίξτε ένα issue](https://github.com/SkeneTechnologies/skene/issues) ή υποβάλετε ένα [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Άδεια χρήσης

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
