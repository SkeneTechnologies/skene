# Integrating skene Docs into the Skene Website

This guide explains how to add the skene documentation to the existing Next.js site at `www.skene.ai` (source: `skene-dashboard`).

## URL structure

The skene docs should live at `/resources/docs/skene/` as a new section alongside the existing dashboard docs at `/resources/docs/`.

### File mapping

| Markdown source | Next.js page | URL |
|----------------|-------------|-----|
| `docs/index.md` | `app/(landing)/resources/docs/skene/page.tsx` | `/resources/docs/skene` |
| `docs/getting-started/installation.md` | `.../skene/getting-started/installation/page.tsx` | `/resources/docs/skene/getting-started/installation` |
| `docs/getting-started/quickstart.md` | `.../skene/getting-started/quickstart/page.tsx` | `/resources/docs/skene/getting-started/quickstart` |
| `docs/guides/analyze.md` | `.../skene/guides/analyze/page.tsx` | `/resources/docs/skene/guides/analyze` |
| `docs/guides/plan.md` | `.../skene/guides/plan/page.tsx` | `/resources/docs/skene/guides/plan` |
| `docs/guides/build.md` | `.../skene/guides/build/page.tsx` | `/resources/docs/skene/guides/build` |
| `docs/guides/chat.md` | `.../skene/guides/chat/page.tsx` | `/resources/docs/skene/guides/chat` |
| `docs/guides/llm-providers.md` | `.../skene/guides/llm-providers/page.tsx` | `/resources/docs/skene/guides/llm-providers` |
| `docs/guides/configuration.md` | `.../skene/guides/configuration/page.tsx` | `/resources/docs/skene/guides/configuration` |
| `docs/integrations/mcp-server.md` | `.../skene/integrations/mcp-server/page.tsx` | `/resources/docs/skene/integrations/mcp-server` |
| `docs/reference/cli.md` | `.../skene/reference/cli/page.tsx` | `/resources/docs/skene/reference/cli` |
| `docs/reference/python-api.md` | `.../skene/reference/python-api/page.tsx` | `/resources/docs/skene/reference/python-api` |
| `docs/reference/manifest-schema.md` | `.../skene/reference/manifest-schema/page.tsx` | `/resources/docs/skene/reference/manifest-schema` |
| `docs/troubleshooting.md` | `.../skene/troubleshooting/page.tsx` | `/resources/docs/skene/troubleshooting` |

## Creating Next.js pages

Each markdown file should be converted to a `page.tsx` following the pattern in `app/(landing)/resources/docs/getting-started/page.tsx`. Here is the template:

```tsx
import type { Metadata } from "next";
import Link from "next/link";

const PAGE_PATH = "/resources/docs/skene/getting-started/installation";
const SITE_URL = "https://www.skene.ai";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "Installation | skene Docs | Skene",
  description: "How to install skene using uvx, pip, or from source.",
  alternates: {
    canonical: `${SITE_URL}${PAGE_PATH}`,
  },
};

function jsonLd() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: "Resources", item: `${SITE_URL}/resources` },
          { "@type": "ListItem", position: 3, name: "Docs", item: `${SITE_URL}/resources/docs` },
          { "@type": "ListItem", position: 4, name: "skene", item: `${SITE_URL}/resources/docs/skene` },
          { "@type": "ListItem", position: 5, name: "Installation", item: `${SITE_URL}${PAGE_PATH}` },
        ],
      },
      {
        "@type": "WebPage",
        name: "Installation | skene Docs",
        description: "How to install skene using uvx, pip, or from source.",
        url: `${SITE_URL}${PAGE_PATH}`,
      },
    ],
  };
}

// Reusable components (or import from shared module)

function Callout({ type, children }: { type: "info" | "tip" | "warning"; children: React.ReactNode }) {
  const styles = {
    info: "border-primary/40 bg-primary/5 text-primary",
    tip: "border-green-500/40 bg-green-500/5 text-green-400",
    warning: "border-amber-500/40 bg-amber-500/5 text-amber-400",
  };
  return (
    <div className={`rounded-lg border p-4 my-4 ${styles[type]}`}>
      {children}
    </div>
  );
}

function Step({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="relative pl-10 pb-8 border-l border-border/40 ml-4">
      <div className="absolute -left-4 top-0 w-8 h-8 rounded-full bg-primary/10 border border-primary/40 flex items-center justify-center text-sm font-bold text-primary">
        {number}
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      {children}
    </div>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre className="bg-[#0a0a0a] border border-border/40 rounded-lg p-4 overflow-x-auto my-4">
      <code className="text-sm font-mono text-muted-foreground">{code}</code>
    </pre>
  );
}

export default function InstallationPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd()) }}
      />
      <article className="max-w-3xl">
        <div className="mb-8">
          <p className="text-sm text-muted-foreground mb-2">3 min read</p>
          <h1 className="text-3xl font-bold text-foreground mb-4">Installation</h1>
          <p className="text-lg text-muted-foreground">
            How to install skene using uvx, pip, or from source.
          </p>
        </div>

        {/* Convert markdown content to JSX here */}

      </article>
    </>
  );
}
```

