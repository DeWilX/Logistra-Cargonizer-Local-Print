"""Per-window UI translations; internal filter values and API data stay unchanged."""
import re
import tkinter as tk
from tkinter import ttk

LANGUAGES = {'lv': 'Latviešu', 'en': 'English', 'nb': 'Norsk bokmål'}
CATALOG = '''Sākums|Home|Hjem
Cargonizer sūtījumi|Cargonizer shipments|Cargonizer sendinger
Printeris un PDF|Printer and PDF|Skriver og PDF
Iestatījumi|Settings|Innstillinger
Darbību žurnāls|Activity log|Aktivitetslogg
Konts|Account|Konto
Printeris|Printer|Skriver
Sūtījumi|Shipments|Sendinger
Pirmā iestatīšana|Initial setup|Førstegangsoppsett
1. Pieslēgt kontu|1. Connect account|1. Koble til konto
2. Izvēlēties printeri|2. Choose printer|2. Velg skriver
3. Pārbaudīt jaunu sūtījumu|3. Check new shipment|3. Kontroller ny sending
Apstiprināt manuāli|Dismiss setup|Lukk oppsett
Aizvērt pirmo iestatīšanu|Dismiss initial setup|Lukk førstegangsoppsett
Palaist automātiku|Start automation|Start automatikk
Apturēt|Stop|Stopp
Automātiski drukāt jaunās etiķetes (izslēgts = tikai saglabāt PDF)|Automatically print new labels (off = save PDF only)|Skriv ut nye etiketter automatisk (av = bare lagre PDF)
Etiķete vai pādruka|Label or reprint|Etikett eller ny utskrift
Sūtījuma ID vai ref. / order numurs (piemēram, ORD-123456789)|Shipment ID or reference / order number (e.g. ORD-123456789)|Sendings-ID eller referanse / ordrenummer (f.eks. ORD-123456789)
Meklēt|Search|Søk
Lejupielādēt PDF|Download PDF|Last ned PDF
Pādrukāt etiķeti|Reprint label|Skriv ut etikett på nytt
Atvērt PDF mapi|Open PDF folder|Åpne PDF-mappe
Pēdējie sūtījumi|Recent shipments|Siste sendinger
Sūtījums|Shipment|Sending
Statuss|Status|Status
Izvēlies sūtījumu un nospied “Pādrukāt etiķeti”. Pādruka ir viena papildu kopija.|Select a shipment and click “Reprint label”. This prints one additional copy.|Velg en sending og klikk «Skriv ut etikett på nytt». Dette skriver ut én ekstra kopi.
Savienojums ar Cargonizer|Cargonizer connection|Tilkobling til Cargonizer
API atslēga|API key|API-nøkkel
API atslēgu atrodi Cargonizer iestatījumos. Tukšs lauks saglabā esošo atslēgu.|Find the API key in Cargonizer settings. Leave blank to keep the saved key.|Finn API-nøkkelen i Cargonizer-innstillingene. La feltet være tomt for å beholde lagret nøkkel.
Saglabāt un pārbaudīt|Save and verify|Lagre og kontroller
Palaist pēc Windows pieteikšanās (system tray)|Start at Windows sign-in (system tray)|Start ved Windows-pålogging (systemstatusfelt)
Aizverot logu, turpināt system tray|Keep running in the system tray when closing the window|Fortsett i systemstatusfeltet når vinduet lukkes
Izvēle saglabājas uzreiz. Lai izietu, tray ikonas izvēlnē izvēlies “Aizvērt”.|Saved immediately. To quit, choose “Exit” from the tray menu.|Lagres umiddelbart. Velg «Avslutt» i menyen i systemstatusfeltet for å avslutte.
Tēma:|Theme:|Tema:
Sistēmas tēma|System theme|Systemtema
Gaišs|Light|Lyst
Tumšs|Dark|Mørkt
Valoda:|Language:|Språk:
PDF saglabāšanas mape:|PDF save folder:|Mappe for PDF-filer:
Izvēlēties mapi|Choose folder|Velg mappe
Izvēle saglabājas uzreiz. Esošie PDF tiek nokopēti jaunajā mapē.|Saved immediately. Existing PDFs are copied to the new folder.|Lagres umiddelbart. Eksisterende PDF-filer kopieres til den nye mappen.
Papildu iestatījumi|Advanced settings|Avanserte innstillinger
API saraksta ceļš|API list path|API-sti for liste
Intervāls sekundēs|Interval in seconds|Intervall i sekunder
Minimālais pārbaudes intervāls: 5 sekundes.|Minimum check interval: 5 seconds.|Minste kontrollintervall: 5 sekunder.
Tikai saglabāt PDF (bez automātiskas drukas)|Only save PDF (no automatic printing)|Bare lagre PDF (ingen automatisk utskrift)
Saglabāt iestatījumus|Save settings|Lagre innstillinger
Datoram jāpaliek ieslēgtam. Ja ieslēgta turpināšana system tray, loga aizvēršana neaptur automātiku.|Keep the computer on. Closing the window does not stop automation when running in the system tray is enabled.|Datamaskinen må være på. Automatikken fortsetter når vinduet lukkes hvis kjøring i systemstatusfeltet er aktivert.
Sūtījumi no Cargonizer|Shipments from Cargonizer|Sendinger fra Cargonizer
Visi|All|Alle
Atvērtie|Open|Åpne
Nosūtītie|Transferred|Overført
Visi pārvadātāji|All carriers|Alle transportører
Periods|Period|Periode
Šodien|Today|I dag
Pēdējās 7 dienas|Last 7 days|Siste 7 dager
Pēdējās 30 dienas|Last 30 days|Siste 30 dager
Šonedēļ|This week|Denne uken
Pagājušajā nedēļā|Last week|Forrige uke
Šomēnes|This month|Denne måneden
Pagājušajā mēnesī|Last month|Forrige måned
Šogad|This year|Dette året
Pagājušajā gadā|Last year|Forrige år
Visi datumi|All dates|Alle datoer
Pielāgots periods|Custom period|Egendefinert periode
No|From|Fra
Līdz|To|Til
Filtrēt|Filter|Filtrer
Notīrīt filtrus|Clear filters|Fjern filtre
Ielādēt sūtījumus|Load shipments|Last inn sendinger
PDF / Druka|PDF / Print|PDF / Utskrift
Saņēmējs|Recipient|Mottaker
Adrese|Address|Adresse
Pārvadātājs|Carrier|Transportør
Produkts|Product|Produkt
Ref.|Ref.|Ref.
Pakas|Packages|Kolli
Datums|Date|Dato
Sūtījuma numurs|Shipment number|Sendingsnummer
Nosūtīts|Transferred|Overført
Atvērts|Open|Åpen
Ctrl: atlasīt atsevišķus sūtījumus. Shift: atlasīt rindu diapazonu. Datumi: dd.mm.gggg. Ielāde neko nedrukā.|Ctrl: select individual shipments. Shift: select a range. Dates: dd.mm.yyyy. Loading does not print.|Ctrl: velg enkelte sendinger. Shift: velg et område. Datoer: dd.mm.åååå. Innlasting skriver ikke ut.
Izvēlies datumu|Choose date|Velg dato
Notīrīt|Clear|Fjern
Janvāris|January|Januar
Februāris|February|Februar
Marts|March|Mars
Aprīlis|April|April
Maijs|May|Mai
Jūnijs|June|Juni
Jūlijs|July|Juli
Augusts|August|August
Septembris|September|September
Oktobris|October|Oktober
Novembris|November|November
Decembris|December|Desember
Pr|Mo|Ma
Ot|Tu|Ti
Tr|We|On
Ce|Th|To
Pk|Fr|Fr
Se|Sa|Lø
Sv|Su|Sø
Printeris un PDF testa druka|Printer and PDF test print|Skriver og PDF-testutskrift
Izvēlies printeri un spied “Izdrukāt PDF”. Iebūvēta testa lapa: 102 × 192 mm.|Choose a printer and click “Print PDF”. Built-in test page: 102 × 192 mm.|Velg skriver og klikk «Skriv ut PDF». Innebygd testside: 102 × 192 mm.
PDF drukāšanas programma (Adobe: Acrobat.exe vai AcroRd32.exe)|PDF printing program (Adobe: Acrobat.exe or AcroRd32.exe)|PDF-utskriftsprogram (Adobe: Acrobat.exe eller AcroRd32.exe)
Atsvaidzināt|Refresh|Oppdater
Atsvaidzināt printerus|Refresh printers|Oppdater skrivere
Saglabāt printeri|Save printer|Lagre skriver
Izdrukāt PDF|Print PDF|Skriv ut PDF
Izvēlēties EXE|Choose EXE|Velg EXE
Pādrukāt etiķeti — izvēlies saglabātu ID vai ievadi sūtījuma ID|Reprint label — choose a saved ID or enter a shipment ID|Skriv ut etikett på nytt — velg lagret ID eller angi sendings-ID
Katra pādruka izdrukā vēl vienu kopiju. Microsoft Print to PDF vietā saglabā oriģinālā PDF kopiju izvēlētajā mapē; printera pārbaude netiek veikta.|Each reprint creates one more copy. Microsoft Print to PDF saves the original PDF to your chosen folder; it does not verify a physical printer.|Hver ny utskrift lager én ekstra kopi. Microsoft Print to PDF lagrer original PDF i valgt mappe; det kontrollerer ikke en fysisk skriver.
Adobe: pirms testa iestati Actual size / 100% un vienu kopiju Reader drukas logā. Papīra izmēru iestati draiverī.|Adobe: select Actual size / 100% and one copy in Reader before testing. Set paper size in the printer driver.|Adobe: velg Actual size / 100% og én kopi i Reader før testen. Angi papirstørrelse i skriverdriveren.
Drukāšanas režīms: |Print backend: |Utskriftsmetode:
Pabeidz pirmo iestatīšanu|Complete initial setup|Fullfør førstegangsoppsett
Iestatījumi jāpārbauda|Settings need verification|Innstillingene må kontrolleres
Gatavs drukāšanai|Ready to print|Klar til utskrift
Automātiskā druka darbojas|Automatic printing is running|Automatisk utskrift kjører
PDF lejupielāde darbojas|PDF download is running|PDF-nedlasting kjører
nav iestatīts|not configured|ikke konfigurert
Konts pieslēgts|Account connected|Konto tilkoblet
Printeris apstiprināts|Printer verified|Skriver kontrollert
Sūtījumu ielāde apstiprināta|Shipment loading verified|Innlasting av sendinger kontrollert
Nav pārbaudīts: |Not verified: |Ikke kontrollert:
Printeris: |Printer: |Skriver:
Konts: |Account: |Konto:
Iestatījumi saglabāti.|Settings saved.|Innstillingene er lagret.
Pirmās iestatīšanas bloks paslēpts.|Initial setup dismissed.|Førstegangsoppsett er lukket.
Kļūda: |Error: |Feil:
Ielādē sūtījumus…|Loading shipments…|Laster inn sendinger…
Pārrēķina filtrus…|Updating filters…|Oppdaterer filtre…
Vispirms izvēlies sūtījumu tabulā.|Select a shipment in the table first.|Velg først en sending i tabellen.
Izvēlēties|Select|Velg
Izvēlies order sūtījumu|Choose order shipment|Velg sending for ordren
Atvērt Logistra Print|Open Logistra Print|Åpne Logistra Print
Aizvērt|Exit|Avslutt
Pādrukāt etiķeti?|Reprint label?|Skriv ut etikett på nytt?
Tas izdrukās vienu papildu kopiju. Vai iepriekšējais darbs vairs negaida printera rindā?|This prints one additional copy. Has the previous job left the printer queue?|Dette skriver ut én ekstra kopi. Er den forrige jobben borte fra skriverkøen?
Pārbaudi testa etiķeti|Check test label|Kontroller testetikett
Vai etiķete fiziski izdrukājās pareizajā izmērā un svītrkodi nav nogriezti?|Did the physical label print at the correct size with complete barcodes?|Ble den fysiske etiketten skrevet ut i riktig størrelse med hele strekkoder?
Nederīgs datumu diapazons: ievadi dd.mm.gggg; sākums nedrīkst būt pēc beigām.|Invalid date range: use dd.mm.yyyy; start must not follow end.|Ugyldig datointervall: bruk dd.mm.åååå; fra-dato må ikke være etter til-dato.
Filtrs nav piemērots. Izlabo datumu vai nospied “Notīrīt filtrus”.|Filter not applied. Correct the date or click “Clear filters”.|Filteret er ikke brukt. Rett datoen eller klikk «Fjern filtre».
Sāksim ar pieslēguma pārbaudi|Start by checking the connection|Start med å kontrollere tilkoblingen
Izpildi trīs soļus zemāk. Iestatījumi saglabājas šajā datorā.|Complete the three steps below. Settings are saved on this computer.|Fullfør de tre trinnene nedenfor. Innstillingene lagres på denne datamaskinen.
Esošs pirms palaišanas|Existing before start|Eksisterte før oppstart
PDF lejupielādēts|PDF downloaded|PDF lastet ned
Nosūtīts drukas rindai|Sent to print queue|Sendt til skriverkø
Drukas rezultāts jāpārbauda|Print result needs checking|Utskriftsresultatet må kontrolleres
Neskaidra druka — jāpārbauda|Uncertain print — check result|Usikker utskrift — kontroller resultatet
Ielādē sūtījumus no Cargonizer. Izvēlētais sūtījums būs pieejams PDF lejupielādei un pādrukai.|Load shipments from Cargonizer. Select a shipment to download or reprint its label.|Last inn sendinger fra Cargonizer. Velg en sending for å laste ned eller skrive ut etiketten på nytt.
Filtri attiecas uz ielādētajiem sūtījumiem un to izveides datumu.|Filters apply to loaded shipments and their creation dates.|Filtre gjelder innlastede sendinger og opprettelsesdatoene deres.
Izveides datuma filtrs: |Creation date filter: |Filter for opprettelsesdato:
Ielādēto sūtījumu datumi: |Loaded shipment dates: |Datoer for innlastede sendinger:
bez sākuma|no start date|ingen fra-dato
bez beigām|no end date|ingen til-dato
Periods mainīts — nospied “Filtrēt” vai “Ielādēt sūtījumus”, lai ielādētu tā vēsturi.|Period changed — click “Filter” or “Load shipments” to load its history.|Perioden er endret — klikk «Filtrer» eller «Last inn sendinger» for å laste inn historikken.
Visas izvēlētā perioda lapas ielādētas.|All pages for the selected period are loaded.|Alle sider for valgt periode er lastet inn.
Izvēlies sūtījumu, lai lejupielādētu vai pādrukātu etiķeti.|Select a shipment to download or reprint its label.|Velg en sending for å laste ned eller skrive ut etiketten på nytt.
Ielāde neizdevās: |Loading failed: |Innlasting mislyktes:
Ievadi sūtījuma ID vai ref. / order numuru.|Enter a shipment ID or reference / order number.|Angi sendings-ID eller referanse / ordrenummer.
Ievadi sūtījuma ID vai izvēlies sūtījumu tabulā.|Enter a shipment ID or select a shipment in the table.|Angi sendings-ID eller velg en sending i tabellen.
Vispirms apturi automātiku.|Stop automation first.|Stopp automatikken først.
Apturi automātiku pirms iestatījumu maiņas.|Stop automation before changing settings.|Stopp automatikken før du endrer innstillingene.
Veic testa druku un apstiprini printera rezultātu.|Print a test label and confirm the printer result.|Skriv ut en testetikett og bekreft resultatet.
Pabeidz konta pieslēgšanu un jaunā sūtījuma pārbaudi.|Complete the account connection and new shipment check.|Fullfør kontotilkoblingen og kontrollen av en ny sending.
Printeris pārbaudīts un saglabāts.|Printer verified and saved.|Skriver kontrollert og lagret.
Pārbaudi papīra izmēru, printera rindu un atkārto testa druku.|Check paper size and printer queue, then repeat the test print.|Kontroller papirstørrelse og skriverkø, og gjenta testutskriften.
Oriģinālā PDF kopija saglabāta izvēlētajā mapē. Druka nav veikta.|Original PDF saved to the chosen folder. Nothing was printed.|Original PDF er lagret i valgt mappe. Ingen utskrift er utført.
Oriģinālā PDF kopija saglabāta izvēlētajā mapē. Druka nav veikta; fiziskais printeris nav apstiprināts.|Original PDF saved to the chosen folder. Nothing was printed; the physical printer is not verified.|Original PDF er lagret i valgt mappe. Ingen utskrift er utført; den fysiske skriveren er ikke kontrollert.
PDF nosūtīts drukas rindai. Pārbaudi fizisko etiķeti. Atkārtots klikšķis drukās vēl vienu kopiju.|PDF sent to the print queue. Check the physical label. Clicking again prints another copy.|PDF er sendt til skriverkøen. Kontroller den fysiske etiketten. Et nytt klikk skriver ut en ekstra kopi.
Izvēlies PDF saglabāšanas mapi|Choose PDF save folder|Velg mappe for PDF-filer
Saglabāt PDF|Save PDF|Lagre PDF
Izvēlies PDF drukāšanas programmu|Choose PDF printing program|Velg PDF-utskriftsprogram
Printeri nav atrasti. Instalē printera draiveri un atsvaidzini sarakstu.|No printers found. Install the printer driver and refresh the list.|Ingen skrivere funnet. Installer skriverdriveren og oppdater listen.
Printeris saglabāts. Ja fona skripts jau darbojas, restartē to, lai lietotu jauno izvēli.|Printer saved. Restart the background worker to use the new selection.|Skriver lagret. Start bakgrunnsjobben på nytt for å bruke det nye valget.
Saglabā testa PDF…|Saving test PDF…|Lagrer test-PDF…
Atjauninājumi|Updates|Oppdateringer
Versija: |Version: |Versjon:
GitHub repozitorijs (owner/repo):|GitHub repository (owner/repo):|GitHub-repositorium (owner/repo):
Pārbaudīt atjauninājumus palaižot|Check for updates on launch|Se etter oppdateringer ved oppstart
Pārbaudīt atjauninājumus|Check for updates|Se etter oppdateringer
Lejupielādēt un atjaunināt|Download and update|Last ned og oppdater
Atjauninājumi no publiska GitHub repozitorija. Iestatījumi saglabājas.|Updates from a public GitHub repository. Your settings are preserved.|Oppdateringer fra et offentlig GitHub-repositorium. Innstillingene beholdes.
Norādi GitHub repozitoriju.|Enter the GitHub repository.|Angi GitHub-repositoriet.
Pārbauda GitHub Releases…|Checking GitHub Releases…|Kontrollerer GitHub Releases…
Atjauninājumu pārbaude neizdevās: |Update check failed: |Kontroll av oppdateringer mislyktes:
Pieejama jauna versija: |New version available: |Ny versjon tilgjengelig:
Jau lieto jaunāko versiju.|You are using the latest version.|Du bruker den nyeste versjonen.
Automātiska EXE aizstāšana pieejama Windows EXE versijā.|Automatic EXE replacement is available in the Windows EXE version.|Automatisk utskifting av EXE er tilgjengelig i Windows EXE-versjonen.
Lejupielādē un pārbauda atjauninājumu…|Downloading and verifying update…|Laster ned og kontrollerer oppdatering…
Atjauninājums pārbaudīts. Sagaida pašreizējās darbības un pārstartē lietotni.|Update verified. Waiting for current work, then restarting the app.|Oppdatering kontrollert. Venter på pågående arbeid og starter deretter appen på nytt.
GitHub laidieni vēl nav publicēti vai repozitorijs nav publisks.|No GitHub releases have been published, or the repository is not public.|Ingen GitHub-utgivelser er publisert, eller repositoriet er ikke offentlig.'''
TRANSLATIONS = {language: {} for language in LANGUAGES}
for line in CATALOG.splitlines():
    original, english, norwegian = line.split('|')
    if original.endswith(' ') and not norwegian.endswith(' '):
        norwegian += ' '
    for language, value in [('lv', original), ('en', english), ('nb', norwegian)]:
        TRANSLATIONS[language][original] = value


