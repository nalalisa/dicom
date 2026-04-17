from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pydicom
from pydicom.tag import Tag

from ge_vivid_spacing_extract import KRETZ_CREATOR_TAG, KRETZ_MAGIC, KRETZ_PAYLOAD_TAG

# Set only this path and run the script.
DICOM_PATH = r""

# Optional settings.
OUTPUT_DIR = Path("ge_scanconvert_output")
OUTPUT_SPACING_MM = None  # Example: (0.667, 0.667, 0.667). None => use payload candidate or fallback.
FALLBACK_SPACING_MM = (0.667, 0.667, 0.667)
SAVE_VOLUME_NPY = False
MAX_TOTAL_VOXELS = 64_000_000


def load_dicom(path: Path) -> pydicom.Dataset:
    return pydicom.dcmread(str(path), defer_size="1 MB")


def ensure_kretz_payload(ds: pydicom.Dataset) -> bytes:
    creator = str(ds.get(KRETZ_CREATOR_TAG).value) if KRETZ_CREATOR_TAG in ds else ""
    if creator != "KRETZ_US" or KRETZ_PAYLOAD_TAG not in ds:
        raise RuntimeError(
            "This script currently supports GE KRETZ_US payloads only. "
            "The given DICOM does not expose (7FE1,0011)=KRETZ_US and (7FE1,1101)."
        )
    payload = bytes(ds[KRETZ_PAYLOAD_TAG].value)
    if not payload.startswith(KRETZ_MAGIC):
        raise RuntimeError("Private payload found, but it does not start with KRETZFILE 1.0.")
    return payload


def buffer_to_float_array(buffer: memoryview) -> np.ndarray:
    if len(buffer) == 0:
        return np.array([], dtype=np.float64)
    if len(buffer) % 8 == 0:
        return np.frombuffer(buffer, dtype="<f8").copy()
    if len(buffer) % 4 == 0:
        return np.frombuffer(buffer, dtype="<f4").astype(np.float64)
    raise ValueError(f"Cannot interpret buffer of length {len(buffer)} as float array")


def parse_kretz_payload_full(payload: bytes) -> dict:
    pos = len(KRETZ_MAGIC)
    dims = [None, None, None]
    theta_angles = np.array([], dtype=np.float64)
    phi_angles = np.array([], dtype=np.float64)
    radial_resolution_mm = None
    offset1 = None
    offset2 = None
    cartesian_spacing_candidate = None
    voxel_data = None

    while pos + 8 <= len(payload):
        group, element, item_size = struct.unpack_from("<HHI", payload, pos)
        pos += 8
        end = pos + item_size
        if end > len(payload):
            break

        buffer = memoryview(payload)[pos:end]
        pos = end

        if (group, element) == (0xC000, 0x0001):
            dims[0] = struct.unpack_from("<H", buffer, 0)[0]
        elif (group, element) == (0xC000, 0x0002):
            dims[1] = struct.unpack_from("<H", buffer, 0)[0]
        elif (group, element) == (0xC000, 0x0003):
            dims[2] = struct.unpack_from("<H", buffer, 0)[0]
        elif (group, element) == (0xC100, 0x0001):
            radial_resolution_mm = struct.unpack_from("<d", buffer, 0)[0] * 1000.0
        elif (group, element) == (0xC200, 0x0001):
            offset1 = struct.unpack_from("<d", buffer, 0)[0]
        elif (group, element) == (0xC200, 0x0002):
            offset2 = struct.unpack_from("<d", buffer, 0)[0]
        elif (group, element) == (0xC300, 0x0001):
            phi_angles = buffer_to_float_array(buffer)
        elif (group, element) == (0xC300, 0x0002):
            theta_angles = buffer_to_float_array(buffer)
        elif (group, element) == (0x0010, 0x0022):
            if len(buffer) >= 8:
                cartesian_spacing_candidate = struct.unpack_from("<d", buffer, 0)[0]
            elif len(buffer) >= 4:
                cartesian_spacing_candidate = float(struct.unpack_from("<f", buffer, 0)[0])
        elif (group, element) == (0xD000, 0x0001):
            voxel_data = bytes(buffer)

    if any(v is None for v in dims):
        raise RuntimeError(f"Failed to parse KRETZ dimensions from payload: {dims}")
    if radial_resolution_mm is None or offset1 is None or offset2 is None:
        raise RuntimeError("Failed to parse KRETZ radial resolution or offsets.")
    if voxel_data is None:
        raise RuntimeError("Failed to parse KRETZ voxel data.")
    if len(theta_angles) != dims[1] or len(phi_angles) != dims[2]:
        raise RuntimeError(
            f"Angle array lengths do not match dimensions: theta={len(theta_angles)} dim_j={dims[1]}, "
            f"phi={len(phi_angles)} dim_k={dims[2]}"
        )

    dim_i, dim_j, dim_k = [int(v) for v in dims]
    expected_voxels = dim_i * dim_j * dim_k
    if len(voxel_data) != expected_voxels:
        if len(voxel_data) % expected_voxels != 0:
            raise RuntimeError(
                f"Voxel data length {len(voxel_data)} is incompatible with dimensions {dims}."
            )
        bytes_per_sample = len(voxel_data) // expected_voxels
        if bytes_per_sample != 1:
            raise RuntimeError(
                f"Voxel data implies {bytes_per_sample} bytes per sample; this script currently expects 8-bit data."
            )

    raw_volume = (
        np.frombuffer(voxel_data, dtype=np.uint8)
        .reshape((dim_k, dim_j, dim_i))
        .transpose(2, 1, 0)
        .copy()
    )

    radial_start_mm = offset1 * radial_resolution_mm
    radial_end_mm = radial_start_mm + max(dim_i - 1, 0) * radial_resolution_mm
    bmode_radius_mm = -offset2 * radial_resolution_mm

    return {
        "dims_ijk": [dim_i, dim_j, dim_k],
        "theta_angles_rad": theta_angles,
        "phi_angles_rad": phi_angles,
        "theta_angles_deg": np.rad2deg(theta_angles),
        "phi_angles_deg": np.rad2deg(phi_angles),
        "radial_resolution_mm": radial_resolution_mm,
        "radial_start_mm": radial_start_mm,
        "radial_end_mm": radial_end_mm,
        "bmode_radius_mm": bmode_radius_mm,
        "cartesian_spacing_candidate_mm": cartesian_spacing_candidate,
        "raw_volume": raw_volume,
    }


