import filecmp
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import mobase

from ..basic_game import BasicGame, BasicGameMappings

try:
    # fmt:off
    from PyQt6.QtCore import QDir, Qt, QTimer
    from PyQt6.QtCore import qCritical as _qCritical
    from PyQt6.QtCore import qInfo as _qInfo
    from PyQt6.QtCore import qVersion
    from PyQt6.QtGui import QAction, QBrush, QIcon, QPalette, QPixmap
    from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QMainWindow,
                                 QMessageBox, QToolBar, QVBoxLayout, QWidget)
except:
    # fmt:off
    from PyQt5.QtCore import QDir, Qt, QTimer
    from PyQt5.QtCore import qCritical as _qCritical
    from PyQt5.QtCore import qInfo as _qInfo
    from PyQt5.QtCore import qVersion
    from PyQt5.QtGui import QBrush, QIcon, QPalette, QPixmap
    from PyQt5.QtWidgets import (QAction, QCheckBox, QComboBox, QDialog,
                                 QMainWindow, QMessageBox, QToolBar,
                                 QVBoxLayout, QWidget)


def qCritical(msg: str, popup=False):
    _qCritical(msg.encode("utf-8"))
    if popup:
        fn = lambda: QMessageBox.critical(
            None, "Mod Organizer 2 Darktide Support Plugin", msg
        )
        QTimer.singleShot(0, fn) if popup == "delayed" else fn()


def qInfo(msg: str):
    _qInfo(msg.encode("utf-8"))


class PluginError(Exception):
    pass


@dataclass
class Mod:
    Priority: int
    Active: bool
    FolderName: str
    NexusID: int = 0
    Name: str = None


NEXUS_DMF = 8
NEXUS_DML = 19
IGNORE = {NEXUS_DML, NEXUS_DMF, "dmf", "base"}

## FIXME: In MO 2.4.4 PluginSetting.key throws "TypeError: No Python class registered for C++ class class QString". If it wasn't for that, I would probably just have these as mobase.PluginSetting
SETTINGS = [
    (
        "combine_with_unmanaged_mods",
        "Also load mods from an existing mod_load_order.txt in the game's mods/ directory.\n"
        "If a mod is both in MO2 and the .txt file, only the MO2 version counts.",
        False,
    ),
    (
        "load_unmanaged_mods_first",
        "When loading unmanaged mods, place them at the top of the mod load order (highest priority).\n"
        "If disabled, place them at the bottom (lowest priority).",
        False,
    ),
    (
        "show_error_popups",
        "When MO2 runs without GUI, show a pop-up window for error messages.\n"
        "If disabled, they only show up in the GUI and/or mo_interface.log",
        True,
    ),
    (
        "inspect_crash",
        "When the game finishes with a non-zero exit code, log an error message.\n"
        "Also searches for Lua Errors in the latest log file in %APPDATA%\\Fatshark\\Darktide\\console_logs",
        True,
    ),
    (
        "override_language",
        "Change the game's language by modifying a virtual copy of your user_settings.config\n"
        'If "language_id" is modified elsewhere, e.g. binaries/mod_loader as documented in DMF, this will not work.\n'
        "warning: While enabled, any changes the game makes to user_settings.config will be written to the virtual copy\n"
        "  instead of the real file. These changes will be lost on the next launch with this setting enabled",
        "",
    ),
    (
        "prefer_microsoft_store_documents",
        "In the sorry case that both default and Microsoft Store documents exist, use %USERPROFILE%\\AppData\\Roaming\\Fatshark\\MicrosoftStore\\Darktide\n"
        "If disabled, the usual path is used: %USERPROFILE%\\AppData\\Roaming\\Fatshark\\Darktide",
        False,
    ),
    (
        "debug_info",
        "Log helpful stuff, including when the program/game is about to run.\n"
        "If you encounter a problem, the log output might help fix it.",
        False,
    ),
]
SETTINGS_CHOICES = {
    "override_language": [
        ("English", "en"),
        ("Deutsch (German)", "de"),
        ("Français (French)", "fr"),
        ("Italiano (Italian)", "it"),
        ("한국어 (Korean)", "ko"),
        ("Español - España (Spanish - Spain)", "es"),
        ("简体中文 (Simplified Chinese)", "zh-cn"),
        ("繁體中文 (Traditional Chinese)", "zh-tw"),
        ("Русский (Russian)", "ru"),
        ("日本語 (Japanese)", "ja"),
        ("Polski (Polish)", "pl"),
        ("Português - Brasil (Portuguese - Brazil)", "pt-br"),
    ]
}


