import base64
import logging
import zlib
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict

import mobase
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..basic_game import BasicGame

SETTINGS_ICON = QIcon(
    QPixmap(
        zlib.decompress(
            base64.b85decode(
                "c$|IIYg^h#6bJD4=TpQAy~IH0K9fR2Cn3>zuVA(GQ3O%jlBfIq-|d+b+-i5-6Z7N;{GFT`CP)!U5m^&)h@#u*_^)4gu!Y!W3J(dd$R@mkZE}u>hfXkO_&$d&x!{Itcug+R2Hpe<CO9wPEm;UD7`!8E?zw}Q?1dH*cF1EKpFz@^r(8lWSaP9w4t=thN^*D~tekSP0!GfIkqkJwP^Ho!$R!_RKQdS|yt4yE=E4aBnrxNFydkGbN(Z(z9vmFGG)!AagAK!3I{4696zBn2C@nP%$yyY`!AG(ani<H*1@@_6L@tHLIeuy_E5*Q*E2FfBJlNtg<2c2}MmZRhx$#CpNfugZ1=Yq{jA56oCFdOWTI<|ssDqu>-Wb>?8xhw0pf$Fi!Xeoji#{SdQLqw@$zG+(zzMl9%1StGZLLY+GkI*e9>ZB{m)aC2<kC1PU>clCDVc-w*0^p8zL1Ry_qu59Qs?24Y^`@1z6N`vnKUqKZJo66jcm139<In<c~QVMxo|EOFejI(OfB35=R7rDz=EuulsPQPM&`J;Z^@-MzJgV7A><g>>W-|v&lTL0jT_4X9)iaVH_#Zqlk+rJ0)CJy&v1|Z3@&+EDh})5iu+V4Xvk%5@%xRUt+(3Zd~I9KI@eyk=UY(((W|&0zfkt<O$1wU+<CG3XIrq{fBExH$G(T|{{~_Uu_drjeXKZ6{wr`gpWlSP8?5=o-al={dJ`z?`lLQS!NTjw^_~7#025ekpso+DFWNv)LzluuiIHz#ug=ep59+;x`s8l>*h7~_DC)Ybv!I<Ms}FFH+wQX_F;J9jb7K@!m*w+7sK<aRM$75o@{d54Z34IqY`R*qlTMQSF@g$`%TY2~E|*g!m(%XEKo$ZCezsgao+Eq~+5jumW(4~0k(9gPnuLY&6v(pd69qcc)l{i0V-g4G#N{TShL~sra#t1EFgwoVYT1n$^l8atNVI`PV}?p*=eu3J$5d_tq7C#GgKFI@*rZZdNoR^}J_h7)ILrz?X|UGe9DM0?!-OQT%?KjJG1$79F@}T8c6V?^mJ)yZ*ro^kVNj}SX2~#9Z2i#dB-7Py2iIXU!e}%)l8dGpj7HO`STySjJ9rY<36=b48iv;}lV)<X!WNAO=6`R|-lUn(_qAS|WCzzYF^AAUeX@yr>vh$|$u=`;tk)?#yuNtyV1#LYzsGs5d+i&CIc(|q?*x08%$nwBbw6vj#$maS53in|oo;HZy?$saUzYgd^XX~vF$$0WJElXKPz7UycrX|gcn&`7N73Jh1DTN"
            )
        )
        .decode()
        .splitlines()
    )
)


