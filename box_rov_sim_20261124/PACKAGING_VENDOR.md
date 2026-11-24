# Packaging: vendored Three.js (required)
`box_run/viewer/vendor/three/build/three.module.js` MUST be included in every copy, zip and Steam depot.
`viewer/index.html` importmap maps `three` to it; without it main_menu and app.js load blank (no error dialog).
