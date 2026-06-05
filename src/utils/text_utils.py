import re
import ipaddress
from urllib.parse import urlparse
import requests

def _decode_text_bytes(raw: bytes) -> str:
    """バイト列を適切なエンコーディングでデコードする。
    chardetで自動検出し、失敗時は日本語主要エンコーディングを順に試みる。"""
    # 1. chardetで自動検出
    try:
        import chardet
        detected = chardet.detect(raw)
        enc = detected.get("encoding")
        conf = detected.get("confidence", 0)
        if enc and conf >= 0.7:
            return raw.decode(enc)
    except Exception:
        pass
    # 2. 日本語主要エンコーディングを順に試みる
    for enc in ("utf-8", "utf-8-sig", "cp932", "shift_jis", "euc-jp", "iso-2022-jp"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # 3. 最終フォールバック（文字化け最小化）
    return raw.decode("utf-8", errors="replace")

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """テキストをBGE-M3のトークン上限に収まるよう文字数でチャンク分割する。
    chunk_size=400文字は512トークン上限に対して安全マージンを持つ目安。
    改行がない長い段落も文字数で強制分割する。"""
    if chunk_size <= 0:
        return [text] if text else []
    if overlap < 0:
        overlap = 0
    # overlap が大きすぎると末尾で極小チャンクが大量に発生するため制限する
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        # 改行や句点で自然な切れ目を探す（最大chunk_size文字の範囲内）
        if end < length:
            for sep in ('\n', '。', '．', '. ', '、', '，'):
                pos = text.rfind(sep, start, end)
                if pos != -1 and pos > start + overlap:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk and (not chunks or chunk != chunks[-1]):
            chunks.append(chunk)
        # 末尾に到達したら終了
        if end >= length:
            break
        # 次の開始位置はオーバーラップ分だけ前に戻す
        next_start = end - overlap
        if next_start <= start:
            next_start = start + max(1, chunk_size - overlap)
        start = min(next_start, length)

    # 末尾の極小チャンクはノイズになりやすいため削除
    min_tail_chars = max(20, overlap // 2)
    if len(chunks) >= 2 and len(chunks[-1]) < min_tail_chars:
        chunks.pop()
    return chunks if chunks else [text[:chunk_size]]

def _detect_audio_ext(audio_bytes: bytes) -> str:
    """マジックバイトから音声フォーマットを判定して適切な拡張子を返す"""
    if audio_bytes[:4] == b"RIFF":
        return ".wav"
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if audio_bytes[:3] == b"ID3" or audio_bytes[:2] == b"\xff\xfb":
        return ".mp3"
    if audio_bytes[:4] == b"fLaC":
        return ".flac"
    # WebM (1a 45 df a3) などその他はwebmとして扱う
    return ".webm"

def _is_safe_url(url: str) -> bool:
    """SSRF対策: プライベートIPアドレス・ローカルホスト・file/ftpスキームを拒否する。"""
    try:
        parsed = urlparse(url)
        # http/https のみ許可
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname or ""
        # localhost 系を拒否
        if hostname in ("localhost", ""):
            return False
        # IPアドレスの場合はプライベート・ループバック・リンクローカルを拒否
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        except ValueError:
            pass  # ホスト名（ドメイン）の場合はスキップ
        return True
    except Exception:
        return False

def _fetch_url_text(url: str, max_chars: int = 4000) -> str:
    """URLにアクセスしてページ本文テキストを返す。失敗時はエラー文字列を返す。"""
    if not _is_safe_url(url):
        return "[セキュリティ上の理由によりこのURLは取得できません]"
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        # script/style/nav/header/footer を除去
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        # ページタイトルを取得
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else ''

        text = soup.get_text(separator="\n", strip=True)
        # 空行を圧縮
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)
        return result[:max_chars] + ("…（以下省略）" if len(result) > max_chars else "")
    except Exception as e:
        return f"[URLの取得に失敗しました: {e}]"

def _fetch_url_text_and_title(url: str, max_chars: int = 4000) -> tuple:
    """URLにアクセスしてページ本文とタイトルを返す。失敗時はエラー文字列を返す。
    戻り値: (text, title)"""
    if not _is_safe_url(url):
        return ("[セキュリティ上の理由によりこのURLは取得できません]", "")
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else ''
        text = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        result = "\n".join(lines)
        return (result[:max_chars] + ("…（以下省略）" if len(result) > max_chars else ""), page_title)
    except Exception as e:
        return (f"[URLの取得に失敗しました: {e}]", "")

def _extract_game_score_from_url(url: str) -> dict | None:
    """指定URLから試合の最終スコアを抽出する。成功時は辞書を返す。
    返り値例: {'teams': [{'name':'北海道日本ハムファイターズ','score':5}, {'name':'埼玉西武','score':4}], 'url': url}
    """
    try:
        if not _is_safe_url(url):
            return None
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Yahoo のスコアテーブル検出 (class 'bb-gameScoreTable') を優先
        table = soup.find('table', class_='bb-gameScoreTable')
        if table:
            # ヘッダ行から「計」の列Indexを探す
            header = None
            for tr in table.find_all('tr'):
                ths = [th.get_text(strip=True) for th in tr.find_all('th')]
                if '計' in ths:
                    header = ths
                    break
            if header:
                idx = header.index('計')
                teams = []
                for tr in table.find_all('tr'):
                    cells = [c.get_text(strip=True) for c in tr.find_all(['th','td'])]
                    if len(cells) > idx:
                        name = cells[0]
                        try:
                            score = int(cells[idx])
                        except Exception:
                            continue
                        teams.append({'name': name, 'score': score})
                if teams:
                    return {'teams': teams, 'url': url}

        # 汎用的なボックススコア検出: '計'と'安'が近くにある構造を探索
        text = soup.get_text('\n')
        if '計' in text and '安' in text:
            # 簡易パース: 行単位で '計' を含む行を探し、その前後の行でチーム名と数値を探す
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i,l in enumerate(lines):
                if l.startswith('計') or l == '計':
                    # 前後にチーム行があると仮定
                    candidates = []
                    for j in range(max(0,i-4), min(len(lines), i+6)):
                        candidates.append(lines[j])
                    # 数字を含む行を抽出
                    parsed = []
                    for c in candidates:
                        m = re.findall(r"(\D{1,30}?)(\d+)\s*$", c)
                        if m:
                            name = m[0][0].strip()
                            score = int(m[0][1])
                            parsed.append({'name': name, 'score': score})
                    if parsed:
                        return {'teams': parsed, 'url': url}

    except Exception:
        return None
    return None

def _extract_urls(text: str) -> list[str]:
    """テキスト中のURLを抽出する。"""
    pattern = r'https?://[^\s\u3000\u300d\u300f\uff09\u300b\u3011\uff3d\uff5d\"\'>\]）】]+'
    return re.findall(pattern, text)

def _parse_chapter_no(text: str) -> int | None:
    s = str(text or "")
    word_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }
    patterns = [
        r"第\s*([0-9０-９]{1,2})\s*章",
        r"\bchapter\s*([0-9]{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b",
        r"\bch(?:apter)?[\s._-]*0*([0-9]{1,2})\b",
        r"(?:^|\s)([0-9０-９]{1,2})\s*[\.:：]\s*[A-Za-z一-龠ァ-ヶ々]",
    ]
    for p in patterns:
        m = re.search(p, s, re.IGNORECASE)
        if not m:
            continue
        found = m.group(1)
        if not found:
            continue
        try:
            lowered = found.lower()
            if lowered in word_map:
                return word_map[lowered]
            return int(str(found).translate(str.maketrans("０１２３４５６７８９", "0123456789")))
        except Exception:
            continue
    return None

def _extract_page_number(text: str) -> int | None:
    """テキストからページ番号を抽出する（例：「425ページの翻訳を」→ 425）"""
    # 「425ページ」「425p」「p425」などのパターンを検出
    match = re.search(r'(?:第\s*)?(\d{1,4})\s*(?:ページ|p|P|pag\.?)?|p(?:ag\.?)?(\d{1,4})', text)
    if match:
        try:
            page_no = int(match.group(1) or match.group(2))
            if 1 <= page_no <= 10000:  # 妥当な範囲
                return page_no
        except (ValueError, TypeError):
            pass
    return None