def choose_output_spacing(info: dict) -> tuple[float, float, float]:
    if OUTPUT_SPACING_MM is not None:
        return tuple(float(v) for v in OUTPUT_SPACING_MM)

    candidate = info.get("cartesian_spacing_candidate_mm")
    if candidate is not None and 0.05 <= float(candidate) <= 5.0:
        value = float(candidate)
        return (value, value, value)
    return tuple(float(v) for v in FALLBACK_SPACING_MM)


def compute_cartesian_grid(info: dict, spacing_mm: tuple[float, float, float]) -> dict:
    theta = info["theta_angles_rad"] - (math.pi / 2.0)
    phi = info["phi_angles_rad"] - (math.pi / 2.0)
    r0 = info["radial_start_mm"]
    r1 = info["radial_end_mm"]
    b = info["bmode_radius_mm"]

    theta_sin = np.sin(theta)[None, :]
    theta_cos = np.cos(theta)[None, :]
    phi_sin = np.sin(phi)[:, None]
    phi_cos = np.cos(phi)[:, None]

    bounds = {
        "x_min": math.inf,
        "x_max": -math.inf,
        "y_min": math.inf,
        "y_max": -math.inf,
        "z_min": math.inf,
        "z_max": -math.inf,
    }
    for radius_mm in (r0, r1):
        x = radius_mm * theta_sin
        y = -(radius_mm * theta_cos - b) * phi_sin
        z = b * (1.0 - phi_cos) + radius_mm * theta_cos * phi_cos
        bounds["x_min"] = min(bounds["x_min"], float(x.min()))
        bounds["x_max"] = max(bounds["x_max"], float(x.max()))
        bounds["y_min"] = min(bounds["y_min"], float(y.min()))
        bounds["y_max"] = max(bounds["y_max"], float(y.max()))
        bounds["z_min"] = min(bounds["z_min"], float(z.min()))
        bounds["z_max"] = max(bounds["z_max"], float(z.max()))

    sx, sy, sz = spacing_mm
    nx = int(math.ceil((bounds["x_max"] - bounds["x_min"]) / sx)) + 1
    ny = int(math.ceil((bounds["y_max"] - bounds["y_min"]) / sy)) + 1
    nz = int(math.ceil((bounds["z_max"] - bounds["z_min"]) / sz)) + 1

    total_voxels = nx * ny * nz
    if total_voxels > MAX_TOTAL_VOXELS:
        raise RuntimeError(
            f"Requested reconstruction grid is too large: {nx}x{ny}x{nz}={total_voxels:,} voxels. "
            "Increase OUTPUT_SPACING_MM or lower resolution."
        )

    x_coords = bounds["x_min"] + np.arange(nx) * sx
    y_coords = bounds["y_min"] + np.arange(ny) * sy
    z_coords = bounds["z_min"] + np.arange(nz) * sz
    return {
        "bounds_mm": bounds,
        "spacing_mm": spacing_mm,
        "shape_xyz": (nx, ny, nz),
        "x_coords": x_coords,
        "y_coords": y_coords,
        "z_coords": z_coords,
        "origin_mm": [bounds["x_min"], bounds["y_min"], bounds["z_min"]],
    }


