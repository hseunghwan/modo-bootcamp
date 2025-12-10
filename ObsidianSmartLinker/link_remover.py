import os
import re
from glob import glob
# from tqdm import tqdm

# ==========================================
# 설정 (Configuration)
# ==========================================
TARGET_DIRS = [
    "gemini-chats",
    "gpt-chats",
    "prj-data"
]
LINK_HEADER = "## 🔗 연관 문서"  # 제거할 헤더 제목
EXCLUDE_DIRS = [".git", ".obsidian", ".trash"]

class ObsidianLinkRemover:
    def __init__(self, base_path):
        self.base_path = base_path

    def get_files(self):
        """대상 디렉토리의 모든 마크다운 파일을 수집합니다."""
        files = []
        for d in TARGET_DIRS:
            path = os.path.join(self.base_path, d)
            if not os.path.exists(path):
                print(f"Warning: Directory not found: {path}")
                continue
            
            for root, _, filenames in os.walk(path):
                if any(exclude in root for exclude in EXCLUDE_DIRS):
                    continue
                    
                for filename in filenames:
                    if filename.endswith(".md"):
                        full_path = os.path.join(root, filename)
                        files.append(full_path)
        return files

    def run(self):
        print("📂 문서를 수집 중입니다...")
        files = self.get_files()
        if not files:
            print("처리할 파일이 없습니다.")
            return

        print(f"🔍 총 {len(files)}개 파일 검사 시작...")
        
        removed_count = 0
        
        # 헤더와 그 뒤의 내용을 찾기 위한 정규식 패턴
        # 헤더부터 시작해서 (다음 # 헤더) 혹은 (파일 끝)까지 매칭
        pattern = re.escape(LINK_HEADER) + r".*?(\n# |$)"

        for fpath in files: # tqdm removed
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if LINK_HEADER in content:
                    # 정규식으로 헤더 섹션 제거
                    # 보통 파일 맨 끝에 위치하므로 파일 끝까지 제거하는 것이 깔끔할 수 있으나,
                    # 안전을 위해 smart_linker.py와 동일한 로직으로 제거
                    
                    # 1. 단순 split 방식 (가장 안전하고 확실하게 헤더 이후를 날리고 싶다면)
                    # new_content = content.split(LINK_HEADER)[0].rstrip() + "\n"
                    
                    # 2. 정규식 방식 (중간에 끼어있는 경우 대비)
                    # 여기서는 smart_linker가 보통 맨 뒤에 추가하므로, 
                    # 만약 중간에 있다면 다음 헤더 전까지만 지우고, 맨 뒤라면 끝까지 지움.
                    
                    # LINK_HEADER로 시작하는 부분을 찾음
                    if re.search(pattern, content, flags=re.DOTALL):
                        new_content = re.sub(pattern, r"\1", content, flags=re.DOTALL)
                        
                        # 만약 치환 후 불필요한 공백이 끝에 남았다면 정리
                        new_content = new_content.rstrip() + "\n"
                        
                        with open(fpath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        removed_count += 1
                        
            except Exception as e:
                print(f"Error processing {fpath}: {e}")

        print(f"✅ 완료! 총 {removed_count}개의 문서에서 링크 섹션이 제거되었습니다.")

if __name__ == "__main__":
    base_dir = os.getcwd()
    remover = ObsidianLinkRemover(base_dir)
    remover.run()
