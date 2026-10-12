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
"""The samples of a DOE used by a sensitivity analysis.

A sensitivity analysis either executes the DOE it needs
or uses a DOE prepared in advance, whose structure is then checked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gemseo.datasets.io_dataset import IODataset
from numpy import isclose

from vimseo.core.model_metadata import MetaDataNames

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gemseo.datasets.dataset import Dataset
    from gemseo.typing import RealArray


def get_variable_names(dataset: Dataset, group_name: str) -> list[str]:
    """Return the names of the variables of a group, in the order of the columns.

    Contrary to :meth:`.Dataset.get_variable_names`, the names are not sorted:
    the samples of a DOE are ordered like the variables of its variables space,
    and a sensitivity analysis relies on this order.

    Args:
        dataset: The samples of the DOE.
        group_name: The name of the group.

    Returns:
        The names of the variables of the group.
    """
    return list(
        dataset
        .get_view(group_names=group_name)
        .columns.get_level_values(dataset.COLUMN_LEVEL_NAMES[1])
        .unique()
    )


def get_output_names(dataset: Dataset, output_names: Sequence[str] = ()) -> list[str]:
    """Return the names of the outputs of a DOE considered by a sensitivity analysis.

    Args:
        dataset: The samples of the DOE.
        output_names: The names of the outputs.
            If empty, use all the outputs of the DOE except the metadata of the model.

    Returns:
        The names of the outputs.

    Raises:
        ValueError: When an output is missing from the DOE.
    """
    available_names = get_variable_names(dataset, IODataset.OUTPUT_GROUP)
    if not output_names:
        metadata_names = {name.name for name in MetaDataNames}
        return [name for name in available_names if name not in metadata_names]

    missing_names = set(output_names).difference(available_names)
    if missing_names:
        msg = (
            f"The outputs {sorted(missing_names)} are missing from the DOE, "
            f"whose outputs are {available_names}."
        )
        raise ValueError(msg)

    return list(output_names)


def to_io_dataset(dataset: Dataset, output_names: Sequence[str]) -> IODataset:
    """Restrict the samples of a DOE to its inputs and to some outputs.

    The other outputs, e.g. the metadata of the model, are removed.

    Args:
        dataset: The samples of the DOE,
            with an input group and an output group.
        output_names: The names of the outputs to keep.

    Returns:
        The samples of the DOE restricted to its inputs and to the outputs.

    Raises:
        ValueError: When the DOE has no input group or no output group.
    """
    for group_name in (IODataset.INPUT_GROUP, IODataset.OUTPUT_GROUP):
        if group_name not in dataset.group_names:
            msg = (
                f"The samples of the DOE must have a group {group_name!r}; "
                f"its groups are {dataset.group_names}."
            )
            raise ValueError(msg)

    io_dataset = IODataset(dataset_name=dataset.name)
    for group_name, names in (
        (IODataset.INPUT_GROUP, get_variable_names(dataset, IODataset.INPUT_GROUP)),
        (IODataset.OUTPUT_GROUP, output_names),
    ):
        for name in names:
            io_dataset.add_variable(
                name,
                dataset
                .get_view(group_names=group_name, variable_names=name)
                .to_numpy()
                .astype(float),
                group_name=group_name,
            )

    return io_dataset


def get_input_samples(dataset: Dataset) -> RealArray:
    """Return the input samples of a DOE.

    Args:
        dataset: The samples of the DOE.

    Returns:
        The input samples, shaped as ``(n_samples, n_input_components)``.
    """
    return dataset.get_view(group_names=IODataset.INPUT_GROUP).to_numpy().astype(float)


def _get_varying_components(point: RealArray, reference_point: RealArray) -> set[int]:
    """Return the components of a point that differ from a reference point.

    Args:
        point: The point.
        reference_point: The reference point.

    Returns:
        The indices of the components that differ.
    """
    return set((~isclose(point, reference_point, rtol=1e-12, atol=0.0)).nonzero()[0])


def check_star_structure(dataset: Dataset) -> bool:
    r"""Check that the samples of a DOE are a star.

    The first sample is the center :math:`x_0`.
    The following ones are :math:`x_0+h_1e_1,\ldots,x_0+h_de_d`
    and, for a two-sided star, :math:`x_0-h_1e_1,\ldots,x_0-h_de_d`;
    only the sign of the steps matters.

    Args:
        dataset: The samples of the DOE.

    Returns:
        Whether the star is two-sided.

    Raises:
        ValueError: When the samples are not a star.
    """
    samples = get_input_samples(dataset)
    n_samples, dimension = samples.shape
    expected = (
        f"a star DOE around a center x0 with {dimension} input components has "
        f"{dimension + 1} (one-sided) or {2 * dimension + 1} (two-sided) samples: "
        "x0, then x0 with its i-th component varied, for each i "
        "(and then for each i again, on the other side, for a two-sided star)"
    )
    if n_samples not in {dimension + 1, 2 * dimension + 1}:
        msg = f"The DOE has {n_samples} samples, whereas {expected}."
        raise ValueError(msg)

    center = samples[0]
    for k, sample in enumerate(samples[1:]):
        i = k % dimension
        if _get_varying_components(sample, center) != {i}:
            msg = (
                f"The sample {k + 1} of the DOE must differ from the center "
                f"in the input component {i} only, since {expected}."
            )
            raise ValueError(msg)

    return n_samples == 2 * dimension + 1


def check_morris_structure(dataset: Dataset) -> None:
    """Check that the samples of a DOE are the replicates of an OAT trajectory.

    These samples are generated by the ``MorrisDOE`` algorithm:
    each block of :math:`d+1` samples is a trajectory where
    the sample :math:`k+1` differs from the sample :math:`k` in the component :math:`k`.

    Args:
        dataset: The samples of the DOE.

    Raises:
        ValueError: When the samples are not replicates of an OAT trajectory.
    """
    samples = get_input_samples(dataset)
    n_samples, dimension = samples.shape
    expected = (
        f"a Morris DOE with {dimension} input components is made of blocks of "
        f"{dimension + 1} samples, where the sample k+1 differs from the sample k "
        "in the input component k only; use the DOE algorithm 'MorrisDOE'"
    )
    if n_samples == 0 or n_samples % (dimension + 1):
        msg = f"The DOE has {n_samples} samples, whereas {expected}."
        raise ValueError(msg)

    for start in range(0, n_samples, dimension + 1):
        for i in range(dimension):
            if _get_varying_components(samples[start + i + 1], samples[start + i]) != {
                i
            }:
                msg = (
                    f"The sample {start + i + 1} of the DOE must differ from "
                    f"the sample {start + i} in the input component {i} only, "
                    f"since {expected}."
                )
                raise ValueError(msg)
