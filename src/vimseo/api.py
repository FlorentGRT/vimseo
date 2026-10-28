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

from __future__ import annotations

import logging
import operator
import warnings
from pathlib import Path

from vimseo.problems.load_cases import DUMMY_LOAD_CASE_NAME

warnings.filterwarnings(
    "ignore",
    message="No runtime found",
    category=UserWarning,
)

# isort: off
# These imports must stay below ``warnings.filterwarnings`` so the "No runtime
# found" UserWarning they trigger at import time is suppressed.
from logging import _nameToLevel  # ruff: ignore[module-import-not-at-top-of-file]
from typing import TYPE_CHECKING  # ruff: ignore[module-import-not-at-top-of-file]

from vimseo.core.components.component_factory import (  # ruff: ignore[module-import-not-at-top-of-file]
    ComponentFactory,
)
from vimseo.core.pre_run_post_model import (  # ruff: ignore[module-import-not-at-top-of-file]
    PreRunPostModel,
)

from vimseo.utilities.datasets import (  # ruff: ignore[module-import-not-at-top-of-file]
    to_dataset as to_dataset,
)

# isort: on

if TYPE_CHECKING:
    from vimseo.core.base_integrated_model import IntegratedModel
    from vimseo.core.model_result import ModelResult
    from vimseo.core.model_settings import IntegratedModelSettings
    from vimseo.material.material import Material
    from vimseo.material.material_registry import MaterialInfo

LOGGER = logging.getLogger(__name__)


def activate_logger(
    level: int | None = None,
    filename: str | Path = "",
    filemode: str = "a",
):
    """Configure the VIMSEO (root) logger.

    Args:
        level: The logging level. If not provided, the level from the VIMSEO
            configuration is used.
        filename: The path to a log file. If provided, log records are also written
            to this file, in addition to the console.
        filemode: The file opening mode, either ``"a"`` (append) or ``"w"``
            (overwrite). Only used when ``filename`` is provided.
    """
    from gemseo import configure_logger

    if not level:
        from vimseo.config.global_configuration import _configuration as configuration

        level = _nameToLevel[configuration.logging.upper()]
    configure_logger(level=level, filename=filename, filemode=filemode)


def create_model(
    model_name: str,
    load_case_name: str = DUMMY_LOAD_CASE_NAME,
    model_options: IntegratedModelSettings | None = None,
    material: str | Path | Material | None = None,
    **options,
) -> IntegratedModel:
    """Create a model from its name.

    Args:
        model_name: string, name of the model to create
            (see :meth:`~vimseo.api.get_available_models` for valid names)
        load_case_name: The name of the load case that the model will execute.
        model_options: A pre-built :class:`.IntegratedModelSettings`. Any model option
            also passed as a keyword argument overrides the corresponding field.
        material: The material to build the model with, overriding the one its class
            declares in ``MATERIAL_FILE``. Either a material name
            (see :meth:`~vimseo.api.get_available_materials`), the path to a material
            JSON file, or a :class:`.Material`. By default, the model's own material
            is used.
        options: The options of the model.

    Returns: An instance of an :class:`.IntegratedModel`.
    """
    from vimseo.core.model_factory import ModelFactory

    if model_options is not None:
        options = {**model_options.model_dump(), **options}
    # Passed as a constructor keyword rather than through ``IntegratedModelSettings``:
    # that settings model is ``extra="forbid"`` and is round-tripped through
    # ``model_dump()``, which would flatten a ``Material`` instance into a plain dict.
    if material is not None:
        options["material"] = material
    return ModelFactory().create(model_name, load_case_name, **options)


def get_available_materials(model_name: str = "") -> list[MaterialInfo]:
    """Find the materials a model can be built with.

    Materials are discovered across |v|'s own ``material_lib`` and that of every
    installed plugin. A material is compatible with a model when it declares the same
    ``grammar_name`` as the model's material grammar; the model's own material always
    comes first.

    Args:
        model_name: The model name. By default, every discoverable material is returned,
            regardless of any model.

    Returns:
        The compatible materials, empty if the model declares no material at all.
    """
    from vimseo.material.material_registry import available_materials
    from vimseo.material.material_registry import compatible_materials

    if not model_name:
        return available_materials()
    return compatible_materials(model_name)


