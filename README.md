9# dicom

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

지금까지 논의된 3D 초음파 스캔 변환(Scan Conversion)의 모든 핵심을 하나로 엮어, **'트랜스듀서 원점을 윗면 중앙에 배치하는 등방성(Isotropic) 변환'**을 기준으로 마스터 정리본을 작성해 드리겠습니다.
메모리 상의 '직육면체 Raw 데이터'를 모니터 상의 '부채꼴 3D 공간'으로 펴내는 전체 수학적 유도 과정과 로직입니다.
### 1. 물리적 공간 정의 및 Bounding Box 유도
컴퓨터 메모리 상의 3D 배열(Raw Data)을 실제 물리적 공간으로 매핑하기 위해, 초음파가 도달하는 최대 물리적 크기(Bounding Box)를 계산합니다.
 * **초기 조건:**
   * 깊이 범위: r_{start} ~ r_{end}
   * 전체 방위각 폭: \theta_{span} \rightarrow 중심축 기준 최대 방위각 \theta_{max} = \frac{\theta_{span}}{2}
   * 전체 고도각 폭: \phi_{span} \rightarrow 중심축 기준 최대 고도각 \phi_{max} = \frac{\phi_{span}}{2}
   * 목표 출력 배열 크기: N \times N \times N (예: 256)
 * **축별 물리적 길이 도출:**
   트랜스듀서 원점을 Z축의 시작점(0)으로 둔 상태에서, 빔이 뻗어나가는 최대 너비와 깊이를 삼각함수로 유도합니다.
   
### 2. 등방성(Isotropic) Spacing 계산
영상의 왜곡(찌그러짐)을 방지하기 위해 가로, 세로, 깊이 방향의 복셀 크기를 모두 동일하게 통일합니다.
 * **최대 축 탐색 및 Spacing 결정:**
   세 축의 물리적 길이 중 가장 긴 축을 기준으로 Spacing(d)을 구하여, 모든 방향의 복셀 간격에 동일하게 적용합니다.
   
### 3. 좌표계 매핑 및 역방향 스캔 변환 (Backward Mapping)
결과물이 담길 N \times N \times N 배열의 인덱스 공간을 실제 물리적 직교 좌표계로 변환한 뒤, 이를 다시 구면 좌표계로 역산합니다.
 * **인덱스 \rightarrow 직교 좌표계 매핑 (Top-Center Origin):**
   배열 인덱스 i, j, k \in [0, N-1] 에 대하여, 트랜스듀서 원점을 윗면(Z=0) 정중앙에 배치하도록 좌표를 평행 이동합니다.
   
 * **직교 좌표계 \rightarrow 구면 좌표계 역산:**
   물리적 공간의 복셀 (x, y, z) 위치에 색을 칠하기 위해, 해당 위치의 원래 초음파 좌표 $(r, \theta, \phi)$가 무엇이었는지 수학적으로 역추적합니다.
   
### 4. 마스킹(Masking) 및 3D 삼선형 보간(Trilinear Interpolation)
역산된 구면 좌표가 실제 초음파가 스캔한 부채꼴 영역 안에 있는지 판별하고, 영역 안이라면 주변 8개 데이터의 가중 평균을 구해 값을 채웁니다.
 * **유효 영역 조건:**
   
 * **보간 로직:**
   위 조건을 만족하지 않으면 배열의 해당 위치는 **0 (Zero Padding)**으로 남습니다. 조건을 만족하면 역산된 (r, \theta, \phi) 실수 좌표를 둘러싼 Raw Data의 인접한 8개 정수 인덱스를 찾아 거리 반비례 가중치로 픽셀 값을 계산합니다.
### 5. 마스터 의사코드 (Master Pseudo-code)
위의 모든 수학적 유도 과정과 로직을 소프트웨어 알고리즘 형태로 정리한 최종 의사코드입니다.
```text
함수 Master_Scan_Conversion(Raw_Data, R시작, R끝, 방위각폭, 고도각폭, N=256):

    // [1] 물리적 한계점(Bounding Box) 계산
    Theta_max = 방위각폭 / 2
    Phi_max = 고도각폭 / 2
    
    L_x = 2 * R끝 * sin(Theta_max)
    L_y = 2 * R끝 * sin(Phi_max)
    L_z = R끝
    
    // [2] Isotropic Spacing 도출
    L_max = max(L_x, L_y, L_z)
    d = L_max / N
    
    // [3] 최종 출력용 빈 3D 배열 생성 (Zero Padding 기본값)
    Display_Volume = 생성(N, N, N, 초기값=0)
    
    // [4] 메모리 배열의 모든 복셀을 순회하며 매핑 및 역산
    FOR i FROM 0 TO N-1:        // X축 인덱스
        FOR j FROM 0 TO N-1:    // Y축 인덱스
            FOR k FROM 0 TO N-1:// Z축 인덱스
                
                // A. 인덱스(메모리)를 직교 좌표(물리공간)로 변환 (윗면 중앙 원점)
                x = (i - (N - 1) / 2) * d
                y = (j - (N - 1) / 2) * d
                z = k * d
                
                // Z가 0이고 X,Y가 0인 원점(트랜스듀서)에서의 분모 0 예외 처리
                IF x == 0 AND y == 0 AND z == 0:
                    r, theta, phi = 0, 0, 0
                ELSE:
                    // B. 직교 좌표를 구면 좌표로 역산
                    r = sqrt(x^2 + y^2 + z^2)
                    theta = arctan(x / z)
                    phi = arcsin(y / r)
                
                // C. 유효 스캔 영역(부채꼴 공간) 확인
                IF (r >= R시작 AND r <= R끝) AND 
                   (abs(theta) <= Theta_max) AND 
                   (abs(phi) <= Phi_max):
                   
                    // D. Raw Data(인덱스 공간의 직육면체)에서 3D 삼선형 보간 수행
                    픽셀값 = Trilinear_Interpolation(Raw_Data, r, theta, phi)
                    
                    // E. 결과 저장
                    Display_Volume[i, j, k] = 픽셀값
                
                // 유효 영역 밖의 값은 초기값인 0이 그대로 유지됨 (Zero Padding)

    RETURN Display_Volume, d

```

