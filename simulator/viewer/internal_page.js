// Standalone diagnostics and the instructor console are internal desktop surfaces.
if (window.rovDesktop?.edition === 'steam') {
  document.documentElement.hidden = true;
  location.replace('/?menu=main');
}
