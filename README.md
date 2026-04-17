# dicom

GE Vivid 3D TEE DICOM 파일에서 spacing 정보를 추출하고, scan conversion 결과를 검증하기 위한 실험용 스크립트 모음입니다.

현재 구성은 특히 `KRETZ_US` private payload를 가진 GE DICOM을 가장 잘 지원합니다.

## 포함 파일

- `ge_vivid_scanconvert_view.py`
  - 가장 간단한 실행용 스크립트
  - 스크립트 상단의 `DICOM_PATH`만 채우고 실행하면 raw geometry를 읽고 scan conversion까지 수행합니다
  - 중심 슬라이스 이미지와 summary JSON을 저장합니다
- `ge_vivid_spacing_extract.py`
  - 분석용 메인 도구
  - DICOM 구조 분석, private creator 탐색, KRETZ payload 파싱, spacing 요약, QC plot 생성, Slicer 결과와의 비교를 지원합니다
- `slicer_kretz_probe.py`
  - 3D Slicer 안에서 실행하는 교차검증 스크립트
  - SlicerHeart의 `KretzFileReader`를 사용해 scan-converted volume의 spacing/origin/dimensions를 JSON으로 저장합니다
- `GE_Vivid_3D_TEE_spacing_plan.md`
  - spacing 추출 및 검증 전략을 정리한 계획 문서
- `GE_Vivid_3D_TEE_DICOM_구조_총정리.md`
  - GE 3D TEE DICOM 구조를 파일 레이어, private tag, KRETZ payload, raw/scan-converted spacing 관점에서 시각적으로 정리한 문서
- `GE_3D_TEE_DICOM_보고서.md`
  - 배경 설명과 구조 분석 보고서
- `GE_3D_TEE_DICOM_발표자료.pptx`
  - 발표 자료

## 지원 범위

### 바로 지원하는 경우

- GE DICOM 안에 `(7FE1,0011)=KRETZ_US`
- 그리고 `(7FE1,1101)` private payload가 있는 경우

이 경우 Python만으로 다음이 가능합니다.

- raw geometry 추출
- radial resolution 추출
- theta / phi angle array 추출
- output spacing을 정해 scan conversion 수행
- 중심 슬라이스 이미지 저장

### 바로 지원하지 않는 경우

- `GEMS_Ultrasound_MovieGroup_001`
- Image3DAPI 계열
- GE vendor DLL 또는 전용 reader가 필요한 경우

이 경우는 `ge_vivid_scanconvert_view.py`가 직접 처리하지 못할 수 있습니다. 대신 `ge_vivid_spacing_extract.py`로 파일 종류를 판별한 뒤, 필요하면 `3D Slicer + SlicerHeart + Image3DAPI` 경로로 가는 것을 권장합니다.

## 준비 사항

### Python

Python 3.10+ 권장. 현재 스크립트는 Windows + Python 3.13 환경에서 기본 동작을 확인했습니다.

### Python 패키지 설치

다음 패키지가 필요합니다.

- `pydicom`
- `numpy`
- `matplotlib`

설치:

```bash
python -m pip install pydicom numpy matplotlib
```

### 선택 사항: 3D Slicer

교차검증까지 하려면 다음이 있으면 좋습니다.

- 3D Slicer
- SlicerHeart extension

이 조합이 있으면 `slicer_kretz_probe.py`로 scan-converted spacing/origin/dimensions를 JSON으로 떨굴 수 있습니다.

## 가장 쉬운 실행 방법

가장 먼저 써볼 파일은 `ge_vivid_scanconvert_view.py` 입니다.

### 1. 스크립트 상단에서 DICOM 경로 입력

파일 상단의 이 부분만 수정합니다.

```python
# Set only this path and run the script.
DICOM_PATH = r"C:\path\to\your_ge_vivid_3d_tee.dcm"
```

원하면 출력 spacing도 고를 수 있습니다.

```python
OUTPUT_SPACING_MM = (0.667, 0.667, 0.667)
```

설정 설명:

- `OUTPUT_SPACING_MM = None`
  - payload 안의 Cartesian spacing candidate가 있으면 먼저 사용
  - 없으면 `FALLBACK_SPACING_MM` 사용
- `FALLBACK_SPACING_MM = (0.667, 0.667, 0.667)`
  - 기본 재구성 grid
- `SAVE_VOLUME_NPY = True`
  - scan-converted volume을 `.npy`로 저장

### 2. 실행

```bash
python ge_vivid_scanconvert_view.py
```

### 3. 생성 결과

기본 출력 폴더:

```text
ge_scanconvert_output/
```

생성 파일:

- `scan_converted_slices.png`
  - axial / coronal / sagittal 중심 슬라이스 + MIP
- `sector_outline.png`
  - 추출된 theta와 radial range로 만든 sector outline
- `summary.json`
  - raw geometry와 scan-converted grid 요약
- `scan_converted_volume.npy`
  - `SAVE_VOLUME_NPY=True`일 때만 저장

### 4. 무엇을 보면 되나

가장 먼저 `scan_converted_slices.png`를 봅니다.

정상적으로 보이면:

- 볼륨이 심하게 찌그러지지 않음
- 부채꼴 기하가 자연스럽게 Cartesian volume으로 들어감
- 중심 슬라이스에 구조물이 그럴듯하게 보임

이상하면:

- 파일이 KRETZ가 아닐 수 있음
- output spacing이 너무 촘촘하거나 너무 거칠 수 있음
- raw geometry 해석이 다른 vendor variant일 수 있음

## 분석용 실행 방법

