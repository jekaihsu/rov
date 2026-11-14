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
fish schools are grouped targets. Cable and crack instances are not yet registered.
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

Remaining acceptance work: UI detector selection and inference scheduling/interpolation for ONNX/remote,
automatic integrated-GPU fallback, GPU performance budget, synchronized render capture, full domain
randomization and recorded trajectories, minimap marking, optional mission gating and SDK result transport.
The current dataset tool captures a short keyboard-driven flight; it does not yet provide those guarantees.
