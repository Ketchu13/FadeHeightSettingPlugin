# Copyright (c) 2018 fieldOfView
# The FadeHeightSettingPlugin is a ketchu13 modified version of LinearAdvanceSettingPlugin by fieldOfView
# Released under the terms of the AGPLv3 or higher.

import re
from collections import OrderedDict
from UM.Extension import Extension
from UM.Application import Application
from UM.Settings.ContainerRegistry import ContainerRegistry
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Settings.SettingDefinition import SettingDefinition
from UM.Logger import Logger


class FadeHeightSettingPlugin(Extension):

    def __init__(self):
        super().__init__()

        self._application = Application.getInstance()

        self._i18n_catalog = None

        self._fade_height_setting_key = "fade_height_mm"
        self._abl_enabled_key = "abl_enabled"

        self._settings_dict = OrderedDict()
        self._settings_dict[self._fade_height_setting_key] = {
            "label": "Fade Height",
            "description": "Sets the auto bed leveling fade height in mm. Note that unless this setting is used in a start gcode snippet, it has no effect!",
            "type": "float",
            "unit": "mm",
            "default_value": 0,
            "minimum_value": 0,
            "maximum_value_warning": 999,

            "settable_per_mesh": False,
            "settable_per_extruder": False,
            "settable_per_meshgroup": False,
            "enabled": "abl_enabled"
        }
        self._settings_dict[self._abl_enabled_key] = {
            "label": "Auto bed leveling correction",
            "description": "Enable or disable the bed leveling correction.",
            "type": "bool",
            "default_value": False,
            "value": True,
            "settable_per_mesh": False,
            "settable_per_extruder": False,
            "settable_per_meshgroup": False
        }

        ContainerRegistry.getInstance().containerLoadComplete.connect(self._onContainerLoadComplete)

        self._application.getOutputDeviceManager().writeStarted.connect(self._filterGcode)

    def _onContainerLoadComplete(self, container_id):
        if not ContainerRegistry.getInstance().isLoaded(container_id):
            # skip containers that could not be loaded, or subsequent findContainers() will cause an infinite loop
            return

        try:
            container = ContainerRegistry.getInstance().findContainers(id=container_id)[0]
        except IndexError:
            # the container no longer exists
            return

        if not isinstance(container, DefinitionContainer):
            # skip containers that are not definitions
            return
        if container.getMetaDataEntry("type") == "extruder":
            # skip extruder definitions
            return

        platform_adhesion_category = container.findDefinitions(key="platform_adhesion")
        fh_setting = container.findDefinitions(key=list(self._settings_dict.keys())[0])
        if platform_adhesion_category and not fh_setting:
            # this machine doesn't have a zoffset setting yet
            platform_adhesion_category = platform_adhesion_category[0]
            for setting_key, setting_dict in self._settings_dict.items():
                definition = SettingDefinition(setting_key, container, platform_adhesion_category, self._i18n_catalog)
                definition.deserialize(setting_dict)

                # add the setting to the already existing platform adhesion settingdefinition
                # private member access is naughty, but the alternative is to serialise, nix and deserialise the whole thing,
                # which breaks stuff
                platform_adhesion_category._children.append(definition)
                container._definition_cache[setting_key] = definition
                container._updateRelations(definition)


    def getPropVal(self, name_key):
        """Get the property value by is name"""
        property_value = self._global_container_stack.getProperty(name_key, "value")
        return property_value


    def _filterGcode(self, output_device):
        scene = self._application.getController().getScene()

        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return

        # check if Fade Height settings are already applied
        start_gcode = global_container_stack.getProperty("machine_start_gcode", "value")
        if "M420 " in start_gcode:
            return

        # get setting from Cura
        fade_height_mm = self.getPropVal()
        abl_enabled = self.getPropVal(self._abl_enabled_key)

        # if fade_height_mm == 0 or abl_enabled is False:
        # return

        gcode_dict = getattr(scene, "gcode_dict", {})
        if not gcode_dict:  # this also checks for an empty dict
            Logger.log("w", "Scene has no gcode to process")
            return

        dict_changed = False
        for plate_id in gcode_dict:
            gcode_list = gcode_dict[plate_id]
            if len(gcode_list) < 2:
                Logger.log("w", "Plate %s does not contain any layers", plate_id)
                continue

            if ";FADEHEIGHTPROCESSED\n" not in gcode_list[0]:
                gcode_list[1] = gcode_list[1] + ("M420 S%i Z%d ;added by FadeHeightSettingPlugin\n" % (
                    int(abl_enabled), fade_height_mm))

                gcode_list[0] += ";FADEHEIGHTPROCESSED\n"
                gcode_dict[plate_id] = gcode_list
                dict_changed = True
            else:
                Logger.log("d", "Plate %s has already been processed", plate_id)
                continue

        if dict_changed:
            setattr(scene, "gcode_dict", gcode_dict)
