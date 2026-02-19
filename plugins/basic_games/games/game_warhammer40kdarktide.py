import filecmp
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Union

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
    priority: int
    active: bool
    folder_name: str
    nexus_id: int = 0
    name: str = None


NEXUS_DMF = 8
NEXUS_DML = 19
IGNORED_MODS = {NEXUS_DML, NEXUS_DMF, "dmf", "base"}

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


class BasedGame:
    def find_directory(
        self: BasicGame,
        paths: Union[str, List[str], Callable[[BasicGame], str]],
        default: Callable[[BasicGame], QDir] = None,
    ):
        if paths:
            if callable(paths):
                paths = paths()

            paths = paths if isinstance(paths, list) else [paths]

            for p in paths:
                if Path(os.path.expandvars(p)).is_dir():
                    return QDir(p)

        return default and default(self)

    @staticmethod
    def add_custom_toolbar_action(
        window: QMainWindow, name, icon_xpm, callback=None
    ) -> QAction:
        def _find_toolbar_action(action_name):
            toolbar1 = None
            for toolbar in window.findChildren(QToolBar):
                for action in toolbar.actions():
                    toolbar1 = toolbar1 or toolbar
                    if action.objectName() == action_name:
                        return toolbar, action

            return toolbar1, None

        # add custom toolbar icon
        toolbar, action = _find_toolbar_action("actionSettings")
        if toolbar:
            try:
                import base64
                import zlib

                custom_action = QAction(
                    QIcon(
                        QPixmap(
                            zlib.decompress(base64.b85decode(icon_xpm))
                            .decode()
                            .splitlines()
                        )
                    ),
                    name,
                    action.parent(),
                )
                toolbar.insertAction(action, custom_action)
                if callback:
                    custom_action.triggered.connect(lambda: callback())
                return custom_action
            except Exception as e:
                qCritical(str(e))

    def is_plugin_active(self: BasicGame):
        game = self._organizer.managedGame()
        return game == self or (
            game.gameName() == self.gameName() and game.author() == self.author()
        )

    def setting(self: BasicGame, key: str):
        return self._organizer.pluginSetting(self.name(), key)

    def set_setting(self: BasicGame, key: str, value):
        self._organizer.setPluginSetting(self.name(), key, value)

    def persistent(self: BasicGame, key: str, default=None):
        return self._organizer.persistent(self.name(), key, default)

    def set_persistent(self: BasicGame, key: str, value, sync=True):
        self._organizer.setPersistent(self.name(), key, value, sync)


