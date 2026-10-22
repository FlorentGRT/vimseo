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

import pytest
from gemseo.core.discipline.data_processor import NameMapping
from gemseo.core.grammars.errors import InvalidDataError
from numpy import array

from vimseo.core.gemseo_discipline_wrapper import GemseoDisciplineWrapper


class _DisciplineWithUnknownOutput(GemseoDisciplineWrapper):
    """A discipline whose ``_run`` returns a name not in its output grammar."""

    def __init__(self) -> None:
        super().__init__()
        self.io.output_grammar.update_from_names(["y"])

    def _run(self, input_data):
        return {"y": array([1.0]), "z": array([2.0])}


def test_forbid_extra_output_names_default():
    """Extra output names are ignored by default."""
    discipline = _DisciplineWithUnknownOutput()
    assert not discipline.forbid_extra_output_names
    assert set(discipline.execute()) == {"y"}


def test_forbid_extra_output_names():
    """A discipline forbidding extra output names raises."""
    discipline = _DisciplineWithUnknownOutput()
    discipline.forbid_extra_output_names = True
    with pytest.raises(InvalidDataError, match="not in its output grammar: z"):
        discipline.execute()


def test_forbid_extra_output_names_with_name_mapping():
    """Names mapped by a data processor are not extra names."""
    discipline = _DisciplineWithUnknownOutput()
    discipline.io.output_grammar.update_from_names(["z_global"])
    discipline.io.data_processor = NameMapping({"z_global": "z"})
    discipline.forbid_extra_output_names = True
    assert set(discipline.execute()) == {"y", "z_global"}
