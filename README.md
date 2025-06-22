# SoberLauncher
An easy launcher to control all your Sober Instances

This is a way to create profiles for Sober and run them all at the same time using environnement variables

🌐 Dependencies
- You will need PyQt6 and python-requests, download them using :
`sudo pacman -S python-requests python-pyqt6` or
`pip install requests PyQt6` (xdotool, flatpak and Sober are also needed, Sober HAS to be downloaded in system using `sudo flatpak install --system flathub org.vinegarhq.Sober`and fix permission issues with `sudo flatpak override --system --device=all org.vinegarhq.Sober`)

⚠️ Clear limitation
- This is a basic project made by me, i'll fix the issues but don't expect a perfect app made by a big team and stuff
- This is made with python, to launch it just double click on the "SoberLauncher.py" file (try to make it executable if it's not for some reason)
- This is mainly made for steamos, this will of course work on other distros but for now this won't be perfect
- This will launch Sober in a specific environnement, which will make all profiles have their own data, meaning this will take a bit of space (roughly 500-700MB per profies), i might make them all use the same data folder but i first need to find the folders responsible for the folder's account data

- (Might've used a lil bit of ai to create this)



![image](https://github.com/user-attachments/assets/db1608d7-e819-4af9-87ed-3923a1204250)
