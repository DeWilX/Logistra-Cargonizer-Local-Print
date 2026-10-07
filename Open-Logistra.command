#!/bin/zsh
cd -- "${0:A:h}"
for candidate in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import tkinter' 2>/dev/null; then
    exec "$candidate" logistra_gui.py
  fi
done
if command -v python3 >/dev/null && python3 -c 'import tkinter' 2>/dev/null; then
  exec python3 logistra_gui.py
fi
echo 'Instalē Python ar Tkinter no https://www.python.org/downloads/macos/ un mēģini vēlreiz.'
read '?Nospied Enter, lai aizvērtu.'