def get_available_load_cases(model_name: str) -> list[str]:
    """Find the load cases available for this model.

    Args:
        model_name: The model name.

    Returns:
        The load cases associated with the specified model.
    """
    from vimseo.core.load_case_factory import LoadCaseFactory
    from vimseo.core.model_factory import ModelFactory

    lc_factory = LoadCaseFactory()
    model_class = ModelFactory().get_class(model_name)
    domain = model_class._LOAD_CASE_DOMAIN
    all_load_case_names = []
    for class_name in lc_factory.class_names:
        if domain != "" and class_name.startswith(domain):
            class_name = class_name.removeprefix(f"{domain}_")
        try:
            lc = lc_factory.create(class_name, domain=domain)
            all_load_case_names.append(lc.name)
        except ImportError:
            continue

    if model_name != "PreRunPostModel" and issubclass(model_class, PreRunPostModel):
        all_component_names = ComponentFactory().class_names
        matching_load_case_names = []
        for c in all_component_names:
            candidate_load_case_name = c.removeprefix(model_class.PRE_PROC_FAMILY + "_")
            if (
                c.startswith(model_class.PRE_PROC_FAMILY)
                and candidate_load_case_name in all_load_case_names
            ):
                matching_load_case_names.append(candidate_load_case_name)
    else:
        # TODO: for non PreRunPostModel, define the load cases used by a model explicitely (as class attribute).
        load_case_names = list(set(all_load_case_names))
        matching_load_case_names = []
        for load_case_name in load_case_names:
            if load_case_name == DUMMY_LOAD_CASE_NAME:
                continue
            try:
                create_model(
                    model_name,
                    load_case_name,
                    archive_manager="DirectoryArchive",
                )
                matching_load_case_names.append(load_case_name)
            except (ImportError, AttributeError):
                continue

    return sorted(matching_load_case_names)


def get_available_models(load_case: str = "") -> list[str]:
    """Returns the list of the available models.

    Args:
        load_case: The considered load case. If specified, only the models
            using this load case are returned.

    Returns:
        The list of names of the available models.
    """
    from vimseo.core.model_factory import ModelFactory

    mf = ModelFactory()
    model_names = mf.class_names
    if load_case == "":
        model_names.remove("PreRunPostModel")
        model_names.remove("ModelComposition")
        return model_names
    model_to_lc = {}
    for model_name in model_names:
        model_to_lc[model_name] = get_available_load_cases(model_name)
    model_names = []
    for model, load_cases in model_to_lc.items():
        if load_case in load_cases:
            model_names.append(model)

    return sorted(model_names)


def get_available_plots():
    """The available plots, deriving from ``Plotter``."""
    from vimseo.tools.post_tools.plot_factory import PlotFactory

    class_names = PlotFactory().class_names
    class_names.remove("Plotter")
    return class_names


def get_available_metrics():
    """The available comparison metrics."""
    from gemseo.utils.metrics.metric_factory import MetricFactory

    return MetricFactory().class_names


def get_available_tools():
    """The available tools."""
    from vimseo.tools.tools_factory import ToolsFactory

    class_names = ToolsFactory().class_names
    class_names.remove("BaseTool")
    return class_names


def _resolve_archive(
    archive_manager: str, directory_archive_root: str | Path
) -> tuple[str, str | Path]:
    """Return the archive settings, with the defaults of the configuration."""
    from vimseo.config.global_configuration import _configuration as config
    from vimseo.storage_management.tool_archive.uri import get_default_archive_root

    return (
        archive_manager or config.run_archive_manager,
        directory_archive_root or get_default_archive_root(),
    )


def _open_simulation_archive(archive_manager: str, directory_archive_root: str | Path):
    """Open the archive of the simulations to read it."""
    from vimseo.storage_management import get_archive_class
    from vimseo.storage_management.base_storage_manager import PersistencyPolicy

    return get_archive_class(archive_manager)(
        PersistencyPolicy.DELETE_NEVER,
        model_name="",
        load_case_name="",
        root_directory=Path(directory_archive_root),
    )


def _get_mlflow_names(summaries: list[dict]) -> dict[str, str]:
    """Return the MLflow names of the columns of the summaries of simulations."""
    from vimseo.storage_management import run_kind

    return {
        "model_name": f"tags.`{run_kind.MODEL_TAG}`",
        "load_case": f"tags.`{run_kind.LOAD_CASE_TAG}`",
        "run_id": f"tags.`{run_kind.RUN_ID_TAG}`",
        "status": "attributes.status",
    }


