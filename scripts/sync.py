import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup

# --- Configuration ---
CF_HANDLE = os.getenv("CF_HANDLE", "abhisheksouw21").strip()
LC_USERNAME = os.getenv("LC_USERNAME", "").strip()
LC_SESSION = os.getenv("LEETCODE_SESSION", "").strip()
LC_CSRF = os.getenv("LEETCODE_CSRF", "").strip()

STATE_FILE = "state.json"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

# --- Helper Functions ---
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"cf_last_id": 0, "lc_processed": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '', name.replace(' ', '_'))

def get_extension(lang):
    lang = lang.lower()
    if 'c++' in lang or 'cpp' in lang: return '.cpp'
    if 'python' in lang: return '.py'
    if 'java' in lang: return '.java'
    return '.txt'

def save_code(platform, folder_name, problem_name, ext, code):
    base_dir = f"{platform}/{folder_name}"
    os.makedirs(base_dir, exist_ok=True)
    
    file_path = f"{base_dir}/{problem_name}{ext}"
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        return True
    return False

# --- Codeforces Logic ---
def fetch_cf_submissions(state):
    print("Fetching Codeforces submissions...")
    url = f"https://codeforces.com/api/user.status?handle={CF_HANDLE}&from=1&count=50"
    res = requests.get(url).json()
    
    if res['status'] != 'OK':
        print("CF API Error")
        return []

    new_subs = []
    max_id = state['cf_last_id']
    
    for sub in res['result']:
        if sub['verdict'] == 'OK' and sub['id'] > state['cf_last_id']:
            new_subs.append(sub)
            max_id = max(max_id, sub['id'])
            
    state['cf_last_id'] = max_id
    return new_subs

def scrape_cf_code(contest_id, sub_id):
    url = f"https://codeforces.com/contest/{contest_id}/submission/{sub_id}"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    code_block = soup.find('pre', id='program-source-text')
    return code_block.text if code_block else None

# --- LeetCode Logic ---
def fetch_lc_submissions(state):
    print("Fetching LeetCode submissions...")
    url = "https://leetcode.com/graphql"
    cookies = {'LEETCODE_SESSION': LC_SESSION, 'csrftoken': LC_CSRF}
    headers = {**HEADERS, 'X-CSRFToken': LC_CSRF, 'Content-Type': 'application/json'}
    
    query = {
        "query": """query recentAcSubmissions($username: String!, $limit: Int!) {
            recentAcSubmissionList(username: $username, limit: $limit) { id title titleSlug }
        }""",
        "variables": {"username": LC_USERNAME, "limit": 20}
    }
    
    res = requests.post(url, json=query, headers=headers, cookies=cookies).json()
    subs = res.get('data', {}).get('recentAcSubmissionList', [])
    
    new_subs = []
    for sub in subs:
        if sub['id'] not in state['lc_processed']:
            detail_query = {
                "query": """query submissionDetails($submissionId: Int!) {
                    submissionDetails(submissionId: $submissionId) { code lang }
                }""",
                "variables": {"submissionId": int(sub['id'])}
            }
            time.sleep(2)
            detail_res = requests.post(url, json=detail_query, headers=headers, cookies=cookies).json()
            details = detail_res.get('data', {}).get('submissionDetails', {})
            
            if details:
                sub['code'] = details.get('code')
                sub['lang'] = details.get('lang')
                new_subs.append(sub)
                state['lc_processed'].append(sub['id'])
                
    return new_subs

# --- Main Execution ---
def main():
    state = load_state()
    added_files = []

    cf_subs = fetch_cf_submissions(state)
    for sub in cf_subs:
        contest_id = str(sub['contestId'])
        prob_name = clean_filename(sub['problem']['name'])
        ext = get_extension(sub['programmingLanguage'])
        
        time.sleep(2)
        code = scrape_cf_code(contest_id, sub['id'])
        
        if code and save_code("codeforces", contest_id, prob_name, ext, code):
            added_files.append(f"codeforces/{contest_id}/{prob_name}{ext}")
            print(f"Added CF: {prob_name}")

    if LC_SESSION and LC_CSRF:
        lc_subs = fetch_lc_submissions(state)
        for sub in lc_subs:
            prob_name = clean_filename(sub['title'])
            ext = get_extension(sub['lang'])
            
            if save_code("leetcode", "solved", prob_name, ext, sub['code']):
                added_files.append(f"leetcode/solved/{prob_name}{ext}")
                print(f"Added LC: {prob_name}")

    save_state(state)
    
    if added_files and 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"commit_msg=Added solution: {', '.join([os.path.basename(p).split('.')[0] for p in added_files])}\n")

if __name__ == "__main__":
    main()