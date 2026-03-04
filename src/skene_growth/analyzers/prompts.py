"""
Prompt templates for PLG analysis.

These are basic, open-source prompts designed for general use.
Premium prompts with higher quality output can override these
in closed-source implementations.
"""

# Tech Stack Detection Prompt
TECH_STACK_PROMPT = """
Analyze the provided files (configuration files and source files) to detect the technology stack used in this project.

IMPORTANT: When determining the **Language**, prioritize actual source files over configuration files.
For example, if you see Python source files (.py) but only a package.json config file,
the language is Python, not JavaScript.
Look at file extensions and code syntax in source files to determine the primary language.

Focus on identifying:
1. **Framework**: The primary web/app framework (e.g., Next.js, FastAPI, Rails, Django)
2. **Language**: The main programming language (e.g., Python, TypeScript, Go) - DETERMINE FROM SOURCE FILES,
   not just config files
3. **Database**: Database technology if detectable (e.g., PostgreSQL, MongoDB, Redis)
4. **Auth**: Authentication method or library (e.g., JWT, OAuth, NextAuth, Clerk)
5. **Deployment**: Deployment platform or method (e.g., Vercel, AWS, Docker, Kubernetes, Netlify)
6. **Package Manager**: Package manager used (e.g., npm, yarn, poetry, cargo)
7. **Services**: Third-party services and integrations used in the project

For **Services**, look for dependencies and environment variables indicating:
- Payment processors: Stripe, PayPal, Paddle, LemonSqueezy
- Email services: SendGrid, Mailgun, Postmark, Resend
- Analytics: Segment, Mixpanel, Amplitude, PostHog
- Monitoring: Sentry, DataDog, New Relic, LogRocket
- Communication: Twilio, Plivo
- Search: Algolia, Elasticsearch, Typesense
- Storage: AWS S3, Cloudflare R2, Cloudinary
- Other SaaS integrations

Return your analysis as JSON matching this structure:
{
    "framework": "string or null",
    "language": "string (required)",
    "database": "string or null",
    "auth": "string or null",
    "deployment": "string or null",
    "package_manager": "string or null",
    "services": ["array of service names"]
}

Be conservative - only include values you're confident about. Use null for uncertain fields.
Return an empty array for services if none are detected.
"""


# Current Growth Features Detection Prompt
def build_growth_features_prompt(existing_loops_summary: str = "") -> str:
    """Build growth features prompt with optional existing loops context."""
    base_prompt = """
Analyze the provided source files and identify current features with growth potential.

A "current growth feature" is an existing feature in the codebase that:
- Enables viral growth (sharing, invitations, referrals)
- Drives user engagement (notifications, gamification, progress tracking)
- Facilitates user onboarding (tutorials, tooltips, guided flows)
- Supports monetization (payments, subscriptions, upgrades)
- Enables data-driven decisions (analytics, dashboards, reporting)
"""

    if existing_loops_summary:
        base_prompt += f"\n{existing_loops_summary}\n"

    base_prompt += """
For each growth feature you identify, provide:
1. **feature_name**: A clear name for the feature
2. **file_path**: The primary file where this feature is implemented
3. **detected_intent**: What growth purpose does this feature serve?
4. **confidence_score**: How confident are you (0.0 to 1.0)?
5. **entry_point**: URL path or function name users interact with (if identifiable)
6. **growth_potential**: List of specific improvements that could boost growth
7. **growth_pillars**: 0-3 of "onboarding", "engagement", "retention" — infer from detected_intent

Return your analysis as a JSON array of current growth features.
Focus on quality over quantity - identify the most impactful features.
"""
    return base_prompt


# Backward compatibility - default prompt without existing loops
GROWTH_FEATURES_PROMPT = build_growth_features_prompt()

# Revenue Leakage Detection Prompt
REVENUE_LEAKAGE_PROMPT = """
Analyze the provided source files and identify potential revenue leakage issues.

Revenue leakage occurs when a product or service could be generating more revenue but isn't due to:
- Missing or weak monetization strategies (free features that should be paid)
- Inadequate pricing tiers or upgrade prompts
- Features that could be monetized but are given away for free
- Missing usage limits or restrictions on free tiers
- Lack of conversion funnels from free to paid
- Missing payment processing or subscription management
- Overly generous free tiers that reduce paid conversions
- Missing premium features or add-ons
- Inefficient pricing models

For each revenue leakage issue you identify, provide:
1. **issue**: Clear description of the revenue leakage problem
2. **file_path**: File where this is detected (if applicable, null otherwise)
3. **impact**: Estimated impact level (high/medium/low)
4. **recommendation**: Specific recommendation for addressing this issue

Return your analysis as a JSON array of revenue leakage issues.
Focus on actionable issues that could realistically impact revenue.
"""


