# GE 3D TEE DICOM 구조 분석 및 Spacing 추출/활용 방안

## 1. 개요

본 문서는 GE Vivid 계열 3D TEE(경식도 심초음파) 데이터가 왜 일반적인 DICOM 파일과 다른 구조를 가지는지, 그 안에서 실제 공간 해상도인 spacing 정보를 어떻게 확보할 수 있는지, 그리고 확보한 spacing을 NRRD의 voxel 거리와 실제 millimeter(mm)로 어떻게 연결할 수 있는지를 설명하기 위한 기술 보고서이다.

핵심 질문은 다음과 같다.

1. DICOM은 무엇이며 왜 표준을 따라야 하는가?
2. GE의 3D TEE DICOM은 왜 표준과 사설 구조가 섞인 형태를 띠는가?
3. 실제 3D spacing 정보는 어디에 있고 어떻게 얻을 수 있는가?
4. scan conversion 이후 NRRD에서 voxel 간 거리는 어떻게 실제 mm로 해석되는가?

---

## 2. DICOM의 의미와 본질

### 2.1 DICOM의 뜻

DICOM은 `Digital Imaging and Communications in Medicine`의 약자이며, 의료 영상과 관련 메타데이터를 저장, 전송, 조회하기 위한 국제 표준 규약이다.

일반적인 이미지 파일이 단순히 픽셀 데이터만 저장하는 것과 달리, DICOM은 다음 정보를 하나의 컨테이너 안에 함께 저장할 수 있다.

- 환자 정보
- 검사 정보
- 장비 정보
- 촬영 조건
- 영상 픽셀 데이터
- 후처리나 분석에 필요한 부가 메타데이터

즉, DICOM은 단순한 그림 파일이 아니라 “의료 영상 데이터 교환용 표준화된 데이터 패키지”에 가깝다.

### 2.2 컴퓨터공학적 관점에서 본 DICOM

컴퓨터공학적으로 DICOM 파일은 연속된 바이트 스트림이며, 그 내부는 `Data Element`의 반복으로 구성된다. 각 Data Element는 기본적으로 다음 구조를 가진다.

- `Tag`: 이 데이터가 무엇인지 나타내는 식별자
- `VR (Value Representation)`: 값의 타입
- `Length`: 값의 길이
- `Value`: 실제 값

즉, DICOM은 본질적으로 아래와 같은 구조가 반복되는 직렬화 포맷이다.

`[Tag] [VR] [Length] [Value] [Tag] [VR] [Length] [Value] ...`

파일 시작부에는 보통 다음이 존재한다.

- 128바이트 preamble
- `DICM` prefix
- File Meta Information

이후부터는 태그 기반 메타데이터와 픽셀 데이터가 순차적으로 배치된다.

### 2.3 DICOM은 txt처럼 아무렇게나 써도 되는가?

아니다. 텍스트 파일처럼 자유 형식으로 작성하는 포맷이 아니다. DICOM은 병원 시스템, PACS, 영상 서버, 뷰어, 분석 소프트웨어 간 상호운용성을 보장하기 위한 표준이므로, 최소한 외형과 핵심 구조는 표준 규약을 따라야 한다.

다만 중요한 예외가 있다. DICOM은 제조사 고유 정보를 넣을 수 있도록 `Private Tag` 영역을 허용한다. 따라서 “겉은 표준, 속은 벤더 독자 규격”인 하이브리드 구조가 실제 현장에서 자주 사용된다.

### 2.4 왜 GE는 완전 독자 포맷이 아니라 DICOM을 제공하는가

이 질문은 GE 파일 구조를 이해하는 데 매우 중요하다. 결론부터 말하면, GE가 완전 독자 포맷만 제공하면 병원 생태계 안에서 데이터가 제대로 유통되기 어렵기 때문이다.

병원에서는 초음파 장비만 따로 존재하는 것이 아니라, 다음 시스템들이 하나의 워크플로로 연결되어 있다.

- 촬영 장비
- PACS 서버
- DICOM 라우터
- 병원 EMR/EHR 연동 시스템
- 범용 뷰어
- 전공의/전문의 판독 환경