def search_model_results(
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
    model_name: str = "",
    load_case: str = "",
    status: str = "FINISHED",
    query: str = "",
) -> list[dict]:
    """Search the archived simulations, without loading their results.

    Its counterpart for the tool runs is :func:`search_tool_runs`.

    Args:
        archive_manager: The archive manager of the simulations, ``"DirectoryArchive"``
            or ``"MlflowArchive"``. If empty, the one of the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: The study. If empty, every study.
        model_name: The name of the model. If empty, every model.
        load_case: The name of the load case. If empty, every load case.
        status: The status of the simulations. If empty, every status.
        query: A query on the summaries, e.g.
            ``"`inputs.height` > 45 or load_case == 'ThreePoints'"``, see
            :mod:`vimseo.results.query`.

    Returns:
        One summary per simulation, from the oldest to the newest: ``run_id``,
        ``study_name``, ``model_name``, ``load_case``, ``status``, ``datetime``,
        ``tool_run_id``, ``uri`` (to load it with :func:`load_model_results`), some
        metadata, and the scalar inputs and outputs as ``inputs.{name}`` and
        ``outputs.{name}``.
    """
    from pandas import DataFrame

    from vimseo.results.query import apply_query
    from vimseo.results.query import to_mlflow_filter

    archive_manager, directory_archive_root = _resolve_archive(
        archive_manager, directory_archive_root
    )
    archive = _open_simulation_archive(archive_manager, directory_archive_root)
    options = {}
    if archive_manager == "MlflowArchive":
        # The conjunctive part of the query is evaluated by the server too.
        names = _get_mlflow_names([])
        names.update({
            name: f"metrics.`{name}`" for name in _get_query_names(query, "inputs.")
        })
        names.update({
            name: f"metrics.`{name[len('outputs.') :]}`"
            for name in _get_query_names(query, "outputs.")
        })
        options["filter_string"] = to_mlflow_filter(query, names)
    summaries = archive.search_results(
        model_name=model_name,
        load_case=load_case,
        study_name=study_name,
        status=status,
        **options,
    )
    if not query:
        return summaries
    return apply_query(DataFrame(summaries), query).to_dict("records")


def _get_query_names(query: str, prefix: str) -> list[str]:
    """Return the backticked names of a query starting with a prefix."""
    import re

    return [name for name in re.findall(r"`([^`]+)`", query) if name.startswith(prefix)]


def search_tool_runs(
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
    tool_name: str = "",
    status: str = "",
    query: str = "",
) -> list[dict]:
    """Search the archived tool runs, without loading their results.

    Its counterpart for the simulations is :func:`search_model_results`.

    Args:
        archive_manager: The archive manager of the tool results. If empty, the one of
            the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: The study. If empty, every study.
        tool_name: The name of the tool. If empty, every tool.
        status: The status of the tool runs. If empty, every status.
        query: A query on the summaries, see :mod:`vimseo.results.query`; the
            settings are ``inputs.{name}`` and the key values ``outputs.{name}``.

    Returns:
        One summary per tool run, from the oldest to the newest, with its ``uri``
        (to load it with :func:`load_tool_results`).
    """
    from pandas import DataFrame

    from vimseo.results.collection import create_tool_summary
    from vimseo.results.query import apply_query
    from vimseo.storage_management.tool_archive.uri import get_default_archive_manager

    tool_archive_manager = open_tool_archive(
        archive_manager or get_default_archive_manager(), directory_archive_root
    )
    summaries = sorted(
        tool_archive_manager.search_tool_runs(
            tool_name=tool_name, status=status, study_name=study_name
        ),
        key=operator.itemgetter("tool_run_id"),
    )
    if not query:
        return summaries
    flat = DataFrame([create_tool_summary(summary) for summary in summaries])
    kept = set(apply_query(flat, query)["tool_run_id"]) if not flat.empty else set()
    return [summary for summary in summaries if summary["tool_run_id"] in kept]


