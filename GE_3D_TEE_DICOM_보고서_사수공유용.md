# GE 3D TEE DICOM 구조 분석 보고서

## 1. 문서 목적

본 문서는 GE Vivid 계열 3D TEE DICOM 데이터의 구조를 분석하고,  
현재 프로젝트에서 필요한 `spacing 해석`과 `후속 활용 방식`을 정리하기 위한 기술 보고서다.

본 보고서의 핵심 목표는 아래와 같다.

- GE 3D TEE DICOM이 일반 DICOM과 다른 이유를 설명
- 실제 3D geometry / spacing 정보가 어디에 있는지 정리
- 현재 분석 결과를 바탕으로 어떤 정보를 실제 파이프라인에 활용할 수 있는지 제시
- 남아 있는 불확실성과 추가 확인 필요 항목을 분리

---

## 2. 요약 결론

### 2.1 핵심 결론

- GE 3D TEE DICOM은 `표준 DICOM 외피 + GE private payload` 구조를 가진다.
- 표준 DICOM 태그만으로는 GE 3D raw geometry를 완전히 해석하기 어렵다.
- 실제 3D spacing은 하나의 값으로 정리되지 않으며, 아래 두 가지를 구분해야 한다.
  - `raw geometry`: acquisition 기준
  - `scan-converted spacing`: Cartesian volume 기준
- `KRETZ_US` branch에서는 공개 구현을 참고해 dimensions, radial resolution, theta/phi arrays, voxel data를 추적할 수 있다.
- 후처리와 정량 계산에서는 `현재 사용하는 volume이 raw 기준인지 scan-converted 기준인지`를 먼저 확정해야 한다.

### 2.2 현재 바로 활용 가능한 판단

- GE payload 구조를 이해할 때는 DICOM public tag만 보지 말고 private creator와 private payload를 함께 봐야 한다.
- NRRD 또는 viewer 상의 spacing은 scan-converted 결과일 가능성이 크므로, raw spacing과 동일한 개념으로 사용하면 안 된다.
- 정량 분석이나 엔진 구현 시에는 `어떤 좌표계의 spacing을 쓰는지`를 문서와 코드 양쪽에서 명시해야 한다.

---

## 3. 분석 범위 및 전제

### 3.1 분석 대상

- GE Vivid 계열 3D TEE DICOM 샘플
- 공개 구현체인 `SlicerHeart`의 GE ultrasound 관련 reader
- private payload branch 중 `KRETZ_US`, `MovieGroup` 계열

### 3.2 분석 목적

이번 분석의 목적은 DICOM 전체 표준을 정리하는 것이 아니라,  
현재 프로젝트에서 필요한 아래 항목을 파악하는 데 있다.

- GE 3D payload 구조의 개요
- spacing 및 geometry 정보의 위치와 의미
- scan conversion 이후 spacing과의 관계
- 후속 구현 시 사용 가능한 정보와 주의사항

---

## 4. GE 3D TEE DICOM이 일반 DICOM과 다른 이유

GE 3D TEE DICOM은 병원 시스템과의 호환성을 위해 외형상 표준 DICOM을 따른다.  
하지만 핵심 3D raw 데이터와 geometry 정보는 private tag 내부에 저장한다.

이 구조는 다음 두 요구를 동시에 만족시키기 위한 것으로 해석된다.

1. `병원 표준 워크플로와의 호환성 유지`
   - PACS 저장
   - DICOM 라우팅
   - 기본 조회 및 검색

2. `제조사 고유 3D 데이터 및 해석 로직 보호`
   - raw tensor
   - beam geometry
   - spacing/angle 정보
   - scan conversion 관련 로직

즉 GE 3D TEE DICOM은 아래처럼 보는 것이 적절하다.

```text
겉: 표준 DICOM
속: GE private 3D payload
```

---

## 5. 구조 분석 결과

## 5.1 DICOM 외피

표준 DICOM 레벨에서는 다음 정보가 존재할 수 있다.

- 환자 및 검사 정보
- 장비 정보
- 표준 메타데이터
- 일부 2D 표시용 데이터
- private creator / private payload container

이 레벨의 의미는 `병원 시스템과의 상호운용성`이다.

## 5.2 GE private payload

private tag 안에는 GE 전용 구조가 들어갈 수 있으며, 현재 확인한 주요 branch는 다음과 같다.

### 1) `KRETZ_US`

대표적 패턴:

- `(7FE1,0011) = KRETZ_US`
- `(7FE1,1101)`에 large payload

특징:

- private tag value 내부에 다시 GE/Kretz 내부 포맷이 포함됨
- direct parse 가능성이 상대적으로 높음
- 공개 구현을 통한 구조 추적이 가능함

