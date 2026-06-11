import argparse
import os
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from model.BFNet import BFNet


def load_checkpoint(path: Path, device: str):
    try:
        return torch.load(str(path), map_location=device, weights_only=True)
    except TypeError:
        return torch.load(str(path), map_location=device)


def preprocess(image: np.ndarray, testsize: int) -> torch.Tensor:
    resized = cv2.resize(image, (testsize, testsize))
    normalized = resized.astype(np.float32) / 255.0
    return torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0)


def generate_depth_map(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    depth = np.sqrt(grad_x ** 2 + grad_y ** 2)
    depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)
    depth = (depth * 255).astype(np.uint8)
    return cv2.cvtColor(depth, cv2.COLOR_GRAY2RGB)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--testsize", type=int, default=352)
    parser.add_argument(
        "--pth_path",
        type=str,
        default=str((Path(__file__).resolve().parent / "model" / "BFNet.pth").resolve()),
    )
    parser.add_argument(
        "--pvt_path",
        type=str,
        default=str((Path(__file__).resolve().parent / "pvt_v2_b2.pth").resolve()),
    )
    parser.add_argument("--output_dir", type=str, default=str((Path(__file__).resolve().parent / "results").resolve()))
    opt = parser.parse_args()

    image_path = Path(opt.image).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")

    weight_path = Path(opt.pth_path).resolve()
    if not weight_path.exists():
        raise FileNotFoundError(f"model weight not found: {weight_path}")

    pvt_path = Path(opt.pvt_path).resolve()
    if not pvt_path.exists():
        raise FileNotFoundError(f"pvt weight not found: {pvt_path}")

    os.environ["BFNET_PVT_PATH"] = str(pvt_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = BFNet(channel=32, kernel_size=3, reduction=4, bias=False, act=torch.nn.PReLU(), n_resblocks=2, iteration=3)
    checkpoint = load_checkpoint(weight_path, device)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]
    model.load_state_dict(checkpoint)
    model.to(device)
    model.eval()

    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise RuntimeError("image read failed")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    image_tensor = preprocess(rgb, opt.testsize).to(device)
    depth_tensor = preprocess(generate_depth_map(rgb), opt.testsize).to(device)
    x_in = torch.cat((image_tensor, depth_tensor), dim=0)

    with torch.no_grad():
        stage_preds, final_pred = model(x_in)
        _ = stage_preds

    resized_pred = F.interpolate(torch.sigmoid(final_pred), size=rgb.shape[:2], mode="bilinear", align_corners=False)
    mask = resized_pred.squeeze().cpu().numpy()
    mask = (mask > 0.5).astype(np.uint8) * 255

    contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    vis = rgb.copy()
    cv2.drawContours(vis, contours, -1, (0, 255, 0), 2)

    output_dir = Path(opt.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = image_path.stem
    mask_path = output_dir / f"{stem}_mask.png"
    vis_path = output_dir / f"{stem}_vis.png"
    cv2.imwrite(str(mask_path), mask)
    cv2.imwrite(str(vis_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    print(f"mask: {mask_path}")
    print(f"visualization: {vis_path}")


if __name__ == "__main__":
    main()
