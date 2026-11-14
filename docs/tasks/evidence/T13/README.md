# T13 local validation evidence

1600×900 before/after and short WebM show a **controlled box fixture**, rendered by Three.js
with the production overlay drawing function. They are projection/overlay validation, not trained
model output or evidence of real-world detection accuracy. The browser test checks the center
against a known camera and box and checks seeded oracle degradation over 10,000 trials.

These small generated files are committed solely to provide durable PR review evidence as requested.
No trained weights, vendored inference libraries, dataset captures, or large binaries are included.

Reproduce with the server on port 8080:
`python simulator/tools/vision/browser_check.py`.

`seastar-scene.png` is an additional capture of existing environment entities through `rovVision.capture`.
The camera was positioned two metres above and one metre behind an instanced seastar and aimed at it.
The same captured RGB and oracle truth were drawn together; both visible seastars are annotated.
This is a tooling camera pose, not a claim that the vehicle flew that trajectory.
