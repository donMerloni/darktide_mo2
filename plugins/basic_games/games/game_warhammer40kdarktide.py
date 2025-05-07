import base64
import filecmp
import shutil
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import mobase

try:
    from PyQt6.QtCore import Qt, qInfo, qCritical
    from PyQt6.QtGui import QAction, QIcon, QPixmap
    from PyQt6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QToolBar, QVBoxLayout, QWidget # fmt:skip
except ImportError:
    from PyQt5.QtCore import Qt, qInfo, qCritical
    from PyQt5.QtGui import QIcon, QPixmap
    from PyQt5.QtWidgets import QAction, QCheckBox, QDialog, QHBoxLayout, QLabel, QMainWindow, QSizePolicy, QToolBar, QVBoxLayout, QWidget # fmt:skip

from ..basic_game import BasicGame


@dataclass
class Mod:
    Priority: int
    Active: bool
    Mod: mobase.IModInterface


class Warhammer40000DarktideGame(BasicGame, mobase.IPluginFileMapper):
    Name = "Warhammer 40,000: Darktide Support Plugin"
    Author = "Nyvrak"
    Version = "1.0.5"

    GameName = "Warhammer 40,000: Darktide"
    GameShortName = "warhammer40kdarktide"
    GameNexusName = "warhammer40kdarktide"
    GameSteamId = 1361210
    GameBinary = "binaries/Darktide.exe"
    GameDataPath = "mods"

    DMF_NexusID = 8
    DML_NexusID = 19

    def __init__(self):
        BasicGame.__init__(self)
        mobase.IPluginFileMapper.__init__(self)

    def init(self, organizer: mobase.IOrganizer):
        BasicGame.init(self, organizer)
        # managedGame() doesn't exist yet...
        organizer.onUserInterfaceInitialized(self.onUserInterfaceInitialized)
        self.activeMappings = None
        return True

    def onUserInterfaceInitialized(self, window: QMainWindow):
        if self._organizer.managedGame().gameShortName() != self.GameShortName:
            # stop if this is not a Darktide instance...
            return

        # register events
        self._organizer.onAboutToRun(self.onAboutToRun)
        self._organizer.modList().onModInstalled(self.onModInstalled)

        # add custom toolbar icon
        for toolbar in window.findChildren(QToolBar):
            if actionSettings := next(
                filter(lambda a: a.objectName() == "actionSettings", toolbar.actions()),
                None,
            ):
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
                    actionSettings.parent(),
                )
                self.customAction.triggered.connect(self.onCustomSettingsOpened)
                toolbar.insertAction(actionSettings, self.customAction)
                break

    def onCustomSettingsOpened(self, checked: bool):
        DarktideSettingsDialog(self).exec()

    def onAboutToRun(self, appPath: str):
        mods = self.getMods()

        # generate mappings
        mappings = []
        if (dml := mods.get(self.DML_NexusID)) and dml.Active:
            if not (m := self.applyDML(dml.Mod)):
                return False
            mappings = m

        self.activeMappings = [*mappings, self.getModListMapping()]

        # update mod list
        self.updateModLoadOrder(mods.values())

        return True

    def onModInstalled(self, mod: mobase.IModInterface):
        if self.looksLikeDML(mod):
            self.installDML(mod)

    def mappings(self):
        return self.activeMappings or []

    def settingsRaw(self):
        # In MO 2.4.4 PluginSetting.key throws "TypeError: No Python class registered for C++ class class QString"
        return [
            (
                "combine_with_unmanaged_mods",
                "Include unmanaged mods from an existing mod_load_order.txt alongside those managed by Mod Organizer 2.\n\n"
                "If a mod appears in both places, MO2 will always take priority—deciding which version is used and whether the mod is enabled.",
                False,
            ),
            (
                "load_unmanaged_mods_first",
                "When combining with unmanaged mods, list them at the top of mod_load_order.txt so they are loaded first.\n\n"
                "Disabling this will list them at the bottom, giving MO2-managed mods higher load priority.",
                False,
            ),
        ]

    def settings(self):
        return [mobase.PluginSetting(*s) for s in self.settingsRaw()]

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
        return {
            info.nexusId() or info.name(): Mod(
                modList.priority(m),
                modList.state(m) & mobase.ModState.ACTIVE,
                info,
            )
            for m in modList.allModsByProfilePriority()
            if (info := modList.getMod(m))
        }

    def looksLikeDML(self, mod: mobase.IModInterface):
        if mod.nexusId() == self.DML_NexusID:
            return True
        if mod.fileTree().find(
            "binaries/mod_loader", mobase.FileTreeEntry.FileTypes.FILE
        ):
            qInfo(f"Auto-detected mod '{mod.name()}' as Darktide Mod Loader")
            mod.setNexusID(self.DML_NexusID)
            return True
        return False

    def installDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == self.DML_NexusID

        modDir = Path(mod.absolutePath())
        customDir = self.getCustomMappingDir()
        shutil.rmtree(customDir, ignore_errors=True)

        # just move DML out of the mods directory, we will map it manually
        def walkTree(name: str, entry: mobase.FileTreeEntry):
            path = entry.path()
            src = modDir / path
            if src.exists():
                shutil.move(src, customDir / path)
            return mobase.IFileTree.WalkReturn.CONTINUE

        mod.fileTree().walk(walkTree)

        qInfo(f"Installed Darktide Mod Loader to: '{customDir}'")

    def applyDML(self, mod: mobase.IModInterface):
        assert mod.nexusId() == self.DML_NexusID

        gameDir = Path(self.gameDirectory().absolutePath())
        customDir = self.getCustomMappingDir()
        if not customDir.exists():
            qCritical(
                f"Tried to apply Darktide Mod Loader but missing directory: '{customDir}'"
            )
            return

        BUNDLE_DB = "bundle/bundle_database.data"
        gameBundle = gameDir / BUNDLE_DB
        customBundle = customDir / BUNDLE_DB
        customBundleBak = customDir / (BUNDLE_DB + ".bak")

        foundPatchedBundle = (
            customBundle.is_file()
            and customBundleBak.is_file()
            and filecmp.cmp(gameBundle, customBundleBak)
        )

        if not foundPatchedBundle:
            # patch a fresh bundle database
            shutil.copy(
                gameBundle,
                customBundle,
            )
            patcher = subprocess.run(
                [customDir / "tools/dtkit-patch.exe", "--patch", customBundle.parent],
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

    def updateModLoadOrder(self, modList: List[Mod]):
        # get mo2 mods
        mods = {
            name: mod for mod in modList if (name := self.getModFolderName(mod.Mod))
        }

        # optionally add unmanaged mods
        if self.getSetting("combine_with_unmanaged_mods"):
            modsDir = self.dataDirectory()
            extraList = Path(self.getModListMappingRaw()[1])

            if extraList.exists():
                with extraList.open() as f:
                    lines = f.read().splitlines()
                    extraPriority = (len(mods) + len(lines)) * (
                        -1 if self.getSetting("load_unmanaged_mods_first") else 1
                    )
                    for i, name in enumerate(lines):
                        if name := name.strip():
                            if (
                                not name.startswith("--")
                                and name not in mods
                                and modsDir.exists(f"{name}/{name}.mod")
                            ):
                                mods[name] = Mod(extraPriority + i, True, None)

        # generate new mod list
        with open(self.getModListMappingRaw()[0], "w") as f:
            for name, mod in sorted(mods.items(), key=lambda m: m[1].Priority):
                if mod.Active:
                    f.write(f"{name}\n")
                else:
                    f.write(f"--{name}\n")

    def getModFolderName(self, mod: mobase.IModInterface):
        if mod.isOverwrite() or mod.isSeparator():
            return
        if mod.nexusId() in {self.DMF_NexusID, self.DML_NexusID}:
            return  # Darktide Mod Framework/Loader is loaded automatically

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
        super().__init__()
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

        for settingKey, settingDesc, _ in self.game.settingsRaw():
            value = self.game.getSetting(settingKey)
            self.initial[settingKey] = value

            rowWidget = QWidget()
            row = QHBoxLayout(rowWidget)
            row.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout.addWidget(rowWidget)

            labels = QVBoxLayout()
            labels.setAlignment(Qt.AlignmentFlag.AlignTop)

            key = QLabel(settingKey)
            key.setStyleSheet(
                f"font-size: {key.font().pointSizeF() + 2}pt; font-weight: bold;"
            )
            # key.setToolTip(settingDesc)
            labels.addWidget(key)

            desc = QLabel(settingDesc)
            desc.setWordWrap(True)
            desc.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            labels.addWidget(desc)

            row.addLayout(labels, stretch=1)

            checkbox = QCheckBox()
            checkbox.setChecked(value)
            checkbox.toggled.connect(lambda v: self.onSettingChanged(v, settingKey))
            self.checkboxes[settingKey] = checkbox
            row.addWidget(checkbox)

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
