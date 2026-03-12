# Manifest Schema Reference

Complete JSON schema reference for growth manifests produced by skene analysis.

## Overview

skene outputs a structured JSON file called `growth-manifest.json` that captures everything discovered during codebase analysis. There are two schema versions:

| Version | Schema | Description |
|---------|--------|-------------|
| **1.0** | `GrowthManifest` | Standard PLG analysis output. Contains tech stack, growth features, opportunities, and revenue leakage. |
| **2.0** | `DocsManifest` | Extended manifest for documentation generation. Inherits all v1.0 fields and adds `product_overview` and `features`. |

The `analyze` command produces a v1.0 manifest by default. When run with the `--product-docs` flag (or via the `generate_manifest` MCP tool with `product_docs: true`), it produces a v2.0 manifest instead.

Both versions are defined as Pydantic models in `src/skene/manifest/schema.py`.

## v1.0 Manifest Example (GrowthManifest)

```json
{
  "version": "1.0",
  "project_name": "my-saas-app",
  "description": "A SaaS application for team collaboration",
  "tech_stack": {
    "framework": "Next.js",
    "language": "TypeScript",
    "database": "PostgreSQL",
    "auth": "NextAuth.js",
    "deployment": "Vercel",
    "package_manager": "npm",
    "services": ["Stripe", "SendGrid"]
  },
  "industry": {
    "primary": "Productivity",
    "secondary": ["B2B", "SaaS", "Enterprise"],
    "confidence": 0.85,
    "evidence": [
      "README mentions 'team collaboration' as primary use case",
      "Target audience includes 'businesses' and 'teams'"
    ]
  },
  "current_growth_features": [
    {
      "feature_name": "Team Invitations",
      "file_path": "src/features/invitations/index.ts",
      "detected_intent": "Viral growth through team expansion",
      "confidence_score": 0.85,
      "entry_point": "/invite",
      "growth_potential": [
        "Add referral tracking",
        "Implement invite rewards"
      ]
    }
  ],
  "growth_opportunities": [
    {
      "feature_name": "Analytics Dashboard",
      "description": "No usage analytics for tracking team activity",
      "priority": "high"
    }
  ],
  "revenue_leakage": [
    {
      "issue": "Free tier allows unlimited usage without conversion prompts",
      "file_path": "src/pricing/tiers.py",
      "impact": "high",
      "recommendation": "Add usage limits or upgrade prompts to encourage paid conversions"
    }
  ],
  "generated_at": "2025-01-15T10:30:00"
}
```

## v2.0 Manifest Example (DocsManifest)

A v2.0 manifest includes all v1.0 fields plus `product_overview` and `features`:

```json
{
  "version": "2.0",
  "project_name": "my-saas-app",
  "description": "A SaaS application for team collaboration",
  "tech_stack": {
    "framework": "Next.js",
    "language": "TypeScript",
    "database": "PostgreSQL",
    "auth": "NextAuth.js",
    "deployment": "Vercel",
    "package_manager": "npm",
    "services": ["Stripe", "SendGrid"]
  },
  "industry": {
    "primary": "Productivity",
    "secondary": ["B2B", "SaaS", "Enterprise"],
    "confidence": 0.85,
    "evidence": [
      "README mentions 'team collaboration' as primary use case",
      "Target audience includes 'businesses' and 'teams'"
    ]
  },
  "current_growth_features": [
    {
      "feature_name": "Team Invitations",
      "file_path": "src/features/invitations/index.ts",
      "detected_intent": "Viral growth through team expansion",
      "confidence_score": 0.85,
      "entry_point": "/invite",
      "growth_potential": [
        "Add referral tracking",
        "Implement invite rewards"
      ]
    }
  ],
  "growth_opportunities": [
    {
      "feature_name": "Analytics Dashboard",
      "description": "No usage analytics for tracking team activity",
      "priority": "high"
    }
  ],
  "revenue_leakage": [
    {
      "issue": "Free tier allows unlimited usage without conversion prompts",
      "file_path": "src/pricing/tiers.py",
      "impact": "high",
      "recommendation": "Add usage limits or upgrade prompts to encourage paid conversions"
    }
  ],
  "product_overview": {
    "tagline": "Team collaboration that scales with your organization",
    "value_proposition": "Simplifies cross-team communication and project tracking, reducing coordination overhead by 40%",
    "target_audience": "Engineering and product teams at mid-size B2B companies"
  },
  "features": [
    {
      "name": "Real-time Chat",
      "description": "Instant messaging with threading, mentions, and emoji reactions",
      "file_path": "src/features/chat/index.ts",
      "usage_example": "import { ChatProvider } from '@/features/chat'",
      "category": "Communication"
    },
    {
      "name": "Project Boards",
      "description": "Kanban-style boards for tracking tasks and milestones",
      "file_path": "src/features/boards/index.ts",
      "usage_example": null,
      "category": "Project Management"
    }
  ],
  "generated_at": "2025-01-15T10:30:00"
}
```

