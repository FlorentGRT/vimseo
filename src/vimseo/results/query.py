# Copyright 2021 IRT Saint Exupery, https://www.irt-saintexupery.com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""The queries selecting results from their summaries.

A query is a string with the syntax of :meth:`pandas.DataFrame.query`, evaluated on the
table of the summaries of the results, one row per result::

    `inputs.height` > 45 and (`outputs.reaction_forces` < -3000 or load_case == 'ThreePoints')

The variables are written ``inputs.{name}`` and ``outputs.{name}`` between backticks,
the metadata by their names, e.g. ``model_name``, ``status``, ``load_case``. The
operators are ``and``, ``or``, ``not``, the comparisons and ``in``, with parentheses.

The query is evaluated the same way for both archives. For an MLflow archive, the
comparisons joined by ``and`` at the top of the query are also translated to an MLflow
filter by :func:`to_mlflow_filter`, so that the server sends fewer runs: MLflow does
not support ``or``.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pandas import DataFrame

_BACKTICKED = re.compile(r"`([^`]+)`")
"""The pattern of a name between backticks."""

_MLFLOW_OPERATORS = {
    ast.Eq: "=",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}
"""The comparison operators supported by the filters of MLflow."""


def apply_query(summaries: DataFrame, query: str) -> DataFrame:
    """Select the summaries matching a query.

    The query is evaluated on the table only: it cannot read a Python variable
    (``@name``) and it is never passed to ``eval``.

    Args:
        summaries: The summaries, one row per result.
        query: The query. If empty, all the summaries are kept.

    Returns:
        The selected summaries.

    Raises:
        ValueError: If the query is malformed or reads a Python variable.
    """
    if not query.strip():
        return summaries
    if "@" in _BACKTICKED.sub("", query):
        msg = f"The query {query!r} cannot read Python variables (@name)."
        raise ValueError(msg)
    if summaries.empty:
        return summaries
    try:
        return summaries.query(query, engine="python", local_dict={}, global_dict={})
    except Exception as error:  # ruff: ignore[blind-except]
        msg = f"The query {query!r} cannot be evaluated: {error}"
        raise ValueError(msg) from error


def _split_conjunction(node: ast.expr) -> list[ast.expr]:
    """Return the terms of a conjunction, or the node itself."""
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        return [term for value in node.values for term in _split_conjunction(value)]
    return [node]


def to_mlflow_filter(query: str, name_to_mlflow: Mapping[str, str]) -> str:
    """Translate the conjunctive part of a query to an MLflow filter.

    Only the comparisons joined by ``and`` at the top of the query, between a name
    known by ``name_to_mlflow`` and a number or a string, are translated; the others
    are left to :func:`apply_query`. The result is a superset of the matches, never a
    subset.

    Args:
        query: The query.
        name_to_mlflow: The MLflow names of the columns of the summaries, e.g.
            ``{"inputs.height": "metrics.`inputs.height`"}``.

    Returns:
        The MLflow filter, empty if nothing can be translated.
    """
    if not query.strip():
        return ""
    names = {}

    def to_identifier(match: re.Match) -> str:
        identifier = f"_column_{len(names)}"
        names[identifier] = match.group(1)
        return identifier

    try:
        tree = ast.parse(_BACKTICKED.sub(to_identifier, query), mode="eval")
    except SyntaxError:
        return ""

    filters = []
    for term in _split_conjunction(tree.body):
        if not (
            isinstance(term, ast.Compare)
            and len(term.ops) == 1
            and type(term.ops[0]) in _MLFLOW_OPERATORS
            and isinstance(term.left, ast.Name)
            and isinstance(term.comparators[0], ast.Constant)
        ):
            continue
        name = names.get(term.left.id, term.left.id)
        value = term.comparators[0].value
        if name not in name_to_mlflow or isinstance(value, bool):
            continue
        mlflow_name = name_to_mlflow[name]
        is_metric = mlflow_name.startswith("metrics.")
        if is_metric != isinstance(value, (int, float)):
            continue
        operator = _MLFLOW_OPERATORS[type(term.ops[0])]
        if not is_metric and operator not in ("=", "!="):
            continue
        literal = repr(value) if is_metric else "'{}'".format(value.replace("'", ""))
        filters.append(f"{mlflow_name} {operator} {literal}")
    return " and ".join(filters)
