"""Info / How to use page content (HTML), Romanian and English. One page per <h2> (InfoPage splits on it).
Every option is explained with its real numbers (owner: more text, but everything well explained). Keep RO and EN
in sync with the code when features change."""

RO = """
<h1>Cum se folosește MoneyMakingMachine</h1>
<p>Aplicația te ajută la fiecare pas al unei nunți, în ordinea din meniul din stânga:</p>
<ol>
<li><b>Descărcare carduri</b>: copiază toate cardurile deodată, verificate, în folderul nunții.</li>
<li><b>Creează proiectul</b>: pune toate filmările pe un timeline, cum le așezi tu pentru selecție, gata de importat în Premiere.</li>
<li><b>Selection &amp; Multicam</b>: <b>Footage Selection</b> alege singur cadrele bune din clipuri; <b>Multicam</b> sincronizează
camerele cu recorderul de la mixer și face montajul petrecerii.</li>
<li><b>Teaser Studio</b>: shortmovie-ul (teaser, pregătiri, biserică, sală, petrecere) pe muzica ta.</li>
<li><b>Long Film</b>: filmul lung până la petrecere, pre-montat din selecțiile tale.</li>
<li><b>Transcriere</b>: interviurile devin text; din interviurile mirilor, Claude face o singură poveste.</li>
</ol>
<p>Fiecare pagină din stânga a acestui Info explică o parte din aplicație, cu fiecare opțiune: ce face, cu ce cifre lucrează
și când merită s-o schimbi. Caută cu bara de sus (de exemplu „tremur”, „drop”, „vornic”).</p>
<p><b>Drag and drop</b>: pe orice pagină poți trage din Finder fișiere sau foldere în loc să le cauți cu butoanele: un XML din Premiere
e importat (selecții, sequence cu interviuri, timeline sincronizat), un folder sau clipuri sunt adăugate, la Creează proiectul folderul
nunții, la Descărcare carduri un folder de copiat (sau, tras peste destinație, destinația), la Teaser Studio XML-ul cu culori =
filmările, iar un fișier audio sau XML-ul montajului muzical = muzica.</p>
<p>Peste tot: notificarea <b>verde</b> = gata, <b>roșie</b> = ceva n-a mers (cu motivul). Aplicația nu modifică și nu șterge
niciodată filmările tale: doar le citește și scrie fișiere XML noi.</p>

<h2>Descărcare carduri</h2>
<p>Copiază cardurile pe disc, toate deodată, fiecare fișier verificat după copiere. De aici începe orice nuntă.</p>
<h3>Pașii</h3>
<ol>
<li><b>Introdu cardurile.</b> Apar singure în listă (la fiecare 3 secunde se uită după carduri noi), bifate. Discul intern
al Mac-ului și imaginile de disc (DMG) nu apar niciodată.</li>
<li><b>Nunta</b>: ziua, luna, anul și numele mirilor. Folderul se numește singur, ca la tine: „NUNTA 4 IULIE Alexandra si Vlad
2026” (în engleză: „WEDDING 4 JULY Alexandra and Vlad 2026”). Îl poți și scrie de mână.</li>
<li><b>Destinația</b>: discul pe care se face folderul nunții.</li>
<li>Bifezi opțiunile și apeși <b>Copiază cardurile bifate</b>. Toate cardurile se copiază în același timp (fiecare pe firul lui).</li>
</ol>
<h3>Ce vezi la fiecare card</h3>
<ul>
<li><b>Mărimea</b> cardului, <b>cât e folosit</b>, <b>tipul</b> (CFexpress, SD) și <b>viteza de citire</b> măsurată.</li>
<li><b>Camera recunoscută</b>: Sony scrie modelul în fișierele XML de lângă clipuri (FX6, FX3, A7 IV); RODE Wireless PRO
(fișiere „…_Wireless_PRO.WAV”) = lavalieră; Zoom / Tascam sau carduri cu mai ales WAV = recorder; DJI = dronă sau Osmo.</li>
<li><b>Folderul</b> în care merge: fx6, fx3, a74, osmo, recorder, lavaliere/lav 1 și lav 2 (pe rând, prima lavalieră lav 1, a doua
lav 2), drona. Îl schimbi din listă; <b>Alt folder…</b> îți dă un câmp în care scrii orice nume. <b>doar verific (backup)</b>
nu copiază cardul, doar îl compară cu copia geamănului lui.</li>
<li>Câte clipuri sunt <b>de la nunta asta</b> și câte rămân de la alte zile (vezi mai jos).</li>
</ul>
<h3>Doar ce s-a filmat la nunta asta (bifat implicit)</h3>
<p>Un card poate avea mai multe nunți (de exemplu cardul mare de FX6, neformatat într-un weekend cu trei nunți). Se copiază doar
clipurile filmate <b>de la data nunții, ora aleasă, până a doua zi la ora aleasă</b> (implicit 05:00 → 05:00), după ceasul camerei.
Restul rămân pe card. Fișierele de lângă clipuri (XML-urile Sony etc.) îl urmează pe clipul lor. Dacă la un card scrie 0 clipuri de
la nunta asta, verifică ceasul camerei sau intervalul orar.</p>
<h3>Opțiunile</h3>
<ul>
<li><b>Verifică fiecare fișier după copiere</b> (bifat): copia e citită înapoi de pe disc și comparată cu cardul printr-o sumă de
control (blake2b). Dacă nu se potrivesc, fișierul apare <b>EȘUAT</b>, în roșu. Durează puțin mai mult (încă o citire a copiei),
dar e singura garanție că fișierul de pe disc e bun.</li>
<li><b>Carduri de backup</b> (bifat): când o cameră înregistrează pe două carduri deodată, aplicația le recunoaște după numele,
mărimile și <b>conținutul</b> fișierelor (compară bucăți din cele mai mari 6 fișiere). Se potrivesc dacă 90% din cardul mai mic e
identic. Se copiază doar cardul cel mai rapid; celălalt e doar verificat față de copie, după ce aceasta s-a terminat. Dacă pe
backup există un clip care lipsește de pe primul card, e copiat de pe backup. Două lavaliere nu sunt niciodată luate drept backup
(au aceleași nume și mărimi, dar alt sunet).</li>
<li><b>Păstrează folderele de pe card</b> (bifat): structura cardului rămâne în folderul camerei (de exemplu fx6/XDROOT/Clip/…).
Debifat: toate fișierele ajung direct în folderul camerei.</li>
<li><b>Sari peste proxy-urile camerelor</b> (.LRF, .LRV, .THM): fișierele mici de previzualizare nu se copiază.</li>
<li><b>Scrie un raport lângă filmări</b> (bifat): _offload_report.txt, cu fiecare fișier, mărimea, suma de control și starea.</li>
<li><b>Scoate cardurile când totul e copiat</b>: le scoate (eject) când totul e copiat, ca să le poți lua imediat.</li>
</ul>
<h3>Siguranță</h3>
<ul>
<li>Cardurile sunt doar <b>citite</b>: nimic nu e schimbat, redenumit sau șters pe ele.</li>
<li>La destinație nu se suprascrie nimic: un fișier identic e recunoscut („deja acolo”), unul diferit cu același nume primește „ (2)”.</li>
<li>Fiecare copie se scrie întâi ca .part și primește numele adevărat abia când e completă: dacă oprești sau pică curentul, nu rămân
copii pe jumătate care să pară bune.</li>
<li>Datele fișierelor rămân cele de pe card (din ele se citește ordinea zilei mai târziu).</li>
</ul>

<h2>Creează proiectul (Premiere / DaVinci)</h2>
<p>După descărcarea cardurilor: toate filmările nunții pe un singur timeline, <b>cum le așezi tu pentru selecție</b> (măsurat pe
selecțiile tale de la 4 iulie și de la Mădălina &amp; Radu).</p>
<ol>
<li><b>Alege folderul</b> nunții. După Descărcare carduri e deja ales. Fiecare folder cu video e o cameră; dacă alegi un folder care
conține un singur folder cu camerele (de exemplu „Video”), aplicația intră singură în el.</li>
<li><b>Camerele</b> apar în ordinea ta: fx6, fx3, a74, osmo, apoi alte foldere necunoscute, apoi drona (drona, mavic, dji), iar
folderele „trash” / „gunoi” la final. <b>Tragi</b> o cameră ca să schimbi ordinea sau o <b>debifezi</b> ca s-o lași afară. Sub listă
vezi folderele doar cu sunet (recorder, lavaliere): rămân afară, ca în selecțiile tale.</li>
<li><b>Numele sequence-ului</b>: implicit „selectie”.</li>
<li><b>Creează XML-ul.</b> Aplicația citește fiecare clip (câteva deodată) și face timeline-ul.</li>
</ol>
<h3>Cum arată timeline-ul</h3>
<ul>
<li>O cameră după alta pe <b>V1</b>, cu <b>10 secunde libere</b> între camere (vezi unde începe fiecare).</li>
<li>Clipurile fiecărei camere <b>în ordinea în care au fost filmate</b>: după ceasul camerei din fișier, dacă toate clipurile camerei
îl au; altfel după data fișierului (copiile o păstrează). Dacă două sunt egale, după nume. Numerotarea care o ia de la capăt
(C9999 → C0001) nu încurcă ordinea.</li>
<li>Fiecare clip <b>întreg</b>, cu <b>tot sunetul lui</b>: canalul 1 pe A1, canalul 2 pe A2 etc. (FX6: 4 canale pe A1–A4, celelalte
camere A1–A2, drona fără sunet), sunetul legat de imagine.</li>
<li>Sequence 25 fps, mărimea camerei principale (la tine 1920×1080).</li>
<li>Proxy-urile (SUB/…S03, foldere PROXY, .LRF) și fișierele XML de lângă clipuri nu intră.</li>
</ul>
<h3>Cum îl pui în proiect</h3>
<p>XML-ul se salvează în folderul nunții („NUNTA … - selectie.xml”; dacă există, primește „ (2)”). <b>Arată în Finder</b> deschide
folderul cu XML-ul selectat. <b>Premiere Pro</b>: cu proiectul tău deschis, tragi XML-ul în panoul Project (sau File &gt; Import):
apare un sequence nou cu toate clipurile, plus un bin cu ele. <b>DaVinci Resolve</b>: File &gt; Import &gt; Timeline. Aplicația nu poate
apăsa singură butoane în Premiere, deci importul e un singur drag.</p>

<h2>Footage Selection: cum alege cadrele</h2>
<p>Un proiect Footage Selection se uită la fiecare clip și păstrează (sau notează) părțile bune. Apoi exportă un XML pe care îl
deschizi în Premiere sau DaVinci.</p>
<h3>Clipurile</h3>
<ul>
<li><b>Adaugă folder</b> sau tragi fișiere / foldere în listă. Fișierele auxiliare (XML-urile Sony, poze, proxy-uri) sunt ignorate.</li>
<li><b>Import XML</b>: clipurile unui timeline din Premiere / DaVinci (de exemplu XML-ul din <b>Creează proiectul</b>) intră în
listă <b>în ordinea de pe timeline</b>. Analiza și exportul păstrează ordinea asta. Clipurile care nu sunt pe acest calculator
sunt sărite (îți spune câte).</li>
<li>Selectezi clipuri în listă și apeși Delete ca să le scoți.</li>
</ul>
<h3>Ce măsoară analiza</h3>
<p><b>Analizează filmările</b> (Analyze Footage) citește video-ul cu FFmpeg (orice format, inclusiv MXF): <b>8 cadre pe secundă</b>, micșorate la
320×180 și alb-negru (destul ca să judece calitatea, de multe ori mai rapid). Pe fiecare cadru măsoară:</p>
<ul>
<li><b>Claritatea</b> (focus): câte detalii fine are imaginea. Un cadru neclar are foarte puține.</li>
<li><b>Expunerea</b>: luminozitatea medie (pe o scară 0–255) sub 45 = prea întunecat, peste 210 = prea luminos; plus partea de
imagine „arsă” (aproape albă): peste 15% din cadru e penalizat.</li>
<li><b>Contrastul</b>: imagine spălată (contrast mic) sau prea dură (contrast foarte mare); la mijloc e ideal.</li>
<li><b>Mișcarea camerei</b>: cât s-a mutat imaginea față de cadrul anterior. Din asta se văd <b>smuciturile</b> (tremurat) și
<b>mutările rapide</b> de la un om la altul.</li>
<li><b>Activitatea</b> din cadru: cât se schimbă imaginea (oameni care se mișcă) și cât de clar e centrul. Asta e „Visual Importance”.</li>
</ul>
<p>Analiza se face <b>o singură dată</b>. După ea, orice slider sau comutator doar recalculează pe datele deja măsurate, deci
rezultatul se schimbă instant. Rezultatele vechi rămân în <b>Istoric</b> (dreapta), ca să le redeschizi.</p>
<p>Ecranul de analiză: sus clipurile analizate chiar acum, la mijloc progresul (pauză / Anulează), jos cele terminate. Analiza merge
și în fundal: revii din Coada de analiză &gt; Deschide sau din proiect cu Vezi analiza.</p>

<h3>Modul Auto: cum dă nota</h3>
<p>Auto e varianta clasică: păstrează doar ce e bun și pune totul pe <b>o singură pistă</b>, cadrele unul după altul. Programul ia
fiecare secundă din clip și notează trei lucruri, fiecare de la 0 la 100%:</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Criteriu</th><th>Pondere</th></tr>
<tr><td>Claritate (focus)</td><td>40%</td></tr>
<tr><td>Stabilitate (tremurat)</td><td>30%</td></tr>
<tr><td>Expunere</td><td>30%</td></tr>
</table>
<p>Apoi nota finală (0–100) = <b>60% media de mai sus + 40% criteriul cel mai slab</b> dintre cele trei. Așa, un singur defect mare
(foarte tremurat, foarte întunecat sau foarte neclar) trage nota în jos, chiar dacă celelalte sunt perfecte.</p>
<h3>Cum se măsoară tremuratul</h3>
<p>Contează <b>smuciturile</b>, nu mișcarea în sine. O panoramare lină sau un gimbal care se plimbă uniform iau notă bună la
stabilitate; tremuratul de mână și zguduiturile scad nota. Aplicația compară mișcarea imaginii între două măsurători (de 8 ori pe
secundă):</p>
<ul>
<li>smucituri foarte mici (sub ~0,5% din lățimea cadrului) → stabilitate <b>100%</b>, nu se penalizează deloc;</li>
<li>smucituri medii (~1,7% din lățime) → <b>50%</b>;</li>
<li>smucituri mari (~3% din lățime sau mai mult) → <b>0%</b>.</li>
</ul>
<h3>Reglajele din Auto</h3>
<ol>
<li><b>Pragul de selecție</b> (Selection threshold; 20–90, implicit 60): se păstrează doar secundele cu nota cel puțin egală cu
pragul. Exemple la pragul 60: un cadru clar și bine expus poate avea stabilitatea până la ~31% și tot rămâne; dacă focusul e doar
70%, stabilitatea trebuie să fie de cel puțin ~43%.</li>
<li><b>Scoate mișcările de cameră</b> (Cut out camera moves; pornit): când muți camera de la un om la altul mai repede de ~20% din cadru pe secundă (sau toată
imaginea se schimbă deodată, ca la o panoramare bruscă), mișcarea se taie și fiecare om devine cadru separat. Exemplu: 3 oameni
filmați câte 2 s, cu mutări între ei = 3 cadre. Panoramările lente nu sunt tăiate. Oprit: mișcările rămân în cadru dacă au notă bună.</li>
<li><b>Lungimea minimă a tăieturii</b> (Minimum cut length; 1–10 s, implicit 3 s): în Auto, cadrele păstrate mai scurte de atât sunt aruncate.</li>
</ol>
<h3>Ca să scoți maximum din Auto</h3>
<ul>
<li><b>Party filmat din mână</b>: prag <b>50–55</b>; altfel aruncă prea mult.</li>
<li><b>Trepied sau gimbal</b> (biserică, discursuri): prag <b>65–70</b>, rămân doar cadrele foarte curate.</li>
<li><b>Prea multe bucăți scurte</b>: urcă lungimea minimă la 4–5 s.</li>
<li><b>Stai ~2 s pe fiecare om</b> când filmezi invitații: pune lungimea minimă pe 2 s, altfel cadrele lor dispar.</li>
<li><b>Vrei mutările lente de la un om la altul</b> în selecție: oprește „Scoate mișcările de cameră”.</li>
<li><b>Prea multe cadre ușor neclare</b>: urcă pragul (focusul cântărește cel mai mult, 40%).</li>
</ul>

<h3>Modul Custom</h3>
<p>Custom îți dă control pe fiecare criteriu și nu aruncă nimic: împarte tot materialul în <b>Poor / Fair / Good</b> (roșu / galben /
verde), pe <b>3 piste</b> (V1 Poor, V2 Fair, V3 Good). Notele se dau pe bucăți de <b>2 secunde</b>.</p>
<p><b>Cele 5 criterii</b> (fiecare cu un comutator și un slider 0–100):</p>
<ul>
<li><b>Contrast</b> (implicit 50): penalizează imaginile spălate sau prea dure.</li>
<li><b>Expunere</b> (Exposure; implicit 50): prea întunecat (luminozitate sub 45/255), prea luminos (peste 210/255) sau zone arse (peste 15% din cadru).</li>
<li><b>Blur / Focus</b> (implicit 60): cadrele neclare.</li>
<li><b>Importanță vizuală</b> (Visual Importance; implicit 40): cât se întâmplă în cadru (60% mișcarea oamenilor + 40% claritatea centrului). E un
criteriu „blând”: ridică nota cadrelor cu acțiune, dar nu coboară niciodată o notă ca „defect”.</li>
<li><b>Tremur / Stabilitate</b> (Shakiness / Stability; implicit 50): tremuratul (aceleași smucituri ca la Auto).</li>
</ul>
<p><b>Ce înseamnă sliderul</b>: cât <b>contează</b> criteriul față de celelalte, nu un prag. Valorile se compară între ele: Focus 60 și
Contrast 30 înseamnă că focusul contează de două ori mai mult. Comutatorul oprit = criteriul nu contează deloc. Nota unei bucăți =
60% media ponderată + 40% cel mai slab criteriu pornit (fără Importanță vizuală).</p>
<p><b>Nivel de strictețe</b> (Strictness preset) și <b>Pragul de calitate</b> (Quality threshold, bara cu două mânere): Custom împarte după <b>procente din tot materialul tău</b>,
nu după o notă fixă. Cele mai slabe X% devin Poor, următoarele Fair, restul Good:</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Preset</th><th>Poor</th><th>Fair</th><th>Good</th></tr>
<tr><td>Lenient</td><td>15%</td><td>35%</td><td>50%</td></tr>
<tr><td>Normal</td><td>25%</td><td>40%</td><td>35%</td></tr>
<tr><td>Strict</td><td>35%</td><td>40%</td><td>25%</td></tr>
</table>
<p>Tragi de mânere ca să alegi tu procentele (presetul devine Custom). Pentru că e relativ, chiar și o nuntă filmată perfect are
niște Poor: cele mai slabe bucăți din ea.</p>
<p><b>Protejează cadrele bune</b> (Protect good frames; pornit): ca să nu fie pedepsite cadrele bune doar pentru că materialul e bun în general: o bucată cu
nota peste <b>65</b> nu e niciodată Poor, iar una peste <b>85</b> nu e niciodată Fair.</p>
<p><b>Lungimea minimă a tăieturii</b> în Custom: bucățile mai scurte de atât se lipesc de vecinul cu nivelul cel mai apropiat (nu se aruncă).</p>
<h3>Setările de export (Output settings)</h3>
<ul>
<li><b>Salvează fișierul rezultat în</b> și <b>Nume fișier</b>: unde se salvează XML-ul și cum se numește.</li>
<li><b>Program de montaj</b>: Premiere Pro sau DaVinci Resolve (același XML; se schimbă doar instrucțiunile).</li>
<li><b>Setări sequence</b>: Rezoluție (Match footage = ca filmările), Frame rate (implicit <b>25</b>, ca toate sequence-urile tale
finale), Câmpuri (Lower Field First / Upper / Progressive).</li><li><b>Generează fișierul rezultat</b> scrie XML-ul.</li>
<li>Fiecare cut are sunetul lui pe A1/A2, legat de imagine (fișierele cu mai mult de 2
canale, ca MXF-ul de FX6, folosesc canalul 1). Culorile clipurilor: roșu / galben / verde după nivel.</li>
</ul>
<h3>Ce nu face</h3>
<ul>
<li>Nu ascultă sunetul: alegerea e doar pe imagine.</li>
<li>Nu recunoaște oameni. „Importance” înseamnă „se mișcă ceva în cadru”, nu „e mireasa în cadru”.</li>
<li>Nu modifică fișierele tale.</li>
</ul>

<h2>Multicam: Sync</h2>
<p>Multicam sincronizează toate camerele cu recorderul de la mixer, apoi (opțional) face montajul. Sunt doi pași separați:
<b>Sync</b> (rapid, doar sunet) și <b>Auto Edit</b> (lent, analiză video). Auto Edit nu se poate apăsa până nu există o sincronizare.</p>
<h3>Pașii</h3>
<ol>
<li><b>Arunci tot materialul</b>: carduri, recorder, foldere întregi. Fișierele auxiliare sunt ignorate automat.</li>
<li><b>Sync</b>: găsește masterul audio (fișierele doar-audio de la recorder; fără recorder, cel mai lung clip cu sunet), sincronizează
fiecare clip pe sunet și grupează clipurile pe camere.</li>
<li>Verifici: tab-ul <b>Clips</b> (clipurile „Check” sau „Failed”; decalajul se corectează cu dublu click pe Start) și tab-ul
<b>Cameras</b> (două camere care sunt de fapt una: le dai același nume și se unesc; rolul Static / Handheld, dacă e greșit).</li>
<li>Poți da deja <b>Export XML</b>: fiecare cameră pe pista ei, cu clipurile întregi sincronizate, plus recorderul. Dacă vrei să
montezi singur, te oprești aici.</li>
</ol>
<h3>Cum sincronizează</h3>
<ul>
<li>Ascultă fiecare canal separat și îl alege pe cel mai puternic (merge cu mono pe 2 canale, cu un canal gol sau cu recordere cu
multe canale). MXF-urile Sony cu mai multe piste de sunet sunt citite dintr-o singură trecere.</li>
<li>Folosește ceasurile ca indiciu (timecode-ul camerei, ora din recorder, data fișierului): primul clip al fiecărei camere e căutat
în tot recorderul, iar rezultatul îi dă eroarea de ceas; următoarele clipuri sunt căutate doar ±90 s în jurul locului prezis (de
~18 ori mai rapid), cu căutare completă dacă nu se găsesc.</li>
<li>Căutarea rapidă scanează întâi tot recorderul pe un contur de volum, apoi verifică exact (GCC-PHAT) doar ±1,5 s în jurul
candidaților. Pe muzică repetitivă, a doua trecere reverifică fiecare bucată.</li>
<li>La final vezi cât a durat citirea fișierelor și cât căutarea. Dacă citirea durează mult, discul încetinește (un HDD extern e
mult mai lent decât un SSD).</li>
</ul>
<h3>Culorile de pe hartă (Sync Map)</h3>
<ul>
<li><b>Verde = High</b>: sigur (toate bucățile ascultate sunt de acord).</li>
<li><b>Galben = Medium</b>: foarte probabil corect (cel puțin 2 bucăți de acord).</li>
<li><b>Portocaliu = Check</b>: poziție nesigură. Ajunge pe pista separată „· check sync” și nu e folosit în montajul automat.</li>
<li><b>Roșu = Failed</b>: nu a putut fi pus („no usable sound” = clip fără sunet folositor, de exemplu gimbal cu microfonul oprit).</li>
<li><b>Mov = By time</b>: drona și camerele fără sunet, așezate aproximativ după oră (corectată cu eroarea de ceas a celorlalte
camere), cu clipul întreg; nu intră în montajul automat.</li>
</ul>
<p>O cameră nu poate filma două lucruri deodată: dacă două clipuri ale aceleiași camere se suprapun, cel mai puțin sigur ajunge pe
„check sync”.</p>
<h3>Lavaliere și recorder</h3>
<p>Recorderul principal e folderul doar-audio cu cele mai multe ore (cel de la mixer). Celelalte foldere doar-audio (LAV I, LAV II)
sunt sincronizate pe el și apar în export pe pistele lor audio, întregi.</p>
<h3>Import XML (sincronizare făcută în altă aplicație)</h3>
<p>Dacă ai sincronizat deja în Syncaila, Premiere sau DaVinci, exportă de acolo un XML (FCP7 XML) cu fiecare cameră pe pista ei și
apasă Import XML. Pozițiile sunt preluate exact (fără să mai sincronizeze), fiecare pistă video devine o cameră, fișierele doar-audio
devin recorderul. Clipurile care nu sunt pe acest calculator sunt sărite, cu avertisment.</p>
<h3>Dacă adaugi fișiere după</h3>
<p>Dai din nou Sync, apoi Auto Edit. A doua oară se analizează doar clipurile noi.</p>

<h2>Multicam: Auto Edit și Auto Director</h2>
<p><b>Auto Edit</b> analizează video-ul fiecărui clip sincronizat (aceeași analiză ca la Footage Selection), stabilește rolul camerelor
(dacă nu l-ai schimbat tu) și construiește montajul. Analiza se salvează: a doua oară se procesează doar clipurile noi. Orice reglaj
din dreapta (Auto Director) se aplică <b>instant</b>, fără o nouă analiză; pe hartă vezi imediat rezultatul.</p>
<h3>Cum alege camera</h3>
<ul>
<li>Fiecare cameră primește la fiecare jumătate de secundă o notă de calitate, cu <b>aceeași formulă ca Auto</b>: claritate 40%,
stabilitate 30%, expunere 30%, iar 40% din notă e criteriul cel mai slab.</li>
<li><b>Camerele din mână</b> sunt judecate și față de propriul lor material: jumătate din nota de stabilitate e absolută, jumătate
e comparată cu tremuratul obișnuit al acelei camere (puțin tremur face parte din stilul ei).</li>
<li><b>Camerele statice</b> primesc un bonus de până la <b>+10 puncte</b> când se întâmplă ceva în cadru (oameni care se mișcă).</li>
<li>În timpul unei <b>mutări de cameră</b> (de la un om la altul), nota acelei camere scade la 15%: aproape niciodată nu se taie pe o mutare.</li>
<li><b>Static / Handheld</b> se ghicește singur: statică = camera practic nu se mișcă niciodată. Îl schimbi în tab-ul Cameras.</li>
<li>Apoi aplicația caută drumul cel mai bun prin camere, respectând lungimile de cadru și ritmul de mai jos.</li>
</ul>
<h3>Reglajele Auto Director</h3>
<ul>
<li><b>Cadru minim</b> (Minimum shot; 1–10 s, implicit 3 s): niciun cadru nu e mai scurt de atât (pe drop, opțiunea de drop are prioritate).</li>
<li><b>Cadru maxim</b> (Maximum shot; 4–120 s, implicit 30 s): un cadru mai lung de atât e întrerupt cu cea mai bună altă cameră.</li>
<li><b>Ritmul tăieturilor</b> (Cut pace; 0–100, implicit 50): cât de ușor schimbă camera. 0 = calm, schimbă rar (doar când altă cameră e mult mai bună);
100 = rapid, schimbă des. Tehnic: „costul” unei schimbări scade de la 20 de puncte (la 0) la 2 puncte (la 100).</li>
<li><b>Static ↔ Handheld</b> (0–100, implicit 60): stânga preferă camerele statice, dreapta pe cele din mână, cu până la 25 de puncte
în plus sau în minus. 50 = neutru. Dacă vezi camera statică prea des (nu tremură niciodată, deci iese mereu „bună”), trage spre dreapta.</li>
<li><b>Cut on the beat</b> (pornit): pe muzică, tăieturile urmează beat-urile și măsurile recorderului; pe vorbire, tăieturile cad în
pauzele dintre fraze. Oprit: montajul pe o grilă de 0,5 s, ca la început.</li>
</ul>
<h3>Învață stilul meu de montaj… (Learn my editing style)</h3>
<p>Alegi XML-ul unei petreceri montate de tine (exportat din Premiere). Aplicația măsoară cum tai: lungimea obișnuită a cadrelor
(cele mai scurte 15% → Cadru minim, cele mai lungi 5% → Cadru maxim), ritmul, cât folosești camerele din mână, cât de des tai pe
drop. Îți arată ce a măsurat; alegi <b>Folosește pentru acest proiect</b> sau <b>Folosește ca stilul meu</b> (atunci fiecare proiect nou pornește cu
setările tale). Muzica se măsoară doar dacă fișierele recorderului din acel XML sunt pe calculator. Stilul e salvat doar pe acest calculator.</p>
<h3>Export XML</h3>
<p>Un singur sequence de 25 fps: <b>V1…Vn</b> câte o pistă pe cameră, fiecare doar cu cadrele ei din montaj (se vede ca montajul
final); <b>A1/A2</b> recorderul întreg; apoi câte o pistă audio pentru fiecare cameră, întreagă și pornită. Deasupra, pista
<b>unghiului alternativ</b> (vezi pagina următoare), oprită. Merge în Premiere (File &gt; Import) și în DaVinci (File &gt; Import &gt; Timeline).</p>

<h2>Multicam pe muzică</h2>
<p><i>Drop, build-up, zone Slower cuts, unghiul alternativ.</i></p>
<p>Cu <b>Cut on the beat</b> pornit, Auto Edit citește muzica recorderului (o dată, apoi rămâne salvată): tempo-ul pe fiecare porțiune
(urmărește schimbările de melodie ale DJ-ului și tempo-ul care „curge” la formație), fiecare beat, începutul fiecărei măsuri,
build-up-urile, drop-urile și zonele cu vorbire.</p>
<p><b>Beat</b> = bătaia pe care o bați din palme (1, 2, 3, 4). <b>Măsură (bar)</b> = 4 beat-uri. La o melodie de club (128 BPM):
1 beat ≈ 0,5 s, 1 măsură ≈ 2 s.</p>
<h3>Ce se întâmplă pe muzică</h3>
<ul>
<li>Cadrele încep pe beat, de obicei pe începutul măsurii, și durează 1–4 măsuri: mai scurte când melodia e intensă, mai lungi când
e calmă (automat, mereu activ). Cadrul minim și ritmul tăieturilor dau ritmul de bază.</li>
<li>Fiecare tăietură cade cu <b>1 cadru (40 ms) înainte de beat</b>: ochiul vede schimbarea cu o mică întârziere, așa că pare exact pe
lovitură.</li>
<li>Unde beat-ul nu e clar (o baladă fără tobe, vorbire) nu se inventează beat-uri: acolo se taie în pauzele dintre fraze sau ca înainte.</li>
<li>Rândul <b>Music</b> de pe hartă arată fiecare melodie cu tempo-ul ei, intensitatea (mai luminos = mai intens), vorbirea (gri) și
drop-urile (linie roz).</li>
</ul>
<h3>Pe drop, schimbă camera la fiecare (On a drop…; pentru toate proiectele)</h3>
<p>Drop-ul = momentul în care intră basul tare după ce muzica „urcă”. O tăietură cade exact pe drop, apoi camera se schimbă la:</p>
<ul>
<li><b>1 beat</b> (~0,5 s): foarte agresiv; doar cu multe camere bune (5+).</li>
<li><b>2 beats</b> (~1 s): ritm de clip; DJ / muzică electronică, 4+ camere.</li>
<li><b>1 bar</b> (~2 s, implicit): energic, dar ușor de urmărit.</li>
<li><b>2 bars</b> (~4 s): mai calm; 2–3 camere sau petrecere liniștită.</li>
<li><b>4 bars</b> (~8 s): aproape fără accelerare.</li>
</ul>
<p>Regula: cu cât ai mai multe camere cu cadre bune, cu atât poți merge mai repede.</p>
<h3>Build-up înainte de drop</h3>
<ul>
<li><b>Un singur cadru până la drop</b> (Hold one shot; implicit): o singură cameră tot build-up-ul (până la 8 măsuri), apoi tăietură fix pe drop.
Contrastul face drop-ul să „lovească”; merge și cu puține camere.</li>
<li><b>Tăieturi tot mai dese</b> (Cut faster and faster): tăieturi tot mai dese (2 măsuri, 1 măsură, 2 beat-uri) până la drop. Tensiune ca într-un teaser;
bine la DJ și cu multe camere.</li>
</ul>
<h3>Zone „Slower cuts” (muzică populară, hore)</h3>
<p>La formație, cu tempo care se schimbă mereu, tăieturile pe măsuri nu se potrivesc. Pe hartă tragi cu mouse-ul peste porțiunea
respectivă și apare o zonă galbenă. În ea se taie pe cel mai apropiat accent din sunet (±0,3 s), cu <b>setările tale de horă</b>,
oricum ar fi setat restul petrecerii: Cadru minim <b>6 s</b>, Cadru maxim <b>120 s</b>, Ritmul tăieturilor <b>50</b>, Static ↔ Handheld <b>45</b>.
Tragi de margini ca s-o muți; sub hartă scrii ora exactă (h:mm:ss.s); click dreapta sau Delete o șterge. Zonele rămân salvate.</p>
<h3>Unghiul alternativ</h3>
<p>În XML, deasupra montajului, o pistă oprită cu a doua cea mai bună cameră pentru fiecare cadru (clipurile se numesc „ALT · cameră”).
Dacă un cadru nu-ți place, activezi pista sau tragi alternativa jos. Cadrele de pe camera statică nu primesc alternativă (acolo ești
safe oricum).</p>
<h3>Exemplu</h3>
<p>DJ, 4 camere, setările implicite: strofa calmă cu cadre de 2–4 măsuri, build-up-ul ținut pe o cameră, tăietură fix pe drop, apoi
altă cameră la fiecare măsură, după drop iar mai liniștit. Încearcă „1 bar” și „2 beats”: schimbarea e instantă.</p>

<h2>Teaser Studio</h2>
<p>Shortmovie-ul pe muzica ta: teaser (~50 s), pregătiri (~70 s), biserica (~45 s), cuplu (~23 s), sala (~20 s), apoi petrecerea
(duratele obișnuite măsurate pe cele 6 filme ale tale). Fiecare nuntă e un proiect (card): <b>+ Proiect nou</b>, click ca să-l deschizi,
✕ ca să-l ștergi, <b>← Proiecte</b> ca să revii. Fiecare proiect ține minte filmările, muzica, momentele și pozele.</p>
<h3>1. Filmări (selecțiile tale)</h3>
<p>În Premiere pui selecțiile într-un sequence și dai Export XML. <b>Contează doar culorile</b> (etichetele din Premiere: click dreapta pe
clip &gt; Label):</p>
<ul>
<li><span style="color:#f08ccb">■</span> <b>Rose</b> mireasa · <span style="color:#3f63e0">■</span> <b>Blue</b> mirele ·
<span style="color:#9b4fc2">■</span> <b>Purple</b> cuplul · <span style="color:#9a6233">■</span> <b>Brown</b> biserica</li>
<li><span style="color:#e3cf3e">■</span> <b>Yellow</b> / <span style="color:#22b8a5">■</span> <b>Caribbean</b> sala ·
<span style="color:#6d78d6">■</span> <b>Iris</b> petrecerea (și first look-ul de dimineață) · <span style="color:#b29de6">■</span>
<b>Violet</b> drona</li>
<li><span style="color:#1f9e96">■</span> <b>Teal</b> locația de la pregătiri · <span style="color:#f39c2c">■</span> <b>Mango</b> vornicul</li>
<li>Ignorate: <b>Tan</b> (interviuri), <b>Forest</b> (nesturi), <b>Lavender</b> (adjustment layer) și clipurile fără culoare.</li>
</ul>
<p>Ordinea și pistele nu contează: ordinea zilei vine din ora filmării. O selecție poate fi mai lungă (de exemplu 10 s de petrecere):
la import, fiecare selecție e analizată o dată (claritate, stabilitate, expunere, mișcare; 4 măsurători pe secundă) și se folosește
partea cea mai bună: cu mișcare pe drop și la petrecere, mai calmă la pregătiri și la biserică. Analiza se poate opri (Cancel), se
salvează la fiecare 25 de selecții și continuă de unde a rămas. Poți genera și înainte să se termine. Clipurile interpretate în
Premiere la alt frame rate (50p ca 25p) sunt citite corect.</p>
<h3>2. Auto sau Blueprint (unul sau altul)</h3>
<ul>
<li><b>Auto</b>: taie pe beat-ul muzicii tale (mai jos).</li>
<li><b>Blueprint</b>: folosește ca șablon unul din shortmovie-urile tale terminate. <b>+ Adaugă</b>: alegi XML-ul filmului, un nume și
stilul (Modern sau Tradițional). Tăieturile, muzica, efectele sonore și ritmul rămân exact ca în filmul tău; fiecare tăietură e
umplută cu un cadru de aceeași culoare din nunta nouă (partea cea mai bună, în ordinea zilei, niciun moment de două ori). Tan rămâne
loc gol cu marker „Aici interviul”; sunetul camerelor și al recorderului vechi nu se păstrează. Nu ai nevoie de muzică (cardul de
muzică dispare). Blueprint-urile sunt salvate pe acest calculator, pentru toate proiectele.</li>
</ul>
<h3>3. Muzica (doar Auto)</h3>
<p>Melodiile deja îmbinate: un fișier audio sau XML-ul montajului muzical (din XML se văd exact schimbările de melodie, chiar și
în același fișier tăiat cu crossfade). Aplicația găsește beat-urile, drop-ul și propune cele <b>șase momente</b> (m:ss), pe care le
poți corecta (un timp greșit se face roșu):</p>
<ul>
<li><b>Drop</b>: drop-ul din melodia de teaser (cea mai mare creștere de bas).</li>
<li><b>Teaser ends</b>: aici încep pregătirile.</li>
<li><b>Getting ready ends</b>: aici începe biserica.</li>
<li><b>Church ends</b>: aici vin cadrele de cuplu, peste finalul jurămintelor (~23 s înainte de melodia de petrecere).</li>
<li><b>Party song starts</b>: melodia de petrecere și prezentarea locației (sala, drona).</li>
<li><b>Venue ends</b>: începe petrecerea propriu-zisă.</li>
</ul>
<p>Timpii trebuie să meargă înainte, în ordinea de mai sus. <b>Detectează din nou</b> le recalculează din muzică.</p>
<h3>4. Mirii (opțional)</h3>
<p>Câte o poză bună cu mireasa și cu mirele (din ziua nunții), apoi <b>Găsește-i în selecții</b>. Recunoaștere facială locală, gratuită
(modelele se descarcă o dată). Fiecare selecție e citită o dată pentru amândoi; rezultatul rămâne salvat. La generare, cadrele de
mireasă, mire, cuplu, biserică și petrecere preferă selecțiile în care apar ei. Nu se folosește la primul dans.</p>
<h3>Generează, Amestecă, Export</h3>
<ul>
<li><b>Generează</b> construiește structura ta: teaser (înainte de drop pregătiri, biserică, cuplu, dronă; după drop petrecere
alternată cu cuplu), pregătiri mireasă / mire (cu cadre de cuplu printre ele, mai multe spre final), biserica cu cuplul la final,
sala (începe cu drona filmată cel mai aproape), apoi petrecerea. Fiecare tăietură cade pe beat.</li>
<li><b>Amestecă cadrele</b> (Shuffle shots) alege alte cadre, păstrând ordinea zilei.</li>
<li><b>Export XML</b>: cadrele pe V1 cu culorile tale, muzica pe A1/A2 și markere pentru fiecare parte (Teaser, DROP, Getting ready,
Church, Couple + vows, Party: venue, Party), ca să pui testimonialele și jurămintele.</li>
</ul>
<h3>Regulile de alegere</h3>
<ul>
<li>Un moment nu e folosit niciodată de două ori (nici în teaser și apoi în film).</li>
<li>Același clip nu apare de două ori la rând, dacă există altul.</li>
<li>Întâi câte o bucată din fiecare selecție, abia apoi a doua bucată din aceeași selecție.</li>
<li>Biserica și sala încep cu cadrul de dronă filmat cel mai aproape de ele; teaserul folosește drona doar dacă ai peste 2 clipuri de dronă.</li>
<li>Iris de dimineață = first look (merge la pregătiri); Iris de după biserică = petrecere.</li>
<li>O tăietură e umplută doar cu o bucată destul de lungă; când nu mai e material, cadrul de dinainte ține mai mult (niciodată o
repetare), iar aplicația îți spune câte secunde au rămas neacoperite.</li>
</ul>
<h3>Test AI (experimental)</h3>
<p>Verifică dacă un model AI gratuit (SigLIP 2, rulează pe Mac) recunoaște cadrele tale la fel ca etichetele tale. <b>Test rapid</b>
(25 de selecții pe culoare, câteva minute) sau <b>toate selecțiile</b> (lent, peste noapte; Mac-ul nu adoarme cât rulează). Prima dată
descarcă modelul (câțiva GB). E doar un test: nu schimbă teaserul.</p>

<h2>Long Film (filmul lung)</h2>
<p>Filmul lung până la petrecere, pre-montat din selecțiile tale cum îl montezi tu (măsurat pe două nunți ale tale: selecțiile +
filmul final). Muzica, interviurile (Tan) și finisajele le pui tu în Premiere; petrecerea e montajul Multicam. Proiecte pe carduri,
ca la Teaser Studio.</p>
<h3>Cardurile paginii</h3>
<ol>
<li><b>Filmări</b>: XML-ul sequence-ului de selecții (vezi pagina „Cum trebuie să arate selecția” și desenul de jos din pagină). Îți
arată camerele găsite, câte selecții are fiecare și dacă ceva nu e bine (de exemplu selecții pierdute după dronă, cu explicația exactă).</li>
<li><b>Auto sau Blueprint</b> (unul sau altul). Blueprint folosește ca șablon unul din filmele tale lungi terminate (blueprint-urile
Long Film sunt separate de cele din Teaser Studio): tăieturile, muzica, efectele și ritmul rămân, fiecare tăietură e umplută cu un
cadru de aceeași culoare din nunta nouă, Tan rămâne loc cu marker „Aici interviul”, iar porțiunile goale de peste 60 s (petrecerea)
primesc marker „Petrecere (montajul Multicam)”. În Blueprint vornicul e umplut tăietură cu tăietură; pentru vornicul sincronizat pe
două camere folosește Auto.</li>
<li><b>Teaser</b> (doar Auto): proiectul din Teaser Studio al aceleiași nunți; teaserul lui (cu muzica) deschide filmul.</li>
<li><b>Construiește</b>, apoi <b>Export XML</b>. Durata scrisă e durata FILMULUI, nu un timp de așteptare.</li>
</ol>
<h3>Ce face Auto, parte cu parte</h3>
<ul>
<li><b>Copiile</b> de la finalul selecțiilor (tot ce e după ultimul cadru cu drona, plus orice selecție care repetă o bucată deja
selectată) nu se folosesc: sunt pentru shortmovie.</li>
<li><b>Camerele</b> sunt recunoscute după fișiere (numele fără cifre + mărimea imaginii + frame rate), iar ziua fiecărei camere după
numerele fișierelor. Camera principală = cea cu cele mai multe cadre de mire / mireasă. Ceasurile camerelor nu sunt folosite între camere.</li>
<li><b>Pregătiri</b>: selecțiile scurte de mire și mireasă (până la 8 s), fără primele ~15% din fiecare parte, din fiecare mijlocul
(0,8–2 s); povestite în paralel, în blocuri ca la tine: un bloc mare cu cine a fost filmat primul (~27% din cadrele lui, 4–20), un bloc
mare cu celălalt (~20%, 4–14), apoi rânduri de 1–7 (de obicei ~4) potrivite așa încât amândoi să se termine odată. Teal la început.</li>
<li><b>Vornic și first look</b>: selecțiile lungi de dimineață ale camerei principale (mire / mireasă peste ~1 min = vornic, Iris peste
15 s) întregi pe V1, cu sunetul continuu. A doua cameră e găsită după sunet (chiar fără biserică pe ea) și pusă întreagă pe V2 (pistă
oprită), cu sunetul pe A3/A4; pe V3 bucăți alternante de ~3–4 s, la pauzele de vorbire. Se folosesc doar potrivirile sigure, în
ordinea zilei. Iris-urile scurte de dimineață urmează ca montaj (~2 s).</li>
<li><b>Biserica</b>: toate cadrele Brown în ordinea ta de pe timeline; cele scurte întregi, din cele lungi (peste 15 s) câteva bucăți de 6 s.</li>
<li><b>Cuplu și sală</b>: dronă, primul bloc de sală, dronă, primul bloc de cuplu, cu câte o dronă la ~7 cadre; ~1,3–1,6 s fiecare.</li>
<li>Fiecare cadru își păstrează culoarea ta și are sunetul legat de imagine; teaserul are muzica pe A5/A6; câte un marker pe fiecare
parte, în limba aplicației. E un pre-montaj: ritmul exact pe muzică și alegerea finală le faci tu.</li>
</ul>

<h2>Cum trebuie să arate selecția</h2>
<p>Ce trebuie să aibă XML-ul pe care îl dai fiecărei funcții. Culorile sunt etichetele (labels) din Premiere: Rose mireasa,
Blue mirele, Purple cuplul, Brown biserica, Iris first look / petrecerea, Teal locația de la pregătiri, Mango vornicul,
Yellow sau Caribbean sala, Violet drona. Tan (interviuri), Forest (nesturi) și Lavender (adjustment layer) sunt ignorate.</p>
<ul>
<li><b>Descărcare carduri, Creează proiectul</b>: nu ai nevoie de nicio selecție.</li>
<li><b>Footage Selection</b>: clipuri brute, în orice ordine (Adaugă folder sau Import XML; exportul păstrează ordinea din listă).</li>
<li><b>Multicam</b>: bagi tot, în orice ordine; camerele se sincronizează după sunet. Import XML: un timeline deja sincronizat
(fiecare pistă video = o cameră).</li>
<li><b>Teaser Studio (Auto)</b>: contează <b>doar culorile</b>. Ordinea și pistele nu contează (ordinea zilei vine din ora filmării).
Clipurile fără culoare nu sunt folosite. Plus muzica ta.</li>
<li><b>Long Film (Auto)</b>: <b>nu merge random</b>. Trebuie:
<ul><li>o culoare pe fiecare selecție (fără culoare = nefolosit);</li>
<li>biserica (Brown) în ordinea în care o vrei în film;</li>
<li>blocul cu drona după tot restul: după el pot fi doar copiile pentru shortmovie (sunt lăsate afară). Dacă multe selecții
sunt după dronă, aplicația îți spune cu roșu exact ce e greșit: care e ultimul cadru cu drona și unde se termină în sequence,
câte selecții de fiecare culoare se pierd după el și care e prima.</li></ul>
Restul poate fi în orice ordine și pe orice piste: camerele sunt recunoscute după fișiere, iar ziua fiecărei camere după numerele
fișierelor. A doua cameră nu are nevoie de biserică: fără Brown, first look-ul ei e găsit după sunet.</li>
<li><b>Blueprint</b> (Teaser Studio și Long Film): filmul tău terminat cu culorile pe clipuri (ca să știe ce arată fiecare tăietură)
și selecțiile nunții noi cu aceleași culori, în orice ordine.</li>
<li><b>Transcriere</b>: orice fișier cu sunet; Import XML ia clipurile în ordinea de pe timeline.</li>
</ul>
<p>Pagina Long Film are jos un desen cu ordinea: trenulețe de culori, cu numele fiecăruia deasupra și camerele dedesubt. Cu 3, 4 sau 5
camere se continuă la fel, una după alta; cadrele cu cuplul pot sta la mijlocul petrecerii; drona rămâne ultima.</p>

<h2>Transcriere</h2>
<p>Interviurile, discursurile, vornicul sau predica devin text, pe acest calculator, gratuit (Whisper; nu se urcă nimic).</p>
<h3>Pașii și opțiunile</h3>
<ul>
<li><b>+ Adaugă fișiere</b>: sunet (lavaliere, recorder) sau video.</li>
<li><b>Import XML</b> (recomandat pentru poveste): sequence-ul tău din Premiere cu interviurile puse unul după altul (File &gt; Export
&gt; Final Cut Pro XML). Fiecare interviu e un segment (clipurile care încep și se termină odată), de exemplu mirele = Color Matte +
lavaliera, mireasa = MXF-ul de FX6 cu cele 4 piste. Din fiecare segment intră în listă fișierul de transcris: lavaliera, dacă e
separată, altfel camera. Povestea copiază apoi <b>exact clipurile tale</b> din acest sequence (aceleași piste de sunet, microfon și
lavalieră, Color Matte), doar cu alți timpi.</li>
<li><b>Limba</b>: Română, Engleză sau Detectează singur.</li>
<li><b>Precizia</b>: <b>Rapid</b> (large-v3-turbo: de câteva ori mai rapid) sau <b>Cel mai precis</b> (large-v3 la precizie maximă:
mai lent, cel mai bun la nume și cuvinte rare). Prima dată modelul se descarcă o singură dată (1,5–3 GB).</li>
<li><b>Ce face ca să înțeleagă mai bine</b>: ascultă <b>canalul cel mai clar</b> al fișierului, nu un amestec. La FX6, microfonul camerei și
lavaliera sunt pe canale diferite, iar aplicația o alege pe cea în care vorbirea iese cel mai clar peste zgomot (lavaliera). Din
numele folderului nunții („NUNTA 22 AUGUST 2026 Florin si Miruna”) ia numele mirilor, ca să le scrie corect. Timpii fiecărei fraze
vin de la primul și ultimul cuvânt (tăieturi mai exacte). Textul e împărțit <b>pe fraze</b>: tăiat la . ? ! și la pauzele de peste
0,6 s; o bucată are cel mult 8 s (una mai lungă e tăiată la cea mai bună pauză reală, de preferat la virgulă sau la un cuvânt de
legătură „și”, „dar”, „pentru că”…; dacă nu există nicio pauză, e o <b>tăiere forțată</b>, în punctul cel mai liniștit din sunet
între 5 și 8 s, și apare așa în raport), ca să poată fi intercalată. Bucățile sub 0,8 s și cele doar cu „ăă”, „deci”, „așa” sunt lipite de vecina cea mai
apropiată (cât timp rămân sub 8 s); o frază scurtă dar întreagă („Da, cu siguranță.”) rămâne singură. Replicile tale scurte
(„Perfect”, „Bravo”, „Mulțumesc”) sunt marcate ca întrebări. Când Whisper uită punctul („din nou Mi-a dat”), un cuvânt cu literă
mare în mijlocul rândului, după un cuvânt fără punctuație, începe o frază nouă (în afară de nume: un cuvânt care în tot interviul apare doar cu literă mare, ca „Mamaia”, „TikTok” sau numele nașului, e
recunoscut singur ca nume; un cuvânt uzual al limbii, din primele 5000, care apare o singură dată cu literă mare, ca „Asta” sau
„Mi-a”, e început de frază; după „cu”, „pe”, „la”, „și” nu se începe niciodată frază nouă; numele mirilor din folder și prenumele
scrise în listă sunt mereu nume),
deci o întrebare lipită de un răspuns ajunge separat. O bucată scurtă nu e lipită niciodată de o întrebare. Când Whisper nu dă timpul
fiecărui cuvânt, porțiunea e transcrisă încă o dată singură; dacă nici atunci, timpii sunt estimați după litere și fiecare tăietură e
mutată în cea mai apropiată pauză reală din sunet (±0,6 s). În listă, un interviu cu bucăți peste 8 s are ⚠. În .txt timpii au
zecimi ([00:00:05.2]). Dacă Whisper
intră în buclă și repetă aceeași frază, repetările sunt scoase.</li>
<li><b>Cine vorbește, măsurat din sunet</b>: înainte de transcriere, aplicația găsește vorbirea și pauzele reale (detectorul
Silero, pe acest calculator) și măsoară cine vorbește. Tu ești departe de lavalieră: dacă fișierul are și microfonul camerei (FX6),
la tine lavaliera e aproape la fel de tare ca microfonul camerei, iar la miri e cu 10–19 dB mai tare; dacă are un singur canal, vocea
ta e cu 10–15 dB mai slabă. Replicile tale (întrebări, „Bravo”, „Spune-i la persoana a doua”) sunt marcate [ÎNTREBARE] din
sunet, chiar fără „?”, iar o întrebare spusă de miri („Ai scăpat?”) rămâne a lor. Unde diferența nu e clară, rândul are (?) și decide
regula veche de text. Apoi fiecare bucată dintre pauze, cu un singur vorbitor, e transcrisă separat, deci întrebarea ta nu se mai lipește
de răspuns. Frazele se taie doar în pauze reale (punctuația doar alege dintre ele); după „?” se taie mereu. La interviul cu amândoi
odată, cu câte o lavalieră pe canale diferite, fiecare bucată primește [S1] sau [S2], iar Claude află din ce spun cine e cine; cu o
singură lavalieră pentru amândoi, vocile lor nu se pot despărți din sunet (decide Claude din text).</li>
<li><b>Calitate</b> (sub text) și <b>Raport de calitate</b>: după fiecare transcriere, aplicația se verifică singură, măsurând din
sunet: câte coduri trec de 8 s (ținta e 0), câte sunt sub 0,8 s, câte au un „?” la mijloc (întrebare lipită de răspuns) și câte
granițe între coduri au o pauză reală între ele (ținta: cel puțin 95 %; tăierile forțate sunt numărate separat), cu lista celor
care cad în vorbire, plus cât de sigur se desparte vocea ta de a mirilor, câte replici de-ale tale au fost marcate [ÎNTREBARE] din
sunet și câte bucăți sunt nesigure. Raportul se salvează lângă
fișier (<i>nume</i>_raport.txt). Verde = toate țintele atinse, roșu = ceva de verificat. La poveste se măsoară la fel tăieturile in /
out, iar raportul se salvează lângă XML.</li>
<li><b>Test pe mai multe nunți…</b>: alegi un folder (de exemplu <i>teste</i>) cu câte un subfolder pentru fiecare nuntă (interviurile
+ XML-ul sursă din Premiere, dacă îl ai). Aplicația le transcrie pe toate, le măsoară ca mai sus, face din fiecare o poveste de test
(toate codurile, alternând interviurile) și îi verifică tăieturile și XML-ul. Rezultatul e un tabel: roșu = sub țintă, ▼ = mai rău
decât la versiunea anterioară (cifrele fiecărei versiuni rămân în rezultate.json, în folderul de test). Alege 3–4 nunți cât mai
diferite: FX6 pe 4 piste, doar lavaliere, interviul cu amândoi odată, sunet prost (afară, vânt).</li>
<li><b>Viteza</b>: pe Mac-urile M1–M4, transcrierea rulează pe placa video (Apple MLX), de câteva ori mai repede decât pe procesor; dacă
nu merge, aplicația trece singură pe varianta de procesor. Pe Mac-urile Intel rulează pe procesor.</li>
<li> Unele cuvinte tot pot ieși pocite: Claude le înțelege din context, iar în
markerele poveștii scrie textul corectat.</li>
<li><b>Transcriere</b>: lângă fiecare fișier apar un .txt (textul cu orele) și un .srt (subtitrare). Textul se vede în dreapta;
<b>Copiază textul</b> îl pune în clipboard.</li>
<li><b>Scoate</b> (sau tasta Delete): scoate fișierul selectat din listă. Fișierul și transcrierea lui rămân pe disc.</li>
</ul>
<h3>Povestea din interviuri (cu Claude)</h3>
<p>Claude citește interviurile mirilor, găsește povestea lor și le împletește într-<b>o singură poveste spusă de amândoi</b>: unul
continuă ideea celuilalt, cu început, mijloc și final. Povestea are cât are nevoie: nu e scurtată forțat. Folosește doar fraze întregi,
exact cum le-au spus; nu inventează nimic. Merge prin <b>abonamentul tău Claude</b> (fără cheie, fără costuri în plus).</p>
<p><b>Cum le împletește:</b> pe amândoi îi întrebi aceleași lucruri (cum v-ați cunoscut, cum e mirele / mireasa, ce iubești la el /
ea, ce vă doriți, un mesaj pentru celălalt), deci pe fiecare temă există versiunea ei și a lui. Claude taie de la unul la celălalt pe
aceeași temă, des, în bucăți scurte, ca și cum unul ar continua ideea celuilalt (el spune ce iubește la ea, apoi ea ce iubește la el).
Ordinea: cum s-au cunoscut, cum se văd unul pe altul, ce îi leagă, viitorul, iar la final mesajele lor (finalul emoționant).
Rezultatul e un XML cu bucățile deja tăiate și puse în ordine: îl imporți în Premiere și ai povestea montată.</p>
<p><b>Întrebările tale nu intră în poveste.</b> Interviurile sunt de tipul „tu întrebi, mirii răspund”: frazele care se termină cu
„?” sunt marcate ca întrebări și nu sunt folosite niciodată (nici în mijlocul unei bucăți), iar Claude primește regula să lase afară
și replicile tale scurte („Perfect!”, „Bravo!”, „Mulțumesc!”) și glumele de la final. Cu un singur interviu, Claude face povestea
lui (sau a ei) curgătoare, ca și cum ar fi spusă fără întrebări.</p>
<ol>
<li>Transcrie interviurile și <b>bifează</b> în listă ce intră în poveste (cele marcate ↻ au fost transcrise de o versiune mai veche,
cu bucăți lungi: Transcriere le reface pe fraze). <b>Cine vorbește</b> e opțional: dacă nu-l alegi, Claude află
singur din ce spun care interviu e al mirelui și care al miresei (numele mirilor le ia din folderul nunții), iar lista se completează
după răspuns. Lângă el poți scrie <b>prenumele</b> (de exemplu Florin): apare în cererea către Claude și în markerele poveștii.</li>
<li><b>1. Copiază pentru Claude</b>: aplicația copiază transcrierile (fiecare frază cu un cod: A1, A2… pentru primul interviu, B1… pentru
al doilea) cu o cerere gata scrisă și deschide un <b>chat nou</b> în Claude. Lipești (Cmd+V) și trimiți.</li>
<li>Când Claude a răspuns, copiezi tot răspunsul (butonul de copiere de sub el) și apeși <b>2. Lipește răspunsul lui Claude</b>: se
deschide o fereastră în care lipești răspunsul (dacă e deja copiat, apare singur), apoi <b>Fă XML-ul cu povestea</b>. Sub butoane
scrie mereu la ce pas ești.</li>
<li>Primești un XML: bucățile una după alta (imagine + tot sunetul, cu 0,12 s înainte și 0,2 s după, fără să intre în fraza
vecină), cu un marker pe fiecare (cine vorbește și ce spune, textul corectat de Claude); textul poveștii apare în aplicație. Două
bucăți din același fișier nu se suprapun niciodată (nici măcar un cadru), oricum ar fi așezate în poveste: dacă s-ar atinge,
tăietura se mută la mijlocul pauzei dintre ele. Începutul și finalul fiecărei bucăți cad într-o pauză reală din
sunet, când există una aproape. Sequence-ul se numește ca al tău, cu „ - STORY” la final.</li>
</ol>
<p><b>Verificarea poveștii.</b> Înainte să scrie XML-ul, aplicația verifică răspunsul lui Claude și apoi XML-ul însuși.
<b>Erorile</b> opresc totul și XML-ul <b>nu</b> se scrie: un cod care nu există, un interval peste două interviuri sau care merge
înapoi, o replică de-a ta ([QUESTION]) folosită, același cod de două ori, bucăți care se suprapun, o bucată după finalul fișierului,
legături sau timpi greșiți în XML. Fereastra le arată pe toate; <b>Copiază pentru Claude</b> copiază o cerere de corectare: o lipești
în același chat, iar răspunsul nou îl lipești la pasul 2. <b>Avertismentele</b> lasă XML-ul scris, doar îți spun unde să te uiți: un
rând fără cod (sărit), o întrebare din mijlocul unui interval (scoasă), bucăți din transcriere mai lungi de 8 s, o bucată care începe
cu „și / dar / pentru că” fără fraza dinainte, același vorbitor de peste 3 ori la rând. Dacă pe o temă vorbește doar unul dintre
miri, asta nu se poate verifica automat (aplicația nu știe temele): uită-te tu.</p>
<p>Regulile date lui Claude, pe scurt: doar răspunsurile mirilor, fraze întregi, tăieturi dese între ei pe aceleași teme, ecouri unul
lângă altul, glumele întregi (cu poantă) sau deloc, fără aceeași informație spusă de amândoi la rând, fără bucăți care au sens doar
cu întrebarea, deschidere puternică și final emoționant. Înjurăturile pot rămâne: le scoți tu la montaj.</p>
<p>Dacă Claude îți spune că ai atins limita, încerci la ora pe care ți-o arată Claude: aplicația ține minte ce ai trimis (chiar după
repornire), deci apeși doar pasul 2 când ai răspunsul, sau pasul 1 din nou într-un chat nou. Rândurile din răspuns fără cod sunt sărite și apar în
verificare.</p>

<h2>Coada de analiză</h2>
<p>Arată tot ce rulează acum: analizele Footage Selection, Sync și Auto Edit din Multicam, analiza selecțiilor din Teaser Studio,
construirea Long Film, Descărcare carduri, Creează proiectul și Transcriere (inclusiv povestea cu Claude), cu progres. <b>Deschide</b> te duce la job. Poți lucra în altă parte cât rulează; joburile merg în fundal.</p>

<h2>Setări</h2>
<h3>Performance</h3>
<ul>
<li>Cardurile de sus: procesorul (câte nuclee), memoria RAM totală, cât folosesc alte aplicații, cât e liberă și cât folosește
aplicația acum; dedesubt, aplicațiile care folosesc cea mai multă memorie.</li>
<li><b>Procese în paralel</b> (Parallel jobs; 1 – numărul de nuclee, implicit un sfert din nuclee): câte clipuri se analizează / citesc în același timp. Fiecare
job folosește câteva nuclee, deci peste un sfert – jumătate din nuclee aduce puțin, iar celelalte aplicații (Premiere) merg mai greu.
<b>RAM-ul nu e limita</b>: aplicația ține în memorie doar bucăți mici, micșorate (de obicei sub 1–2 GB). Timpul se duce pe decodarea
video, care e treaba procesorului (și a decodorului video al Mac-ului).</li>
<li><b>Decodare video hardware (Mac)</b> (pornit): decodorul video al Mac-ului face o parte din muncă (VideoToolbox), acolo unde
FFmpeg-ul inclus îl suportă; dacă un codec nu e suportat, aplicația trece singură pe procesor.</li>
</ul>
<h3>Limba</h3>
<p>English sau Română: toată aplicația și aceste pagini. Se aplică la următoarea pornire. Termenii de montaj (Sync, Auto Edit, Export
XML, Drop, Build-up) rămân în engleză, ca în Premiere.</p>
<h3>Update-uri</h3>
<ul>
<li>La pornire aplicația verifică singură dacă există o versiune nouă și te anunță. <b>Caută update-uri</b> verifică oricând.</li>
<li><b>Descarcă și instalează</b> aduce versiunea pentru Mac-ul tău (Apple Silicon sau Intel) în Downloads, cu procent în Setări, și
deschide DMG-ul: tragi MoneyMakingMachine în Applications (Replace), închizi aplicația și o deschizi din nou.</li>
<li>Dacă verificarea nu merge, mesajul spune de ce (fără internet, serverul a refuzat pentru moment etc.).</li>
</ul>
<h3>Salvează raportul de erori…</h3>
<p>Când ceva nu merge: salvezi raportul și i-l trimiți lui Claude. Conține jurnalul aplicației (ce a făcut și erorile) și informații de
bază despre calculator, fără video. O eroare care se repetă apare o singură dată pe minut, nu în buclă.</p>

<h2>Sfaturi utile</h2>
<ul>
<li><b>Auto sau Custom?</b> Auto păstrează doar cadrele bune, pe o pistă. Custom notează tot (Poor / Fair / Good) pe 3 piste și îți dă
control pe fiecare criteriu.</li>
<li><b>Camera statică apare prea des</b> în Multicam? Trage „Static ↔ Handheld” spre dreapta: camera statică nu tremură niciodată,
deci iese mereu „bună”.</li>
<li><b>Timecode</b>: setează-l cât mai aproape de ora reală. Nu trebuie să fie exact la cadru (e doar un indiciu), dar face Sync mult
mai rapid. La fel ceasul camerelor: de el depind ordinea zilei și Descărcare carduri (doar ce s-a filmat la nunta asta).</li>
<li><b>Nu muta și nu redenumi fișierele</b> după export: XML-ul arată spre locul lor de pe disc; dacă le muți, Premiere îți cere să le
reconectezi (Link Media).</li>
<li><b>Proxy-urile</b> camerelor (DJI .LRF, GoPro .LRV, Sony SUB/…S03.MP4) sunt ignorate peste tot: au același sunet ca originalul și
ar dubla camera.</li>
<li><b>Clipuri fără sunet</b> (gimbal cu microfonul oprit): în Multicam apar „Failed: no usable sound”; le pui de mână (dublu click pe
Start) sau folosești Import XML din Syncaila.</li>
<li><b>Formate</b>: orice citește FFmpeg (MXF, MP4, MOV, MKV, AVI etc.). BRAW (Blackmagic) și R3D (RED) nu sunt suportate.</li>
<li><b>Toate sequence-urile finale sunt la 25 fps.</b></li>
<li><b>Proiectele se salvează singure</b> pe calculator. Ștergerea unui proiect nu șterge clipurile tale.</li>
</ul>

"""


