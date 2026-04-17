from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pydicom
from pydicom.tag import BaseTag, Tag

KRETZ_MAGIC = b"KRETZFILE 1.0   "
KRETZ_CREATOR_TAG = Tag(0x7FE1, 0x0011)
KRETZ_PAYLOAD_TAG = Tag(0x7FE1, 0x1101)
MOVIEGROUP_CREATOR = "GEMS_Ultrasound_MovieGroup_001"
KRETZ_CREATOR = "KRETZ_US"

STANDARD_SPACING_TAGS: dict[BaseTag, str] = {
    Tag(0x0028, 0x0030): "PixelSpacing",
    Tag(0x0018, 0x1164): "ImagerPixelSpacing",
    Tag(0x0018, 0x2010): "NominalScannedPixelSpacing",
    Tag(0x0028, 0x0034): "PixelAspectRatio",
    Tag(0x0018, 0x0088): "SpacingBetweenSlices",
    Tag(0x0018, 0x0050): "SliceThickness",
}

ULTRASOUND_REGION_SUBTAGS: dict[BaseTag, str] = {
    Tag(0x0018, 0x6012): "RegionSpatialFormat",
    Tag(0x0018, 0x6014): "RegionDataType",
    Tag(0x0018, 0x6016): "RegionFlags",
    Tag(0x0018, 0x6018): "RegionLocationMinX0",
    Tag(0x0018, 0x601A): "RegionLocationMinY0",
    Tag(0x0018, 0x601C): "RegionLocationMaxX1",
    Tag(0x0018, 0x601E): "RegionLocationMaxY1",
    Tag(0x0018, 0x6024): "PhysicalUnitsXDirection",
    Tag(0x0018, 0x6026): "PhysicalUnitsYDirection",
    Tag(0x0018, 0x602C): "PhysicalDeltaX",
    Tag(0x0018, 0x602E): "PhysicalDeltaY",
}


@dataclass
class ValidationCheck:
    name: str
    ok: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a GE Vivid 3D TEE DICOM, extract spacing-related metadata, "
            "parse KRETZ payload when available, and emit QC artifacts."
        )
    )
    parser.add_argument("dicom_path", help="Path to the GE DICOM file")
    parser.add_argument(
        "--output-dir",
        default="ge_spacing_output",
        help="Directory for JSON summary and QC plots",
    )
    parser.add_argument(
        "--export-kretz-payload",
        action="store_true",
        help="Export the raw KRETZ payload to output_dir/kretz_payload.bin",
    )
    parser.add_argument(
        "--predict-spacing",
        nargs=3,
        type=float,
        metavar=("SX", "SY", "SZ"),
        default=(0.667, 0.667, 0.667),
        help=(
            "Cartesian resampling spacing used for scan-conversion prediction. "
            "Matches SlicerHeart default if left unchanged."
        ),
    )
    parser.add_argument(
        "--slicer-probe-json",
        help=(
            "Optional JSON produced by slicer_kretz_probe.py for comparison with "
            "predicted scan-conversion geometry."
        ),
    )
    return parser.parse_args()


def tag_to_str(tag: BaseTag) -> str:
    return f"({tag.group:04X},{tag.element:04X})"


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return {"bytes_len": len(value), "preview_hex": value[:32].hex()}
    if isinstance(value, BaseTag):
        return tag_to_str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    return str(value)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_dicom(path: Path) -> pydicom.Dataset:
    return pydicom.dcmread(str(path), defer_size="1 MB")


def collect_private_creators(ds: pydicom.Dataset) -> list[dict[str, Any]]:
    creators: list[dict[str, Any]] = []
    for tag in ds.keys():
        if tag.element >= 0x0100:
            continue
        elem = ds[tag]
        value = elem.value
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace").rstrip("\x00 ").strip()
        if isinstance(value, str) and value:
            creators.append(
                {
                    "tag": tag_to_str(tag),
                    "group": f"{tag.group:04X}",
                    "element": f"{tag.element:04X}",
                    "creator": value,
                }
            )
    return creators


