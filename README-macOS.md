# Logistra Print for macOS

GitHub Releases provides ready-to-use applications for both Mac processor types:

- Apple Silicon (M1 and newer): `Logistra-macOS-arm64.zip`.
- Intel: `Logistra-macOS-x86_64.zip`.

Extract the matching ZIP and move `Logistra.app` to Applications. Python is included; no separate installation is required.

## First launch and the macOS security warning

The application is currently not signed with an Apple Developer ID certificate or notarized. macOS may therefore report that it cannot verify the developer or check the application for malicious software.

1. Download the application from this project's [GitHub Releases](https://github.com/DeWilX/Logistra-Cargonizer-Local-Print/releases/latest) and try opening `Applications/Logistra.app`.
2. If an unidentified-developer warning appears, dismiss it and open **Apple menu → System Settings → Privacy & Security**.
3. Under **Security**, click **Open Anyway** next to `Logistra`. Enter your Mac password or use Touch ID if requested.
4. Click **Open** in the confirmation dialog. Open the application from Applications on subsequent launches.

This permission applies to this application only. You do not need to disable Gatekeeper for your computer. If a warning specifically reports detected malware or a damaged or modified application, do not use these steps to bypass it; stop and download a fresh copy from Releases. See [Apple's instructions for opening applications safely](https://support.apple.com/102445).

## Updates

Starting with version 0.1.8, **Settings → Updates** lets you check for, download and install a newer version automatically. The application selects the matching Apple Silicon or Intel archive, verifies its size and SHA-256 digest, waits for active work to finish, replaces `Logistra.app` and launches it again. Settings, the Keychain API key and print history are preserved. The previous application remains beside it as an `.update-backup-…` copy. macOS requests administrator authorization if the installation folder is not writable.

Move `Logistra.app` to Applications and launch it from there before updating. Copies running from a disk image or a temporary macOS App Translocation folder cannot update in place. To upgrade from an older version, close it, download the latest ZIP and replace `Logistra.app` manually once. Update diagnostics are stored in `~/Library/Application Support/Logistra/updates/update.log`.

## Setup and printing

In Settings, enter your own Cargonizer Sender ID and API key, then save and check the connection. No account or printer is preconfigured. The key is stored in the macOS login Keychain, rather than the configuration or activity log. A Windows DPAPI key file cannot be transferred to a Mac.

Select a printer installed in **System Settings → Printers & Scanners**. The application uses CUPS queues and `lp`, requests one copy and sets `print-scaling=none`. **Test print** is optional and sends the included 102 × 192 mm test label in the selected interface language: Latvian, English or Norwegian Bokmål. Check the driver's paper size before printing. Successful submission to a queue does not confirm that a physical label was printed.

Shipments load on launch when an API key is available. Choose a period preset or dates in the calendar, then use **Filter** after entering dates manually. Use Command/Ctrl or Shift to select multiple shipments. Hover over the account, printer or shipment status to see the reason for its green or red indicator. A successfully loaded empty shipment list is normal.

Settings, logs and the SQLite print history are stored in `~/Library/Application Support/Logistra`. You can choose the PDF download folder in Settings. Replacing the application preserves these files. Run automatic printing for a Sender ID on only one computer at a time.

Automation checks open and transferred shipments, including all result pages. A shipment can therefore be found after it transfers between checks. New IDs are saved before downloading; PDFs that are not yet available remain queued for retry. The first run, including migration from open-only automation, skips existing shipments as a baseline. After downtime, discovery resumes from its saved date.

Minimizing the window keeps the application running in the background. The Mac must remain powered on and awake. Automatic launch uses `~/Library/LaunchAgents/app.logistra.print.plist`. The system tray feature is available on Windows. Automatic application updates are available in the packaged Windows and Mac versions.

GitHub builds and tests Apple Silicon and Intel versions separately, including packaged application self-tests, replacement and restart checks, and an audit of bundled defaults. Access to the user's Keychain, physical printing and launch at login still need confirmation on the user's Mac.

## Running and building from source

Install Python 3.12 with Tkinter and the dependencies in `requirements-build.txt`, then run `python3 logistra_gui.py`. To build the application, run `python3 build_app.py`.

## Support the project

Developer: **Gustavs Meijers**. If the application is useful to you, you can support its development with a [donation on Ko-fi](https://ko-fi.com/gustavsm).

## License

From version 0.1.6, business use, modification and free redistribution are permitted. The application and modified versions may not be sold or distributed for a fee without the author's written permission. See the included `LICENSE` file for the full terms. Copies previously distributed under the MIT License retain their original permissions.
