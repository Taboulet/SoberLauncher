#!/usr/bin/env python3

import sys
import os
import subprocess
import shutil
import json
import re

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QLineEdit, QMessageBox, QInputDialog, QLabel, QDialog, QSizePolicy, QListWidget,
    QAbstractItemView, QCheckBox, QDialogButtonBox, QTabWidget, QMenu
)
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt

__version__ = "Release V1.4"


class UpdateThread(QThread):
    update_failed = pyqtSignal(str)
    update_success = pyqtSignal()

    def run(self):
        try:
            subprocess.run(
                ["python3", os.path.join(os.path.dirname(__file__), "update.py")],
                check=True
            )
            self.update_success.emit()
        except subprocess.CalledProcessError as e:
            self.update_failed.emit(str(e))

    def __init__(self):
        super().__init__()


class CreateProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Profile")
        layout = QVBoxLayout(self)

        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Enter the profile name")
        layout.addWidget(QLabel("Profile Name:"))
        layout.addWidget(self.name_input)

        self.copy_checkbox = QCheckBox(
            "Copy the main profile's folder (will make Roblox immediately available without having to redownload it after)",
            self
        )
        layout.addWidget(self.copy_checkbox)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def getData(self):
        return self.name_input.text().strip(), self.copy_checkbox.isChecked()


