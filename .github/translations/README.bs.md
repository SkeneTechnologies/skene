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


Skene je alat za analizu kodne baze namijenjen rastu vođenom proizvodom. Skenira vašu kodnu bazu, otkriva prilike za rast i generiše konkretne planove implementacije.

## Brzi početak

Instalirajte i pokrenite interaktivni terminal UI:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Čarobnjak vas vodi kroz odabir provajdera, autentifikaciju i analizu — nije potrebna prethodna konfiguracija.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Šta radi

- **Detekcija tehnološkog steka** -- prepoznaje frameworke, baze podataka, autentifikaciju i deployment
- **Otkrivanje funkcionalnosti rasta** -- pronalazi postojeće tokove registracije, dijeljenje, pozivnice i naplatu
- **Registar funkcionalnosti** -- prati funkcionalnosti kroz različita pokretanja analize i povezuje ih sa growth loop-ovima
- **Analiza gubitka prihoda** -- otkriva propuštenu monetizaciju i slabe cjenovne nivoe
- **Generisanje plana rasta** -- pravi prioritizirane growth loop-ove sa planovima implementacije
- **Promptovi za implementaciju** -- priprema gotove promptove za Cursor, Claude i druge AI alate
- **Deployment telemetrije** -- generiše Supabase migracije i šalje ih na upstream
- **Validacija petlji** -- provjerava da li su zahtjevi growth loop-ova implementirani
- **Interaktivni chat** -- postavljajte pitanja o svojoj kodnoj bazi direktno u terminalu

Podržava OpenAI, Gemini, Claude, LM Studio, Ollama i bilo koji endpoint kompatibilan sa OpenAI. Dostupan je besplatan lokalni audit, bez potrebe za API ključem.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Instalacija

### Terminal UI (preporučeno)

TUI je interaktivni čarobnjak koji vas vodi kroz cijeli radni tok. Bez preduvjeta — instalator se brine za sve.

```bash
# Instalacija TUI-a
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Pokrenite ga
skene
```

### Python CLI

Ako preferirate komandnu liniju, možete pokrenuti Skene direktno sa `uvx` (instalacija nije potrebna) ili ga instalirati globalno:

```bash
# Instalirajte uv (ako ga nemate)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Pokrenite direktno (instalacija nije potrebna)
uvx skene

# Ili instalirajte globalno
pip install skene
```

Za detalje korištenja CLI-a, pogledajte [dokumentaciju](https://www.skene.ai/resources/docs/skene).

## Struktura monorepoa

| Direktorij | Opis | Jezik | Distribucija |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analitički engine | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktivni terminal UI čarobnjak | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE plugin | — | — |

TUI (`tui/`) je Bubble Tea aplikacija koja pruža interaktivno iskustvo čarobnjaka i orkestrira Python CLI putem `uvx`. Svaki paket ima nezavisne CI/CD pipeline-ove.

## Doprinos

Doprinosi su dobrodošli. Molimo [otvorite issue](https://github.com/SkeneTechnologies/skene/issues) ili pošaljite [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licenca

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
