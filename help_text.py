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

<h2>Teaser Studio (protejat cu parolă)</h2>
<ol>
<li><b>Footage:</b> în Premiere pui clipurile etichetate pe culori într-un sequence (selects) și dai Export XML. Culori:
Rose mireasă, Blue mire, Purple cuplu, Brown biserică, Yellow sală, Iris petrecere, Violet dronă. Tan, Forest și Lavender
sunt ignorate.</li>
<li><b>Music:</b> melodiile deja îmbinate, într-un fișier audio sau ca XML al montajului muzical (din XML se văd exact
schimbările de melodie).</li>
<li><b>Parts:</b> aplicația găsește drop-ul și părțile (Teaser, Pregătiri, Biserica, Petrecere); le poți corecta.</li>
<li><b>Generate</b> construiește structura ta: teaser (înainte de drop pregătiri, biserică, cuplu, dronă; după drop
petrecere alternată cu cuplu), pregătiri mireasă/mire, biserica cu cuplul la final, sala, apoi petrecerea. Fiecare tăietură
cade pe beat. <b>Shuffle</b> alege alte cadre; <b>Export XML</b> are markere pentru fiecare parte, ca să pui testimonialele și
jurămintele în Premiere.</li>
</ol>
<h2>Sfaturi utile</h2>
<ul>
<li><b>Auto sau Custom?</b> Auto este varianta clasică: păstrează cadrele bune și le pune pe o singură pistă. Custom îți dă
control pe fiecare criteriu și împarte totul în Poor / Fair / Good, pe 3 piste.</li>
<li><b>Mutări rapide între persoane.</b> Dacă stai cam 2 secunde pe fiecare om, pune „Minimum cut length” pe 2 s. Pe 3 s,
cadrele mai scurte sunt eliminate.</li>
<li><b>Camera statică apare prea des?</b> Trage „Static ↔ Handheld” spre dreapta sau pornește „Static cameras only as
backup". Programul judecă doar calitatea tehnică, iar camera statică nu tremură niciodată, de aceea o preferă.</li>
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

<h2>Teaser Studio (password protected)</h2>
<ol>
<li><b>Footage:</b> in Premiere put your colour-labelled clips in a sequence (selects) and Export XML. Colours: Rose bride,
Blue groom, Purple couple, Brown church, Yellow venue, Iris party, Violet drone. Tan, Forest and Lavender are ignored.</li>
<li><b>Music:</b> your songs already joined, as one audio file or as the XML of your music edit (the XML shows exactly where
each song starts).</li>
<li><b>Parts:</b> the app finds the drop and the parts (Teaser, Pregătiri, Biserica, Petrecere); you can correct them.</li>
<li><b>Generate</b> builds your structure: teaser (before the drop getting ready, church, couple, drone; after the drop party
alternating with the couple), bride/groom getting ready, the church ending with the couple, the venue, then the party.
Every cut lands on a beat. <b>Shuffle</b> picks other shots; <b>Export XML</b> has a marker for every part, so you can add
testimonials and vows in Premiere.</li>
</ol>
<h2>Useful tips</h2>
<ul>
<li><b>Auto or Custom?</b> Auto is the classic version: it keeps the good shots and puts them on one track. Custom gives you
control over every criterion and splits everything into Poor / Fair / Good on 3 tracks.</li>
<li><b>Quick moves between people.</b> If you stay about 2 seconds on each person, set "Minimum cut length" to 2 s. At 3 s,
shorter shots are dropped.</li>
<li><b>Static camera used too often?</b> Drag "Static ↔ Handheld" to the right or turn on "Static cameras only as backup".
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