def open_tool_archive(
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
):
    """Open the archive manager of the tool results.

    Args:
        archive_manager: The archive manager. If empty, the one of the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: The study of the tool runs written through the archive manager.
            If empty, the one of the configuration.

    Returns:
        The archive manager of the tool results, to search the tool runs and read
        their results.
    """
    from vimseo.storage_management.tool_archive import open_tool_archive as open_
    from vimseo.storage_management.tool_archive.uri import get_default_archive_manager
    from vimseo.storage_management.tool_archive.uri import get_default_archive_root

    return open_(
        archive_manager or get_default_archive_manager(),
        directory_archive_root or get_default_archive_root(),
        study_name,
    )


class _ModelResultLoader:
    """Load the model results of an archive, creating one model per load case."""

    def __init__(self, archive_manager: str, directory_archive_root: str | Path):
        self.__archive = {
            "archive_manager": archive_manager,
            "directory_archive_root": directory_archive_root,
        }
        self.__models = {}

    def __call__(self, summary) -> ModelResult:
        from vimseo.core.model_result import ModelResult
        from vimseo.storage_management.tool_archive.uri import load_model_data

        key = (summary["model_name"], summary["load_case"])
        if key not in self.__models:
            self.__models[key] = create_model(*key)
        return ModelResult.from_dict(
            load_model_data(summary["uri"], **self.__archive), model=self.__models[key]
        )


def open_model_results(
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
    query: str = "",
    failed: bool | None = None,
    **metadata,
):
    """Open the model results of an archive, as a collection.

    The results are loaded only when accessed: the collection is built from the
    summaries of :func:`search_model_results`.

    Args:
        archive_manager: The archive manager of the simulations. If empty, the one of
            the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: The study. If empty, every study.
        query: A query on the summaries, see :mod:`vimseo.results.query`.
        failed: Whether to keep only the failed simulations (``True``), only the
            others (``False``) or both (``None``).
        **metadata: Values of metadata, e.g. ``model_name="BendingTestAnalytical"``.

    Returns:
        The model results, a :class:`.ModelResults`.
    """
    from pandas import DataFrame

    from vimseo.results.collection import ModelResults

    archive_manager, directory_archive_root = _resolve_archive(
        archive_manager, directory_archive_root
    )
    summaries = search_model_results(
        archive_manager, directory_archive_root, study_name, status=""
    )
    return ModelResults(
        DataFrame(summaries, columns=None if summaries else ["run_id", "status"]),
        _ModelResultLoader(archive_manager, directory_archive_root),
    ).filter(query, failed, **metadata)


def open_tool_results(
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
    query: str = "",
    failed: bool | None = None,
    **metadata,
):
    """Open the tool results of an archive, as a collection.

    Args:
        archive_manager: The archive manager of the tool results. If empty, the one of
            the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: The study. If empty, every study.
        query: A query on the summaries, see :mod:`vimseo.results.query`.
        failed: Whether to keep only the failed tool runs (``True``), only the others
            (``False``) or both (``None``).
        **metadata: Values of metadata, e.g. ``tool_name="DOETool"``.

    Returns:
        The tool results, a :class:`.ToolResults`.
    """
    from pandas import DataFrame

    from vimseo.results.collection import ToolResults
    from vimseo.results.collection import create_tool_summary
    from vimseo.storage_management.tool_archive.uri import load_tool_result

    summaries = [
        create_tool_summary(summary)
        for summary in search_tool_runs(
            archive_manager, directory_archive_root, study_name
        )
    ]

    def load(summary):
        return load_tool_result(
            summary["uri"],
            archive_manager=archive_manager,
            directory_archive_root=directory_archive_root,
        )

    return ToolResults(
        DataFrame(summaries, columns=None if summaries else ["tool_run_id", "status"]),
        load,
    ).filter(query, failed, **metadata)


def _as_references(references) -> list:
    """Return one reference or a sequence of references as a list."""
    if isinstance(references, (str, Path)):
        return [references]
    return list(references)


