from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from application.errors import CatalogueConflictError
from database.models import ExplosiveProduct as ExplosiveProductRow
from domain.blasting.charge_design import ChargeForm, ExplosiveProduct, ExplosiveProductKind


def _domain(row: ExplosiveProductRow) -> ExplosiveProduct:
    return ExplosiveProduct(
        id=row.id, name=row.name, kind=ExplosiveProductKind(row.kind),
        display_color=row.display_color, enabled=row.is_enabled,
        density_kg_m3=float(row.density_kg_m3) if row.density_kg_m3 is not None else None,
        cartridge_diameter_mm=float(row.cartridge_diameter_mm) if row.cartridge_diameter_mm is not None else None,
        cartridge_mass_kg=float(row.cartridge_mass_kg) if row.cartridge_mass_kg is not None else None,
        default_pitch_m=float(row.default_pitch_m) if row.default_pitch_m is not None else None,
        charge_form=ChargeForm(row.charge_form),
    )


def _values(product: ExplosiveProduct) -> dict:
    return dict(name=product.name, kind=product.kind.value,
                density_kg_m3=product.density_kg_m3,
                cartridge_diameter_mm=product.cartridge_diameter_mm,
                cartridge_mass_kg=product.cartridge_mass_kg,
                display_color=product.display_color,
                default_pitch_m=product.default_pitch_m,
                is_enabled=product.enabled, charge_form=product.charge_form.value)


class SqlAlchemyExplosiveCatalogue:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def list_products(self, *, enabled_only: bool = False) -> list[ExplosiveProduct]:
        with self._session_factory() as session:
            statement = select(ExplosiveProductRow)
            if enabled_only:
                statement = statement.where(ExplosiveProductRow.is_enabled.is_(True))
            rows = session.scalars(statement.order_by(ExplosiveProductRow.name,
                                                       ExplosiveProductRow.id)).all()
            return [_domain(row) for row in rows]

    def get_product(self, product_id: int) -> ExplosiveProduct | None:
        with self._session_factory() as session:
            row = session.get(ExplosiveProductRow, product_id)
            return _domain(row) if row else None

    def create_product(self, product: ExplosiveProduct) -> ExplosiveProduct:
        row = ExplosiveProductRow(**_values(product))
        return self._write(lambda session: session.add(row), row)

    def update_product(self, product: ExplosiveProduct) -> ExplosiveProduct:
        def update(session):
            nonlocal row
            row = session.get(ExplosiveProductRow, product.id)
            if row is None:
                raise LookupError("Explosive product was not found")
            for name, value in _values(product).items():
                setattr(row, name, value)
        row = None
        return self._write(update, row_getter=lambda: row)

    def set_product_enabled(self, product_id: int, enabled: bool) -> ExplosiveProduct:
        def update(session):
            nonlocal row
            row = session.get(ExplosiveProductRow, product_id)
            if row is None:
                raise LookupError("Explosive product was not found")
            row.is_enabled = enabled
        row = None
        return self._write(update, row_getter=lambda: row)

    def _write(self, operation, row=None, row_getter=None) -> ExplosiveProduct:
        session = self._session_factory()
        try:
            operation(session)
            session.flush()
            target = row_getter() if row_getter else row
            result = _domain(target)
            session.commit()
            return result
        except IntegrityError as exc:
            session.rollback()
            raise CatalogueConflictError("An explosive product with this name already exists") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