## Field Reference

### GrowthManifest (top-level, v1.0)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `string` | No (default: `"1.0"`) | Manifest schema version. |
| `project_name` | `string` | Yes | Name of the analyzed project. |
| `description` | `string \| null` | No | Brief description of the project. |
| `tech_stack` | `TechStack` | Yes | Detected technology stack. |
| `industry` | `IndustryInfo \| null` | No | Inferred industry/market vertical classification. |
| `current_growth_features` | `GrowthFeature[]` | No (default: `[]`) | Identified current features with growth potential. |
| `growth_opportunities` | `GrowthOpportunity[]` | No (default: `[]`) | Growth opportunities to address. |
| `revenue_leakage` | `RevenueLeakage[]` | No (default: `[]`) | Potential revenue leakage issues. |
| `generated_at` | `datetime` | No (auto-set) | When the manifest was generated. Always overwritten to current machine time. |

### DocsManifest (additional fields, v2.0)

Inherits all `GrowthManifest` fields above. The `version` field defaults to `"2.0"`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | `string` | No (default: `"2.0"`) | Manifest schema version for docs-enabled manifests. |
| `product_overview` | `ProductOverview \| null` | No | High-level product overview for documentation. |
| `features` | `Feature[]` | No (default: `[]`) | User-facing feature documentation. |

### TechStack

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `framework` | `string \| null` | No | Primary framework (e.g., `"Next.js"`, `"FastAPI"`, `"Rails"`). |
| `language` | `string` | Yes | Primary programming language (e.g., `"Python"`, `"TypeScript"`). |
| `database` | `string \| null` | No | Database technology (e.g., `"PostgreSQL"`, `"MongoDB"`). |
| `auth` | `string \| null` | No | Authentication method (e.g., `"JWT"`, `"OAuth"`, `"Clerk"`). |
| `deployment` | `string \| null` | No | Deployment platform (e.g., `"Vercel"`, `"AWS"`, `"Docker"`). |
| `package_manager` | `string \| null` | No | Package manager (e.g., `"npm"`, `"poetry"`, `"cargo"`). |
| `services` | `string[]` | No (default: `[]`) | Third-party services and integrations (e.g., `"Stripe"`, `"SendGrid"`, `"Twilio"`). |

### GrowthFeature

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `feature_name` | `string` | Yes | Name of the feature or growth area. |
| `file_path` | `string` | Yes | Primary file path where this feature is implemented. |
| `detected_intent` | `string` | Yes | Detected purpose or intent of the feature. |
| `confidence_score` | `float` | Yes | Confidence in the detection, between `0.0` and `1.0`. |
| `entry_point` | `string \| null` | No | Entry point for users (e.g., URL path, function name). |
| `growth_potential` | `string[]` | No (default: `[]`) | List of growth opportunities specific to this feature. |
| `loop_ids` | `string[]` | No (default: `[]`) | IDs of growth loops linked to this feature (populated by the feature registry). |
| `growth_pillars` | `string[]` | No (default: `[]`) | 0-3 growth pillars: `"onboarding"`, `"engagement"`, `"retention"`. |

