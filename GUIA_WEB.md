# Publicar el juego en la web (Pygbag + GitHub + Vercel)

## 1. Probarlo en el navegador (en tu PC)
Desde la carpeta que CONTIENE a `videojuego/` (no dentro):

    pip install pygbag
    pygbag videojuego

Abre http://localhost:8000 (la primera vez descarga el motor y tarda un poco).
Si juega bien ahí, está listo para publicar.

## 2. Generar la versión web
    pygbag --build videojuego

Crea `videojuego/build/web/` (index.html + videojuego.apk + favicon). **Esa carpeta es lo que se publica.**
Cada vez que cambies el código o los assets, vuelve a ejecutar este comando.

## 3. Subir a GitHub
Dentro de `videojuego/`:

    git init
    git add .
    git commit -m "Juego de magos - version web"
    git branch -M main
    git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
    git push -u origin main

IMPORTANTE: `build/web/` debe quedar en el repositorio (el `.gitignore` solo excluye `build/web-cache/`).

## 4. Conectar en Vercel
1. vercel.com -> Add New -> Project -> importa el repositorio de GitHub.
2. Framework Preset: **Other**. No pongas Build Command ni Install Command (ya lo define `vercel.json`).
3. Output Directory: `build/web` (también está en `vercel.json`).
4. Deploy. Cada `git push` con una nueva carpeta `build/web` se republica solo.

## Notas
- Controles en web: igual que en escritorio (A/D, ESPACIO, SHIFT, J, 1/2/3, P). Haz clic en el juego para darle foco al teclado.
- En el navegador no existe "salir": ESC solo pausa.
- Si al cargar ves pantalla negra: revisa la consola del navegador (F12) y que estés usando https o localhost.
