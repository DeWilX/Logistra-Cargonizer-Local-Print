# Logistra macOS

Šī ir tā paša Logistra GUI macOS versija: API iestatījumi, printeru saraksts, PDF lejupielāde, testa druka, pādruka, sūtījumu uzskaite un fona pārbaudes.

Izvēlies savu instalēto printeri. Draiveris un drukas formāts jāpārbauda konkrētajā Mac datorā.

1. Instalē [Python 3.10+ no python.org](https://www.python.org/downloads/macos/) ar Tkinter. Adobe Reader vai SumatraPDF macOS versijai nav nepieciešams.
2. Atarhivē mapi stabilā vietā, piemēram, Documents/Logistra. Atver `Open-Logistra.command`. Ja Finder neļauj to palaist, Terminal šajā mapē izpildi `chmod +x Open-Logistra.command`, tad `./Open-Logistra.command`. Alternatīvi: `python3 logistra_gui.py`.
3. Cilnē **Iestatījumi** ievadi savu Sender ID un API atslēgu, saglabā un pārbaudi pieslēgumu. Atslēga glabājas macOS login Keychain, nevis konfigurācijā vai žurnālā. macOS var prasīt atļaut Python piekļuvi šim Keychain ierakstam. Windows DPAPI failu uz Mac pārnest nevar.
4. Cilnē **Printeris un pādruka** izvēlies macOS instalēto printeri un saglabā. Printeri jāpievieno System Settings → Printers & Scanners. Lietotne rāda CUPS rindas nosaukumus; neinstalētus printerus tā nemeklē tīklā.
5. Nospied **Izdrukāt PDF**, lai drukātu iekļauto **102 × 192 mm** testa etiķeti. Papīra izmēru iestati printera draiverī. Druka izmanto macOS `lp`, vienu kopiju un `print-scaling=none`; faktiskais draivera rezultāts jāpārbauda fiziski. Sekmīga nosūtīšana rindai nenozīmē, ka printeris jau izdrukājis.

Jaunu sūtījumu meklēšanas pārbaude joprojām nepieciešama ar reālu jaunu `open` sūtījumu. Automātika noklusējumā izslēgta. Pēc saraksta pārbaudes un testa drukas: apstiprini saraksta pārbaudi, saglabā, saglabā sākuma atskaiti, izvēlies automātisko druku, saglabā un palaid. Daudzlapu sarakstu apstrāde vēl nav ieviesta.

Minimizēts logs turpina strādāt fonā. Aizverot logu, automātika apstājas pēc pašreizējās darbības pabeigšanas. Mac datoram jābūt ieslēgtam un nedrīkst gulēt. Automātiska palaišana pēc pieteikšanās saglabā lietotāja `~/Library/LaunchAgents/app.logistra.print.plist`; tā stājas spēkā nākamajā pieteikšanās reizē. Noņemot šo izvēli un saglabājot, fails tiek dzēsts. Ja aģents jau ielādēts pašreizējā sesijā, to izkrauj ar `launchctl bootout gui/$(id -u)/app.logistra.print` vai izraksties un piesakies vēlreiz. Lietotnes mapi pēc autostart iestatīšanas nepārvieto; ja pārvieto, iestatījumu saglabā vēlreiz.

Pādrukai izvēlies saglabātu sūtījuma ID vai ievadi ID manuāli. Lokāli saglabāta etiķete neprasa API piekļuvi. Pādruka ir viena papildu kopija un nemaina automātiskās drukas uzskaiti. Pirms tās pārbaudi printera rindu.

Žurnāls: `data/gui.log`. Atslēga nav žurnālā. PDF un apstrādes SQLite datubāze glabājas programmas `data` mapē. Dažādiem datoriem ir atsevišķa uzskaite: vienam Sender ID automātiku vienlaikus darbini tikai vienā datorā, citādi abi var izdrukāt to pašu etiķeti.

Lokālie testi pārbauda CUPS komandu, saraksta parsēšanu, Keychain saglabāšanas izsaukumu un LaunchAgent konfigurāciju. Reāla Keychain piekļuve, GUI, palaišana pēc pieteikšanās un fiziskā printera druka vēl jātestē lietotāja Mac datorā.

Avoti: [CUPS drukas komandas](https://www.cups.org/doc/options.html), [Python GUI uz macOS](https://docs.python.org/3/using/mac.html), [Apple Keychain](https://developer.apple.com/documentation/security/keychain-items), [Apple LaunchAgents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
