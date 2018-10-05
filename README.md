# FadeHeightSettingPlugin

This plugin adds a setting named "Fade Height" to the platform Adhesion category in the Custom print setup of Cura.

If the start gcode doesn't include an M420 statement to set the fade height value, a single G-code line is added before the start G-code:
```
...
M420 Z{fade_height_mm}
...
```

Users may want to add more detailed M420 parameters in their start G-code snippet, eg:

```
...
M420 S0 => Auto bed leveling disabled (0, 1)
...
```