def find_private_tag(
    ds: pydicom.Dataset, group: int, element: int, private_creator: str
) -> BaseTag | None:
    for tag, data_element in ds.items():
        if tag.group != group or tag.element >= 0x0100:
            continue
        value = data_element.value
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str) and value.rstrip("\x00 ").strip() == private_creator:
            return Tag(group, (tag.element << 8) + element)
    return None


def extract_standard_spacing_candidates(ds: pydicom.Dataset) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for tag, name in STANDARD_SPACING_TAGS.items():
        if tag in ds:
            result[name] = to_jsonable(ds[tag].value)

    region_seq_tag = Tag(0x0018, 0x6011)
    regions: list[dict[str, Any]] = []
    if region_seq_tag in ds:
        for index, item in enumerate(ds[region_seq_tag].value):
            item_result: dict[str, Any] = {"index": index}
            for subtag, name in ULTRASOUND_REGION_SUBTAGS.items():
                if subtag in item:
                    item_result[name] = to_jsonable(item[subtag].value)
            regions.append(item_result)
    result["SequenceOfUltrasoundRegions"] = regions
    return result


def identify_ge_flavor(ds: pydicom.Dataset) -> dict[str, Any]:
    manufacturer = str(getattr(ds, "Manufacturer", "") or "")
    model = str(getattr(ds, "ManufacturerModelName", "") or "")
    result: dict[str, Any] = {
        "manufacturer": manufacturer,
        "model": model,
        "flavor": "unknown",
        "detail": "",
    }

    creator_7fe1_0011 = str(ds.get(KRETZ_CREATOR_TAG).value) if KRETZ_CREATOR_TAG in ds else ""
    creator_7fe1_0010 = str(ds.get(Tag(0x7FE1, 0x0010)).value) if Tag(0x7FE1, 0x0010) in ds else ""

    if creator_7fe1_0011 == KRETZ_CREATOR and KRETZ_PAYLOAD_TAG in ds:
        result["flavor"] = "kretz_us"
        result["detail"] = "Detected (7FE1,0011)=KRETZ_US and payload at (7FE1,1101)."
        return result

    if creator_7fe1_0010 == MOVIEGROUP_CREATOR:
        root_tag = find_private_tag(ds, 0x7FE1, 0x01, MOVIEGROUP_CREATOR)
        type_tag = find_private_tag(ds, 0x7FE1, 0x02, MOVIEGROUP_CREATOR)
        contains_3d = False
        if root_tag and root_tag in ds:
            try:
                movie_group = ds[root_tag].value
                for item in movie_group:
                    if type_tag and type_tag in item:
                        value = str(item[type_tag].value)
                        if "3D" in value:
                            contains_3d = True
                            break
            except Exception:
                contains_3d = False
        result["flavor"] = "moviegroup_3d" if contains_3d else "moviegroup"
        result["detail"] = (
            "Detected GEMS_Ultrasound_MovieGroup_001 private creator. 3D marker present in private sequence."
            if contains_3d
            else "Detected GEMS_Ultrasound_MovieGroup_001 private creator."
        )
        return result

    if "GE Healthcare" in manufacturer or "Kretztechnik" in manufacturer:
        result["detail"] = "GE manufacturer detected, but no supported KRETZ/MovieGroup payload matched."
    return result


def unpack_first_scalar(buffer: memoryview, prefer_double: bool = True) -> float | None:
    if len(buffer) >= 8 and prefer_double:
        return struct.unpack_from("<d", buffer, 0)[0]
    if len(buffer) >= 4:
        return float(struct.unpack_from("<f", buffer, 0)[0])
    return None


def unpack_first_uint16(buffer: memoryview) -> int | None:
    if len(buffer) >= 2:
        return struct.unpack_from("<H", buffer, 0)[0]
    return None


def buffer_to_float_array(buffer: memoryview) -> np.ndarray:
    if len(buffer) == 0:
        return np.array([], dtype=np.float64)
    if len(buffer) % 8 == 0:
        return np.frombuffer(buffer, dtype="<f8").copy()
    if len(buffer) % 4 == 0:
        return np.frombuffer(buffer, dtype="<f4").astype(np.float64)
    raise ValueError(f"Cannot interpret buffer of length {len(buffer)} as float array")


