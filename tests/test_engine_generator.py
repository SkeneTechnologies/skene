from pathlib import Path

from skene.engine import generator


def test_resolve_schema_prefers_skene_yaml(tmp_path: Path):
    skene_dir = tmp_path / "skene"
    skene_context_dir = tmp_path / "skene-context"
    skene_dir.mkdir(parents=True)
    skene_context_dir.mkdir(parents=True)
    (skene_dir / "schema.yaml").write_text("tables: []", encoding="utf-8")
    (skene_context_dir / "schema.md").write_text("# schema", encoding="utf-8")

    resolved = generator._resolve_schema_path(tmp_path)
    assert resolved == skene_dir / "schema.yaml"


def test_resolve_schema_uses_skene_context_when_skene_missing(tmp_path: Path):
    skene_context_dir = tmp_path / "skene-context"
    skene_context_dir.mkdir(parents=True)
    (skene_context_dir / "schema.md").write_text("# schema", encoding="utf-8")

    resolved = generator._resolve_schema_path(tmp_path)
    assert resolved == skene_context_dir / "schema.md"


def test_load_schema_context_warns_when_schema_missing(tmp_path: Path, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(generator, "warning", warnings.append)

    source, content = generator._load_schema_context(tmp_path)

    assert source == "not found"
    assert content == ""
    assert warnings == [generator.SCHEMA_NOT_FOUND_WARNING]


def test_load_schema_context_reads_content(tmp_path: Path, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(generator, "warning", warnings.append)
    schema_path = tmp_path / "skene-context" / "schema.yaml"
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text("version: 1\n", encoding="utf-8")

    source, content = generator._load_schema_context(tmp_path)

    assert source == str(schema_path)
    assert content == "version: 1"
    assert warnings == []
