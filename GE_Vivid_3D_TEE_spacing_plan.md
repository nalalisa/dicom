# GE Vivid 3D TEE DICOM Spacing 추출 및 검증 계획

## 목적

이 문서는 GE Vivid 3D TEE DICOM 파일에서 spacing 정보를 실전적으로 추출하고, 그 값이 맞는지 검증하는 실행 계획서다. 함께 제공하는 스크립트는 plain Python 환경에서의 direct parse와, 3D Slicer가 있을 때의 교차검증을 지원한다.

핵심 목표는 두 가지다.

1. GE 파일에서 신뢰할 수 있는 spacing 정보를 뽑아낸다.
2. 그 값이 단순 추정이 아니라는 점을 구조적, 시각적, 교차도구 방식으로 검증한다.

## 먼저 분리해서 봐야 하는 두 종류의 spacing

### 1. 원본 RAW geometry spacing

이것이 가장 중요한 값이다. scan conversion 이전의 빔 좌표계 기준 정보다.

- 깊이 방향: `radial resolution`
- 방위각 방향: `theta angle array`
- 고도각 방향: `phi angle array`
- 시작 위치: `offset1`
- B-mode radius 관련 항목: `offset2`

원본 RAW에서는 lateral/elevation이 고정 mm spacing이 아니다. 즉 “한 칸이 몇 mm냐”가 깊이에 따라 달라진다. 따라서 원본의 정확한 물리 기술은 `radial resolution + theta array + phi array` 조합이다.

### 2. Scan-converted Cartesian voxel spacing

이것은 RAW를 Cartesian volume으로 재구성한 뒤의 voxel spacing이다. 예를 들어 `(0.667, 0.667, 0.667) mm` 같은 값이 여기에 해당한다.

중요한 점은 이 값이 항상 원본에서 직접 온 값이 아니라는 것이다. 특히 SlicerHeart는 scan conversion 시 사용자가 output spacing을 고를 수 있으므로, Slicer에서 보이는 spacing은 reconstruction grid일 수 있다.

즉 실무에서는 다음을 반드시 구분해야 한다.

- 원본 acquisition geometry
- 재구성 후 volume spacing

## 실전 추출 전략

### 1단계: 파일 종류 식별

먼저 private creator와 private payload를 보고 파일이 어느 계열인지 판별한다.

- `KRETZ_US` 계열이면 direct parse 우선
- `GEMS_Ultrasound_MovieGroup_001` 계열이면 external reader 경로 우선

실무적으로 가장 중요한 분기는 아래와 같다.

- `(7FE1,0011)=KRETZ_US` 와 `(7FE1,1101)` payload가 있으면 KRETZ direct parse 가능성이 높다.
- `(7FE1,0010)=GEMS_Ultrasound_MovieGroup_001` 이면 MovieGroup/Image3DAPI 계열일 수 있다.

### 2단계: KRETZ payload direct parse

KRETZ payload가 있으면 이 경로가 가장 강하다. SlicerHeart의 공개 C++ 구현 기준으로, 다음 item들이 핵심이다.

- `(C000,0001)`: Dimension I
- `(C000,0002)`: Dimension J
- `(C000,0003)`: Dimension K
- `(C100,0001)`: Radial resolution
- `(C200,0001)`: offset1
- `(C200,0002)`: offset2
- `(C300,0001)`: Phi angle array
- `(C300,0002)`: Theta angle array
- `(0010,0022)`: Cartesian spacing candidate
- `(D000,0001)`: Voxel data

이 중 실제로 가장 신뢰해야 할 값은 아래다.

- radial resolution
- theta angle array
- phi angle array
- offset1, offset2

반면 `(0010,0022)`는 참고값으로만 두는 것이 안전하다. SlicerHeart 코드에도 “works, but not confirmed” 성격의 주석이 있다.

### 3단계: MovieGroup 계열이면 external reader로 전환

MovieGroup 3D 계열은 공개 파서만으로 정확한 spacing을 복원하기 어려운 경우가 있다. 이 경우는 다음 경로가 현실적이다.

- 3D Slicer + SlicerHeart + Image3dAPI
- GE 제공 DLL/SDK
- EchoPAC 또는 제조사 전용 도구

즉 KRETZ는 direct parse, MovieGroup은 external reader로 접근하는 것이 안전하다.

## “정확한 spacing을 얻었다”고 판단하는 기준

### 1. 구조적 검증

파싱한 값이 내부 구조와 모순이 없어야 한다.

- payload가 `KRETZFILE 1.0` magic으로 시작하는가
- theta 개수 = Dimension J 인가
- phi 개수 = Dimension K 인가
- radial resolution > 0 인가
- theta, phi가 단조 증가하는가
- voxel byte count가 dimension product와 합리적으로 맞는가

이 단계는 “파일을 잘못 읽은 것은 아닌가”를 걸러낸다.

### 2. 물리적 검증

추출한 geometry가 초음파 데이터로서 말이 되는지 본다.

- radial resolution이 비현실적이지 않은가
- theta/phi step이 비정상적으로 흔들리지 않는가
- start depth, end depth, sector range가 3D TEE로서 그럴듯한가
- 깊이에 따른 lateral/elevation arc length가 자연스럽게 증가하는가