def summarize_raw_spacing(
    radial_resolution_mm: float | None,
    radial_start_mm: float | None,
    radial_end_mm: float | None,
    theta_angles_rad: np.ndarray,
    phi_angles_rad: np.ndarray,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "exact_raw_spacing_definition": (
            "Raw GE/KRETZ spacing is not a single mm/mm/mm tuple. "
            "The exact raw geometry is radial_resolution_mm plus theta/phi angle arrays. "
            "Lateral and elevation physical step size in mm depends on depth."
        )
    }
    if radial_resolution_mm is None:
        return summary

    summary["radial_resolution_mm"] = radial_resolution_mm
    summary["radial_start_mm"] = radial_start_mm
    summary["radial_end_mm"] = radial_end_mm

    for axis_name, angles in (("theta", theta_angles_rad), ("phi", phi_angles_rad)):
        if angles.size >= 2:
            step_rad = np.diff(angles)
            summary[f"{axis_name}_step_deg_stats"] = {
                "min": float(np.rad2deg(step_rad.min())),
                "mean": float(np.rad2deg(step_rad.mean())),
                "max": float(np.rad2deg(step_rad.max())),
            }
            summary[f"{axis_name}_range_deg"] = {
                "start": float(np.rad2deg(angles[0])),
                "end": float(np.rad2deg(angles[-1])),
                "range": float(np.rad2deg(angles[-1] - angles[0])),
            }

    if radial_start_mm is not None and radial_end_mm is not None:
        sample_depths = {
            "start_mm": radial_start_mm,
            "mid_mm": (radial_start_mm + radial_end_mm) / 2.0,
            "end_mm": radial_end_mm,
        }
        for axis_name, angles in (("theta", theta_angles_rad), ("phi", phi_angles_rad)):
            if angles.size >= 2:
                step_rad = np.diff(angles)
                arc_stats: dict[str, Any] = {}
                for label, depth_mm in sample_depths.items():
                    arc_lengths = depth_mm * step_rad
                    arc_stats[label] = {
                        "min": float(arc_lengths.min()),
                        "mean": float(arc_lengths.mean()),
                        "max": float(arc_lengths.max()),
                    }
                summary[f"{axis_name}_arc_length_mm_at_sample_depths"] = arc_stats

    return summary