EN = """
<h1>How to use MoneyMakingMachine</h1>
<p>The app helps with every step of a wedding, in the order of the menu on the left:</p>
<ol>
<li><b>Card Offload</b>: copies every card at once, checked, into the wedding folder.</li>
<li><b>Create Project</b>: puts all the footage on one timeline, the way you lay it out for the selection, ready to import into Premiere.</li>
<li><b>Selection &amp; Multicam</b>: <b>Footage Selection</b> picks the good shots from the clips by itself; <b>Multicam</b> syncs the
cameras to the mixer recorder and edits the party.</li>
<li><b>Teaser Studio</b>: the short film (teaser, getting ready, church, venue, party) on your music.</li>
<li><b>Long Film</b>: the long film up to the party, pre-edited from your selects.</li>
<li><b>Transcribe</b>: the interviews become text; from the couple's interviews Claude makes one story.</li>
</ol>
<p>Every page on the left of this Info explains one part of the app with every option: what it does, the numbers it works with
and when it is worth changing. Search with the bar at the top (for example "shake", "drop", "vornic").</p>
<p><b>Drag and drop</b>: on every page you can drag files or folders from Finder instead of looking for them with the buttons: a
Premiere XML is imported (selects, a sequence with interviews, a synced timeline), a folder or clips are added, in Create Project the
wedding folder, in Card Offload a folder to copy (or, dropped on the destination, the destination), in Teaser Studio the XML with
colours = the footage, and an audio file or the XML of the music edit = the music.</p>
<p>Everywhere: a <b>green</b> notification = done, <b>red</b> = something did not work (with the reason). The app never changes or
deletes your footage: it only reads it and writes new XML files.</p>

<h2>Card Offload</h2>
<p>Copies the cards to a disk, all at once, every file checked after copying. Every wedding starts here.</p>
<h3>The steps</h3>
<ol>
<li><b>Insert the cards.</b> They appear in the list by themselves (it looks for new cards every 3 seconds), ticked. The Mac's
internal disk and disk images (DMG) never appear.</li>
<li><b>The wedding</b>: day, month, year and the couple's names. The folder names itself the way you do it: "WEDDING 4 JULY
Alexandra and Vlad 2026" (in Romanian: "NUNTA 4 IULIE Alexandra si Vlad 2026"). You can also type it.</li>
<li><b>Destination</b>: the disk where the wedding folder is made.</li>
<li>Tick the options and press <b>Copy the ticked cards</b>. All cards are copied at the same time (each on its own thread).</li>
</ol>
<h3>What you see on each card</h3>
<ul>
<li>The card's <b>size</b>, <b>how much is used</b>, the <b>type</b> (CFexpress, SD) and the measured <b>read speed</b>.</li>
<li>The <b>camera recognised</b>: Sony writes the model in the XML files next to the clips (FX6, FX3, A7 IV); RODE Wireless PRO
("…_Wireless_PRO.WAV" files) = lavalier; Zoom / Tascam or cards with mostly WAV = recorder; DJI = drone or Osmo.</li>
<li>The <b>folder</b> it goes to: fx6, fx3, a74, osmo, recorder, lavaliere/lav 1 and lav 2 (in turn: the first lavalier lav 1, the second
lav 2), drona. Change it in the list; <b>Other folder…</b> gives you a field to type any name. <b>check only (backup)</b> does not copy
the card, it only compares it with its twin's copy.</li>
<li>How many clips are <b>from this wedding</b> and how many stay from other days (see below).</li>
</ul>
<h3>Only what was filmed at this wedding (ticked by default)</h3>
<p>A card can hold several weddings (for example the big FX6 card, not formatted during a weekend with three weddings). Only the clips
filmed <b>from the wedding day at the chosen hour to the next day at the chosen hour</b> (default 05:00 → 05:00), by the camera's clock,
are copied. The rest stays on the card. The files next to the clips (Sony XMLs etc.) follow their clip. If a card shows 0 clips from
this wedding, check the camera's clock or the hours.</p>
<h3>The options</h3>
<ul>
<li><b>Check every file after copying</b> (ticked): the copy is read back from the disk and compared with the card with a checksum
(blake2b). If they differ, the file shows <b>FAILED</b>, in red. It takes a little longer (one more read of the copy), but it is the
only guarantee that the file on the disk is good.</li>
<li><b>Backup cards</b> (ticked): when a camera records to two cards at once, the app recognises them by the names, sizes and
<b>content</b> of the files (it compares pieces of the 6 biggest files). They match when 90% of the smaller card is identical. Only the
fastest card is copied; the other is only checked against the copy, after the copy has finished. If the backup has a clip missing from
the first card, it is copied from the backup. Two lavaliers are never taken for backups (same names and sizes, different sound).</li>
<li><b>Keep the card's folders</b> (ticked): the card's structure stays inside the camera folder (e.g. fx6/XDROOT/Clip/…). Unticked:
every file goes straight into the camera folder.</li>
<li><b>Skip the camera proxies</b> (.LRF, .LRV, .THM): the small preview files are not copied.</li>
<li><b>Write a report next to the footage</b> (ticked): _offload_report.txt, with every file, its size, checksum and status.</li>
<li><b>Eject the cards when everything is copied</b>: so you can take them right away.</li>
</ul>
<h3>Safety</h3>
<ul>
<li>The cards are only <b>read</b>: nothing on them is changed, renamed or deleted.</li>
<li>Nothing at the destination is overwritten: an identical file is recognised ("already there"), a different one with the same name
gets " (2)".</li>
<li>Every copy is first written as .part and gets its real name only when complete: if you stop or the power goes, no half copies that
look good are left behind.</li>
<li>The files keep the card's dates (the order of the day is read from them later).</li>
</ul>

<h2>Create Project (Premiere / DaVinci)</h2>
<p>After the card offload: all the wedding's footage on one timeline, <b>the way you lay it out for the selection</b> (measured on your
4 July and Madalina &amp; Radu selects).</p>
<ol>
<li><b>Choose the wedding folder</b>. After Card Offload it is already chosen. Every folder with video is a camera; if you pick a folder
that holds a single folder with the cameras (e.g. "Video"), the app goes into it by itself.</li>
<li>The <b>cameras</b> come in your order: fx6, fx3, a74, osmo, then other unknown folders, then the drone (drona, mavic, dji), and
"trash" / "gunoi" folders last. <b>Drag</b> a camera to change the order or <b>untick</b> it to leave it out. Under the list you see the
sound-only folders (recorder, lavaliere): they stay out, like in your selects.</li>
<li><b>Sequence name</b>: "selects" by default.</li>
<li><b>Create the XML.</b> The app reads every clip (several at a time) and builds the timeline.</li>
</ol>
<h3>What the timeline looks like</h3>
<ul>
<li>One camera after the other on <b>V1</b>, with <b>10 empty seconds</b> between cameras (you see where each one starts).</li>
<li>Every camera's clips <b>in the order they were filmed</b>: by the camera's clock in the file when every clip of that camera has
it; otherwise by the file date (copies keep it). When two are equal, by name. Numbering that starts again (C9999 → C0001) does not
mix up the order.</li>
<li>Every clip <b>whole</b>, with <b>all its sound</b>: channel 1 on A1, channel 2 on A2 etc. (FX6: 4 channels on A1–A4, the other
cameras A1–A2, the drone no sound), linked to the picture.</li>
<li>25 fps sequence, the main camera's size (yours: 1920×1080).</li>
<li>Proxies (SUB/…S03, PROXY folders, .LRF) and the XML files next to the clips stay out.</li>
</ul>
<h3>How to put it into your project</h3>
<p>The XML is saved in the wedding folder ("WEDDING … - selects.xml"; if it exists, it gets " (2)"). <b>Show in Finder</b> opens the
folder with the XML selected. <b>Premiere Pro</b>: with your project open, drag the XML into the Project panel (or File &gt; Import): a
new sequence with every clip appears, plus a bin with them. <b>DaVinci Resolve</b>: File &gt; Import &gt; Timeline. The app cannot press
buttons inside Premiere by itself, so the import is one drag.</p>

<h2>Footage Selection: how it picks shots</h2>
<p>A Footage Selection project looks at every clip and keeps (or grades) the good parts, then exports an XML you open in Premiere or
DaVinci.</p>
<h3>The clips</h3>
<ul>
<li><b>Add Folder</b> or drag files / folders into the list. Side files (Sony XMLs, pictures, proxies) are ignored.</li>
<li><b>Import XML</b>: the clips of a Premiere / DaVinci timeline (for example the XML from <b>Create Project</b>) come into the list
<b>in the timeline's order</b>. The analysis and the export keep that order. Clips that are not on this computer are skipped (it tells
you how many).</li>
<li>Select clips in the list and press Delete to remove them.</li>
</ul>
<h3>What the analysis measures</h3>
<p><b>Analyze Footage</b> reads the video with FFmpeg (any format, MXF included): <b>8 frames per second</b>, scaled down to 320×180
and grey (enough to judge quality, many times faster). On every frame it measures:</p>
<ul>
<li><b>Sharpness</b> (focus): how much fine detail the picture has. An out-of-focus frame has very little.</li>
<li><b>Exposure</b>: the average brightness (on a 0–255 scale) under 45 = too dark, over 210 = too bright; plus the "burnt" part of the
picture (almost white): more than 15% of the frame is penalised.</li>
<li><b>Contrast</b>: a washed-out picture (low contrast) or a harsh one (very high contrast); the middle is ideal.</li>
<li><b>Camera movement</b>: how far the picture moved since the previous frame. This shows the <b>jerks</b> (shake) and the
<b>fast moves</b> from one person to another.</li>
<li><b>Activity</b> in the frame: how much the picture changes (people moving) and how sharp the centre is. This is "Visual Importance".</li>
</ul>
<p>The analysis runs <b>once</b>. After it, every slider or switch only recalculates on the data already measured, so the result
changes instantly. Older results stay in <b>History</b> (right), to reopen them.</p>
<p>The analysis screen: the clips being analysed now at the top, the progress in the middle (Pause / Cancel), the finished ones below.
It also runs in the background: come back from Analysis Queue &gt; Open or from the project with View analysis.</p>

<h3>Auto mode: how the score works</h3>
<p>Auto is the classic way: it keeps only what is good and puts everything on <b>one track</b>, shot after shot. The app takes every
second of the clip and scores three things, each from 0 to 100%:</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Criterion</th><th>Weight</th></tr>
<tr><td>Sharpness (focus)</td><td>40%</td></tr>
<tr><td>Stability (shake)</td><td>30%</td></tr>
<tr><td>Exposure</td><td>30%</td></tr>
</table>
<p>Then the final score (0–100) = <b>60% the average above + 40% the weakest</b> of the three. So one big flaw (very shaky, very dark
or very soft) pulls the score down even when the other two are perfect.</p>
<h3>How shake is measured</h3>
<p>What counts is the <b>jerks</b>, not the movement itself. A smooth pan or a gimbal moving evenly scores well on stability; hand
shake and bumps lower it. The app compares the picture's movement between two measurements (8 times per second):</p>
<ul>
<li>very small jerks (under ~0.5% of the frame width) → stability <b>100%</b>, not penalised at all;</li>
<li>medium jerks (~1.7% of the width) → <b>50%</b>;</li>
<li>big jerks (~3% of the width or more) → <b>0%</b>.</li>
</ul>
<h3>The Auto controls</h3>
<ol>
<li><b>Selection threshold</b> (20–90, default 60): only the seconds scoring at least this much are kept. Examples at 60: a sharp,
well-exposed shot can drop to ~31% stability and still stays; if the focus is only 70%, the stability must be at least ~43%.</li>
<li><b>Cut out camera moves</b> (on): when you move the camera from one person to another faster than ~20% of the frame per second (or
the whole picture changes at once, like a whip pan), the move is cut out and every person becomes a separate shot. Example: 3 people
filmed 2 s each with moves between them = 3 shots. Slow pans are not cut. Off: the moves stay in when they score well.</li>
<li><b>Minimum cut length</b> (1–10 s, default 3 s): in Auto, kept shots shorter than this are dropped.</li>
</ol>
<h3>To get the most out of Auto</h3>
<ul>
<li><b>Handheld party</b>: threshold <b>50–55</b>; otherwise it throws away too much.</li>
<li><b>Tripod or gimbal</b> (church, speeches): threshold <b>65–70</b>, only very clean shots stay.</li>
<li><b>Too many short pieces</b>: raise the minimum cut length to 4–5 s.</li>
<li><b>You stay ~2 s on each person</b> when filming the guests: set the minimum cut length to 2 s, or their shots disappear.</li>
<li><b>You want the slow moves between people</b> in the selection: turn off "Cut out camera moves".</li>
<li><b>Too many slightly soft shots</b>: raise the threshold (focus weighs the most, 40%).</li>
</ul>

<h3>Custom mode</h3>
<p>Custom gives you control over every criterion and throws nothing away: it splits all the footage into <b>Poor / Fair / Good</b>
(red / yellow / green) on <b>3 tracks</b> (V1 Poor, V2 Fair, V3 Good). The scores are given on <b>2-second</b> pieces.</p>
<p><b>The 5 criteria</b> (each with a switch and a 0–100 slider):</p>
<ul>
<li><b>Contrast</b> (default 50): penalises washed-out or harsh pictures.</li>
<li><b>Exposure</b> (default 50): too dark (brightness under 45/255), too bright (over 210/255) or burnt areas (over 15% of the frame).</li>
<li><b>Blur / Focus</b> (default 60): soft shots.</li>
<li><b>Visual Importance</b> (default 40): how much is happening in the frame (60% people moving + 40% sharpness of the centre). It is a
"soft" criterion: it raises the score of shots with action but never lowers a score as a "flaw".</li>
<li><b>Shakiness / Stability</b> (default 50): shake (the same jerks as in Auto).</li>
</ul>
<p><b>What the slider means</b>: how much the criterion <b>counts</b> compared with the others, not a threshold. The values are compared
with each other: Focus 60 and Contrast 30 means focus counts twice as much. Switch off = the criterion does not count at all. The score
of a piece = 60% the weighted average + 40% the weakest criterion switched on (without Visual Importance).</p>
<p><b>Strictness preset</b> and <b>Quality threshold</b> (the bar with two handles): Custom splits by <b>percentages of all your footage</b>,
not by a fixed score. The weakest X% become Poor, the next ones Fair, the rest Good:</p>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Preset</th><th>Poor</th><th>Fair</th><th>Good</th></tr>
<tr><td>Lenient</td><td>15%</td><td>35%</td><td>50%</td></tr>
<tr><td>Normal</td><td>25%</td><td>40%</td><td>35%</td></tr>
<tr><td>Strict</td><td>35%</td><td>40%</td><td>25%</td></tr>
</table>
<p>Drag the handles to choose the percentages yourself (the preset becomes Custom). Because it is relative, even a perfectly filmed
wedding has some Poor: its weakest pieces.</p>
<p><b>Protect good frames</b> (on): so good shots are not punished just because the footage is good overall: a piece scoring above
<b>65</b> is never Poor, and one above <b>85</b> is never Fair.</p>
<p><b>Minimum cut length</b> in Custom: pieces shorter than this are joined to the neighbour with the closest level (not thrown away).</p>
<h3>Output settings</h3>
<ul>
<li><b>Save Results File In</b> and <b>Filename</b>: where the XML is saved and its name.</li>
<li><b>Output Software</b>: Premiere Pro or DaVinci Resolve (the same XML; only the instructions change).</li>
<li><b>Sequence Settings</b>: Frame size (Match footage = like the footage), Frame rate (default <b>25</b>, like all your final sequences),
Fields (Lower Field First / Upper / Progressive).</li><li><b>Generate Result File</b> writes the XML.</li>
<li>Every cut has its own sound on A1/A2, linked to the picture (files with more than 2 channels, like FX6 MXF, use channel 1). The
clips' colours: red / yellow / green by level.</li>
</ul>
<h3>What it does not do</h3>
<ul>
<li>It does not listen to the sound: the choice is on the picture only.</li>
<li>It does not recognise people. "Importance" means "something moves in the frame", not "the bride is in the frame".</li>
<li>It does not change your files.</li>
</ul>

<h2>Multicam: Sync</h2>
<p>Multicam syncs every camera to the mixer recorder, then (optionally) edits. Two separate steps: <b>Sync</b> (fast, sound only) and
<b>Auto Edit</b> (slow, video analysis). Auto Edit cannot be pressed until a sync exists.</p>
<h3>The steps</h3>
<ol>
<li><b>Drop all the material</b>: cards, recorder, whole folders. Side files are ignored automatically.</li>
<li><b>Sync</b>: finds the audio master (the recorder's audio-only files; without a recorder, the longest clip with sound), syncs every
clip by sound and groups the clips into cameras.</li>
<li>Check: the <b>Clips</b> tab ("Check" or "Failed" clips; fix the offset with a double click on Start) and the <b>Cameras</b> tab
(two cameras that are really one: give them the same name and they merge; the Static / Handheld role, if wrong).</li>
<li>You can already <b>Export XML</b>: every camera on its track with the whole synced clips, plus the recorder. If you edit yourself,
stop here.</li>
</ol>
<h3>How it syncs</h3>
<ul>
<li>It listens to every channel separately and takes the loudest (works with mono on 2 channels, an empty channel or multi-channel
recorders). Sony MXF files with several sound tracks are read in one pass.</li>
<li>It uses the clocks as hints (camera timecode, the recorder's time, the file date): the first clip of each camera is searched in the
whole recorder, which gives that camera's clock error; the next clips are searched only ±90 s around the predicted place (~18x faster),
with a full search when they are not found.</li>
<li>The fast search first scans the whole recorder on a loudness contour, then checks exactly (GCC-PHAT) only ±1.5 s around the
candidates. On repetitive music a second pass re-checks every piece.</li>
<li>At the end you see how long reading the files took and how long searching. If reading takes long, the disk is the slow part (an
external HDD is much slower than an SSD).</li>
</ul>
<h3>The colours on the map (Sync Map)</h3>
<ul>
<li><b>Green = High</b>: sure (every piece listened to agrees).</li>
<li><b>Yellow = Medium</b>: very likely right (at least 2 pieces agree).</li>
<li><b>Orange = Check</b>: unsure position. It goes to the separate "· check sync" track and is not used in the automatic edit.</li>
<li><b>Red = Failed</b>: could not be placed ("no usable sound" = no useful sound, e.g. a gimbal with the mic off).</li>
<li><b>Purple = By time</b>: the drone and cameras without sound, placed approximately by time (corrected by the other cameras' clock
error), whole clip; not in the automatic edit.</li>
</ul>
<p>A camera cannot film two things at once: if two clips of the same camera overlap, the less sure one goes to "check sync".</p>
<h3>Lavaliers and recorder</h3>
<p>The main recorder is the audio-only folder with the most hours (the mixer's). The other audio-only folders (LAV I, LAV II) are synced
to it and exported whole on their own audio tracks.</p>
<h3>Import XML (synced in another app)</h3>
<p>If you already synced in Syncaila, Premiere or DaVinci, export an XML (FCP7 XML) with every camera on its track and press Import XML.
The positions are taken exactly (no new sync), every video track becomes a camera, the audio-only files become the recorder. Clips that
are not on this computer are skipped, with a warning.</p>
<h3>If you add files later</h3>
<p>Press Sync again, then Auto Edit. The second time only the new clips are analysed.</p>

<h2>Multicam: Auto Edit and Auto Director</h2>
<p><b>Auto Edit</b> analyses the video of every synced clip (the same analysis as Footage Selection), sets the cameras' roles (unless you
changed them) and builds the edit. The analysis is saved: the second time only new clips are processed. Every Auto Director control on
the right applies <b>instantly</b>, without a new analysis; the map shows the result right away.</p>
<h3>How it picks the camera</h3>
<ul>
<li>Every camera gets a quality score every half second, with <b>the same formula as Auto</b>: sharpness 40%, stability 30%, exposure
30%, and 40% of the score is the weakest criterion.</li>
<li><b>Handheld cameras</b> are also judged against their own footage: half of the stability score is absolute, half is compared with
that camera's usual shake (a little wobble is part of its look).</li>
<li><b>Static cameras</b> get a bonus of up to <b>+10 points</b> when something happens in the frame (people moving).</li>
<li>During a <b>camera move</b> (from one person to another) that camera's score drops to 15%: it almost never cuts to a move.</li>
<li><b>Static / Handheld</b> is guessed by itself: static = the camera practically never moves. Change it in the Cameras tab.</li>
<li>Then the app finds the best path through the cameras, respecting the shot lengths and the pace below.</li>
</ul>
<h3>The Auto Director controls</h3>
<ul>
<li><b>Minimum shot</b> (1–10 s, default 3 s): no shot is shorter (on a drop, the drop option wins).</li>
<li><b>Maximum shot</b> (4–120 s, default 30 s): a shot longer than this is interrupted with the best other camera.</li>
<li><b>Cut pace</b> (0–100, default 50): how easily it changes camera. 0 = calm, changes rarely (only when another camera is much better);
100 = fast, changes often. Technically: the "cost" of a change goes from 20 points (at 0) down to 2 points (at 100).</li>
<li><b>Static ↔ Handheld</b> (0–100, default 60): left prefers the static cameras, right the handheld ones, by up to 25 points either
way. 50 = neutral. If you see the static camera too often (it never shakes, so it always looks "good"), drag to the right.</li>
<li><b>Cut on the beat</b> (on): on music, the cuts follow the recorder's beats and bars; on speech, the cuts fall in the pauses between
sentences. Off: the edit on a 0.5 s grid, like at the start.</li>
</ul>
<h3>Learn my editing style…</h3>
<p>Pick the XML of a party you edited (exported from Premiere). The app measures how you cut: your usual shot length (the shortest 15% →
Minimum shot, the longest 5% → Maximum shot), the pace, how much you use the handheld cameras, how often you cut on drops. It shows what it
measured; choose <b>Use for this project</b> or <b>Use as my style</b> (then every new project starts with your settings). The music is
measured only if that XML's recorder files are on this computer. The style is saved on this computer only.</p>
<h3>Export XML</h3>
<p>One 25 fps sequence: <b>V1…Vn</b> one track per camera, each holding only its cuts of the edit (it plays as the final edit);
<b>A1/A2</b> the whole recorder; then one audio track per camera, whole and switched on. On top, the <b>alternative angle</b> track (see
the next page), switched off. It works in Premiere (File &gt; Import) and DaVinci (File &gt; Import &gt; Timeline).</p>

<h2>Multicam on the music</h2>
<p><i>Drop, build-up, Slower cuts zones, the alternative angle.</i></p>
<p>With <b>Cut on the beat</b> on, Auto Edit reads the recorder's music (once, then it stays saved): the tempo of every part (it follows
the DJ's song changes and a live band's drifting tempo), every beat, the start of every bar, the build-ups, the drops and the speech.</p>
<p><b>Beat</b> = the clap you'd clap along (1, 2, 3, 4). <b>Bar</b> = 4 beats. On a club song (128 BPM): 1 beat ≈ 0.5 s, 1 bar ≈ 2 s.</p>
<h3>What happens on the music</h3>
<ul>
<li>Shots start on the beat, usually on the start of the bar, and last 1–4 bars: shorter when the song is intense, longer when it is calm
(automatic, always on). Minimum shot and Cut pace set the base rhythm.</li>
<li>Every cut falls <b>1 frame (40 ms) before the beat</b>: the eye sees the change a little late, so it looks exactly on the hit.</li>
<li>Where the beat is not clear (a ballad without drums, speech) no beats are invented: there it cuts in the pauses between sentences or
the old way.</li>
<li>The <b>Music</b> row on the map shows every song with its tempo, intensity (brighter = more intense), speech (grey) and drops (pink line).</li>
</ul>
<h3>On a drop, change camera every (all projects)</h3>
<p>The drop = the moment the heavy bass comes in after the music "rises". One cut falls exactly on the drop, then the camera changes every:</p>
<ul>
<li><b>1 beat</b> (~0.5 s): very aggressive; only with many good cameras (5+).</li>
<li><b>2 beats</b> (~1 s): music-video pace; DJ / electronic, 4+ cameras.</li>
<li><b>1 bar</b> (~2 s, default): energetic but easy to follow.</li>
<li><b>2 bars</b> (~4 s): calmer; 2–3 cameras or a quieter party.</li>
<li><b>4 bars</b> (~8 s): almost no speed-up.</li>
</ul>
<p>The rule: the more cameras with good shots you have, the faster you can go.</p>
<h3>Build-up before a drop</h3>
<ul>
<li><b>Hold one shot until the drop</b> (default): one camera for the whole build-up (up to 8 bars), then a cut exactly on the drop. The
contrast makes the drop "hit"; works with few cameras too.</li>
<li><b>Cut faster and faster</b>: cuts closer and closer (2 bars, 1 bar, 2 beats) until the drop. Teaser-like tension; good for DJs and
many cameras.</li>
</ul>
<h3>"Slower cuts" zones (folk music, hora)</h3>
<p>With a live band and an ever-changing tempo, cuts on bars do not fit. Drag the mouse over that part of the map and a yellow zone
appears. Inside it the cuts fall on the nearest accent in the sound (±0.3 s), with <b>your hora settings</b>, whatever the rest of the
party uses: Minimum shot <b>6 s</b>, Maximum shot <b>120 s</b>, Cut pace <b>50</b>, Static ↔ Handheld <b>45</b>. Drag the edges to move it;
under the map type the exact time (h:mm:ss.s); right click or Delete removes it. The zones stay saved.</p>
<h3>The alternative angle</h3>
<p>In the XML, above the edit, a switched-off track with the second best camera for every shot (clips named "ALT · camera"). If you do not
like a shot, switch the track on or drag the alternative down. Shots on the static camera get no alternative (you are safe there anyway).</p>
<h3>Example</h3>
<p>DJ, 4 cameras, default settings: the calm verse with 2–4 bar shots, the build-up held on one camera, a cut exactly on the drop, then
another camera every bar, calmer again after the drop. Try "1 bar" and "2 beats": the change is instant.</p>

<h2>Teaser Studio</h2>
<p>The short film on your music: teaser (~50 s), getting ready (~70 s), church (~45 s), couple (~23 s), venue (~20 s), then the party
(the usual lengths measured on your 6 films). Every wedding is a project (card): <b>+ New Project</b>, click to open, ✕ to delete,
<b>← Projects</b> to go back. Every project remembers the footage, music, moments and photos.</p>
<h3>1. Footage (your selects)</h3>
<p>In Premiere put the selects in a sequence and Export XML. <b>Only the colours matter</b> (Premiere labels: right click the clip &gt;
Label):</p>
<ul>
<li><span style="color:#f08ccb">■</span> <b>Rose</b> bride · <span style="color:#3f63e0">■</span> <b>Blue</b> groom ·
<span style="color:#9b4fc2">■</span> <b>Purple</b> couple · <span style="color:#9a6233">■</span> <b>Brown</b> church</li>
<li><span style="color:#e3cf3e">■</span> <b>Yellow</b> / <span style="color:#22b8a5">■</span> <b>Caribbean</b> venue ·
<span style="color:#6d78d6">■</span> <b>Iris</b> party (and the morning first look) · <span style="color:#b29de6">■</span>
<b>Violet</b> drone</li>
<li><span style="color:#1f9e96">■</span> <b>Teal</b> getting-ready location · <span style="color:#f39c2c">■</span> <b>Mango</b> vornic</li>
<li>Ignored: <b>Tan</b> (interviews), <b>Forest</b> (nests), <b>Lavender</b> (adjustment layers) and clips without a colour.</li>
</ul>
<p>Order and tracks do not matter: the order of the day comes from the recording time. A selection can be longer (e.g. 10 s of party):
on import every selection is analysed once (sharpness, stability, exposure, movement; 4 measurements per second) and its best part is
used: with movement on the drop and at the party, calmer in getting ready and church. The analysis can be stopped (Cancel), is saved every
25 selections and continues where it stopped. You can generate before it ends. Clips interpreted at another frame rate in Premiere (50p as
25p) are read correctly.</p>
<h3>2. Auto or Blueprint (one or the other)</h3>
<ul>
<li><b>Auto</b>: cuts on the beat of your music (below).</li>
<li><b>Blueprint</b>: uses one of your finished short films as a template. <b>+ Add</b>: pick the film's XML, a name and the style (Modern
or Traditional). The cuts, music, sound effects and pacing stay exactly as in your film; every cut is filled with a shot of the same colour
from the new wedding (its best part, in the order of the day, no moment twice). Tan stays an empty place with an "Interview here" marker;
the old wedding's camera and recorder sound is not kept. No music needed (the music card disappears). Blueprints are saved on this
computer, for every project.</li>
</ul>
<h3>3. Music (Auto only)</h3>
<p>The songs already joined: one audio file or the XML of your music edit (the XML shows the exact song changes, even inside one file cut
with crossfades). The app finds the beats and the drop and proposes the <b>six moments</b> (m:ss), which you can correct (a wrong time
turns red):</p>
<ul>
<li><b>Drop</b>: the drop of the teaser song (the biggest bass rise).</li>
<li><b>Teaser ends</b>: getting ready starts here.</li>
<li><b>Getting ready ends</b>: the church starts here.</li>
<li><b>Church ends</b>: the couple shots come here, over the end of the vows (~23 s before the party song).</li>
<li><b>Party song starts</b>: the party song and the venue presentation (venue, drone).</li>
<li><b>Venue ends</b>: the party itself starts.</li>
</ul>
<p>The times must go forward, in the order above. <b>Detect again</b> recalculates them from the music.</p>
<h3>4. The couple (optional)</h3>
<p>One good photo of the bride and one of the groom (from the wedding day), then <b>Find them in the selections</b>. Local, free face
recognition (the models download once). Every selection is read once for both; the result stays saved. When generating, the bride, groom,
couple, church and party shots prefer the selections where they appear. Not used for the first dance.</p>
<h3>Generate, Shuffle, Export</h3>
<ul>
<li><b>Generate</b> builds your structure: teaser (before the drop getting ready, church, couple, drone; after the drop party alternating
with couple), bride / groom getting ready (with couple shots among them, more towards the end), the church with the couple at the end, the
venue (opening with the drone filmed closest to it), then the party. Every cut falls on the beat.</li>
<li><b>Shuffle shots</b> picks other shots, keeping the order of the day.</li>
<li><b>Export XML</b>: the shots on V1 with your colours, the music on A1/A2 and a marker for every part (Teaser, DROP, Getting ready,
Church, Couple + vows, Party: venue, Party), to place the testimonials and vows.</li>
</ul>
<h3>The picking rules</h3>
<ul>
<li>A moment is never used twice (not in the teaser and again in the film).</li>
<li>The same clip never appears twice in a row when there is another.</li>
<li>One piece of every selection first, only then a second piece of the same selection.</li>
<li>Church and venue open with the drone shot filmed closest to them; the teaser uses the drone only with more than 2 drone clips.</li>
<li>Morning Iris = first look (goes to getting ready); Iris after the church = party.</li>
<li>A cut is filled only by a piece long enough; when footage runs out the previous shot runs longer (never a repeat), and the app tells
you how many seconds were left uncovered.</li>
</ul>
<h3>AI test (experimental)</h3>
<p>Checks whether a free AI model (SigLIP 2, runs on the Mac) recognises your shots like your labels. <b>Quick test</b> (25 selections per
colour, a few minutes) or <b>every selection</b> (slow, overnight; the Mac does not sleep while it runs). The first time it downloads the
model (a few GB). It is only a test: it does not change the teaser.</p>

<h2>Long Film</h2>
<p>The long film up to the party, pre-edited from your selects the way you edit it (measured on two of your weddings: selects + final
film). You add the music, interviews (Tan) and finishing in Premiere; the party is the Multicam edit. Projects on cards, like Teaser Studio.</p>
<h3>The cards of the page</h3>
<ol>
<li><b>Footage</b>: the XML of your selects sequence (see the page "What your selects need" and the drawing at the bottom of the page). It
shows the cameras found, how many selections each has and whether something is wrong (for example selections lost after the drone, with
the exact explanation).</li>
<li><b>Auto or Blueprint</b> (one or the other). Blueprint uses one of your finished long films as a template (Long Film blueprints are
separate from Teaser Studio's): the cuts, music, effects and pacing stay, every cut is filled with a shot of the same colour from the new
wedding, Tan stays a place with an "Interview here" marker, and empty stretches over 60 s (the party) get a "Party (the Multicam edit)"
marker. In Blueprint the vornic is filled cut by cut; for the vornic synced on two cameras use Auto.</li>
<li><b>Teaser</b> (Auto only): the Teaser Studio project of the same wedding; its teaser (with its music) opens the film.</li>
<li><b>Build</b>, then <b>Export XML</b>. The length shown is the FILM's length, not a waiting time.</li>
</ol>
<h3>What Auto does, part by part</h3>
<ul>
<li>The <b>copies</b> at the end of your selects (everything after the last drone shot, plus any selection repeating a piece already
selected) are not used: they are for the short film.</li>
<li>The <b>cameras</b> are recognised by their files (name without digits + picture size + frame rate), and every camera's day by its file
numbers. The main camera = the one with the most groom / bride shots. Camera clocks are never compared between cameras.</li>
<li><b>Getting ready</b>: the short groom and bride selections (up to 8 s), without the first ~15% of each side, the middle of each
(0.8–2 s); told in parallel, in blocks like yours: a big block of whoever was filmed first (~27% of their shots, 4–20), a big block of
the other (~20%, 4–14), then turns of 1–7 (usually ~4) sized so both end together. Teal first.</li>
<li><b>Vornic and first look</b>: the main camera's long morning selections (groom / bride over ~1 min = vornic, Iris over 15 s) whole on
V1, with continuous sound. The second camera is found by sound (even without a church on it) and put whole on V2 (track off), with its
sound on A3/A4; on V3 alternating pieces of ~3–4 s, in the speech pauses. Only sure matches are used, in the order of the day. The short
morning Iris follow as a montage (~2 s).</li>
<li><b>Church</b>: every Brown shot in your timeline order; short ones whole, from long ones (over 15 s) a few 6 s pieces.</li>
<li><b>Couple and venue</b>: drone, the first venue block, drone, the first couple block, with a drone every ~7 shots; ~1.3–1.6 s each.</li>
<li>Every shot keeps your colour and has its sound linked to the picture; the teaser has its music on A5/A6; one marker per part, in the
app's language. It is a pre-edit: the exact rhythm on the music and the final choice are yours.</li>
</ul>

<h2>What your selects need</h2>
<p>What the XML you give each feature must have. The colours are your Premiere labels: Rose bride, Blue groom, Purple couple,
Brown church, Iris first look / party, Teal getting-ready location, Mango vornic, Yellow or Caribbean venue, Violet drone.
Tan (interviews), Forest (nests) and Lavender (adjustment layers) are ignored.</p>
<ul>
<li><b>Card Offload, Create Project</b>: no selects needed.</li>
<li><b>Footage Selection</b>: raw clips, any order (Add Folder or Import XML; the export keeps the list's order).</li>
<li><b>Multicam</b>: dump everything, any order; the cameras are synced by sound. Import XML: an already synced timeline (every
video track = a camera).</li>
<li><b>Teaser Studio (Auto)</b>: <b>only the colours</b> matter. Order and tracks do not (the day's order comes from the recording
time). Clips without a colour are not used. Plus your music.</li>
<li><b>Long Film (Auto)</b>: <b>random does not work</b>. It needs:
<ul><li>a colour on every selection (no colour = not used);</li>
<li>the church (Brown) in the order you want it in the film;</li>
<li>the drone block after everything else: only copies for the short film may come after it (they are left out). If many
selections are after the drone, the app tells you in red exactly what is wrong: which is the last drone shot and where it ends on the
sequence, how many selections of each colour are lost after it and which is the first.</li></ul>
Everything else can be in any order and on any tracks: the cameras are recognised by their files and every camera's day by its
file numbers. The second camera does not need a church: without Brown, its first look is found by sound.</li>
<li><b>Blueprint</b> (Teaser Studio and Long Film): your finished film with the colours on its clips (so it knows what every cut
shows) and the new wedding's selects with the same colours, in any order.</li>
<li><b>Transcribe</b>: any file with sound; Import XML takes the clips in the timeline's order.</li>
</ul>
<p>The Long Film page has a drawing of the order at the bottom: trains of colours, the name of each above it and the cameras under it.
With 3, 4 or 5 cameras it continues the same way, one after the other; couple shots can sit in the middle of the party; the drone stays last.</p>

<h2>Transcribe</h2>
<p>Interviews, speeches, the vornic or the sermon become text, on this computer, for free (Whisper; nothing is uploaded).</p>
<h3>Steps and options</h3>
<ul>
<li><b>+ Add files</b>: sound (lavaliers, recorder) or video.</li>
<li><b>Import XML</b> (recommended for the story): your Premiere sequence with the interviews one after the other (File &gt; Export &gt;
Final Cut Pro XML). Every interview is a segment (the clips that start and end together), for example the groom = Color Matte +
lavalier, the bride = the FX6 MXF with its 4 tracks. From every segment the file to transcribe goes into the list: the lavalier when it
is separate, otherwise the camera. The story then copies <b>exactly your clips</b> from this sequence (the same sound tracks, mic and
lavalier, Color Matte), only with other times.</li>
<li><b>Language</b>: Romanian, English or Detect it.</li>
<li><b>Precision</b>: <b>Fast</b> (large-v3-turbo: several times faster) or <b>The most precise</b> (large-v3 at full precision: slower,
best on names and rare words). The first time the model downloads once (1.5–3 GB).</li>
<li><b>What it does to understand better</b>: it listens to the file's <b>clearest channel</b>, not a mix. On the FX6 the camera mic and
the lavalier are on different channels, and the app picks the one where the speech stands out most over the noise (the lavalier). From
the wedding folder's name ("NUNTA 22 AUGUST 2026 Florin si Miruna") it takes the couple's names, to write them right. Every sentence's
times come from its first and last word (tighter cuts). The text is split <b>into sentences</b>: cut at . ? ! and at pauses longer
than 0.6 s; a piece lasts at most 8 s (a longer one is cut at the best real pause, preferably at a comma or a linking word "and", "but",
"because"…; when there is no pause at all it is a <b>forced cut</b>, at the quietest point of the sound between 5 and 8 s, listed as
such in the report), so it
can be interleaved. Pieces under 0.8 s and pieces with only "uh", "so", "like" are joined to the closest neighbour (as long as they
stay under 8 s); a short but whole sentence ("Yes, definitely.") stays alone. Your short lines ("Perfect", "Bravo", "Thank you") are
marked as questions. When Whisper forgets the full stop ("again Then she"), a word with a capital letter in the middle of a line, after
a word without punctuation, starts a new sentence (except names: a word that appears only with a capital letter in the whole interview, like "Mamaia", "TikTok" or the
godfather's name, is recognised as a name by itself; a common word of the language, one of the first 5000, that appears only once with
a capital letter, like "Asta" or "Mi-a", starts a sentence; a sentence never starts right after "cu", "pe", "la", "și"; the couple's
names from the folder and the first names typed in the list are always names), so a question glued to an
answer ends up separate. A short piece is never glued to a question. When Whisper gives no time for each word, that part is
transcribed again on its own; if that fails too, the times are estimated from the letters and every cut is moved to the closest real
pause in the sound (±0.6 s). In the list, an interview with pieces over 8 s has ⚠. In the .txt the times have tenths
([00:00:05.2]). When Whisper
loops and repeats one sentence, the repeats are removed.</li>
<li><b>Who speaks, measured from the sound</b>: before transcribing, the app finds the speech and the real pauses (the Silero
detector, on this computer) and measures who speaks. You are far from the lavalier: when the file also has the camera microphone
(FX6), for you the lavalier is about as loud as the camera mic, for the couple 10–19 dB louder; with one channel only, your voice is
10–15 dB weaker. Your lines (questions, "Bravo", "Say it in the second person") are marked [QUESTION] from the sound, even without a
"?", and a question said by the couple ("Did you make it?") stays theirs. Where the difference is not clear the line has (?) and the old
text rule decides. Then every stretch between pauses, with one speaker, is transcribed on its own, so your question no longer sticks to
the answer. Sentences are cut only at real pauses (punctuation only chooses among them); after a "?" always. In the interview with both
at once, with a lavalier each on different channels, every piece gets [S1] or [S2] and Claude finds out from what they say who is who;
with one lavalier for both, their voices cannot be told apart from the sound (Claude decides from the text).</li>
<li><b>Quality</b> (under the text) and <b>Quality report</b>: after every transcription the app checks itself, measuring from the
sound: how many codes pass 8 s (target 0), how many are under 0.8 s, how many have a "?" in the middle (a question glued to an
answer) and how many borders between codes have a real pause between them (target 95 % or more; forced cuts are counted on their own), with the
list of those that fall in speech, plus how surely your voice is told apart from the couple's, how many of your lines were marked
[QUESTION] from the sound and how many pieces are unsure.
The report is saved next to the file (<i>name</i>_raport.txt). Green = every target met, red = something to check. For the story the
cut in / out points are measured the same way and the report is saved next to the XML.</li>
<li><b>Test on several weddings…</b>: choose a folder (e.g. <i>teste</i>) with one sub-folder per wedding (the interviews + the source
XML from Premiere, if you have it). The app transcribes them all, measures them as above, makes a test story of each (every code,
alternating the interviews) and checks its cuts and XML. The result is a table: red = under the target, ▼ = worse than the previous
version (the numbers of every version stay in rezultate.json, in the test folder). Choose 3–4 weddings as different as possible:
FX6 on 4 tracks, lavaliers only, the interview with both at once, bad sound (outside, wind).</li>
<li><b>Speed</b>: on M1–M4 Macs the transcription runs on the graphics chip (Apple MLX), several times faster than on the processor; if it
does not work, the app switches to the processor by itself. On Intel Macs it runs on the processor.</li>
<li> Some words can still come out misspelled: Claude understands them from the
context and writes the corrected text in the story's markers.</li>
<li><b>Transcribe</b>: next to every file a .txt (the text with times) and a .srt (subtitles). The text shows on the right; <b>Copy the
text</b> puts it on the clipboard.</li>
<li><b>Remove</b> (or the Delete key): takes the selected file off the list. The file and its transcript stay on the disk.</li>
</ul>
<h3>The story of the interviews (with Claude)</h3>
<p>Claude reads the couple's interviews, finds their story and weaves them into <b>one story told by both</b>: one continues the other's
thought, with a beginning, a middle and an ending. The story is as long as it needs to be: it is not shortened by force. It uses only whole
sentences, exactly as they said them; it invents nothing. It works through <b>your Claude subscription</b> (no key, no extra cost).</p>
<p><b>How it weaves them:</b> you ask both the same things (how you met, what the groom / bride is like, what you love about him / her,
what you wish for, a message to the other), so every theme has her version and his. Claude cuts from one to the other on the same
theme, often, in short pieces, as if one continued the other's thought (he says what he loves about her, then she what she loves about
him). The order: how they met, how they see each other, what binds them, the future, and at the end their messages (the emotional
ending). The result is an XML with the pieces already cut and in order: import it into Premiere and the story is edited.</p>
<p><b>Your questions never go into the story.</b> The interviews go "you ask, the couple answers": sentences ending with "?" are
marked as questions and never used (not even inside a piece), and Claude gets the rule to leave out your short lines too ("Perfect!",
"Bravo!", "Thank you!") and the jokes at the end. With one interview, Claude makes that person's story flow as if told without
questions.</p>
<ol>
<li>Transcribe the interviews and <b>tick</b> in the list what goes into the story (the ones marked ↻ were transcribed by an older
version, in long pieces: Transcribe redoes them in sentences). <b>Who is speaking</b> is optional: when you do not set
it, Claude finds out from what they say which interview is the groom's and which the bride's (the names come from the wedding folder),
and the list is filled in after the answer. Next to it you can write the <b>first name</b> (e.g. Florin): it goes into the request to
Claude and into the story's markers.</li>
<li><b>1. Copy for Claude</b>: the app copies the transcripts (every sentence with a code: A1, A2… for the first interview, B1… for the
second) with a request already written and opens a <b>new chat</b> in Claude. Paste (Cmd+V) and send.</li>
<li>When Claude has answered, copy the whole answer (the copy button under it) and press <b>2. Paste Claude's answer</b>: a window
opens where you paste the answer (if it is already copied, it is there by itself), then <b>Make the story XML</b>. Under the buttons
it always says which step you are at.</li>
<li>You get an XML: the pieces one after the other (picture + all the sound, 0.12 s before and 0.2 s after, never into the
neighbouring sentence), a marker on each (who speaks and what, the text corrected by Claude); the story's text shows in the app. Two
pieces of the same file never overlap (not even one frame), however they are placed in the story: if they would touch, the cut moves to
the middle of the pause between them. The start and the end of every piece fall into a real pause of the sound when there is one close by. The
sequence is named like yours, with " - STORY" at the end.</li>
</ol>
<p><b>The story check.</b> Before writing the XML, the app checks Claude's answer and then the XML itself. <b>Errors</b> stop everything
and the XML is <b>not</b> written: a code that does not exist, a range across two interviews or going backwards, one of your lines
([QUESTION]) used, the same code twice, pieces that overlap, a piece past the end of the file, wrong links or times in the XML. The
window lists them all; <b>Copy for Claude</b> copies a fix request: paste it in the same chat, and paste the new answer at step 2.
<b>Warnings</b> leave the XML written and only tell you where to look: a line without a code (skipped), a question inside a range (left
out), transcript pieces longer than 8 s, a piece starting with "and / but / because" without the sentence before it, the same speaker
more than 3 times in a row. A theme where only one of them speaks cannot be checked automatically (the app does not know the themes):
have a look yourself.</p>
<p>The rules given to Claude, in short: only the couple's answers, whole sentences, frequent cuts between them on the same themes,
echoes next to each other, jokes whole (with the punchline) or not at all, no information said by both in a row, no piece that only
makes sense with the question, a strong opening and an emotional ending. Swearing may stay: you remove it when editing.</p>
<p>If Claude says you reached your limit, try again at the time Claude shows: the app remembers what you sent (even after a restart), so
you only press step 2 when you have the answer, or step 1 again in a new chat. Lines of the answer without a code are skipped and show in
the check.</p>

<h2>Analysis Queue</h2>
<p>Shows everything running now: Footage Selection analyses, Multicam Sync and Auto Edit, the Teaser Studio selection analysis, the
Long Film build, Card Offload, Create Project and Transcribe (the Claude story too), with progress. <b>Open</b> takes you to the job. You can work elsewhere while it runs; the jobs run in the background.</p>

<h2>Settings</h2>
<h3>Performance</h3>
<ul>
<li>The cards at the top: the processor (how many cores), the total RAM, how much other apps use, how much is free and how much the app
uses now; below, the apps using the most memory.</li>
<li><b>Parallel jobs</b> (1 – the number of cores; default a quarter of the cores): how many clips are analysed / read at the same time.
Every job uses a few cores, so more than a quarter to a half of the cores brings little, and other apps (Premiere) get slower. <b>RAM is
not the limit</b>: the app keeps only small, scaled-down pieces in memory (usually under 1–2 GB). The time goes into decoding the video,
which is the processor's work (and the Mac's video decoder).</li>
<li><b>Hardware video decoding (Mac)</b> (on): the Mac's video decoder does part of the work (VideoToolbox) where the bundled FFmpeg
supports it; if a codec is not supported, the app falls back to the processor by itself.</li>
</ul>
<h3>Language</h3>
<p>English or Română: the whole app and these pages. It applies at the next start. Editing terms (Sync, Auto Edit, Export XML, Drop,
Build-up) stay in English, as in Premiere.</p>
<h3>Updates</h3>
<ul>
<li>At start the app checks by itself whether there is a new version and tells you. <b>Check for updates</b> checks any time.</li>
<li><b>Download and install</b> brings the version for your Mac (Apple Silicon or Intel) into Downloads, with a percentage in Settings, and
opens the DMG: drag MoneyMakingMachine into Applications (Replace), close the app and open it again.</li>
<li>If the check does not work, the message says why (no internet, the server refused for now, etc.).</li>
</ul>
<h3>Save error report…</h3>
<p>When something does not work: save the report and send it to Claude. It contains the app's log (what it did and the errors) and basic
information about the computer, no video. An error that repeats shows at most once a minute, never in a loop.</p>

<h2>Useful tips</h2>
<ul>
<li><b>Auto or Custom?</b> Auto keeps only the good shots, on one track. Custom grades everything (Poor / Fair / Good) on 3 tracks and
gives you control over every criterion.</li>
<li><b>The static camera shows too often</b> in Multicam? Drag "Static ↔ Handheld" to the right: the static camera never shakes, so it
always looks "good".</li>
<li><b>Timecode</b>: set it as close to the real time as you can. It does not need to be frame accurate (it is only a hint), but it makes
Sync much faster. The same for the camera clocks: the order of the day and Card Offload (only what was filmed at this wedding) depend on them.</li>
<li><b>Do not move or rename the files</b> after exporting: the XML points to their place on the disk; if you move them, Premiere asks you
to relink them (Link Media).</li>
<li><b>Camera proxies</b> (DJI .LRF, GoPro .LRV, Sony SUB/…S03.MP4) are ignored everywhere: they have the same sound as the original and
would double the camera.</li>
<li><b>Clips without sound</b> (gimbal with the mic off): in Multicam they show "Failed: no usable sound"; place them by hand (double click
on Start) or use Import XML from Syncaila.</li>
<li><b>Formats</b>: anything FFmpeg reads (MXF, MP4, MOV, MKV, AVI etc.). BRAW (Blackmagic) and R3D (RED) are not supported.</li>
<li><b>All final sequences are 25 fps.</b></li>
<li><b>Projects save themselves</b> on your computer. Deleting a project does not delete your clips.</li>
</ul>

"""

HELP = {"ro": RO, "en": EN}
