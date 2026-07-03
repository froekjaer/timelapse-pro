# TimeLapse Pro website

Statisk public website til `www.timelapse-pro.dk`.

## Struktur

- `index.html` - public website med login-links til `backend.timelapse-pro.dk`
- `styles.css` - layout og visuel stil
- `script.js` - lille header-effekt
- `assets/` - komprimerede TimeLapse Pro-billeder

## Hosting

Sitet kan hostes som statiske filer, fx Cloudflare Pages.

Produktionsmodel:

- `www.timelapse-pro.dk` hoster dette site.
- Kunde/admin login linker til `https://backend.timelapse-pro.dk/login`.
- Backend kører separat bag Cloudflare Tunnel eller tilsvarende reverse proxy.
