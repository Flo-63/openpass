/*!
===============================================================================
Project   : openpass
Script    : tailwind.config.js
Created   : 18.10.2025
Author    : Florian
Purpose   : [Describe the purpose of this script.]

@docstyle: google
@language: english
@voice: imperative
===============================================================================
*/
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./blueprints/**/*.html",
    "./static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#2563eb", dark: "#1e40af" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
