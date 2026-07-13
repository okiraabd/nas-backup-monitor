"""Shared helper for building bulk-delete WHERE conditions.

Both the logs and reports routers accept "delete by IDs and/or by period"
requests. The way the SQLAlchemy conditions are assembled is identical; only
the columns and how each router derives the date bounds differ. This helper
captures that common shape so the two endpoints stay in sync.
"""
from sqlalchemy import and_, or_
from sqlalchemy.sql.elements import ColumnElement


def build_bulk_delete_conditions(
    *,
    id_column,
    ids: list[int] | None,
    date_column,
    date_from=None,
    date_to=None,
) -> list[ColumnElement]:
    """Return WHERE conditions for a bulk delete by IDs and/or a date range.

    - IDs alone -> ``id IN (...)``.
    - A date range alone -> ``date >= from`` and/or ``date <= to``.
    - Both -> additive: ``id IN (...) OR (date range)`` so either set matches.

    The caller is responsible for rejecting the empty-filter case and for
    normalizing ``date_from``/``date_to`` (e.g. converting local calendar days
    to UTC bounds) before calling this helper.
    """
    date_conditions: list[ColumnElement] = []
    if date_from is not None:
        date_conditions.append(date_column >= date_from)
    if date_to is not None:
        date_conditions.append(date_column <= date_to)

    if date_conditions:
        if ids:
            # ID selection and period selection are additive: delete either set.
            return [or_(id_column.in_(ids), and_(*date_conditions))]
        return date_conditions

    if ids:
        return [id_column.in_(ids)]

    return []
