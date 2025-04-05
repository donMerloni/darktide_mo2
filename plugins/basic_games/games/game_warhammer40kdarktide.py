from dataclasses import dataclass
from pathlib import Path

import mobase
from PyQt6.QtCore import QDir

from ..basic_game import BasicGame


class Warhammer40000DarktideGame(BasicGame):
    Name = "Warhammer 40,000: Darktide Support Plugin"
    Author = "Nyvrak"
    Version = "1.0.1"

    GameName = "Warhammer 40,000: Darktide"
    GameShortName = "warhammer40kdarktide"
    GameNexusName = "warhammer40kdarktide"
    GameSteamId = 1361210
    GameBinary = "binaries/Darktide.exe"
    GameDataPath = "mods"

    def init(self, organizer: mobase.IOrganizer):
        super().init(organizer)
        self.organizer = organizer
        organizer.onAboutToRun(lambda *a: self.onAboutToRun(*a))
        organizer.modList().onModMoved(lambda *a: self.onModMoved(*a))
        organizer.modList().onModStateChanged(lambda a: self.onModStateChanged(a))
        return True

    def onAboutToRun(self, appName: str, folder: QDir, executable: str):
        self.updateModLoadOrder()
        return True

    def onModMoved(self, mod: str, oldPriority: int, newPriority: int):
        self.updateModLoadOrder()

    def onModStateChanged(self, changes: dict[str, mobase.ModState]):
        self.updateModLoadOrder()

    def updateModLoadOrder(self):
        modDir = self.dataDirectory()
        modListPath = Path(modDir.absoluteFilePath("mod_load_order.txt"))

        @dataclass
        class Mod:
            Name: str
            Active: str
            Order: int
            IsSeparator: bool = False

        mods: list[Mod] = []

        if modListPath.exists():
            with modListPath.open() as f:
                # read the mod list from mod_load_order.txt
                for i, line in enumerate(f.read().splitlines()):
                    if line := line.strip():
                        if line.startswith("--"):
                            mods.append(Mod(line[2:], False, i))
                        else:
                            mods.append(Mod(line, True, i))

        modsIndex = {mod.Name.strip(): mod for mod in mods}
        maxOrder = len(mods) and mods[-1].Order or 0

        # apply enabled/disabled mod organizer mods
        organizerMods = self.organizer.modList().allModsByProfilePriority()
        organizerModsSet = set(self.getModFolderName(mod) for mod in organizerMods)
        for mod in organizerMods:
            isSeparator = False

            if modInfo := self.organizer.modList().getMod(mod):
                isSeparator = modInfo.isSeparator()

            isActive = self.organizer.modList().state(mod) & mobase.ModState.ACTIVE
            priority = self.organizer.modList().priority(mod)
            folderName = (
                mod
                if isSeparator
                else (
                    self.getModFolderName(mod)
                    or f"YOU SHOULD NEVER SEE THIS (TURN BACK NOW BEFORE ITS TOO LATE) (Culprit: {mod})"
                )
            )

            if folderName not in modsIndex:
                mods.append(Mod(folderName, isActive, maxOrder + priority))
                modsIndex[folderName] = mods[-1]
            modsIndex[folderName].Active = isActive
            modsIndex[folderName].Order = maxOrder + priority
            modsIndex[folderName].IsSeparator = isSeparator

        with modListPath.open("w") as f:
            for mod in sorted(mods, key=lambda x: x.Order):
                if mod.IsSeparator:
                    # f.write(f"----- {mod.Name} -----\n")
                    continue

                if (
                    mod.Name in organizerModsSet
                    and not mod.Active
                    and not Path(modDir.absoluteFilePath(mod.Name)).exists()
                ):
                    # completely remove line if it was likely added by us aswell
                    continue

                if mod.Active:
                    f.write(f"{mod.Name}\n")
                else:
                    f.write(f"--{mod.Name}\n")

    def getModFolderName(self, mod: str):
        if not (modInfo := self.organizer.modList().getMod(mod)):
            return

        folderName = None

        def walk(name: str, entry: mobase.FileTreeEntry):
            if entry.isDir():
                nonlocal folderName
                folderName = entry.name()

                if modInfo.fileTree().find(
                    f"{folderName}/{folderName}.mod", mobase.FileTreeEntry.FILE
                ):
                    return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        modInfo.fileTree().walk(walk)

        return folderName
