"""
Documentation generator using growth manifests.

Generates markdown documentation from GrowthManifest data using Jinja2 templates.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from skene.manifest import GrowthManifest


class DocsGenerator:
    """
    Generates documentation from a GrowthManifest.

    Uses Jinja2 templates to produce various documentation formats:
    - Context documents (for AI/LLM consumption)
    - Product documentation
    - SEO-optimized pages

    Example:
        generator = DocsGenerator()
        docs = generator.generate_context(manifest)
        generator.write_to_file(docs, "skene/context.md")

        # Or generate all docs at once
        generator.generate_all(manifest, output_dir="./skene-docs")
    """

    def __init__(self, templates_dir: Path | str | None = None):
        """
        Initialize the docs generator.

        Args:
            templates_dir: Custom templates directory. If None, uses built-in templates.
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"
        else:
            templates_dir = Path(templates_dir)

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_context(self, manifest: GrowthManifest) -> str:
        """
        Generate a context document for AI/LLM consumption.

        This document provides structured context about the project
        that can be used by AI tools for code generation, analysis, etc.

        Args:
            manifest: The growth manifest to generate docs from

        Returns:
            Markdown content as string
        """
        template = self.env.get_template("analysis.md.j2")
        return template.render(manifest=manifest, **self._get_context_vars(manifest))

    def generate_analysis(self, manifest: GrowthManifest) -> str:
        """
        Generate a markdown analysis summary from the manifest.

        Args:
            manifest: The growth manifest to generate docs from

        Returns:
            Markdown content as string
        """
        template = self.env.get_template("analysis.md.j2")
        return template.render(manifest=manifest, **self._get_context_vars(manifest))

    def generate_growth_template(self, template_data: dict[str, Any]) -> str:
        """
        Generate markdown from a growth template JSON.

        Automatically detects template structure and uses appropriate Jinja template:
        - If template has 'lifecycles' key -> uses plg_lifecycle_template.md.j2
        - Otherwise -> uses growth_template.md.j2 (legacy format)

        Args:
            template_data: The growth template data to render

        Returns:
            Markdown content as string
        """
        # Detect template structure
        if "lifecycles" in template_data:
            # New PLG lifecycle template with milestones and metrics
            template = self.env.get_template("plg_lifecycle_template.md.j2")
        else:
            # Legacy template with visuals and keywordMappings
            template = self.env.get_template("growth_template.md.j2")

        return template.render(template=template_data)

    def generate_product_docs(self, manifest: GrowthManifest) -> str:
        """
        Generate product documentation.

        Creates human-readable documentation about the project's
        features, tech stack, and growth opportunities.

        Args:
            manifest: The growth manifest to generate docs from

        Returns:
            Markdown content as string
        """
        template = self.env.get_template("product_docs.md.j2")
        return template.render(manifest=manifest, **self._get_context_vars(manifest))

    def generate_seo_page(
        self,
        manifest: GrowthManifest,
        topic: str,
        keywords: list[str] | None = None,
    ) -> str:
        """
        Generate an SEO-optimized page.

        Creates content optimized for search engines based on
        the project's current growth features and capabilities.

        Args:
            manifest: The growth manifest to generate docs from
            topic: The topic/title for the SEO page
            keywords: Optional list of keywords to target

        Returns:
            Markdown content as string
        """
        template = self.env.get_template("seo_page.md.j2")
        return template.render(
            manifest=manifest,
            topic=topic,
            keywords=keywords or [],
            **self._get_context_vars(manifest),
        )

    def generate_all(
        self,
        manifest: GrowthManifest,
        output_dir: Path | str,
    ) -> dict[str, Path]:
        """
        Generate all documentation types and write to files.

        Args:
            manifest: The growth manifest to generate docs from
            output_dir: Directory to write documentation to

        Returns:
            Dictionary mapping doc type to file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        files_written = {}

        # Generate context document
        context_content = self.generate_context(manifest)
        context_path = output_dir / "context.md"
        context_path.write_text(context_content)
        files_written["context"] = context_path

        # Generate product docs
        product_content = self.generate_product_docs(manifest)
        product_path = output_dir / "product_docs.md"
        product_path.write_text(product_content)
        files_written["product_docs"] = product_path

        return files_written

    def write_to_file(self, content: str, path: Path | str) -> Path:
        """
        Write generated content to a file.

        Args:
            content: The content to write
            path: File path to write to

        Returns:
            The path that was written to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def _get_context_vars(self, manifest: GrowthManifest) -> dict[str, Any]:
        """Get common context variables for templates."""
        current_features = manifest.current_growth_features
        opportunities = manifest.growth_opportunities

        context = {
            "project_name": manifest.project_name,
            "description": manifest.description,
            "tech_stack": manifest.tech_stack,
            "current_growth_features": current_features,
            "growth_opportunities": opportunities,
            "generated_at": manifest.generated_at,
            "feature_count": len(current_features),
            "opportunity_count": len(opportunities),
            "high_priority_opportunities": [g for g in opportunities if g.priority == "high"],
        }

        # Add docs-specific fields if available (DocsManifest)
        if hasattr(manifest, "product_overview"):
            context["product_overview"] = manifest.product_overview
        if hasattr(manifest, "features"):
            context["features"] = manifest.features

        # Add industry classification if available
        if hasattr(manifest, "industry"):
            context["industry"] = manifest.industry

        return context
