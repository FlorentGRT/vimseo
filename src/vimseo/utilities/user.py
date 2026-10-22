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

"""Name of the user running VIMSEO."""

from __future__ import annotations

import getpass
import os

UNKNOWN_USER = "unknown"


def get_user_name() -> str:
    """Return the name of the current user, or ``"unknown"`` if it cannot be found.

    ``getpass.getuser`` relies on environment variables, then on the POSIX-only
    ``pwd`` module, and ``os.getlogin`` needs a console: either may fail on Windows
    (e.g. in a tox environment), in a service or in a container.
    """
    for getter in (getpass.getuser, os.getlogin):
        try:
            return getter()
        except (ImportError, KeyError, OSError):
            continue
    return UNKNOWN_USER
