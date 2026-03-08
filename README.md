# Mod Organizer 2 Plugin for Darktide

[NexusMods page](https://www.nexusmods.com/warhammer40kdarktide/mods/492)

## Changelog

### Version 1.0.10
- prevent inactive mods from replacing active ones with same folder name
  
### Version 1.0.9
- fix Desktop shortcut not loading mods

### Version 1.0.8
- use utf-8

### Version 1.0.7
- support "Auto Mod Loading and Ordering" and any other mod that modifies Darktide Mod Loader's mods/ folder

### Version 1.0.6
- fix zip files(?) / phantom issue for real this time?
- ban dmf/base from ever entering mod_load_order.txt
- re-style settings dialog a bit
- add a Debug Info print setting
- general refactor
  
### Version 1.0.5
- hotfix for raw zip files

### Version 1.0.4
- combine with "experimental" version, perhaps an even bigger experiment. hopefully this absolves the pyqt5 branch
- no longer uses overwrite/ folder. Mod list is written into the profile/ folder
- play nicer with other global instances
  - only show custom toolbar icon for Darktide instance
  - fix error when switching to other instance (walkTree returning None)
- ability to install Darktide Mod Loader, wow. (on NexusMods, you need to right-click the "Manual Download" button, copy the link address, append &nmm=1 and download using that link)
- fix xpm.py script messing up transparency when quantizing

### Version 1.0.3c
- fixed walkTree() returning None...
  
### Version 1.0.3b
- make compatible with Mod Organizer v2.4.4 (PyQt5, Python 3.8). Maybe helps with SteamTinkerLaunch?

### Version 1.0.3
- fix "load_unmanaged_mods_first" not working sometimes
- added alternative version 1.0.3b

### Version 1.0.2
- mod_load_order.txt is no longer overwritten but instead generated in the overwrite/ folder
- ummanaged mods are no longer combined by default, but you can enable it in the settings
- can change unmanaged mods priority in the settings
- added a custom toolbar button for only the plugin's settings

### Version 1.0.1
- find the mod folder by looking for a .mod file
