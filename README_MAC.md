# ClipSelect pe Mac, fără să instalezi nimic

## Obține DMG-ul (o singură dată, din browser)
1. Cont gratuit pe github.com > New repository (ex. `clipselect`, Private e ok) > Create.
2. În repo: "uploading an existing file" > trage tot conținutul folderului `clipselect` (fișierele .py, requirements.txt etc.).
3. Folderul ascuns `.github` nu se încarcă la drag&drop. Apasă Add file > Create new file, scrie la nume
   `.github/workflows/build.yml`, lipește conținutul din fișierul `build.yml` din arhivă și dă Commit.
4. Tab-ul Actions > rulează "build" (pornește și singur la commit). După ~10 minute, deschizi rularea și descarci
   de la Artifacts: `ClipSelect-Apple-Silicon-M1-M2-M3-M4` (Mac-uri din 2020+) sau `ClipSelect-Mac-Intel`.

## Instalare
Deschizi .dmg, tragi ClipSelect în Applications. Aplicația nu e notarizată de Apple (asta cere cont de dezvoltator,
99$/an), deci prima dată: click dreapta pe aplicație > Open > Open. Se face o singură dată.