class Warhammer40000DarktideGame(BasicGame, BasedGame, mobase.IPluginFileMapper):
    Name = "Warhammer 40,000: Darktide Support Plugin"
    Author = "Nyvrak"
    Version = "1.0.9"

    GameName = "Warhammer 40,000: Darktide"
    GameShortName = "warhammer40kdarktide"
    GameNexusName = "warhammer40kdarktide"
    GameSteamId = 1361210
    GameBinary = "binaries/Darktide.exe"
    GameDataPath = "mods"

    def GameDocumentsDirectory(self):
        paths = [
            "%USERPROFILE%/AppData/Roaming/Fatshark/Darktide",
            "%USERPROFILE%/AppData/Roaming/Fatshark/MicrosoftStore/Darktide",
        ]
        return (
            list(reversed(paths))
            if self.setting("prefer_microsoft_store_documents")
            else paths
        )

    CustomSettingsName = "Darktide Settings"
    CustomSettingsIcon = "c$|IIYg^h#6bJD4=TpQAy~IH0K9fR2Cn3>zuVA(GQ3O%jlBfIq-|d+b+-i5-6Z7N;{GFT`CP)!U5m^&)h@#u*_^)4gu!Y!W3J(dd$R@mkZE}u>hfXkO_&$d&x!{Itcug+R2Hpe<CO9wPEm;UD7`!8E?zw}Q?1dH*cF1EKpFz@^r(8lWSaP9w4t=thN^*D~tekSP0!GfIkqkJwP^Ho!$R!_RKQdS|yt4yE=E4aBnrxNFydkGbN(Z(z9vmFGG)!AagAK!3I{4696zBn2C@nP%$yyY`!AG(ani<H*1@@_6L@tHLIeuy_E5*Q*E2FfBJlNtg<2c2}MmZRhx$#CpNfugZ1=Yq{jA56oCFdOWTI<|ssDqu>-Wb>?8xhw0pf$Fi!Xeoji#{SdQLqw@$zG+(zzMl9%1StGZLLY+GkI*e9>ZB{m)aC2<kC1PU>clCDVc-w*0^p8zL1Ry_qu59Qs?24Y^`@1z6N`vnKUqKZJo66jcm139<In<c~QVMxo|EOFejI(OfB35=R7rDz=EuulsPQPM&`J;Z^@-MzJgV7A><g>>W-|v&lTL0jT_4X9)iaVH_#Zqlk+rJ0)CJy&v1|Z3@&+EDh})5iu+V4Xvk%5@%xRUt+(3Zd~I9KI@eyk=UY(((W|&0zfkt<O$1wU+<CG3XIrq{fBExH$G(T|{{~_Uu_drjeXKZ6{wr`gpWlSP8?5=o-al={dJ`z?`lLQS!NTjw^_~7#025ekpso+DFWNv)LzluuiIHz#ug=ep59+;x`s8l>*h7~_DC)Ybv!I<Ms}FFH+wQX_F;J9jb7K@!m*w+7sK<aRM$75o@{d54Z34IqY`R*qlTMQSF@g$`%TY2~E|*g!m(%XEKo$ZCezsgao+Eq~+5jumW(4~0k(9gPnuLY&6v(pd69qcc)l{i0V-g4G#N{TShL~sra#t1EFgwoVYT1n$^l8atNVI`PV}?p*=eu3J$5d_tq7C#GgKFI@*rZZdNoR^}J_h7)ILrz?X|UGe9DM0?!-OQT%?KjJG1$79F@}T8c6V?^mJ)yZ*ro^kVNj}SX2~#9Z2i#dB-7Py2iIXU!e}%)l8dGpj7HO`STySjJ9rY<36=b48iv;}lV)<X!WNAO=6`R|-lUn(_qAS|WCzzYF^AAUeX@yr>vh$|$u=`;tk)?#yuNtyV1#LYzsGs5d+i&CIc(|q?*x08%$nwBbw6vj#$maS53in|oo;HZy?$saUzYgd^XX~vF$$0WJElXKPz7UycrX|gcn&`7N73Jh1DTN"

    def __init__(self):
        BasicGame.__init__(self)
        mobase.IPluginFileMapper.__init__(self)

    def init(self, organizer: mobase.IOrganizer):
        BasicGame.init(self, organizer)

        self._mappings.documentsDirectory._default = lambda _: self.find_directory(
            self.GameDocumentsDirectory,
            BasicGameMappings._default_documents_directory,
        )

        self.show_error_popups = self.setting("show_error_popups")
        self.settings_action: QAction = None
        self.settings_dialog: QDialog = None

        organizer.onUserInterfaceInitialized(self.onUserInterfaceInitialized)
        organizer.onAboutToRun(self.onAboutToRun)
        organizer.onFinishedRun(self.onFinishedRun)
        organizer.modList().onModInstalled(self.onModInstalled)

        return True

    def mappings(self):
        return self.custom_mappings

    def settings(self):
        ## FIXME: In MO 2.4.4 PluginSetting.key throws "TypeError: No Python class registered for C++ class class QString". If it wasn't for that, I would probably just have these as mobase.PluginSetting
        return [mobase.PluginSetting(*s) for s in SETTINGS]

    def onUserInterfaceInitialized(self, window: QMainWindow):
        self.show_error_popups = False

        # MO2 always calls onUserInterfaceInitialized for every plugin, even when not active
        if not self.is_plugin_active():
            return

        if icon := getattr(self, "CustomSettingsIcon", None):
            self.settings_action = self.add_custom_toolbar_action(
                window,
                getattr(self, "CustomSettingsName", f"{self.gameName()} Settings"),
                icon,
                self.open_settings_dialog,
            )
            self.settings_dialog = DarktideSettingsDialog(self)

    def onAboutToRun(self, appPath: str):
        try:
            if self.setting("debug_info"):
                self.debug_info()

            self.custom_mappings = self.build_custom_mappings()

            return True
        except PluginError as err:
            qCritical(str(err), popup=self.show_error_popups)
            return False

    def onFinishedRun(self, appPath: str, exitCode: int):
        STILL_ACTIVE = 259
        STATUS_OK = {None, 0, STILL_ACTIVE}

        if exitCode not in STATUS_OK and self.setting("inspect_crash"):
            msg = [f"{Path(appPath).name} exited with code {exitCode}"]
            console_logs = Path(
                self.documentsDirectory().absoluteFilePath("console_logs")
            )
            if log := max(console_logs.glob("*.log"), key=os.path.getmtime, default=None):
                with log.open("r", encoding="utf-8") as f:
                    if errors := re.findall(
                        r"<<Lua Error>>(.+?)<</Lua Error>>",
                        f.read(),
                        re.DOTALL | re.IGNORECASE,
                    ):

                        def _time_ago(seconds):
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
                            - log.stat().st_mtime
                        )
                        msg.append(
                            f"\n\nRecent Lua Errors in\n{log.name}\n    (modified {_time_ago(seconds)})\n"
                        )
                        msg.extend(f"\n#{i}: {s}" for i, s in enumerate(errors, 1))

            qCritical("".join(msg), popup=self.show_error_popups and "delayed")

    def onModInstalled(self, mod: mobase.IModInterface):
        self.identify_mod(mod)
        if mod.nexusId() == NEXUS_DML:
            self.install_dml(mod)

    def open_settings_dialog(self):
        (self.settings_dialog or DarktideSettingsDialog(self)).exec()
        self.settings_dialog = None

    def build_custom_mappings(self):
        mods = self.get_mods()
        mappings = []

        # add our custom mappings for DML, if installed
        if dml := next((m for m in mods if m.nexus_id == NEXUS_DML and m.active), None):
            toAdd = self.apply_dml(self._organizer.modList().getMod(dml.name))
            mappings.extend(toAdd)

        # add mapping for mod_load_order.txt
        mappings.append(self.apply_mod_list(mods))

        # virtualize user_settings.config to override language
        if config := self.apply_user_settings():
            mappings.append(config)

        return mappings

    def custom_mappings_directory(self):
        return Path(self._organizer.basePath()) / "custom_mappings/Darktide Mod Loader"

    def get_mods(self):
        modList = self._organizer.modList()
        return [
            Mod(
                modList.priority(name),
                bool(modList.state(name) & mobase.ModState.ACTIVE),
                self.get_mod_folder_name(mod),
                mod.nexusId(),
                name,
            )
            for name in modList.allModsByProfilePriority()
            if (mod := modList.getMod(name))
        ]

    def get_unmanaged_mods(self):
        mod_list = Path(self.mod_list_mapping()[1])
        if not mod_list.exists():
            return []

        data = self.dataDirectory()
        with mod_list.open("r", encoding="utf-8") as f:
            return [
                name
                for line in f.read().splitlines()
                if (name := line.strip())
                and not name.startswith("--")
                and data.exists(f"{name}/{name}.mod")
            ]

    def identify_mod(self, mod: mobase.IModInterface):
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

    def install_dml(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML

        mod_dir = Path(mod.absolutePath())
        custom_dir = self.custom_mappings_directory()
        shutil.rmtree(custom_dir, ignore_errors=True)

        ## TODO: this whole "manual mapping of parts of a mod" thing could be made into a helper class or whatever

        # move the contents of DML into a custom folder, we will map them manually
        def _move_contents(name: str, entry: mobase.FileTreeEntry):
            path = entry.path()
            src = mod_dir / path
            if src.exists():
                shutil.move(src, custom_dir / path)
            return mobase.IFileTree.WalkReturn.CONTINUE

        mod.fileTree().walk(_move_contents)

        # unwrap the mods/ directory and move contents back so they can naturally get overridden by other mods, e.g. "Auto Mod Loading and Ordering"
        custom_mods_dir = custom_dir / "mods"
        for item in os.listdir(custom_mods_dir):
            shutil.move(custom_mods_dir / item, mod_dir / item)
        os.rmdir(custom_mods_dir)  # not needed but I'm paranoid

        qInfo(f"Installed Darktide Mod Loader to: '{custom_dir}'")

    def mod_list_mapping(self):
        ## FIXME: I wish I didn't need to do this... but same issue as settings()
        return (
            str(self._organizer.profilePath() / Path("mod_load_order.txt")),
            self.dataDirectory().absoluteFilePath("mod_load_order.txt"),
        )

    def apply_dml(self, mod: mobase.IModInterface):
        assert mod.nexusId() == NEXUS_DML

        game_dir = Path(self.gameDirectory().absolutePath())
        custom_dir = self.custom_mappings_directory()
        if not custom_dir.exists():
            raise PluginError(
                f"Tried to apply DML but missing directory: '{custom_dir}'. Try reinstalling Darktide Mod Loader"
            )

        BUNDLE_DB = "bundle/bundle_database.data"
        game_bundle = game_dir / BUNDLE_DB
        custom_bundle = custom_dir / BUNDLE_DB
        custom_bundle_bak = custom_dir / (BUNDLE_DB + ".bak")

        found_patched_bundle = (
            custom_bundle.is_file()
            and custom_bundle_bak.is_file()
            and filecmp.cmp(game_bundle, custom_bundle_bak)
            and not filecmp.cmp(game_bundle, custom_bundle)
        )

        if not found_patched_bundle:
            patcher = custom_dir / "tools/dtkit-patch.exe"
            if not patcher.is_file():
                raise PluginError(
                    f"Tried to patch '{custom_bundle}' with DML but missing patcher: '{patcher}'. Try reinstalling Darktide Mod Loader"
                )

            # patch a fresh bundle database
            shutil.copy(game_bundle, custom_bundle)
            patcher = subprocess.run(
                [patcher, "--patch", custom_bundle.parent],
                capture_output=True,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            qInfo(f"dtkit-patch.exe: {patcher.stderr.decode().strip()}")

        # map {customDir}/Path to {gameDir}/Path
        mappings = [
            mobase.Mapping(
                str(path.absolute()),
                str(game_dir / path.relative_to(custom_dir)),
                not path.is_file(),
            )
            for path in custom_dir.iterdir()
        ]
        if not mappings:
            raise PluginError(
                "Tried to generate custom mappings for DML but got nothing! Try reinstalling Darktide Mod Loader"
            )

        return mappings

    def apply_mod_list(self, mods: List[Mod] = None):
        mods = mods or self.get_mods()
        mods_dict: Dict[str, Mod] = {}

        # add MO2 mods
        for mod in mods:
            # here we only care about things that go into mod_load_order.txt
            if not mod.folder_name:
                continue

            # make sure active mods dont get deactivated by other mods changing the same folder
            existing = mods_dict.get(mod.folder_name)
            if not existing or (not existing.active and mod.active):
                mods_dict[mod.folder_name] = mod

        # optionally add unmanaged mods
        if self.setting("combine_with_unmanaged_mods"):
            unmanaged_mods = self.get_unmanaged_mods()
            unmanaged_priority = (
                -len(unmanaged_mods)
                if self.setting("load_unmanaged_mods_first")
                else len(mods)
            )
            for i, name in enumerate(unmanaged_mods, unmanaged_priority):
                if name not in mods_dict:
                    mods_dict[name] = Mod(i, True, name)

        # generate new mod list
        mod_list = self.mod_list_mapping()
        with open(mod_list[0], mode="w", encoding="utf-8") as f:
            for mod in sorted(mods_dict.values(), key=lambda m: m.priority):
                if mod.folder_name in IGNORED_MODS:
                    continue

                if mod.active:
                    f.write(f"{mod.folder_name}\n")
                else:
                    f.write(f"--{mod.folder_name}\n")

        return mobase.Mapping(*mod_list, False)

    def apply_user_settings(self):
        if lang := self.setting("override_language"):
            CONFIG = "user_settings.config"
            user_config = Path(self.documentsDirectory().absoluteFilePath(CONFIG))
            virt_config = Path(self._organizer.overwritePath()) / CONFIG

            md5 = hashlib.md5()
            md5.update(lang.encode("utf-8"))
            if user_config.is_file():
                md5.update(user_config.read_bytes())
            config_hash = md5.digest().hex().casefold()

            is_new_config = config_hash != self.persistent(CONFIG)
            if is_new_config:
                self.set_persistent(CONFIG, config_hash, False)

                pattern = re.compile(r"^\s*language_id\s*=\s*\".*?\"\s*$", re.IGNORECASE)
                with virt_config.open("w", encoding="utf-8", newline="\n") as virt:
                    if user_config.is_file():
                        with user_config.open("r", encoding="utf-8") as user:
                            virt.writelines(
                                line for line in user if not pattern.match(line)
                            )
                    virt.write(f'language_id = "{lang}"\n')

                qInfo(f"Generated new virtual config '{virt_config}'")

            return mobase.Mapping(str(virt_config), str(user_config), False, True)

    def get_mod_folder_name(self, mod: mobase.IModInterface):
        if mod.isSeparator():
            return
        if mod.nexusId() in IGNORED_MODS:
            return

        tree = mod.fileTree()
        folder_name: str = None

        def _find_mod_file(name: str, entry: mobase.FileTreeEntry):
            if entry.isDir():
                name = entry.name()
                if tree.find(f"{name}/{name}.mod", mobase.FileTreeEntry.FILE):
                    nonlocal folder_name
                    folder_name = name
                    return mobase.IFileTree.WalkReturn.STOP

            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(_find_mod_file)

        if not folder_name:
            qCritical(f"Could not find mod folder name for: '{mod.name()}'")

        return folder_name

    def debug_info(self):
        import sys

        stuff = [
            ("Plugin", f"{self.Name} ({self.Version}) by {self.Author}"),
            ("OS", os.name),
            ("Python", sys.version),
            ("Qt", str(qVersion())),
            ("ModOrganizer2", str(self._organizer.appVersion())),
            ("mod_load_order.txt", self.mod_list_mapping()),
            ("Mods", self.get_mods()),
            ("Unmanaged mods", self.get_unmanaged_mods()),
        ]
        qInfo("Debug Info: " + " ".join(f'{k} = "{v}";' for k, v in stuff))


class DarktideSettingsDialog(QDialog):
    def __init__(self, game: Warhammer40000DarktideGame):
        QDialog.__init__(self)
        self.game = game
        self.setWindowTitle(game.settings_action.text())
        self.setWindowIcon(game.settings_action.icon())
        self.finished.connect(self.on_finished)
        self.init_widgets()

    def init_widgets(self):
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

        # create setting widgets
        for setting_key, setting_desc, setting_default in SETTINGS:
            data = self.game.setting(setting_key)
            self.initial[setting_key] = data

            if isinstance(setting_default, bool):
                # simple toggle
                checkbox = QCheckBox(setting_key)
                checkbox.setToolTip(setting_desc)
                checkbox.setChecked(data)
                checkbox.toggled.connect(
                    lambda v, k=setting_key: self.on_setting_changed(k, v)
                )
                self.widgets[setting_key] = checkbox
                layout.addWidget(checkbox)
                continue

            if choices := SETTINGS_CHOICES.get(setting_key):
                # dropdown select
                combo = QComboBox()
                combo.setToolTip(setting_desc)
                combo.addItem(setting_key, "")
                for label, choice in choices:
                    combo.addItem(label, choice)
                combo.setCurrentIndex(max(0, combo.findData(data)))

                def _update_style(index):
                    combo.setProperty("sad", index == 0)
                    combo.style().polish(combo)

                _update_style(combo.currentIndex())
                combo.currentIndexChanged.connect(_update_style)
                combo.setItemData(0, QBrush(disabled), Qt.ItemDataRole.ForegroundRole)

                self.widgets[setting_key] = combo
                layout.addWidget(combo)
                continue

        self.widgets["debug_info"].toggled.connect(lambda v: v and self.game.debug_info())

        self.update_coherency()

    def update_coherency(self):
        self.widgets["load_unmanaged_mods_first"].setEnabled(
            self.widgets["combine_with_unmanaged_mods"].isChecked()
        )

    def on_setting_changed(self, key: str, value: bool):
        self.update_coherency()

    def on_finished(self, result: int):
        for k, v0 in self.initial.items():
            w = self.widgets[k]
            v = w.currentData() if isinstance(w, QComboBox) else w.isChecked()
            if v0 != v:
                self.game.set_setting(k, v)
