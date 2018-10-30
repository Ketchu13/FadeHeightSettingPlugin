# FadeHeightSettingPlugin

This plugin adds a setting named **Fade Height** to the platform Adhesion category in the Custom print setup of **Cura**.

*"Fade height gradually reduce leveling correction until a set height is reached "*_ Marlin Firmware

If the start gcode doesn't include a M420 statement to set the fade height value, a single G-code line is added after the start G-code:
```
...
M420 S{abl_enabled} Z{fade_height_mm}
...
```
**What's new in v 0.1.3:**
* Fix version number.
* Edit some comments / descriptions.
* Setting now disable the bed leveling correction, instead of turning off the plugin.
* Fix missing assignement.
