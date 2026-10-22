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

"""A dashboard exploring the model results of an archive.

Every model result of the archive is listed, whatever its study, model and load case;
the user then refines the selection from the values present in the archive.
"""

from __future__ import annotations

import streamlit as st

from vimseo.api import open_model_results
from vimseo.dashboards.model_results.model_results_viewer_model import ARCHIVE_MANAGERS
from vimseo.dashboards.model_results.model_results_viewer_model import DEFAULT_COLUMNS
from vimseo.dashboards.model_results.model_results_viewer_model import METADATA_FILTERS
from vimseo.dashboards.model_results.model_results_viewer_model import build_query
from vimseo.dashboards.model_results.model_results_viewer_model import get_values
from vimseo.dashboards.model_results.model_results_viewer_model import (
    get_variable_columns,
)
from vimseo.dashboards.model_results.model_results_viewer_model import initialize
from vimseo.dashboards.model_results.model_results_viewer_model import plot_scalars
from vimseo.dashboards.visualisation.generic_layout import generate_layout


@st.cache_resource
def _open_model_results(archive_manager: str, directory_archive_root: str):
    """Open the model results of an archive, once per archive."""
    return open_model_results(archive_manager, directory_archive_root)


def model_results_viewer() -> None:
    initialize(st.session_state)

    st.sidebar.selectbox("Archive manager", ARCHIVE_MANAGERS, key="archive_manager")
    st.sidebar.text_input(
        "Root directory of the archive",
        key="directory_archive_root",
        help="If empty, the one of the configuration.",
    )
    if st.sidebar.button("Reload the archive"):
        _open_model_results.clear()

    try:
        model_results = _open_model_results(
            st.session_state.archive_manager, st.session_state.directory_archive_root
        )
    except Exception as error:  # ruff: ignore[blind-except]
        st.error(f"The archive cannot be opened: {error}")
        return

    if not len(model_results):
        st.info("There is no model result in this archive.")
        return

    summaries = model_results.summaries
    for name, label in METADATA_FILTERS.items():
        st.sidebar.multiselect(
            label,
            get_values(summaries, name),
            key=name,
            help="If empty, all of them.",
        )
    st.sidebar.text_input(
        "Query",
        key="query",
        help="E.g. `inputs.height` > 45 or load_case == 'ThreePoints'",
    )

    query = build_query(
        {name: st.session_state[name] for name in METADATA_FILTERS},
        st.session_state.query,
    )
    try:
        model_results = model_results.filter(query)
    except ValueError as error:
        st.error(str(error))
        return

    st.write(f"{len(model_results)} model results out of {len(summaries)}.")
    summaries = model_results.summaries
    st.multiselect(
        "Inputs and outputs to show",
        get_variable_columns(summaries),
        key="variable_columns",
    )
    columns = [
        *(column for column in DEFAULT_COLUMNS if column in summaries.columns),
        *st.session_state.variable_columns,
    ]
    event = st.dataframe(
        summaries[columns],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="table",
    )
    selected_rows = event.selection.rows
    if not selected_rows:
        st.info("Select some results in the table to plot them.")
        return

    run_ids = list(summaries["run_id"].iloc[selected_rows])
    selected = model_results.filter(f"run_id in {run_ids!r}")
    if st.session_state.variable_columns:
        st.plotly_chart(
            plot_scalars(selected.summaries, st.session_state.variable_columns),
            use_container_width=True,
        )
    if len(get_values(selected.summaries, "model_name")) > 1:
        st.info("The curves are superposed for the results of a single model.")
        return

    for name, figure in selected.visualize().items():
        st.plotly_chart(figure, use_container_width=True, key=f"curves_{name}")


if __name__ == "__main__":
    generate_layout("Model results")
    model_results_viewer()
