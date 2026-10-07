# Desktop builds

See [README.md](README.md) for setup, local builds, GitHub releases and verified Windows updates.

The latest local build is `dist/github-release/Logistra-Print.exe`; its ZIP includes Latvian instructions. It includes Python, Tkinter, icons, the default test PDF and all runtime dependencies. User settings and DPAPI keys are kept outside the executable, preserving them during updates.

The build command supports `--dist-dir`, `--version X.Y.Z` and `--repository owner/repo`. GitHub tagged releases embed their actual version and repository. Only generic `config.defaults.json` is bundled.

Physical printing must be verified on the computer with the chosen printer installed. The test suite uses print mocks and does not perform physical printing.
