"""
Programmatic SEO page builder.

Generates multiple SEO-optimized pages from growth manifest data.
"""

from pathlib import Path
from typing import Any

from skene.docs.generator import DocsGenerator
from skene.manifest import GrowthManifest


class PSEOBuilder:
    """
    Builds multiple SEO-optimized pages from a GrowthManifest.

    Generates pages for:
    - Each current growth feature
    - Each technology in the stack
    - Custom topics based on keywords

    Example:
        builder = PSEOBuilder()
        pages = builder.build_all(manifest, output_dir="./seo-pages")
        print(f"Generated {len(pages)} SEO pages")
    """

    def __init__(self, generator: DocsGenerator | None = None):
        """
        Initialize the PSEO builder.

        Args:
            generator: DocsGenerator instance to use. Creates new one if None.
        """
        self.generator = generator or DocsGenerator()

    def build_feature_pages(
        self,
        manifest: GrowthManifest,
        output_dir: Path | str,
    ) -> list[Path]:
        """
        Generate SEO pages for each current growth feature.

        Args:
            manifest: The growth manifest
            output_dir: Directory to write pages to

        Returns:
            List of paths to generated pages
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for feature in manifest.current_growth_features:
            # Generate keywords from growth potential
            keywords = feature.growth_potential[:5] if feature.growth_potential else []
            keywords.append(manifest.project_name)

            content = self.generator.generate_seo_page(
                manifest=manifest,
                topic=feature.feature_name,
                keywords=keywords,
            )

            # Create slug from feature name
            slug = self._slugify(feature.feature_name)
            page_path = output_dir / f"{slug}.md"
            page_path.write_text(content)
            pages.append(page_path)

        return pages

    def build_tech_pages(
        self,
        manifest: GrowthManifest,
        output_dir: Path | str,
    ) -> list[Path]:
        """
        Generate SEO pages for each technology in the stack.

        Args:
            manifest: The growth manifest
            output_dir: Directory to write pages to

        Returns:
            List of paths to generated pages
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        tech_stack = manifest.tech_stack

        # Generate page for each non-null technology
        techs = [
            ("framework", tech_stack.framework),
            ("language", tech_stack.language),
            ("database", tech_stack.database),
            ("authentication", tech_stack.auth),
            ("deployment", tech_stack.deployment),
        ]

        for tech_type, tech_name in techs:
            if not tech_name:
                continue

            topic = f"{manifest.project_name} with {tech_name}"
            keywords = [
                tech_name,
                tech_type,
                manifest.project_name,
                f"{tech_name} {tech_type}",
            ]

            content = self.generator.generate_seo_page(
                manifest=manifest,
                topic=topic,
                keywords=keywords,
            )

            slug = self._slugify(f"{tech_type}-{tech_name}")
            page_path = output_dir / f"{slug}.md"
            page_path.write_text(content)
            pages.append(page_path)

        return pages

    def build_custom_pages(
        self,
        manifest: GrowthManifest,
        topics: list[dict[str, Any]],
        output_dir: Path | str,
    ) -> list[Path]:
        """
        Generate custom SEO pages from topic definitions.

        Args:
            manifest: The growth manifest
            topics: List of topic dicts with 'title' and optional 'keywords'
            output_dir: Directory to write pages to

        Returns:
            List of paths to generated pages
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for topic_def in topics:
            title = topic_def.get("title", "")
            keywords = topic_def.get("keywords", [])

            if not title:
                continue

            content = self.generator.generate_seo_page(
                manifest=manifest,
                topic=title,
                keywords=keywords,
            )

            slug = self._slugify(title)
            page_path = output_dir / f"{slug}.md"
            page_path.write_text(content)
            pages.append(page_path)

        return pages

    def build_all(
        self,
        manifest: GrowthManifest,
        output_dir: Path | str,
        include_features: bool = True,
        include_tech: bool = True,
    ) -> dict[str, list[Path]]:
        """
        Generate all SEO pages.

        Args:
            manifest: The growth manifest
            output_dir: Directory to write pages to
            include_features: Whether to generate feature pages
            include_tech: Whether to generate tech stack pages

        Returns:
            Dictionary mapping page type to list of paths
        """
        output_dir = Path(output_dir)
        result = {}

        if include_features:
            feature_dir = output_dir / "features"
            result["features"] = self.build_feature_pages(manifest, feature_dir)

        if include_tech:
            tech_dir = output_dir / "tech"
            result["tech"] = self.build_tech_pages(manifest, tech_dir)

        return result

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re

        # Convert to lowercase
        slug = text.lower()
        # Replace spaces and special chars with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Collapse multiple hyphens
        slug = re.sub(r"-+", "-", slug)
        return slug
