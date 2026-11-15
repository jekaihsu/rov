"""Train torchvision SSD from scratch on exported COCO; never download pretrained weights."""
import argparse
import json
from pathlib import Path


def main():
    import torch
    import torchvision
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset
    from torchvision.transforms.functional import pil_to_tensor

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("model.onnx"))
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable: no usable weights trained; use oracle")
    data = json.loads((args.dataset / "train.json").read_text(encoding="utf-8"))

    class Captures(Dataset):
        def __len__(self):
            return len(data["images"])

        def __getitem__(self, index):
            image = data["images"][index]
            rgb = pil_to_tensor(Image.open(args.dataset / image["file_name"]).convert("RGB")).float() / 255
            labels = []
            boxes = []
            for annotation in data["annotations"]:
                if annotation["image_id"] != image["id"]:
                    continue
                x, y, w, h = annotation["bbox"]
                boxes.append([x, y, x+w, y+h])
                labels.append(annotation["category_id"]+1)
            return rgb.cuda(), {"boxes": torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4).cuda(),
                                "labels": torch.tensor(labels, dtype=torch.int64).cuda()}

    model = torchvision.models.detection.ssd300_vgg16(
        weights=None, weights_backbone=None, num_classes=len(data["categories"])+1).cuda()
    loader = DataLoader(Captures(), batch_size=4, shuffle=True, collate_fn=lambda rows: tuple(zip(*rows)))
    optimizer = torch.optim.SGD(model.parameters(), lr=.001, momentum=.9, weight_decay=.0005)
    model.train()
    for epoch in range(args.epochs):
        for images, targets in loader:
            optimizer.zero_grad()
            loss = sum(model(list(images), list(targets)).values())
            loss.backward()
            optimizer.step()
        print(f"epoch {epoch+1}: loss={loss.item():.5f}", flush=True)
    torch.save(model.state_dict(), args.output.with_suffix(".pt"))
    model.eval()

    class Export(torch.nn.Module):
        def __init__(self, detector):
            super().__init__()
            self.detector = detector

        def forward(self, image):
            result = self.detector([image[0]])[0]
            boxes = result["boxes"] / 300
            xywh = torch.cat((boxes[:, :2], boxes[:, 2:]-boxes[:, :2]), dim=1)
            return torch.cat((xywh, result["scores"][:, None], (result["labels"]-1)[:, None]), dim=1)

    torch.onnx.export(Export(model), torch.zeros(1, 3, 300, 300, device="cuda"), str(args.output),
                      opset_version=17, input_names=["rgb"], output_names=["detections"], dynamo=False)


if __name__ == "__main__":
    main()