이 환경에서는 특정 제조사 장비가 만들어낸 데이터가 적어도 저장, 검색, 전송, 기본 조회 정도는 다른 시스템과 호환되어야 한다. GE가 완전 독자 포맷만 사용하면 다음 문제가 생긴다.

- PACS 적재 실패 또는 별도 커넥터 필요
- 타 시스템에서 검색/조회 불가
- 병원 내 표준 영상 워크플로와 분리
- 장비 도입 및 운영 비용 증가

즉 GE 입장에서도 “아예 독자 포맷만 쓰는 것”은 병원 도입성과 실사용성 측면에서 불리하다. 따라서 외부 인터페이스는 DICOM으로 유지하는 것이 합리적이다.

하지만 동시에 GE는 자사 장비의 고유 3D RAW 데이터와 해석 로직까지 모두 표준 공개 형식으로 내놓고 싶어 하지는 않는다. 그래서 실제 전략은 다음과 같이 정리된다.

- 외부 호환을 위해 DICOM을 제공한다.
- 핵심 고유 데이터는 private tag와 독자 payload로 보호한다.

즉 GE가 DICOM을 제공하는 이유는 “표준 생태계에 들어가기 위해서”이고, private 구조를 쓰는 이유는 “핵심 기술을 그대로 노출하지 않기 위해서”이다.

---

## 3. DICOM 표준과 Private Tag

### 3.1 Public Tag와 Private Tag

DICOM 태그는 크게 두 종류로 볼 수 있다.

- Public Tag: 전 세계적으로 의미가 고정된 표준 태그
- Private Tag: 제조사나 특정 시스템만 의미를 아는 사설 태그

일반적으로 홀수 그룹 번호는 Private Tag로 쓰인다. 제조사는 이 영역에 자신들만의 메타데이터, RAW payload, 내부 분석 결과 등을 저장할 수 있다.

### 3.2 Private Tag가 필요한 이유

의료기기 제조사는 새로운 센서 구조, 독자 압축 포맷, 전용 분석 결과, 3D raw tensor 같은 표준에 아직 반영되지 않은 정보를 저장해야 한다. 표준 DICOM만으로는 이를 충분히 표현하기 어렵기 때문에 private 영역이 사용된다.

### 3.3 파서는 private tag를 어떻게 처리하는가

잘 만들어진 DICOM 파서는 모르는 태그를 만나더라도 바로 오류를 내지 않는다. 대신 `Length`를 읽고 그만큼 건너뛴다. 그래서 범용 DICOM 뷰어는 GE private payload를 이해하지 못해도, 그 앞뒤에 있는 표준 태그와 2D 이미지는 정상적으로 표시할 수 있다.

이 점이 GE 파일이 RadiAnt 같은 범용 뷰어에서 “어느 정도는 열리는” 이유다.

---

## 4. 왜 GE의 DICOM은 트로이 목마 구조를 띠는가

### 4.1 트로이 목마 구조의 의미

GE 3D TEE DICOM은 겉으로는 표준 DICOM처럼 보이지만, 실제 핵심 3D RAW 데이터와 기하학 정보는 private tag 내부에 숨기는 구조를 가진다. 이 구조를 비유적으로 “트로이 목마 구조”라고 부를 수 있다.

겉껍데기는 병원 시스템이 받아들일 수 있는 표준 형식이고, 내부에는 GE 전용 데이터와 해석 로직이 숨어 있다.

### 4.2 왜 이런 구조가 필요한가

#### 1) 완전 독자 포맷만으로는 병원 워크플로에 들어가기 어렵다

GE가 순수 독자 파일 포맷만 제공하면 GE 장비, GE 서버, GE 뷰어가 모두 필요해지는 강한 벤더 종속 구조가 생긴다. 이 경우 병원은 기존 PACS와 범용 뷰어 환경을 그대로 활용하기 어렵고, 운영 복잡도와 비용이 증가한다.

따라서 GE도 병원 환경에 자연스럽게 통합되려면 적어도 외부 인터페이스는 DICOM 형태로 제공할 필요가 있다.

#### 2) 병원 인프라와의 호환성 유지

