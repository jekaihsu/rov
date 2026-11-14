"""Capture clean onboard RGB and sampled visibility annotations from a running viewer."""
import argparse
import json
import random
from pathlib import Path
from shutil import which


def export_labels(root, records, classes):
    """Write YOLO and COCO with identical deterministic splits, including negatives."""
    counts = {name: 0 for name in classes}
    for split in ("train", "val"):
        images = []
        annotations = []
        for record in records:
            if record["split"] != split:
                continue
            image_id = len(images) + 1
            images.append({"id": image_id, "file_name": record["file"],
                           "width": record["width"], "height": record["height"]})
            lines = []
            for target in record["truth"]:
                category = classes.index(target["category"])
                x, y, w, h = target["box"]
                counts[classes[category]] += 1
                lines.append(f"{category} {x+w/2:.8f} {y+h/2:.8f} {w:.8f} {h:.8f}")
                box = [x*record["width"], y*record["height"], w*record["width"], h*record["height"]]
                annotations.append({"id": len(annotations)+1, "image_id": image_id,
                                    "category_id": category, "bbox": box, "area": box[2]*box[3],
                                    "iscrowd": 0, "occlusion": target["occlusion"],
                                    "distance_m": target["distance_m"]})
            label = root / "labels" / split / (Path(record["file"]).stem + ".txt")
            label.parent.mkdir(parents=True, exist_ok=True)
            label.write_text("\n".join(lines), encoding="utf-8")
        coco = {"images": images, "annotations": annotations,
                "categories": [{"id": i, "name": name} for i, name in enumerate(classes)]}
        (root / f"{split}.json").write_text(json.dumps(coco), encoding="utf-8")
    (root / "statistics.json").write_text(json.dumps(counts), encoding="utf-8")
    (root / "dataset.yaml").write_text(
        f"path: {root.resolve()}\ntrain: images/train\nval: images/val\nnames: {json.dumps(classes)}\n",
        encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/?play=1&nointro&vision&cam=onboard")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()
    if args.frames < 2:
        parser.error("at least two frames required for train/val")
    from playwright.sync_api import sync_playwright
    rng = random.Random(args.seed)
    classes = json.loads(Path(__file__).with_name("classes.json").read_text())
    records = []
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=which("chromium") or which("google-chrome"),
                                    args=["--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(args.url)
        page.wait_for_function("window.rovVision")
        # Use the existing camera hotkey through the UI; do not change physics or authoritative state.
        page.evaluate("window.rovVision.enabled = true")
        for i in range(args.frames):
            page.wait_for_timeout(300)
            truth = page.evaluate("window.rovVision.capture()")
            split = "val" if i % 5 == 0 else "train"
            file = f"images/{split}/{i:06d}.png"
            path = args.output / file
            path.parent.mkdir(parents=True, exist_ok=True)
            canvas = page.locator("#vp canvas").first
            if not canvas.count():
                raise RuntimeError("viewer canvas unavailable")
            canvas.screenshot(path=str(path))
            size = canvas.bounding_box()
            records.append({"file": file, "split": split, "width": int(size["width"]),
                            "height": int(size["height"]), "truth": truth, "seed": args.seed})
            # Seeded control commands generate a short random flight using normal keyboard controls.
            page.keyboard.down(rng.choice(["w", "a", "s", "d"]))
            page.wait_for_timeout(100)
            for key in ("w", "a", "s", "d"):
                page.keyboard.up(key)
        browser.close()
    export_labels(args.output, records, classes)
    (args.output / "capture.json").write_text(json.dumps(records), encoding="utf-8")
    print(f"Exported {len(records)} frames to {args.output}")


if __name__ == "__main__":
    main()
