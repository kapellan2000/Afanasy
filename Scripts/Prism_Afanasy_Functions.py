#
# Copyright (C) 2016-2020 Richard Frangenberg
#
# Licensed under GNU GPL-3.0-or-later
#
# This file is part of Prism.
#
# Prism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Prism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Prism.  If not, see <https://www.gnu.org/licenses/>.


import os
import sys
import subprocess
import time
import logging
import importlib
import inspect

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

from PrismUtils.Decorators import err_catcher as err_catcher


logger = logging.getLogger(__name__)


class Prism_Afanasy_Functions(object):
    def __init__(self, core, plugin):
        self.core = core
        self.plugin = plugin
        self.af_path = self.refreshIntegrations()
        if self.af_path:
            sys.path.append(os.path.join(self.af_path,"afanasy","python"))
            sys.path.append(os.path.join(self.af_path,"lib","python"))

            os.environ['CGRU_LOCATION'] = self.af_path
            import af
            self.af = af
            
        self.coreName = self.core.appPlugin.pluginName
        if  self.coreName == "Houdini": #to do
            self.hou = importlib.import_module("hou")
            self.renderName = "None"
        elif self.coreName == "Maya":
            self.ass_param = {}
            self.self_prefix = 'meArnoldRender_'
            self.cmds = importlib.import_module("maya.cmds")
            self.mel = importlib.import_module("maya.mel")

            render_settings_node = "defaultRenderGlobals"
            self.renderName =  self.cmds.getAttr(render_settings_node + ".currentRenderer")
            gen_type = "generate_ass"
            self.generate_scenes = getattr(self, gen_type, None)

        self.core.plugins.registerRenderfarmPlugin(self)
        self.core.registerCallback("onStateStartup", self.onStateStartup, plugin=self.plugin)
        self.core.registerCallback("onStateGetSettings", self.onStateGetSettings, plugin=self.plugin)
        self.core.registerCallback("onStateSettingsLoaded", self.onStateSettingsLoaded, plugin=self.plugin)
        self.core.registerCallback("projectSettings_loadUI", self.projectSettings_loadUI, plugin=self.plugin)
        self.core.registerCallback(
            "preProjectSettingsLoad", self.preProjectSettingsLoad, plugin=self.plugin
        )
        self.core.registerCallback(
            "preProjectSettingsSave", self.preProjectSettingsSave, plugin=self.plugin
        )
        self.core.registerCallback("prePublish", self.prePublish, plugin=self.plugin)
        self.core.registerCallback("postPublish", self.postPublish, plugin=self.plugin)
        dft = """[expression,#  available variables:
#  "core" - PrismCore
#  "context" - dict

if context.get("type") == "asset":
    base = "@asset@"
else:
    base = "@sequence@-@shot@"

template = base + "_@product@@identifier@_@version@"]"""

        data = {"label": "Afanasy Job Name", "key": "@Afanasy_job_name@", "value": dft, "requires": []}
        self.core.projects.addProjectStructureItem("AfanasyJobName", data)


    def refreshIntegrations(self):
        integrations = self.core.integration.getIntegrations()
        if "Afanasy" in integrations:
            afPath = integrations["Afanasy"][0]
        else:
            afPath = ""
        return afPath
        

    def CallAfanasyCommand(self, arguments, hideWindow=True, readStdout=True, silent=False):
        try:
            import afcmd
            action = 'get'
            verbose=False
            arguments['ids'] = None
            output = afcmd._sendRequest(action, arguments, verbose)

        except Exception as e:
            if e.errno == 2:
                msg = "Cannot connect to Afanasy. Unable to find the \"Afanasycommand\" executable."
                if silent:
                    logger.warning(msg)
                else:
                    self.core.popup(msg)

                return False

        return output

    @err_catcher(name=__name__)
    def refreshPools(self):
        if not hasattr(self.core, "projectPath"):
            return
        with self.core.waitPopup(self.core, "Getting pools from Afanasy. Please wait..."):
            output = self.CallAfanasyCommand({'type': 'pools'}, silent=True)

        if output and "Error" not in output:

            AfanasyPools = []
            if output is not None:
                if 'pools' in output:
                    for poolData in output['pools']:
                        print(poolData['name'])
                        AfanasyPools.append(poolData['name'])
        else:
            AfanasyPools = []

        self.core.setConfig("Afanasy", "pools", val=AfanasyPools, config="project")
        return AfanasyPools

    @err_catcher(name=__name__)
    def getRenderer(self):
        print("Renderer")
        pools = [self.renderName]
        return pools

    @err_catcher(name=__name__)
    def getAfanasyPools(self):
        if not hasattr(self.core, "projectPath"):
            return

        pools = self.core.getConfig("Afanasy", "pools", config="project")
        if not pools :
            self.refreshPools()
            pools = self.core.getConfig("Afanasy", "pools", config="project")

        pools = pools or []
        return pools

    @err_catcher(name=__name__)
    def onRefreshPoolsClicked(self, settings):
        self.refreshPools()
        self.refreshGroups()
        settings.gb_dlPoolPresets.refresh()

    @err_catcher(name=__name__)
    def projectSettings_loadUI(self, origin):
        self.addUiToProjectSettings(origin)

    @err_catcher(name=__name__)
    def addUiToProjectSettings(self, projectSettings):
        projectSettings.w_Afanasy = QWidget()
        lo_Afanasy = QGridLayout()
        projectSettings.w_Afanasy.setLayout(lo_Afanasy)

        projectSettings.chb_submitScenes = QCheckBox("Submit scenefiles together with jobs")
        projectSettings.chb_submitScenes.setToolTip("When checked the scenefile, from which a Afanasy job gets submitted, will be copied to the Afanasy repository.\nWhen disabled When disabled the Afanasy Workers will open the scenefile at the original location. This can be useful when using relative filepaths, but has the risk of getting overwritten by artists while a job is rendering.")
        projectSettings.chb_submitScenes.setChecked(True)
        lo_Afanasy.addWidget(projectSettings.chb_submitScenes)

        projectSettings.gb_dlPoolPresets = PresetWidget(self)
        projectSettings.gb_dlPoolPresets.setCheckable(True)
        projectSettings.gb_dlPoolPresets.setChecked(False)
        lo_Afanasy.addWidget(projectSettings.gb_dlPoolPresets)

        projectSettings.w_refreshPools = QWidget()
        projectSettings.lo_refreshPools = QHBoxLayout()
        projectSettings.w_refreshPools.setLayout(projectSettings.lo_refreshPools)
        projectSettings.lo_refreshPools.addStretch()
        projectSettings.b_refreshPools = QPushButton("Refresh Pools/Groups")
        projectSettings.b_refreshPools.clicked.connect(lambda: self.onRefreshPoolsClicked(projectSettings))
        projectSettings.lo_refreshPools.addWidget(projectSettings.b_refreshPools)
        lo_Afanasy.addWidget(projectSettings.w_refreshPools)

        sp_stretch = QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Expanding)
        lo_Afanasy.addItem(sp_stretch)
        projectSettings.tw_settings.addTab(projectSettings.w_Afanasy, "Afanasy")

    @err_catcher(name=__name__)
    def preProjectSettingsLoad(self, origin, settings):
        if "Afanasy" in settings:
            if "submitScenes" in settings["Afanasy"]:
                val = settings["Afanasy"]["submitScenes"]
                origin.chb_submitScenes.setChecked(val)

            if "usePoolPresets" in settings["Afanasy"]:
                val = settings["Afanasy"]["usePoolPresets"]
                origin.gb_dlPoolPresets.setChecked(val)

            if "poolPresets" in settings["Afanasy"]:
                val = settings["Afanasy"]["poolPresets"]
                if val:
                    origin.gb_dlPoolPresets.loadPresetData(val)

    @err_catcher(name=__name__)
    def preProjectSettingsSave(self, origin, settings):
        if "Afanasy" not in settings:
            settings["Afanasy"] = {}
            settings["Afanasy"]["submitScenes"] = origin.chb_submitScenes.isChecked()
            settings["Afanasy"]["usePoolPresets"] = origin.gb_dlPoolPresets.isChecked()
            settings["Afanasy"]["poolPresets"] = origin.gb_dlPoolPresets.getPresetData()

    @err_catcher(name=__name__)
    def prePublish(self, origin):
        origin.submittedDlJobs = {}
        origin.submittedDlJobData = {}

    @err_catcher(name=__name__)
    def postPublish(self, origin, pubType, result):
        origin.submittedDlJobs = {}
        origin.submittedDlJobData = {}

    @err_catcher(name=__name__)
    def sm_dep_preExecute(self, origin):
        warnings = []

        return warnings

    @err_catcher(name=__name__)
    def onStateStartup(self, state):
        if state.className == "Dependency":
            state.tw_caches.itemClicked.connect(
                lambda x, y: self.sm_updateDlDeps(state, x, y)
            )
            state.tw_caches.itemDoubleClicked.connect(self.sm_dlGoToNode)
        else:
            if hasattr(state, "cb_dlPool"):
                state.cb_dlPool.addItems(self.getAfanasyPools())

            if hasattr(state, "cb_dlGroup"):
                state.cb_dlGroup.addItems(self.getAfanasyGroups())

            if hasattr(state, "gb_submit"):
                lo = state.gb_submit.layout()

                state.w_dlRenderer = QWidget()
                state.lo_dlRenderer = QHBoxLayout()
                state.lo_dlRenderer.setContentsMargins(0, 0, 0, 0)
                state.l_dlRenderer = QLabel("Render:")
                state.cb_dlRenderer = QComboBox()
                state.cb_dlRenderer.setToolTip("Set active render")
                state.cb_dlRenderer.setMinimumWidth(150)
                state.w_dlRenderer.setLayout(state.lo_dlRenderer)
                state.lo_dlRenderer.addWidget(state.l_dlRenderer)
                state.lo_dlRenderer.addStretch()
                state.lo_dlRenderer.addWidget(state.cb_dlRenderer)
                state.cb_dlRenderer.addItems(self.getRenderer())
                state.cb_dlRenderer.activated.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_dlRenderer)

                state.w_machineLimit = QWidget()
                state.lo_machineLimit = QHBoxLayout()
                state.lo_machineLimit.setContentsMargins(9, 0, 9, 0)
                state.l_machineLimit = QLabel("Machine Limit:")
                state.sp_machineLimit = QSpinBox()
                state.sp_machineLimit.setMaximum(99999)
                state.w_machineLimit.setLayout(state.lo_machineLimit)
                state.lo_machineLimit.addWidget(state.l_machineLimit)
                state.lo_machineLimit.addStretch()
                state.lo_machineLimit.addWidget(state.sp_machineLimit)
                state.sp_machineLimit.editingFinished.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_machineLimit)

                state.w_dlPool = QWidget()
                state.lo_dlPool = QHBoxLayout()
                state.lo_dlPool.setContentsMargins(9, 0, 9, 0)
                state.l_dlPool = QLabel("Pool:")
                state.cb_dlPool = QComboBox()
                state.cb_dlPool.setToolTip("Afanasy Pool (can be updated in the Prism Project Settings)")
                state.cb_dlPool.setMinimumWidth(150)
                state.w_dlPool.setLayout(state.lo_dlPool)
                state.lo_dlPool.addWidget(state.l_dlPool)
                state.lo_dlPool.addStretch()
                state.lo_dlPool.addWidget(state.cb_dlPool)
                state.cb_dlPool.addItems(self.getAfanasyPools())
                state.cb_dlPool.activated.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_dlPool)

                state.gb_selected = QGroupBox("Export only selected objects")
                state.gb_selected.setCheckable(True)
                state.gb_selected.setChecked(False)
                lo.addWidget(state.gb_selected)

                state.gb_prioJob = QGroupBox("Use existing .ass files")
                state.gb_prioJob.setCheckable(True)
                state.gb_prioJob.setChecked(False)
                lo.addWidget(state.gb_prioJob)

                state.lo_prioJob = QVBoxLayout()
                state.gb_prioJob.setLayout(state.lo_prioJob)
                state.gb_prioJob.toggled.connect(state.stateManager.saveStatesToScene)

                state.w_highPrio = QWidget()
                state.lo_highPrio = QHBoxLayout()
                state.l_highPrio = QLabel("Priority:")
                state.sp_highPrio = QSpinBox()
                state.sp_highPrio.setMaximum(100)
                state.sp_highPrio.setValue(70)
                state.lo_prioJob.addWidget(state.w_highPrio)
                state.w_highPrio.setLayout(state.lo_highPrio)
                state.lo_highPrio.addWidget(state.l_highPrio)
                state.lo_highPrio.addStretch()
                state.lo_highPrio.addWidget(state.sp_highPrio)
                state.lo_highPrio.setContentsMargins(0, 0, 0, 0)
                state.sp_highPrio.editingFinished.connect(state.stateManager.saveStatesToScene)


                state.w_generationPt = QWidget()
                state.lo_generationPt = QHBoxLayout()
                state.l_generationPt = QLabel("Directory NAme:")
                state.e_generationPt = QLineEdit()
                state.e_generationPt.setText("ass")
                state.b_generationPt = QToolButton()
                state.b_generationPt.setText("...")
                state.b_generationPt.setStyleSheet("font: 14pt; text-align: center;")
                state.b_generationPt.clicked.connect(lambda: self.openFolderDialog(state))
                state.lo_prioJob.addWidget(state.w_generationPt)
                state.w_generationPt.setLayout(state.lo_generationPt)
                state.lo_generationPt.addWidget(state.l_generationPt)
                state.lo_generationPt.addStretch()
                state.lo_generationPt.addWidget(state.e_generationPt)
                state.lo_generationPt.addWidget(state.b_generationPt)
                state.lo_generationPt.setContentsMargins(0, 0, 0, 0)

                state.gb_cleanup = QGroupBox("cleanup .ass/.vrscenes")
                state.gb_cleanup.setCheckable(True)
                state.gb_cleanup.setChecked(False)
                lo.addWidget(state.gb_cleanup)
                
                state.gb_cleanup = QGroupBox("cleanup temp scene")
                state.gb_cleanup.setCheckable(True)
                state.gb_cleanup.setChecked(False)
                lo.addWidget(state.gb_cleanup)

                state.w_hostMask = QWidget()
                state.lo_hostMask = QHBoxLayout()
                state.lo_hostMask.setContentsMargins(9, 0, 9, 0)
                state.l_hostMask = QLabel("Host Mask:")
                state.e_hostMask = QLineEdit()
                state.e_hostMask.setMaximumWidth(800)
                state.w_hostMask.setLayout(state.lo_hostMask)
                state.lo_hostMask.addWidget(state.l_hostMask)
                state.lo_hostMask.addStretch()
                state.lo_hostMask.addWidget(state.e_hostMask)
                state.e_hostMask.editingFinished.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_hostMask)

                state.w_excludeHostMask = QWidget()
                state.lo_excludeHostMask = QHBoxLayout()
                state.lo_excludeHostMask.setContentsMargins(9, 0, 9, 0)
                state.l_excludeHostMask = QLabel("Exclude Host Mask:")
                state.e_excludeHostMask = QLineEdit()
                state.e_excludeHostMask.setMaximumWidth(800)
                state.w_excludeHostMask.setLayout(state.lo_excludeHostMask)
                state.lo_excludeHostMask.addWidget(state.l_excludeHostMask)
                state.lo_excludeHostMask.addStretch()
                state.lo_excludeHostMask.addWidget(state.e_excludeHostMask)
                state.e_excludeHostMask.editingFinished.connect(lambda: handleEditingFinished(state, "excludeHostMask"))
                lo.addWidget(state.w_excludeHostMask)

                state.w_dependMask = QWidget()
                state.lo_dependMask = QHBoxLayout()
                state.lo_dependMask.setContentsMargins(9, 0, 9, 0)
                state.l_dependMask = QLabel("Depend Mask:")
                state.e_dependMask = QLineEdit()
                state.e_dependMask.setMaximumWidth(800)
                state.w_dependMask.setLayout(state.lo_dependMask)
                state.lo_dependMask.addWidget(state.l_dependMask)
                state.lo_dependMask.addStretch()
                state.lo_dependMask.addWidget(state.e_dependMask)
                state.e_dependMask.editingFinished.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_dependMask)

                state.w_globalDependMask = QWidget()
                state.lo_globalDependMask = QHBoxLayout()
                state.lo_globalDependMask.setContentsMargins(9, 0, 9, 0)
                state.l_globalDependMask = QLabel("Global Depend Mask:")
                state.e_globalDependMask = QLineEdit()
                state.e_globalDependMask.setMaximumWidth(800)
                state.w_globalDependMask.setLayout(state.lo_globalDependMask)
                state.lo_globalDependMask.addWidget(state.l_globalDependMask)
                state.lo_globalDependMask.addStretch()
                state.lo_globalDependMask.addWidget(state.e_globalDependMask)
                state.e_globalDependMask.editingFinished.connect(state.stateManager.saveStatesToScene)
                lo.addWidget(state.w_globalDependMask)

    @err_catcher(name=__name__)
    def presetChanged(self, state):

        if data["pool"]:
            idx = state.cb_dlPool.findText(data["pool"])
            if idx != -1:
                state.cb_dlPool.setCurrentIndex(idx)

        if data["secondaryPool"]:
            idx = state.cb_sndPool.findText(data["secondaryPool"])
            if idx != -1:
                state.cb_sndPool.setCurrentIndex(idx)

        if data["group"]:
            idx = state.cb_dlGroup.findText(data["group"])
            if idx != -1:
                state.cb_dlGroup.setCurrentIndex(idx)

        state.stateManager.saveStatesToScene()

    @err_catcher(name=__name__)

    def openFolderDialog(self, state):
        folder_path = QFileDialog.getExistingDirectory(None, "Select folder", "", QFileDialog.ShowDirsOnly)
        if folder_path:
            state.e_generationPt.setText(folder_path)

    @err_catcher(name=__name__)
    def onStateGetSettings(self, state, settings):
        if hasattr(state, "gb_submit"):
            settings["dl_machineLimit"] = state.sp_machineLimit.value()
            settings["curdlpool"] = state.cb_dlPool.currentText()
            settings["dl_useSecondJob"] = state.gb_prioJob.isChecked()
            settings["dl_secondJobPrio"] = state.sp_highPrio.value()

    @err_catcher(name=__name__)
    def onStateSettingsLoaded(self, state, settings):
        if hasattr(state, "gb_submit"):
            if "dl_machineLimit" in settings:
                state.sp_machineLimit.setValue(settings["dl_machineLimit"])

            if "curdlpool" in settings:
                idx = state.cb_dlPool.findText(settings["curdlpool"])
                if idx != -1:
                    state.cb_dlPool.setCurrentIndex(idx)

            if "dl_sndPool" in settings:
                idx = state.cb_sndPool.findText(settings["dl_sndPool"])
                if idx != -1:
                    state.cb_sndPool.setCurrentIndex(idx)

            if "curdlgroup" in settings:
                idx = state.cb_dlGroup.findText(settings["curdlgroup"])
                if idx != -1:
                    state.cb_dlGroup.setCurrentIndex(idx)

            if "dl_useSecondJob" in settings:
                state.gb_prioJob.setChecked(settings["dl_useSecondJob"])

            if "dl_secondJobPrio" in settings:
                state.sp_highPrio.setValue(settings["dl_secondJobPrio"])

            if "dl_poolPreset" in settings:
                idx = state.cb_dlPreset.findText(settings["dl_poolPreset"])
                if idx != -1:
                    state.cb_dlPreset.setCurrentIndex(idx)

    @err_catcher(name=__name__)
    def sm_houExport_activated(self, origin):
        origin.f_osDependencies.setVisible(False)
        origin.f_osUpload.setVisible(False)
        origin.f_osPAssets.setVisible(False)
        origin.gb_osSlaves.setVisible(False)

    @err_catcher(name=__name__)
    def sm_houExport_preExecute(self, origin):
        warnings = []

        return warnings

    @err_catcher(name=__name__)
    def sm_houRender_updateUI(self, origin):
        showGPUsettings = (
            origin.node is not None and origin.node.type().name() == "Redshift_ROP"
        )
        origin.w_dlGPUpt.setVisible(showGPUsettings)
        origin.w_dlGPUdevices.setVisible(showGPUsettings)

    @err_catcher(name=__name__)
    def sm_houRender_managerChanged(self, origin):
        origin.f_osDependencies.setVisible(False)
        origin.f_osUpload.setVisible(False)

        origin.f_osPAssets.setVisible(False)
        origin.gb_osSlaves.setVisible(False)
        origin.w_dlConcurrentTasks.setVisible(True)

        showGPUsettings = (
            origin.node is not None and origin.node.type().name() == "Redshift_ROP"
        )
        origin.w_dlGPUpt.setVisible(showGPUsettings)
        origin.w_dlGPUdevices.setVisible(showGPUsettings)

    @err_catcher(name=__name__)
    def sm_houRender_preExecute(self, origin):
        warnings = []

        return warnings

    @err_catcher(name=__name__)
    def sm_render_updateUI(self, origin):
        if hasattr(origin, "f_osDependencies"):
            origin.f_osDependencies.setVisible(False)

        if hasattr(origin, "gb_osSlaves"):
            origin.gb_osSlaves.setVisible(False)

        if hasattr(origin, "f_osUpload"):
            origin.f_osUpload.setVisible(False)

        if hasattr(origin, "f_osPAssets"):
            origin.f_osPAssets.setVisible(False)

        origin.w_dlConcurrentTasks.setVisible(True)

        curRenderer = getattr(self.core.appPlugin, "getCurrentRenderer", lambda x: "")(
            origin
        ).lower()

        if hasattr(origin, "w_dlGPUpt"):
            showGPUsettings = "redshift" in curRenderer if curRenderer else False
            origin.w_dlGPUpt.setVisible(showGPUsettings)
            origin.w_dlGPUdevices.setVisible(showGPUsettings)

    @err_catcher(name=__name__)
    def sm_render_managerChanged(self, origin):
        getattr(self.core.appPlugin, "sm_render_managerChanged", lambda x, y: None)(
            origin, False
        )

    @err_catcher(name=__name__)
    def sm_render_preExecute(self, origin):
        warnings = []

        return warnings

    @err_catcher(name=__name__)
    def getCurrentSceneFiles(self, origin):
        curFileName = self.core.getCurrentFileName()
        scenefiles = [curFileName]
        return scenefiles

    @err_catcher(name=__name__)
    def getJobName(self, details=None, origin=None):
        scenefileName = os.path.splitext(self.core.getCurrentFileName(path=False))[0]
        details = details or {}
        context = details.copy()
        context["scenefilename"] = scenefileName
        if origin and getattr(origin, "node", None):
            context["ropname"] = origin.node.name()

        jobName = self.core.projects.getResolvedProjectStructurePath("AfanasyJobName", context=context, fallback="")
        return jobName


    @err_catcher(name=__name__)
    def sm_render_submitJob(
        self,
        origin,
        jobOutputFile,
        parent,
        files=None,
        isSecondJob=False,
        prio=None,
        frames=None,
        handleMaster=False,
        details=None,
        allowCleanup=True,
        jobnameSuffix=None,
        useBatch=None,
        sceneDescription=None,
        skipSubmission=False
    ):
    
    
        if self.core.appPlugin.pluginName == "Houdini":
            jobOutputFile = self.processHoudiniPath(origin, jobOutputFile)

        if parent:
            dependencies = parent.dependencies
        else:
            dependencies = []

        jobOutputFileOrig = jobOutputFile

        jobName = self.getJobName(details, origin)
        rangeType = origin.cb_rangeType.currentText()
        frameRange = origin.getFrameRange(rangeType)
        if rangeType != "Expression":
            startFrame, endFrame = frameRange
            if rangeType == "Single Frame":
                endFrame = startFrame
            frameStr = "%s-%s" % (int(startFrame), int(endFrame))
        else:
            frameStr = ",".join([str(x) for x in frameRange])

        jobPrio = origin.sp_rjPrio.value()

        submitScene = self.core.getConfig(
            "Afanasy", "submitScenes", dft=True, config="project"
        )
        
        jobPool = origin.cb_dlPool.currentText()
        jobTimeOut = str(origin.sp_rjTimeout.value())
        jobMachineLimit = str(origin.sp_machineLimit.value())
        jobFramesPerTask = origin.sp_rjFramesPerTask.value()
        jobBatchName = jobName.replace("_high_prio", "")
        suspended = origin.chb_rjSuspended.isChecked()
        if (
            hasattr(origin, "w_dlConcurrentTasks")
            and not origin.w_dlConcurrentTasks.isHidden()
        ):
            jobConcurrentTasks = origin.sp_dlConcurrentTasks.value()
        else:
            jobConcurrentTasks = None

        # Create submission info file

        jobInfos = {}
        jobInfos["Name"] = jobName

        if jobnameSuffix:
            jobInfos["Name"] += jobnameSuffix

        jobInfos["Pool"] = jobPool
        jobInfos["Priority"] = jobPrio
        jobInfos["TaskTimeoutMinutes"] = jobTimeOut
        jobInfos["MachineLimit"] = jobMachineLimit
        jobInfos["Frames"] = frameStr
        jobInfos["ChunkSize"] = jobFramesPerTask
        jobInfos["OutputFilename0"] = jobOutputFile
        self.addEnvironmentItem(jobInfos, "prism_project", self.core.prismIni.replace("\\", "/"))
        self.addEnvironmentItem(jobInfos, "prism_source_scene", self.core.getCurrentFileName())
        if os.getenv("PRISM_LAUNCH_ENV"):
            envData = self.core.configs.readJson(data=os.getenv("PRISM_LAUNCH_ENV"))
            for item in envData.items():
                self.addEnvironmentItem(jobInfos, item[0], item[1])

        if suspended:
            jobInfos["InitialStatus"] = "Suspended"

        if jobConcurrentTasks:
            jobInfos["ConcurrentTasks"] = jobConcurrentTasks

        if sceneDescription or useBatch:
            jobInfos["BatchName"] = jobBatchName

        if len(dependencies) > 0:
            depType = dependencies[0]["type"]
            jobInfos["IsFrameDependent"] = "false" if depType == "job" else "true"
            if depType in ["job", "frame"]:
                jobids = []
                for dep in dependencies:
                    jobids += dep["jobids"]

                jobInfos["JobDependencies"] = ",".join(jobids)
                if depType == "frame":
                    jobInfos["FrameDependencyOffsetStart"] = dependencies[0]["offset"]

            elif depType == "file":
                jobInfos["ScriptDependencies"] = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "AfanasyDependency.py")
                )

        # Create plugin info file

        pluginInfos = {}
        pluginInfos["Build"] = "64bit"

        if hasattr(origin, "w_dlGPUpt") and not origin.w_dlGPUpt.isHidden():
            pluginInfos["GPUsPerTask"] = origin.sp_dlGPUpt.value()

        if hasattr(origin, "w_dlGPUdevices") and not origin.w_dlGPUdevices.isHidden():
            pluginInfos["GPUsSelectDevices"] = origin.le_dlGPUdevices.text()

        if not submitScene:
            pluginInfos["SceneFile"] = self.core.getCurrentFileName()


        arguments = []
        dlParams =[]
        # bake part

        if not origin.gb_prioJob.isChecked():
            arrPath = self.generate_scenes(jobInfos, pluginInfos, arguments)
        else:
            pass

        for i in arrPath:
            jobInfos["PathS"] = i

            if not skipSubmission:
                result = self.AfanasySubmitJob(jobInfos, pluginInfos, arguments)

        result ="Result=Success"
        return result

    def pathGen(self):
        sName = self.core.getCurrentFileName()
        if "." in sName and sName.count('.') == 1:
            path = self.core.getCurrentFileName().split(".")[0].replace("\\", "//")
        else:
            path = "error"
        return path
    def getImageFileNamePrefix ( self ) :

        fileNamePrefix = self.cmds.getAttr('defaultRenderGlobals.imageFilePrefix')
        if fileNamePrefix == None or fileNamePrefix == '':
            fileNamePrefix = getMayaSceneName()
        return fileNamePrefix
        
    @err_catcher(name=__name__)
    def generate_ass(self, jobInfos, pluginInfos, arguments):
        print(jobInfos)

        rangeGet = jobInfos['Frames'].split("-")
        filename = ""
        assArr = []
        # save RenderGlobals
        defGlobals = 'defaultRenderGlobals'
        aiGlobals = 'defaultArnoldRenderOptions'
        saveGlobals = {}

        # override RenderGlobals
        self.cmds.setAttr(defGlobals + '.animation', 1)  # always use 'name.#.ext' format
        self.cmds.setAttr(defGlobals + '.outFormatControl', 0)
        self.cmds.setAttr(defGlobals + '.putFrameBeforeExt', 1)
        separator = ['none', '.', '_'][1]  # to do

        if separator == 'none':
            self.cmds.setAttr(defGlobals + '.periodInExt', 0)
        elif separator == '.':
            self.cmds.setAttr(defGlobals + '.periodInExt', 1)
        else:
            self.cmds.setAttr(defGlobals + '.periodInExt', 2)

        image_name = self.getImageFileNamePrefix()

        self.cmds.setAttr(aiGlobals + '.binaryAss', 1)  # to do ass_binary
        self.cmds.setAttr(aiGlobals + '.expandProcedurals', 1)  # to do
        self.cmds.setAttr(aiGlobals + '.outputAssBoundingBox', 1)  # to do
        self.cmds.setAttr(aiGlobals + '.absoluteTexturePaths', 1)  # to do
        self.cmds.setAttr(aiGlobals + '.absoluteProceduralPaths', 1)  # to do
        self.cmds.setAttr(aiGlobals + '.plugins_path', "", type='string')  # to do
        self.cmds.setAttr(aiGlobals + '.procedural_searchpath', "", type='string')  # to do
        #self.cmds.setAttr(aiGlobals + '.shader_searchpath', "", type='string')  # to do
        self.cmds.setAttr(aiGlobals + '.texture_searchpath', "", type='string')  # to do

        # Clear .output_ass_filename to force using the default filename from RenderGlobals
        self.cmds.setAttr(aiGlobals + '.output_ass_filename', '', type='string')

        ass_dirname = self.cmds.workspace(fileRuleEntry='ASS')
        if ass_dirname == '':
            ass_dirname = 'ass'
            self.cmds.workspace(fileRule=('ASS', ass_dirname))
            self.cmds.workspace(saveWorkspace=True)

        renderLayers = []
        # save the current layer
        current_layer = self.cmds.editRenderLayerGlobals(q=True, currentRenderLayer=True)
        exportAllRenderLayers = ""  # to do
        if exportAllRenderLayers:
            renderLayers = getRenderLayersList(True)  # renderable only
        else:
            # use only the current layer
            renderLayers.append(current_layer)
        
        for layer in renderLayers:
            assgen_cmd = ''

            saveGlobals['renderableLayer'] = self.cmds.getAttr(layer + '.renderable')
            self.cmds.setAttr(layer + '.renderable', True)
            
            
			
            layer_in_filename = layer
            if layer == 'defaultRenderLayer':
                layer_in_filename = 'masterLayer'

            
            
            
            
            assgen_cmd = 'arnoldExportAss' #+ self.get_assgen_options(layer)
            assgen_cmd += ' -startFrame %d' % int(rangeGet[0])
            assgen_cmd += ' -endFrame %d' % int(rangeGet[1])
            assgen_cmd += ' -frameStep %d' % 1
            # if ass_deferred:
                # if ass_binary:
                    # assgen_cmd += ' -ai:bass 1'
                # if ass_export_bounds:
                    # assgen_cmd += ' -ai:exbb 1'
                    
			
			# assgen_cmd += ' -ai:lve 1' # ' -ai:lfv 2'
			# assgen_cmd += ' -ai:sppg "' + ar_plugin_path + '"'
			# assgen_cmd += ' -ai:sppr "' + ar_proc_search_path + '"'
			# assgen_cmd += ' -ai:spsh "' + ar_shader_search_path + '"'
			# assgen_cmd += ' -ai:sptx "' + ar_tex_search_path + '"'
			

			# if ass_compressed :
				# assgen_cmd += ' -compressed'

			# if not ass_binary :
				# assgen_cmd += ' -asciiAss'

			# if ass_selection :
				# assgen_cmd += ' -selected'

			# if ass_expand_procedurals :
				# assgen_cmd += ' -expandProcedurals'
				
			# if ass_export_bounds:
				# assgen_cmd += ' -boundingBox'

            filename += self.pathGen()+ '/' + layer_in_filename
            assgen_cmd += ' -filename "' + filename + '.ass\"'
            
            assArr.append("kick -i " + filename + ".ass") #to do
            self.mel.eval(assgen_cmd)

            self.cmds.setAttr(layer + '.renderable', saveGlobals['renderableLayer'])

        if exportAllRenderLayers:
            # restore the current layer
            cmds.editRenderLayerGlobals(currentRenderLayer=current_layer)
        
        return assArr



    @err_catcher(name=__name__)
    def addEnvironmentItem(self, data, key, value):
        idx = 0
        while True:
            k = "EnvironmentKeyValue" + str(idx)
            if k not in data:
                data[k] = "%s=%s" % (key, value)
                break

            idx += 1

        return data



    @err_catcher(name=__name__)
    def getJobIdFromSubmitResult(self, result):
        result = str(result)
        lines = result.split("\n")
        for line in lines:
            if line.startswith("JobID"):
                jobId = line.split("=")[1]
                return jobId

    @err_catcher(name=__name__)
    def AfanasySubmitJob(self, jobInfos, pluginInfos, arguments):
    
        frame_info = inspect.stack()[1]
        calling_function_name = frame_info.function

        print("Submit")
        print(jobInfos)

        
        service = 'arnold' #to do
        
        self.core.callback(
            name="preSubmit_Afanasy",
            args=[self, jobInfos, pluginInfos, arguments],
        )

        # Create a job
        self.job = self.af.Job(jobInfos['Name'])


        # Set job depend mask
        self.job.setDependMask(jobInfos['Name'])


        # Set maximum tasks that can be executed simultaneously
        self.job.setMaxRunningTasks(15)

        # Set job hosts mask
        self.job.setHostsMask('render.*')
        

        self.job.setPriority(jobInfos['Priority'])

        # Start job paused
        #if jobInfos['InitialStatus']=='Suspended':
        if 'InitialStatus' in jobInfos:
            self.job.offLine()

        # Create a block with provided name and service type
        block = self.af.Block('back', service)

        # Set block tasks command
        block.setCommand(jobInfos["PathS"])

        # Set block tasks preview command arguments
        block.setFiles(['jpg/img.@####@.jpg'])

        # Set block to numeric type, providing first, last frame and frames per host
        rangeGet = jobInfos['Frames'].split("-")
        block.setNumeric(int(rangeGet[0]), int(rangeGet[1]), 1)

        # Add block to the job
        self.job.blocks.append(block)

        # Set command to execute by server after a job is deleted.
        #self.job.setCmdPost('rm /projects/test/nuke/scene.nk.tmp.nk')
        # Send job to Afanasy server

        result = self.job.send()
        if result[0]:
            jobResult="Result=Success"
        else:
            jobResult="Result=Err"


        logger.debug("submitting job: " + str(arguments))
        return jobResult