병원의 PACS, DICOM 라우터, 뷰어, 아카이브 시스템은 기본적으로 표준 DICOM을 기대한다. 만약 GE가 완전한 독자 포맷만 사용하면 병원 시스템에서 저장, 조회, 전송 자체가 어려워진다.

즉, PACS를 통과하려면 최소한 표준 DICOM 외형은 반드시 필요하다.

#### 3) 범용 뷰어에서 최소한의 열람 보장

모든 사용자가 GE 전용 워크스테이션을 쓰는 것은 아니다. RadiAnt 같은 범용 뷰어에서도 환자 정보, 검사 정보, 대표 2D 이미지 정도는 볼 수 있어야 임상 워크플로가 돌아간다.

따라서 표준 태그와 대표 2D 이미지, 또는 스크린샷 수준의 데이터는 public 영역에 둔다.

#### 4) 핵심 3D 데이터와 해석 로직 보호

GE 입장에서 진짜 고부가가치 자산은 단순 2D 이미지가 아니라 다음과 같은 요소다.

- 3D raw tensor
- beam geometry
- spacing과 angle 정보
- scan conversion 로직
- 전용 측정 및 렌더링 알고리즘

이 정보가 완전히 공개되면 타사 소프트웨어도 GE 장비 데이터를 동일 수준으로 분석할 수 있게 된다. 따라서 핵심 payload는 private tag와 독자 바이너리 구조로 숨겨 전용 소프트웨어나 SDK가 있어야만 완전하게 활용 가능하도록 만든다.

#### 5) 표준 DICOM만으로 표현하기 어려운 제조사 고유 정보

특히 3D 초음파 RAW 데이터는 단순 2D 영상과 다르게 다음과 같은 제조사 고유 파라미터가 필요하다.

- 빔 수
- azimuth/elevation 방향의 각도 간격
- 깊이 샘플링 간격
- 스캔 시작점과 범위
- 내부 압축 방식
- 프로브/장비별 geometry

이 정보는 표준 태그만으로 완전히 기술하기 어려운 경우가 많다. 따라서 제조사는 private tag나 독자 payload를 선택한다.

#### 6) 기술적 요구와 사업적 목적의 절충

결론적으로 GE의 트로이 목마 구조는 다음 두 조건을 동시에 만족시키는 절충안이다.

- 병원 시스템에는 표준 DICOM처럼 보이게 한다.
- 핵심 3D 정보는 자사 생태계 안에 묶어 둔다.

즉, 기술적으로는 상호운용성을 확보하고, 사업적으로는 벤더 락인과 차별화된 분석 기능을 유지하는 구조다.

---

## 5. GE 3D TEE DICOM의 실제 구조

### 5.1 일반적인 흐름

GE 3D TEE DICOM은 대개 다음과 같이 구성된다.

1. 표준 DICOM 헤더와 일반 메타데이터
2. 범용 뷰어가 표시 가능한 2D 정보 또는 표준 이미지 영역
3. private creator
4. private tag 내부의 대용량 3D payload

대표적인 예시는 다음과 같다.

- `(7FE1,0010)` 또는 `(7FE1,0011)`: Private Creator
- `(7FE1,1001)` 또는 `(7FE1,1101)`: GE 3D payload

이 private payload 안에는 다시 GE/Kretz 계열 독자 바이너리 구조가 들어갈 수 있다.

### 5.2 Kretzfile 인셉션 구조

GE/Kretz 계열 파일에서는 DICOM private tag value 내부가 다시 독립적인 바이너리 포맷으로 구성되는 경우가 있다. 즉 DICOM 안에 또 다른 파일이 들어 있는 구조다.

이 내부 payload는 보통 다음 순서로 파악한다.

1. private tag value 추출
2. 앞부분의 magic/signature 확인
3. 내부 chunk 또는 구조체 형태 분석
4. 차원 정보, spacing, raw tensor 읽기

따라서 분석 관점에서는 “DICOM 파싱”과 “GE 내부 포맷 파싱”이 분리된 두 단계 작업이 된다.

---

## 6. Spacing의 의미

### 6.1 spacing이란 무엇인가

