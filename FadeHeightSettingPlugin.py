# Copyright (c) 2022 fieldOfView, ketchu13
# The FadeHeightSettingPlugin is a ketchu13 modified version of LinearAdvanceSettingPlugin by fieldOfView
# Released under the terms of the AGPLv3 or higher.
import logging
from logging import handlers, Logger

from collections import OrderedDict
from typing import List

from UM.Application import Application
from UM.Extension import Extension

from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.SettingDefinition import SettingDefinition


class K13Logger(Logger):
    def __init__(self, name: str):
        super().__init__(name=name, level="debug")
        self._name = name
        self._logger = None
        self.setLogger()

    def check_init_logger(self):
        if not self._logger:
            self.setLogger()

    def setLogger(self):
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)
        hdlr = logging.handlers.RotatingFileHandler(
            filename='logs/%s_.log' % self._name,
            encoding='utf-8',
            maxBytes=3 * 1024 * 1024,  # 32 MiB
            backupCount=9,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        hdlr.setFormatter(formatter)
        self._logger.addHandler(hdlr)

    def get(self):
        return self._logger


class FadeHeightSettingPlugin(Extension):
    def __init__(self):
        super().__init__()
        self.logger = K13Logger("FadeHeightSettingPlugin")
        self._application = Application.getInstance()

        self._i18n_catalog = None

        self._fade_height_setting_key = "fade_height_mm"
        self._abl_enabled_key         = "abl_enabled"

        self._settings_dict = OrderedDict()
        self._settings_dict[self._fade_height_setting_key] = {
            "label"                 : "Fade Height",
            "description"           : "Sets the auto bed leveling fade height in mm. Note that unless this setting is used in a start gcode snippet, it has no effect!",
            "type"                  : "float",
            "unit"                  : "mm",
            "default_value"         : 0,
            "minimum_value"         : 0,
            "maximum_value_warning" : 999,
            "resolve"               : "extruderValue(adhesion_extruder_nr, 'adhesion_z_offset') if resolveOrValue('adhesion_type') != 'none' else min(extruderValues('adhesion_z_offset'))",
            "settable_per_mesh"     : False,
            "settable_per_extruder" : False,
            "settable_per_meshgroup": False,
            "enabled"               : "abl_enabled"
        }
        self._settings_dict[self._abl_enabled_key] = {
            "label"                 : "Auto bed leveling correction",
            "description"           : "Enable or disable the bed leveling correction.",
            "type"                  : "bool",
            "default_value"         : False,
            "value"                 : True,
            "settable_per_mesh"     : False,
            "settable_per_extruder" : False,
            "settable_per_meshgroup": False
        }
        self._expanded_categories = []  # type: List[str]  # temporary list used while creating nested settings

        ContainerRegistry.getInstance().containerLoadComplete.connect(self._onContainerLoadComplete)

        self._application.getOutputDeviceManager().writeStarted.connect(self._filterGcode)

    def _onContainerLoadComplete(self, container_id: str):
        if not ContainerRegistry.getInstance().isLoaded(container_id):
            self.logger.info("skip containers that could not be loaded, or subsequent findContainers() will cause an infinite loop")
            return

        try:
            container = ContainerRegistry.getInstance().findContainers(id=container_id)[0]
        except IndexError:
            self.logger.info("the container no longer exists")
            return

        if not isinstance(container, DefinitionContainer):
            self.logger.info("skip containers that are not definitions")
            return
        if container.getMetaDataEntry("type") == "extruder":
            self.logger.info("kip extruder definitions")
            return

        platform_adhesion_category = container.findDefinitions(key="platform_adhesion")

        fh_setting = container.findDefinitions(key=list(self._settings_dict.keys())[0])

        if platform_adhesion_category and not fh_setting:
            platform_adhesion_category = platform_adhesion_category[0]
            for setting_key, setting_dict in self._settings_dict.items():
                setting_definition = SettingDefinition(setting_key, container, platform_adhesion_category, self._i18n_catalog)
                setting_definition.deserialize(setting_dict)

                platform_adhesion_category._children.append(setting_definition)
                container._definition_cache[setting_key] = setting_definition
                container._updateRelations(setting_definition)

    def getPropVal(self, name_key: str) -> str or None:
        """Get the property value by is naming"""
        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return None
        property_value = global_container_stack.getProperty(name_key, "value")
        return property_value

    def _filterGcode(self, output_device):
        scene = self._application.getController().getScene()

        global_container_stack = self._application.getGlobalContainerStack()
        used_extruder_stacks = self._application.getExtruderManager().getUsedExtruderStacks()
        if not global_container_stack or not used_extruder_stacks:
            return

        self.logger.debug("check if Fade Height settings are already applied")
        start_gcode = global_container_stack.getProperty("machine_start_gcode", "value")
        if "M420 " in start_gcode:
            return

        self.logger.debug("get setting from Cura")
        fade_height_mm = self.getPropVal(self._fade_height_setting_key)
        abl_enabled = self.getPropVal(self._abl_enabled_key)

        gcode_dict = getattr(scene, "gcode_dict", {})
        if not gcode_dict:  # this also checks for an empty dict
            self.logger.warning("Scene has no gcode to process")
            return

        dict_changed = False
        for plate_id in gcode_dict:
            gcode_list = gcode_dict[plate_id]
            if len(gcode_list) < 2:
                self.logger.warning("Plate %s does not contain any layers", plate_id)
            else:
                if ";FADEHEIGHTPROCESSED\n" not in gcode_list[0]:
                    gcode_list[1] = gcode_list[1] +\
                                    ("M420 S%i Z%d ;added by FadeHeightSettingPlugin\n" % (int(abl_enabled), fade_height_mm))
                    gcode_list[0] += ";FADEHEIGHTPROCESSED\n"
                    gcode_dict[plate_id] = gcode_list
                    dict_changed = True
                else:
                    self.logger.debug("Plate %s has already been processed", plate_id)

        if dict_changed:
            setattr(scene, "gcode_dict", gcode_dict)