### GrowthOpportunity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `feature_name` | `string` | Yes | Name of the missing feature or opportunity. |
| `description` | `string` | Yes | Description of what is missing and why it matters. |
| `priority` | `"high" \| "medium" \| "low"` | Yes | Priority level for addressing this opportunity. |

### RevenueLeakage

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issue` | `string` | Yes | Description of the revenue leakage issue. |
| `file_path` | `string \| null` | No | File path where this issue is detected (if applicable). |
| `impact` | `"high" \| "medium" \| "low"` | Yes | Estimated impact on revenue. |
| `recommendation` | `string` | Yes | Recommendation for addressing this issue. |

### IndustryInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `primary` | `string \| null` | No | Primary industry vertical (e.g., `"DevTools"`, `"FinTech"`, `"E-commerce"`). |
| `secondary` | `string[]` | No (default: `[]`) | Supporting tags for sub-verticals or go-to-market nuance (e.g., `"B2B"`, `"SaaS"`). |
| `confidence` | `float \| null` | No | Confidence score between `0.0` and `1.0` for the classification. |
| `evidence` | `string[]` | No (default: `[]`) | Short bullets citing specific repo signals that support the classification. |

### ProductOverview (v2.0 only)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tagline` | `string \| null` | No | Short one-liner describing the product (under 15 words). |
| `value_proposition` | `string \| null` | No | What problem the product solves and why it matters. |
| `target_audience` | `string \| null` | No | Who the product is for (e.g., developers, businesses). |

### Feature (v2.0 only)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Human-readable feature name. |
| `description` | `string` | Yes | User-facing description of what the feature does. |
| `file_path` | `string \| null` | No | Primary file where this feature is implemented. |
| `usage_example` | `string \| null` | No | Code snippet or usage example. |
| `category` | `string \| null` | No | Feature category (e.g., `"Authentication"`, `"API"`, `"UI"`). |

## Validation

Use the `validate` command to check that a manifest file conforms to the schema:

```bash
uvx skene validate ./growth-manifest.json
# Or using the shorthand:
uvx skene validate ./growth-manifest.json
```

The command parses the JSON and validates it against the `GrowthManifest` Pydantic model. On success, it prints a summary table showing the project name, version, tech stack language, and counts of growth features and opportunities. On failure, it prints the validation error and exits with code 1.

Note that `validate` uses the v1.0 `GrowthManifest` schema. Since `DocsManifest` (v2.0) inherits from `GrowthManifest`, a v2.0 manifest will also pass v1.0 validation -- the extra `product_overview` and `features` fields are simply ignored.

## How Manifests Are Generated

There are two ways to generate a manifest:

### 1. The `analyze` CLI command

The primary way to generate a manifest is through the `analyze` command:

```bash
# Generate a v1.0 GrowthManifest
uvx skene analyze .

# Generate a v2.0 DocsManifest (includes product_overview and features)
uvx skene analyze . --product-docs
```

By default, the manifest is written to `./skene-context/growth-manifest.json`. You can change the output path with the `--output` flag:

```bash
uvx skene analyze . --output ./my-manifest.json
```

### 2. The `generate_manifest` MCP tool

When using skene as an [MCP server](../integrations/mcp-server.md), the `generate_manifest` tool produces the same output programmatically. It accepts pre-computed analysis results for individual phases (tech stack, industry, features) or auto-analyzes any missing phases. Set the `product_docs` parameter to `true` to generate a v2.0 `DocsManifest`.

## Notes on `generated_at`

The `generated_at` field is always overwritten to the current machine time via a Pydantic model validator, regardless of what value the LLM provides during analysis. This ensures the timestamp accurately reflects when the manifest was created on your system.