더 자세한 분석은 `ge_vivid_spacing_extract.py`를 사용합니다.

### 기본 실행

```bash
python ge_vivid_spacing_extract.py "C:\path\to\file.dcm" --output-dir out
```

### payload도 저장

```bash
python ge_vivid_spacing_extract.py "C:\path\to\file.dcm" --output-dir out --export-kretz-payload
```

### scan conversion geometry를 특정 spacing으로 예측

```bash
python ge_vivid_spacing_extract.py "C:\path\to\file.dcm" --output-dir out --predict-spacing 0.667 0.667 0.667
```

### 생성 결과

- `spacing_summary.json`
- `qc_angles.png`
- `qc_sector_outline.png`
- optional `kretz_payload.bin`

### 이 스크립트가 해주는 것

- GE flavor 판별
  - `kretz_us`
  - `moviegroup_3d`
  - `unknown`
- 표준 spacing 후보 추출
- private creator 목록 추출
- KRETZ payload parsing
- validation check 생성
- raw geometry 요약
- SlicerHeart 방식에 맞춘 Cartesian bounds/dimensions 예측

## 3D Slicer 교차검증 방법

이 단계는 선택 사항이지만, spacing이 정말 맞는지 검증할 때 유용합니다.

### 1. 준비

- 3D Slicer 설치
- Extension Manager에서 `SlicerHeart` 설치

### 2. probe 스크립트 실행

```bash
Slicer.exe --no-splash --python-script slicer_kretz_probe.py -- "C:\path\to\file.dcm" "C:\path\to\probe.json" 0.667 0.667 0.667
```

### 3. 생성되는 것

`probe.json` 안에 다음이 들어갑니다.

- scan-converted spacing
- origin
- dimensions

### 4. 메인 분석 결과와 비교

이제 아래처럼 비교할 수 있습니다.

```bash
python ge_vivid_spacing_extract.py "C:\path\to\file.dcm" --output-dir out --predict-spacing 0.667 0.667 0.667 --slicer-probe-json "C:\path\to\probe.json"
```

여기서 중요한 것은 “숫자 하나가 정확히 같으냐”보다 다음입니다.

- predicted dimensions == actual dimensions
- predicted origin이 actual origin과 충분히 가까운가
- chosen output spacing이 Slicer probe spacing과 같은가

## spacing 해석에서 가장 중요한 점

이 저장소에서는 spacing을 두 층으로 구분합니다.

### 1. raw spacing

진짜 원본 acquisition geometry입니다.

- radial resolution
- theta array
- phi array
- offsets

이것이 가장 중요한 값입니다.

### 2. scan-converted spacing

재구성 후 Cartesian volume의 voxel spacing입니다.

이 값은 시각화와 후처리에 매우 유용하지만, 반드시 원본 acquisition spacing과 같지는 않습니다.

즉:

- 연구 목적으로 원본 geometry를 논하려면 raw spacing을 봐야 합니다
- segmentation, visualization, voxel distance 계산을 하려면 scan-converted spacing을 씁니다

## 추천 사용 순서

### 빠른 시각 확인만 필요할 때

1. `ge_vivid_scanconvert_view.py`
2. `scan_converted_slices.png` 확인

### spacing 값을 구조적으로 검토하고 싶을 때

1. `ge_vivid_spacing_extract.py`
2. `spacing_summary.json`
3. `qc_angles.png`
4. `qc_sector_outline.png`

### 신뢰도 높은 검증까지 하고 싶을 때

1. `ge_vivid_spacing_extract.py`
2. `slicer_kretz_probe.py`
3. Slicer 결과와 predicted geometry 비교

## 자주 생기는 문제

### `This script currently supports GE KRETZ_US payloads only`

파일이 `MovieGroup` 또는 다른 private 구조일 가능성이 큽니다. 이 경우 direct parse 대신 Slicer/Image3DAPI 경로를 고려해야 합니다.

### reconstruction grid가 너무 큼

`MAX_TOTAL_VOXELS` 제한에 걸린 경우입니다.

해결:

- `OUTPUT_SPACING_MM`를 더 크게 잡기
- 예: `(1.0, 1.0, 1.0)` 또는 `(1.2, 1.2, 1.2)`

### 슬라이스가 비어 보임

가능성:

- output spacing이 너무 거침
- 파일 variant가 예상과 다름
- raw geometry가 KRETZ라도 다른 vendor variation일 수 있음

## 이 저장소에서 확인한 구현 근거

스크립트 설계는 아래 공개 구현 흐름을 참고해 만들었습니다.

- SlicerHeart `DicomUltrasoundPlugin`
- SlicerHeart `KretzFileReader`
- SlicerHeart `GeUsMovieReader`

핵심적으로 참고한 내용:

- `KRETZ_US` payload 식별 방식
- KRETZ item 구조
- `C000/C100/C200/C300/D000` 항목 해석
- scan conversion 시 geometry 계산 방식

## 참고 문서

- [GE_Vivid_3D_TEE_spacing_plan.md](GE_Vivid_3D_TEE_spacing_plan.md)
- [GE_3D_TEE_DICOM_보고서.md](GE_3D_TEE_DICOM_보고서.md)

## 한 줄 요약

가장 먼저는 `ge_vivid_scanconvert_view.py` 상단에 DICOM 경로를 넣고 실행해 보시면 됩니다.  
그 다음 `scan_converted_slices.png`가 정상적으로 보이는지 확인하고, 더 깊게 보려면 `ge_vivid_spacing_extract.py`와 `slicer_kretz_probe.py`로 검증을 확장하면 됩니다.
