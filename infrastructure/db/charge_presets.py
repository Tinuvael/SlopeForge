from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from database.models import ChargeDesignPreset as Row
from domain.blasting.charge_design import ChargeComponentKind
from domain.blasting.charge_presets import ChargeDesignPreset, ChargePresetComponent

def _domain(row):
    return ChargeDesignPreset(row.id, row.site_id, row.name,
        [ChargePresetComponent(kind=ChargeComponentKind(item["kind"]),
            start_depth_m=item["start_depth_m"], end_depth_m=item["end_depth_m"],
            source_product_id=item.get("source_product_id"), cartridge_pitch_m=item.get("cartridge_pitch_m"))
         for item in row.components_json], row.created_at, row.updated_at)
def _json(items):
    return [{"kind": i.kind.value, "start_depth_m": i.start_depth_m, "end_depth_m": i.end_depth_m,
             "source_product_id": i.source_product_id, "cartridge_pitch_m": i.cartridge_pitch_m}
            for i in items]

class SqlAlchemyChargePresetRepository:
    def __init__(self, session_factory): self.session_factory = session_factory
    def list_for_site(self, site_id):
        with self.session_factory() as session:
            return [_domain(row) for row in session.scalars(select(Row).where(Row.site_id==site_id).order_by(Row.name, Row.id))]
    def create(self, preset):
        return self._write(Row(site_id=preset.site_id, name=preset.name, components_json=_json(preset.components)))
    def update(self, preset):
        with self.session_factory() as session:
            row=session.get(Row,preset.id)
            if row is None or row.site_id != preset.site_id: raise LookupError("Charge preset was not found")
            row.name=preset.name; row.components_json=_json(preset.components)
            return self._commit(session,row)
    def delete(self,preset_id,site_id):
        with self.session_factory() as session:
            row=session.get(Row,preset_id)
            if row is None or row.site_id != site_id: raise LookupError("Charge preset was not found")
            session.delete(row); session.commit()
    def _write(self,row):
        with self.session_factory() as session:
            session.add(row); return self._commit(session,row)
    def _commit(self,session,row):
        try:
            session.flush(); result=_domain(row); session.commit(); return result
        except IntegrityError as exc:
            session.rollback(); raise ValueError("A charge preset with this name already exists in the Project") from exc