spacing은 데이터 인덱스 한 칸이 현실 세계에서 얼마만큼의 거리 또는 각도에 대응하는지 나타내는 값이다.

예를 들어 3D Cartesian volume에서 spacing이 `(0.5, 0.5, 0.8)`이라면:

- x축 voxel 1칸 = 0.5 mm
- y축 voxel 1칸 = 0.5 mm
- z축 voxel 1칸 = 0.8 mm

이 정보가 있어야 영상 위의 길이, 면적, 부피 측정이 실제 물리 단위로 가능해진다.

### 6.2 초음파 RAW에서 spacing은 더 복잡하다

3D 초음파 RAW는 처음부터 Cartesian voxel 격자가 아니라 beam 기반 좌표계에 가깝다. 즉 원본 공간은 보통 다음 세 축으로 생각해야 한다.

- `r`: depth 방향 샘플 인덱스
- `θ`: azimuth 방향 빔 인덱스
- `φ`: elevation 방향 빔 인덱스

이때 원본 spacing은 단순히 mm/mm/mm가 아니라 아래처럼 표현될 수 있다.

- `Δr`: 깊이 방향 실제 거리 간격(mm)
- `Δθ`: azimuth 방향 각도 간격(degree)
- `Δφ`: elevation 방향 각도 간격(degree)

즉 scan conversion 이전에는 “깊이 축은 거리”, “나머지 두 축은 각도”인 혼합적 기하 구조를 가진다.

---

## 7. GE 3D spacing을 얻는 방법

### 7.1 방법 1: 표준 태그 먼저 확인

제조사가 표준을 잘 따랐다면 아래 태그에서 단서를 찾을 수 있다.

- `(0018,6011)` Sequence of Ultrasound Regions
- `(0018,6024)` Physical Units X Direction
- `(0018,6026)` Physical Units Y Direction
- `(0018,602C)` Physical Delta X
- `(0018,602E)` Physical Delta Y

하지만 GE 3D TEE RAW에서는 여기 표준 태그가 2D 표시용 정보만 담고 있고, 진짜 3D spacing은 private 영역에 있을 가능성이 크다.

### 7.2 방법 2: 3D Slicer + SlicerHeart 사용

실무적으로 가장 빠르고 재현성 있는 방법은 `3D Slicer`와 `SlicerHeart`를 사용하는 것이다.

SlicerHeart의 DICOM ultrasound plugin은 다음을 수행한다.

1. GE/Kretz 파일인지 식별
2. private tag payload의 위치를 찾음
3. 내부 reader(C++)로 전달
4. 3D volume으로 로딩
5. 측정 가능한 volume node 생성

중요한 점은, 만약 3D Slicer에서 볼륨이 정상 렌더링되고 길이 측정이 가능하다면, 프로그램 내부적으로 spacing 또는 spacing에 준하는 geometry 변환 정보가 확보되었다는 뜻이라는 점이다.

### 7.3 방법 3: Slicer에서 spacing 직접 읽기

Slicer에서 로드 후 `Volumes` 모듈 또는 Python interactor에서 spacing을 확인할 수 있다.

예시:

```python
volumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
spacing = volumeNode.GetSpacing()
print(spacing)
```

다만 이 값은 다음 둘 중 하나일 수 있다.

- 원본 acquisition spacing
- scan conversion 후 재표본화된 Cartesian voxel spacing

실무적으로는 후자인 경우가 많다.

### 7.4 방법 4: private payload 직접 파싱

보다 원천적인 방법은 private tag value를 직접 추출해서 파싱하는 것이다.

절차는 다음과 같다.

1. `pydicom`으로 DICOM 로드
2. `(7FE1,1101)` 또는 `(7FE1,1001)`의 value 추출
3. value 내부의 GE/Kretz payload를 별도 바이너리로 저장
4. magic number, chunk 구조, 내부 헤더 분석
5. dimensions, spacing, origin, raw tensor 매핑

이 방식은 가장 저수준이지만, 원본 RAW geometry를 확인하는 데 가장 직접적이다.

---

## 8. SlicerHeart 코드 관점에서 spacing 확보 원리