def parse_kretz_payload(payload: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "magic_ok": payload.startswith(KRETZ_MAGIC),
        "payload_size_bytes": len(payload),
        "items_seen": 0,
        "recognized_items": {},
        "warnings": [],
    }
    if not payload.startswith(KRETZ_MAGIC):
        result["warnings"].append("Payload does not start with KRETZFILE 1.0 header.")
        return result

    pos = len(KRETZ_MAGIC)
    dims = [None, None, None]
    theta_angles = np.array([], dtype=np.float64)
    phi_angles = np.array([], dtype=np.float64)
    radial_resolution_mm = None
    offset1 = None
    offset2 = None
    cartesian_spacing_mm = None
    voxel_data_bytes = None
    unknown_items: list[dict[str, Any]] = []

    while pos + 8 <= len(payload):
        group, element, item_size = struct.unpack_from("<HHI", payload, pos)
        pos += 8
        end = pos + item_size
        if end > len(payload):
            result["warnings"].append(
                f"Item ({group:04X},{element:04X}) overruns payload: pos={pos}, size={item_size}."
            )
            break

        buffer = memoryview(payload)[pos:end]
        pos = end
        result["items_seen"] += 1
        item_key = f"({group:04X},{element:04X})"

        if (group, element) == (0xC000, 0x0001):
            dims[0] = unpack_first_uint16(buffer)
        elif (group, element) == (0xC000, 0x0002):
            dims[1] = unpack_first_uint16(buffer)
        elif (group, element) == (0xC000, 0x0003):
            dims[2] = unpack_first_uint16(buffer)
        elif (group, element) == (0xC100, 0x0001):
            value = unpack_first_scalar(buffer, prefer_double=True)
            if value is not None:
                radial_resolution_mm = value * 1000.0
        elif (group, element) == (0xC200, 0x0001):
            offset1 = unpack_first_scalar(buffer, prefer_double=True)
        elif (group, element) == (0xC200, 0x0002):
            offset2 = unpack_first_scalar(buffer, prefer_double=True)
        elif (group, element) == (0xC300, 0x0001):
            phi_angles = buffer_to_float_array(buffer)
        elif (group, element) == (0xC300, 0x0002):
            theta_angles = buffer_to_float_array(buffer)
        elif (group, element) == (0x0010, 0x0022):
            cartesian_spacing_mm = unpack_first_scalar(buffer, prefer_double=True)
        elif (group, element) == (0xD000, 0x0001):
            voxel_data_bytes = item_size
        else:
            if len(unknown_items) < 32:
                unknown_items.append({"item": item_key, "size_bytes": item_size})

    dim_i, dim_j, dim_k = dims
    theta_deg = np.rad2deg(theta_angles) if theta_angles.size else np.array([], dtype=np.float64)
    phi_deg = np.rad2deg(phi_angles) if phi_angles.size else np.array([], dtype=np.float64)
    theta_step_deg = np.diff(theta_deg) if theta_deg.size >= 2 else np.array([], dtype=np.float64)
    phi_step_deg = np.diff(phi_deg) if phi_deg.size >= 2 else np.array([], dtype=np.float64)

    radial_start_mm = None
    bmode_radius_mm = None
    radial_end_mm = None
    if radial_resolution_mm is not None and offset1 is not None:
        radial_start_mm = offset1 * radial_resolution_mm
    if radial_resolution_mm is not None and dim_i is not None and radial_start_mm is not None:
        radial_end_mm = radial_start_mm + max(dim_i - 1, 0) * radial_resolution_mm
    if radial_resolution_mm is not None and offset2 is not None:
        bmode_radius_mm = -offset2 * radial_resolution_mm

    voxel_count_expected = None
    voxel_bytes_per_sample = None
    if all(v is not None for v in dims):
        voxel_count_expected = int(dim_i * dim_j * dim_k)
        if voxel_data_bytes:
            voxel_bytes_per_sample = voxel_data_bytes / voxel_count_expected

    result["recognized_items"] = {
        "dimensions_ijk": dims,
        "radial_resolution_mm": radial_resolution_mm,
        "offset1_index_units": offset1,
        "offset2_index_units": offset2,
        "radial_start_mm": radial_start_mm,
        "radial_end_mm": radial_end_mm,
        "bmode_radius_mm": bmode_radius_mm,
        "theta_angles_rad": theta_angles.tolist(),
        "phi_angles_rad": phi_angles.tolist(),
        "theta_angles_deg": theta_deg.tolist(),
        "phi_angles_deg": phi_deg.tolist(),
        "theta_step_deg": theta_step_deg.tolist(),
        "phi_step_deg": phi_step_deg.tolist(),
        "cartesian_spacing_mm_candidate": cartesian_spacing_mm,
        "voxel_data_bytes": voxel_data_bytes,
        "voxel_count_expected": voxel_count_expected,
        "voxel_bytes_per_sample": voxel_bytes_per_sample,
        "unknown_items_preview": unknown_items,
    }
    result["derived_spacing"] = summarize_raw_spacing(
        radial_resolution_mm,
        radial_start_mm,
        radial_end_mm,
        theta_angles,
        phi_angles,
    )
    return result


