"""Format-neutral triangulated surface import for DXF and Datamine wireframes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from infrastructure.datamine.dmfile import DispatchFactory
from infrastructure.datamine.wireframes import (
    DatamineWireframeImportError,
    import_datamine_wireframe,
)


class SurfaceImportError(ValueError):
    pass


@dataclass(frozen=True)
class SurfaceImportResult:
    surface: TriangleSurface
    source_format: str
    source_paths: tuple[Path, ...]

    @property
    def vertex_count(self) -> int:
        return len(self.surface.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.surface.triangles)


def _same_xyz(a: tuple[float, float, float], b: tuple[float, float, float], tolerance: float = 1e-9) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(a, b))


def _dxf_entity_attributes(document: Any, entity: Any) -> dict[str, Any]:
    layer_name = str(entity.dxf.get("layer", "0"))
    raw_aci = int(entity.dxf.get("color", 256))
    true_color = entity.dxf.get("true_color", None)
    effective_aci = None
    if raw_aci == 256:  # BYLAYER
        try:
            effective_aci = abs(int(document.layers.get(layer_name).color))
        except Exception:
            effective_aci = None
    elif raw_aci not in {0, 256}:  # BYBLOCK cannot be resolved from modelspace alone
        effective_aci = abs(raw_aci)
    return {
        "dxf_entity_type": entity.dxftype(),
        "dxf_handle": entity.dxf.get("handle", None),
        "dxf_layer": layer_name,
        "dxf_raw_aci": raw_aci,
        "dxf_colour_mode": "BYLAYER" if raw_aci == 256 else "BYBLOCK" if raw_aci == 0 else "ACI",
        "dxf_effective_aci": effective_aci,
        "dxf_true_color": int(true_color) if true_color is not None else None,
    }


def _triangulate_indices(indices: Iterable[int]) -> list[tuple[int, int, int]]:
    values = list(indices)
    if len(values) < 3:
        return []
    return [(values[0], values[index], values[index + 1]) for index in range(1, len(values) - 1)]


def import_dxf_surface(path: str | Path) -> SurfaceImportResult:
    try:
        import ezdxf
    except ImportError as exc:
        raise SurfaceImportError("ezdxf is required to import DXF surfaces") from exc

    source_path = Path(path)
    try:
        document = ezdxf.readfile(source_path)
    except (OSError, ezdxf.DXFError) as exc:
        raise SurfaceImportError(f"Could not read DXF surface: {exc}") from exc

    vertices: list[SurfaceVertex] = []
    triangles: list[SurfaceTriangle] = []
    vertex_lookup: dict[tuple[float, float, float], int] = {}

    def add_vertex(value: Any) -> int:
        xyz = (float(value.x), float(value.y), float(value.z))
        if xyz not in vertex_lookup:
            vertex_lookup[xyz] = len(vertices)
            vertices.append(SurfaceVertex(*xyz))
        return vertex_lookup[xyz]

    def append_face(face_vertices: list[Any], entity: Any, source_suffix: str = "") -> None:
        xyz = [(float(value.x), float(value.y), float(value.z)) for value in face_vertices]
        if len(xyz) == 4 and _same_xyz(xyz[2], xyz[3]):
            face_vertices = face_vertices[:3]
        face_indices = [add_vertex(value) for value in face_vertices]
        attributes = _dxf_entity_attributes(document, entity)
        handle = attributes.get("dxf_handle") or f"DXF-{len(triangles) + 1}"
        for part, indices in enumerate(_triangulate_indices(face_indices), start=1):
            try:
                triangles.append(
                    SurfaceTriangle(
                        indices,
                        source_id=f"{handle}{source_suffix}:{part}",
                        source_attributes=dict(attributes),
                    )
                )
            except ValueError as exc:
                raise SurfaceImportError(f"Invalid DXF face {handle!r}: {exc}") from exc

    for entity in document.modelspace():
        entity_type = entity.dxftype()
        if entity_type == "3DFACE":
            append_face(
                [entity.dxf.vtx0, entity.dxf.vtx1, entity.dxf.vtx2, entity.dxf.vtx3],
                entity,
            )
            continue

        if entity_type == "POLYLINE" and bool(getattr(entity, "is_poly_face_mesh", False)):
            try:
                mesh_vertices, mesh_faces = entity.indexed_faces()
                mesh_vertices = list(mesh_vertices)
                for face_number, face in enumerate(mesh_faces, start=1):
                    indices_method = getattr(face, "indices", None)
                    if not callable(indices_method):
                        raise SurfaceImportError("Unsupported DXF polyface face representation")
                    face_vertices = [mesh_vertices[index].dxf.location for index in indices_method()]
                    append_face(face_vertices, entity, f":face{face_number}")
            except SurfaceImportError:
                raise
            except Exception as exc:
                raise SurfaceImportError(f"Could not read DXF polyface mesh: {exc}") from exc
            continue

        if entity_type == "MESH":
            try:
                mesh_vertices = list(entity.vertices)
                for face_number, face in enumerate(entity.faces, start=1):
                    face_vertices = [mesh_vertices[int(index)] for index in face]
                    append_face(face_vertices, entity, f":face{face_number}")
            except Exception as exc:
                raise SurfaceImportError(f"Could not read DXF MESH entity: {exc}") from exc

    if not triangles:
        raise SurfaceImportError(
            "DXF contains no supported triangulated surface entities (3DFACE, polyface POLYLINE or MESH)."
        )
    try:
        surface = TriangleSurface(
            vertices=tuple(vertices),
            triangles=tuple(triangles),
            source_files=(source_path.name,),
            source_attributes={"format": "DXF"},
        )
    except ValueError as exc:
        raise SurfaceImportError(f"Invalid DXF surface: {exc}") from exc
    return SurfaceImportResult(surface, "dxf", (source_path,))


def import_surface_geometry(
    path: str | Path,
    *,
    dispatch_factory: DispatchFactory | None = None,
) -> SurfaceImportResult:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == ".dxf":
        return import_dxf_surface(source_path)
    if suffix in {".dm", ".dmx"}:
        try:
            result = import_datamine_wireframe(source_path, dispatch_factory=dispatch_factory)
        except DatamineWireframeImportError as exc:
            raise SurfaceImportError(str(exc)) from exc
        return SurfaceImportResult(
            result.surface,
            "datamine",
            (result.triangle_path, result.point_path),
        )
    raise SurfaceImportError(
        f"Unsupported surface geometry format {suffix or '(none)'!r}. Use DXF, DM or DMX."
    )
