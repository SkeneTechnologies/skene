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


Skene é um kit de ferramentas de análise de código focado em crescimento liderado por produto. Ele escaneia sua base de código, identifica oportunidades de crescimento e gera planos de implementação prontos para executar.

## Início rápido

Instale e abra a interface de terminal interativa:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

O assistente guia você pela escolha do provedor, autenticação e análise — sem precisar de configuração prévia.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## O que ele faz

- **Detecção de stack tecnológico** -- identifica frameworks, bancos de dados, autenticação e deploy
- **Descoberta de recursos de crescimento** -- encontra fluxos de cadastro, compartilhamento, convites e cobrança já existentes
- **Registro de recursos** -- rastreia recursos entre execuções de análise e os conecta a growth loops
- **Análise de perda de receita** -- aponta monetização ausente e faixas de preço fracas
- **Geração de plano de crescimento** -- produz growth loops priorizados com roteiros de implementação
- **Prompts de implementação** -- monta prompts prontos para usar no Cursor, Claude ou outras ferramentas de IA
- **Deploy de telemetria** -- gera migrações Supabase e envia para o upstream
- **Validação de loops** -- verifica se os requisitos do growth loop foram implementados
- **Chat interativo** -- faça perguntas sobre sua base de código direto no terminal

Suporta OpenAI, Gemini, Claude, LM Studio, Ollama e qualquer endpoint compatível com OpenAI. Auditoria local gratuita disponível, sem precisar de chave de API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Instalação

### Interface de terminal (recomendada)

A TUI é um assistente interativo que conduz você por todo o fluxo de trabalho. Sem pré-requisitos — o instalador cuida de tudo.

```bash
# Instalar a TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Iniciar
skene
```

### CLI em Python

Se preferir a linha de comando, você pode rodar o Skene diretamente com `uvx` (sem precisar instalar nada) ou instalá-lo globalmente:

```bash
# Instalar uv (se você não tiver)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Executar diretamente (sem necessidade de instalação)
uvx skene

# Ou instalar globalmente
pip install skene
```

Para detalhes de uso da CLI, consulte a [documentação](https://www.skene.ai/resources/docs/skene).

## Estrutura do monorepo

| Diretório | Descrição | Linguagem | Distribuição |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + motor de análise | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Assistente interativo de terminal | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin para Cursor IDE | — | — |

A TUI (`tui/`) é um app Bubble Tea que oferece uma experiência de assistente interativo e orquestra a CLI em Python via `uvx`. Cada pacote tem pipelines de CI/CD independentes.

## Contribuindo

Contribuições são bem-vindas. [Abra uma issue](https://github.com/SkeneTechnologies/skene/issues) ou envie um [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licença

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
