# TAILWIND.md

### Lokale TailwindCSS-Integration für openpass

---

## Überblick

Dieses Projekt nutzt **TailwindCSS lokal**, ohne CDN oder externe Scripts.
Das CSS wird über die **Tailwind CLI** gebaut und in `static/css/` gespeichert.

Ziel:

* Keine Inline-Skripte → **CSP-konform**
* Keine Abhängigkeit vom Internet im Deployment
* Klare Trennung von **Entwicklungs-** und **Produktionsbuilds**

---

## Verzeichnisstruktur

```
openpass/
├── static/
│   ├── css/
│   │   ├── input.css          # Tailwind-Quelle mit @tailwind Direktiven
│   │   ├── tailwind.css       # Minifiziertes Produktions-CSS
│   │   ├── tailwind.dev.css   # Lesbare CSS-Datei für Entwicklung
│   │   ├── base.css           # Eigene Styles (optional)
│   │   └── branding.css       # Vereins-/Projektbranding
├── tailwind.config.js         # Tailwind-Konfiguration
├── package.json               # NPM-Skripte und Abhängigkeiten
└── package-lock.json
```

---

## Voraussetzungen

### Lokale Umgebung

Installiere NodeJS + NPM (unter Ubuntu/WSL):

```bash
sudo apt update
sudo apt install -y nodejs npm
```

Prüfe Versionen:

```bash
node -v
npm -v
```

---

## Installation (einmalig)

```bash
npm install
```

Dadurch werden alle Abhängigkeiten (TailwindCSS etc.) installiert.
Die generierten Module landen **nicht im Git-Repo**
(→ stehen in `.gitignore`).

---

## Entwicklung (live & unminified)

Starte im Projektverzeichnis:

```bash
npm run dev
```

Das bewirkt:

* Tailwind beobachtet automatisch deine Templates (`templates/**/*.html`)
* Baut bei Änderungen sofort `static/css/tailwind.dev.css`
* Ausgabe ist **formatiert und lesbar**

Man kann in Flask einfach weiterarbeiten – Tailwind aktualisiert live.

---

## Produktion (Deployment)

Bevor du deployst (z. B. mit Kamal oder Docker):

```bash
npm run build
```

🔹 Was passiert:

* Tailwind erzeugt **`static/css/tailwind.css`**
* Diese Datei ist **minifiziert**
* Wird vom Flask-Template eingebunden über:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/tailwind.css') }}">
```

Diese Datei muss **committet** werden,
damit der Server kein Node benötigt.

---

## Nützliche Zusatzbefehle

| Befehl          | Beschreibung                          |
| --------------- | ------------------------------------- |
| `npm run dev`   | Baut lesbar und beobachtet Änderungen |
| `npm run build` | Baut minifiziert für Deployment       |
| `npm run clean` | Löscht Node-Module und Cache          |

---

## Tailwind-Input-Datei (`static/css/input.css`)

Dies ist die Ausgangsbasis für die Builds:

```css
/* static/css/input.css */

@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html { scroll-behavior: smooth; }
  body { @apply bg-gray-50 text-gray-800; }
}

@layer components {
  .button { @apply bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 transition; }
}

@layer utilities {
  .scroll-container { @apply overflow-y-auto max-h-[75vh]; }
}
```

---

## Tailwind-Konfiguration (`tailwind.config.js`)

```js
module.exports = {
  content: [
    "./templates/**/*.html",
    "./blueprints/**/*.html",
    "./static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2563eb",
        secondary: "#1e40af",
      },
    },
  },
  plugins: [],
};
```