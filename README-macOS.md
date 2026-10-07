# Logistra Print macOS

GitHub Releases piedāvā gatavu lietotni abiem Mac procesoru veidiem:

- Apple Silicon (M1 un jaunāki): `Logistra-macOS-arm64.zip`.
- Intel: `Logistra-macOS-x86_64.zip`.

Izpako atbilstošo ZIP un pārvieto `Logistra.app` uz Applications. Python ir iekļauts. Lietotne pašlaik nav parakstīta ar Apple Developer sertifikātu vai notarizēta; macOS var prasīt atļauju to atvērt System Settings → Privacy & Security.

Iestatījumos ievadi savu Sender ID un API atslēgu, saglabā un pārbaudi pieslēgumu. Nav iepriekš aizpildīta konta vai printera. Atslēga glabājas macOS login Keychain, nevis konfigurācijā vai žurnālā. Windows DPAPI failu uz Mac pārnest nevar.

Izvēlies printeri, kas pievienots System Settings → Printers & Scanners. Lietotne izmanto CUPS rindas un `lp`, vienu kopiju un `print-scaling=none`. Poga Izdrukāt PDF nosūta iekļauto 102 × 192 mm testa etiķeti; pirms drukāšanas pārbaudi draivera papīra izmēru. Sekmīga nosūtīšana rindai nenozīmē, ka etiķete fiziski izdrukāta.

Iestatījumi, žurnāls un SQLite uzskaite glabājas `~/Library/Application Support/Logistra`. PDF mapi var izvēlēties iestatījumos. Lietotnes aizstāšana ar jaunāku versiju saglabā šos datus. Vienam Sender ID automātisko druku vienlaikus darbini vienā datorā.

Minimizēts logs turpina darbu fonā. Mac datoram jābūt ieslēgtam un nedrīkst gulēt. Automātiska palaišana izmanto `~/Library/LaunchAgents/app.logistra.print.plist`. Windows system tray un automātiska EXE aizstāšana ir Windows funkcijas; Mac atjauninājumam lejupielādē atbilstošo ZIP un aizstāj lietotni.

GitHub būvē un pārbauda Apple Silicon un Intel versijas atsevišķi, tostarp palaiž gatavās lietotnes pašpārbaudi un pārbauda arhīva noklusējuma iestatījumus. Reāla Keychain piekļuve, printera druka un palaišana pēc pieteikšanās vēl jāpārbauda lietotāja Mac datorā.

Palaišanai no pirmkoda instalē Python 3.12 ar Tkinter, atkarības no `requirements-build.txt` un palaid `python3 logistra_gui.py`. Būvēšanai palaid `python3 build_app.py`.
