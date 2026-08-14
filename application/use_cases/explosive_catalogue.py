from __future__ import annotations

from dataclasses import replace
from domain.blasting.charge_design import ExplosiveProduct
from application.ports.explosive_catalogue import ExplosiveCatalogueQueries, ExplosiveCatalogueWrites


class ExplosiveCatalogue:
    def __init__(self, queries: ExplosiveCatalogueQueries, writes: ExplosiveCatalogueWrites,
                 *, can_edit: bool):
        self._queries, self._writes, self._can_edit = queries, writes, can_edit

    def list_products(self) -> list[ExplosiveProduct]:
        return self._queries.list_products()

    def list_enabled_products(self) -> list[ExplosiveProduct]:
        return self._queries.list_products(enabled_only=True)

    def get_product(self, product_id: int) -> ExplosiveProduct | None:
        return self._queries.get_product(product_id)

    def _require_edit(self) -> None:
        if not self._can_edit:
            raise PermissionError("Explosive catalogue is read-only for the current user")

    def create_product(self, product: ExplosiveProduct) -> ExplosiveProduct:
        self._require_edit()
        return self._writes.create_product(replace(product, id=0))

    def update_product(self, product: ExplosiveProduct) -> ExplosiveProduct:
        self._require_edit()
        # ExplosiveProduct is intentionally editable in catalogue forms.  Rebuild
        # it at the application boundary so direct mutations cannot bypass its
        # domain validation before reaching persistence.
        validated = replace(product)
        return self._writes.update_product(validated)

    def set_product_enabled(self, product_id: int, enabled: bool) -> ExplosiveProduct:
        self._require_edit()
        return self._writes.set_product_enabled(product_id, enabled)