### 8.1 Python 레벨의 역할

SlicerHeart의 `DicomUltrasoundPlugin.py`는 먼저 파일이 GE 3D ultrasound인지 식별한다.  
예를 들어 `examineGeKretzUS()`는 다음을 확인한다.

- SOP Class UID
- private creator 존재 여부
- GE/Kretz 관련 private tag 존재 여부

이 단계의 목적은 “이 파일이 어떤 reader로 처리되어야 하는가”를 결정하는 것이다.

### 8.2 loadKretzUS의 의미

`loadKretzUS()`는 실제 3D payload 시작 위치를 찾아 C++ reader에 넘기는 역할을 한다.

즉 Python은:

- DICOM 껍질을 읽고
- private payload가 시작되는 파일 offset을 구하고
- 그 offset을 C++ loader에 넘긴다

### 8.3 C++ reader의 역할

C++ reader는 전달받은 offset 위치부터 GE/Kretz 내부 포맷을 파싱한다.  
여기서 다음 정보가 추출되거나 계산된다.

- volume dimensions
- spacing 또는 geometry 변환에 필요한 파라미터
- raw scalar data
- 최종 volume node 생성 정보

즉, Slicer에서 측정 가능한 volume이 만들어졌다는 사실 자체가 geometry 해석이 성공했다는 강력한 증거다.

---

## 9. Scan conversion과 spacing의 관계

### 9.1 scan conversion 이전

원본 3D 초음파 데이터는 보통 다음처럼 생각할 수 있다.

`Raw[φ][θ][r]`

각 인덱스는 다음을 의미한다.

- `r`: 한 빔을 따라 샘플링한 깊이 인덱스
- `θ`: azimuth 방향 빔 인덱스
- `φ`: elevation 방향 빔 인덱스

이 상태에서는 인덱스 차이를 바로 mm 거리로 해석할 수 없다.  
이유는 두 축이 각도 단위이기 때문이다.

### 9.2 scan conversion 이후

scan conversion은 이 beam 기반 또는 구면계 기반 데이터를 Cartesian voxel 격자로 재배열하는 과정이다.  
이 단계가 끝나면 데이터는 `(x, y, z)` 축을 가지는 정규 volume이 되고, 각 축 spacing은 보통 mm 단위가 된다.

즉 scan conversion 이후 NRRD의 spacing은 “실제 3차원 공간 위의 voxel 간 물리 거리”를 뜻한다.

### 9.3 델타값이 없으면 어떤 문제가 생기는가

원본 `Δr`, `Δθ`, `Δφ`를 모르면 대략적인 렌더링은 할 수 있어도 다음 문제가 생긴다.

- 종횡비 왜곡
- 실제 길이 측정 불가능
- 부피 계산 부정확
- 심장 구조가 비정상적으로 늘어나거나 찌그러짐

따라서 정량 분석에는 spacing이 필수다.

---

## 10. NRRD에서 voxel 간 거리와 실제 mm의 관계

### 10.1 NRRD의 기본 개념

NRRD는 3차원 또는 다차원 배열과 그 좌표계 정보를 함께 저장하는 포맷이다.  
의료 영상에서는 scan-converted volume을 담는 데 자주 사용된다.

NRRD에서 중요한 것은 단순 voxel 값뿐 아니라 다음 메타데이터다.

- sizes
- space directions
- space origin

많은 경우 `space directions`의 각 벡터 길이가 해당 축의 spacing을 의미한다.

### 10.2 쉬운 해석

예를 들어 NRRD spacing이 아래와 같다고 하자.

- x spacing = 0.5 mm
- y spacing = 0.5 mm
- z spacing = 0.8 mm

그러면:

- x 방향으로 voxel 1칸 이동 = 0.5 mm
- y 방향으로 voxel 1칸 이동 = 0.5 mm
- z 방향으로 voxel 1칸 이동 = 0.8 mm

### 10.3 인덱스 차이를 실제 거리로 바꾸는 공식

두 점의 voxel index 차이가 `(Δi, Δj, Δk)`이고 spacing이 `(sx, sy, sz)`라면 실제 거리(mm)는 다음과 같다.

