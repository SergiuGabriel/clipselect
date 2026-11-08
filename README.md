# ClipSelect

Pre-selecție automată a materialului video (claritate, stabilitate, expunere) cu export XML pentru Premiere Pro.

## Instalare
    pip install -r requirements.txt
    python app.py

(Dacă ai deja `ffmpeg` în PATH, îl folosește pe acela; altfel folosește binarul din `imageio-ffmpeg`.)

## Utilizare
1. Trage clipuri/foldere în fereastră sau folosește butoanele (orice fișier e acceptat; FFmpeg decide dacă îl poate citi, inclusiv .MXF de la Sony FX6).
2. Analizează. Ajustează pragul și lungimea minimă: selecțiile se recalculează instant.
3. Exportă XML, apoi în Premiere: File > Import. Rezultă o secvență cu segmentele bune, etichetate cu culoare (Forest/Mango/Rose).

## Limite
- BRAW și R3D (RED) necesită SDK-urile producătorilor; FFmpeg nu le decodează.
- Exportul conține doar video (fără audio), iar timecode-ul sursă nu e transferat.
