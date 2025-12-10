import os
import re
import numpy as np
from glob import glob
from tqdm import tqdm
from kiwipiepy import Kiwi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# ==========================================
# 설정 (Configuration)
# ==========================================
TARGET_DIRS = [
    "gemini-chats",
    "gpt-chats",
    "prj-data"
]
LINK_HEADER = "## 🔗 연관 문서"  # 문서에 삽입될 헤더 제목
SIMILARITY_THRESHOLD = 0.15      # 유사도 임계값
MAX_LINKS = 8                    # 최대 링크 개수
TITLE_WEIGHT = 3                 # 제목 가중치 (본문에 제목을 N번 반복하는 효과)
SAME_FOLDER_WEIGHT = 1.2         # 같은 폴더 내 문서 가중치
EXCLUDE_DIRS = [".git", ".obsidian", ".trash"]

# ==========================================
# 클래스 정의
# ==========================================

class ObsidianSmartLinker:
    def __init__(self, base_path):
        self.base_path = base_path
        print("🧠 형태소 분석기(Kiwi) 로딩 중...")
        self.kiwi = Kiwi()
        # 불용어 추가 (필요시 확장)
        self.stop_words = {'것', '수', '등', '이', '그', '저', '때', '를', '가', '은', '는', '에', '의', '와', '과', '도', '으로', '로', '자', '위'}
        
    def get_files(self):
        """대상 디렉토리의 모든 마크다운 파일을 수집합니다."""
        files = []
        for d in TARGET_DIRS:
            path = os.path.join(self.base_path, d)
            if not os.path.exists(path):
                print(f"Warning: Directory not found: {path}")
                continue
            
            # 재귀적으로 md 파일 검색
            for root, _, filenames in os.walk(path):
                # 제외 폴더 체크
                if any(exclude in root for exclude in EXCLUDE_DIRS):
                    continue
                    
                for filename in filenames:
                    if filename.endswith(".md"):
                        full_path = os.path.join(root, filename)
                        files.append(full_path)
        return files

    def preprocess_text(self, text):
        """
        기존 연관 문서 섹션을 제거하고 텍스트를 정제합니다.
        """
        # 기존 링크 섹션 제거 (재귀 참조 방지)
        # 헤더가 나오면 그 뒤를 다 자르거나, 다음 헤더 전까지 자름. 여기선 간단히 헤더 뒤를 날림(일반적으로 맨 뒤에 위치하므로)
        # 하지만 중간에 있을 수도 있으니 정규식 사용
        pattern = re.escape(LINK_HEADER) + r".*?(\n# |$)"
        # LINK_HEADER 부터 파일 끝까지 제거하는 로직이 안전함 (보통 부록처럼 맨 뒤에 두므로)
        split_text = text.split(LINK_HEADER)
        return split_text[0]

    def extract_nouns(self, text):
        """
        Kiwi를 사용하여 명사만 추출합니다.
        """
        try:
            tokens = self.kiwi.tokenize(text)
            # NNG(일반명사), NNP(고유명사), NR(수사), SL(알파벳-영어단어)
            nouns = [t.form for t in tokens if (t.tag.startswith('NN') or t.tag == 'SL') and len(t.form) > 1]
            return [n for n in nouns if n not in self.stop_words]
        except Exception as e:
            print(f"Tokenization Error: {e}")
            return []

    def tokenizer_wrapper(self, text):
        return self.extract_nouns(text)

    def run(self):
        print("📂 문서를 수집 중입니다...")
        files = self.get_files()
        if not files:
            print("분석할 파일이 없습니다. 경로를 확인해주세요.")
            return

        print(f"🔍 총 {len(files)}개 파일 분석 시작...")

        documents = []
        filenames = []
        file_dirs = []

        # 1. 데이터 로드 및 전처리
        for fpath in tqdm(files, desc="Text Loading"):
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                filename = os.path.splitext(os.path.basename(fpath))[0]
                clean_content = self.preprocess_text(content)
                
                # 가중치 로직 1: 제목 키워드 가중치 (제목을 내용에 반복 추가)
                # 제목에서 특수문자 제거 후 내용에 추가
                clean_title = re.sub(r'[^\w\s]', ' ', filename)
                weighted_content = (f"{clean_title} " * TITLE_WEIGHT) + " " + clean_content
                
                documents.append(weighted_content)
                filenames.append(filename)
                file_dirs.append(os.path.dirname(fpath))
            except Exception as e:
                print(f"Error reading {fpath}: {e}")

        if not documents:
            return

        # 2. TF-IDF 벡터화
        print("🧮 TF-IDF 행렬 생성 및 명사 추출 중 (Kiwi)...")
        vectorizer = TfidfVectorizer(
            tokenizer=self.tokenizer_wrapper,
            min_df=1,              # 문서가 적으므로 1개 문서에만 나와도 포함
            max_df=0.95,           # 95% 이상 문서에 등장하면 제외
            token_pattern=None     # 커스텀 토크나이저 사용 시 None
        )
        try:
            tfidf_matrix = vectorizer.fit_transform(documents)
            feature_names = np.array(vectorizer.get_feature_names_out())
        except ValueError as e:
            print(f"TF-IDF Error: {e}")
            return

        # 3. 코사인 유사도 계산
        print("⚡ 코사인 유사도 계산 중...")
        cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

        # 4. 결과 처리 및 파일 업데이트
        print("📝 문서 업데이트 중...")
        updated_count = 0
        
        for idx, fpath in enumerate(tqdm(files, desc="Updating Files")):
            sim_scores = list(enumerate(cosine_sim[idx]))
            
            # 가중치 로직 2: 같은 폴더 내 문서 가중치 적용
            adjusted_scores = []
            current_dir = file_dirs[idx]
            
            for i, score in sim_scores:
                if i == idx: continue # 자기 자신 제외
                
                final_score = score
                if file_dirs[i] == current_dir:
                    final_score *= SAME_FOLDER_WEIGHT
                
                # 유사도가 1.0을 넘지 않도록 클램핑 (가중치 때문에 넘을 수 있음)
                final_score = min(final_score, 1.0)

                if final_score >= SIMILARITY_THRESHOLD:
                    adjusted_scores.append((i, final_score))

            # 점수순 정렬 및 상위 N개 추출
            adjusted_scores = sorted(adjusted_scores, key=lambda x: x[1], reverse=True)
            top_indices = adjusted_scores[:MAX_LINKS]

            # 링크 텍스트 생성
            if not top_indices:
                # 연관 문서가 없으면 섹션 자체를 생성하지 않거나 제거할 수도 있음.
                # 여기서는 빈 섹션은 만들지 않음
                continue

            link_lines = [f"\n{LINK_HEADER}\n"]
            
            for i, score in top_indices:
                target_filename = filenames[i]
                
                # 키워드 추출: 두 문서의 벡터 곱이 큰 상위 단어
                vec_a = tfidf_matrix[idx]
                vec_b = tfidf_matrix[i]
                common_vector = vec_a.multiply(vec_b)
                
                if common_vector.nnz > 0:
                    # 데이터 값 기준으로 정렬하여 상위 인덱스 추출
                    # common_vector.data는 0이 아닌 값들만 있음
                    # argsort는 오름차순이므로 뒤에서부터 자름
                    sorted_indices = np.argsort(common_vector.data)[-3:][::-1]
                    real_indices = common_vector.indices[sorted_indices]
                    keywords = feature_names[real_indices]
                    kw_str = ", ".join(keywords)
                else:
                    kw_str = "매칭 키워드 없음"

                link_line = f"- [[{target_filename}]] <!-- 키워드: {kw_str} / 유사도 점수: {score:.2f} -->"
                link_lines.append(link_line)

            new_link_section = "\n".join(link_lines) + "\n"

            try:
                # 원본 파일 읽기
                with open(fpath, 'r', encoding='utf-8') as f:
                    original_content = f.read()

                # 기존 섹션 교체 로직
                # 1. LINK_HEADER가 존재하면, 그 위치부터 파일 끝(혹은 다음 헤더)까지 교체
                if LINK_HEADER in original_content:
                    # 헤더부터 시작해서, (다음 # 헤더) 혹은 (파일 끝)까지 매칭
                    # 보통 연관 문서는 파일 끝에 둠.
                    pattern = re.escape(LINK_HEADER) + r".*?(?=\n# |$)"
                    new_content = re.sub(pattern, new_link_section.strip(), original_content, flags=re.DOTALL)
                else:
                    # 없으면 파일 끝에 추가 (개행 확보)
                    new_content = original_content.rstrip() + "\n" + new_link_section

                # 내용이 바뀌었을 때만 쓰기
                if new_content != original_content:
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated_count += 1
            except Exception as e:
                print(f"Error writing {fpath}: {e}")

        print(f"✅ 완료! 총 {updated_count}개의 문서가 갱신되었습니다.")

if __name__ == "__main__":
    # 현재 작업 디렉토리 기준
    base_dir = os.getcwd()
    linker = ObsidianSmartLinker(base_dir)
    linker.run()
