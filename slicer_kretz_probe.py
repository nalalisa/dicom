from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_args(argv: list[str]) -> tuple[Path, Path, list[float]]:
    if len(argv) < 3:
        raise SystemExit(
            "Usage inside Slicer:\n"
            "  Slicer.exe --no-splash --python-script slicer_kretz_probe.py -- "
            "<dicom_file> <output_json> [sx sy sz]\n"
        )
    dicom_path = Path(argv[1]).resolve()
    output_json = Path(argv[2]).resolve()
    if len(argv) >= 6:
        spacing = [float(argv[3]), float(argv[4]), float(argv[5])]
    else:
        spacing = [0.667, 0.667, 0.667]
    return dicom_path, output_json, spacing


def main(argv: list[str]) -> int:
    dicom_path, output_json, requested_spacing = parse_args(argv)

    import pydicom as dicom
    import slicer

    if not hasattr(slicer.modules, "kretzfilereader"):
        raise RuntimeError("SlicerHeart KretzFileReader module is not available in this Slicer installation.")

    ds = dicom.dcmread(str(dicom_path), defer_size=30)
    kretz_data_tag = dicom.tag.Tag("0x7fe1", "0x1101")
    if kretz_data_tag not in ds:
        raise RuntimeError("KRETZ payload tag (7FE1,1101) not found.")

    data_item = ds.get(kretz_data_tag)
    if not hasattr(data_item, "file_tell"):
        raise RuntimeError("pydicom data element does not expose file_tell; cannot locate embedded payload.")

    payload_offset = int(data_item.file_tell)
    logic = slicer.modules.kretzfilereader.logic()
    node_name = slicer.mrmlScene.GenerateUniqueName("KretzProbe")
    volume_node = logic.LoadKretzFile(
        str(dicom_path),
        node_name,
        True,
        requested_spacing,
        payload_offset,
    )
    if not volume_node:
        raise RuntimeError("LoadKretzFile returned no volume node.")

    image_data = volume_node.GetImageData()
    result = {
        "input_file": str(dicom_path),
        "payload_offset": payload_offset,
        "requested_output_spacing_mm": requested_spacing,
        "scan_converted": {
            "spacing_mm": list(volume_node.GetSpacing()),
            "origin_mm": list(volume_node.GetOrigin()),
            "dimensions": list(image_data.GetDimensions()) if image_data else None,
            "node_name": volume_node.GetName(),
        },
        "note": (
            "This spacing is the scan-converted Cartesian output spacing. "
            "It is a resampling grid chosen for reconstruction, not the raw acquisition spacing."
        ),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {output_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
