#!/usr/bin/env python3

import sys
import os
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox, QInputDialog, QLabel, QDialog, QSizePolicy, QListWidget, QAbstractItemView
from PyQt6.QtGui import QIcon, QPixmap

class SoberLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.base_dir = None
        self.profiles = []
        self.selected_profiles = [] 
        self.initUI()
        self.loadPreviousDirectory()

    def initUI(self):
        main_layout = QHBoxLayout()  

       
        left_layout = QVBoxLayout()
        
        
        top_bar = QHBoxLayout()

        self.selectDirButton = QPushButton("Select Base Directory")
        self.selectDirButton.clicked.connect(self.selectDirectory)
        top_bar.addWidget(self.selectDirButton)

        self.profileInput = QLineEdit()
        self.profileInput.setPlaceholderText("Enter profile name")
        top_bar.addWidget(self.profileInput)

        self.createProfileButton = QPushButton("Create Profile")
        self.createProfileButton.clicked.connect(self.createProfile)
        top_bar.addWidget(self.createProfileButton)

        self.exitAllButton = QPushButton("Exit All Sessions")
        self.exitAllButton.clicked.connect(self.exitAllSessions)
        top_bar.addWidget(self.exitAllButton)

        self.aboutButton = QPushButton("About")
        self.aboutButton.clicked.connect(self.showAbout)
        top_bar.addWidget(self.aboutButton)

        left_layout.addLayout(top_bar)

        
        self.profileList = QListWidget()
        self.profileList.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  
        self.profileList.itemSelectionChanged.connect(self.updateSelectedProfiles)
        left_layout.addWidget(self.profileList)

        
        right_layout = QVBoxLayout()
        self.selectedProfileLabel = QLabel("Selected Profiles: None")
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

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)
        self.setWindowTitle("Sober Launcher")
        self.setWindowIcon(QIcon("SoberLauncher.svg")) 
        self.showMaximized()  

        self.scanForProfiles()

    def selectDirectory(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Select Base Directory")
        if dir_selected:
            self.base_dir = os.path.abspath(dir_selected)
            QMessageBox.information(self, "Directory Selected", f"Base Directory: {self.base_dir}")
            self.scanForProfiles()
            self.savePreviousDirectory()  

    def savePreviousDirectory(self):
        """✅ Save the selected directory for persistence."""
        if self.base_dir:
            with open("last_directory.txt", "w") as f:
                f.write(self.base_dir)

    def loadPreviousDirectory(self):
        """✅ Load the last used directory."""
        if os.path.exists("last_directory.txt"):
            with open("last_directory.txt", "r") as f:
                self.base_dir = os.path.abspath(f.read().strip())
                self.scanForProfiles()

    def createProfile(self):
        if not self.base_dir:
            QMessageBox.warning(self, "Error", "Please select a base directory first.")
            return

        profile_name = self.profileInput.text().strip()
        if profile_name:
            profile_path = os.path.join(self.base_dir, profile_name)
            local_path = os.path.join(profile_path, ".local")

            try:
                os.makedirs(profile_path, exist_ok=True)
                os.makedirs(local_path, exist_ok=True)
                self.scanForProfiles()
                QMessageBox.information(self, "Profile Created", f"Profile '{profile_name}' created successfully!")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Failed to create profile directory: {e}")
        else:
            QMessageBox.warning(self, "Error", "Enter a valid profile name.")

    def updateSelectedProfiles(self):
        """✅ Update selected profiles when selection changes."""
        self.selected_profiles = [item.text() for item in self.profileList.selectedItems()]
        self.selectedProfileLabel.setText(f"Selected Profiles: {', '.join(self.selected_profiles) if self.selected_profiles else 'None'}")

    def launchGame(self):
        """✅ Launch multiple selected profiles."""
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return
        
        for profile in self.selected_profiles:
            if profile == "Main Profile":
                subprocess.Popen("flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
                subprocess.Popen(command, shell=True)

    def runWithConsole(self):
        """✅ Launch multiple selected profiles with a console."""
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return
        
        for profile in self.selected_profiles:
            if profile == "Main Profile":
                subprocess.Popen("konsole -e flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'konsole -e env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
                subprocess.Popen(command, shell=True)

    def runSpecificGame(self):
        """✅ Run a specific game for selected profiles."""
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return
        
        url, ok = QInputDialog.getText(self, "Game Link", "Enter the game link:")
        if ok and url.strip():
            for profile in self.selected_profiles:
                if profile == "Main Profile":
                    subprocess.Popen(f'flatpak run org.vinegarhq.Sober "{url.strip()}"', shell=True)
                else:
                    profile_path = os.path.join(self.base_dir, profile)
                    command = f'env HOME="{profile_path}" flatpak run org.vinegarhq.Sober "{url.strip()}"'
                    subprocess.Popen(command, shell=True)

    def scanForProfiles(self):
        """✅ Ensure 'Main Profile' is always first, then sorted profiles."""
        self.profileList.clear()
        profiles = ["Main Profile"]

        if self.base_dir and os.path.exists(self.base_dir):
            with os.scandir(self.base_dir) as entries:
                for entry in entries:
                    if entry.is_dir():
                        local_path = os.path.join(entry.path, ".local")
                        if os.path.exists(local_path) and os.path.isdir(local_path):
                            profiles.append(entry.name)

        profiles.sort()
        self.profileList.addItems(profiles)

    def exitAllSessions(self):
        result = QMessageBox.question(self, "Confirm Exit", "Do you want to force-close all Sober sessions?", 
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if result == QMessageBox.StandardButton.Yes:
            subprocess.run("flatpak kill org.vinegarhq.Sober", shell=True)
            QMessageBox.information(self, "Exit", "All Sober sessions have been forcibly closed.")

    def showAbout(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About Sober Launcher")
        layout = QHBoxLayout()

        icon_label = QLabel()
        icon_label.setPixmap(QPixmap("SoberLauncher.svg")) 
        title_label = QLabel("<b>Sober Launcher</b><br>An easy launcher to control all your Sober Instances<br><br><i>Author: Taboulet</i>")

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        dialog.setLayout(layout)
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SoberLauncher()
    window.show()
    sys.exit(app.exec())
