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


Skene on koodipohjan analyysityökalu tuotevetoiseen kasvuun. Se skannaa koodipohjaasi, löytää kasvumahdollisuuksia ja tuottaa toimintakelpoisia toteutussuunnitelmia.

## Pikaopas

Asenna ja käynnistä interaktiivinen terminaalikäyttöliittymä:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Ohjattu toiminto opastaa sinut palveluntarjoajan valinnan, todennuksen ja analyysin läpi — etukäteiskonfigurointia ei tarvita.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Mitä se tekee

- **Teknologiapinon tunnistus** -- tunnistaa sovelluskehykset, tietokannat, todennuksen, käyttöönoton
- **Kasvuominaisuuksien löytäminen** -- löytää olemassa olevat rekisteröitymisvirrat, jakamisen, kutsut, laskutuksen
- **Ominaisuusrekisteri** -- seuraa ominaisuuksia analyysiajojen välillä, yhdistää ne kasvusilmukoihin
- **Tuottomenetysanalyysi** -- löytää puuttuvan monetisoinnin ja heikot hinnoittelutasot
- **Kasvusuunnitelmien luonti** -- tuottaa priorisoidut kasvusilmukat toteutuksen tiekartan kanssa
- **Toteutuskehotteet** -- rakentaa käyttövalmiit kehotteet Cursor-, Claude- tai muille tekoälytyökaluille
- **Telemetrian käyttöönotto** -- luo Supabase-migraatiot ja työntää ne ylävirtaan
- **Silmukan validointi** -- varmistaa, että kasvusilmukan vaatimukset on toteutettu
- **Interaktiivinen keskustelu** -- kysy kysymyksiä koodipohjastasi terminaalissa

Tukee OpenAI-, Gemini-, Claude-, LM Studio-, Ollama- ja mitä tahansa OpenAI-yhteensopivaa päätepistettä. Ilmainen paikallinen tarkastus saatavilla ilman API-avainta.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Asennus

### Terminaalikäyttöliittymä (suositeltu)

TUI on interaktiivinen opas, joka ohjaa sinut koko työnkulun läpi. Ei esivaatimuksia — asennusohjelma hoitaa kaiken.

```bash
# Asenna TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Käynnistä se
skene
```

### Python CLI

Jos suosit komentoriviä, voit ajaa Skene-ohjelmaa suoraan `uvx`-komennolla (asennusta ei tarvita) tai asentaa sen globaalisti:

```bash
# Asenna uv (jos sinulla ei ole sitä)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Aja suoraan (asennusta ei tarvita)
uvx skene

# Tai asenna globaalisti
pip install skene
```

CLI-käytön yksityiskohdat löydät [dokumentaatiosta](https://www.skene.ai/resources/docs/skene).

## Monorepo-rakenne

| Kansio | Kuvaus | Kieli | Jakelu |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analysointimoottori | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Interaktiivinen terminaalikäyttöliittymäopas | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE -laajennus | — | — |

TUI (`tui/`) on Bubble Tea -sovellus, joka tarjoaa interaktiivisen ohjatun kokemuksen ja ohjaa Python CLI:tä `uvx`-komennon kautta. Jokaisella paketilla on itsenäiset CI/CD-putket.

## Osallistuminen

Osallistuminen on tervetullutta. [Luo ongelmaraportti](https://github.com/SkeneTechnologies/skene/issues) tai lähetä [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Lisenssi

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