def validate_kretz(parse_result: dict[str, Any]) -> list[ValidationCheck]:
    recognized = parse_result.get("recognized_items", {})
    dims = recognized.get("dimensions_ijk", [None, None, None])
    theta = np.asarray(recognized.get("theta_angles_rad", []), dtype=np.float64)
    phi = np.asarray(recognized.get("phi_angles_rad", []), dtype=np.float64)
    resolution = recognized.get("radial_resolution_mm")
    voxel_bytes_per_sample = recognized.get("voxel_bytes_per_sample")

    checks = [
        ValidationCheck("magic_header", bool(parse_result.get("magic_ok")), "Payload starts with KRETZFILE 1.0 header."),
        ValidationCheck("dimensions_present", all(v is not None and v > 0 for v in dims), f"dimensions={dims}"),
        ValidationCheck("radial_resolution_present", resolution is not None and resolution > 0, f"radial_resolution_mm={resolution}"),
        ValidationCheck("theta_count_matches_dim_j", dims[1] is not None and len(theta) == dims[1], f"theta_count={len(theta)}, dim_j={dims[1]}"),
        ValidationCheck("phi_count_matches_dim_k", dims[2] is not None and len(phi) == dims[2], f"phi_count={len(phi)}, dim_k={dims[2]}"),
        ValidationCheck("theta_monotonic", len(theta) < 2 or np.all(np.diff(theta) >= 0), "Theta angles should be non-decreasing."),
        ValidationCheck("phi_monotonic", len(phi) < 2 or np.all(np.diff(phi) >= 0), "Phi angles should be non-decreasing."),
        ValidationCheck(
            "voxel_bytes_per_sample_reasonable",
            voxel_bytes_per_sample is None or abs(voxel_bytes_per_sample - round(voxel_bytes_per_sample)) < 1e-6,
            f"bytes_per_sample={voxel_bytes_per_sample}",
        ),
    ]
    return checks


def infer_validation_level(checks: list[ValidationCheck]) -> str:
    if not checks:
        return "unknown"
    passed = sum(1 for check in checks if check.ok)
    if passed == len(checks):
        return "high"
    if passed >= max(3, len(checks) - 2):
        return "medium"
    return "low"


def predict_cartesian_geometry(
    parse_result: dict[str, Any], output_spacing_mm: tuple[float, float, float]
) -> dict[str, Any]:
    recognized = parse_result.get("recognized_items", {})
    dims = recognized.get("dimensions_ijk", [None, None, None])
    theta = np.asarray(recognized.get("theta_angles_rad", []), dtype=np.float64)
    phi = np.asarray(recognized.get("phi_angles_rad", []), dtype=np.float64)
    radial_resolution_mm = recognized.get("radial_resolution_mm")
    radial_start_mm = recognized.get("radial_start_mm")
    bmode_radius_mm = recognized.get("bmode_radius_mm")

    if not all(v is not None and v > 0 for v in dims):
        return {"available": False, "reason": "Missing dimensions"}
    if radial_resolution_mm is None or radial_start_mm is None or bmode_radius_mm is None:
        return {"available": False, "reason": "Missing resolution or offsets"}
    if theta.size != dims[1] or phi.size != dims[2]:
        return {"available": False, "reason": "Angle array lengths do not match dimensions"}

    dim_i = int(dims[0])
    radial_end_mm = radial_start_mm + max(dim_i - 1, 0) * radial_resolution_mm
    theta_shifted = theta - (math.pi / 2.0)
    phi_shifted = phi - (math.pi / 2.0)

    bounds = {
        "x_min": math.inf,
        "x_max": -math.inf,
        "y_min": math.inf,
        "y_max": -math.inf,
        "z_min": math.inf,
        "z_max": -math.inf,
    }

    theta_sin = np.sin(theta_shifted)[None, :]
    theta_cos = np.cos(theta_shifted)[None, :]
    phi_sin = np.sin(phi_shifted)[:, None]
    phi_cos = np.cos(phi_shifted)[:, None]

    for radius_mm in (radial_start_mm, radial_end_mm):
        x = radius_mm * theta_sin
        y = -(radius_mm * theta_cos - bmode_radius_mm) * phi_sin
        z = bmode_radius_mm * (1.0 - phi_cos) + radius_mm * theta_cos * phi_cos
        bounds["x_min"] = min(bounds["x_min"], float(x.min()))
        bounds["x_max"] = max(bounds["x_max"], float(x.max()))
        bounds["y_min"] = min(bounds["y_min"], float(y.min()))
        bounds["y_max"] = max(bounds["y_max"], float(y.max()))
        bounds["z_min"] = min(bounds["z_min"], float(z.min()))
        bounds["z_max"] = max(bounds["z_max"], float(z.max()))

    sx, sy, sz = output_spacing_mm
    predicted_dims = [
        int(math.ceil((bounds["x_max"] - bounds["x_min"]) / sx)),
        int(math.ceil((bounds["y_max"] - bounds["y_min"]) / sy)),
        int(math.ceil((bounds["z_max"] - bounds["z_min"]) / sz)),
    ]
    return {
        "available": True,
        "output_spacing_mm": list(output_spacing_mm),
        "origin_mm_candidate": [bounds["x_min"], bounds["y_min"], bounds["z_min"]],
        "bounds_mm": bounds,
        "predicted_dimensions": predicted_dims,
        "note": (
            "This reproduces the geometry/bounds logic used by SlicerHeart scan conversion. "
            "The predicted dimensions depend on the chosen output_spacing_mm."
        ),
    }


