"""Output file writing utilities."""

from pathlib import Path

from skene.output import success, warning


def write_product_docs(manifest_data: dict, manifest_path: Path) -> None:
    """Generate and save product documentation alongside analysis output.

    Args:
        manifest_data: The manifest data dict
        manifest_path: Path to the growth-manifest.json (used to determine output location)
    """
    from skene.docs import DocsGenerator
    from skene.manifest import DocsManifest, GrowthManifest

    try:
        # Parse manifest (DocsManifest for v2.0, GrowthManifest otherwise)
        if manifest_data.get("version") == "2.0" or "product_overview" in manifest_data or "features" in manifest_data:
            manifest = DocsManifest.model_validate(manifest_data)
        else:
            manifest = GrowthManifest.model_validate(manifest_data)
    except Exception as exc:
        warning(f"Failed to parse manifest for product docs: {exc}")
        return

    output_dir = manifest_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    product_docs_path = output_dir / "product-docs.md"

    try:
        generator = DocsGenerator()
        product_content = generator.generate_product_docs(manifest)
        product_docs_path.write_text(product_content)
        success(f"Product docs saved to: {product_docs_path}")
    except Exception as exc:
        warning(f"Failed to generate product docs: {exc}")


async def write_growth_template(llm, manifest_data: dict, manifest_path: Path | None = None) -> dict | None:
    """Generate and save the growth template JSON output.

    Args:
        llm: LLM client
        manifest_data: Manifest data
        manifest_path: Path to the manifest file (template will be saved to same directory)

    Returns:
        Template data dict if successful, None if failed
    """
    from skene.templates import generate_growth_template, write_growth_template_outputs

    try:
        template_data = await generate_growth_template(llm, manifest_data)
        # Save template to the same directory as the manifest
        if manifest_path:
            output_dir = manifest_path.parent
        else:
            from skene.output_paths import DEFAULT_OUTPUT_DIR

            output_dir = Path(DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = write_growth_template_outputs(template_data, output_dir)
        success(f"Growth template saved to: {json_path}")
        return template_data
    except Exception as exc:
        warning(f"Failed to generate growth template: {exc}")
        return None
