from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import mobase

try:
    from PyQt6.QtCore import qCritical as _qCritical, qInfo as _qInfo, qVersion
    from PyQt6.QtGui import QAction, QIcon, QPixmap
    from PyQt6.QtWidgets import QCheckBox, QDialog, QMainWindow, QPushButton, QToolBar, QVBoxLayout # fmt:skip
except:
    from PyQt5.QtCore import qCritical as _qCritical, qInfo as _qInfo, qVersion
    from PyQt5.QtGui import QIcon, QPixmap
    from PyQt5.QtWidgets import QAction, QCheckBox, QDialog, QMainWindow, QPushButton, QToolBar, QVBoxLayout # fmt:skip


def qCritical(msg: str):
    _qCritical(msg.encode("utf-8"))


def qInfo(msg: str):
    _qInfo(msg.encode("utf-8"))


from ..basic_game import BasicGame


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

# In MO 2.4.4 PluginSetting.key throws "TypeError: No Python class registered for C++ class class QString"
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
        "debug_info_on_run",
        "Log helpful stuff when the program/game is about to run.\n"
        "If you encounter a bug, the log output might help fix it.",
        False,
    ),
]


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
        # managedGame() doesn't exist yet...
        organizer.onUserInterfaceInitialized(self.onUserInterfaceInitialized)
        self.customMappings = None
        return True

    def debugInfo(self):
        import json, os, sys

        modList = self._organizer.modList()

        # i'm not even gonna risk using f"{expr=}" ...
        qCritical(f"Debug Info:")
        qCritical(f"os.name={str(os.name)}")
        qCritical(f"sys.version={str(sys.version)}")
        qCritical(f"sys.api_version={str(sys.api_version)}")
        qCritical(f"qVersion()={qVersion()}")
        qCritical(f"organizer.appVersion()={str(self._organizer.appVersion())}")
        qCritical(f"allMods()={modList.allMods()}")
        qCritical(f"allModsByProfilePriority()={modList.allModsByProfilePriority()}")
        qCritical(f"Plugin={self.Name}, {self.Author}, {self.Version}")
        qCritical(f"getModListMappingRaw()={self.getModListMappingRaw()}")
        qCritical(f"getMods()={json.dumps(self.getMods(), default=repr)}")
        qCritical(
            f"getUnmanagedMods()={json.dumps(self.getModsUnmanaged(), default=repr)}"
        )

    def onUserInterfaceInitialized(self, window: QMainWindow):
        if self._organizer.managedGame().gameShortName() != self.GameShortName:
            # stop if this is not a Darktide instance...
            return

        # register events
        self._organizer.onAboutToRun(self.onAboutToRun)
        self._organizer.modList().onModInstalled(self.onModInstalled)

        # add custom toolbar icon
        for toolbar in window.findChildren(QToolBar):
            for action in toolbar.actions():
                if action.objectName() != "actionSettings":
                    continue

                try:
                    import base64, zlib

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
                finally:
                    return

    def onCustomSettingsOpened(self, checked: bool):
        DarktideSettingsDialog(self).exec()

    def generateCustomMappings(self):
        if self.getSetting("debug_info_on_run"):
            self.debugInfo()

        mods = self.getMods()

        # generate mappings
        mappings = []
        for mod in mods:
            if mod.NexusID == NEXUS_DML:
                if mod.Active:
                    modList = self._organizer.modList()
                    if not (m := self.applyDML(modList.getMod(mod.Name))):
                        return None
                    mappings = m
                break

        self.customMappings = [*mappings, self.getModListMapping()]

        # update mod list
        self.updateModLoadOrder(mods)

        return self.customMappings

    def onAboutToRun(self, appPath: str):
        # this only happens in "interactive" mode (not when running shortcuts e.g.)
        try:
            return bool(self.generateCustomMappings())
        except PluginError as err:
            qCritical(str(err))

    def onModInstalled(self, mod: mobase.IModInterface):
        self.autodetectMod(mod)
        if mod.nexusId() == NEXUS_DML:
            self.installDML(mod)

    def mappings(self):
        return self.customMappings or self.generateCustomMappings()

    def settings(self):
        return [mobase.PluginSetting(*s) for s in SETTINGS]

    def getSetting(self, key: str):
        return self._organizer.pluginSetting(self.name(), key)

    def setSetting(self, key: str, value):
        self._organizer.setPluginSetting(self.name(), key, value)

    def getCustomMappingDir(self):
        return Path(self._organizer.basePath()) / "custom_mappings/Darktide Mod Loader"

    def getModListMappingRaw(self):
        # i wish i didn't need to do this... but same issue as settings()
        return (
            str(self._organizer.profilePath() / Path("mod_load_order.txt")),
            self.dataDirectory().absoluteFilePath("mod_load_order.txt"),
        )

    def getModListMapping(self):
        return mobase.Mapping(
            *self.getModListMappingRaw(),
            False,
        )

    def getMods(self):
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

    def getModsUnmanaged(self):
        listFile = Path(self.getModListMappingRaw()[1])
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

    def autodetectMod(self, mod: mobase.IModInterface):
        if mod.nexusId():
            return

        if mod.fileTree().find(
            "binaries/mod_loader", mobase.FileTreeEntry.FileTypes.FILE
        ):
            qInfo(f"Auto-detected mod '{mod.name()}' as Darktide Mod Loader")
            mod.setNexusID(NEXUS_DML)
        elif mod.fileTree().find("dmf/dmf.mod", mobase.FileTreeEntry.FileTypes.FILE):
            qInfo(f"Auto-detected mod '{mod.name()}' as Darktide Mod Framework")
            mod.setNexusID(NEXUS_DMF)

    def installDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML
        import os, shutil

        modDir = Path(mod.absolutePath())
        customDir = self.getCustomMappingDir()
        shutil.rmtree(customDir, ignore_errors=True)

        ## TODO: this whole "manual mapping of parts of a mod" thing could be made into a helper class or whatever

        # move the contents of DML into a custom folder, we will map them manually
        def walkTree(name: str, entry: mobase.FileTreeEntry):
            path = entry.path()
            src = modDir / path
            if src.exists():
                shutil.move(src, customDir / path)
            return mobase.IFileTree.WalkReturn.CONTINUE

        mod.fileTree().walk(walkTree)

        # unwrap the mods/ directory and move contents back, so they can naturally get overridden by other mods, e.g. "Auto Mod Loading and Ordering"
        customMods = customDir / "mods"
        for item in os.listdir(customMods):
            shutil.move(customMods / item, modDir / item)
        os.rmdir(customMods)  # not needed but I'm paranoid

        qInfo(f"Installed Darktide Mod Loader to: '{customDir}'")

    def applyDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML
        import filecmp

        gameDir = Path(self.gameDirectory().absolutePath())
        customDir = self.getCustomMappingDir()
        if not customDir.exists():
            raise PluginError(
                f"Tried to generate custom mappings for Darktide Mod Loader but missing directory: '{customDir}'. Try reinstalling Darktide Mod Loader"
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
            import shutil, subprocess

            patcher = customDir / "tools/dtkit-patch.exe"
            if not patcher.is_file():
                raise PluginError(
                    f"Tried to toggle mods but missing patcher: '{patcher}'. Try reinstalling Darktide Mod Loader"
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

        # generate the mappings
        maps = []
        for p in customDir.iterdir():
            maps.append(
                mobase.Mapping(
                    str(p.absolute()),
                    str(gameDir / p.relative_to(customDir)),
                    not p.is_file(),
                )
            )
        return maps

    def updateModLoadOrder(self, mods: List[Mod]):
        # get mo2 mods
        modsDict: Dict[str, Mod] = {}
        for mod in mods:
            existing = modsDict.get(mod.FolderName)
            # make sure active mods dont get deactivated by other mods changing the same folder
            if mod.FolderName and (not existing or (not existing.Active and mod.Active)):
                modsDict[mod.FolderName] = mod

        # optionally add unmanaged mods
        if self.getSetting("combine_with_unmanaged_mods"):
            extraMods = self.getModsUnmanaged()
            extraPriority = (len(mods) + len(extraMods)) * (
                -1 if self.getSetting("load_unmanaged_mods_first") else 1
            )
            for i, name in enumerate(extraMods):
                if name not in modsDict:
                    modsDict[name] = Mod(extraPriority + i, True, name)

        # generate new mod list
        with open(self.getModListMappingRaw()[0], mode="w", encoding="utf-8") as f:
            for mod in sorted(modsDict.values(), key=lambda m: m.Priority):
                if mod.FolderName in IGNORE:
                    continue

                if mod.Active:
                    f.write(f"{mod.FolderName}\n")
                else:
                    f.write(f"--{mod.FolderName}\n")

    def getModFolderName(self, mod: mobase.IModInterface):
        if mod.isSeparator():
            return
        if mod.nexusId() in IGNORE:
            return

        fileTree = mod.fileTree()
        folderName: str = None

        def walkTree(name: str, entry: mobase.FileTreeEntry):
            if entry.isDir():
                name = entry.name()
                if fileTree.find(f"{name}/{name}.mod", mobase.FileTreeEntry.FILE):
                    nonlocal folderName
                    folderName = name
                    return mobase.IFileTree.WalkReturn.STOP

            return mobase.IFileTree.WalkReturn.CONTINUE

        fileTree.walk(walkTree)

        if not folderName:
            qCritical(f"Could not find mod folder name for: '{mod.name()}'")

        return folderName


class DarktideSettingsDialog(QDialog):
    def __init__(self, game: Warhammer40000DarktideGame):
        QDialog.__init__(self)
        self.game = game
        self.setWindowTitle("Darktide Settings")
        self.setWindowIcon(game.customAction.icon())
        # self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.finished.connect(self.onFinished)
        self.initWidgets()

    def initWidgets(self):
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.initial: Dict[str, bool] = {}
        layout = QVBoxLayout(self)

        bg = self.palette().highlight().color()
        fg = self.palette().highlightedText().color()
        pt = max(self.font().pointSize(), 11)
        self.setStyleSheet(
            f"* {{ font-size: {pt}pt; }}"
            "QCheckBox { padding: 5px; border-radius: 5px; }"
            f"QCheckBox:hover {{ background-color: {bg.name()}; color: {fg.name()};  }}"
        )

        for settingKey, settingDesc, _ in SETTINGS:
            value = self.game.getSetting(settingKey)
            self.initial[settingKey] = value

            checkbox = QCheckBox(settingKey)
            checkbox.setToolTip(settingDesc)
            checkbox.setChecked(value)
            checkbox.toggled.connect(lambda v: self.onSettingChanged(v, settingKey))
            self.checkboxes[settingKey] = checkbox
            layout.addWidget(checkbox)

        debug = QPushButton("Debug Info")
        debug.setToolTip(
            "If you encounter a bug, the log output of this button might help fix it."
        )
        debug.clicked.connect(self.game.debugInfo)
        layout.addWidget(debug)

        self.updateSettingCoherency()

    def updateSettingCoherency(self):
        self.checkboxes["load_unmanaged_mods_first"].setEnabled(
            self.checkboxes["combine_with_unmanaged_mods"].isChecked()
        )

    def onSettingChanged(self, value: bool, key: str):
        self.updateSettingCoherency()

    def onFinished(self, result: int):
        for k, v0 in self.initial.items():
            if v0 != (v := self.checkboxes[k].isChecked()):
                self.game.setSetting(k, v)