def compare_with_slicer_probe(predicted: dict[str, Any], slicer_probe_json_path: Path) -> dict[str, Any]:
    if not predicted.get("available"):
        return {"available": False, "reason": "Predicted geometry unavailable"}

    probe = json.loads(slicer_probe_json_path.read_text(encoding="utf-8"))
    scan = probe.get("scan_converted")
    if not scan:
        return {"available": False, "reason": "scan_converted block missing from Slicer probe JSON"}

    predicted_dims = predicted["predicted_dimensions"]
    actual_dims = scan.get("dimensions")
    predicted_origin = np.asarray(predicted["origin_mm_candidate"], dtype=np.float64)
    actual_origin = np.asarray(scan.get("origin_mm", []), dtype=np.float64)
    predicted_spacing = np.asarray(predicted["output_spacing_mm"], dtype=np.float64)
    actual_spacing = np.asarray(scan.get("spacing_mm", []), dtype=np.float64)

    comparison = {
        "available": True,
        "dimensions_match": predicted_dims == actual_dims,
        "predicted_dimensions": predicted_dims,
        "actual_dimensions": actual_dims,
        "spacing_match": bool(actual_spacing.size == 3 and np.allclose(predicted_spacing, actual_spacing, atol=1e-6)),
        "predicted_spacing_mm": predicted["output_spacing_mm"],
        "actual_spacing_mm": scan.get("spacing_mm"),
    }
    if actual_origin.size == 3:
        comparison["origin_close_mm"] = bool(np.allclose(predicted_origin, actual_origin, atol=1.0))
        comparison["predicted_origin_mm"] = predicted["origin_mm_candidate"]
        comparison["actual_origin_mm"] = scan.get("origin_mm")
        comparison["origin_abs_error_mm"] = np.abs(predicted_origin - actual_origin).tolist()
    else:
        comparison["origin_close_mm"] = False
    return comparison