class Locale:
    def __init__(self, language='lv'):
        self.language = language if language in LANGUAGES else 'lv'
        self.refreshers = []

    def translate(self, value):
        if not isinstance(value, str) or self.language == 'lv':
            return value
        catalog = TRANSLATIONS[self.language]
        if value in catalog:
            return catalog[value]
        match = re.fullmatch(r'Pārbaude ik pēc (\d+) sekundēm', value)
        if match:
            return ('Check every {} seconds' if self.language == 'en' else 'Kontroll hvert {}. sekund').format(match[1])
        templates = [
            (r'Rāda (\d+) no (\d+)', 'Showing {} of {}', 'Viser {} av {}'),
            (r'No Cargonizer ielādēti (\d+) sūtījumi. Nekas netika izdrukāts.', '{} shipments loaded from Cargonizer. Nothing was printed.', '{} sendinger lastet inn fra Cargonizer. Ingen utskrift er utført.'),
            (r'Atrasti (\d+) printeri. Izvēlies vajadzīgo.', '{} printers found. Choose a printer.', '{} skrivere funnet. Velg en skriver.'),
        ]
        for expression, english, norwegian in templates:
            value = re.sub(expression, lambda match: (english if self.language == 'en' else norwegian).format(*match.groups()), value)
        # Only whole words/phrases are translated; names, references and dates are retained.
        pattern = '|'.join(re.escape(key) for key in sorted(catalog, key=len, reverse=True) if len(key) >= 4)
        return re.sub(r'(?<!\w)(?:' + pattern + r')(?!\w)', lambda match: catalog[match[0]], value)

    def set_language(self, language):
        self.language = language
        for refresh in list(self.refreshers):
            try:
                refresh()
            except tk.TclError:
                pass


