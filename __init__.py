# Copyright (c) 2019 ketchu13
# The FadeHeightSettingPlugin is released under the terms of the AGPLv3 or higher.

from . import FadeHeightSettingPlugin


def getMetaData():
    return {}

def register(app):
    return {"extension": FadeHeightSettingPlugin.FadeHeightSettingPlugin()}
