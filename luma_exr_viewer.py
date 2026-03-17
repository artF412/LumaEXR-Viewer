import argparse
import os
from pathlib import Path
from typing import Optional

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "LumaEXR Viewer"
APP_ICON_PATH = Path(__file__).with_name("assets") / "app_icon.png"


def clamp_highlights(rgb: np.ndarray, percentile: float = 99.97) -> np.ndarray:
    peak_map = np.max(rgb, axis=2)
    valid = peak_map[peak_map > 0.0]
    if valid.size == 0:
        return rgb

    clip_value = float(np.percentile(valid, percentile))
    if clip_value <= 0.0:
        return rgb

    scale = np.minimum(1.0, clip_value / np.maximum(peak_map, 1e-6))
    return rgb * scale[..., None]


def despeckle_highlights(
    rgb: np.ndarray,
    ratio_threshold: float = 6.0,
    floor_percentile: float = 99.5,
) -> np.ndarray:
    luminance = (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    ).astype(np.float32)
    median_rgb = np.dstack([cv2.medianBlur(rgb[..., channel], 3) for channel in range(3)])
    median_luminance = (
        median_rgb[..., 0] * 0.2126
        + median_rgb[..., 1] * 0.7152
        + median_rgb[..., 2] * 0.0722
    ).astype(np.float32)

    floor_value = float(np.percentile(luminance[luminance > 0.0], floor_percentile)) if np.any(luminance > 0.0) else 0.0
    hot_mask = (luminance > floor_value) & (luminance > median_luminance * ratio_threshold)
    if not np.any(hot_mask):
        return rgb

    filtered = rgb.copy()
    filtered[hot_mask] = median_rgb[hot_mask]
    return filtered


def prepare_display_image(rgb: np.ndarray, clamp_enabled: bool, denoise_enabled: bool) -> np.ndarray:
    image = rgb
    if denoise_enabled:
        image = despeckle_highlights(image)
    if clamp_enabled:
        image = clamp_highlights(image)
    return image


def tone_map(rgb: np.ndarray, exposure: float) -> np.ndarray:
    scaled = np.maximum(rgb, 0.0) * (2.0 ** exposure)
    mapped = scaled / (1.0 + scaled)
    gamma = np.power(np.clip(mapped, 0.0, 1.0), 1.0 / 2.2)
    return (gamma * 255.0).clip(0, 255).astype(np.uint8)