class PresetWidget(QGroupBox):
    def __init__(self, plugin, presetData=None):
        super(PresetWidget, self).__init__()
        self.plugin = plugin
        self.core = self.plugin.core
        self.core.parentWindow(self)

        self.loadLayout()
        self.connectEvents()
        if presetData:
            self.loadPresetData(presetData)

    @err_catcher(name=__name__)
    def loadLayout(self):
        self.w_add = QWidget()
        self.b_add = QToolButton()
        self.lo_add = QHBoxLayout()
        self.w_add.setLayout(self.lo_add)
        self.lo_add.addStretch()
        self.lo_add.addWidget(self.b_add)

        path = os.path.join(
            self.core.prismRoot, "Scripts", "UserInterfacesPrism", "add.png"
        )
        icon = self.core.media.getColoredIcon(path)
        self.b_add.setIcon(icon)
        self.b_add.setIconSize(QSize(20, 20))
        self.b_add.setToolTip("Add Preset")
        if self.core.appPlugin.pluginName != "Standalone":
            self.b_add.setStyleSheet(
                "QWidget{padding: 0; border-width: 0px;background-color: transparent} QWidget:hover{border-width: 1px; }"
            )

        path = os.path.join(
            self.core.prismRoot, "Scripts", "UserInterfacesPrism", "reset.png"
        )
        icon = self.core.media.getColoredIcon(path)

        self.lo_preset = QVBoxLayout()
        self.lo_main = QVBoxLayout()
        self.setLayout(self.lo_main)
        self.lo_main.addLayout(self.lo_preset)
        self.lo_main.addWidget(self.w_add)
        self.setTitle("Pool Presets")

    @err_catcher(name=__name__)
    def connectEvents(self):
        self.b_add.clicked.connect(self.addItem)

    @err_catcher(name=__name__)
    def refresh(self):
        data = self.getPresetData()
        self.clearItems()
        self.loadPresetData(data)

    @err_catcher(name=__name__)
    def loadPresetData(self, presetData):
        self.clearItems()
        for preset in presetData:
            self.addItem(
                name=preset["name"],
                pool=preset["pool"],
                group=preset["group"]
            )

    @err_catcher(name=__name__)
    def addItem(self, name=None, pool=None, secondaryPool=None, group=None):
        item = PresetItem(self.plugin)
        item.removed.connect(self.removeItem)
        if name:
            item.setName(name)

        if pool:
            item.setPool(pool)

        if group:
            item.setGroup(group)

        self.lo_preset.addWidget(item)
        return item

    @err_catcher(name=__name__)
    def removeItem(self, item):
        idx = self.lo_preset.indexOf(item)
        if idx != -1:
            w = self.lo_preset.takeAt(idx)
            if w.widget():
                w.widget().deleteLater()

    @err_catcher(name=__name__)
    def clearItems(self):
        for idx in reversed(range(self.lo_preset.count())):
            item = self.lo_preset.takeAt(idx)
            w = item.widget()
            if w:
                w.setVisible(False)
                w.deleteLater()

    @err_catcher(name=__name__)
    def getPresetData(self):
        presetData = []
        for idx in range(self.lo_preset.count()):
            w = self.lo_preset.itemAt(idx)
            widget = w.widget()
            if widget:
                if isinstance(widget, PresetItem):
                    if not widget.name():
                        continue

                    sdata = {
                        "name": widget.name(),
                        "pool": widget.pool(),
                        "group": widget.group(),
                    }
                    presetData.append(sdata)

        return presetData


