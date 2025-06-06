#!/usr/bin/env python3

import sys
import os
import subprocess
import shutil
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QFileDialog, QLineEdit, QMessageBox, QInputDialog, QLabel, QDialog, QSizePolicy, QListWidget, QAbstractItemView
from PyQt6.QtGui import QIcon, QPixmap  # ✅ Correct imports for icons

class SoberLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.base_dir = None  # ✅ Initialize base_dir
        self.profiles = []
        self.selected_profiles = []  # ✅ Allow multiple profile selection
        self.initUI()
        self.loadPreviousDirectory()

    def initUI(self):
        main_layout = QHBoxLayout()  # ✅ Ensure right panel is positioned correctly

        # Left section for profile selection
        left_layout = QVBoxLayout()
        
        # Top bar layout
        top_bar = QHBoxLayout()

        self.selectDirButton = QPushButton("Select Base Directory")
        self.selectDirButton.clicked.connect(self.selectDirectory)
        top_bar.addWidget(self.selectDirButton)

        # Add refresh button with an icon
        self.refreshButton = QPushButton()
        self.refreshButton.setIcon(QIcon.fromTheme("view-refresh"))  # Use a standard refresh icon
        self.refreshButton.setToolTip("Refresh Profiles")
        self.refreshButton.clicked.connect(self.scanForProfiles)  # Connect to the scanForProfiles method
        top_bar.addWidget(self.refreshButton)

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

        # Profile list (✅ Correct normal selection behavior: Shift & Ctrl work properly)
        self.profileList = QListWidget()
        self.profileList.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # ✅ Fixed selection behavior
        self.profileList.itemSelectionChanged.connect(self.updateSelectedProfiles)
        left_layout.addWidget(self.profileList)

        # Right panel (✅ Correctly positioned to the right)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)  # Optional: Remove extra margins
        right_layout.setSpacing(10)  # Optional: Adjust spacing between widgets

        self.selectedProfileLabel = QLabel("Selected Profiles: None")
        self.selectedProfileLabel.setWordWrap(True)  # ✅ Enable word wrapping for long text
        self.selectedProfileLabel.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # ✅ Prevent expanding the window
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

        # Set a fixed width for the right panel
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_layout)
        right_panel_widget.setFixedWidth(300)  # ✅ Set the desired fixed width for the right bar

        main_layout.addLayout(left_layout)
        main_layout.addWidget(right_panel_widget)  # Add the fixed-width right panel

        self.setLayout(main_layout)
        self.setWindowTitle("Sober Launcher")
        self.setWindowIcon(QIcon("SoberLauncher.svg"))  # ✅ Properly loads app icon
        self.showMaximized()  # ✅ Opens maximized (not fullscreen)

        self.scanForProfiles()

    def selectDirectory(self):
        dir_selected = QFileDialog.getExistingDirectory(self, "Select Base Directory")
        if dir_selected:
            self.base_dir = os.path.abspath(dir_selected)
            QMessageBox.information(self, "Directory Selected", f"Base Directory: {self.base_dir}")
            self.scanForProfiles()
            self.savePreviousDirectory()  # ✅ Fixed missing method call

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
        """✅ Create a new profile with a dialog to choose the name."""
        if not self.base_dir:
            QMessageBox.warning(self, "Error", "Please select a base directory first.")
            return

        # Show input dialog to get the profile name
        profile_name, ok = QInputDialog.getText(self, "Choose a Name", "Enter the profile name:")
        if ok and profile_name.strip():
            profile_name = profile_name.strip()
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
        """✅ Launch multiple selected profiles with the default terminal."""
        if not self.selected_profiles:
            QMessageBox.warning(self, "Error", "No profiles selected.")
            return

        # Check for terminal emulator availability
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
            if profile == "Main Profile":
                subprocess.Popen(f"{terminal_command} flatpak run org.vinegarhq.Sober", shell=True)
            else:
                profile_path = os.path.join(self.base_dir, profile)
                command = f'{terminal_command} env HOME="{profile_path}" flatpak run org.vinegarhq.Sober'
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
        profiles = []

        if self.base_dir and os.path.exists(self.base_dir):
            with os.scandir(self.base_dir) as entries:
                for entry in entries:
                    if entry.is_dir():
                        local_path = os.path.join(entry.path, ".local")
                        if os.path.exists(local_path) and os.path.isdir(local_path):
                            profiles.append(entry.name)

        profiles.sort()  # Sort profiles alphabetically
        if "Main Profile" in profiles:
            profiles.remove("Main Profile")  # Remove "Main Profile" if it exists in the list
        profiles.insert(0, "Main Profile")  # Ensure "Main Profile" is always at the top
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
        icon_label.setPixmap(QPixmap("SoberLauncher.svg"))  # ✅ Properly displays About icon
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