def resize_for_preview(image: np.ndarray, max_size: int = 1200) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(max_size / max(height, width), 1.0)
    if scale == 1.0:
        return image
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def load_exr(path: str) -> np.ndarray:
    raw = cv2.imread(path, cv2.IMREAD_ANYCOLOR | cv2.IMREAD_ANYDEPTH)
    if raw is None:
        raise ValueError(f"Cannot read EXR file: {path}")
    if raw.ndim == 2:
        raw = np.repeat(raw[..., None], 3, axis=2)
    rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
    rgb = np.nan_to_num(rgb.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    return np.maximum(rgb, 0.0)


class HDRViewerApp:
    def __init__(self, root: tk.Tk, initial_path: Optional[str] = None):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1400x900")

        self.image_rgb: Optional[np.ndarray] = None
        self.preview_rgb: Optional[np.ndarray] = None
        self.current_path: Optional[str] = None
        self.preview_ref: Optional[ImageTk.PhotoImage] = None
        self.preview_image: Optional[np.ndarray] = None
        self.refresh_job: Optional[str] = None

        self.exposure_var = tk.DoubleVar(value=0.0)
        self.clamp_var = tk.BooleanVar(value=True)
        self.denoise_var = tk.BooleanVar(value=True)

        self._set_app_icon()
        self._build_layout()

        if initial_path:
            self.open_path(initial_path)

    def _set_app_icon(self) -> None:
        if not APP_ICON_PATH.exists():
            return
        try:
            icon = tk.PhotoImage(file=str(APP_ICON_PATH))
        except tk.TclError:
            return
        self.root.iconphoto(True, icon)
        self.root._app_icon = icon

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=12)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(3, weight=1)

        ttk.Button(toolbar, text="Open EXR", command=self.ask_open).grid(row=0, column=0, sticky="w")
        ttk.Label(toolbar, text="Exposure").grid(row=0, column=1, sticky="w", padx=(16, 8))
        ttk.Scale(toolbar, variable=self.exposure_var, from_=-6.0, to=6.0).grid(row=0, column=2, sticky="ew")
        ttk.Checkbutton(toolbar, text="Clamp Highlights", variable=self.clamp_var, command=self.schedule_preview_refresh).grid(
            row=0, column=4, sticky="w", padx=(12, 0)
        )
        ttk.Checkbutton(toolbar, text="Denoise Speckles", variable=self.denoise_var, command=self.schedule_preview_refresh).grid(
            row=0, column=5, sticky="w", padx=(12, 0)
        )
        ttk.Button(toolbar, text="Save JPG", command=self.save_jpg).grid(row=0, column=6, sticky="e", padx=(12, 0))

        self.exposure_text = tk.StringVar(value="0.00 EV")
        ttk.Label(toolbar, textvariable=self.exposure_text, width=10).grid(row=0, column=3, sticky="w", padx=(10, 0))

        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(self.root, textvariable=self.path_var, padding=(12, 0, 12, 8)).grid(row=2, column=0, sticky="ew")

        self.image_label = ttk.Label(self.root, anchor="center")
        self.image_label.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.exposure_var.trace_add("write", lambda *_: self.schedule_preview_refresh())

    def ask_open(self) -> None:
        path = filedialog.askopenfilename(
            title="Open EXR / HDR image",
            filetypes=[
                ("OpenEXR / HDR", "*.exr *.hdr"),
                ("EXR only", "*.exr"),
                ("Radiance HDR", "*.hdr"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        try:
            self.image_rgb = load_exr(path)
        except Exception as exc:
            messagebox.showerror("Open EXR failed", str(exc))
            return

        self.preview_rgb = resize_for_preview(self.image_rgb)
        self.current_path = path
        self.path_var.set(str(Path(path).resolve()))
        self.refresh_preview()

    def schedule_preview_refresh(self) -> None:
        self.exposure_text.set(f"{self.exposure_var.get():.2f} EV")
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
        self.refresh_job = self.root.after(40, self.refresh_preview)

    def refresh_preview(self) -> None:
        self.refresh_job = None
        self.exposure_text.set(f"{self.exposure_var.get():.2f} EV")
        if self.preview_rgb is None:
            return

        processed = prepare_display_image(
            self.preview_rgb,
            clamp_enabled=self.clamp_var.get(),
            denoise_enabled=self.denoise_var.get(),
        )
        preview = tone_map(processed, self.exposure_var.get())
        self.preview_image = preview
        photo = ImageTk.PhotoImage(Image.fromarray(preview))
        self.preview_ref = photo
        self.image_label.configure(image=photo)

    def save_jpg(self) -> None:
        if self.image_rgb is None or self.current_path is None:
            messagebox.showinfo("No image", "Open an EXR file first.")
            return

        default_name = f"{Path(self.current_path).stem}_preview.jpg"
        output = filedialog.asksaveasfilename(
            title="Save JPG preview",
            defaultextension=".jpg",
            initialfile=default_name,
            filetypes=[("JPEG image", "*.jpg"), ("JPEG image", "*.jpeg")],
        )
        if not output:
            return

        processed = prepare_display_image(
            self.image_rgb,
            clamp_enabled=self.clamp_var.get(),
            denoise_enabled=self.denoise_var.get(),
        )
        full_image = tone_map(processed, self.exposure_var.get())
        Image.fromarray(full_image).save(output, format="JPEG", quality=95)
        messagebox.showinfo("Saved", f"Saved JPG to:\n{output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple viewer for EXR HDR images.")
    parser.add_argument("path", nargs="?", help="Optional EXR path to open immediately.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = tk.Tk()
    HDRViewerApp(root, initial_path=args.path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
