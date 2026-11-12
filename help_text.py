"""Info / How to use page content (HTML), Romanian and English."""

RO = """
<h1>Cum se folosește MoneyMakingMachine</h1>
<p>Aplicația are două tipuri de proiecte: <b>Footage Selection</b> (alege cadrele bune dintr-un set de clipuri) și
<b>Multicam</b> (sincronizează mai multe camere cu recorderul de la mixer și face montajul).</p>

<h2>Multicam: Sync și Auto Edit</h2>
<p>Întâi dai <b>Sync</b>, apoi <b>Auto Edit</b>. Auto Edit nu face sincronizarea, iar butonul lui nu se poate apăsa până nu
există o sincronizare. Sunt doi pași separați, făcuți așa intenționat: sincronizarea e rapidă, iar analiza video e partea
lentă, deci o rulezi doar dacă vrei montajul automat.</p>
<h3>Procesul complet</h3>
<ol>
<li><b>Arunci tot materialul în Footage</b>: carduri, recorder, foldere întregi. Fișierele auxiliare (XML-urile Sony,
poze etc.) sunt ignorate automat.</li>
<li><b>Sync</b> (rapid):
  <ul>
  <li>citește fiecare fișier și găsește masterul audio (fișierele doar-audio de la recorder);</li>
  <li>sincronizează fiecare clip pe sunet, folosind timecode-ul camerelor ca indiciu ca să caute mai repede;</li>
  <li>grupează clipurile pe camere și așază toate fișierele de recorder pe un singur timeline.</li>
  <li>După el ai harta, tab-urile Cameras și Clips, și poți deja da <b>Export</b>: în Premiere primești fiecare cameră pe
  pista ei, cu clipurile întregi sincronizate, plus recorderul. Dacă vrei să montezi singur, te poți opri aici.</li>
  </ul></li>
<li><b>Verifici și corectezi</b>, dacă e cazul:
  <ul>
  <li><b>Clips</b>: clipurile marcate „Check” sau „Failed”. Pe cele cu decalaj greșit le corectezi cu dublu click pe valoarea
  din coloana Start.</li>
  <li><b>Cameras</b>: dacă două camere detectate sunt de fapt una, le dai același nume și se unesc. Tot aici schimbi rolul
  (Static / Handheld) dacă programul l-a ghicit greșit.</li>
  </ul></li>
<li><b>Auto Edit</b> (lent, opțional):
  <ul>
  <li>analizează video-ul fiecărui clip sincronizat (claritate, tremur, expunere, mișcări de cameră);</li>
  <li>stabilește rolul camerelor, dacă nu l-ai schimbat tu;</li>
  <li>regizorul automat construiește montajul.</li>
  <li>Analiza se salvează. Dacă mai apeși o dată, clipurile deja analizate nu se mai procesează.</li>
  </ul></li>
<li><b>Reglezi montajul din dreapta</b>: minimum și maximum shot, ritmul tăieturilor, Static ↔ Handheld, cut on the beat,
static doar ca rezervă. Totul se recalculează instant, fără o nouă analiză, iar pe hartă vezi imediat rezultatul.</li>
<li><b>Export XML</b>: un singur sequence, fiecare cameră pe pista ei cu doar cut-urile ei, recorderul și sunetul
camerelor întregi.</li>
</ol>
<p><b>Dacă adaugi fișiere după:</b> dai din nou Sync, apoi Auto Edit. A doua oară se analizează doar clipurile noi, deci
merge mult mai repede.</p>
<h3>Lavaliere, dronă, camere fără sunet</h3>
<ul>
<li><b>Recorderul principal</b> e folderul cu cele mai multe ore de audio (recorderul de la mixer). Celelalte foldere doar cu
audio (de exemplu <b>LAV I</b>, <b>LAV II</b>) sunt sincronizate pe el și apar în export pe pistele lor audio, întregi.</li>
<li><b>Drona și camerele fără sunet</b> nu pot fi sincronizate pe sunet. Sunt așezate <b>aproximativ după oră</b> (timecode
sau ora din fișier, corectată cu eroarea de ceas învățată de la celelalte camere), apar în mov („By time”), pe pista lor,
cu clipul întreg, și nu sunt folosite în montajul automat.</li>
<li>La finalul sincronizării vezi <b>cât a durat</b> citirea fișierelor și cât căutarea. Dacă citirea durează mult, discul e
cel care încetinește (un HDD extern e mult mai lent decât un SSD).</li>
</ul>
<h3>Import XML (sincronizare făcută în altă aplicație)</h3>
<p>Dacă ai sincronizat deja materialul în <b>Syncaila</b>, Premiere Pro sau DaVinci Resolve, exportă de acolo un XML (FCP7 XML)
cu fiecare cameră pe pista ei și apasă <b>Import XML</b>. Aplicația preia pozițiile exact cum sunt (fără să mai sincronizeze),
fiecare pistă video devine o cameră, iar fișierele doar-audio devin recorderul. Apoi dai <b>Auto Edit</b> și <b>Export XML</b>,
ca de obicei.</p>
<p><b>Culorile de pe hartă:</b> verde = <b>High</b> (sigur), galben = <b>Medium</b> (foarte probabil corect), portocaliu =
<b>Check</b> (poziție nesigură), roșu = <b>Failed</b> (nu a putut fi pus). Pe rândul „Auto edit”, fiecare culoare e o cameră.
O cameră nu poate filma două lucruri deodată: dacă două clipuri ale aceleiași camere se suprapun, cel mai puțin sigur
ajunge pe pista „check sync”.</p>
<p><b>Pista „· check sync":</b> clipurile a căror poziție nu e sigură sunt puse toate pe o singură pistă separată și nu sunt
folosite în montajul automat. Le verifici în tab-ul Clips și le corectezi cu dublu click pe Start.</p>
<p><b>Export XML</b> merge și în Premiere Pro (File &gt; Import), și în DaVinci Resolve (File &gt; Import &gt; Timeline).</p>

<h2>Footage Selection: ce face „Analyze Footage”</h2>
<p><b>Ecranul de analiză:</b> sus clipurile analizate chiar acum, la mijloc progresul (Pause / Cancel), jos cele terminate.
Analiza merge și în fundal: revii din <b>Analysis Queue &gt; Open</b> sau din proiect cu <b>View analysis</b>.</p>
<p>„Analyze Footage” se uită la fiecare clip și dă o notă fiecărei porțiuni.</p>
<h3>Ce face, pas cu pas</h3>
<ol>
<li><b>Citește video-ul</b> cu FFmpeg (orice format, inclusiv MXF). Ia 8 cadre pe secundă, micșorate la 320×180 și
alb-negru. Nu are nevoie de mai mult ca să judece calitatea, și așa merge mult mai repede.</li>
<li><b>Măsoară pe fiecare cadru:</b>
  <ul>
  <li><b>claritatea</b>: cât de multe detalii fine are imaginea (un cadru neclar are puține);</li>
  <li><b>expunerea</b>: dacă e prea întunecat sau are zone „arse”;</li>
  <li><b>contrastul</b>: dacă imaginea e spălată sau prea dură;</li>
  <li><b>mișcarea camerei</b>: cât s-a deplasat imaginea față de cadrul anterior. Așa deosebește tremurul (sacadat, încoace
  și încolo) de o mișcare lină, și prinde mutările rapide de la o persoană la alta;</li>
  <li><b>activitatea din cadru</b>: cât se schimbă imaginea (oameni care se mișcă). Asta e „Visual Importance”.</li>
  </ul></li>
<li><b>Dă note pe porțiuni:</b> în Auto, pe fiecare secundă dintre două mișcări de cameră; în Custom, pe ferestre de
2 secunde.</li>
<li><b>Împarte rezultatul:</b>
  <ul>
  <li><b>Auto</b> păstrează ce trece de prag, taie mișcările dintre subiecte și aruncă bucățile mai scurte decât
  „Minimum cut length”. Exportă totul pe o singură pistă.</li>
  <li><b>Custom</b> împarte în Poor / Fair / Good după slidere și procente. Exportă pe 3 piste.</li>
  <li>În ambele cazuri, <b>fiecare cut are sunetul lui</b> (pe A1/A2), legat de imagine: îl muți sau îl tai împreună cu
  cadrul.</li>
  </ul></li>
</ol>
<p>Analiza se face o singură dată. După ea, sliderele și comutatoarele doar recalculează pe datele deja măsurate, deci se
schimbă instant. Rezultatul rămâne salvat în History, ca să-l poți redeschide.</p>
<h3>Ce nu face</h3>
<ul>
<li><b>Nu modifică fișierele tale.</b> Doar le citește și generează XML-ul pentru Premiere.</li>
<li><b>Nu ascultă sunetul.</b> În Footage Selection, alegerea e doar pe imagine.</li>
<li><b>Nu recunoaște oameni sau fețe.</b> „Importance” înseamnă doar „se mișcă ceva în cadru”, nu „e mireasa în cadru”.</li>
</ul>
<p>În proiectele Multicam, butonul Auto Edit face exact aceeași analiză pe clipurile fiecărei camere. Rezultatul îl
folosește apoi regizorul automat ca să aleagă camera pentru fiecare moment.</p>

<h2>Auto Edit pe muzică</h2>
<p>Când <b>Cut on the beat</b> e pornit, Auto Edit citește muzica de pe recorder (o singură dată, apoi rămâne în proiect):
tempo-ul pe fiecare porțiune (urmărește schimbările de melodie ale DJ-ului și tempo-ul care „curge" la formație), fiecare
beat, primul beat din fiecare măsură, build-up-urile și drop-urile, plus zonele cu vorbire.</p>
<ul>
<li><b>Pe muzică:</b> cadrele încep pe beat, de obicei pe începutul măsurii, și durează 1–4 măsuri (mai scurt când melodia
e mai intensă, mai lung când e calmă).</li>
<li><b>Pe drop:</b> o tăietură exact pe drop, apoi o schimbare de cameră la fiecare 1 beat / 2 beat-uri / 1 măsură / 2 măsuri /
4 măsuri (Auto Director).</li>
<li><b>Build-up:</b> un singur cadru până la drop (Hold) sau tăieturi tot mai dese, din Auto Director.</li>
<li><b>Pe vorbire</b> (discursuri, toasturi): tăieturile cad în pauzele dintre fraze. Unde beat-ul nu e clar (o baladă fără
tobe) nu se inventează beat-uri: acolo se taie ca înainte.</li>
<li><b>Cut on the beat oprit:</b> Auto Edit lucrează exact ca înainte.</li>
</ul>
<p>Opțiunile sunt în panoul <b>Auto Director</b> (dreapta, în proiectul Multicam), la <b>On the music · all projects</b>: sunt aceleași pentru toate proiectele, alegi o dată și rămân. Sunt active doar când Cut on the beat e pornit.</p>
<p><b>Rândul Music</b> de pe Sync Map (după Auto Edit) arată fiecare melodie cu tempo-ul ei, intensitatea (mai luminos = mai
intens), vorbirea (gri) și drop-urile (linie roz).</p>
<h2>On the music: ce înseamnă opțiunile (pe înțelesul tuturor)</h2>
<p><b>Beat</b> = bătaia pe care o bați din palme pe melodie (1, 2, 3, 4). <b>Măsură</b> (bar) = 4 beat-uri la rând.
La o melodie de club (128 BPM): 1 beat ≈ 0,5 s, 1 măsură ≈ 2 s. Opțiunile sunt în <b>Multicam &gt; Auto Director &gt; On the music · all
projects</b>, contează doar cu <b>Cut on the beat</b> pornit și sunt aceleași pentru toate proiectele.</p>
<h3>On a drop, change camera every</h3>
<p>Drop-ul = momentul în care intră basul tare după ce muzica „urcă" și lumea sare. Opțiunea spune cât de des se schimbă
camera <b>în timpul drop-ului</b>:</p>
<ul>
<li><b>1 beat</b> (~0,5 s): foarte agresiv; doar cu multe camere bune (5+), pentru efect scurt.</li>
<li><b>2 beats</b> (~1 s): energic, ritm de clip; DJ / muzică electronică, 4+ camere.</li>
<li><b>1 bar</b> (~2 s, implicit): energic dar ușor de urmărit; de obicei o lași așa.</li>
<li><b>2 bars</b> (~4 s): mai calm; 2-3 camere sau petrecere mai liniștită.</li>
<li><b>4 bars</b> (~8 s): aproape fără accelerare pe drop.</li>
</ul>
<p>Regula: cu cât ai mai multe camere cu cadre bune, cu atât poți merge mai repede. Pe drop, opțiunea are prioritate față
de Minimum shot.</p>
<h3>Build-up before a drop</h3>
<p>Build-up-ul = partea de dinainte de drop în care muzica „crește" (tobe tot mai dese, sunet care urcă, de obicei fără
bas), cam 4-8 măsuri.</p>
<ul>
<li><b>Hold one shot until the drop</b> (implicit): o singură cameră tot build-up-ul, apoi tăietură fix pe drop. Contrastul
face drop-ul să „lovească"; varianta sigură, merge și cu puține camere.</li>
<li><b>Cut faster and faster</b>: tăieturi tot mai dese (2 măsuri, 1 măsură, 2 beat-uri) până la drop. Tensiune ca într-un
teaser; bine la DJ și cu multe camere.</li>
</ul>
<h3>Tăieturi mai rapide pe muzica intensă (automat)</h3>
<p>Pentru restul melodiei (nu pentru drop) e mereu activ: pe părțile intense cadrele sunt mai scurte (până la 1 măsură), pe cele calme mai lungi (până la 4 măsuri). Montajul „respiră” cu muzica; Minimum shot și Cut pace dau ritmul de bază.</p>
<h3>Exemplu</h3>
<p>DJ, 4 camere, setările implicite: strofa calmă cu cadre de 2-4 măsuri, build-up-ul ținut pe o cameră, tăietură fix pe
drop, apoi altă cameră la fiecare măsură, după drop iar mai liniștit. Sfat: încearcă „1 bar" și „2 beats": schimbarea e
instantă, fără să refaci analiza.</p>
<h2>Zone „Slower cuts", unghi alternativ, învață stilul meu</h2>
<h3>Zone „Slower cuts" (pentru muzica populară)</h3>
<p>La muzica populară (formație, tempo care se schimbă mereu, hore și sârbe) tăieturile pe măsuri nu se potrivesc, iar
partea asta arată mai bine puțin mai calmă. Pe <b>Sync Map</b> tragi cu mouse-ul peste porțiunea respectivă și apare o
zonă galbenă <b>Slower cuts</b>. În ea Auto Edit taie <b>ca înainte de tăierea pe măsuri</b> (pe cel mai apropiat accent din
sunet) și cu <b>cadre mai lungi</b> (minimum 6 s și cel puțin dublul lui Minimum shot, fără să treacă de Maximum shot).
Restul petrecerii rămâne tăiat pe muzică.</p>
<ul>
<li>Tragi de marginea zonei ca s-o muți; sub hartă ai lista zonelor, unde scrii ora exactă (h:mm:ss.s).</li>
<li>Click dreapta pe zonă sau <b>Delete</b> o șterge. Zonele rămân salvate în proiect.</li>
</ul>
<h3>Unghi alternativ</h3>
<p>În XML-ul exportat, deasupra montajului, ai o pistă <b>dezactivată</b> cu a doua cea mai bună cameră pentru fiecare cadru
(clipurile se numesc „ALT · cameră"). Dacă un cadru nu-ți place, activezi pista sau tragi cadrul alternativ jos, fără să
cauți. Pe cadrele de pe camera statică nu se pune alternativă (acolo ești safe oricum); camera statică poate apărea ca
alternativă pentru cadrele de pe camerele din mână.</p>
<h3>Tăietura cu un cadru înainte de beat (automat)</h3>
<p>Pe muzică, fiecare tăietură cade cu <b>1 cadru (40 ms) înainte de beat</b>: ochiul percepe schimbarea cu o mică întârziere, așa că tăietura pare exact pe lovitură. Sequence-ul exportat e mereu la <b>25 fps</b>.</p>
<h3>Learn my editing style</h3>
<p>În Auto Director, <b>Learn my editing style…</b>: alegi XML-ul unei petreceri montate de tine (exportat din Premiere).
Aplicația măsoară cum tai: cât de lungi îți sunt cadrele în general, pe muzică calmă, pe muzică intensă și pe drop-uri, cât
de des tai pe beat și dacă tai înainte de el, cât folosești camerele din mână. Îți arată ce a măsurat și setările care
taie ca tine; alegi <b>Use for this project</b> sau <b>Use as my style</b> (atunci fiecare proiect nou pornește cu ele).</p>
<ul>
<li>Muzica se măsoară doar dacă fișierele recorder-ului din acel XML sunt pe calculator; altfel se măsoară doar cadrele.</li>
<li>Stilul e salvat <b>doar pe calculatorul tău</b>: un coleg pe alt calculator își învață propriul stil.</li>
</ul>
<h2>Teaser Studio</h2>
<h3>Culorile recomandate (pentru tine și pentru colegi)</h3>
<p>Teaser Studio știe ce e în cadre doar după <b>culoarea etichetei din Premiere</b>. Ca să meargă la fel pentru oricine,
folosiți aceleași culori (în Premiere: click dreapta pe clip &gt; <b>Label</b> &gt; culoarea):</p>
<table cellspacing='0' cellpadding='4'><tr><td><span style='color:#e384b6'>■</span></td><td><b>Rose</b></td><td>mireasa (pregătiri)</td></tr><tr><td><span style='color:#4a6fd6'>■</span></td><td><b>Blue</b></td><td>mirele (pregătiri)</td></tr><tr><td><span style='color:#9638c4'>■</span></td><td><b>Purple</b></td><td>cuplu (first look, ședință, după biserică)</td></tr><tr><td><span style='color:#9a6a3a'>■</span></td><td><b>Brown</b></td><td>biserica</td></tr><tr><td><span style='color:#e3c74a'>■</span></td><td><b>Yellow</b></td><td>sala / locația</td></tr><tr><td><span style='color:#1dc6a8'>■</span></td><td><b>Caribbean</b></td><td>tot sala / locația (ca Yellow)</td></tr><tr><td><span style='color:#6f86e8'>■</span></td><td><b>Iris</b></td><td>petrecerea (doar cadrele de seară)</td></tr><tr><td><span style='color:#a990dd'>■</span></td><td><b>Violet</b></td><td>drona</td></tr><tr><td><span style='color:#c9a77c'>■</span></td><td><b>Tan</b></td><td>interviuri cu invitații · ignorat</td></tr><tr><td><span style='color:#4f8a2f'>■</span></td><td><b>Forest</b></td><td>nest-uri (nested sequences) · ignorat</td></tr><tr><td><span style='color:#d7a6e8'>■</span></td><td><b>Lavender</b></td><td>adjustment layers · ignorat</td></tr></table>
<p>Sfaturi: etichetați clipurile în bin înainte să le puneți în sequence-ul de selecții; o selecție poate fi și mai lungă
(de exemplu 10 s de petrecere), aplicația alege singură partea cea mai bună. Clipurile fără culoare sunt ignorate.</p>

<ol>
<li><b>Footage:</b> în Premiere pui clipurile etichetate pe culori într-un sequence (selects) și dai Export XML. Culori:
Rose mireasă, Blue mire, Purple cuplu, Brown biserică, Yellow sală, Iris petrecere, Violet dronă. Tan, Forest și Lavender
sunt ignorate.</li>
<li><b>Music:</b> melodiile deja îmbinate, într-un fișier audio sau ca XML al montajului muzical (din XML se văd exact
schimbările de melodie).</li>
<li><b>Parts:</b> aplicația propune șase momente și le poți corecta (m:ss):
  <ul>
  <li><b>Drop</b>: drop-ul din melodia de teaser (găsit automat);</li>
  <li><b>Teaser ends</b>: finalul părții de după drop, aici încep pregătirile;</li>
  <li><b>Getting ready ends</b>: aici începe biserica;</li>
  <li><b>Church ends</b>: aici vin cadrele de cuplu, peste finalul jurămintelor;</li>
  <li><b>Party song starts</b>: începe melodia de petrecere și prezentarea locației (sala, drona);</li>
  <li><b>Venue ends</b>: începe petrecerea propriu-zisă.</li>
  </ul>
  Dacă dai muzica ca XML, granițele dintre melodii sunt luate exact de acolo. Timpii trebuie să meargă înainte, în
  ordinea de mai sus.</li>
<li><b>Proiecte:</b> sus ai lista de proiecte Teaser (câte unul pe nuntă): <b>+ New teaser</b>, Rename, Delete. Fiecare
proiect ține minte footage-ul, muzica, cele șase momente și ordinea.</li>
<li><b>Analiza selecțiilor</b> se poate opri oricând cu <b>Cancel</b>; ce s-a analizat rămâne salvat și continuă data
viitoare de unde a rămas. Poți genera și înainte să se termine (selecțiile neanalizate se folosesc fără alegerea celei mai
bune bucăți). O vezi și în Analysis Queue.</li>
<li><b>Mirii (opțional):</b> câte o poză bună cu mireasa și cu mirele, din ziua nunții, apoi <b>Găsește-i în selecții</b>.
Recunoaștere facială locală, gratuită. La generare, cadrele de mireasă, mire, cuplu, biserică și petrecere preferă selecțiile în
care apar ei. Căutarea se face o singură dată pe proiect (rămâne salvată).</li>
<li><b>Test AI (experimental):</b> verifică dacă SigLIP 2, un model AI gratuit care rulează pe Mac, recunoaște cadrele tale ca
etichetele tale. <b>Test rapid</b> (25 de selecții pe culoare, câteva minute) sau <b>Toate selecțiile</b> (lent: lasă-l peste
noapte; Mac-ul nu adoarme cât rulează). Prima dată descarcă modelul (câțiva GB). Rezultatul rămâne salvat. Nu schimbă
teaserul.</li>
<li><b>Selecțiile tale:</b> poți da selecții mai lungi (de exemplu 10 s de petrecere). La import, aplicația se uită la fiecare
selecție o singură dată (claritate, stabilitate, expunere, mișcare) și folosește partea cea mai bună din ea: cu mișcare pe
drop și la petrecere, mai calmă la pregătiri și la biserică. Folosește întâi câte o bucată din fiecare selecție, apoi a
doua. Clipurile interpretate în Premiere la alt frame rate (de exemplu 50p ca 25p) sunt citite corect.</li>
<li><b>Reguli de alegere:</b> un moment nu e folosit niciodată de două ori (nici în teaser și apoi în film), același
clip nu apare de două ori la rând, biserica și sala încep cu cadrul de dronă filmat cel mai aproape de ele, iar
petrecerea folosește doar cadrele Iris filmate după biserică (cele de dimineață sunt first look). Dacă nu ajunge
materialul, aplicația îți spune câte secunde au rămas neacoperite.</li>
<li><b>Ordinea poveștii:</b> fiecare parte urmează ziua, în ordinea în care au fost filmate cadrele (după timecode / ora din fișier; dacă unele clipuri n-au oră, după ordinea din sequence-ul tău). Teaserul e mereu amestecat. <b>Shuffle shots</b> alege alte cadre, păstrând ordinea.</li>
<li><b>Generate</b> construiește structura ta: teaser (înainte de drop pregătiri, biserică, cuplu, dronă; după drop
petrecere alternată cu cuplu), pregătiri mireasă/mire, biserica cu cuplul la final, sala, apoi petrecerea. Fiecare tăietură
cade pe beat. <b>Shuffle</b> alege alte cadre; <b>Export XML</b> are markere pentru fiecare parte, ca să pui testimonialele și
jurămintele în Premiere (markere: Teaser, DROP, Getting ready, Church, Couple + vows, Party: venue, Party).</li>
</ol>
<h2>Long Film (filmul lung)</h2>
<p>Filmul lung pre-montat din selecțiile tale etichetate. Fiecare selecție e pusă <b>întreagă, în ordinea ta</b>; muzica,
interviurile și finisajele le adaugi tu în Premiere. Petrecerea rămâne montajul din Multicam.</p>
<ol>
<li><b>Filmări:</b> XML-ul sequence-ului de selecții, cu aceleași culori ca în Teaser Studio. În sequence pui ziua camerei 1,
lași o <b>pauză de câteva minute</b>, apoi ziua camerei 2. Aplicația recunoaște singură cele două camere după pauză. În
fiecare cameră, <b>primul cadru maro</b> (biserica) desparte dimineața de rest: Iris înainte de biserică = first look,
după = petrecere.</li>
<li><b>Teaser:</b> alegi proiectul din Teaser Studio al aceleiași nunți; teaserul lui (cu muzica) deschide filmul.</li>
<li><b>Vornic (opțional, oprit implicit):</b> pornește-l doar la nunțile cu vornic și alege o poză bună cu el (fața bine
vizibilă). Aplicația îi găsește cadrele Iris de dimineață după față, pe ambele camere (recunoaștere facială locală, gratuită).
Camera unde fața lui e mai mare e cea medium (V1), cealaltă (wide) e așezată după sunet pe V2, iar pe V3 ai o variantă
tăiată automat, care alternează camerele în pauzele lui de vorbire. Poți marca cadrele de vornic și cu Mango.</li>
<li><b>Construiește</b>, apoi <b>Export XML</b>.</li>
</ol>
<p>Părțile, în ordine: Teaser · Pregătiri (doar camera 1) · First look (ambele camere) · Vornic · Biserica (exact în ordinea ta,
ambele camere) · Cuplu și sală (cuplul după biserică, apoi drona și sala) · un marker „Petrecere". Fiecare parte are un
marker; fiecare cadru are sunetul camerei pe A1/A2, teaserul are muzica pe A3/A4.</p>
<h2>Update-uri și probleme</h2>
<ul>
<li>Aplicația verifică singură la pornire dacă există o versiune nouă și te anunță. În <b>Settings &gt; Check for updates</b>
o poți verifica oricând, iar <b>Download</b> deschide pagina cu fișierele noi.</li>
<li>Când ceva nu merge: <b>Settings &gt; Save error report</b> și trimite fișierul lui Claude. Conține ce a făcut aplicația și
erorile, fără video.</li>
</ul>
<h2>Sfaturi utile</h2>
<p><b>Limba aplicației:</b> Setări &gt; Limba (English / Română). Se aplică la următoarea pornire, pentru toată aplicația și pentru aceste pagini. Termenii de montaj (Sync, Auto Edit, Export XML, Drop) rămân în engleză, ca în Premiere.</p>
<ul>
<li><b>Auto sau Custom?</b> Auto este varianta clasică: păstrează cadrele bune și le pune pe o singură pistă. Custom îți dă
control pe fiecare criteriu și împarte totul în Poor / Fair / Good, pe 3 piste.</li>
<li><b>Mutări rapide între persoane.</b> Dacă stai cam 2 secunde pe fiecare om, pune „Minimum cut length” pe 2 s. Pe 3 s,
cadrele mai scurte sunt eliminate.</li>
<li><b>Camera statică apare prea des?</b> Trage „Static ↔ Handheld” spre dreapta. Programul judecă doar calitatea tehnică, iar camera statică nu tremură niciodată, de aceea o preferă.</li>
<li><b>Timecode.</b> Setează timecode-ul camerelor cât mai aproape de ora reală. Nu trebuie să fie exact la cadru: e folosit
doar ca indiciu, dar face sincronizarea mult mai rapidă.</li>
<li><b>Import în Premiere:</b> File &gt; Import și alegi fișierul XML. Apare un sequence nou în proiect.</li>
<li><b>Nu muta și nu redenumi fișierele</b> după export. XML-ul arată spre locul lor de pe disc; dacă le muți, Premiere îți
cere să le reconectezi (Link Media).</li>
<li><b>Viteză:</b> în Settings &gt; Performance alegi câte clipuri se procesează în paralel. Memoria RAM nu e limita,
procesorul este.</li>
<li><b>Sunet:</b> aplicația ascultă fiecare canal separat și îl alege pe cel cu sunet, deci merge și cu mono pus pe
2 canale (chiar dacă doar unul se aude) sau cu recordere cu multe canale.</li>
<li><b>Proxy-urile</b> camerelor (DJI .LRF, GoPro .LRV, Sony SUB/…S03.MP4) sunt ignorate automat: au același sunet ca
originalul și ar dubla camera.</li>
<li><b>Clipuri fără sunet</b> (de exemplu camere pe gimbal cu microfonul oprit) nu pot fi sincronizate pe sunet. Apar ca
„Failed: no usable sound”; le poți pune de mână (dublu click pe Start) sau folosești Import XML din Syncaila.</li>
<li><b>Formate:</b> orice citește FFmpeg (MXF, MP4, MOV, MKV, AVI etc.). BRAW (Blackmagic) și R3D (RED) nu sunt suportate.</li>
<li><b>Analysis Queue</b> îți arată ce rulează acum (analize, Sync, Auto Edit) și te duce înapoi la ele.</li>
<li><b>Proiectele se salvează singure</b> pe calculator. Ștergerea unui proiect nu șterge clipurile tale.</li>
</ul>
"""

