from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from application.errors import CatalogueConflictError
from database.models import ChargeDesignPreset as PresetRow
from domain.blasting.charge_design import ChargeDesignPreset, ChargePresetComponent


def _domain(row):
    return ChargeDesignPreset(row.id, row.site_id, row.name, tuple(ChargePresetComponent(**item) for item in row.components_json))


class SqlAlchemyChargePresetPersistence:
    def __init__(self, session_factory): self._session_factory = session_factory
    def list_presets(self, site_id):
        with self._session_factory() as session:
            return [_domain(row) for row in session.scalars(select(PresetRow).where(PresetRow.site_id == site_id).order_by(PresetRow.name)).all()]
    @staticmethod
    def _json(components):
        return [dict(kind=item.kind.value, start_depth_m=item.start_depth_m, end_depth_m=item.end_depth_m,
            source_product_id=item.source_product_id, cartridge_pitch_m=item.cartridge_pitch_m) for item in components]
    def create_preset(self, site_id, name, components):
        return self._write(lambda s: PresetRow(site_id=site_id, name=name, components_json=self._json(components)))
    def update_preset(self, preset_id, site_id, name, components):
        def operation(session):
            row=session.get(PresetRow,preset_id)
            if row is None or row.site_id != site_id: raise LookupError("Charge preset was not found")
            row.name=name; row.components_json=self._json(components); return row
        return self._write(operation)
    def delete_preset(self, preset_id, site_id):
        with self._session_factory() as session:
            row=session.get(PresetRow,preset_id)
            if row is None or row.site_id != site_id: raise LookupError("Charge preset was not found")
            session.delete(row); session.commit()
    def _write(self, operation):
        with self._session_factory() as session:
            try:
                row=operation(session); session.add(row); session.flush(); result=_domain(row); session.commit(); return result
            except IntegrityError as exc:
                session.rollback(); raise CatalogueConflictError("A charge preset with this name already exists") from exc
