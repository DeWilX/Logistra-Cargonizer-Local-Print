# Logistra Print macOS

GitHub Releases piedāvā gatavu lietotni abiem Mac procesoru veidiem:

- Apple Silicon (M1 un jaunāki): `Logistra-macOS-arm64.zip`.
- Intel: `Logistra-macOS-x86_64.zip`.

Izpako atbilstošo ZIP un pārvieto `Logistra.app` uz Applications. Python ir iekļauts.

## Pirmā palaišana un macOS drošības brīdinājums

Lietotne pašlaik nav parakstīta ar Apple Developer ID sertifikātu vai notarizēta. Tāpēc macOS var ziņot, ka nevar pārbaudīt izstrādātāju vai pārliecināties, ka lietotne nesatur kaitīgu programmatūru.

1. Lejupielādē lietotni no šī projekta [GitHub Releases](https://github.com/DeWilX/Logistra-Cargonizer-Local-Print/releases/latest) un mēģini atvērt `Applications/Logistra.app`.
2. Ja parādās nepārbaudīta izstrādātāja brīdinājums, aizver to un atver **Apple izvēlne → System Settings → Privacy & Security**.
3. Sadaļā **Security** pie `Logistra` nospied **Open Anyway**. Ievadi Mac paroli vai apstiprini ar Touch ID, ja nepieciešams.
4. Atkārtotajā dialogā nospied **Open**. Turpmāk lietotni atver no Applications.

Šī atļauja attiecas uz konkrēto lietotni. Nav jāizslēdz Gatekeeper visam datoram. Ja brīdinājums norāda uz atrastu kaitīgu programmatūru, bojātu vai modificētu lietotni, neizmanto šos soļus tā apiešanai; pārtrauc palaišanu un lejupielādē jaunu kopiju no laidieniem. [Apple instrukcija par drošu lietotņu atvēršanu](https://support.apple.com/102445).

## Atjaunināšana

Aizver veco Logistra kopiju, lejupielādē savam procesoram paredzēto jaunāko ZIP un aizstāj `Logistra.app` mapē Applications. Atver tieši šo kopiju un iestatījumos pārbaudi versijas numuru. Iestatījumi un drukāšanas vēsture saglabājas. Versijā 0.1.5 ir labota atjauninājumu pārbaudes SSL sertifikātu kļūda un pievienota rezerves pārbaude GitHub API limita gadījumā; repozitorija ievades lauks ir noņemts.

## Iestatīšana

Iestatījumos ievadi savu Sender ID un API atslēgu, saglabā un pārbaudi pieslēgumu. Nav iepriekš aizpildīta konta vai printera. Atslēga glabājas macOS login Keychain, nevis konfigurācijā vai žurnālā. Windows DPAPI failu uz Mac pārnest nevar.

Izvēlies printeri, kas pievienots System Settings → Printers & Scanners. Lietotne izmanto CUPS rindas un `lp`, vienu kopiju un `print-scaling=none`. Poga Testa print nosūta iekļauto 102 × 192 mm testa etiķeti; pirms drukāšanas pārbaudi draivera papīra izmēru. Sekmīga nosūtīšana rindai nenozīmē, ka etiķete fiziski izdrukāta.

Iestatījumi, žurnāls un SQLite uzskaite glabājas `~/Library/Application Support/Logistra`. PDF mapi var izvēlēties iestatījumos. Lietotnes aizstāšana ar jaunāku versiju saglabā šos datus. Vienam Sender ID automātisko druku vienlaikus darbini vienā datorā.

Minimizēts logs turpina darbu fonā. Mac datoram jābūt ieslēgtam un nedrīkst gulēt. Automātiska palaišana izmanto `~/Library/LaunchAgents/app.logistra.print.plist`. Windows system tray un automātiska EXE aizstāšana ir Windows funkcijas; Mac atjauninājumam lejupielādē atbilstošo ZIP un aizstāj lietotni.

GitHub būvē un pārbauda Apple Silicon un Intel versijas atsevišķi, tostarp palaiž gatavās lietotnes pašpārbaudi un pārbauda arhīva noklusējuma iestatījumus. Reāla Keychain piekļuve, printera druka un palaišana pēc pieteikšanās vēl jāpārbauda lietotāja Mac datorā.

Palaišanai no pirmkoda instalē Python 3.12 ar Tkinter, atkarības no `requirements-build.txt` un palaid `python3 logistra_gui.py`. Būvēšanai palaid `python3 build_app.py`.

## Atbalsts projektam

Izstrādātājs: **Gustavs Meijers**. Ja lietotne noder, vari atbalstīt tās attīstību ar [ziedojumu Ko-fi](https://ko-fi.com/gustavsm).

## Licence

No versijas 0.1.6 atļauta lietošana uzņēmumā, modificēšana un bezmaksas izplatīšana. Programmu vai tās modificētās versijas nedrīkst pārdot vai izplatīt par maksu bez autora rakstiskas atļaujas. Pilns teksts iekļauts failā LICENSE. Iepriekš ar MIT licenci izplatītās kopijas saglabā savas sākotnējās tiesības.
