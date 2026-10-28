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

import json
import logging
import operator
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

from vimseo.core.model_metadata import MetaDataNames
from vimseo.storage_management import run_kind
from vimseo.storage_management.base_archive_storage import BaseArchiveManager
from vimseo.storage_management.base_archive_storage import _order_results
from vimseo.storage_management.base_archive_storage import create_simulation_summary
from vimseo.utilities.json_grammar_utils import EnhancedJSONEncoderArchive
from vimseo.utilities.model_data import decapsulate_length_one_array

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping
    from collections.abc import Sequence

    from vimseo.storage_management.base_archive_storage import ArchiveResultType
    from vimseo.storage_management.base_archive_storage import ModelDataType
    from vimseo.storage_management.base_storage_manager import PersistencyPolicy

LOGGER = logging.getLogger(__name__)


class DirectoryArchive(BaseArchiveManager):
    """A database of model results stored in local directories.

    A simulation is archived in the directory
    ``{root}/{study}/{model}/{load_case}/{job}/``, whose file ``results.json`` holds
    its inputs, outputs and metadata. The job directory is named by the ``run_id`` of
    the simulation, or by its ``job_name`` when one is given. The file is written when
    the job starts, with the status ``RUNNING``, then rewritten when the job ends,
    with the status ``FINISHED`` or ``FAILED``.
    """

    _RESULTS_JSON_FILE = "results.json"

    def __init__(
        self,
        persistency: PersistencyPolicy,
        model_name,
        load_case_name,
        root_directory: Path | str = "",
        job_name="",
        persistent_file_names=(),
        study_name: str = "",
    ):
        super().__init__(persistency, job_name, persistent_file_names, study_name)
        self._root_directory = Path(root_directory)
        self._model_name = model_name
        self._load_case_name = load_case_name
        self._job_directory = ""
        self._accept_overwrite_job_dir = False

    @property
    def root_directory(self) -> str:
        """The root directory where results are stored."""
        return str(self._root_directory.absolute())

    @property
    def _job_sub_path(self) -> Path:
        """The path of the job directories under the root directory."""
        return Path(self._study_name, self._model_name, self._load_case_name)

    def create_job_directory(
        self,
        run_id: str = "",
        input_data: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Create the job directory of a simulation.

        Args:
            run_id: The ``run_id`` of the simulation, naming the job directory when
                there is no job name. If both are empty, the directory is numbered.
            input_data: The inputs of the simulation. If given, they are written
                with the metadata and the status ``RUNNING``.
            metadata: The metadata known at the start of the simulation.
        """
        self._job_directory = self._create_job_directory(
            self._root_directory, self._job_name or run_id, self._job_sub_path
        )
        self._current_run_id = self._job_directory
        if input_data is not None:
            self._write_results({
                "inputs": decapsulate_length_one_array(input_data),
                "outputs": {},
                "metadata": {
                    **decapsulate_length_one_array(metadata or {}),
                    MetaDataNames.status: run_kind.RUNNING,
                },
            })

    def delete_job_directory(self):
        job_dir = self._job_directory
        if self._job_directory != "":
            LOGGER.info(f"Removing job directory: {job_dir}")
            shutil.rmtree(str(job_dir))

    def abort_job(self) -> None:
        """Write the status ``FAILED`` in the file of the current job, if any."""
        if self._job_directory == "":
            return
        path = Path(self._job_directory) / self._RESULTS_JSON_FILE
        if not path.is_file():
            return
        archive_result = json.loads(path.read_text())
        archive_result["metadata"][MetaDataNames.status] = run_kind.FAILED
        self._write_results(archive_result)

    @classmethod
    def _is_finished(cls, archive_dir: Path) -> bool:
        """Return whether the simulation of a job directory is finished.

        A result without status, from an archive older than the statuses, is
        finished.
        """
        archive_result = json.loads((archive_dir / cls._RESULTS_JSON_FILE).read_text())
        return (
            archive_result["metadata"].get(MetaDataNames.status, run_kind.FINISHED)
            == run_kind.FINISHED
        )

    def get_archived_results(
        self, run_ids: Sequence[str] | Sequence[Path] | None = None
    ):
        """Return archived results.

        Args:
            run_ids: The paths to the result files of the runs.
                If ``None``, use all the finished runs of the archive.
                If empty, no result is returned.

        Returns:
            The archived results,
            or ``None`` if the archive directory does not exist.
        """
        if run_ids is not None and len(run_ids) == 0:
            LOGGER.warning("No run IDs were given; no archived result is returned.")
            return []

        root_archive = self._root_directory / self._job_sub_path

        if not root_archive.is_dir():
            LOGGER.info(
                f"root_archive to be imported is not yet a directory (empty): {root_archive}",
            )
            return None

        if run_ids is not None:
            target_files = run_ids
        else:
            target_files = []
            for root, _, files in os.walk(root_archive):
                if self._RESULTS_JSON_FILE in files and self._is_finished(Path(root)):
                    target_files.append(Path(root) / self._RESULTS_JSON_FILE)

        results = [{} for f in target_files]

        for i, file in enumerate(target_files):
            archive_dir = Path(file).parent
            try:
                archive_result = self.get_result(archive_dir)
            except FileNotFoundError as err:  # ruff: ignore[blind-except]
                msg = f"{err!s} \nError encountered while parsing file {file}"
                raise FileNotFoundError(msg) from err

            # wrap job results in the #i item of the bundle
            results[i] = {
                **archive_result,
                "dir_archive_job": archive_dir,
                "ID": i + 1,
            }

        return results

    def get_results_by_run_id(self, run_ids: Iterable[str]) -> list[ModelDataType]:
        run_ids = list(run_ids)
        found = {}
        # A job directory is named by the run_id of its simulation, unless it has a
        # job name or comes from an archive older than this naming.
        for run_id in dict.fromkeys(run_ids):
            for path in self._root_directory.glob(
                f"*/*/*/{run_id}/{self._RESULTS_JSON_FILE}"
            ):
                result = self.get_result(path.parent)
                if self._get_run_id(result) == run_id:
                    found[run_id] = {**result, "dir_archive_job": path.parent}
                    break
        wanted = set(run_ids) - set(found)
        if wanted:
            for root, _, files in os.walk(self._root_directory):
                if self._RESULTS_JSON_FILE not in files:
                    continue
                result = self.get_result(root)
                run_id = self._get_run_id(result)
                if run_id in wanted:
                    found[run_id] = {**result, "dir_archive_job": Path(root)}
                    wanted.discard(run_id)
                    if not wanted:
                        break
        return _order_results(run_ids, found, self._root_directory)

    def search_results(
        self,
        model_name: str = "",
        load_case: str = "",
        study_name: str = "",
        status: str = "FINISHED",
    ) -> list[dict[str, object]]:
        summaries = []
        pattern = (
            f"{study_name or '*'}/{model_name or '*'}/{load_case or '*'}/*/"
            f"{self._RESULTS_JSON_FILE}"
        )
        for path in self._root_directory.glob(pattern):
            archive_result = json.loads(path.read_text())
            summary = create_simulation_summary(
                archive_result,
                path.relative_to(self._root_directory).parts[0],
                str(path.parent),
            )
            if status == "" or summary["status"] == status:
                summaries.append(summary)
        return sorted(summaries, key=operator.itemgetter("run_id"))

    @staticmethod
    def _get_run_id(result: ModelDataType) -> str:
        """Return the ``run_id`` of a result read from the archive."""
        return str(result["outputs"].get(MetaDataNames.run_id, [""])[0])

    def _write_results(self, archive_result: ArchiveResultType) -> None:
        """Write the file of the results of the current job."""
        Path(self._job_directory / self._RESULTS_JSON_FILE).write_text(
            json.dumps(archive_result, cls=EnhancedJSONEncoderArchive)
        )

    def copy_persistent_files(self, src_dir: Path | str) -> None:
        if src_dir == "":
            return

        for file_name in self._persistent_file_names:
            target = src_dir / file_name
            if target.is_file():
                shutil.copy(str(target), str(self._job_directory))
            else:
                LOGGER.warning(
                    f"The file {target} was meant to be copied "
                    f"from the scratch directory to the archive "
                    f"but it was not found."
                )

    def publish(self, archive_result: ArchiveResultType) -> None:
        archive_result["metadata"][MetaDataNames.status] = run_kind.FINISHED
        self._write_results(archive_result)

    def _encode_result(self, archive_result: ArchiveResultType) -> ArchiveResultType:
        """Encode a job result, from ModelResult format to an archived format."""
        return archive_result

    def _decode_result(self, directory_result: ArchiveResultType) -> ModelDataType:
        """Decode a job result, from an archived format, to a ModelResult format."""

        r = deepcopy(directory_result)
        inputs = {k: np.atleast_1d(v) for k, v in r["inputs"].items()}
        outputs = {k: np.atleast_1d(v) for k, v in r["outputs"].items()}
        metadata = {k: np.atleast_1d(v) for k, v in r["metadata"].items()}
        outputs.update(metadata)

        return {"inputs": inputs, "outputs": outputs}

    def get_result(self, archive_dir_path: str | Path = "") -> ModelDataType:
        archive_dir_path = (
            self._job_directory if archive_dir_path == "" else archive_dir_path
        )
        with Path(Path(archive_dir_path) / self._RESULTS_JSON_FILE).open() as f:
            directory_result = json.load(f)
            return self._decode_result(directory_result)