### Conversion notes

- Markdown headings (`## Section`) become `<h2>`, `<h3>`, etc. with Tailwind classes
- Code blocks become `<CodeBlock code="..." />` components
- Prerequisite boxes become `<Callout type="info">` or `<Callout type="warning">`
- Step-by-step instructions become `<Step number={1} title="...">` components
- Internal links map to Next.js `<Link href="/resources/docs/skene/...">` paths
- Tables use standard HTML `<table>` with Tailwind styling

## Sidebar navigation

Create a layout at `app/(landing)/resources/docs/skene/layout.tsx` following the existing `layout.tsx` pattern.

Define the navigation items:

```tsx
import {
  BookOpen,
  Download,
  Zap,
  Search,
  Map,
  Hammer,
  MessageSquare,
  Cpu,
  Settings,
  Plug,
  Terminal,
  Code,
  FileJson,
  HelpCircle,
} from "lucide-react";

const docsNavItems = [
  { href: "/resources/docs/skene", label: "Overview", icon: BookOpen },
  { href: "/resources/docs/skene/getting-started/installation", label: "Installation", icon: Download },
  { href: "/resources/docs/skene/getting-started/quickstart", label: "Quickstart", icon: Zap },
  { href: "/resources/docs/skene/guides/analyze", label: "Analyze", icon: Search },
  { href: "/resources/docs/skene/guides/plan", label: "Plan", icon: Map },
  { href: "/resources/docs/skene/guides/build", label: "Build", icon: Hammer },
  { href: "/resources/docs/skene/guides/chat", label: "Chat", icon: MessageSquare },
  { href: "/resources/docs/skene/guides/llm-providers", label: "LLM Providers", icon: Cpu },
  { href: "/resources/docs/skene/guides/configuration", label: "Configuration", icon: Settings },
  { href: "/resources/docs/skene/integrations/mcp-server", label: "MCP Server", icon: Plug },
  { href: "/resources/docs/skene/reference/cli", label: "CLI Reference", icon: Terminal },
  { href: "/resources/docs/skene/reference/python-api", label: "Python API", icon: Code },
  { href: "/resources/docs/skene/reference/manifest-schema", label: "Manifest Schema", icon: FileJson },
  { href: "/resources/docs/skene/troubleshooting", label: "Troubleshooting", icon: HelpCircle },
];
```

The layout should follow the exact same structure as the existing docs layout:
- `'use client'` directive
- Mobile: `<details>/<summary>` collapsible dropdown
- Desktop: Fixed left sidebar (`hidden md:block`, sticky)
- Active state: `text-primary` + `bg-primary/10` based on current pathname
- Auto-generated prev/next navigation at the bottom of each page

## Linking from existing docs

Add a link to the skene docs from the main docs landing page or sidebar. Options:

1. Add a "skene CLI" entry to the existing `docsNavItems` in the main docs layout, linking to `/resources/docs/skene`
2. Add a card/section on the docs landing page pointing to the CLI documentation

## Metadata patterns

Each page needs:

- **title**: `"Page Title | skene Docs | Skene"`
- **description**: The one-sentence summary from the top of each markdown file
- **canonical URL**: `https://www.skene.ai/resources/docs/skene/[path]`
- **JSON-LD BreadcrumbList**: Home > Resources > Docs > skene > [Section] > [Page]
- **JSON-LD WebPage**: name, description, url

## Styling reference

Match the existing dark theme:

| Element | Tailwind class |
|---------|---------------|
| Page background | `bg-[#060606]` |
| Borders | `border-border/40` |
| Primary text | `text-foreground` |
| Secondary text | `text-muted-foreground` |
| Active nav item | `text-primary bg-primary/10` |
| Container | `container mx-auto px-4 sm:px-6 lg:px-8` |
| Info callout | `border-primary/40 bg-primary/5` |
| Tip callout | `border-green-500/40 bg-green-500/5` |
| Warning callout | `border-amber-500/40 bg-amber-500/5` |
| Code blocks | `bg-[#0a0a0a] border-border/40` |

## Shared components

Consider extracting `Callout`, `Step`, and `CodeBlock` into shared components at `components/docs/` so they can be reused across both the dashboard docs and skene docs. The existing dashboard docs define these inline in each page — extracting them would reduce duplication.