def fractional_angle_index(values: np.ndarray, axis_values: np.ndarray) -> np.ndarray:
    return np.interp(values, axis_values, np.arange(len(axis_values), dtype=np.float64))


def trilinear_sample(volume: np.ndarray, i_f: np.ndarray, j_f: np.ndarray, k_f: np.ndarray, valid: np.ndarray) -> np.ndarray:
    output = np.zeros(i_f.shape, dtype=np.float32)
    if not np.any(valid):
        return output

    flat_valid = valid.ravel()
    i_vals = i_f.ravel()[flat_valid]
    j_vals = j_f.ravel()[flat_valid]
    k_vals = k_f.ravel()[flat_valid]

    dim_i, dim_j, dim_k = volume.shape

    i0 = np.floor(i_vals).astype(np.int32)
    j0 = np.floor(j_vals).astype(np.int32)
    k0 = np.floor(k_vals).astype(np.int32)

    i1 = np.clip(i0 + 1, 0, dim_i - 1)
    j1 = np.clip(j0 + 1, 0, dim_j - 1)
    k1 = np.clip(k0 + 1, 0, dim_k - 1)

    di = np.where(i1 == i0, 0.0, i_vals - i0)
    dj = np.where(j1 == j0, 0.0, j_vals - j0)
    dk = np.where(k1 == k0, 0.0, k_vals - k0)

    c000 = volume[i0, j0, k0].astype(np.float32)
    c100 = volume[i1, j0, k0].astype(np.float32)
    c010 = volume[i0, j1, k0].astype(np.float32)
    c110 = volume[i1, j1, k0].astype(np.float32)
    c001 = volume[i0, j0, k1].astype(np.float32)
    c101 = volume[i1, j0, k1].astype(np.float32)
    c011 = volume[i0, j1, k1].astype(np.float32)
    c111 = volume[i1, j1, k1].astype(np.float32)

    c00 = c000 * (1 - di) + c100 * di
    c10 = c010 * (1 - di) + c110 * di
    c01 = c001 * (1 - di) + c101 * di
    c11 = c011 * (1 - di) + c111 * di

    c0 = c00 * (1 - dj) + c10 * dj
    c1 = c01 * (1 - dj) + c11 * dj
    values = c0 * (1 - dk) + c1 * dk

    output_flat = output.ravel()
    output_flat[flat_valid] = values
    return output