# PluginSetting.key throws TypeError: No Python class registered for C++ class class QString
SETTINGS = [
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


class Warhammer40000DarktideGame(BasicGame):
    Name = "Warhammer 40,000: Darktide Support Plugin"
    Author = "Nyvrak"
    Version = "1.0.3c"

    GameName = "Warhammer 40,000: Darktide"
    GameShortName = "warhammer40kdarktide"
    GameNexusName = "warhammer40kdarktide"
    GameSteamId = 1361210
    GameBinary = "binaries/Darktide.exe"
    GameDataPath = "mods"

    def settings(self):
        return [mobase.PluginSetting(*s) for s in SETTINGS]

    def init(self, organizer: mobase.IOrganizer):
        super().init(organizer)
        self.organizer = organizer

        # register events
        organizer.onUserInterfaceInitialized(self.onUserInterfaceInitialized)
        organizer.onAboutToRun(self.onAboutToRun)
        organizer.modList().onModMoved(self.onModMoved)
        organizer.modList().onModStateChanged(self.onModStateChanged)
        organizer.modList().onModInstalled(self.onModInstalled)
        organizer.modList().onModRemoved(self.onModRemoved)

        return True

    def getSetting(self, key: str):
        return self.organizer.pluginSetting(self.name(), key)

    def setSetting(self, key: str, value):
        self.organizer.setPluginSetting(self.name(), key, value)

    def onUserInterfaceInitialized(self, window: QMainWindow):
        self.updateModLoadOrder()
        for toolbar in window.findChildren(QToolBar):
            if actionSettings := next(
                filter(lambda a: a.objectName() == "actionSettings", toolbar.actions()),
                None,
            ):
                action = QAction(
                    SETTINGS_ICON,
                    "Darktide Settings",
                    actionSettings.parent(),
                )
                action.triggered.connect(self.onCustomSettingsOpened)
                toolbar.insertAction(actionSettings, action)
                break

    def onCustomSettingsOpened(self, checked: bool):
        DarktideSettingsDialog(self).exec()

    def onAboutToRun(self, appPath: str):
        self.updateModLoadOrder()
        return True

    def onModMoved(self, mod: str, oldPriority: int, newPriority: int):
        self.updateModLoadOrder()

    def onModInstalled(self, mod: mobase.IModInterface):
        self.updateModLoadOrder()

    def onModRemoved(self, mod: str):
        self.updateModLoadOrder()

    def onModStateChanged(self, changes: Dict[str, mobase.ModState]):
        self.updateModLoadOrder()

    def updateModLoadOrder(self):
        modList = self.organizer.modList()

        @dataclass
        class Mod:
            Order: int
            Name: str
            Enabled: bool

        # get mo2 mods
        mods = {
            name: Mod(
                modList.priority(mod),
                name,
                modList.state(mod) & mobase.ModState.ACTIVE,
            )
            for mod in modList.allModsByProfilePriority()
            if (name := self.getModFolderName(mod))
        }

        # optionally add unmanaged mods
        if self.getSetting("combine_with_unmanaged_mods"):
            modsDir = self.dataDirectory()
            extraList = Path(modsDir.absolutePath()) / "mod_load_order.txt"

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
                                mods[name] = Mod(extraPriority + i, name, True)

        # generate new mod list
        newlist = Path(self.organizer.overwritePath()) / "mod_load_order.txt"
        with newlist.open("w") as f:
            for mod in sorted(mods.values(), key=lambda m: m.Order):
                if mod.Enabled:
                    f.write(f"{mod.Name}\n")
                else:
                    f.write(f"--{mod.Name}\n")

    def getModFolderName(self, mod: str):
        if not (info := self.organizer.modList().getMod(mod)):
            return
        if info.isSeparator():
            return
        if info.nexusId() in {8, 19}:
            return  # Darktide Mod Framework/Loader is loaded automatically

        fileTree = info.fileTree()
        folderName: str = None

        def walkTree(name: str, entry: mobase.FileTreeEntry):
            if not entry.isDir():
                return mobase.IFileTree.WalkReturn.CONTINUE

            name = entry.name()
            if fileTree.find(f"{name}/{name}.mod", mobase.FileTreeEntry.FILE):
                nonlocal folderName
                folderName = name
                return mobase.IFileTree.WalkReturn.STOP

            return mobase.IFileTree.WalkReturn.CONTINUE

        fileTree.walk(walkTree)

        if not folderName:
            logging.error(f"Could not get mod folder name for: '{mod}'")

        return folderName


class DarktideSettingsDialog(QDialog):
    def __init__(self, game: Warhammer40000DarktideGame):
        super().__init__()
        self.game = game
        self.setWindowTitle("Darktide Settings")
        self.setWindowIcon(SETTINGS_ICON)
        self.initWidgets()
        self.finished.connect(self.onFinished)

    def initWidgets(self):
        self.checkboxes: Dict[str, QCheckBox] = {}
        self.initial: Dict[str, bool] = {}
        layout = QVBoxLayout(self)

        for settingKey, settingDesc, _ in SETTINGS:
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
            labels.addWidget(key)

            desc = QLabel(settingDesc)
            desc.setWordWrap(True)
            desc.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            labels.addWidget(desc)

            row.addLayout(labels, stretch=1)

            checkbox = QCheckBox()
            checkbox.setChecked(value)
            checkbox.toggled.connect(self.onSettingChanged)
            self.checkboxes[settingKey] = checkbox
            row.addWidget(checkbox)

        self.updateSettingCoherency()

    def updateSettingCoherency(self):
        self.checkboxes["load_unmanaged_mods_first"].setEnabled(
            self.checkboxes["combine_with_unmanaged_mods"].isChecked()
        )

    def onSettingChanged(self, value: bool):
        self.updateSettingCoherency()

    def onFinished(self, result: int):
        update = False
        for k, v0 in self.initial.items():
            if v0 != (v := self.checkboxes[k].isChecked()):
                update = True
                self.game.setSetting(k, v)
        if update:
            self.game.updateModLoadOrder()