# Manifest Generation Prompt
def build_manifest_prompt(existing_loops_summary: str = "") -> str:
    """Build manifest generation prompt with optional existing loops context."""
    base_prompt = """
Generate a complete growth manifest by combining the analysis results.

You have been provided with:
- Tech stack analysis (detected technologies)
- Current growth features analysis (existing features with growth potential)
- Revenue leakage analysis (potential revenue issues)
- Industry classification (market vertical and business model tags)
"""

    if existing_loops_summary:
        base_prompt += f"\n{existing_loops_summary}\n"

    base_prompt += """
Your task is to:
1. Create a cohesive project summary
2. Include the tech stack and current growth features from the analysis
3. Include revenue leakage issues from the analysis
4. Include the industry classification from the analysis
5. Identify growth opportunities - missing features that could drive growth
"""

    if existing_loops_summary:
        base_prompt += """
**IMPORTANT:** When identifying growth opportunities, DO NOT duplicate or overlap with the existing growth loops listed above.
Focus on complementary opportunities that build on or extend the existing loops, or address entirely different growth areas.
"""  # noqa: E501

    base_prompt += """
For growth opportunities, consider what's missing:
- User onboarding flows
- Viral/sharing mechanisms
- Analytics and insights
- Monetization capabilities
- Engagement features
- Community features

Return a complete growth manifest as JSON with:
- project_name: Inferred from the codebase
- description: Brief project description
- tech_stack: From the tech stack analysis
- current_growth_features: From the growth features analysis
- revenue_leakage: From the revenue leakage analysis
- industry: From the industry classification analysis (include primary, secondary, confidence, evidence)
- growth_opportunities: Your identified opportunities with feature_name, description, priority (high/medium/low), growth_pillars (0-3 of "onboarding", "engagement", "retention")
"""
    return base_prompt


# Backward compatibility - default prompt without existing loops
MANIFEST_PROMPT = build_manifest_prompt()

# Industry Classification Prompt
INDUSTRY_PROMPT = """
Analyze the provided documentation and package metadata files to classify the industry/market vertical.

Your task is to determine what **market vertical or domain** this product serves (NOT the technology stack).

Focus on identifying:
1. **primary**: A concise industry vertical label. Common examples:
   - DevTools (developer tools, SDKs, APIs, infrastructure)
   - FinTech (payments, banking, investing, accounting)
   - E-commerce (online retail, marketplaces, product catalogs)
   - Healthcare (medical, wellness, patient management)
   - EdTech (learning, training, educational content)
   - Marketing (advertising, analytics, CRM, email marketing)
   - HR (recruiting, payroll, employee management)
   - Security (authentication, compliance, monitoring)
   - Productivity (collaboration, project management, notes)
   - Data/Analytics (business intelligence, data pipelines, visualization)
   - Media/Entertainment (streaming, content, gaming)
   - Real Estate (property, rentals, listings)
   - Logistics (shipping, supply chain, inventory)
   - Other (specify if none of the above fit)

2. **secondary**: 0-5 supporting tags for sub-verticals or business model nuance:
   - Business model: B2B, B2C, B2B2C
   - Delivery model: SaaS, On-premise, Hybrid, API-first
   - Market position: Enterprise, SMB, Startup, Consumer
   - Distribution: Marketplace, OpenSource, Freemium

3. **confidence**: A score from 0.0 to 1.0 indicating how confident you are.
   - 0.8-1.0: Clear product/domain signals in README or docs
   - 0.5-0.7: Some signals but could be interpreted differently
   - 0.0-0.4: Minimal or ambiguous signals

4. **evidence**: 2-5 short bullet points citing **specific signals** from the files:
   - Quote key phrases from README (e.g., "README mentions 'team collaboration tool'")
   - Reference package description or keywords
   - Note integration names that hint at domain (e.g., "Integrates with Shopify suggests E-commerce")
   - Mention user-facing docs headings or terminology

**Signals to look for (high to low priority):**
- README product description, tagline, "what it does", "who it's for"
- package.json description/keywords, pyproject.toml description/classifiers
- Integration names (Stripe → payments, Shopify → e-commerce, HIPAA → healthcare)
- Domain vocabulary in documentation

**IMPORTANT - Uncertainty rule:**
If the repository lacks clear product/domain signals (e.g., generic library, no README, unclear purpose),
return:
- primary: null
- secondary: []
- confidence: low (< 0.3)
- evidence: explain what signals were missing or why classification is uncertain

Return your analysis as JSON:
{
    "primary": "string or null",
    "secondary": ["array of tags"],
    "confidence": 0.0-1.0,
    "evidence": ["array of short evidence strings"]
}

Be conservative - it's better to return null with low confidence than to guess incorrectly.
"""

