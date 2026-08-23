// URL de base du backend. Charge AVANT app.js (voir index.html).
//
// "" (vide) = meme origine que la page - c'est le bon reglage pour le web/PWA
// en dev local ou une fois deploye derriere le meme nom de domaine que le
// backend Flask.
//
// Pour l'appli Android empaquetee via Capacitor, la page est servie depuis
// une origine locale (https://localhost dans la WebView), donc il n'y a PAS
// de serveur Flask a cette adresse. Il faut alors remplacer la ligne
// ci-dessous par l'URL PUBLIQUE du backend deploye, par exemple :
//   window.AIDA_API_BASE_URL = "https://api.aida-assistant.com";
// (sans "/api" a la fin, sans slash final)
window.AIDA_API_BASE_URL = "";
