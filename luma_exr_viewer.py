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
CANVAS_BG = "#f3efe8"
CANVAS_TEXT = "#7a6f64"


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
        self.zoom_factor = 1.0
        self.fit_zoom = 1.0
        self.display_width = 0
        self.display_height = 0
        self.display_offset_x = 0
        self.display_offset_y = 0
        self.scroll_width = 0
        self.scroll_height = 0

        self.exposure_var = tk.DoubleVar(value=0.0)
        self.clamp_var = tk.BooleanVar(value=True)
        self.denoise_var = tk.BooleanVar(value=True)
        self.zoom_text = tk.StringVar(value="100%")

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
        ttk.Button(toolbar, text="Zoom -", command=lambda: self.change_zoom(0.8)).grid(row=0, column=6, sticky="w", padx=(12, 0))
        ttk.Button(toolbar, text="Zoom +", command=lambda: self.change_zoom(1.25)).grid(row=0, column=7, sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Fit", command=self.reset_zoom_to_fit).grid(row=0, column=8, sticky="w", padx=(8, 0))
        ttk.Label(toolbar, textvariable=self.zoom_text, width=8).grid(row=0, column=9, sticky="w", padx=(8, 0))
        ttk.Button(toolbar, text="Save JPG", command=self.save_jpg).grid(row=0, column=10, sticky="e", padx=(12, 0))

        self.exposure_text = tk.StringVar(value="0.00 EV")
        ttk.Label(toolbar, textvariable=self.exposure_text, width=10).grid(row=0, column=3, sticky="w", padx=(10, 0))

        self.path_var = tk.StringVar(value="No file selected")
        ttk.Label(self.root, textvariable=self.path_var, padding=(12, 0, 12, 8)).grid(row=2, column=0, sticky="ew")

        viewer_frame = ttk.Frame(self.root)
        viewer_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        viewer_frame.columnconfigure(0, weight=1)
        viewer_frame.rowconfigure(0, weight=1)

        self.image_canvas = tk.Canvas(viewer_frame, background=CANVAS_BG, highlightthickness=0)
        self.image_canvas.grid(row=0, column=0, sticky="nsew")

        self.y_scroll = ttk.Scrollbar(viewer_frame, orient="vertical", command=self.image_canvas.yview)
        self.y_scroll.grid(row=0, column=1, sticky="ns")
        self.x_scroll = ttk.Scrollbar(viewer_frame, orient="horizontal", command=self.image_canvas.xview)
        self.x_scroll.grid(row=1, column=0, sticky="ew")
        self.image_canvas.configure(xscrollcommand=self.x_scroll.set, yscrollcommand=self.y_scroll.set)

        self.image_canvas.bind("<Configure>", self._on_canvas_resize)
        self.image_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.image_canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.image_canvas.bind("<B1-Motion>", self._on_pan_move)

        self.exposure_var.trace_add("write", lambda *_: self.schedule_preview_refresh())
        self._draw_empty_state()

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
            self._draw_empty_state()
            return

        preserve_view = self.preview_image is not None
        view_x: Optional[float] = None
        view_y: Optional[float] = None

        if preserve_view:
            view_x = self.image_canvas.xview()[0]
            view_y = self.image_canvas.yview()[0]

        processed = prepare_display_image(
            self.preview_rgb,
            clamp_enabled=self.clamp_var.get(),
            denoise_enabled=self.denoise_var.get(),
        )
        preview = tone_map(processed, self.exposure_var.get())
        self.preview_image = preview
        self._update_fit_zoom()
        self._render_canvas_image(
            reset_zoom=not preserve_view,
            view_x=view_x,
            view_y=view_y,
        )

    def _draw_empty_state(self) -> None:
        self.image_canvas.delete("all")
        canvas_width = max(self.image_canvas.winfo_width(), 1)
        canvas_height = max(self.image_canvas.winfo_height(), 1)
        center_x = canvas_width // 2
        center_y = canvas_height // 2
        self.image_canvas.create_text(
            center_x,
            center_y - 14,
            text="Open an EXR file to start",
            fill=CANVAS_TEXT,
            font=("Segoe UI", 18, "bold"),
        )
        self.image_canvas.create_text(
            center_x,
            center_y + 18,
            text="Mouse wheel to zoom, drag to pan",
            fill=CANVAS_TEXT,
            font=("Segoe UI", 11),
        )
        self.image_canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
        self.x_scroll.set(0.0, 1.0)
        self.y_scroll.set(0.0, 1.0)
        self.zoom_text.set("Fit")

    def _render_canvas_image(
        self,
        reset_zoom: bool = False,
        anchor_canvas_x: Optional[float] = None,
        anchor_canvas_y: Optional[float] = None,
        anchor_image_u: Optional[float] = None,
        anchor_image_v: Optional[float] = None,
        view_x: Optional[float] = None,
        view_y: Optional[float] = None,
    ) -> None:
        if self.preview_image is None:
            return

        if reset_zoom:
            self._update_fit_zoom()
            self.zoom_factor = 1.0

        base_height, base_width = self.preview_image.shape[:2]
        display_zoom = max(self.fit_zoom * self.zoom_factor, 0.05)
        display_width = max(1, int(base_width * display_zoom))
        display_height = max(1, int(base_height * display_zoom))
        canvas_width = max(self.image_canvas.winfo_width(), 1)
        canvas_height = max(self.image_canvas.winfo_height(), 1)

        interpolation = cv2.INTER_LINEAR if display_zoom >= 1.0 else cv2.INTER_AREA
        display_image = cv2.resize(self.preview_image, (display_width, display_height), interpolation=interpolation)
        offset_x = max((canvas_width - display_width) // 2, 0)
        offset_y = max((canvas_height - display_height) // 2, 0)
        scroll_width = max(display_width, canvas_width)
        scroll_height = max(display_height, canvas_height)
        self.display_width = display_width
        self.display_height = display_height
        self.display_offset_x = offset_x
        self.display_offset_y = offset_y
        self.scroll_width = scroll_width
        self.scroll_height = scroll_height

        photo = ImageTk.PhotoImage(Image.fromarray(display_image))
        self.preview_ref = photo
        self.image_canvas.delete("all")
        self.image_canvas.create_image(offset_x, offset_y, anchor="nw", image=photo)
        self.image_canvas.configure(scrollregion=(0, 0, scroll_width, scroll_height))

        if (
            anchor_canvas_x is not None
            and anchor_canvas_y is not None
            and anchor_image_u is not None
            and anchor_image_v is not None
        ):
            self._restore_view_anchor(anchor_canvas_x, anchor_canvas_y, anchor_image_u, anchor_image_v)
        elif view_x is not None and view_y is not None:
            self._restore_view_fraction(view_x, view_y)
        elif reset_zoom:
            self._center_view()

        self.zoom_text.set(f"{display_zoom * 100:.0f}%")

    def _center_view(self) -> None:
        canvas_width = max(self.image_canvas.winfo_width(), 1)
        canvas_height = max(self.image_canvas.winfo_height(), 1)
        if self.scroll_width > canvas_width:
            left = max((self.scroll_width - canvas_width) / 2.0, 0.0)
            self.image_canvas.xview_moveto(left / max(self.scroll_width, 1))
        else:
            self.image_canvas.xview_moveto(0.0)
        if self.scroll_height > canvas_height:
            top = max((self.scroll_height - canvas_height) / 2.0, 0.0)
            self.image_canvas.yview_moveto(top / max(self.scroll_height, 1))
        else:
            self.image_canvas.yview_moveto(0.0)

    def _capture_anchor(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        content_x = self.image_canvas.canvasx(canvas_x)
        content_y = self.image_canvas.canvasy(canvas_y)
        image_u = (content_x - self.display_offset_x) / max(self.display_width, 1)
        image_v = (content_y - self.display_offset_y) / max(self.display_height, 1)
        return image_u, image_v

    def _restore_view_anchor(self, canvas_x: float, canvas_y: float, image_u: float, image_v: float) -> None:
        canvas_width = max(self.image_canvas.winfo_width(), 1)
        canvas_height = max(self.image_canvas.winfo_height(), 1)
        target_x = self.display_offset_x + image_u * self.display_width
        target_y = self.display_offset_y + image_v * self.display_height
        left = target_x - canvas_x
        top = target_y - canvas_y
        max_left = max(self.scroll_width - canvas_width, 0)
        max_top = max(self.scroll_height - canvas_height, 0)
        left = min(max(left, 0.0), max_left)
        top = min(max(top, 0.0), max_top)
        self.image_canvas.xview_moveto(0.0 if self.scroll_width <= canvas_width else left / self.scroll_width)
        self.image_canvas.yview_moveto(0.0 if self.scroll_height <= canvas_height else top / self.scroll_height)

    def _restore_view_fraction(self, view_x: float, view_y: float) -> None:
        self.image_canvas.xview_moveto(min(max(view_x, 0.0), 1.0))
        self.image_canvas.yview_moveto(min(max(view_y, 0.0), 1.0))

    def _update_fit_zoom(self) -> None:
        if self.preview_image is None:
            self.fit_zoom = 1.0
            return

        canvas_width = max(self.image_canvas.winfo_width(), 1)
        canvas_height = max(self.image_canvas.winfo_height(), 1)
        image_height, image_width = self.preview_image.shape[:2]
        self.fit_zoom = min(canvas_width / image_width, canvas_height / image_height)

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        if self.preview_image is None:
            self._draw_empty_state()
            return
        previous_fit = self.fit_zoom
        self._update_fit_zoom()
        if abs(previous_fit - self.fit_zoom) > 1e-3 and self.zoom_factor == 1.0:
            self._render_canvas_image(reset_zoom=False)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.preview_image is None:
            return
        factor = 1.1 if event.delta > 0 else 1.0 / 1.1
        self.change_zoom(factor, anchor_canvas_x=event.x, anchor_canvas_y=event.y)

    def _on_pan_start(self, event: tk.Event) -> None:
        self.image_canvas.scan_mark(event.x, event.y)

    def _on_pan_move(self, event: tk.Event) -> None:
        self.image_canvas.scan_dragto(event.x, event.y, gain=1)

    def change_zoom(
        self,
        factor: float,
        anchor_canvas_x: Optional[float] = None,
        anchor_canvas_y: Optional[float] = None,
    ) -> None:
        if self.preview_image is None:
            return
        if anchor_canvas_x is None or anchor_canvas_y is None:
            anchor_canvas_x = self.image_canvas.winfo_width() / 2.0
            anchor_canvas_y = self.image_canvas.winfo_height() / 2.0

        image_u, image_v = self._capture_anchor(anchor_canvas_x, anchor_canvas_y)
        self.zoom_factor = min(max(self.zoom_factor * factor, 0.25), 16.0)
        self._render_canvas_image(
            reset_zoom=False,
            anchor_canvas_x=anchor_canvas_x,
            anchor_canvas_y=anchor_canvas_y,
            anchor_image_u=image_u,
            anchor_image_v=image_v,
        )

    def reset_zoom_to_fit(self) -> None:
        if self.preview_image is None:
            return
        self.zoom_factor = 1.0
        self._render_canvas_image(reset_zoom=False)

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
