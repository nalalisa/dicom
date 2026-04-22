# Gemini CLI 실전 사용 가이드
## C++ Visual Studio SLN 대규모 엔진 팀 개발 기준

---

## 목차
1. [설치 및 초기 세팅](#1-설치-및-초기-세팅)
2. [SLN 프로젝트 구조 이해](#2-sln-프로젝트-구조-이해)
3. [GEMINI.md 계층 설계](#3-geminimd-계층-설계)
4. [컨텍스트 관리 전략](#4-컨텍스트-관리-전략)
5. [실전 작업 패턴](#5-실전-작업-패턴)
6. [팀 협업 & Git 운영](#6-팀-협업--git-운영)
7. [자주 쓰는 프롬프트 모음](#7-자주-쓰는-프롬프트-모음)

---

## 1. 설치 및 초기 세팅

```bash
# 설치
npm install -g @google/gemini-cli

# 로그인
gemini auth login

# 버전 확인
gemini --version

# 프로젝트 루트에서 실행 (sln 파일 있는 위치)
cd C:/Projects/MyEngine
gemini
```

> **핵심 원칙**: Gemini CLI는 실행한 폴더를 기준으로 파일을 탐색한다.
> 항상 `.sln` 파일이 있는 **솔루션 루트**에서 실행할 것.

---

## 2. SLN 프로젝트 구조 이해

### SLN vs vcxproj 역할 구분

| 구분 | 파일 | 역할 | 빌드 결과 |
|------|------|------|-----------|
| Solution | `.sln` | 프로젝트 묶음 컨테이너, 의존관계 정의 | 없음 |
| Project | `.vcxproj` | 실제 빌드 단위, 파일 목록/컴파일 옵션 | `.lib` / `.dll` / `.exe` |
| Filter | `.vcxproj.filters` | VS 탐색기 표시용 폴더 구조 | 없음 |

### 일반적인 엔진 솔루션 구조

```
MyEngine.sln
├── Engine/
│   ├── Engine.vcxproj          → Engine.lib   (코어, ECS, 이벤트)
│   └── src/
├── Renderer/
│   ├── Renderer.vcxproj        → Renderer.lib (Vulkan/DX12 추상화)
│   └── src/
├── Editor/
│   ├── Editor.vcxproj          → Editor.exe   (ImGui 에디터)
│   └── src/
├── Game/
│   ├── Game.vcxproj            → Game.exe     (게임 로직)
│   └── src/
└── Tests/
    ├── Tests.vcxproj           → Tests.exe    (단위 테스트)
    └── src/
```

### 프로젝트 간 의존관계

```
Game.exe
  └── Engine.lib
        └── Renderer.lib

Editor.exe
  └── Engine.lib
  └── Renderer.lib
```

### vcxproj에서 파일 목록 추출 (Gemini에 넘기기 전 전처리)

```bash
# 특정 프로젝트의 소스 파일 목록 확인
grep -oP '(?<=<ClCompile Include=")[^"]+' Renderer/Renderer.vcxproj

# 헤더 파일 목록 확인
grep -oP '(?<=<ClInclude Include=")[^"]+' Renderer/Renderer.vcxproj
```

---

## 3. GEMINI.md 계층 설계

### 폴더 구조

```
MyEngine/
├── GEMINI.md                   ← 전체 개요 (git 관리 여부는 팀 결정)
├── .gemini/
│   └── context.md              ← 팀 공용 규약 (git에 올림)
├── Engine/
│   └── GEMINI.md               ← Engine 프로젝트 전용
├── Renderer/
│   └── GEMINI.md               ← Renderer 프로젝트 전용
└── Editor/
    └── GEMINI.md               ← Editor 프로젝트 전용
```

> 해당 프로젝트 폴더에서 gemini 실행 시 가장 가까운 GEMINI.md부터 읽힌다.
> 작업 범위를 자동으로 좁혀주는 효과.

---

### 루트 GEMINI.md 템플릿

```markdown
# GEMINI.md

## 프로젝트 개요
자체 제작 C++ 게임엔진
- 언어: C++20
- 빌드: Visual Studio 2022, x64
- 렌더링 백엔드: Vulkan

## 솔루션 구조
| 프로젝트      | 경로                        | 출력          | 역할              |
|-------------|---------------------------|-------------|-----------------|
| Engine      | Engine/Engine.vcxproj      | Engine.lib  | 코어, ECS, 이벤트  |
| Renderer    | Renderer/Renderer.vcxproj  | Renderer.lib| Vulkan 렌더링     |
| Editor      | Editor/Editor.vcxproj      | Editor.exe  | ImGui 에디터      |
| Game        | Game/Game.vcxproj          | Game.exe    | 게임 로직          |

## 의존관계
Game, Editor → Engine → Renderer

## 팀 코딩 규약
- 멤버변수: m_ prefix (예: m_device, m_commandPool)
- 포인터: raw pointer 금지, unique_ptr / shared_ptr 사용
- 에러처리: Result<T, Error> 반환, 예외(throw) 금지
- 네이밍: 클래스 PascalCase / 함수 camelCase / 상수 UPPER_SNAKE_CASE
- 주석: 함수 위에 Doxygen 스타일 (///)

## Git 브랜치 전략
- main        : 릴리즈 전용 (직접 push 금지)
- develop     : 통합 브랜치
- feature/*   : 기능 개발   (예: feature/pbr-material)
- fix/*       : 버그 수정   (예: fix/barrier-crash)
- refactor/*  : 리팩토링   (예: refactor/ecs-pool)

## 커밋 컨벤션
feat:     새 기능
fix:      버그 수정
refactor: 구조 개선 (기능 변화 없음)
perf:     성능 최적화
docs:     문서 수정
test:     테스트 추가/수정
```

---

### 모듈별 GEMINI.md 템플릿 (예: Renderer)

```markdown
# Renderer/GEMINI.md

## 이 프로젝트의 역할
Vulkan 기반 렌더링 백엔드. RenderGraph 패턴 사용.

## 핵심 클래스
- RenderGraph   : 렌더패스 등록, barrier 자동 처리, Execute 관리
- VulkanDevice  : 물리/논리 디바이스, 큐 패밀리 추상화
- RenderPass    : 개별 패스 (Shadow, GBuffer, Lighting 등)
- Pipeline      : PSO 캐싱, 쉐이더 바인딩
- Material      : 쉐이더 파라미터, 텍스처 바인딩

## 주의사항
- Execute() 호출 전 반드시 barrier 상태 확인
- Pipeline은 싱글톤 캐시 사용 (PipelineCache::Get())
- Swapchain resize 시 모든 framebuffer 재생성 필요

## 외부 의존
- Engine.lib (ApplicationBase, Logger)
- vulkan-1.lib, VulkanMemoryAllocator
```

---

## 4. 컨텍스트 관리 전략

### 세션 시작 루틴 (매번 습관화)

```
지금 [feature/pbr-material] 브랜치에서 작업 중이야.
오늘 목표: Material 클래스에 PBR 파라미터 추가하고 Shader 연결.
GEMINI.md 읽고 현재 컨텍스트 요약해줘.
```

### 컨텍스트가 잘릴 것 같을 때

```
지금까지 논의한 내용과 결정사항 요약해줘.
다음 세션에서 이어받을 수 있게 정리해줘.
```

→ 출력 결과를 복사해서 다음 세션 첫 프롬프트에 붙여넣기.

### 작업 범위별 실행 위치

```bash
# 엔진 전체 작업
cd C:/Projects/MyEngine
gemini

# Renderer 집중 작업
cd C:/Projects/MyEngine/Renderer
gemini

# 특정 모듈 파일만 열고 시작
cd C:/Projects/MyEngine
gemini --context Renderer/src/RenderGraph.h Renderer/src/RenderGraph.cpp
```

### 컨텍스트 절약 팁

| 상황 | 방법 |
|------|------|
| 구조 파악 | 헤더(.h)만 먼저 읽힘 |
| 구현 작업 | 해당 .cpp만 추가 |
| 크로스 프로젝트 | 경계 인터페이스 헤더만 |
| 전체 파악 | 모듈별로 세션 나눠서 진행 |

---

## 5. 실전 작업 패턴

### 새 기능 개발 시작

```
feature/pbr-material 브랜치 시작할 거야.

목표: Material에 PBR 파라미터(albedo, metallic, roughness, ao) 추가
영향 범위: Material, Shader, Pipeline, RenderPass

영향받는 파일 목록 뽑아주고 작업 순서 잡아줘.
```

---

### 버그 수정

```
RenderGraph::Execute()에서 image barrier가 중복 삽입되는 것 같아.
증상: 동일 리소스에 barrier가 2번 들어가서 validation layer 경고 발생.

원인 찾고 수정해줘.
[Renderer/src/RenderGraph.cpp 열어둔 상태]
```

---

### 기존 코드 스타일 파악 (처음 합류하거나 모르는 모듈)

```
RenderGraph.cpp 보고 이 프로젝트의 코딩 패턴 분석해줘.
- 에러 처리 방식
- 메모리 관리 패턴
- 네이밍 규칙
- 주석 스타일
GEMINI.md에 추가할 규약 형태로 정리해줘.
```

---

### 크로스 프로젝트 작업

```
Engine에서 Renderer로 RenderCommand를 전달하는 구조 개선하고 싶어.
현재 인터페이스 분석하고 개선안 제안해줘.
[Engine/src/RenderCommand.h, Renderer/src/RenderGraph.h 열어둔 상태]
```

---

### 리팩토링

```
ComponentPool을 dense array 방식으로 리팩토링해줘.
조건:
- 기존 public 인터페이스 유지
- iteration 성능 개선이 목적
- RAII 유지
[Engine/src/ecs/ComponentPool.h, ComponentPool.cpp 열어둔 상태]
```

---

### 크래시 디버깅

```
이 스택트레이스로 크래시 원인 분석해줘.

#0  ComponentPool<TransformComponent>::Get()
#1  RenderSystem::Update()
#2  World::Tick()

원인과 수정 방법 알려줘.
[관련 파일 열어둔 상태]
```

---

### 테스트 코드 생성

```
ComponentPool 단위테스트 작성해줘.
- Google Test 기준
- edge case 포함 (빈 pool, 최대 용량, 삭제 후 재삽입)
[Engine/src/ecs/ComponentPool.h 열어둔 상태]
```

---

## 6. 팀 협업 & Git 운영

### GEMINI.md git 처리 방법

**옵션 A: 개인용 (gitignore 처리)**
```bash
# .gitignore에 추가
echo "GEMINI.md" >> .gitignore
echo "**/GEMINI.md" >> .gitignore
```
각자 자기 스타일로 작성. 팀원 영향 없음.

**옵션 B: 팀 공용 규약만 git에 올리기 (권장)**
```bash
# .gemini/context.md 는 git에 올림
git add .gemini/context.md

# 개인 GEMINI.md는 gitignore
echo "GEMINI.md" >> .gitignore
echo "**/GEMINI.md" >> .gitignore
```

```markdown
# 개인 GEMINI.md 예시
<!-- 팀 공용 규약 참조 -->
ref: .gemini/context.md

## 내 담당 모듈
Renderer 담당. RenderGraph, VulkanDevice 위주 작업.

## 내 로컬 설정
Debug 빌드 기준으로 작업 중.
```

---

### vcxproj 충돌 처리 (팀 작업 시 가장 흔한 문제)

여러 명이 동시에 파일을 추가하면 vcxproj XML이 충돌난다.

```bash
# 충돌 발생 시
git diff Renderer/Renderer.vcxproj
```

해결 방법: 양쪽 `<ClCompile>`, `<ClInclude>` 항목을 **모두 살린다**.
GUID 충돌은 한쪽 것을 버린다.

```bash
# GEMINI.md merge 전략 설정 (충돌 방지)
echo "GEMINI.md merge=ours" >> .gitattributes
echo "**/GEMINI.md merge=ours" >> .gitattributes
git add .gitattributes
```

---

### PR 전 체크

```
이 변경사항 PR 올리기 전에 검토해줘.

체크 항목:
1. 팀 코딩 규약 위반 여부
2. 사이드이펙트 가능성
3. 누락된 엣지케이스
4. 메모리 누수 가능성

변경 파일: [파일들 열어둔 상태]
```

---

### 커밋 메시지 생성

```
방금 작업한 내용으로 커밋 메시지 써줘.
형식: [type]: 한줄 요약 (영문 또는 한글)
      (빈줄)
      상세 설명 (무엇을, 왜 변경했는지)
```

---

### git 올릴 때 주의사항

```bash
# AI가 생성한 코드는 반드시 diff 확인 후 커밋
git diff src/

# 의도치 않은 파일 변경 확인
git status

# GEMINI.md에 민감 정보 포함 여부 확인
# (API 키, 내부 IP, 비밀번호 등 절대 금지)
```

---

## 7. 자주 쓰는 프롬프트 모음

### 구조 파악

```
이 프로젝트의 [모듈명] 구조를 분석해줘.
클래스 관계, 데이터 흐름, 외부 의존성 위주로 설명해줘.
```

### 함수 흐름 추적

```
[함수명] 호출부터 반환까지 전체 흐름 추적해줘.
중요한 상태 변화와 side effect 포함해서.
```

### 성능 분석

```
[함수명 / 시스템명] 성능 병목 분석해줘.
핫패스 기준으로 개선 우선순위 정해줘.
```

### 인터페이스 설계

```
[기능] 추가할 때 인터페이스 어떻게 설계하면 좋을지 제안해줘.
기존 코딩 스타일과 RAII 원칙 지켜줘.
```

### 코드 리뷰

```
이 코드 리뷰해줘.
성능 / 메모리 / 스레드 안전성 / 코딩 규약 위반 위주로 봐줘.
```

### 문서화

```
이 클래스/함수에 Doxygen 주석 추가해줘.
팀 컨벤션: /// 스타일, @brief @param @return 포함.
```

---

## 작업 흐름 한눈에 보기

```
솔루션 루트에서 gemini 실행
        ↓
세션 초기화 프롬프트
(브랜치명 + 오늘 목표 + 컨텍스트 요약 요청)
        ↓
헤더로 구조 파악 → cpp로 구현 진입
        ↓
작업 진행 (버그수정 / 기능추가 / 리팩토링)
        ↓
컨텍스트 길어지면 중간 요약 저장
        ↓
PR 전 규약 체크
        ↓
커밋 메시지 생성 → git push
```

---

*이 가이드는 팀 규약과 엔진 구조에 맞게 지속적으로 업데이트할 것.*