# Logistra Print

A Windows desktop application for downloading Cargonizer shipping labels and printing them on a locally installed printer. Python is included in the EXE. The interface supports Latvian, English and Norwegian Bokmål.

## Getting started

Download `Logistra-Print.exe` from this repository's GitHub Releases and put it in a permanent, writable folder. In Settings, enter your own Cargonizer Sender ID and API key. Choose and save a locally installed printer, then verify the included test label before enabling automatic printing. No account, company or printer is preconfigured.

For macOS, download the Apple Silicon or Intel ZIP, extract it and move `Logistra.app` to Applications. Python is included. The app is not Developer ID signed or notarized. For an unidentified-developer warning, follow the **System Settings → Privacy & Security → Open Anyway** steps in [README-macOS.md](README-macOS.md), also included in the Mac ZIP. Do not disable Gatekeeper globally or override a warning that specifically detects malware. See [Apple's instructions](https://support.apple.com/102445).

The API key is protected with Windows DPAPI. User settings, the key and printing history live under `%LOCALAPPDATA%\Logistra`; PDFs can be saved to a chosen folder. Updating the EXE preserves those files. Keys cannot be moved between Windows accounts or computers.

## Features

- Permanent system tray icon, optional close-to-tray and minimized Windows sign-in startup.
- System, light and dark themes; live language switching.
- Shipment history with complete pagination, carrier/text/date filters, period presets and calendars.
- Ctrl/Shift selection, PDF downloads, reprints and exact reference/order lookup across history.
- PDF filenames include shipment ID and reference.
- Automatic polling with a five-second minimum and an API rate-limit cooldown.
- SQLite duplicate protection, initial baseline and no automatic retries of uncertain print jobs.
- Adobe Reader or SumatraPDF printing. Microsoft Print to PDF saves the original PDF instead of reprinting through Adobe.
- GitHub release update checking, verified download, backup and EXE replacement after active work finishes.

Print commands do not prove that a physical label was printed. Install the printer driver, choose the correct paper size and verify barcodes. The included test page is 102 × 192 mm. Automatic discovery currently rejects multiple pages of new shipments; history browsing supports all pages.

## Build locally

Run `Build-Windows.ps1` or install Python 3.12 and run:

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -q
python build_app.py --version 0.1.0 --repository YOUR-OWNER/YOUR-REPO
```

The output is `dist/Logistra-Print.exe` and `dist/Logistra-Windows-exe.zip`. Builds always bundle `config.defaults.json`, never the local `config.json`. Local data, credentials, PDFs, logs, screenshots, build environments and EXEs are ignored by Git.

## GitHub build and release

Pushes to `main`/`master` and pull requests run tests and create downloadable Windows and macOS build artifacts. Push a version tag such as `v0.1.2` to build and publish a Windows EXE/ZIP and macOS ZIPs for Apple Silicon (`arm64`) and Intel (`x86_64`) in GitHub Releases. Publication waits until all three builds and packaged application checks pass. The tag must be `vX.Y.Z`; each update requires a higher version. The release job uses the repository's built-in `GITHUB_TOKEN` with contents-write permission. No Cargonizer credentials belong in repository secrets.

Release builds embed the actual repository name and version. Settings → Updates shows the version, developer and update buttons; the update repository is configured by the build and does not require user input. Automatic checking runs on launch and offers a download/update action. The current implementation uses public repositories. Installation waits for active work, keeps an EXE backup and restarts the app; the EXE folder must be writable. Download or replacement failures leave the current EXE in place; replacement diagnostics are in `%LOCALAPPDATA%\Logistra\updates\update.log`.

Updates use [GitHub's latest release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release) and the [release asset SHA-256 digest](https://docs.github.com/en/rest/releases/assets#get-a-release-asset). Older releases without a digest cannot be installed automatically.

## Development notes

Run `Open-Logistra.cmd` for the Python GUI. The local `config.json` is created from the generic defaults and is ignored by Git. Do not commit user data. Interactive tray tests are skipped in GitHub Actions; the Windows release job also runs the packaged EXE self-test.

macOS builds are available in GitHub Releases and include Python. Automatic EXE replacement is Windows-only. See [README-macOS.md](README-macOS.md) and [LIETOSANA-Windows.txt](LIETOSANA-Windows.txt).

## Support the project

Developed by **Gustavs Meijers**. If Logistra Print helps you, you can support its development with a [donation on Ko-fi](https://ko-fi.com/gustavsm).
