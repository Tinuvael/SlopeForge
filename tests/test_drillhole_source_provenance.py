from pathlib import Path


def test_canonical_drillholes_keep_source_attributes_and_files():
    domain = Path("domain/blasting/drillholes.py").read_text(encoding="utf-8")
    service = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    storage = Path("infrastructure/files/drillhole_geometry.py").read_text(encoding="utf-8")
    assert '"source_attributes"' in domain
    assert 'attrs.setdefault("source_file", line.source_file)' in domain
    assert "source_files=[item.to_dict() for item in stored_files]" in service
    assert '"sha256"' in storage