def create_qc_plots(parse_result: dict[str, Any], output_dir: Path) -> list[str]:
    files: list[str] = []
    recognized = parse_result.get("recognized_items", {})
    theta_deg = np.asarray(recognized.get("theta_angles_deg", []), dtype=np.float64)
    phi_deg = np.asarray(recognized.get("phi_angles_deg", []), dtype=np.float64)
    theta_step_deg = np.asarray(recognized.get("theta_step_deg", []), dtype=np.float64)
    phi_step_deg = np.asarray(recognized.get("phi_step_deg", []), dtype=np.float64)
    radial_start_mm = recognized.get("radial_start_mm")
    radial_end_mm = recognized.get("radial_end_mm")

    if theta_deg.size or phi_deg.size:
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        ax = axes[0, 0]
        if theta_deg.size:
            ax.plot(theta_deg, marker="o", linewidth=1)
        ax.set_title("Theta Angles (deg)")
        ax.set_xlabel("Index j")
        ax.set_ylabel("deg")
        ax.grid(True, alpha=0.3)

        ax = axes[0, 1]
        if phi_deg.size:
            ax.plot(phi_deg, marker="o", linewidth=1, color="tab:orange")
        ax.set_title("Phi Angles (deg)")
        ax.set_xlabel("Index k")
        ax.set_ylabel("deg")
        ax.grid(True, alpha=0.3)

        ax = axes[1, 0]
        if theta_step_deg.size:
            ax.plot(theta_step_deg, marker="o", linewidth=1, label="theta step")
        if phi_step_deg.size:
            ax.plot(phi_step_deg, marker="o", linewidth=1, label="phi step")
        ax.set_title("Angle Step Uniformity (deg)")
        ax.set_xlabel("Step index")
        ax.set_ylabel("deg")
        ax.grid(True, alpha=0.3)
        ax.legend()

        ax = axes[1, 1]
        if radial_start_mm is not None and radial_end_mm is not None and theta_step_deg.size:
            sample_depths = [radial_start_mm, (radial_start_mm + radial_end_mm) / 2.0, radial_end_mm]
            labels = ["start", "mid", "end"]
            for depth_mm, label in zip(sample_depths, labels):
                arc_mm = depth_mm * np.deg2rad(theta_step_deg)
                ax.plot(arc_mm, marker="o", linewidth=1, label=f"theta arc @ {label} ({depth_mm:.1f} mm)")
        ax.set_title("Lateral Arc Length per Theta Step")
        ax.set_xlabel("Step index")
        ax.set_ylabel("mm")
        ax.grid(True, alpha=0.3)
        if ax.has_data():
            ax.legend(fontsize=8)

        fig.tight_layout()
        out_path = output_dir / "qc_angles.png"
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
        files.append(str(out_path))

    if theta_deg.size and radial_start_mm is not None and radial_end_mm is not None:
        theta_rad = np.deg2rad(theta_deg - 90.0)
        fig, ax = plt.subplots(figsize=(6, 6))
        for radius_mm, style in ((radial_start_mm, "--"), (radial_end_mm, "-")):
            x = radius_mm * np.sin(theta_rad)
            z = radius_mm * np.cos(theta_rad)
            ax.plot(x, z, style, linewidth=2, label=f"r={radius_mm:.1f} mm")

        for theta_edge in (theta_rad[0], theta_rad[-1]):
            x = np.array([radial_start_mm * np.sin(theta_edge), radial_end_mm * np.sin(theta_edge)])
            z = np.array([radial_start_mm * np.cos(theta_edge), radial_end_mm * np.cos(theta_edge)])
            ax.plot(x, z, "k-", linewidth=1)

        ax.set_title("2D Sector Outline from Extracted Geometry")
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("z (mm)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        out_path = output_dir / "qc_sector_outline.png"
        fig.savefig(out_path, dpi=160)
        plt.close(fig)
        files.append(str(out_path))

    return files


def build_summary(path: Path, ds: pydicom.Dataset, args: argparse.Namespace) -> dict[str, Any]:
    ge_flavor = identify_ge_flavor(ds)
    summary: dict[str, Any] = {
        "input_file": str(path),
        "dicom": {
            "SOPClassUID": str(getattr(ds, "SOPClassUID", "") or ""),
            "Manufacturer": str(getattr(ds, "Manufacturer", "") or ""),
            "ManufacturerModelName": str(getattr(ds, "ManufacturerModelName", "") or ""),
            "Modality": str(getattr(ds, "Modality", "") or ""),
            "SeriesDescription": str(getattr(ds, "SeriesDescription", "") or ""),
            "Rows": int(getattr(ds, "Rows", 0) or 0),
            "Columns": int(getattr(ds, "Columns", 0) or 0),
            "NumberOfFrames": int(getattr(ds, "NumberOfFrames", 0) or 0),
        },
        "private_creators": collect_private_creators(ds),
        "standard_spacing_candidates": extract_standard_spacing_candidates(ds),
        "ge_detection": ge_flavor,
        "practical_conclusion": {},
    }

    if ge_flavor["flavor"] == "kretz_us":
        payload = bytes(ds[KRETZ_PAYLOAD_TAG].value)
        if args.export_kretz_payload:
            payload_path = Path(args.output_dir) / "kretz_payload.bin"
            payload_path.write_bytes(payload)
            summary["kretz_payload_export"] = str(payload_path)
        kretz = parse_kretz_payload(payload)
        checks = validate_kretz(kretz)
        kretz["validation"] = [asdict(check) for check in checks]
        kretz["validation_level"] = infer_validation_level(checks)
        predicted = predict_cartesian_geometry(kretz, tuple(args.predict_spacing))
        kretz["predicted_scan_conversion"] = predicted
        if args.slicer_probe_json:
            kretz["slicer_probe_comparison"] = compare_with_slicer_probe(predicted, Path(args.slicer_probe_json))
        summary["kretz_analysis"] = kretz
        summary["practical_conclusion"] = {
            "status": "raw_spacing_extracted",
            "message": (
                "Raw GE/KRETZ spacing was extracted directly from the private payload. "
                "Use radial_resolution_mm + theta/phi angle arrays as the authoritative raw geometry."
            ),
            "important_note": (
                "A final Cartesian voxel spacing does not exist until you choose a scan-conversion output grid. "
                "SlicerHeart defaults to a user-selected resampling spacing, which is not the same thing as raw acquisition spacing."
            ),
        }
    elif ge_flavor["flavor"] == "moviegroup_3d":
        summary["practical_conclusion"] = {
            "status": "needs_external_reader",
            "message": (
                "This file looks like a GE MovieGroup/Image3DAPI-style 3D file rather than a direct KRETZ payload. "
                "Use 3D Slicer + SlicerHeart + Image3dAPI or GE-provided DLL/SDK for full spacing extraction."
            ),
            "important_note": (
                "The open SlicerHeart GeUsMovieReader handles 2D/2D+t sequences and does not recover 3D spacing "
                "from MovieGroup by itself."
            ),
        }
    else:
        summary["practical_conclusion"] = {
            "status": "not_confirmed",
            "message": "No supported KRETZ payload was identified. Review private creators and consider a Slicer/Image3DAPI path.",
        }

    return summary


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"Input: {summary['input_file']}")
    print(f"GE flavor: {summary['ge_detection']['flavor']}")
    print(summary["ge_detection"]["detail"])
    conclusion = summary.get("practical_conclusion", {})
    if conclusion:
        print(f"Conclusion: {conclusion.get('status')}")
        print(conclusion.get("message", ""))

    kretz = summary.get("kretz_analysis")
    if kretz:
        recognized = kretz.get("recognized_items", {})
        print(f"Dimensions (I/J/K): {recognized.get('dimensions_ijk')}")
        print(f"Radial resolution (mm): {recognized.get('radial_resolution_mm')}")
        print(f"Radial start/end (mm): {recognized.get('radial_start_mm')} / {recognized.get('radial_end_mm')}")
        print(
            "Theta count / Phi count: "
            f"{len(recognized.get('theta_angles_deg', []))} / {len(recognized.get('phi_angles_deg', []))}"
        )
        print(f"Validation level: {kretz.get('validation_level')}")
        if kretz.get("predicted_scan_conversion", {}).get("available"):
            pred = kretz["predicted_scan_conversion"]
            print(
                "Predicted scan-converted dims for spacing "
                f"{pred['output_spacing_mm']}: {pred['predicted_dimensions']}"
            )


def main() -> int:
    args = parse_args()
    dicom_path = Path(args.dicom_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_dir(output_dir)

    ds = read_dicom(dicom_path)
    summary = build_summary(dicom_path, ds, args)

    if "kretz_analysis" in summary:
        plot_files = create_qc_plots(summary["kretz_analysis"], output_dir)
        summary["kretz_analysis"]["qc_plots"] = plot_files

    json_path = output_dir / "spacing_summary.json"
    json_path.write_text(json.dumps(to_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    print_human_summary(summary)
    print(f"Saved summary JSON: {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