class SoberLauncher(QWidget):
    def __init__(self):
        super().__init__()
        # État
        self.base_dir = None
        self.profiles = []
        self.selected_profiles = []
        self.processes = {}            # profile_name -> subprocess.Popen
        self.launched_profiles = set() # profils lancés durant cette session
        self.settings_json = "SL_Settings.json"
        self.legacy_settings_txt = "SL_Settings.txt"
        self.legacy_last_dir_txt = "last_directory.txt"

        # Réglages
        self.display_name = "[Name]"
        self.privateServers = []  # liste de tuples (name, parameter)

        # Charger réglages (JSON + migration auto)
        self.loadSettings()

        # UI
        self.initUI()

        # Charger profils si base_dir connu
        self.scanForProfiles()

        # Timer pour checker les processus
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self.checkProcesses)
        self.process_timer.start(2000)

    # ------------- Réglages (JSON + migration) -------------

    def loadSettings(self):
        data = {}

        # 1) Si JSON existe, on charge
        if os.path.exists(self.settings_json):
            try:
                with open(self.settings_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        # 2) Sinon, on tente migration depuis SL_Settings.txt + last_directory.txt
        else:
            base_dir = None
            name = "[Name]"
            servers = []

            # Lire last_directory.txt (hérité)
            if os.path.exists(self.legacy_last_dir_txt):
                try:
                    with open(self.legacy_last_dir_txt, "r", encoding="utf-8") as f:
                        base_dir = os.path.abspath(f.read().strip()) or None
                except Exception:
                    base_dir = None

            # Lire SL_Settings.txt (hérité)
            if os.path.exists(self.legacy_settings_txt):
                try:
                    with open(self.legacy_settings_txt, "r", encoding="utf-8") as f:
                        lines = [line.strip() for line in f.readlines()]
                    for line in lines:
                        if line.startswith("last_directory="):
                            # si présent, privilégier cette valeur
                            v = line[len("last_directory="):].strip()
                            base_dir = os.path.abspath(v) if v else base_dir
                        elif line.startswith("Name="):
                            name = line[len("Name="):] or "[Name]"
                        elif line.startswith("PrivateServers="):
                            raw = line[len("PrivateServers="):]
                            if raw:
                                # Ancien format "Nom|Param,Nom2|Param2"
                                for s in raw.split(","):
                                    if "|" in s:
                                        n, p = s.split("|", 1)
                                        servers.append({"name": n, "parameter": p})
                except Exception:
                    pass

            data = {
                "last_directory": base_dir,
                "Name": name,
                "PrivateServers": servers,
            }

            # Écrire le JSON migré
            try:
                with open(self.settings_json, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Appliquer avec valeurs de secours
        self.base_dir = data.get("last_directory") or None
        self.display_name = data.get("Name", self.display_name)

        normalized = []
        for item in data.get("PrivateServers", []):
            if isinstance(item, dict) and "name" in item and "parameter" in item:
                normalized.append((item["name"], item["parameter"]))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                normalized.append((item[0], item[1]))
        self.privateServers = normalized

    def saveSettings(self):
        data = {
            "last_directory": self.base_dir,
            "Name": self.display_name,
            "PrivateServers": [{"name": n, "parameter": p} for (n, p) in self.privateServers],
            "version": __version__
        }
        try:
            with open(self.settings_json, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")

    # ------------- Profils / Processus -------------

    def createProfile(self):
        if not self.base_dir:
            QMessageBox.warning(self, "Error", "Please select a base directory first.")
            return

        dialog = CreateProfileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            profile_name, copy_main = dialog.getData()
            if not profile_name:
                QMessageBox.warning(self, "Error", "Enter a valid profile name.")
                return

            profile_path = os.path.join(self.base_dir, profile_name)
            local_path = os.path.join(profile_path, ".local")

            try:
                os.makedirs(profile_path, exist_ok=True)
                os.makedirs(local_path, exist_ok=True)
                if copy_main:
                    import getpass
                    user = getpass.getuser()
                    src = f"/home/{user}/.var/app/org.vinegarhq.Sober/"
                    dst_parent = os.path.join(profile_path, ".var/app/")
                    os.makedirs(dst_parent, exist_ok=True)
                    subprocess.run(["cp", "-r", src, dst_parent], check=True)
                    appdata_path = os.path.join(dst_parent, "org.vinegarhq.Sober/data/sober/appData")
                    if os.path.exists(appdata_path):
                        subprocess.run(["rm", "-rf", appdata_path], check=True)
                self.scanForProfiles()
                QMessageBox.information(self, "Profile Created", f"Profile '{profile_name}' created successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create profile directory: {e}")

    def launchGame(self):
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return

        for profile in self.selected_profiles:
            if profile in self.processes and self.processes[profile].poll() is None:
                continue  # déjà lancé

            if profile == "Main Profile":
                proc = subprocess.Popen("flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
                proc = subprocess.Popen(command, shell=True)
            self.processes[profile] = proc
            self.launched_profiles.add(profile)
        self.updateMissingInstancesLabel()

    def checkProcesses(self):
        closed = [p for p, proc in self.processes.items() if proc.poll() is not None]
        for p in closed:
            del self.processes[p]
        self.updateMissingInstancesLabel()

    def runWithConsole(self):
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return

        terminal_command = None
        if shutil.which("konsole"):
            terminal_command = "konsole -e"
        elif shutil.which("x-terminal-emulator"):
            terminal_command = "x-terminal-emulator -e"
        elif shutil.which("gnome-terminal"):
            terminal_command = "gnome-terminal --"
        else:
            QMessageBox.critical(self, "Error", "No compatible terminal emulator found.")
            return

        for profile in self.selected_profiles:
            if profile in self.processes and self.processes[profile].poll() is None:
                continue

            if profile == "Main Profile":
                proc = subprocess.Popen(f"{terminal_command} flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'{terminal_command} env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
                proc = subprocess.Popen(command, shell=True)
            self.processes[profile] = proc
            self.launched_profiles.add(profile)
        self.updateMissingInstancesLabel()

    def runSpecificGame(self):
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return

        url, ok = QInputDialog.getText(self, "Game Link", "Enter the game link:")
        if ok and url.strip():
            match = re.search(r"games/(\d+)", url.strip())
            if not match:
                QMessageBox.warning(self, "Error", "Invalid Roblox game link.")
                return

            place_id = match.group(1)
            roblox_command = f'roblox://experience?placeId={place_id}'

            for profile in self.selected_profiles:
                if profile in self.processes and self.processes[profile].poll() is None:
                    continue

                if profile == "Main Profile":
                    proc = subprocess.Popen(f'flatpak run org.vinegarhq.Sober "{roblox_command}"', shell=True)
                else:
                    profile_path = os.path.join(self.base_dir, profile)
                    command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober "{roblox_command}"'
                    proc = subprocess.Popen(command, shell=True)
                self.processes[profile] = proc
                self.launched_profiles.add(profile)
            self.updateMissingInstancesLabel()

    def scanForProfiles(self):
        self.profileList.clear()
        profiles = []

        if self.base_dir and os.path.exists(self.base_dir):
            with os.scandir(self.base_dir) as entries:
                for entry in entries:
                    if entry.is_dir():
                        local_path = os.path.join(entry.path, ".local")
                        if os.path.exists(local_path) and os.path.isdir(local_path):
                            profiles.append(entry.name)

        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

        profiles.sort(key=natural_sort_key)
        if "Main Profile" in profiles:
            profiles.remove("Main Profile")
        profiles.insert(0, "Main Profile")

        self.profileList.addItems(profiles)
        self.updateMissingInstancesLabel(profiles)

    def updateMissingInstancesLabel(self, profiles=None):
        running = list(self.processes.keys())
        missing = [p for p in self.launched_profiles if p not in running]
        if missing:
            text = "Launched instances not running: " + ", ".join(missing)
        else:
            text = "Launched instances not running: None"

        font = self.missingInstancesLabel.font()
        base_size = 12
        max_len = 60
        if len(text) > max_len:
            font.setPointSize(max(base_size - (len(text) - max_len) // 8, 7))
        else:
            font.setPointSize(base_size)
        self.missingInstancesLabel.setFont(font)
        self.missingInstancesLabel.setText(text)

    def runMissingInstances(self):
        running = list(self.processes.keys())
        missing = [p for p in self.launched_profiles if p not in running]
        if not missing:
            QMessageBox.information(self, "Info", "No missing instances to run.")
            return
        for profile in missing:
            if profile == "Main Profile":
                proc = subprocess.Popen("flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
                proc = subprocess.Popen(command, shell=True)
            self.processes[profile] = proc
            self.launched_profiles.add(profile)
        self.updateMissingInstancesLabel()

    def exitAllSessions(self):
        result = QMessageBox.question(
            self, "Confirm Exit",
            "Do you want to force-close all Sober sessions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result == QMessageBox.StandardButton.Yes:
            subprocess.run("flatpak kill org.vinegarhq.Sober", shell=True)
            self.launched_profiles.clear()
            self.updateMissingInstancesLabel()
            QMessageBox.information(self, "Exit", "All Sober sessions have been forcibly closed.")

    # ------------- À propos / Update -------------

    def showAbout(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About Sober Launcher")
        layout = QVBoxLayout()

        icon_label = QLabel()
        icon_label.setPixmap(QPixmap("SoberLauncher.svg"))
        title_label = QLabel("<b>Sober Launcher</b><br>An easy launcher to control all your Sober Instances<br><br><i>Author: Taboulet</i>")
        version_label = QLabel(f"<b>Current Version:</b> {__version__}")

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(version_label)

        update_button = QPushButton("Update")
        update_button.clicked.connect(self.runUpdateScript)
        layout.addWidget(update_button)

        dialog.setLayout(layout)
        dialog.exec()

    def runUpdateScript(self):
        self.update_thread = UpdateThread()
        self.update_thread.update_failed.connect(lambda error: QMessageBox.critical(self, "Error", f"Failed to run update script: {error}"))
        self.update_thread.update_success.connect(lambda: QMessageBox.information(self, "Update", "Update completed successfully."))
        self.update_thread.start()

    # ------------- Crash windows -------------

    def removeCrashWindows(self):
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", "Crash"], capture_output=True, text=True
            )
            if result.returncode != 0 or not result.stdout.strip():
                QMessageBox.information(self, "Info", "No 'Crash' windows found.")
                return

            window_ids = result.stdout.strip().split("\n")
            for window_id in window_ids:
                subprocess.run(["xdotool", "windowkill", window_id])
        except FileNotFoundError:
            QMessageBox.critical(
                self, "Error", "The 'xdotool' command is not available. Please ensure it is installed."
            )

    # ------------- Lancement via lien pour manquants -------------

    def runMissingInstancesWithLink(self):
        running = list(self.processes.keys())
        missing = [p for p in self.launched_profiles if p not in running]
        if not missing:
            QMessageBox.information(self, "Info", "No missing instances to run.")
            return

        url, ok = QInputDialog.getText(self, "Game Link", "Enter the game link for all missing instances:")
        if not (ok and url.strip()):
            return

        match = re.search(r"games/(\d+)", url.strip())
        if not match:
            QMessageBox.warning(self, "Error", "Invalid Roblox game link.")
            return

        place_id = match.group(1)
        roblox_command = f'roblox://experience?placeId={place_id}'

        for profile in missing:
            if profile == "Main Profile":
                proc = subprocess.Popen(f'flatpak run org.vinegarhq.Sober "{roblox_command}"', shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober "{roblox_command}"'
                proc = subprocess.Popen(command, shell=True)
            self.processes[profile] = proc
            self.launched_profiles.add(profile)
        self.updateMissingInstancesLabel()

    def launchMainProfile(self):
        profile = "Main Profile"
        if profile in self.processes and self.processes[profile].poll() is None:
            QMessageBox.information(self, "Info", "Main Profile is already running.")
            return
        proc = subprocess.Popen("flatpak run org.vinegarhq.Sober", shell=True)
        self.processes[profile] = proc
        self.launched_profiles.add(profile)
        self.updateMissingInstancesLabel()

    # ------------- Nom affiché -------------

    def editDisplayName(self):
        name, ok = QInputDialog.getText(self, "Edit Name", "Enter your name:", text=self.display_name)
        if ok and name.strip():
            self.display_name = name.strip()
            self.displayNameLabel.setText(f"Hi, {self.display_name}")
            self.saveSettings()

    def loadDisplayName(self):
        self.displayNameLabel.setText(f"Hi, {self.display_name}")

    # ------------- Serveurs privés -------------

    def addPrivateServer(self):
        name, ok1 = QInputDialog.getText(self, "Private Server Name", "Enter a name for the private server:")
        if not ok1 or not name.strip():
            return
        parameter, ok2 = QInputDialog.getText(self, "Parameter", "Enter the parameter:")
        if not ok2 or not parameter.strip():
            return

        name = name.strip()
        parameter = parameter.strip()
        self.privateServers.append((name, parameter))
        self.saveSettings()
        self.refreshPrivateServerButtons()

    def addPrivateServerButtonWidget(self, name, parameter):
        btn = QPushButton(name)
        btn.setMinimumWidth(120)
        btn.clicked.connect(lambda: self.runParameter(parameter))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, b=btn, n=name, p=parameter: self.showPrivateServerContextMenu(b, n, p)
        )
        self.privateServerButtonsLayout.addWidget(btn)

    def showPrivateServerContextMenu(self, button, name, parameter):
        menu = QMenu()
        remove_action = menu.addAction("Remove")
        edit_action = menu.addAction("Edit")
        action = menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        if action == remove_action:
            self.removePrivateServerButton(name)
        elif action == edit_action:
            self.editPrivateServerButton(name, parameter)

    def removePrivateServerButton(self, name):
        self.privateServers = [(n, p) for (n, p) in self.privateServers if n != name]
        self.saveSettings()
        self.refreshPrivateServerButtons()

    def editPrivateServerButton(self, old_name, old_parameter):
        name, ok1 = QInputDialog.getText(self, "Edit Private Server Name", "Edit the name:", text=old_name)
        if not ok1 or not name.strip():
            return
        parameter, ok2 = QInputDialog.getText(self, "Edit Parameter", "Edit the parameter:", text=old_parameter)
        if not ok2 or not parameter.strip():
            return
        name = name.strip()
        parameter = parameter.strip()

        updated = []
        for (n, p) in self.privateServers:
            if n == old_name:
                updated.append((name, parameter))
            else:
                updated.append((n, p))
        self.privateServers = updated
        self.saveSettings()
        self.refreshPrivateServerButtons()

    def runParameter(self, parameter):
        command = f'flatpak run org.vinegarhq.Sober "{parameter}"'
        subprocess.Popen(command, shell=True)

    def quickLaunch(self):
        parameter, ok = QInputDialog.getText(self, "Parameter", "Enter the parameter:")
        if not ok or not parameter.strip():
            return
        self.runParameter(parameter.strip())

    def refreshPrivateServerButtons(self):
        # Nettoyer
        while self.privateServerButtonsLayout.count():
            item = self.privateServerButtonsLayout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        # Recréer
        for name, parameter in self.privateServers:
            self.addPrivateServerButtonWidget(name, parameter)

    # ------------- UI -------------

    def initUI(self):
        main_tab_widget = QTabWidget()

        # Barre globale (placeholder)
        global_top_bar = QHBoxLayout()
        global_top_bar.addStretch(1)

        # ----- Onglet Instances -----
        instances_tab = QWidget()
        instances_layout = QVBoxLayout(instances_tab)

        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        top_bar = QHBoxLayout()
        self.selectDirButton = QPushButton("Select Base Directory")
        self.selectDirButton.clicked.connect(self.selectDirectory)
        top_bar.addWidget(self.selectDirButton)

        self.refreshButton = QPushButton()
        self.refreshButton.setIcon(QIcon.fromTheme("view-refresh"))
        self.refreshButton.setToolTip("Refresh Profiles")
        self.refreshButton.clicked.connect(self.scanForProfiles)
        top_bar.addWidget(self.refreshButton)

        self.createProfileButton = QPushButton("Create Profile")
        self.createProfileButton.clicked.connect(self.createProfile)
        top_bar.addWidget(self.createProfileButton)

        self.exitAllButton = QPushButton("Exit All Sessions")
        self.exitAllButton.clicked.connect(self.exitAllSessions)
        top_bar.addWidget(self.exitAllButton)

        self.removeCrashButton = QPushButton("Remove Crash")
        self.removeCrashButton.clicked.connect(self.removeCrashWindows)
        top_bar.addWidget(self.removeCrashButton)

        self.aboutButtonInstances = QPushButton("About")
        self.aboutButtonInstances.clicked.connect(self.showAbout)
        top_bar.addWidget(self.aboutButtonInstances)

        left_layout.addLayout(top_bar)

        self.profileList = QListWidget()
        self.profileList.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.profileList.itemSelectionChanged.connect(self.updateSelectedProfiles)
        left_layout.addWidget(self.profileList)

        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.selectedProfileLabel = QLabel("Selected Profiles: None")
        self.selectedProfileLabel.setWordWrap(True)
        self.selectedProfileLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        right_layout.addWidget(self.selectedProfileLabel)

        self.launchButton = QPushButton("Launch Game")
        self.launchButton.clicked.connect(self.launchGame)
        right_layout.addWidget(self.launchButton)

        self.consoleLaunchButton = QPushButton("Run with Console")
        self.consoleLaunchButton.clicked.connect(self.runWithConsole)
        right_layout.addWidget(self.consoleLaunchButton)

        self.runSpecificGameButton = QPushButton("Run Specific Game")
        self.runSpecificGameButton.clicked.connect(self.runSpecificGame)
        right_layout.addWidget(self.runSpecificGameButton)

        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_layout)
        right_panel_widget.setFixedWidth(300)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(right_panel_widget)

        bottom_layout = QHBoxLayout()
        self.missingInstancesLabel = QLabel("Instances not running: None")
        self.missingInstancesLabel.setWordWrap(True)
        self.missingInstancesLabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_layout.addWidget(self.missingInstancesLabel)

        self.runMissingButton = QPushButton("Run Missing Instances")
        self.runMissingButton.clicked.connect(self.runMissingInstances)
        bottom_layout.addWidget(self.runMissingButton)

        self.runMissingWithLinkButton = QPushButton()
        self.runMissingWithLinkButton.setIcon(QIcon.fromTheme("internet-web-browser"))
        self.runMissingWithLinkButton.setToolTip("Run Missing Instances with Game Link")
        self.runMissingWithLinkButton.clicked.connect(self.runMissingInstancesWithLink)
        bottom_layout.addWidget(self.runMissingWithLinkButton)

        instances_layout.addLayout(main_layout)
        instances_layout.addLayout(bottom_layout)
        instances_tab.setLayout(instances_layout)

        # ----- Onglet Roblox Player -----
        roblox_tab = QWidget()
        roblox_layout = QVBoxLayout()
        roblox_tab.setLayout(roblox_layout)

        roblox_layout.addStretch(2)

        name_row = QHBoxLayout()
        self.displayNameLabel = QLabel(f"Hi, {self.display_name}")
        self.displayNameLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        font = self.displayNameLabel.font()
        font.setPointSize(32)
        font.setBold(True)
        self.displayNameLabel.setFont(font)
        name_row.addWidget(self.displayNameLabel)

        pencil_btn = QPushButton()
        pencil_btn.setIcon(QIcon.fromTheme("document-edit"))
        pencil_btn.setFixedSize(32, 32)
        pencil_btn.setToolTip("Edit name")
        pencil_btn.clicked.connect(self.editDisplayName)
        name_row.addWidget(pencil_btn)

        name_row.addStretch(1)
        roblox_layout.addLayout(name_row)

        roblox_layout.addStretch(1)

        play_button = QPushButton("Play")
        play_button.setFixedHeight(60)
        play_button.setStyleSheet("font-size: 20px;")
        play_button.clicked.connect(self.launchMainProfile)
        roblox_layout.addWidget(play_button, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        button_row = QHBoxLayout()
        self.addPrivateServerButton = QPushButton("Add private server")
        self.addPrivateServerButton.clicked.connect(self.addPrivateServer)
        button_row.addWidget(self.addPrivateServerButton)

        self.quickLaunchButton = QPushButton("Quick launch")
        self.quickLaunchButton.clicked.connect(self.quickLaunch)
        button_row.addWidget(self.quickLaunchButton)

        self.privateServerButtonsLayout = QHBoxLayout()
        button_row.addLayout(self.privateServerButtonsLayout)
        button_row.addStretch(1)

        roblox_layout.addLayout(button_row)
        roblox_layout.addStretch(6)

        # Recharger le nom et les serveurs privés à l'affichage
        QTimer.singleShot(0, self.loadDisplayName)
        QTimer.singleShot(0, self.refreshPrivateServerButtons)

        # Tabs
        main_tab_widget.addTab(instances_tab, "Instances")
        main_tab_widget.addTab(roblox_tab, "Roblox Player")
        main_tab_widget.setCurrentIndex(0)

        wrapper_layout = QVBoxLayout()
        wrapper_layout.addLayout(global_top_bar)
        wrapper_layout.addWidget(main_tab_widget)
        self.setLayout(wrapper_layout)

        self.setWindowTitle("Sober Launcher")
        self.setWindowIcon(QIcon("SoberLauncher.svg"))
        self.showMaximized()

    # ------------- Sélection et dossiers -------------

    def selectDirectory(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Select Base Directory")
        if dir_selected:
            self.base_dir = os.path.abspath(dir_selected)
            self.saveSettings()
            QMessageBox.information(self, "Directory Selected", f"Base Directory: {self.base_dir}")
            self.scanForProfiles()

    def updateSelectedProfiles(self):
        self.selected_profiles = [item.text() for item in self.profileList.selectedItems()]
        self.selectedProfileLabel.setText(
            f"Selected Profiles: {', '.join(self.selected_profiles) if self.selected_profiles else 'None'}"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SoberLauncher()
    window.show()
    sys.exit(app.exec())