def load_model_results(
    references,
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
):
    """Load model results from their references, without executing their models.

    A reference is a ``run_id``, ``run:{run_id}``, the job directory of a simulation
    or ``runs:/{mlflow_run_id}`` (see :mod:`vimseo.storage_management.tool_archive.uri`),
    e.g. the ``uri`` of a summary of :func:`search_model_results` or the
    ``simulation_run_ids`` of a tool result. The class of a model must be installed.
    Its counterpart for the tool results is :func:`load_tool_results`.

    Args:
        references: One reference or a sequence of references.
        archive_manager: The archive manager of the simulations. If empty, guess it
            from the archive, else the one of the configuration.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: Accepted so that the same archive settings are passed to every
            function; the results are searched in every study, whatever its value.

    Returns:
        The model results, a :class:`.ModelResults` in the order of the references,
        even for a single reference: ``load_model_results(ref)[0]``.

    Raises:
        KeyError: If a simulation is not in the archive.
    """
    from pandas import DataFrame

    from vimseo.core.model_result import ModelResult
    from vimseo.results.collection import ModelResults
    from vimseo.storage_management.base_archive_storage import create_simulation_summary
    from vimseo.storage_management.tool_archive.uri import load_model_data

    models = {}
    results = {}
    summaries = []
    for reference in _as_references(references):
        data = load_model_data(
            reference,
            archive_manager=archive_manager,
            directory_archive_root=directory_archive_root,
        )
        result = _from_model_data(ModelResult, data, models)
        summary = create_simulation_summary(
            result.to_dict(), result.study_name, f"run:{result.run_id}"
        )
        results[summary["run_id"]] = result
        summaries.append(summary)
    return ModelResults(
        DataFrame(summaries, columns=None if summaries else ["run_id", "status"]),
        lambda summary: results[summary["run_id"]],
        cache=dict(results),
    )


def _from_model_data(model_result_class, data, models):
    """Create a model result, reusing the model of its load case."""
    from vimseo.core.model_metadata import MetaDataNames

    outputs = data["outputs"]
    key = (
        str(outputs[MetaDataNames.model][0]),
        str(outputs[MetaDataNames.load_case][0]),
    )
    if key not in models:
        models[key] = create_model(*key)
    return model_result_class.from_dict(data, model=models[key])


def load_tool_results(
    references,
    archive_manager: str = "",
    directory_archive_root: str | Path = "",
    study_name: str = "",
):
    """Load tool results from their references, without their tools.

    A reference is a ``tool_run_id``, ``tool-run:{tool_run_id}``, a result file, the
    directory of a tool run or ``runs:/{mlflow_run_id}`` (see
    :mod:`vimseo.storage_management.tool_archive.uri`), e.g. the ``uri`` of a summary
    of :func:`search_tool_runs`. Its counterpart for the model results is
    :func:`load_model_results`.

    Args:
        references: One reference or a sequence of references.
        archive_manager: The archive manager of the tool results, used by the
            identifiers. If empty, guess it from the archive.
        directory_archive_root: The root directory of the archive. If empty, the one
            of the configuration.
        study_name: Accepted so that the same archive settings are passed to every
            function; the results are searched in every study, whatever its value.

    Returns:
        The tool results, a :class:`.ToolResults` in the order of the references,
        even for a single reference: ``load_tool_results(ref)[0]``.
    """
    from pandas import DataFrame

    from vimseo.results.collection import ToolResults
    from vimseo.results.collection import create_tool_summary
    from vimseo.storage_management.tool_archive.base_tool_archive import create_summary
    from vimseo.storage_management.tool_archive.uri import load_tool_result

    results = {}
    summaries = []
    for reference in _as_references(references):
        result = load_tool_result(
            reference,
            archive_manager=archive_manager,
            directory_archive_root=directory_archive_root,
        )
        metadata = result.metadata
        summary = create_tool_summary({
            **create_summary(
                "",
                metadata.tool_run_id,
                metadata.parent_tool_run_id,
                "FINISHED",
                result=result,
            ),
            "tool_name": metadata.misc.get("tool_name", type(result).__name__),
            "uri": str(reference),
        })
        results[summary["tool_run_id"]] = result
        summaries.append(summary)
    return ToolResults(
        DataFrame(summaries, columns=None if summaries else ["tool_run_id", "status"]),
        lambda summary: results[summary["tool_run_id"]],
        cache=dict(results),
    )


def print_config():
    """Returns: representation of the current configuration variables."""
    from vimseo.config.global_configuration import _configuration as configuration

    LOGGER.info(configuration.model_dump())


def print_config_help():
    """Return the help about configuration file."""
    from vimseo.config.global_configuration import _configuration as configuration

    LOGGER.info(configuration.model_fields)


activate_logger(_nameToLevel["INFO"])
