# Smart Linker 스크립트 매뉴얼

**작성일:** 2025-12-10
**스크립트명:** `smart_linker.py`
**목적:** Obsidian 문서 보관함 내의 마크다운 파일들을 분석하여, 내용이 유사한 문서들을 자동으로 찾아 연결(Backlink)해주는 도구

---

## 1. 개요 (Overview)

이 스크립트는 로컬 환경에서 Python의 NLP(자연어 처리) 및 머신러닝 라이브러리를 활용하여 문서 간의 유사도를 계산합니다. 외부 API(OpenAI 등)를 사용하지 않아 비용이 발생하지 않으며, 수천 개의 문서도 수 초 내에 분석할 수 있는 고성능 스크립트입니다.

### 핵심 기능
- **형태소 분석:** 한국어 형태소 분석기 `Kiwi`를 사용하여 정확한 명사(Noun)만 추출합니다.
- **고속 연산:** `scikit-learn`과 `numpy`를 활용한 TF-IDF 행렬 연산으로 $O(N^2)$ 유사도 계산을 빠르게 수행합니다.
- **가중치 로직:** 문서 제목과 동일 폴더 내 문서에 가중치를 부여하여 더 관련성 높은 결과를 제공합니다.
- **메타데이터 제공:** 단순 링크뿐만 아니라, **매칭된 핵심 키워드**와 **유사도 점수**를 주석으로 함께 표시합니다.

---

## 2. 설치 및 실행 환경 (Installation)

### 필요 라이브러리
스크립트 실행을 위해 가상환경(venv) 사용을 권장합니다.

```bash
# 가상환경 생성 (최초 1회)
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 의존성 패키지 설치
pip install numpy scikit-learn kiwipiepy tqdm
```

### 실행 방법
프로젝트 루트 디렉토리에서 아래 명령어를 실행합니다.

```bash
python smart_linker.py
```

---

## 3. 알고리즘 및 로직 (Algorithm)

### 3.1. 전처리 (Preprocessing)
1. **문서 수집:** 설정된 `TARGET_DIRS` 내의 모든 `.md` 파일을 재귀적으로 탐색합니다.
2. **섹션 제거:** 이미 생성된 `## 🔗 연관 문서` 섹션이 있다면 분석에서 제외하여 루프(Loop)를 방지합니다.
3. **가중치 주입:** 문서의 **파일명(Title)**을 본문 내용 앞에 3번 반복(`TITLE_WEIGHT`)하여 추가합니다. 이는 제목에 포함된 키워드가 본문 단어보다 중요하게 취급되도록 합니다.

### 3.2. 텍스트 마이닝 (Text Mining)
1. **토큰화 (Tokenization):** `Kiwi` 분석기를 사용하여 텍스트에서 조사, 어미 등을 제거하고 **명사(NNG, NNP, NR, SL)**만 추출합니다.
2. **벡터화 (Vectorization):** `TfidfVectorizer`를 사용하여 문서를 TF-IDF(Term Frequency - Inverse Document Frequency) 벡터로 변환합니다.
   - 너무 흔한 단어(상위 95% 등장)는 불용어 처리하여 무시합니다.

### 3.3. 유사도 계산 (Similarity Calculation)
1. **코사인 유사도:** 생성된 TF-IDF 행렬에 대해 Linear Kernel 연산을 수행하여 모든 문서 쌍 간의 코사인 유사도를 한 번에 계산합니다.
2. **후처리 가중치:**
   - **폴더 가중치:** 비교하는 두 문서가 같은 폴더에 있을 경우, 계산된 점수에 `1.2배` 가중치를 부여합니다.
   - **임계값 필터링:** 최종 점수가 `0.15` 미만인 경우 연관 문서에서 제외합니다.

### 3.4. 키워드 추출 (Keyword Extraction)
두 문서 간의 연관성을 설명하는 키워드를 추출하기 위해, 두 문서 벡터의 **Element-wise Product(요소별 곱)** 값이 가장 큰 단어 3개를 선정합니다. 즉, 두 문서 모두에서 높은 TF-IDF 값을 가지는 단어를 찾습니다.

---

## 4. 설정 변경 (Configuration)

`smart_linker.py` 파일 상단의 변수를 수정하여 동작을 제어할 수 있습니다.

| 변수명 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `TARGET_DIRS` | `["gemini-chats", "gpt-chats", "prj-data"]` | 분석 대상 폴더 목록 |
| `LINK_HEADER` | `"## 🔗 연관 문서"` | 문서 하단에 삽입될 섹션 제목 |
| `SIMILARITY_THRESHOLD` | `0.15` | 이 점수 이상일 때만 링크 생성 (0~1 사이) |
| `MAX_LINKS` | `8` | 한 문서당 표시할 최대 링크 개수 |
| `TITLE_WEIGHT` | `3` | 제목 키워드 반복 횟수 (중요도) |
| `SAME_FOLDER_WEIGHT` | `1.2` | 같은 폴더 내 문서에 부여할 가중치 배수 |

---

## 5. 결과 예시 (Output)

스크립트 실행 후, 각 마크다운 파일 하단에 다음과 같은 내용이 추가되거나 갱신됩니다.

```markdown
## 🔗 연관 문서
- [[서비스 스케일링과 퀄리티 타협 251209]] <!-- 키워드: cursor, 모드, 대화 / 유사도 점수: 0.35 -->
- [[Cursor_Pro_크레딧_소진_후_방법 251210]] <!-- 키워드: cursor, 크레딧, 소진 / 유사도 점수: 0.29 -->
- [[Cursor AI Composer1 모델 특징 251128]] <!-- 키워드: cursor, 모델, sonnet / 유사도 점수: 0.25 -->
```

---

## 6. 링크 제거 (Cleaning)

생성된 연관 문서 링크를 일괄 삭제하려면 `link_remover.py`를 사용합니다.

```bash
python link_remover.py
```

이 스크립트는 `smart_linker.py`가 생성한 `## 🔗 연관 문서` 섹션을 감지하여 해당 섹션과 그 내용을 안전하게 제거합니다.