### 2) `GEMS_Ultrasound_MovieGroup_001`

대표적 패턴:

- `(7FE1,0010) = GEMS_Ultrasound_MovieGroup_001`

특징:

- nested sequence 또는 movie group 구조를 가질 수 있음
- 2D / 3D / temporal 요소가 혼합될 수 있음
- vendor-specific reader 의존성이 더 클 수 있음

---

## 6. spacing 및 geometry 해석

## 6.1 spacing을 하나로 보면 안 되는 이유

GE 3D TEE 데이터에서 spacing은 단일 개념이 아니라 최소 두 층으로 나누어 해석해야 한다.

### raw geometry

raw acquisition 기준 정보다.

대표 구성:

- `radial_resolution`
- `theta angle array`
- `phi angle array`
- 필요 시 `offset`

이 좌표계는 보통 아래와 같이 이해할 수 있다.

```text
Raw[r_index, theta_index, phi_index]
```

즉 depth 방향은 거리(mm)에 대응하고, 나머지 두 축은 각도 기반이다.

### scan-converted spacing

scan conversion 이후 생성된 Cartesian volume의 voxel spacing이다.

```text
(sx, sy, sz) mm per voxel
```

이 값은 후처리, 시각화, 길이 측정 등에 바로 활용하기 쉬운 형태다.

## 6.2 현재 분석에서 중요한 판단

- `raw geometry`와 `scan-converted spacing`은 서로 다른 의미다.
- viewer 또는 NRRD에서 확인되는 spacing은 대개 scan-converted 결과일 가능성이 높다.
- 원본 acquisition geometry를 논할 때 scan-converted spacing을 그대로 쓰면 해석이 왜곡될 수 있다.

---

## 7. KRETZ branch에서 확인 가능한 정보

공개 구현을 기준으로 KRETZ payload에서는 다음 정보가 확인 가능하다.

| 항목 | 의미 |
|---|---|
| Dimension I/J/K | raw tensor shape |
| Radial resolution | depth 방향 샘플 간격 |
| Offset1/Offset2 | geometry 보정 또는 시작 위치 관련 정보 |
| Phi angle array | elevation 방향 각도 배열 |
| Theta angle array | azimuth 방향 각도 배열 |
| Cartesian spacing candidate | scan-converted spacing 후보 |
| Voxel data | intensity data |

이로부터 얻을 수 있는 중요한 해석은 다음과 같다.

- raw 텐서는 정규 Cartesian grid가 아니라 beam geometry 기반으로 획득된 데이터다.
- raw geometry를 복원하려면 radial resolution만으로는 부족하고, theta/phi angle 정보가 함께 필요하다.
- scan conversion 이후 spacing 후보와 raw geometry 관련 파라미터는 분리해서 다뤄야 한다.

---

## 8. SlicerHeart 기준 해석

현재 분석 과정에서 SlicerHeart 공개 구현은 구조 파악의 주요 참고 자료로 활용했다.

### Python 레벨에서 수행되는 일

- GE 3D ultrasound DICOM 여부 식별
- private creator 및 payload 위치 확인
- 적절한 C++ reader로 전달

### C++ reader에서 수행되는 일

- private payload 내부 구조 파싱
- volume dimensions 확인
- geometry / spacing 관련 정보 해석
- 최종적으로 volume node 생성

따라서 `Slicer에서 정상 렌더링 및 길이 측정이 가능하다`는 사실은,  
내부적으로 geometry 해석이 성공했다는 강한 근거가 된다.

다만 여기서 확인되는 spacing이 항상 원본 raw spacing을 직접 의미하는 것은 아니며,  
scan conversion 이후 volume spacing일 가능성을 함께 고려해야 한다.

---

## 9. NRRD spacing과 실제 거리 해석

scan-converted volume을 NRRD로 다룰 경우, 일반적으로 spacing은 Cartesian voxel 간 실제 물리 거리(mm)로 해석할 수 있다.

예를 들어 spacing이 `(sx, sy, sz)`일 때,  
voxel index 차이 `(Δi, Δj, Δk)`에 대한 실제 거리는 아래와 같이 계산된다.

```text
distance_mm = sqrt((Δi*sx)^2 + (Δj*sy)^2 + (Δk*sz)^2)
```

즉, NRRD 또는 viewer 상의 spacing은 정량 계산에 직접 사용하기 편한 값이다.  
다만 이 값은 raw acquisition geometry와 동일 개념이 아닐 수 있으므로, 용도를 분리해야 한다.

권장 해석:

- `원본 GE payload 구조 분석`: raw geometry 기준
- `후처리/시각화/측정`: scan-converted volume spacing 기준

---

## 10. 현재 프로젝트 관점의 적용 방안

현재 프로젝트에서 본 분석 결과는 아래와 같이 활용 가능하다.

### 10.1 데이터 해석 단계

- GE DICOM의 geometry는 public tag만으로 판단하지 않는다.
- private creator와 payload branch를 함께 확인한다.
- raw geometry와 scan-converted spacing을 문서/코드에서 분리 관리한다.

### 10.2 학습 및 후처리 단계

- 학습 데이터 전처리 시 현재 사용하는 spacing이 raw 기준인지 scan-converted 기준인지 명시한다.
- 길이/면적/부피 해석이 들어가는 경우 spacing의 기준 좌표계를 함께 기록한다.

### 10.3 엔진/정량 계산 단계

- measure 계산 전 source of truth가 되는 좌표계를 먼저 확정한다.
- viewer나 NRRD 기반 정량이면 scan-converted spacing을 사용한다.
- 원본 probe geometry 자체를 반영해야 하는 계산이라면 raw geometry를 별도 유지해야 한다.

---

## 11. 현재까지 확인된 사항과 남은 이슈

## 11.1 현재까지 확인된 사항

- GE 3D TEE DICOM은 표준 DICOM 외피와 private payload의 이중 구조를 가진다.
- KRETZ branch에서는 공개 구현을 참고해 주요 geometry 관련 항목을 추적할 수 있다.
- raw geometry와 scan-converted spacing은 분리해서 해석해야 한다.
- SlicerHeart는 실제 geometry 해석이 가능한 참고 구현으로 활용할 수 있다.

## 11.2 남은 이슈

- 현재 프로젝트에서 사용 중인 모든 GE 데이터가 동일 branch를 따르는지
- 장비 또는 export 버전에 따라 private item 구성이 달라지는지
- 현재 확보한 spacing 후보가 raw 기준인지 scan-converted 기준인지
- 최종 엔진/후처리에서 어떤 좌표계를 기준으로 정량 계산할지

---

## 12. 제안 사항

향후 구현과 문서화를 위해 아래 항목을 권장한다.

1. 코드와 문서에서 `spacing`이라는 단어를 단독으로 쓰지 않는다.
2. 아래 용어를 분리해서 사용한다.
   - `raw_geometry`
   - `radial_resolution_mm`
   - `theta_angles`
   - `phi_angles`
   - `scan_converted_spacing_mm`
3. 샘플별로 아래 항목을 체크리스트로 관리한다.
   - private creator 종류
   - payload branch
   - dimensions 확인 여부
   - spacing 후보 확인 여부
   - raw / scan-converted 구분 여부

---

## 13. 결론

GE 3D TEE DICOM은 병원 시스템과의 호환성을 위해 표준 DICOM 형식을 유지하면서,  
핵심 3D raw 데이터와 geometry 정보는 private payload 안에 저장하는 구조를 가진다.

현재 분석 결과 기준으로, spacing과 geometry를 올바르게 해석하려면 다음 구분이 필수적이다.

- `원본 acquisition geometry`
- `scan conversion 이후 volume spacing`

즉 본 과제는 단순히 “spacing 값을 하나 찾는 문제”가 아니라,  
`어떤 좌표계에서 어떤 spacing을 사용할 것인가`를 명확히 하는 문제에 가깝다.

현재 단계에서 가장 중요한 후속 작업은 다음과 같다.

- 현재 사용 중인 데이터 branch와 geometry 해석 기준을 확정
- raw geometry와 scan-converted spacing을 분리 기록
- 정량 계산 및 후처리에서 사용할 기준 좌표계를 명시

---

## 참고 자료

- [SlicerHeart repository](https://github.com/SlicerHeart/SlicerHeart)
- [DicomUltrasoundPlugin.py](https://raw.githubusercontent.com/SlicerHeart/SlicerHeart/master/DicomUltrasoundPlugin/DicomUltrasoundPlugin.py)
- [KretzFileReader logic](https://raw.githubusercontent.com/SlicerHeart/SlicerHeart/master/KretzFileReader/Logic/vtkSlicerKretzFileReaderLogic.cxx)
- [GeUsMovieReader logic](https://raw.githubusercontent.com/SlicerHeart/SlicerHeart/master/GeUsMovieReader/Logic/vtkSlicerGeUsMovieReaderLogic.cxx)
- [Image import notes](https://raw.githubusercontent.com/SlicerHeart/SlicerHeart/master/Docs/ImageImportExport.md)
