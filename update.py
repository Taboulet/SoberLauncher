#!/usr/bin/env python3

import os
import sys
import requests
import zipfile
import shutil
from PyQt6.QtWidgets import QApplication, QMessageBox

GITHUB_API_RELEASES_URL = "https://api.github.com/repos/Taboulet/SoberLauncher/releases/latest"
CURRENT_DIRECTORY = os.getcwd()

def get_latest_release():
    """Fetch the latest release information from GitHub."""
    try:
        response = requests.get(GITHUB_API_RELEASES_URL)
        if response.status_code == 200:
            data = response.json()
            return data.get("name", "Unknown Release"), data.get("zipball_url", None)
        else:
            return "Unknown Release", None
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Error fetching release information: {e}")
        return "Unknown Release", None

def download_and_extract_zip(url):
    """Download and extract the latest release ZIP file."""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            zip_path = os.path.join(CURRENT_DIRECTORY, "update.zip")
            with open(zip_path, "wb") as f:
                f.write(response.content)

            # Extract the ZIP file
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall("update_temp")

            # Locate the extracted folder (e.g., Taboulet-SoberLauncher-<hash>)
            extracted_folder = next(
                (os.path.join("update_temp", d) for d in os.listdir("update_temp") if os.path.isdir(os.path.join("update_temp", d))),
                None
            )

            if not extracted_folder:
                QMessageBox.critical(None, "Error", "Failed to locate the extracted update folder.")
                return

            # Move extracted files to the current directory
            files_replaced = False
            for root, dirs, files in os.walk(extracted_folder):
                for file in files:
                    src_path = os.path.join(root, file)
                    rel_path = os.path.relpath(src_path, extracted_folder)
                    dest_path = os.path.join(CURRENT_DIRECTORY, rel_path)

                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.move(src_path, dest_path)
                    files_replaced = True

            # Make the updater and launcher executable
            launcher_path = os.path.join(CURRENT_DIRECTORY, "SoberLauncher.py")
            updater_path = os.path.join(CURRENT_DIRECTORY, "update.py")
            if os.path.exists(launcher_path):
                os.chmod(launcher_path, 0o755)  # Make executable
            if os.path.exists(updater_path):
                os.chmod(updater_path, 0o755)  # Make executable

            # Cleanup
            os.remove(zip_path)
            shutil.rmtree("update_temp")

            if files_replaced:
                QMessageBox.information(None, "Update", "Update completed successfully.")
            else:
                QMessageBox.warning(None, "Update", "No files were replaced during the update.")
        else:
            QMessageBox.critical(None, "Error", "Failed to download the update.")
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Error during update: {e}")

def main():
    app = QApplication([])

    latest_release_title, zip_url = get_latest_release()
    if not zip_url:
        QMessageBox.critical(None, "Error", "Failed to fetch the latest release.")
        sys.exit()

    reply = QMessageBox.question(
        None,
        "Update Available",
        f"The latest release is: {latest_release_title}.\nWould you like to update?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if reply == QMessageBox.StandardButton.Yes:
        download_and_extract_zip(zip_url)
    else:
        QMessageBox.information(None, "Update", "Update canceled.")

    app.exec()

if __name__ == "__main__":
    main()