class PresetItem(QWidget):

    removed = Signal(object)

    def __init__(self, plugin):
        super(PresetItem, self).__init__()
        self.plugin = plugin
        self.core = self.plugin.core
        self.loadLayout()

    @err_catcher(name=__name__)
    def loadLayout(self):
        self.e_name = QLineEdit()
        self.e_name.setPlaceholderText("Name")
        self.cb_pool = QComboBox()
        self.cb_pool.setToolTip("Pool")
        self.cb_pool.addItems(["< Pool >"] + self.plugin.getAfanasyPools())
        self.cb_group = QComboBox()
        self.cb_group.setToolTip("Group")
        self.cb_group.addItems(["< Group >"] + self.plugin.getAfanasyGroups())

        self.b_remove = QToolButton()
        self.b_remove.clicked.connect(lambda: self.removed.emit(self))

        self.lo_main = QHBoxLayout()
        self.lo_main.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.lo_main)
        self.lo_main.addWidget(self.e_name, 10)
        self.lo_main.addWidget(self.cb_pool, 10)
        self.lo_main.addWidget(self.cb_group, 10)
        self.lo_main.addWidget(self.b_remove)

        path = os.path.join(
            self.core.prismRoot, "Scripts", "UserInterfacesPrism", "delete.png"
        )
        icon = self.core.media.getColoredIcon(path)
        self.b_remove.setIcon(icon)
        self.b_remove.setIconSize(QSize(20, 20))
        self.b_remove.setToolTip("Delete")
        if self.core.appPlugin.pluginName != "Standalone":
            self.b_remove.setStyleSheet(
                "QWidget{padding: 0; border-width: 0px;background-color: transparent} QWidget:hover{border-width: 1px; }"
            )

    @err_catcher(name=__name__)
    def name(self):
        return self.e_name.text()

    @err_catcher(name=__name__)
    def setName(self, name):
        return self.e_name.setText(name)

    @err_catcher(name=__name__)
    def pool(self):
        return self.cb_pool.currentText()

    @err_catcher(name=__name__)
    def setPool(self, pool):
        idx = self.cb_pool.findText(pool)
        if idx != -1:
            self.cb_pool.setCurrentIndex(idx)

    @err_catcher(name=__name__)
    def group(self):
        return self.cb_group.currentText()

    @err_catcher(name=__name__)
    def setGroup(self, group):
        idx = self.cb_group.findText(group)
        if idx != -1:
            self.cb_group.setCurrentIndex(idx)