def scan_convert_volume(info: dict, grid: dict) -> np.ndarray:
    raw = info["raw_volume"]
    theta_axis = info["theta_angles_rad"]
    phi_axis = info["phi_angles_rad"]
    radial_start_mm = info["radial_start_mm"]
    radial_end_mm = info["radial_end_mm"]
    radial_resolution_mm = info["radial_resolution_mm"]
    b = info["bmode_radius_mm"]

    x_coords = grid["x_coords"]
    y_coords = grid["y_coords"]
    z_coords = grid["z_coords"]
    nx, ny, nz = grid["shape_xyz"]

    volume = np.zeros((nz, ny, nx), dtype=np.uint8)
    xv, yv = np.meshgrid(x_coords, y_coords, indexing="xy")

    theta_min = float(theta_axis[0])
    theta_max = float(theta_axis[-1])
    phi_min = float(phi_axis[0])
    phi_max = float(phi_axis[-1])

    for iz, z in enumerate(z_coords):
        w = z - b
        u_minus_b = np.hypot(yv, w)
        u = b + u_minus_b
        r = np.hypot(xv, u)

        theta_shift = np.arctan2(xv, u)
        phi_shift = np.arctan2(-yv, w)
        theta_raw = theta_shift + (math.pi / 2.0)
        phi_raw = phi_shift + (math.pi / 2.0)

        valid = (
            (r >= radial_start_mm)
            & (r <= radial_end_mm)
            & (theta_raw >= theta_min)
            & (theta_raw <= theta_max)
            & (phi_raw >= phi_min)
            & (phi_raw <= phi_max)
        )

        i_f = (r - radial_start_mm) / radial_resolution_mm
        j_f = fractional_angle_index(theta_raw, theta_axis)
        k_f = fractional_angle_index(phi_raw, phi_axis)

        slice_data = trilinear_sample(raw, i_f, j_f, k_f, valid)
        volume[iz] = np.clip(np.round(slice_data), 0, 255).astype(np.uint8)

        if (iz + 1) % max(1, nz // 10) == 0 or iz == nz - 1:
            print(f"Scan converting: {iz + 1}/{nz} slices")

    return volume


def save_slice_figure(volume: np.ndarray, output_dir: Path) -> Path:
    nz, ny, nx = volume.shape
    axial = volume[nz // 2, :, :]
    coronal = volume[:, ny // 2, :]
    sagittal = volume[:, :, nx // 2]
    mip = volume.max(axis=0)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    items = [
        ("Axial (middle z)", axial),
        ("Coronal (middle y)", coronal),
        ("Sagittal (middle x)", sagittal),
        ("MIP (z max projection)", mip),
    ]
    for ax, (title, image) in zip(axes.ravel(), items):
        ax.imshow(image, cmap="gray", origin="lower")
        ax.set_title(title)
        ax.axis("off")

    fig.tight_layout()
    out_path = output_dir / "scan_converted_slices.png"
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def save_sector_outline(info: dict, output_dir: Path) -> Path:
    theta_deg = info["theta_angles_deg"]
    theta_rad = np.deg2rad(theta_deg - 90.0)
    r0 = info["radial_start_mm"]
    r1 = info["radial_end_mm"]

    fig, ax = plt.subplots(figsize=(6, 6))
    for radius_mm, style in ((r0, "--"), (r1, "-")):
        x = radius_mm * np.sin(theta_rad)
        z = radius_mm * np.cos(theta_rad)
        ax.plot(x, z, style, linewidth=2, label=f"r={radius_mm:.1f} mm")

    for theta_edge in (theta_rad[0], theta_rad[-1]):
        x = np.array([r0 * np.sin(theta_edge), r1 * np.sin(theta_edge)])
        z = np.array([r0 * np.cos(theta_edge), r1 * np.cos(theta_edge)])
        ax.plot(x, z, "k-", linewidth=1)

    ax.set_title("Extracted Sector Outline")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("z (mm)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out_path = output_dir / "sector_outline.png"
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return out_path


def build_summary(dicom_path: Path, info: dict, grid: dict, output_dir: Path) -> dict:
    return {
        "input_file": str(dicom_path),
        "raw_geometry": {
            "dims_ijk": info["dims_ijk"],
            "radial_resolution_mm": info["radial_resolution_mm"],
            "radial_start_mm": info["radial_start_mm"],
            "radial_end_mm": info["radial_end_mm"],
            "bmode_radius_mm": info["bmode_radius_mm"],
            "theta_range_deg": [float(info["theta_angles_deg"][0]), float(info["theta_angles_deg"][-1])],
            "phi_range_deg": [float(info["phi_angles_deg"][0]), float(info["phi_angles_deg"][-1])],
            "cartesian_spacing_candidate_mm": info["cartesian_spacing_candidate_mm"],
        },
        "scan_conversion": {
            "output_spacing_mm": list(grid["spacing_mm"]),
            "origin_mm": grid["origin_mm"],
            "shape_xyz": list(grid["shape_xyz"]),
            "bounds_mm": grid["bounds_mm"],
        },
        "artifacts": {
            "slice_figure": str(output_dir / "scan_converted_slices.png"),
            "sector_outline": str(output_dir / "sector_outline.png"),
            "volume_npy": str(output_dir / "scan_converted_volume.npy") if SAVE_VOLUME_NPY else None,
        },
        "note": (
            "The extracted raw spacing is the authoritative acquisition geometry. "
            "The scan-converted output spacing is a chosen reconstruction grid for visualization."
        ),
    }


def main() -> int:
    if not DICOM_PATH:
        raise SystemExit("Set DICOM_PATH at the top of the script before running.")

    dicom_path = Path(DICOM_PATH).expanduser().resolve()
    output_dir = OUTPUT_DIR.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ds = load_dicom(dicom_path)
    payload = ensure_kretz_payload(ds)
    info = parse_kretz_payload_full(payload)
    spacing_mm = choose_output_spacing(info)
    grid = compute_cartesian_grid(info, spacing_mm)

    print(f"Input: {dicom_path}")
    print(f"Raw dims (I/J/K): {info['dims_ijk']}")
    print(f"Raw radial resolution (mm): {info['radial_resolution_mm']}")
    print(f"Raw radial start/end (mm): {info['radial_start_mm']} / {info['radial_end_mm']}")
    print(f"Chosen scan-conversion spacing (mm): {spacing_mm}")
    print(f"Output grid shape (x/y/z): {grid['shape_xyz']}")

    volume = scan_convert_volume(info, grid)
    slice_figure = save_slice_figure(volume, output_dir)
    sector_outline = save_sector_outline(info, output_dir)

    if SAVE_VOLUME_NPY:
        np.save(output_dir / "scan_converted_volume.npy", volume)

    summary = build_summary(dicom_path, info, grid, output_dir)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved slice figure: {slice_figure}")
    print(f"Saved sector outline: {sector_outline}")
    print(f"Saved summary JSON: {output_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
