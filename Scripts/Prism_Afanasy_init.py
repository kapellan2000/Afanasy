# -*- coding: utf-8 -*-
#
####################################################
#
# PRISM - Pipeline for animation and VFX projects
#
# www.prism-pipeline.com
#
# contact: contact@prism-pipeline.com
#
####################################################
#
#
# Copyright (C) 2016-2021 Richard Frangenberg
#
# Licensed under GNU LGPL-3.0-or-later
#
# This file is part of Prism.
#
# Prism is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Prism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Prism.  If not, see <https://www.gnu.org/licenses/>.


from Prism_Afanasy_Variables import Prism_Afanasy_Variables
from Prism_Afanasy_Functions import Prism_Afanasy_Functions
from Prism_Afanasy_Integration import Prism_Afanasy_Integration

class Prism_Afanasy(Prism_Afanasy_Variables, Prism_Afanasy_Functions, Prism_Afanasy_Integration,):
    def __init__(self, core):
        Prism_Afanasy_Variables.__init__(self, core, self)
        Prism_Afanasy_Functions.__init__(self, core, self)
        Prism_Afanasy_Integration.__init__(self, core, self)