EN = """
<h1>How to use MoneyMakingMachine</h1>
<p>The app has two kinds of projects: <b>Footage Selection</b> (picks the good shots from a set of clips) and
<b>Multicam</b> (syncs several cameras to the mixer recorder and builds the edit).</p>

<h2>Multicam: Sync and Auto Edit</h2>
<p>Press <b>Sync</b> first, then <b>Auto Edit</b>. Auto Edit does not sync, and its button stays disabled until a sync
exists. They are two separate steps on purpose: syncing is fast, while the video analysis is the slow part, so you only
run it when you want the automatic edit.</p>
<h3>The full process</h3>
<ol>
<li><b>Drop all your material into Footage</b>: cards, recorder, whole folders. Side files (Sony XMLs, photos and so on)
are skipped automatically.</li>
<li><b>Sync</b> (fast):
  <ul>
  <li>reads every file and finds the audio master (the audio-only recorder files);</li>
  <li>syncs every clip by its sound, using the cameras' timecode as a hint to search faster;</li>
  <li>groups the clips by camera and lays all recorder files out on one timeline.</li>
  <li>Afterwards you have the map, the Cameras and Clips tabs, and you can already <b>Export</b>: in Premiere you get every
  camera on its own track with its full clips synced, plus the recorder. If you want to edit yourself, you can stop here.</li>
  </ul></li>
<li><b>Check and correct</b> if needed:
  <ul>
  <li><b>Clips</b>: clips marked "Check" or "Failed". Fix a wrong offset by double-clicking its value in the Start column.</li>
  <li><b>Cameras</b>: if two detected cameras are really one, give them the same name and they merge. This is also where you
  change the role (Static / Handheld) if the app guessed it wrong.</li>
  </ul></li>
<li><b>Auto Edit</b> (slow, optional):
  <ul>
  <li>analyses the video of every synced clip (sharpness, shake, exposure, camera moves);</li>
  <li>sets the camera roles, unless you changed them yourself;</li>
  <li>the automatic director builds the edit.</li>
  <li>The analysis is saved. If you press it again, clips that were already analysed are not processed again.</li>
  </ul></li>
<li><b>Tune the edit on the right</b>: minimum and maximum shot, cut pace, Static ↔ Handheld, cut on the beat, static only
as backup. Everything updates instantly without a new analysis, and the map shows the result right away.</li>
<li><b>Export XML</b>: one sequence, every camera on its own track with only its cuts, the recorder and the camera
sound uncut.</li>
</ol>
<p><b>If you add files later:</b> press Sync again, then Auto Edit. The second time only the new clips are analysed, so it
is much faster.</p>
<h3>Lavaliers, drone, cameras without sound</h3>
<ul>
<li>The <b>main recorder</b> is the audio-only folder with the most hours (the mixer recorder). Other audio-only folders
(e.g. <b>LAV I</b>, <b>LAV II</b>) are synced to it and exported on their own audio tracks, uncut.</li>
<li><b>Drone and cameras without sound</b> cannot be synced by sound. They are placed <b>approximately by time</b> (timecode or
file time, corrected by the clock error learned from the other cameras), shown in purple ("By time"), on their own track
with the full clip, and are not used by the auto edit.</li>
<li>When the sync finishes you see <b>how long</b> reading the files and searching took. If reading takes long, the disk is
what slows it down (an external HDD is much slower than an SSD).</li>
</ul>
<h3>Import XML (synced in another app)</h3>
<p>If your footage is already synced in <b>Syncaila</b>, Premiere Pro or DaVinci Resolve, export an XML (FCP7 XML) from there
with every camera on its own track and press <b>Import XML</b>. The app takes the positions exactly as they are (it does not
sync again), every video track becomes a camera and audio-only files become the recorder. Then press <b>Auto Edit</b> and
<b>Export XML</b> as usual.</p>
<p><b>Map colours:</b> green = <b>High</b> (sure), yellow = <b>Medium</b> (very likely right), orange = <b>Check</b>
(position unsure), red = <b>Failed</b> (could not be placed). On the "Auto edit" row every colour is a camera. A camera cannot
film two things at once: when two clips of the same camera overlap, the less sure one goes to the "check sync" track.</p>
<p><b>The "· check sync" track:</b> clips whose position is not certain all go on one separate track and are not used in the
auto edit. Check them in the Clips tab and fix them by double-clicking Start.</p>
<p><b>Export XML</b> works in Premiere Pro (File &gt; Import) and in DaVinci Resolve (File &gt; Import &gt; Timeline).</p>

<h2>Footage Selection: what "Analyze Footage" does</h2>
<p><b>The analysis screen:</b> on top the clips being analysed right now, in the middle the progress (Pause / Cancel), at the
bottom the finished ones. It also runs in the background: come back from <b>Analysis Queue &gt; Open</b> or from the project
with <b>View analysis</b>.</p>
<p>"Analyze Footage" looks at every clip and gives every part of it a score.</p>
<h3>Step by step</h3>
<ol>
<li><b>Reads the video</b> with FFmpeg (any format, MXF included). It takes 8 frames per second, scaled down to 320×180 in
black and white. That is all it needs to judge quality, and it is much faster this way.</li>
<li><b>Measures on every frame:</b>
  <ul>
  <li><b>sharpness</b>: how much fine detail the image has (a blurred frame has little);</li>
  <li><b>exposure</b>: whether it is too dark or has blown-out areas;</li>
  <li><b>contrast</b>: whether the image is washed out or too harsh;</li>
  <li><b>camera movement</b>: how far the image moved since the previous frame. This tells shake (jerky, back and forth)
  apart from a smooth move, and catches quick moves from one person to another;</li>
  <li><b>activity in the frame</b>: how much the image changes (people moving). This is "Visual Importance".</li>
  </ul></li>
<li><b>Scores the parts:</b> in Auto, every second between two camera moves; in Custom, 2-second windows.</li>
<li><b>Splits the result:</b>
  <ul>
  <li><b>Auto</b> keeps what passes the threshold, cuts out the moves between subjects and drops pieces shorter than
  "Minimum cut length". Everything is exported on one track.</li>
  <li><b>Custom</b> splits into Poor / Fair / Good using the sliders and percentages. Exported on 3 tracks.</li>
  <li>Either way, <b>every cut carries its own sound</b> (on A1/A2), linked to the picture: it moves and trims together
  with the shot.</li>
  </ul></li>
</ol>
<p>The analysis runs only once. After that, sliders and switches just recalculate on the data already measured, so they
change instantly. The result stays saved in History so you can reopen it.</p>
<h3>What it does not do</h3>
<ul>
<li><b>It does not change your files.</b> It only reads them and writes the XML for Premiere.</li>
<li><b>It does not listen to the sound.</b> In Footage Selection the choice is based on the image only.</li>
<li><b>It does not recognise people or faces.</b> "Importance" only means "something moves in the frame", not "the bride is
in the frame".</li>
</ul>
<p>In Multicam projects, the Auto Edit button runs exactly the same analysis on every camera's clips. The automatic
director then uses it to choose the camera for every moment.</p>

<h2>Auto Edit on the music</h2>
<p>When <b>Cut on the beat</b> is on, Auto Edit reads the music of the recorder (once, then it stays in the project): the tempo
of every part (it follows the DJ's song changes and a band's drifting tempo), every beat, beat 1 of every bar, the build-ups
and the drops, and the parts with speech.</p>
<ul>
<li><b>On music:</b> shots start on a beat, usually on beat 1 of the bar, and last 1-4 bars (shorter when the music is more
intense, longer when it is calm).</li>
<li><b>On a drop:</b> a cut exactly on the drop, then a camera change every 1 beat / 2 beats / 1 bar / 2 bars / 4 bars
(Auto Director).</li>
<li><b>Build-up:</b> one shot until the drop (Hold) or faster and faster cuts, in Auto Director.</li>
<li><b>On speech</b> (speeches, toasts): cuts fall in the pauses between sentences. Where the beat is not clear (a ballad
without drums) no beat is invented: cuts work as before there.</li>
<li><b>Cut on the beat off:</b> Auto Edit works exactly as before.</li>
</ul>
<p>The options are in the <b>Auto Director</b> panel (right side of a Multicam project), under <b>On the music · all projects</b>: the same for every project, choose once and they stay. They work when Cut on the beat is on.</p>
<p>The <b>Music row</b> on the Sync Map (after Auto Edit) shows every song with its tempo, its intensity (brighter = more
intense), speech (grey) and the drops (pink line).</p>
<h2>On the music: what the options mean (in plain words)</h2>
<p><b>Beat</b> = the pulse you clap to (1, 2, 3, 4). <b>Bar</b> = 4 beats in a row. In a club song (128 BPM): 1 beat ≈ 0.5 s,
1 bar ≈ 2 s. The options are in <b>Auto Director &gt; On the music · all projects</b>, they only matter with <b>Cut on the
beat</b> on and they are the same for every project.</p>
<h3>On a drop, change camera every</h3>
<p>The drop = the moment the big bass comes in after the music "rises" and people jump. The option says how often the
camera changes <b>during the drop</b>:</p>
<ul>
<li><b>1 beat</b> (~0.5 s): very aggressive; only with many good cameras (5+), for a short effect.</li>
<li><b>2 beats</b> (~1 s): energetic, music-video rhythm; DJ / electronic music, 4+ cameras.</li>
<li><b>1 bar</b> (~2 s, default): energetic but easy to watch; usually leave it here.</li>
<li><b>2 bars</b> (~4 s): calmer; 2-3 cameras or a quieter party.</li>
<li><b>4 bars</b> (~8 s): almost no speed-up on the drop.</li>
</ul>
<p>The rule: the more cameras with good shots, the faster you can go. On a drop this option wins over Minimum shot.</p>
<h3>Build-up before a drop</h3>
<p>The build-up = the part before the drop where the music "grows" (faster and faster drums, rising sound, usually no bass),
about 4-8 bars.</p>
<ul>
<li><b>Hold one shot until the drop</b> (default): one camera for the whole build-up, then a cut exactly on the drop. The
contrast makes the drop hit; the safe choice, works with few cameras too.</li>
<li><b>Cut faster and faster</b>: cuts closer and closer (2 bars, 1 bar, 2 beats) until the drop. Tension like a teaser;
good for DJ sets and many cameras.</li>
</ul>
<h3>Faster cuts on intense music (automatic)</h3>
<p>For the rest of the song (not the drop) it is always on: intense parts get shorter shots (down to 1 bar), calm parts longer ones (up to 4 bars). The edit breathes with the music; Minimum shot and Cut pace set the base rhythm.</p>
<h3>Example</h3>
<p>DJ, 4 cameras, default settings: calm verse with 2-4 bar shots, the build-up held on one camera, a cut exactly on the
drop, then another camera every bar, after the drop calmer again. Tip: try "1 bar" and "2 beats": the change is instant,
no new analysis needed.</p>
<h2>Slower cuts zones, alternative angle, learn my style</h2>
<h3>"Slower cuts" zones (for folk music)</h3>
<p>With folk music (a live band, a tempo that keeps changing, hora and sârba) cutting on the bars does not fit and that part
looks better a bit calmer. On the <b>Sync Map</b> drag across that part: a yellow <b>Slower cuts</b> zone appears. Inside it
Auto Edit cuts <b>the way it did before the bars</b> (on the nearest accent of the sound) and with <b>longer shots</b> (at
least 6 s and twice the Minimum shot, never past Maximum shot). The rest of the party stays cut on the music.</p>
<ul>
<li>Drag an edge of the zone to move it; under the map the list of zones takes the exact times (h:mm:ss.s).</li>
<li>Right-click the zone or press <b>Delete</b> to remove it. Zones are saved with the project.</li>
</ul>
<h3>Alternative angle</h3>
<p>In the exported XML, above the edit, there is a <b>switched-off</b> track with the second best camera for every shot (the
clips are named "ALT · camera"). If a shot does not work, turn the track on or drag the alternative down, no searching.
Shots on the static camera get no alternative (they are safe anyway); the static camera can be the alternative for shots on
the handheld cameras.</p>
<h3>The cut one frame before the beat (automatic)</h3>
<p>On music every cut falls <b>1 frame (40 ms) before the beat</b>: the eye sees a change a little late, so the cut feels exactly on the hit. The exported sequence is always <b>25 fps</b>.</p>
<h3>Learn my editing style</h3>
<p>In Auto Director, <b>Learn my editing style…</b>: pick the XML of a party you edited (exported from Premiere). The app
measures how you cut: your shot lengths overall, on calm music, on intense music and on drops, how often you cut on the
beat and whether before it, how much you use the handheld cameras. It shows what it measured and the settings that cut like
you; choose <b>Use for this project</b> or <b>Use as my style</b> (then every new project starts with them).</p>
<ul>
<li>The music is measured only if the recorder files of that XML are on this computer; otherwise only the shots.</li>
<li>Your style is saved <b>on this computer only</b>: a colleague on another computer learns his own.</li>
</ul>
<h2>Teaser Studio</h2>
<h3>Recommended colours (for you and your colleagues)</h3>
<p>Teaser Studio knows what is in a shot only from its <b>Premiere label colour</b>. To make it work the same for everyone,
use the same colours (in Premiere: right-click the clip &gt; <b>Label</b> &gt; the colour):</p>
<table cellspacing='0' cellpadding='4'><tr><td><span style='color:#e384b6'>■</span></td><td><b>Rose</b></td><td>the bride (getting ready)</td></tr><tr><td><span style='color:#4a6fd6'>■</span></td><td><b>Blue</b></td><td>the groom (getting ready)</td></tr><tr><td><span style='color:#9638c4'>■</span></td><td><b>Purple</b></td><td>the couple (first look, shoot, after church)</td></tr><tr><td><span style='color:#9a6a3a'>■</span></td><td><b>Brown</b></td><td>the church</td></tr><tr><td><span style='color:#e3c74a'>■</span></td><td><b>Yellow</b></td><td>the venue / location</td></tr><tr><td><span style='color:#1dc6a8'>■</span></td><td><b>Caribbean</b></td><td>also the venue / location (like Yellow)</td></tr><tr><td><span style='color:#6f86e8'>■</span></td><td><b>Iris</b></td><td>the party (evening shots only)</td></tr><tr><td><span style='color:#a990dd'>■</span></td><td><b>Violet</b></td><td>the drone</td></tr><tr><td><span style='color:#c9a77c'>■</span></td><td><b>Tan</b></td><td>guest interviews · ignored</td></tr><tr><td><span style='color:#4f8a2f'>■</span></td><td><b>Forest</b></td><td>nests (nested sequences) · ignored</td></tr><tr><td><span style='color:#d7a6e8'>■</span></td><td><b>Lavender</b></td><td>adjustment layers · ignored</td></tr></table>
<p>Tips: label the clips in the bin before putting them in the selects sequence; a selection can be longer (e.g. 10 s of
party), the app picks its best part. Clips without a colour are ignored.</p>

<ol>
<li><b>Footage:</b> in Premiere put your colour-labelled clips in a sequence (selects) and Export XML. Colours: Rose bride,
Blue groom, Purple couple, Brown church, Yellow venue, Iris party, Violet drone. Tan, Forest and Lavender are ignored.</li>
<li><b>Music:</b> your songs already joined, as one audio file or as the XML of your music edit (the XML shows exactly where
each song starts).</li>
<li><b>Parts:</b> the app proposes six moments and you can correct them (m:ss):
  <ul>
  <li><b>Drop</b>: the drop of the teaser song (found automatically);</li>
  <li><b>Teaser ends</b>: end of the part after the drop, getting ready starts here;</li>
  <li><b>Getting ready ends</b>: the church starts here;</li>
  <li><b>Church ends</b>: the couple shots start here, over the end of the vows;</li>
  <li><b>Party song starts</b>: the party song and the venue presentation (venue, drone) start;</li>
  <li><b>Venue ends</b>: the party itself starts.</li>
  </ul>
  If you give the music as an XML, the song changes are taken from it exactly. The times must go forward, in the order
  above.</li>
<li><b>Projects:</b> at the top you have the list of teaser projects (one per wedding): <b>+ New teaser</b>, Rename,
Delete. Every project remembers its footage, music, six moments and order.</li>
<li><b>Looking at the selections</b> can be stopped any time with <b>Cancel</b>; what is done is saved and continues next
time where it was. You can generate before it finishes (unanalysed selections are used without picking their best part).
It also shows in Analysis Queue.</li>
<li><b>Bride and groom (optional):</b> a good photo of each from the wedding day, then <b>Find them in the selections</b>.
Local, free face recognition. When generating, the bride, groom, couple, church and party shots prefer the selections where
they are seen. The search runs once per project (it is saved).</li>
<li><b>AI test (experimental):</b> checks if SigLIP 2, a free AI model running on this Mac, recognises your shots like your
labels. <b>Quick test</b> (25 selections per colour, a few minutes) or <b>Every selection</b> (slow: leave it overnight; the
Mac does not go to sleep while it runs). The first time it downloads the model (a few GB). The result is saved. It does not
change the teaser.</li>
<li><b>Your selections:</b> you can give longer selections (for example 10 s of party). On import the app looks at every
selection once (sharpness, steadiness, exposure, movement) and uses its best part: with movement on the drop and in the
party, calmer in getting ready and church. It uses one bit of every selection before a second one. Clips interpreted at
another frame rate in Premiere (e.g. 50p as 25p) are read correctly.</li>
<li><b>Shot rules:</b> a moment is never used twice (not even in the teaser and then in the film), the same clip never
appears twice in a row, church and venue open with the drone shot recorded closest to them, and the party only uses Iris
shots recorded after the church (the morning ones are the first look). If there is not enough footage, the app tells you
how many seconds are left uncovered.</li>
<li><b>Story order:</b> every part follows the day, in the order the shots were recorded (timecode / file time; if some clips have no recording time, the order of your sequence). The teaser is always mixed. <b>Shuffle shots</b> picks other shots and keeps the order.</li>
<li><b>Generate</b> builds your structure: teaser (before the drop getting ready, church, couple, drone; after the drop party
alternating with the couple), bride/groom getting ready, the church ending with the couple, the venue, then the party.
Every cut lands on a beat. <b>Shuffle</b> picks other shots; <b>Export XML</b> has a marker for every part, so you can add
testimonials and vows in Premiere (markers: Teaser, DROP, Getting ready, Church, Couple + vows, Party: venue, Party).</li>
</ol>
<h2>Long Film</h2>
<p>The long film pre-cut from your labelled selections. Every selection goes in <b>whole, in your order</b>; you add the music,
the interviews and the final touches in Premiere. The party stays the Multicam edit.</p>
<ol>
<li><b>Footage:</b> the XML of your selects sequence, same colours as Teaser Studio. Put camera 1's day, leave a <b>pause of a
few minutes</b>, then camera 2's day. The app finds the two cameras by the pause. In every camera the <b>first Brown shot</b>
(the church) separates the morning from the rest: Iris before the church = first look, after = party.</li>
<li><b>Teaser:</b> pick the Teaser Studio project of the same wedding; its teaser (with the music) opens the film.</li>
<li><b>Vornic (optional, off by default):</b> turn it on only for weddings with a vornic and pick a good photo of him (face
well visible). The app finds his Iris shots of the morning by his face, on both cameras (local, free face recognition). The
camera where his face is bigger is the medium one (V1), the other one (wide) is placed by the sound on V2, and V3 holds a cut
version that alternates the cameras in the pauses of his speech. You can also mark the vornic shots Mango.</li>
<li><b>Build</b>, then <b>Export XML</b>.</li>
</ol>
<p>The parts, in order: Teaser · Getting ready (camera 1 only) · First look (both cameras) · Vornic · Church (exactly your
order, both cameras) · Couple and venue (the couple after the church, then the drone and the venue) · a "Party" marker. Every
part has a marker; every shot carries its camera sound on A1/A2, the teaser its music on A3/A4.</p>
<h2>Updates and problems</h2>
<ul>
<li>At start the app checks by itself for a new version and tells you. <b>Settings &gt; Check for updates</b> checks any time,
and <b>Download</b> opens the page with the new files.</li>
<li>When something does not work: <b>Settings &gt; Save error report</b> and send the file to Claude. It contains what the app
did and the errors, no video.</li>
</ul>
<h2>Useful tips</h2>
<p><b>App language:</b> Settings &gt; Language (English / Română). It applies the next time the app starts, to the whole app and these pages. Editing terms (Sync, Auto Edit, Export XML, Drop) stay in English, like in Premiere.</p>
<ul>
<li><b>Auto or Custom?</b> Auto is the classic version: it keeps the good shots and puts them on one track. Custom gives you
control over every criterion and splits everything into Poor / Fair / Good on 3 tracks.</li>
<li><b>Quick moves between people.</b> If you stay about 2 seconds on each person, set "Minimum cut length" to 2 s. At 3 s,
shorter shots are dropped.</li>
<li><b>Static camera used too often?</b> Drag "Static ↔ Handheld" to the right.
The app only judges technical quality, and a static camera never shakes, which is why it likes it.</li>
<li><b>Timecode.</b> Set the cameras' timecode as close to the real time of day as you can. It does not have to be frame
accurate: it is only used as a hint, but it makes syncing much faster.</li>
<li><b>Importing into Premiere:</b> File &gt; Import and choose the XML file. A new sequence appears in the project.</li>
<li><b>Do not move or rename the files</b> after exporting. The XML points to where they are on disk; if you move them,
Premiere asks you to reconnect them (Link Media).</li>
<li><b>Speed:</b> in Settings &gt; Performance you choose how many clips are processed in parallel. RAM is not the limit,
the processor is.</li>
<li><b>Sound:</b> the app listens to every channel separately and uses the one with sound, so mono recorded on 2 channels
(even if only one is audible) and multi-channel recorders both work.</li>
<li><b>Camera proxies</b> (DJI .LRF, GoPro .LRV, Sony SUB/…S03.MP4) are skipped automatically: they carry the same sound as
the original and would duplicate the camera.</li>
<li><b>Clips without sound</b> (e.g. gimbal cameras with the mic off) cannot be synced by sound. They show as
"Failed: no usable sound"; place them by hand (double-click Start) or use Import XML from Syncaila.</li>
<li><b>Formats:</b> anything FFmpeg reads (MXF, MP4, MOV, MKV, AVI and more). BRAW (Blackmagic) and R3D (RED) are not
supported.</li>
<li><b>Analysis Queue</b> shows what is running right now (analyses, Sync, Auto Edit) and takes you back to it.</li>
<li><b>Projects save themselves</b> on your computer. Deleting a project does not delete your clips.</li>
</ul>
"""

HELP = {"ro": RO, "en": EN}