def locale_for(widget):
    while widget is not None:
        if hasattr(widget, '_logistra_locale'):
            return widget._logistra_locale
        widget = getattr(widget, 'master', None)
    return None


def translate(widget, value):
    locale = locale_for(widget)
    return locale.translate(value) if locale else value


def install_widgets():
    if getattr(ttk, '_logistra_localized', False):
        return
    ttk._logistra_localized = True
    class Localized:
        def __init__(self, master=None, **kwargs):
            self._locale = locale_for(master)
            self._original_text = kwargs.get('text')
            self._original_values = kwargs.get('values')
            self._headings = {}
            self._mirrors = []
            if self._locale:
                if 'text' in kwargs:
                    kwargs['text'] = self._locale.translate(kwargs['text'])
                if 'values' in kwargs:
                    kwargs['values'] = [self._locale.translate(value) for value in kwargs['values']]
                model = kwargs.get('textvariable')
                if isinstance(model, tk.Variable):
                    display = tk.StringVar(master=master, value=self._locale.translate(model.get()))
                    busy = [False]
                    def refresh(*_):
                        if not busy[0]:
                            busy[0] = True
                            try:
                                display.set(self._locale.translate(model.get()))
                            finally:
                                busy[0] = False
                    def changed(*_):
                        if not busy[0] and self._original_values is not None:
                            busy[0] = True
                            try:
                                value = display.get()
                                original = next((item for item in self._original_values if self._locale.translate(item) == value), value)
                                model.set(original)
                            finally:
                                busy[0] = False
                    model.trace_add('write', refresh)
                    display.trace_add('write', changed)
                    kwargs['textvariable'] = display
                    self._mirrors.append((model, display, refresh, changed))
                    self._locale.refreshers.append(refresh)
            super().__init__(master, **kwargs)
            if self._locale:
                self._locale.refreshers.append(self._refresh_language)

        def _refresh_language(self):
            values = {}
            if self._original_text is not None:
                values['text'] = self._locale.translate(self._original_text)
            if self._original_values is not None:
                values['values'] = [self._locale.translate(value) for value in self._original_values]
            if values:
                super().configure(**values)
            for column, original in self._headings.items():
                super().heading(column, text=self._locale.translate(original))

        def configure(self, cnf=None, **kwargs):
            if self._locale:
                if 'text' in kwargs:
                    self._original_text = kwargs['text']
                    kwargs['text'] = self._locale.translate(kwargs['text'])
                if 'values' in kwargs:
                    self._original_values = kwargs['values']
                    kwargs['values'] = [self._locale.translate(value) for value in kwargs['values']]
            return super().configure(cnf, **kwargs)
        config = configure

        def __setitem__(self, key, value):
            self.configure(**{key: value})

        def heading(self, column, option=None, **kwargs):
            if self._locale and 'text' in kwargs:
                self._headings[column] = kwargs['text']
                kwargs['text'] = self._locale.translate(kwargs['text'])
            return super().heading(column, option, **kwargs)

    for name in ('Label', 'Button', 'Checkbutton', 'Radiobutton', 'Labelframe', 'LabelFrame', 'Combobox', 'Treeview'):
        original = getattr(ttk, name)
        setattr(ttk, name, type(name, (Localized, original), {}))
    from tkinter import commondialog
    original_show = commondialog.Dialog.show
    def show(dialog, **options):
        master = dialog.master or tk._default_root
        for key in ('title', 'message', 'detail'):
            if key in dialog.options:
                dialog.options[key] = translate(master, dialog.options[key])
            if key in options:
                options[key] = translate(master, options[key])
        return original_show(dialog, **options)
    commondialog.Dialog.show = show
