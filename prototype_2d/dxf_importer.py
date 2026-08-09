"""Import supported DXF modelspace polylines as ordinary Datamine lines."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from math import isclose

from .models import DatamineLine, DataminePoint


class DxfImportError(ValueError):
    pass


@dataclass
class DxfImportSummary:
    file_name: str
    format: str = "DXF"
    line_count: int = 0
    polyline_2d_count: int = 0
    polyline_3d_count: int = 0
    lwpolyline_count: int = 0
    total_vertices: int = 0
    skipped_unsupported_entity_count: int = 0
    layers: list[str] = field(default_factory=list)


@dataclass
class DxfImportResult:
    lines: list[DatamineLine]
    summary: DxfImportSummary


def _same_xyz(a, b, tolerance: float = 1e-9) -> bool:
    return all(isclose(float(x), float(y), abs_tol=tolerance, rel_tol=0.0) for x, y in zip(a, b))


def import_dxf_polylines(path: str | Path) -> DxfImportResult:
    """Read straight LWPOLYLINE/2D POLYLINE/3D POLYLINE entities from modelspace."""
    try:
        import ezdxf
        from ezdxf.lldxf.const import (
            POLYLINE_CURVE_FIT_VERTICES_ADDED,
            POLYLINE_SPLINE_FIT_VERTICES_ADDED,
        )
    except ImportError as exc:  # dependency error, not an import workaround
        raise DxfImportError("ezdxf is required to import DXF geometry") from exc

    source_path = Path(path)
    try:
        document = ezdxf.readfile(source_path)
    except (OSError, ezdxf.DXFError) as exc:
        raise DxfImportError(f"Could not read DXF: {exc}") from exc

    summary = DxfImportSummary(source_path.name)
    lines: list[DatamineLine] = []
    layers: set[str] = set()
    curved_message = ("Curved DXF polyline segments are not supported. "
                      "Convert them to straight polyline segments before import.")
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        mode = entity_type
        if entity_type == "LWPOLYLINE":
            if any(abs(float(bulge)) > 1e-12 for (bulge,) in entity.get_points("b")):
                raise DxfImportError(curved_message)
            vertices = list(entity.vertices_in_wcs())
            closed = bool(entity.closed)
            summary.lwpolyline_count += 1
        elif entity_type == "POLYLINE":
            mode = entity.get_mode()
            if mode not in {"AcDb2dPolyline", "AcDb3dPolyline"}:
                summary.skipped_unsupported_entity_count += 1
                continue
            fitted_curve_flags = (
                POLYLINE_CURVE_FIT_VERTICES_ADDED
                | POLYLINE_SPLINE_FIT_VERTICES_ADDED
            )
            if int(entity.dxf.get("flags", 0)) & fitted_curve_flags:
                raise DxfImportError(curved_message)
            if mode == "AcDb2dPolyline" and any(abs(float(v.dxf.get("bulge", 0))) > 1e-12 for v in entity.vertices):
                raise DxfImportError(curved_message)
            vertices = list(entity.points_in_wcs())
            closed = bool(entity.is_closed)
            if mode == "AcDb3dPolyline":
                summary.polyline_3d_count += 1
            else:
                summary.polyline_2d_count += 1
        else:
            summary.skipped_unsupported_entity_count += 1
            continue

        imported_order = len(lines) + 1
        handle = entity.dxf.get("handle", None)
        layer = str(entity.dxf.get("layer", "0"))
        source_id = str(handle) if handle else f"DXF-{imported_order:06d}"
        xyz = [(float(v.x), float(v.y), float(v.z)) for v in vertices]
        if closed and xyz and not _same_xyz(xyz[0], xyz[-1]):
            xyz.append(xyz[0])
        points = [DataminePoint(x, y, z, index, extra_values={
            "dxf_entity_type": entity_type, "dxf_handle": handle,
            "dxf_layer": layer, "dxf_polyline_mode": mode,
        }) for index, (x, y, z) in enumerate(xyz, start=1)]
        lines.append(DatamineLine(source_id, points, source_type=layer, assigned_type=layer,
                                  source_file=str(source_path), import_order=imported_order))
        summary.total_vertices += len(points)
        layers.add(layer)

    summary.line_count = len(lines)
    summary.layers = sorted(layers)
    return DxfImportResult(lines, summary)
