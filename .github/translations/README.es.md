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


Skene es un conjunto de herramientas de análisis de código para el crecimiento impulsado por el producto. Escanea tu código, detecta oportunidades de crecimiento y genera planes de implementación accionables.

## Inicio rápido

Instala y lanza la interfaz de terminal interactiva:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

El asistente te guía a través de la selección de proveedor, la autenticación y el análisis — no se necesita ninguna configuración previa.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Qué hace

- **Detección de la pila tecnológica** -- identifica frameworks, bases de datos, autenticación, despliegue
- **Descubrimiento de funciones de crecimiento** -- encuentra flujos de registro existentes, compartir, invitaciones, facturación
- **Registro de funciones** -- rastrea funciones a través de las ejecuciones de análisis y las vincula a los bucles de crecimiento
- **Análisis de fugas de ingresos** -- detecta monetización faltante y niveles de precios débiles
- **Generación de planes de crecimiento** -- produce bucles de crecimiento priorizados con hojas de ruta de implementación
- **Prompts de implementación** -- crea prompts listos para usar para Cursor, Claude u otras herramientas de IA
- **Despliegue de telemetría** -- genera migraciones de Supabase y las envía al upstream
- **Validación de bucles** -- verifica que los requisitos de los bucles de crecimiento estén implementados
- **Chat interactivo** -- haz preguntas sobre tu código en la terminal

Compatible con OpenAI, Gemini, Claude, LM Studio, Ollama y cualquier endpoint compatible con OpenAI. Auditoría local gratuita disponible sin necesidad de clave API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Instalación

### Interfaz de terminal (recomendada)

La TUI es un asistente interactivo que te guía a través de todo el flujo de trabajo. Sin requisitos previos — el instalador se encarga de todo.

```bash
# Instalar la TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Lanzarla
skene
```

### CLI de Python

Si prefieres la línea de comandos, puedes ejecutar Skene directamente con `uvx` (sin necesidad de instalación) o instalarlo globalmente:

```bash
# Instalar uv (si no lo tienes)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ejecutar directamente (sin instalación)
uvx skene

# O instalar globalmente
pip install skene
```

Para detalles sobre el uso de la CLI, consulta la [documentación](https://www.skene.ai/resources/docs/skene).

## Estructura del monorepo

| Directorio | Descripción | Lenguaje | Distribución |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + motor de análisis | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Asistente interactivo de interfaz de terminal | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin de Cursor IDE | — | — |

La TUI (`tui/`) es una aplicación Bubble Tea que proporciona una experiencia de asistente interactivo y orquesta la CLI de Python a través de `uvx`. Cada paquete tiene sus propios pipelines de CI/CD independientes.

## Contribuir

Las contribuciones son bienvenidas. Por favor [abre un issue](https://github.com/SkeneTechnologies/skene/issues) o envía un [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Licencia

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