여기서 중요한 점은 lateral/elevation에서 “1 index = 몇 mm”가 깊이에 따라 달라진다는 사실을 확인하는 것이다.

### 3. 시각적 검증

QC plot을 만들어 geometry가 이상하지 않은지 확인한다.

추천 plot:

- theta angle vs index
- phi angle vs index
- theta/phi increment plot
- sector outline plot
- 특정 깊이에서 lateral arc length plot

### 4. 교차도구 검증

가능하면 3D Slicer를 써서 같은 파일을 읽고 geometry를 교차검증한다.

하지만 여기서도 주의점이 있다. Slicer의 scan-converted spacing은 raw spacing이 아니라 reconstruction grid일 수 있다. 따라서 검증 포인트는 “spacing 숫자가 똑같은가”가 아니라 아래다.

- 내가 파싱한 raw geometry로 계산한 Cartesian bounds/dimensions
- Slicer가 같은 output spacing으로 재구성했을 때의 bounds/dimensions

이 잘 맞으면 geometry 파싱이 거의 맞았다고 볼 수 있다.

## 권장 실무 절차

1. Python 스크립트로 DICOM을 분석한다.
2. 파일이 `KRETZ_US`인지 `MovieGroup`인지 판별한다.
3. `KRETZ_US`이면 payload를 직접 파싱해 raw geometry를 얻는다.
4. validation check와 QC plot을 확인한다.
5. 필요하면 3D Slicer에서 같은 output spacing으로 재구성하고 dimensions/origin을 비교한다.
6. 가능하면 EchoPAC 측정값 또는 화면 depth ruler와도 비교한다.

## 제공 스크립트

### `ge_vivid_spacing_extract.py`

plain Python에서 실행하는 메인 도구다.

기능:

- DICOM 기본 메타데이터 요약
- private creator 탐색
- GE flavor 판별
- KRETZ payload direct parse
- raw geometry spacing 요약
- validation check 생성
- QC plot 생성
- scan-conversion geometry prediction
- 선택적으로 Slicer probe JSON과 비교

예시:

```bash
python ge_vivid_spacing_extract.py "C:\path\file.dcm" --output-dir out
```

payload도 저장하려면:

```bash
python ge_vivid_spacing_extract.py "C:\path\file.dcm" --output-dir out --export-kretz-payload
```

Slicer와 같은 reconstruction spacing으로 예측하려면:

```bash
python ge_vivid_spacing_extract.py "C:\path\file.dcm" --output-dir out --predict-spacing 0.667 0.667 0.667
```

### `slicer_kretz_probe.py`

3D Slicer 안에서 실행하는 보조 검증 스크립트다.

기능:

- DICOM 안의 KRETZ payload offset 찾기
- SlicerHeart `LoadKretzFile()` 호출
- scan-converted volume의 spacing/origin/dimensions 저장

실행 예시:

```bash
Slicer.exe --no-splash --python-script slicer_kretz_probe.py -- "C:\path\file.dcm" "C:\path\probe.json" 0.667 0.667 0.667
```

주의:

- 이 결과는 raw spacing이 아니라 scan-converted output spacing이다.
- 대신 main script가 예측한 geometry와 비교하는 데 매우 유용하다.

### `ge_vivid_scanconvert_view.py`

경로만 스크립트 상단의 `DICOM_PATH`에 넣고 바로 실행하는 단일 실행 스크립트다.

기능:

- KRETZ payload에서 raw geometry 추출
- output spacing 선택
- Python만으로 scan conversion 수행
- 중심 axial/coronal/sagittal 슬라이스와 MIP 이미지 저장
- sector outline 이미지 저장
- summary JSON 저장

이 스크립트는 “spacing이 맞는지 눈으로 먼저 확인하고 싶다”는 목적에 가장 적합하다.

## 권장 판정 로직

### High confidence

- KRETZ direct parse 성공
- validation check 대부분 통과
- theta/phi/dim 일치
- QC plot 정상
- Slicer predicted vs actual dimensions/origin 일치

### Medium confidence

- KRETZ parse는 성공했지만
- Slicer cross-check가 아직 없거나
- 일부 보조 정보가 부족함

### Low confidence

- KRETZ payload가 아니고 MovieGroup 계열
- SDK/Image3DAPI 없이 3D spacing을 직접 복원할 수 없음

## 핵심 결론

GE Vivid 3D TEE DICOM에서 spacing을 “정확히” 얻으려면, raw spacing과 scan-converted voxel spacing을 분리해서 다뤄야 한다.

가장 신뢰도 높은 경로는 다음이다.

1. `KRETZ_US` payload를 직접 파싱한다.
2. `radial resolution + theta array + phi array + offsets`를 원본 geometry로 사용한다.
3. 이것으로 scan conversion geometry를 예측한다.
4. 동일 output spacing으로 SlicerHeart를 돌려 dimensions/origin을 비교한다.
5. 가능하면 EchoPAC 또는 depth ruler와도 비교한다.

즉 실전에서는 “spacing 값 하나를 찾는다”보다, geometry 전체가 일관되게 맞는지 검증하는 방식이 더 안전하다.