```text
distance_mm = sqrt((Δi*sx)^2 + (Δj*sy)^2 + (Δk*sz)^2)
```

예를 들어:

- index 차이 = `(10, 4, 3)`
- spacing = `(0.5, 0.5, 0.8)` mm

이면,

```text
distance_mm = sqrt((10*0.5)^2 + (4*0.5)^2 + (3*0.8)^2)
            = sqrt(25 + 4 + 5.76)
            = sqrt(34.76)
            ≈ 5.90 mm
```

즉 voxel 개수만으로는 실제 길이를 알 수 없고, 반드시 spacing이 곱해져야 한다.

### 10.4 중요한 주의점

GE RAW spacing과 NRRD spacing은 동일하지 않을 수 있다.

- GE RAW spacing: 원본 beam geometry 기반
- NRRD spacing: scan conversion 이후 Cartesian voxel spacing

따라서 분석 목적에 따라 어떤 spacing을 사용할지 명확히 해야 한다.

- 원본 acquisition geometry를 연구하려면 RAW 기준 spacing
- 3D volume 상 측정과 후처리를 하려면 NRRD 기준 spacing

---

## 11. 실무 권장 분석 절차

### 11.1 가장 현실적인 접근

1. DICOM 표준 태그 확인
2. private creator 및 private payload 존재 확인
3. 3D Slicer + SlicerHeart로 로딩 시도
4. 로딩 성공 시 volume spacing 확인
5. NRRD export 후 후처리 및 측정
6. 원본 geometry 검증이 필요하면 private payload 직접 파싱

### 11.2 목적별 권고안

#### 임상 시각화/일반 분석 목적

- Slicer에서 로드
- NRRD로 export
- export된 volume의 spacing 활용

#### 정량 연구/재현성 검증 목적

- private payload도 별도 보관
- 원본 spacing과 NRRD spacing 차이를 문서화
- 필요 시 GE/Kretz 내부 geometry를 직접 복원

#### 제품화 또는 자동화 파이프라인 목적

- 표준 DICOM 메타데이터 추출
- private payload 추출
- scan conversion 결과와 원본 geometry를 분리 관리

---

## 12. 결론

GE의 3D TEE DICOM은 표준 DICOM 규약을 따르되, 핵심 3D RAW 데이터와 geometry 정보를 private tag 안에 숨기는 트로이 목마형 구조를 가진다.  
이 구조는 병원 PACS와 범용 뷰어 호환성을 유지하면서도, 고부가가치 3D 데이터와 해석 로직은 자사 생태계 안에 보호하려는 기술적·사업적 절충의 결과다.

Spacing을 확보하는 방법은 크게 세 단계로 정리할 수 있다.

1. 표준 태그 확인
2. 3D Slicer/SlicerHeart를 통한 로딩 및 spacing 확인
3. 필요 시 private payload 직접 파싱

또한 scan conversion 이후 NRRD에서의 spacing은 voxel 간 물리 거리(mm)를 의미하며, 이를 통해 길이와 부피를 실제 단위로 계산할 수 있다. 다만 원본 GE RAW spacing과 NRRD spacing은 서로 다른 좌표계 개념일 수 있으므로, 분석 목적에 따라 구분해서 사용해야 한다.

---

## 13. 핵심 요약

- DICOM은 의료 영상 교환을 위한 국제 표준 규약이다.
- GE 3D TEE DICOM은 표준 외피와 private payload가 공존하는 하이브리드 구조다.
- 이 구조는 PACS 호환성과 벤더 고유 기술 보호를 동시에 만족시키기 위한 트로이 목마 전략이다.
- 범용 뷰어는 표준 2D 부분만 읽고, private 3D payload는 건너뛴다.
- 실제 3D spacing은 표준 태그보다 private payload나 전용 reader에서 확보될 가능성이 높다.
- 3D Slicer에서 정상 렌더링과 길이 측정이 가능하다면, 내부적으로 geometry 해석이 성공했다는 뜻이다.
- NRRD spacing은 scan conversion 이후 Cartesian voxel 간 실제 mm 거리로 해석할 수 있다.
