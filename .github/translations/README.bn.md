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


Skene হলো পণ্য-নেতৃত্বাধীন প্রবৃদ্ধির জন্য একটি কোডবেস বিশ্লেষণ টুলকিট। এটি আপনার কোডবেস স্ক্যান করে, প্রবৃদ্ধির সুযোগ শনাক্ত করে এবং কার্যকর বাস্তবায়ন পরিকল্পনা তৈরি করে।

## দ্রুত শুরু

ইনস্টল করুন এবং ইন্টারেক্টিভ টার্মিনাল UI চালু করুন:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

উইজার্ড আপনাকে প্রোভাইডার নির্বাচন, প্রমাণীকরণ এবং বিশ্লেষণের মধ্য দিয়ে নিয়ে যায় — আগে থেকে কোনো কনফিগারেশনের প্রয়োজন নেই।

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## এটি কী করে

- **টেক স্ট্যাক শনাক্তকরণ** -- ফ্রেমওয়ার্ক, ডেটাবেস, প্রমাণীকরণ এবং ডিপ্লয়মেন্ট চিহ্নিত করে
- **গ্রোথ ফিচার আবিষ্কার** -- বিদ্যমান সাইনআপ ফ্লো, শেয়ারিং, ইনভাইট, বিলিং খুঁজে বের করে
- **ফিচার রেজিস্ট্রি** -- বিশ্লেষণ রান জুড়ে ফিচার ট্র্যাক করে, গ্রোথ লুপের সাথে সংযুক্ত করে
- **রেভিনিউ লিকেজ বিশ্লেষণ** -- অনুপস্থিত মনিটাইজেশন এবং দুর্বল প্রাইসিং টিয়ার চিহ্নিত করে
- **গ্রোথ প্ল্যান তৈরি** -- বাস্তবায়ন রোডম্যাপসহ অগ্রাধিকারভিত্তিক গ্রোথ লুপ তৈরি করে
- **ইমপ্লিমেন্টেশন প্রম্পট** -- Cursor, Claude বা অন্যান্য AI টুলের জন্য ব্যবহারযোগ্য প্রম্পট তৈরি করে
- **টেলিমেট্রি ডিপ্লয়মেন্ট** -- Supabase মাইগ্রেশন তৈরি করে এবং আপস্ট্রিমে পুশ করে
- **লুপ ভ্যালিডেশন** -- গ্রোথ লুপের প্রয়োজনীয়তা বাস্তবায়িত হয়েছে কিনা যাচাই করে
- **ইন্টারেক্টিভ চ্যাট** -- টার্মিনালে আপনার কোডবেস সম্পর্কে প্রশ্ন করুন

OpenAI, Gemini, Claude, LM Studio, Ollama এবং যেকোনো OpenAI-সামঞ্জস্যপূর্ণ এন্ডপয়েন্ট সমর্থন করে। কোনো API কী ছাড়াই বিনামূল্যে লোকাল অডিট উপলব্ধ।

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## ইনস্টলেশন

### টার্মিনাল UI (প্রস্তাবিত)

TUI হলো একটি ইন্টারেক্টিভ উইজার্ড যা আপনাকে সম্পূর্ণ ওয়ার্কফ্লোর মধ্য দিয়ে গাইড করে। কোনো পূর্বশর্ত নেই — ইনস্টলার সবকিছু সামলায়।

```bash
# TUI ইনস্টল করুন
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# এটি চালু করুন
skene
```

### Python CLI

আপনি যদি কমান্ড লাইন পছন্দ করেন, তাহলে `uvx` দিয়ে সরাসরি Skene চালাতে পারেন (ইনস্টলের প্রয়োজন নেই) অথবা গ্লোবালি ইনস্টল করতে পারেন:

```bash
# uv ইনস্টল করুন (যদি না থাকে)
curl -LsSf https://astral.sh/uv/install.sh | sh

# সরাসরি চালান (ইনস্টলের প্রয়োজন নেই)
uvx skene

# অথবা গ্লোবালি ইনস্টল করুন
pip install skene
```

CLI ব্যবহারের বিস্তারিত জানতে, [ডকুমেন্টেশন](https://www.skene.ai/resources/docs/skene) দেখুন।

## মনোরিপো কাঠামো

| ডিরেক্টরি | বিবরণ | ভাষা | বিতরণ |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + বিশ্লেষণ ইঞ্জিন | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | ইন্টারেক্টিভ টার্মিনাল UI উইজার্ড | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Cursor IDE প্লাগইন | — | — |

TUI (`tui/`) হলো একটি Bubble Tea অ্যাপ যা একটি ইন্টারেক্টিভ উইজার্ড অভিজ্ঞতা প্রদান করে এবং `uvx`-এর মাধ্যমে Python CLI পরিচালনা করে। প্রতিটি প্যাকেজের স্বতন্ত্র CI/CD পাইপলাইন রয়েছে।

## অবদান

অবদান স্বাগত। অনুগ্রহ করে একটি [ইস্যু খুলুন](https://github.com/SkeneTechnologies/skene/issues) অথবা একটি [পুল রিকোয়েস্ট](https://github.com/SkeneTechnologies/skene/pulls) জমা দিন।

## লাইসেন্স

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
