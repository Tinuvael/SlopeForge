from __future__ import annotations

from ui.pages.block_overview_widgets import (
    BlockAttachmentPreview,
    BlockGeometryCard,
    BlockNotesCard,
    BlockRecentActivityCard,
    BlockRelatedEntityList,
)


class ContourAttachmentPreview(BlockAttachmentPreview):
    """Contour attachment preview with the stabilized Block sidebar behaviour."""


class ContourGeometryCard(BlockGeometryCard):
    """Contour plan card using the same stable dimensions as Production Block."""


class ContourNotesCard(BlockNotesCard):
    """Contour Notes card using the same compact scrollable editor viewport."""


class ContourRecentActivityCard(BlockRecentActivityCard):
    """Contour activity preview with four fixed-height history slots."""


class ContourRelatedEntityList(BlockRelatedEntityList):
    """Contour related Assessment Areas with the same row geometry and styling."""
