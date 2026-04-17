$OutputPath = "C:\Users\Andrew\Documents\PROJECT\DICOM\GE_3D_TEE_DICOM_발표자료.pptx"

function Add-TitleSlide {
    param($Presentation, $Title, $Subtitle)
    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, 1)
    $slide.Shapes.Title.TextFrame.TextRange.Text = $Title
    $slide.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text = $Subtitle
}

function Add-BulletsSlide {
    param($Presentation, $Title, [string[]]$Bullets)
    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, 2)
    $slide.Shapes.Title.TextFrame.TextRange.Text = $Title
    $textRange = $slide.Shapes.Placeholders.Item(2).TextFrame.TextRange
    $textRange.Text = ($Bullets -join "`r")
    for ($i = 1; $i -le $Bullets.Count; $i++) {
        $paragraph = $textRange.Paragraphs($i)
        $paragraph.ParagraphFormat.Bullet.Visible = -1
        $paragraph.Font.Size = 24
    }
}

if (Test-Path $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

$powerPoint = $null
$presentation = $null

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1
    $presentation = $powerPoint.Presentations.Add()

    Add-TitleSlide $presentation `
        "GE 3D TEE DICOM 구조 분석 및 Spacing 추출" `
        "DICOM 표준, GE Private 구조, 트로이 목마 전략, NRRD mm 해석"

    Add-BulletsSlide $presentation "발표 목적" @(
        "DICOM의 의미와 표준 구조를 정리한다",
        "GE 3D TEE DICOM이 왜 일반 DICOM과 다르게 보이는지 설명한다",
        "왜 GE가 트로이 목마형 구조를 선택했는지 설명한다",
        "실제 spacing을 얻는 방법과 NRRD에서 mm로 해석하는 원리를 정리한다"
    )

    Add-BulletsSlide $presentation "DICOM이란 무엇인가" @(
        "Digital Imaging and Communications in Medicine의 약자다",
        "의료 영상과 환자/검사/장비 메타데이터를 함께 저장하는 국제 표준이다",
        "컴퓨터공학적으로는 Tag, VR, Length, Value가 반복되는 직렬화 바이트 스트림이다",
        "병원 시스템 간 상호운용성을 위해 최소한의 외형과 규약을 따라야 한다"
    )

    Add-BulletsSlide $presentation "왜 GE도 DICOM을 제공하는가" @(
        "병원은 GE 장비만이 아니라 PACS, 라우터, 범용 뷰어가 연결된 생태계로 동작한다",
        "완전 독자 포맷만 쓰면 저장, 전송, 조회, 기본 열람에서 큰 마찰이 생긴다",
        "따라서 외부 인터페이스는 DICOM으로 맞추는 것이 병원 도입과 운영에 유리하다",
        "대신 핵심 3D RAW와 geometry는 private 구조로 숨겨 차별화와 통제력을 유지한다"
    )

    Add-BulletsSlide $presentation "DICOM의 기본 구조" @(
        "파일 시작부는 보통 128-byte preamble과 DICM prefix를 가진다",
        "이후 Data Element가 순차적으로 이어진다",
        "각 요소는 Tag, VR, Length, Value로 구성된다",
        "파서는 모르는 태그를 만나도 Length를 보고 건너뛸 수 있다"
    )

    Add-BulletsSlide $presentation "Public Tag와 Private Tag" @(
        "Public Tag는 표준 의미가 고정되어 있어 모든 파서가 비슷하게 해석한다",
        "Private Tag는 제조사만 아는 정보를 저장하는 사설 영역이다",
        "최신 기능, RAW 데이터, 독자 알고리즘 결과는 보통 private tag에 저장된다",
        "따라서 DICOM은 표준 컨테이너이면서 동시에 벤더 확장 포맷이 되기도 한다"
    )

    Add-BulletsSlide $presentation "GE DICOM이 트로이 목마 구조를 띠는 이유" @(
        "완전 독자 포맷만으로는 병원 표준 워크플로에 자연스럽게 들어가기 어렵다",
        "병원 PACS와 DICOM 라우터를 통과하려면 표준 DICOM 외형이 필요하다",
        "범용 뷰어에서도 최소한 환자 정보와 대표 2D 이미지는 보여야 한다",
        "핵심 3D RAW 데이터와 geometry는 GE 전용 소프트웨어에서만 완전하게 쓰이게 하고 싶다",
        "즉 호환성과 벤더 통제를 동시에 만족시키는 절충 구조다"
    )

    Add-BulletsSlide $presentation "트로이 목마 구조의 실제 모습" @(
        "겉부분에는 표준 DICOM 헤더, 환자 정보, 검사 정보, 2D 이미지가 들어간다",
        "속부분에는 private creator와 private payload가 들어간다",
        "대표적으로 7FE1 그룹의 private tag에 GE 3D 데이터가 저장될 수 있다",
        "범용 뷰어는 표준 부분만 읽고 private 3D는 건너뛴다"
    )

    Add-BulletsSlide $presentation "왜 RadiAnt에서는 열리나" @(
        "RadiAnt는 표준 DICOM 파서를 사용해 아는 태그는 읽고 모르는 태그는 건너뛴다",
        "따라서 표준 2D 이미지와 일반 메타데이터는 정상 표시할 수 있다",
        "하지만 GE private payload 내부의 3D RAW 구조는 해석하지 못할 수 있다",
        "즉 일부는 보이지만 완전한 3D 재구성은 어려운 경우가 많다"
    )

    Add-BulletsSlide $presentation "GE 3D TEE 데이터의 실제 위치" @(
        "GE 계열 파일에서는 GEMS_Ultrasound_MovieGroup_001 또는 KRETZ_US가 단서가 된다",
        "7FE1,0010 또는 7FE1,0011은 private creator 역할을 할 수 있다",
        "7FE1,1001 또는 7FE1,1101은 대용량 3D payload일 가능성이 높다",
        "이 payload 내부에는 다시 GE 또는 Kretz 고유 바이너리 포맷이 들어갈 수 있다"
    )

    Add-BulletsSlide $presentation "Spacing이란 무엇인가" @(
        "spacing은 인덱스 한 칸이 현실에서 얼마인지 나타내는 값이다",
        "Cartesian volume에서는 보통 x, y, z 각 축의 voxel 간 거리(mm)를 뜻한다",
        "이 값이 있어야 길이, 면적, 부피를 실제 물리 단위로 계산할 수 있다",
        "spacing이 없으면 렌더링은 가능해도 정량 측정은 신뢰하기 어렵다"
    )

    Add-BulletsSlide $presentation "초음파 RAW에서 spacing이 더 어려운 이유" @(
        "원본 3D 초음파는 바로 x, y, z voxel 격자가 아니다",
        "보통 depth r, azimuth theta, elevation phi 축으로 저장된다",
        "따라서 원본 spacing은 delta r(mm), delta theta(degree), delta phi(degree) 조합일 수 있다",
        "이 geometry를 scan conversion을 통해 Cartesian volume으로 바꿔야 한다"
    )

    Add-BulletsSlide $presentation "Spacing을 얻는 현실적인 방법" @(
        "첫째, 표준 태그에서 Ultrasound Region과 Physical Delta를 확인한다",
        "둘째, 3D Slicer와 SlicerHeart로 파일을 로드해 spacing을 읽는다",
        "셋째, 필요하면 private payload를 직접 추출해 GE/Kretz 내부 포맷을 파싱한다",
        "실무에서는 Slicer 기반 확인이 가장 빠르고 재현성도 높다"
    )

    Add-BulletsSlide $presentation "SlicerHeart 관점의 핵심 원리" @(
        "Python plugin은 GE/Kretz 파일인지 식별하고 private payload 위치를 찾는다",
        "loadKretzUS는 payload 시작 offset을 C++ reader에 넘긴다",
        "C++ reader는 내부 바이너리를 읽어 volume과 geometry를 복원한다",
        "따라서 Slicer에서 길이 측정이 가능하면 geometry 해석이 성공한 것이다"
    )

    Add-BulletsSlide $presentation "NRRD에서 voxel 간 거리가 mm가 되는 원리" @(
        "scan conversion 이후 NRRD는 보통 Cartesian 3D volume이다",
        "각 축 spacing이 x, y, z 방향 voxel 1칸당 실제 거리(mm)를 뜻한다",
        "두 점의 index 차이에 spacing을 곱하면 실제 길이를 계산할 수 있다",
        "distance = sqrt((di*sx)^2 + (dj*sy)^2 + (dk*sz)^2)"
    )

    Add-BulletsSlide $presentation "예시" @(
        "spacing이 0.5, 0.5, 0.8 mm라고 가정한다",
        "index 차이가 10, 4, 3 voxel이면",
        "실제 거리는 sqrt((10x0.5)^2 + (4x0.5)^2 + (3x0.8)^2)다",
        "계산 결과는 약 5.90 mm가 된다"
    )

    Add-BulletsSlide $presentation "실무 권장 절차" @(
        "DICOM 표준 태그와 private creator 존재 여부를 먼저 확인한다",
        "3D Slicer와 SlicerHeart로 로딩해 volume과 spacing을 점검한다",
        "필요하면 NRRD로 export해 후처리와 측정을 진행한다",
        "정밀 연구가 필요하면 private payload를 직접 파싱해 원본 geometry를 검증한다"
    )

    Add-BulletsSlide $presentation "결론" @(
        "GE 3D TEE DICOM은 표준 외피와 private 핵심 payload가 공존하는 하이브리드 구조다",
        "이 트로이 목마 구조는 PACS 호환성과 벤더 고유 기술 보호를 동시에 만족시킨다",
        "spacing 확보는 표준 태그 확인, Slicer 활용, private 파싱의 세 단계로 접근할 수 있다",
        "NRRD spacing은 scan conversion 이후 실제 voxel 간 mm 거리 해석의 핵심이다"
    )

    $presentation.SaveAs($OutputPath)
}
finally {
    if ($presentation) { $presentation.Close() }
    if ($powerPoint) { $powerPoint.Quit() }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

Write-Output "Created: $OutputPath"
