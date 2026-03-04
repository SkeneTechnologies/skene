"""
Pydantic schemas for growth manifest output.

These models define the structure of growth-manifest.json, which captures:
- Tech stack detection
- Current growth features identification
- Growth opportunities
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TechStack(BaseModel):
    """Detected technology stack of the project."""

    framework: str | None = Field(
        default=None,
        description="Primary framework (e.g., 'Next.js', 'FastAPI', 'Rails')",
    )
    language: str = Field(
        description="Primary programming language (e.g., 'Python', 'TypeScript')",
    )
    database: str | None = Field(
        default=None,
        description="Database technology (e.g., 'PostgreSQL', 'MongoDB')",
    )
    auth: str | None = Field(
        default=None,
        description="Authentication method (e.g., 'JWT', 'OAuth', 'Clerk')",
    )
    deployment: str | None = Field(
        default=None,
        description="Deployment platform (e.g., 'Vercel', 'AWS', 'Docker')",
    )
    package_manager: str | None = Field(
        default=None,
        description="Package manager (e.g., 'npm', 'poetry', 'cargo')",
    )
    services: list[str] = Field(
        default_factory=list,
        description="Third-party services and integrations (e.g., 'Stripe', 'SendGrid', 'Twilio')",
    )


class GrowthFeature(BaseModel):
    """A current feature with growth potential."""

    feature_name: str = Field(
        description="Name of the feature or growth area",
    )
    file_path: str = Field(
        description="Primary file path where this feature is implemented",
    )
    detected_intent: str = Field(
        description="Detected purpose or intent of the feature",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the detection (0.0-1.0)",
    )
    entry_point: str | None = Field(
        default=None,
        description="Entry point for users (e.g., URL path, function name)",
    )
    growth_potential: list[str] = Field(
        default_factory=list,
        description="List of growth opportunities for this feature",
    )
    growth_pillars: list[str] = Field(
        default_factory=list,
        description="Growth pillars: onboarding, engagement, retention (0-3)",
    )
    loop_ids: list[str] = Field(
        default_factory=list,
        description="IDs of loops that implement or enhance this feature",
    )


class GrowthOpportunity(BaseModel):
    """A growth opportunity or missing feature."""

    feature_name: str = Field(
        description="Name of the missing feature or opportunity",
    )
    description: str = Field(
        description="Description of what's missing and why it matters",
    )
    priority: Literal["high", "medium", "low"] = Field(
        description="Priority level for addressing this opportunity",
    )
    growth_pillars: list[str] = Field(
        default_factory=list,
        description="Growth pillars: onboarding, engagement, retention (0-3)",
    )


class RevenueLeakage(BaseModel):
    """Potential revenue leakage issue."""

    issue: str = Field(
        description="Description of the revenue leakage issue",
    )
    file_path: str | None = Field(
        default=None,
        description="File path where this issue is detected (if applicable)",
    )
    impact: Literal["high", "medium", "low"] = Field(
        description="Estimated impact on revenue",
    )
    recommendation: str = Field(
        description="Recommendation for addressing this issue",
    )


class IndustryInfo(BaseModel):
    """Industry/market vertical classification for the project."""

    primary: str | None = Field(
        default=None,
        description="Primary industry vertical (e.g., 'DevTools', 'FinTech', 'E-commerce', 'Healthcare', 'EdTech')",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="Supporting tags for sub-verticals or go-to-market nuance (e.g., 'B2B', 'SaaS', 'Marketplace')",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) for the classification",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Short bullets citing specific repo signals that support the classification",
    )


class ProductOverview(BaseModel):
    """High-level product information for documentation."""

    tagline: str | None = Field(
        default=None,
        description="Short one-liner describing the product (under 15 words)",
    )
    value_proposition: str | None = Field(
        default=None,
        description="What problem the product solves and why it matters",
    )
    target_audience: str | None = Field(
        default=None,
        description="Who the product is for (e.g., developers, businesses)",
    )


class Feature(BaseModel):
    """User-facing feature documentation."""

    name: str = Field(
        description="Human-readable feature name",
    )
    description: str = Field(
        description="User-facing description of what the feature does",
    )
    file_path: str | None = Field(
        default=None,
        description="Primary file where this feature is implemented",
    )
    usage_example: str | None = Field(
        default=None,
        description="Code snippet or usage example",
    )
    category: str | None = Field(
        default=None,
        description="Feature category (e.g., 'Authentication', 'API', 'UI')",
    )


class GrowthManifest(BaseModel):
    """
    Complete growth manifest for a project.

    This is the primary output of PLG analysis, capturing everything
    needed to understand a project's growth potential.
    """

    version: str = Field(
        default="1.0",
        description="Manifest schema version",
    )
    project_name: str = Field(
        description="Name of the analyzed project",
    )
    description: str | None = Field(
        default=None,
        description="Brief description of the project",
    )
    tech_stack: TechStack = Field(
        description="Detected technology stack",
    )
    industry: IndustryInfo | None = Field(
        default=None,
        description="Inferred industry/market vertical classification",
    )
    current_growth_features: list[GrowthFeature] = Field(
        default_factory=list,
        description="Identified current growth features",
    )
    growth_opportunities: list[GrowthOpportunity] = Field(
        default_factory=list,
        description="Growth opportunities to address",
    )
    revenue_leakage: list[RevenueLeakage] = Field(
        default_factory=list,
        description="Potential revenue leakage issues",
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the manifest was generated",
    )

    @model_validator(mode="after")
    def set_generated_at_to_now(self) -> "GrowthManifest":
        """Always set generated_at to current machine time, ignoring LLM-provided values."""
        object.__setattr__(self, "generated_at", datetime.now())
        return self

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
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
                    "services": ["Stripe", "SendGrid"],
                },
                "industry": {
                    "primary": "Productivity",
                    "secondary": ["B2B", "SaaS", "Enterprise"],
                    "confidence": 0.85,
                    "evidence": [
                        "README mentions 'team collaboration' as primary use case",
                        "Target audience includes 'businesses' and 'teams'",
                    ],
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
                            "Implement invite rewards",
                        ],
                    }
                ],
                "growth_opportunities": [
                    {
                        "feature_name": "Analytics Dashboard",
                        "description": "No usage analytics for tracking team activity",
                        "priority": "high",
                    }
                ],
                "revenue_leakage": [
                    {
                        "issue": "Free tier allows unlimited usage without conversion prompts",
                        "file_path": "src/pricing/tiers.py",
                        "impact": "high",
                        "recommendation": "Add usage limits or upgrade prompts to encourage paid conversions",
                    }
                ],
                "generated_at": "2024-01-15T10:30:00Z",
            }
        },
    )


class DocsManifest(GrowthManifest):
    """
    Extended manifest with documentation-specific fields.

    Inherits all GrowthManifest fields and adds:
    - product_overview: High-level product description
    - features: User-facing feature documentation
    """

    version: str = Field(
        default="2.0",
        description="Manifest schema version (2.0 for docs-enabled)",
    )
    product_overview: ProductOverview | None = Field(
        default=None,
        description="High-level product overview",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="User-facing feature documentation",
    )
