# BRANDING.md

## Inhaltsverzeichnis

1. [Was ist Branding?](#was-ist-branding)
2. [Was kann gebrandet werden?](#was-kann-gebrandet-werden)
3. [Wie kann gebrandet werden?](#wie-kann-gebrandet-werden)
4. [Anforderungen an Logos](#anforderungen-an-logos)
5. [Farbdefinitionen und ihre Anwendung](#farbdefinitionen-und-ihre-anwendung)

---

## Was ist Branding?

Branding beschreibt die Möglichkeit, zentrale visuelle Elemente der Anwendung an ein individuelles Erscheinungsbild anzupassen.
Dies umfasst insbesondere Logos, Texte und Farben, die das Look & Feel der Anwendung prägen.

## Was kann gebrandet werden?

Aktuell können folgende Elemente individuell angepasst werden:

* **Logos** (z.B. `logo.png`, `openpass-logo.png`)
* **Textbausteine** (z.B. App-Titel, Vereinsname, Kontaktadresse, Beschreibungen)
* **Farben**

## Wie kann gebrandet werden?

Branding erfolgt durch eine zentrale JSON-Datei:

* Die Datei `branding.json` enthält die Definitionen der Textelemente sowie die zentrale Farbdefinitionen in logischer Gruppierung.
* **Alle Anpassungen werden hier vorgenommen**
* Die in der branding.json gemachten Einstellungen werden vom System beim Start der Applikation eingelesen und angewendet.

## Anforderungen an Logos

* <ANWENDUNG> nutzt 3 Logo-Dateien
1. **logo.png**
Das ist das Logo, was auf jeder Seite oben im Header angezeigt wird, ist also der zentrale "Eye-Catcher" der App.
Farblich sollte sie möglichst guten Kontrast zur Theme-Color haben, also beispielsweise "weiß." Der Hintergrund des Logos
sollte für bestmögliche Darstellung transparent sein. Die Größe sollte 512x512 Pixel sein, womit die Grafik sehr gut
skaliert.

2. **logo-black.png**
Dieses Logo wird als "Wasserzeichen" im Ausweis verwendet und sollte eine dunkle Farbe auf hellem oder idealerweise
transparentem Hintergrund haben. Als Wasserzeichen wird das Logo es bei der Darstellung hochskaliert und farblich
"verwässert". Die Größe sollte ebenfalls etwa 512x512 Pixel sein.

3. **<ANWENDUNG>-icon.png**
Dies wird als Icon für den Start-Bildschirm" verwendet, sofern die App per Button installiert wird.
*
* **Pfad**: alle Dateien liegen im Verzeichnis `/branding` und werden durch Flask-Viewfunktionen bedient.

## Farbdefinitionen und ihre Anwendung

Die Farbdefinitionen werden in der Datei branding.json verwaltet. Jede Farbe wird dort einmal definiert und über
CSS-Variablen global verfügbar gemacht. Nachfolgend ein Überblick über die vorhandenen Definitionen:

### Allgemeine Farben

```json
"theme_color": "#1C91FF",
"theme_color_dark": "#1176cc",

"text_color": "#333333",
"heading_color": "#333333",
"expired_heading_color": "#d32f2f",
"inactive_color": "#999999",
```
### Hintergrundfarben
```json
"background_color": "#f5f9ff",
"background_muted_color": "#f8f8f8",
"box_background_color": "#ffffff",
"qr_background_color": "#f3f3f3",
```
### Highlights & Statusfarben
```json
"highlight_color": "#EAF4FF",
"gold_color": "#d4af37",

"success_color": "#4CAF50",
"error_color": "#f44336",
"warning_color": "#FFC107",
"info_color": "#2196F3",
```
### Rahmen & Schatten
```json
"border_color": "#DDDDDD",
"border_muted_color": "#bbbbbb",
"shadow_color": "rgba(0, 0, 0, 0.1)",
```
### Buttons
```json
"button_text_color": "#ffffff",
"button_muted_color": "#333333",
"button_muted_bg": "#eeeeee",
"button_muted_hover_bg": "#cccccc"
```
Diese Definitionen werden automatisch in CSS-Variablen wie folgt überführt:
```css
:root {
  ...
  --text-color: {{ branding.text_color }};
  --background-color: {{ branding.background_color }};
  ...
}
```
In einer CSS-Datei wird background-color nicht mehr direkt sondern z.B. wie folgt definiert:
```css
body {
  background-color: var(--background-color);
  color: var(--text-color);
}
```
Mit diesem Verfahren werden Farbdefinitionen in allen css automatisch gemäß der Festlegungen in der Branding.json gesetzt.