class Warhammer40000DarktideGame(BasicGame, mobase.IPluginFileMapper):
    Name = "Warhammer 40,000: Darktide Support Plugin"
    Author = "Nyvrak"
    Version = "1.0.9"

    GameName = "Warhammer 40,000: Darktide"
    GameShortName = "warhammer40kdarktide"
    GameNexusName = "warhammer40kdarktide"
    GameSteamId = 1361210
    GameBinary = "binaries/Darktide.exe"
    GameDataPath = "mods"

    def __init__(self):
        BasicGame.__init__(self)
        mobase.IPluginFileMapper.__init__(self)

    def init(self, organizer: mobase.IOrganizer):
        BasicGame.init(self, organizer)

        self.show_error_popups = self.getSetting("show_error_popups")
        self._mappings.documentsDirectory._default = (
            lambda _: self.findDocumentsDirectory()
        )

        organizer.onUserInterfaceInitialized(self.onUserInterfaceInitialized)
        organizer.onAboutToRun(self.onAboutToRun)
        organizer.onFinishedRun(self.onFinishedRun)
        organizer.modList().onModInstalled(self.onModInstalled)

        return True

    def findDocumentsDirectory(self):
        paths = [
            "%USERPROFILE%/AppData/Roaming/Fatshark/Darktide",
            "%USERPROFILE%/AppData/Roaming/Fatshark/MicrosoftStore/Darktide",
        ]
        if self.getSetting("prefer_microsoft_store_documents"):
            paths.reverse()

        for p in paths:
            if Path(os.path.expandvars(p)).is_dir():
                self.GameDocumentsDirectory = p
                return QDir(p)

        return BasicGameMappings._default_documents_directory(self)

    def debugInfo(self):
        import json
        import sys

        modList = self._organizer.modList()
        stuff = [
            ("os.name", os.name),
            ("sys.version", sys.version),
            ("sys.api_version", sys.api_version),
            ("qVersion()", qVersion()),
            ("organizer.appVersion()", self._organizer.appVersion()),
            ("allMods()", modList.allMods()),
            ("allModsByProfilePriority()", modList.allModsByProfilePriority()),
            ("Plugin", f"{self.Name}, {self.Author}, {self.Version}"),
            ("getModListTxtMapping()", self.getModListTxtMapping()),
            ("getMo2Mods()", json.dumps(self.getMo2Mods(), default=repr)),
            ("getUnmanagedMods()", json.dumps(self.getUnmanagedMods(), default=repr)),
        ]
        qCritical("Debug Info:\n" + "\n".join(f"{k}={str(v)}" for k, v in stuff))

    def onUserInterfaceInitialized(self, window: QMainWindow):
        self.show_error_popups = False

        # MO2 always calls onUserInterfaceInitialized for every plugin, even when not active
        game = self._organizer.managedGame()
        if not (game == self or game.gameShortName() == self.gameShortName()):
            # stop if our plugin is not active (e.g. not a Darktide instance)
            return

        def _findToolbarAction(actionName):
            toolbar1 = None
            for toolbar in window.findChildren(QToolBar):
                for action in toolbar.actions():
                    toolbar1 = toolbar1 or toolbar
                    if action.objectName() == actionName:
                        return toolbar, action

            return toolbar1, None

        # add custom toolbar icon
        toolbar, action = _findToolbarAction("actionSettings")
        if toolbar:
            try:
                import base64
                import zlib

                self.customAction = QAction(
                    QIcon(
                        QPixmap(
                            zlib.decompress(
                                base64.b85decode(
                                    "c$|IIYg^h#6bJD4=TpQAy~IH0K9fR2Cn3>zuVA(GQ3O%jlBfIq-|d+b+-i5-6Z7N;{GFT`CP)!U5m^&)h@#u*_^)4gu!Y!W3J(dd$R@mkZE}u>hfXkO_&$d&x!{Itcug+R2Hpe<CO9wPEm;UD7`!8E?zw}Q?1dH*cF1EKpFz@^r(8lWSaP9w4t=thN^*D~tekSP0!GfIkqkJwP^Ho!$R!_RKQdS|yt4yE=E4aBnrxNFydkGbN(Z(z9vmFGG)!AagAK!3I{4696zBn2C@nP%$yyY`!AG(ani<H*1@@_6L@tHLIeuy_E5*Q*E2FfBJlNtg<2c2}MmZRhx$#CpNfugZ1=Yq{jA56oCFdOWTI<|ssDqu>-Wb>?8xhw0pf$Fi!Xeoji#{SdQLqw@$zG+(zzMl9%1StGZLLY+GkI*e9>ZB{m)aC2<kC1PU>clCDVc-w*0^p8zL1Ry_qu59Qs?24Y^`@1z6N`vnKUqKZJo66jcm139<In<c~QVMxo|EOFejI(OfB35=R7rDz=EuulsPQPM&`J;Z^@-MzJgV7A><g>>W-|v&lTL0jT_4X9)iaVH_#Zqlk+rJ0)CJy&v1|Z3@&+EDh})5iu+V4Xvk%5@%xRUt+(3Zd~I9KI@eyk=UY(((W|&0zfkt<O$1wU+<CG3XIrq{fBExH$G(T|{{~_Uu_drjeXKZ6{wr`gpWlSP8?5=o-al={dJ`z?`lLQS!NTjw^_~7#025ekpso+DFWNv)LzluuiIHz#ug=ep59+;x`s8l>*h7~_DC)Ybv!I<Ms}FFH+wQX_F;J9jb7K@!m*w+7sK<aRM$75o@{d54Z34IqY`R*qlTMQSF@g$`%TY2~E|*g!m(%XEKo$ZCezsgao+Eq~+5jumW(4~0k(9gPnuLY&6v(pd69qcc)l{i0V-g4G#N{TShL~sra#t1EFgwoVYT1n$^l8atNVI`PV}?p*=eu3J$5d_tq7C#GgKFI@*rZZdNoR^}J_h7)ILrz?X|UGe9DM0?!-OQT%?KjJG1$79F@}T8c6V?^mJ)yZ*ro^kVNj}SX2~#9Z2i#dB-7Py2iIXU!e}%)l8dGpj7HO`STySjJ9rY<36=b48iv;}lV)<X!WNAO=6`R|-lUn(_qAS|WCzzYF^AAUeX@yr>vh$|$u=`;tk)?#yuNtyV1#LYzsGs5d+i&CIc(|q?*x08%$nwBbw6vj#$maS53in|oo;HZy?$saUzYgd^XX~vF$$0WJElXKPz7UycrX|gcn&`7N73Jh1DTN"
                                )
                            )
                            .decode()
                            .splitlines()
                        )
                    ),
                    "Darktide Settings",
                    action.parent(),
                )
                self.customAction.triggered.connect(self.onCustomSettingsOpened)
                toolbar.insertAction(action, self.customAction)
            except Exception as e:
                qCritical(str(e))

    def onCustomSettingsOpened(self, checked: bool):
        DarktideSettingsDialog(self).exec()

    def generateCustomMappings(self):
        mo2Mods = self.getMo2Mods()
        mappings = []

        # add our custom mappings for DML, if installed
        if dml := next((m for m in mo2Mods if m.NexusID == NEXUS_DML and m.Active), None):
            toAdd = self.applyDML(self._organizer.modList().getMod(dml.Name))
            mappings.extend(toAdd)

        # add mapping for mod_load_order.txt
        mappings.append(self.writeModListTxt(mo2Mods))

        # virtualize user_settings.config to override language
        if config := self.writeUserSettingsConfig():
            mappings.append(config)

        return mappings

    def onAboutToRun(self, appPath: str):
        try:
            if self.getSetting("debug_info"):
                self.debugInfo()

            self.customMappings = self.generateCustomMappings()

            return True
        except PluginError as err:
            qCritical(str(err), popup=self.show_error_popups)
            return False

    def onFinishedRun(self, appPath: str, exitCode: int):
        STILL_ACTIVE = 259
        OK_STATUS = {None, 0, STILL_ACTIVE}

        if exitCode not in OK_STATUS and self.getSetting("inspect_crash"):
            msg = [f"{Path(appPath).name} exited with code {exitCode}"]

            logDir = Path(self.documentsDirectory().absoluteFilePath("console_logs"))
            if latestLog := max(logDir.glob("*.log"), key=os.path.getmtime, default=None):
                with latestLog.open("r") as f:
                    if errors := re.findall(
                        r"<<Lua Error>>(.+?)<</Lua Error>>",
                        f.read(),
                        re.DOTALL | re.IGNORECASE,
                    ):

                        def _timeAgo(seconds):
                            for unit, name in [
                                (60 * 60 * 24, "day"),
                                (60 * 60, "hour"),
                                (60, "minute"),
                                (1, "second"),
                            ]:
                                if seconds >= unit:
                                    n = int(seconds / unit)
                                    return f"{n} {name}" + (" ago" if n == 1 else "s ago")
                            return "now"

                        seconds = (
                            datetime.now(tz=timezone.utc).timestamp()
                            - latestLog.stat().st_mtime
                        )
                        msg.append(
                            f"\n\nRecent Lua Errors in\n{latestLog.name}\n    (modified {_timeAgo(seconds)})\n"
                        )
                        msg.extend(f"\n#{i}: {s}" for i, s in enumerate(errors, 1))

            qCritical("".join(msg), popup=self.show_error_popups and "delayed")

    def onModInstalled(self, mod: mobase.IModInterface):
        self.autoDetectMod(mod)
        if mod.nexusId() == NEXUS_DML:
            self.installDML(mod)

    def mappings(self):
        return self.customMappings

    def settings(self):
        ## FIXME: In MO 2.4.4 PluginSetting.key throws "TypeError: No Python class registered for C++ class class QString". If it wasn't for that, I would probably just have these as mobase.PluginSetting
        return [mobase.PluginSetting(*s) for s in SETTINGS]

    def getSetting(self, key: str):
        return self._organizer.pluginSetting(self.name(), key)

    def setSetting(self, key: str, value):
        self._organizer.setPluginSetting(self.name(), key, value)

    def get(self, key: str, default=None):
        return self._organizer.persistent(self.name(), key, default)

    def set(self, key: str, value, sync=True):
        self._organizer.setPersistent(self.name(), key, value, sync)

    def customMappingsDirectory(self):
        return Path(self._organizer.basePath()) / "custom_mappings/Darktide Mod Loader"

    def getModListTxtMapping(self):
        ## FIXME: I wish I didn't need to do this... but same issue as settings()
        return (
            str(self._organizer.profilePath() / Path("mod_load_order.txt")),
            self.dataDirectory().absoluteFilePath("mod_load_order.txt"),
        )

    def getMo2Mods(self):
        modList = self._organizer.modList()
        return [
            Mod(
                modList.priority(name),
                bool(modList.state(name) & mobase.ModState.ACTIVE),
                self.getModFolderName(mod),
                mod.nexusId(),
                name,
            )
            for name in modList.allModsByProfilePriority()
            if (mod := modList.getMod(name))
        ]

    def getUnmanagedMods(self):
        listFile = Path(self.getModListTxtMapping()[1])
        if not listFile.exists():
            return []

        modsDir = self.dataDirectory()
        with listFile.open(encoding="utf-8") as f:
            return [
                name
                for line in f.read().splitlines()
                if (name := line.strip())
                and not name.startswith("--")
                and modsDir.exists(f"{name}/{name}.mod")
            ]

    def autoDetectMod(self, mod: mobase.IModInterface):
        if mod.nexusId():
            return
        tree = mod.fileTree()

        if tree.find("binaries/mod_loader", mobase.FileTreeEntry.FileTypes.FILE):
            qInfo(f"Auto-detected mod '{mod.name()}' as Darktide Mod Loader")
            mod.setNexusID(NEXUS_DML)
            return

        if tree.find("dmf/dmf.mod", mobase.FileTreeEntry.FileTypes.FILE):
            qInfo(f"Auto-detected mod '{mod.name()}' as Darktide Mod Framework")
            mod.setNexusID(NEXUS_DMF)
            return

    def installDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML

        modDir = Path(mod.absolutePath())
        customDir = self.customMappingsDirectory()
        shutil.rmtree(customDir, ignore_errors=True)

        ## TODO: this whole "manual mapping of parts of a mod" thing could be made into a helper class or whatever

        # move the contents of DML into a custom folder, we will map them manually
        def _moveFiles(name: str, entry: mobase.FileTreeEntry):
            path = entry.path()
            src = modDir / path
            if src.exists():
                shutil.move(src, customDir / path)
            return mobase.IFileTree.WalkReturn.CONTINUE

        mod.fileTree().walk(_moveFiles)

        # unwrap the mods/ directory and move contents back so they can naturally get overridden by other mods, e.g. "Auto Mod Loading and Ordering"
        customMods = customDir / "mods"
        for item in os.listdir(customMods):
            shutil.move(customMods / item, modDir / item)
        os.rmdir(customMods)  # not needed but I'm paranoid

        qInfo(f"Installed Darktide Mod Loader to: '{customDir}'")

    def applyDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML

        gameDir = Path(self.gameDirectory().absolutePath())
        customDir = self.customMappingsDirectory()
        if not customDir.exists():
            raise PluginError(
                f"Tried to apply DML but missing directory: '{customDir}'. Try reinstalling Darktide Mod Loader"
            )

        BUNDLE_DB = "bundle/bundle_database.data"
        gameBundle = gameDir / BUNDLE_DB
        customBundle = customDir / BUNDLE_DB
        customBundleBak = customDir / (BUNDLE_DB + ".bak")

        foundPatchedBundle = (
            customBundle.is_file()
            and customBundleBak.is_file()
            and filecmp.cmp(gameBundle, customBundleBak)
            and not filecmp.cmp(gameBundle, customBundle)
        )

        if not foundPatchedBundle:
            patcher = customDir / "tools/dtkit-patch.exe"
            if not patcher.is_file():
                raise PluginError(
                    f"Tried to patch '{customBundle}' with DML but missing patcher: '{patcher}'. Try reinstalling Darktide Mod Loader"
                )

            # patch a fresh bundle database
            shutil.copy(gameBundle, customBundle)
            patcher = subprocess.run(
                [patcher, "--patch", customBundle.parent],
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            qInfo(f"dtkit-patch.exe: {patcher.stderr.decode().strip()}")

        # map {customDir}/Path to {gameDir}/Path
        mappings = [
            mobase.Mapping(
                str(path.absolute()),
                str(gameDir / path.relative_to(customDir)),
                not path.is_file(),
            )
            for path in customDir.iterdir()
        ]
        if not mappings:
            raise PluginError(
                "Tried to generate custom mappings for DML but got nothing! Try reinstalling Darktide Mod Loader"
            )

        return mappings

    def writeModListTxt(self, mo2Mods: List[Mod] = None):
        mo2Mods = mo2Mods or self.getMo2Mods()
        modsDict: Dict[str, Mod] = {}

        # add MO2 mods
        for mod in mo2Mods:
            # here we only care about things that go into mod_load_order.txt
            if not mod.FolderName:
                continue

            # make sure active mods dont get deactivated by other mods changing the same folder
            existing = modsDict.get(mod.FolderName)
            if not existing or (not existing.Active and mod.Active):
                modsDict[mod.FolderName] = mod

        # optionally add unmanaged mods
        if self.getSetting("combine_with_unmanaged_mods"):
            unmanagedMods = self.getUnmanagedMods()
            unmanagedPriority = (
                -len(unmanagedMods)
                if self.getSetting("load_unmanaged_mods_first")
                else len(mo2Mods)
            )
            for i, name in enumerate(unmanagedMods, unmanagedPriority):
                if name not in modsDict:
                    modsDict[name] = Mod(i, True, name)

        # generate new mod list
        mapping = self.getModListTxtMapping()
        with open(mapping[0], mode="w", encoding="utf-8") as f:
            for mod in sorted(modsDict.values(), key=lambda m: m.Priority):
                if mod.FolderName in IGNORE:
                    continue

                if mod.Active:
                    f.write(f"{mod.FolderName}\n")
                else:
                    f.write(f"--{mod.FolderName}\n")

        return mobase.Mapping(*mapping, False)

    def writeUserSettingsConfig(self):
        if lang := self.getSetting("override_language"):
            CONFIG = "user_settings.config"
            userConfig = Path(self.documentsDirectory().absoluteFilePath(CONFIG))
            virtConfig = Path(self._organizer.overwritePath()) / CONFIG

            md5 = hashlib.md5()
            md5.update(lang.encode("utf-8"))
            if userConfig.is_file():
                md5.update(userConfig.read_bytes())
            configHash = md5.digest().hex().casefold()

            isNewConfig = configHash != self.get(CONFIG)
            if isNewConfig:
                self.set(CONFIG, configHash, False)

                pattern = re.compile(r"^\s*language_id\s*=\s*\".*?\"\s*$", re.IGNORECASE)
                with virtConfig.open("w", encoding="utf-8", newline="\n") as virt:
                    if userConfig.is_file():
                        with userConfig.open("r", encoding="utf-8") as user:
                            virt.writelines(
                                line for line in user if not pattern.match(line)
                            )
                    virt.write(f'language_id = "{lang}"\n')

                qInfo(f"Generated new virtual config '{virtConfig}'")

            return mobase.Mapping(str(virtConfig), str(userConfig), False, True)

    def getModFolderName(self, mod: mobase.IModInterface):
        if mod.isSeparator():
            return
        if mod.nexusId() in IGNORE:
            return

        tree = mod.fileTree()
        folderName: str = None

        def _findModFile(name: str, entry: mobase.FileTreeEntry):
            if entry.isDir():
                name = entry.name()
                if tree.find(f"{name}/{name}.mod", mobase.FileTreeEntry.FILE):
                    nonlocal folderName
                    folderName = name
                    return mobase.IFileTree.WalkReturn.STOP

            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(_findModFile)

        if not folderName:
            qCritical(f"Could not find mod folder name for: '{mod.name()}'")

        return folderName


class DarktideSettingsDialog(QDialog):
    def __init__(self, game: Warhammer40000DarktideGame):
        QDialog.__init__(self)
        self.game = game
        self.setWindowTitle("Darktide Settings")
        self.setWindowIcon(game.customAction.icon())
        self.finished.connect(self.onFinished)
        self.initWidgets()

    def initWidgets(self):
        self.widgets: Dict[str, QWidget] = {}
        self.initial: Dict[str, bool] = {}
        layout = QVBoxLayout(self)

        bg = self.palette().highlight().color()
        fg = self.palette().highlightedText().color()
        disabled = self.palette().color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text
        )
        pt = max(self.font().pointSize(), 11)
        self.setStyleSheet(
            f"* {{ font-size: {pt}pt; }}"
            "QCheckBox { padding: 5px; border-radius: 5px; }"
            f"QCheckBox:hover {{ background-color: {bg.name()}; color: {fg.name()};  }}"
            f'QComboBox[sad="true"] {{ color: {disabled.name()}; }}'
        )

        # settings
        for settingKey, settingDesc, settingDefault in SETTINGS:
            data = self.game.getSetting(settingKey)
            self.initial[settingKey] = data

            if isinstance(settingDefault, bool):
                # simple toggle
                checkbox = QCheckBox(settingKey)
                checkbox.setToolTip(settingDesc)
                checkbox.setChecked(data)
                checkbox.toggled.connect(lambda v: self.onSettingChanged(v, settingKey))
                self.widgets[settingKey] = checkbox
                layout.addWidget(checkbox)
                continue

            if choices := SETTINGS_CHOICES.get(settingKey):
                # dropdown select
                combo = QComboBox()
                combo.setToolTip(settingDesc)
                combo.addItem(settingKey, "")
                for label, choice in choices:
                    combo.addItem(label, choice)
                combo.setCurrentIndex(max(0, combo.findData(data)))

                def _update_style(index):
                    combo.setProperty("sad", index == 0)
                    combo.style().polish(combo)

                _update_style(combo.currentIndex())
                combo.currentIndexChanged.connect(_update_style)
                combo.setItemData(0, QBrush(disabled), Qt.ItemDataRole.ForegroundRole)

                self.widgets[settingKey] = combo
                layout.addWidget(combo)
                continue

        self.widgets["debug_info"].toggled.connect(lambda v: v and self.game.debugInfo())

        self.updateSettingCoherency()

    def updateSettingCoherency(self):
        self.widgets["load_unmanaged_mods_first"].setEnabled(
            self.widgets["combine_with_unmanaged_mods"].isChecked()
        )
        self.widgets["inspect_crash"].setEnabled(
            self.widgets["show_error_popups"].isChecked()
        )

    def onSettingChanged(self, value: bool, key: str):
        self.updateSettingCoherency()

    def onFinished(self, result: int):
        for k, v0 in self.initial.items():
            w = self.widgets[k]
            v = w.currentData() if isinstance(w, QComboBox) else w.isChecked()
            if v0 != v:
                self.game.setSetting(k, v)
