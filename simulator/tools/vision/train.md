# Synthetic vision workflow (experimental)

No usable weights have been trained. No GPU is available in the development environment.
The game defaults to the optional oracle overlay (`?vision&cam=onboard`, N toggles).
Oracle labels are simulator assistance, not evidence of deployed AI accuracy or real vehicle capabilities.

Start `cd simulator && python -m qysim.server`, then from the repository root:

```
python simulator/tools/vision/make_dataset.py --output simulator/output/vision --frames 100
```

Captures use normalized top-left xywh boxes, YOLO center xywh text, and COCO pixel xywh.
Occlusion is a ray sample estimate, not a pixel mask. Bounding boxes cover projected geometry,
including occluded portions. Categories currently follow the existing observation targets;
fish schools are grouped targets. Cable is registered as a geometry target; crack markers are not yet registered.
Train/validation is every fifth frame: adjacent frames can leak similar scenes; collect separate
scenario/seed runs for a defensible evaluation before using model metrics.

On a CUDA workstation create an isolated environment with torch (BSD-3-Clause), torchvision
(BSD-3-Clause), Pillow (MIT-CMU), onnx (Apache-2.0), and run:

```
python simulator/tools/vision/train.py simulator/output/vision --epochs 50 --output model.onnx
```

SSD/VGG architecture is torchvision BSD-3-Clause; `weights=None, weights_backbone=None` prohibits
pretrained downloads. Outputs are self-trained weights, kept outside source control. Review their
training data rights before distribution. Evaluate held-out scenes and real footage; an ONNX export
alone does not establish a usable model. Training/export have not been executed here.

`OnnxDetector` accepts local `runtimeUrl`, `wasmPaths`, `modelUrl`, `size:300`. Supply MIT
onnxruntime-web ESM/WASM files locally after license review; none are vendored or fetched by default.
Worker tries WebGPU then WASM; contract is RGB float NCHW, square resize, [N,6] normalized
[x,y,w,h,score,class] with class IDs matching classes.json. Other models need an adapter.
`RemoteDetector` sends JSON {id,image,width,height} (image: encoded data URL) and expects
{id,detections:[{cls,score,box}]}; start the empty reference service with
`python simulator/tools/vision/remote_server.py`. websockets is BSD-3-Clause.
No Ultralytics code, architecture, or weights are used.

Configure alternative detectors through `window.rovVision.configure({mode:'onnx', ...config})`
or `{mode:'remote',url:'ws://127.0.0.1:8766'}`. Inference defaults to 10 Hz, smooths matched entity
boxes each render, reduces frequency when slow and falls back to oracle above 500 ms or on failure.
This heuristic is not a measured GPU performance guarantee. M shares detected entities through the
existing expedition marker protocol (server visibility/discovery requirements still apply).

SDK extension `get_sim_detections()` requires an active reporting viewer; reports expire after one second.
These are client reports and are not aligned to the SDK's separate synthetic camera frames.
Dataset capture renders and extracts labels in the same JS call. Seeded visibility, silt, light and camera
depth perturbations are recorded; `--trajectory` accepts Three.js position/quaternion poses.
Remaining acceptance work: full detector configuration UI, per-fish/crack registration, broader projection/occlusion fixtures,
real GPU inference/export validation and the <=15% FPS performance measurement.

`?vision-confirm-photo` enables a client-only detection-before-photo guard, otherwise existing
photo rules are unchanged. This does not alter authoritative expedition scoring. Toggle vision
on and use the onboard camera when this option is enabled. It is a simulator workflow assumption,
not a measured capability of any real vehicle. Detector settings can also be supplied via the JS API.
