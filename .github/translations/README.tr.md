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


Skene, ürün odaklı büyüme için tasarlanmış bir kod tabanı analiz araç setidir. Kod tabanınızı tarar, büyüme fırsatlarını tespit eder ve hayata geçirilebilir uygulama planları üretir.

## Hızlı başlangıç

Etkileşimli terminal arayüzünü kurun ve başlatın:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Sihirbaz; sağlayıcı seçimi, kimlik doğrulama ve analiz sürecinde size yol gösterir — önceden yapılandırmaya gerek yok.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Ne yapar

- **Teknoloji yığını tespiti** -- framework'leri, veritabanlarını, kimlik doğrulamayı ve dağıtımı tanımlar
- **Büyüme özelliklerinin keşfi** -- mevcut kayıt akışlarını, paylaşımı, davetleri ve faturalandırmayı bulur
- **Özellik kayıt defteri** -- özellikleri analiz çalışmaları boyunca takip eder ve büyüme döngülerine bağlar
- **Gelir kaçağı analizi** -- eksik kalan gelir fırsatlarını ve zayıf fiyatlandırma katmanlarını tespit eder
- **Büyüme planı oluşturma** -- uygulama yol haritalarıyla birlikte önceliklendirilmiş büyüme döngüleri üretir
- **Uygulama promptları** -- Cursor, Claude ya da diğer yapay zekâ araçları için kullanıma hazır promptlar üretir
- **Telemetri dağıtımı** -- Supabase migrasyonları üretir ve upstream'e gönderir
- **Döngü doğrulama** -- büyüme döngüsü gereksinimlerinin uygulanıp uygulanmadığını doğrular
- **Etkileşimli sohbet** -- terminalde kod tabanınız hakkında soru sorun

OpenAI, Gemini, Claude, LM Studio, Ollama ve OpenAI ile uyumlu herhangi bir uç noktayı destekler. API anahtarı gerektirmeyen ücretsiz yerel denetim de mevcuttur.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Kurulum

### Terminal arayüzü (önerilen)

TUI, tüm iş akışında size rehberlik eden etkileşimli bir sihirbazdır. Ön koşul yok — yükleyici her şeyi halleder.

```bash
# TUI'yi kur
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Başlat
skene
```

### Python CLI

Komut satırını tercih ediyorsanız, Skene'i doğrudan `uvx` ile çalıştırabilir (kurulum gerekmez) veya global olarak kurabilirsiniz:

```bash
# uv'yi kur (eğer yoksa)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Doğrudan çalıştır (kurulum gerekmez)
uvx skene

# Veya global olarak kur
pip install skene
```

CLI kullanım detayları için [dokümantasyona](https://www.skene.ai/resources/docs/skene) bakın.

## Monorepo yapısı

| Dizin | Açıklama | Dil | Dağıtım |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + analiz motoru | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Etkileşimli terminal arayüzü sihirbazı | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE eklentisi | — | — |

TUI (`tui/`), etkileşimli bir sihirbaz deneyimi sunan ve Python CLI'yi `uvx` aracılığıyla yöneten bir Bubble Tea uygulamasıdır. Her paketin bağımsız CI/CD süreçleri vardır.

## Katkıda bulunma

Katkılarınızı bekliyoruz. Bir [issue açabilir](https://github.com/SkeneTechnologies/skene/issues) ya da [pull request](https://github.com/SkeneTechnologies/skene/pulls) gönderebilirsiniz.

## Lisans

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