# Product Overview Extraction Prompt
PRODUCT_OVERVIEW_PROMPT = """
Analyze the provided documentation files to extract product overview information.

Focus on identifying:
1. **Tagline**: A short one-liner (under 15 words) that captures what the product does
2. **Value Proposition**: What problem does this solve? Why should someone use it? (2-3 sentences)
3. **Target Audience**: Who is this product for? (e.g., developers, marketers, enterprises)

Look for this information in:
- README.md introductions and first paragraphs
- Package description fields (package.json description, pyproject.toml)
- About/Overview sections
- Marketing copy in documentation

Return your analysis as JSON:
{
    "tagline": "string or null",
    "value_proposition": "string or null",
    "target_audience": "string or null"
}

Be concise but informative. Write from the perspective of explaining the product to someone new.
Use null for fields you cannot confidently determine from the provided files.
"""

# Features Documentation Prompt
FEATURES_PROMPT = """
Analyze the source files to document user-facing features.

For each major feature, provide:
1. **name**: Human-readable feature name (not code identifiers)
2. **description**: User-facing description of what it does (1-2 sentences, non-technical)
3. **file_path**: Primary implementation file
4. **usage_example**: Short code snippet or usage example (if identifiable)
5. **category**: Feature category (e.g., "Authentication", "API", "Data Management", "UI")

Focus on:
- Features users interact with directly
- Core functionality, not internal utilities or helpers
- Clear, non-technical descriptions where possible
- The value each feature provides to users

Return as a JSON array of features:
[
    {
        "name": "Feature Name",
        "description": "What this feature does for users",
        "file_path": "path/to/file.py",
        "usage_example": "optional code example",
        "category": "Category"
    }
]

Prioritize the most important 5-10 features. Quality over quantity.
"""


# Documentation Manifest Generation Prompt
def build_docs_manifest_prompt(existing_loops_summary: str = "") -> str:
    """Build documentation manifest prompt with optional existing loops context."""
    base_prompt = """
Generate a complete documentation manifest by combining all analysis results.

You have been provided with:
- Tech stack analysis (detected technologies)
- Product overview (tagline, value proposition, target audience)
- Industry classification (market vertical and business model tags)
- Features documentation (user-facing feature descriptions)
- Current growth features analysis (existing features with growth potential)
"""

    if existing_loops_summary:
        base_prompt += f"\n{existing_loops_summary}\n"

    base_prompt += """
Your task is to:
1. Create a cohesive DocsManifest combining all sections
2. Infer a project_name from the codebase structure or package files
3. Write a brief description summarizing the project
4. Include all provided analysis data including industry classification
5. Identify growth opportunities - missing features that could drive growth
"""

    if existing_loops_summary:
        base_prompt += """
**IMPORTANT:** When identifying growth opportunities, DO NOT duplicate or overlap with the existing growth loops listed above.
Focus on complementary opportunities that build on or extend the existing loops, or address entirely different growth areas.
"""  # noqa: E501

    base_prompt += """
For growth opportunities, consider what's missing:
- User onboarding flows
- Viral/sharing mechanisms
- Analytics and insights
- Monetization capabilities
- Engagement features

Return a complete manifest as JSON with:
- version: "2.0"
- project_name: Inferred from the codebase
- description: Brief project description
- tech_stack: From the tech stack analysis
- product_overview: From the product overview analysis
- industry: From the industry classification analysis (include primary, secondary, confidence, evidence)
- features: From the features documentation
- current_growth_features: From the growth features analysis
- growth_opportunities: Your identified opportunities with feature_name, description, priority, growth_pillars (0-3 of onboarding/engagement/retention)
"""
    return base_prompt


# Backward compatibility - default prompt without existing loops
DOCS_MANIFEST_PROMPT = build_docs_manifest_prompt()
