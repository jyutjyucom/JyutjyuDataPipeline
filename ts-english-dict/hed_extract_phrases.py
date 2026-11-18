import argparse
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup


def _norm_spaces(s: str) -> str:
    # 把各种空白（包括 NBSP 和换行）压成普通空格
    s = s.replace("\u00A0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _resolve_default_html() -> Path:
    """
    找到当前项目里的 HED 主 HTML 文件（带 NBSP 的真实文件名）。
    """
    here = Path(__file__).resolve().parent
    # 仓库里的真实文件名（含 NBSP）
    candidate = here / "HED\u00A0Alphabetically\u00A0(A-Y)\u00A0October\u00A02024.html"
    if candidate.exists():
        return candidate

    # 兜底：在当前目录里找唯一一个 .html
    html_files = sorted(here.glob("*.html"))
    if not html_files:
        raise FileNotFoundError(f"No .html files found in {here}")
    if len(html_files) == 1:
        return html_files[0]
    # 多个的话优先名字里带 HED 的
    with_hed = [p for p in html_files if "HED" in p.name]
    if len(with_hed) == 1:
        return with_hed[0]
    raise FileNotFoundError(
        "Cannot uniquely determine HED HTML file. Candidates:\n"
        + "\n".join(f"- {p.name}" for p in html_files)
    )


def _get_main_table(input_html: Path):
    html_text = input_html.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html_text, "html.parser")

    container_div = soup.find("div", id="z-alf_27758")
    if container_div is None:
        raise RuntimeError("Could not find <div id='z-alf_27758'> in the HTML file.")

    main_table = container_div.find("table")
    if main_table is None:
        raise RuntimeError("Could not find main <table> inside the HED container div.")

    return main_table


def _split_cell_into_lines(td):
    """
    把一个单元格按 <br> 拆成若干“文本行”。

    关键点：Excel 导出的 HTML 里，<br> 经常嵌套在 <font> 内部，
    不能只遍历 td.children；这里直接把所有 <br> 替换成换行符再 split。
    """
    # BeautifulSoup 的 Tag 没有可靠的深拷贝，这里用 str(td) 重新 parse 一个副本
    clone = BeautifulSoup(str(td), "html.parser")
    td2 = clone.find("td") or clone  # 兜底
    marker = "\uE000"  # private-use char; not whitespace; unlikely to appear in real content
    for br in td2.find_all("br"):
        br.replace_with(marker)

    # 注意：Excel 导出的 HTML 源码里本身就带很多换行缩进（不是 <br>），
    # 这些不应该导致“拆行”。这里先把真实换行统一变空格，只用 marker 来拆行。
    raw = td2.get_text(separator=" ", strip=True)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")

    lines = [_norm_spaces(x) for x in raw.split(marker)]
    return [x for x in lines if x]


def _html_fragment_to_text(fragment: str) -> str:
    # 保留兼容：部分逻辑仍可能调用
    if not fragment:
        return ""
    frag = BeautifulSoup(fragment, "html.parser")
    text = frag.get_text(separator=" ", strip=True)
    return _norm_spaces(text)


def _is_note_line(text: str) -> bool:
    """
    判断一行是不是“构形/变体说明”而不是实词条，简单用前缀来区分。
    """
    if not text:
        return True
    stripped = text.lstrip()
    lower = stripped.lower()
    note_prefixes = (
        "comp.",
        "(comp.",
        "composition:",
        "(composition:",
        "variant:",
        "(variant:",
        "note:",
        "(note:",
    )
    if lower.startswith(note_prefixes):
        return True
    # 条目内用 ➀➁➂➃➄➅ 等编号的旧义说明，也视作注释，归入字头释义
    circled_nums = ("➀", "➁", "➂", "➃", "➄", "➅", "➆", "➇", "➈")
    if stripped.startswith(circled_nums):
        return True
    return False


def _is_phrase_exclude_line(text: str) -> bool:
    """
    这些行在 HED 里通常不是“词条”，而是补充说明/另读/参见等。
    你希望的输出里应当跳过它们。
    """
    if not text:
        return True
    s = text.strip()
    # 常见：<又> xxx. (See ...)
    if s.startswith("<又>"):
        return True
    # 行内又音注记：如 "bedbug.¹¹ 又 bï. (See 蜰 bï)."、"trench.⁵ 又> hõ. (See …)"
    # 这类注记和释义在同一行，不是独立词条。
    if re.search(
        r"(?<![\u4e00-\u9fff])(?:<又>|又>|又)\s*[A-Za-zÄäÊêËëÎîÏïÔôÖöÛûÜüÁáÉéÍíÓóÚúÀàÈèÌìÒòÙùÃãÕõŨũÑñ][^(]*\(See",
        s,
    ):
        return True
    # 纯标签行（<文读>、<old> 等），去掉标签后没有内容
    if not re.sub(r"<[^<>]{1,12}>", "", s).strip():
        return True
    # 跨行残片：以左括号开头（如 "(cf 樔…"、"(variants: …"）
    if s.startswith("(") or s.startswith("（"):
        return True
    # 纯参见行
    if s.startswith("(See ") or s.startswith("See "):
        return True
    # 括号内“前简/变体说明”等（如 "(former simplified and variant form: 亜) ä yà )."）
    if s.startswith("(former "):
        return True
    # 字头释义延续（如 "<lit.> encourage; exhort..."），不单独成条
    if s.startswith("<lit.>") or s.startswith("<wr.>"):
        return True
    return False


_CJK_RE = re.compile(r"[\u3400-\u9FFF]")


def _looks_like_cjk_sentence(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # Must contain CJK
    if not _CJK_RE.search(s):
        return False
    # Should not look like romanization
    if re.search(r"[A-Za-z]", s):
        return False
    # Typically ends with Chinese punctuation or has commas/periods
    return True


def _looks_like_bracketed_cjk_sentence(s: str) -> bool:
    s = s.strip()
    return s.startswith("[") and s.endswith("]") and _looks_like_cjk_sentence(s[1:-1])


def _looks_like_gps_sentence(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # Starts with Latin, often has diacritics/hyphens, commas/periods
    if not re.match(r"^[A-Za-zÄäÂâÊêËëÎîÏïÔôÖöÛûÜüÁáÉéÍíÓóÚúÀàÈèÌìÒòÙùÃãÕõŨũÑñ]", s):
        return False
    # GPS often has hyphens and diacritics
    if re.search(r"[âäêëîïôöûüãõũñ\-]", s, re.IGNORECASE):
        return True
    # Fall back: contains many hyphen-separated chunks
    if s.count("-") >= 2:
        return True
    return False


def _looks_like_pinyin_sentence(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # Pinyin has tone marks and spaces; usually contains commas/periods
    if _CJK_RE.search(s):
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    # Must have at least one tone-mark vowel or apostrophe, or multiple words
    if re.search(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ']", s):
        return True
    if len(s.split()) >= 2:
        return True
    return False


def _is_cjk_only_line(s: str) -> bool:
    """整行仅 CJK（无拉丁字母），用于识别「繁/简」独占一行的块。"""
    s = s.strip()
    return bool(s) and _CJK_RE.search(s) and not re.search(r"[A-Za-z]", s)


def _is_english_only_line(s: str) -> bool:
    """整行像纯英译（无 CJK、非 GPS 句、无汉拼声调字母），用于合并多行英译。"""
    s = s.strip()
    if not s or _CJK_RE.search(s):
        return False
    if _is_note_line(s) or _is_phrase_exclude_line(s):
        return False
    if _looks_like_gps_sentence(s):
        return False
    # 仅当含汉拼声调字母（āáǎà 等）才视为汉拼；多词无声调（如 "Mencius, another day..."）算英译
    if _PINYIN_TONE_LETTER_RE.search(s):
        return False
    return bool(re.search(r"[A-Za-z]", s))


# 汉语拼音常用带声调字母（含大小写）；用于区分汉拼与台山话 GPS
_PINYIN_TONE_LETTER_RE = re.compile(
    r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ"
    r"ĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙǕǗǙǛ]"
)
# 汉拼也会用撇号（如 xī'ān），但仅含撇号无声调字母的（如 don't）是英文缩写，不算汉拼


def _looks_like_pinyin_token(tok: str) -> bool:
    """Token 含汉语拼音声调字母则视为汉拼；仅含撇号（如 don't）不算汉拼。"""
    return bool(_PINYIN_TONE_LETTER_RE.search(tok))


def _try_parse_phrase_line(line: str):
    """
    尝试把一条“词句”拆成：繁体(整词)、GPS、汉拼、英译。
    形如：哑巴[啞巴] ä-bä yǎba a dumb person, mute.⁵
    同时识别前缀 “<台>” 作为台山话标记。
    """
    tag = ""
    s = line.lstrip()
    if s.startswith("<台>"):
        tag = "台"
        s = s[len("<台>") :].lstrip()
        line = s

    # 特例 1：像 “啊,好吧! À, hāo-bà! À, hǎoba! Er, OK!” 这种完整例句
    m_ex = re.match(r"^(.+?[。！？!])\s+(.+?[!])\s+(.+?[!])\s+(.+)$", line)
    if m_ex and _CJK_RE.search(m_ex.group(1)):
        phrase_ch = m_ex.group(1)
        gps = m_ex.group(2)
        # 《台》条目的第三段是方言罗马字而非汉语拼音，汉拼留空并并入英译
        if tag == "台":
            pinyin = ""
            english = (m_ex.group(3) + " " + m_ex.group(4)).strip()
        else:
            pinyin = m_ex.group(3)
            english = m_ex.group(4)
        trad = phrase_ch
        simp = phrase_ch
        return trad, simp, gps, pinyin, _norm_spaces(english), tag

    # 粗分 token，避免简单按位置切分导致 'or' 乱入 GPS/汉拼
    tokens = line.split()
    if len(tokens) < 3:
        # 若整行只有中文词形，解析出繁/简供后续多行合并用
        phrase_ch = _norm_spaces(line)
        if phrase_ch and _CJK_RE.search(phrase_ch) and not re.search(r"[A-Za-z]", phrase_ch):
            pairs = re.findall(r"([^ \[]+)\[([^\]]+)\]", phrase_ch)
            if pairs:
                simp = " or ".join(b.strip() for b, _ in pairs if b.strip())
                trad = " or ".join(t.strip() for _, t in pairs if t.strip())
                return trad, simp, "", "", "", tag
            if "[" in phrase_ch and "]" in phrase_ch:
                left, right = phrase_ch.find("["), phrase_ch.rfind("]")
                base, inner = phrase_ch[:left].strip(), phrase_ch[left + 1 : right].strip()
                if base and inner:
                    return inner, base, "", "", "", tag
            # 无括号的纯中文句（如 "佛肸召，子欲往。"）也作为繁/简，以便与下一行 GPS、再下一行汉拼合并
            return phrase_ch, phrase_ch, "", "", "", tag
        return "", "", "", "", _norm_spaces(line), tag

    # 判断一个 token 是否“像 GPS”（Hoisanva），特征：含有变音字母或连字符
    def looks_like_gps(tok: str) -> bool:
        return bool(re.search(r"[-âäêëîïôöûüáéíóúǎǐǒǔàèìòùãõũñ]", tok))

    # 判断 token 是否“更像 GPS 而非汉拼”：必须含台山话特有变音
    # 仅含汉拼式声调+连字符的（如 dānsì-hújiāng、Dì-sān）不算 GPS，避免与汉拼混淆
    def looks_like_gps_specific(tok: str) -> bool:
        # 台山话特有或常见变音（ë ï ö û õ ũ ã ñ â ä），汉拼里少见
        if re.search(r"[ëïöûõũãñâä]", tok):
            return True
        # 有连字符且含上述变音之一（如 nî-yiù 的 î）才算 GPS
        if "-" in tok and re.search(r"[âêîôûãõũñ]", tok):
            return True
        return False

    # 1) 先找第一个 GPS token：在此之前的都视为“词形部分”（可含 or、多种写法）
    # 注意：中文 token（含 CJK 字符）即使有标点也不应被视为 GPS
    phrase_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # 如果包含 CJK 字符，一定是词形部分，不是 GPS
        if _CJK_RE.search(tok):
            phrase_tokens.append(tok)
            i += 1
        # 如果不含 CJK 且看起来像 GPS，停止收集 phrase_tokens
        elif looks_like_gps(tok):
            break
        else:
            # 其他情况（如纯英文）也归入 phrase_tokens，直到遇到 GPS
            phrase_tokens.append(tok)
            i += 1

    if i >= len(tokens):
        # 找不到 GPS，就当整行是英文释义
        return "", "", "", "", _norm_spaces(line), tag

    # 2) 收集 GPS 区：连续收集所有 GPS token，直到遇到明显是汉拼的 token
    gps_tokens = [tokens[i]]
    i += 1
    
    # 处理 "or" 变体：收集 "GPS1 or GPS2" 格式
    while i + 1 < len(tokens) and tokens[i].lower() == "or":
        next_tok = tokens[i + 1]
        # 若下一 token 明显是 GPS（有连字符或台山话变音），则视为 GPS 变体，加入
        if looks_like_gps_specific(next_tok):
            gps_tokens.extend(tokens[i : i + 2])
            i += 2
            continue
        # 若下一 token 像汉拼且不像 GPS，才停止（如 "GPS1 or GPS2 汉拼" 里的汉拼）
        if _looks_like_pinyin_token(next_tok):
            break
        if looks_like_gps(next_tok):
            gps_tokens.extend(tokens[i : i + 2])
            i += 2
        else:
            break

    # 处理括号（GPS 里带括号，如 "ä- (y) à"）
    while i < len(tokens) and re.match(r"^\(.*\)$", tokens[i]):
        gps_tokens.append(tokens[i])
        i += 1
    
    # 继续收集后续的 GPS token（可能是连续多个，如 "Äi, ngô-jï-ào-lēl."）
    while i < len(tokens):
        tok = tokens[i]
        # 如果包含 CJK 字符，不应归入 GPS（应该已经在 phrase_tokens 中）
        if _CJK_RE.search(tok):
            break
        
        # 优先检查：如果 token 明显是 GPS（有连字符或台山话特有变音），直接归入 GPS
        # 即使它也可能包含汉拼式声调（如 "ngô-diù-būt-huï-lēl." 中的 ô）
        if looks_like_gps_specific(tok):
            gps_tokens.append(tok)
            i += 1
            continue
        
        # 如果看起来像汉拼，需要判断：如果下一个 token 更像 GPS（有连字符或台山话特有变音），
        # 则这个 token 可能是 GPS 的一部分（如 "Ài," 后跟 "dāo-jï-nguĩ-xū"）
        if _looks_like_pinyin_token(tok):
            # 检查下一个 token 是否更像 GPS
            if i + 1 < len(tokens) and looks_like_gps_specific(tokens[i + 1]):
                # 下一个 token 更像 GPS，所以当前 token 也是 GPS 的一部分
                gps_tokens.append(tok)
                i += 1
            else:
                # 否则停止 GPS 收集，这个 token 将作为汉拼的开始
                break
        
        # 如果看起来像 GPS（有变音或连字符），继续收集
        elif looks_like_gps(tok):
            gps_tokens.append(tok)
            i += 1
        # 单字符/带标点的罗马字：仅当可能是 GPS 的一部分时才归入
        elif re.match(r"^[A-Za-zÄäÂâÊêËëÎîÏïÔôÖöÛûÜüÁáÉéÍíÓóÚúÀàÈèÌìÒòÙùÃãÕõŨũÑñ][,;.!?]?$", tok):
            # 如果下一个 token 是 GPS，这个单字符可能是 GPS 的一部分（如 "Äi," 后跟 "ngô-jï-..."）
            if i + 1 < len(tokens) and looks_like_gps(tokens[i + 1]):
                gps_tokens.append(tok)
                i += 1
            else:
                # 否则停止 GPS 收集
                break
        else:
            # 其他情况（如英文）停止 GPS 收集
            break

    if i >= len(tokens):
        return "", "", "", "", _norm_spaces(line), tag

    # 3) GPS 之后为汉拼（可多 token，直至遇到不像汉拼的 token），再后为英译
    # 标记为《台》的为台山话等方言，无汉语拼音，GPS 后直接是英译，汉拼列留空
    if tag == "台":
        pinyin = ""
        english_tokens = tokens[i:]
    else:
        pinyin_tokens = []
        while i < len(tokens) and _looks_like_pinyin_token(tokens[i]):
            pinyin_tokens.append(tokens[i])
            i += 1
        pinyin = " ".join(pinyin_tokens)
        english_tokens = tokens[i:]

    phrase_ch = " ".join(phrase_tokens)
    gps = " ".join(gps_tokens)
    english = " ".join(english_tokens)

    # 处理形如 “哑巴[啞巴]” 的情况：
    # 约定：中括号外为简体形式，中括号内为繁体形式。
    trad = phrase_ch
    simp = ""

    # 情形 1：有多组 “简体[繁体] or 简体[繁体] ...”
    # 例如：家无儋石[家無儋石] or 家无担石[家無擔石]
    pairs = re.findall(r"([^ \[]+)\[([^\]]+)\]", phrase_ch)
    if pairs:
        simp = " or ".join(b.strip() for b, _ in pairs if b.strip())
        trad = " or ".join(t.strip() for _, t in pairs if t.strip())
    else:
        # 情形 2：单个 “简体[繁体]”
        if "[" in phrase_ch and "]" in phrase_ch:
            left = phrase_ch.find("[")
            right = phrase_ch.rfind("]")
            base = phrase_ch[:left]
            inner = phrase_ch[left + 1 : right]
            base = base.strip()
            inner = inner.strip()
            if base and inner:
                simp = base
                trad = inner

    # 情形 3：英译开头为 “or 简[繁] GPS 汉拼 …”，即多种写法的第二种，合并到繁/简/GPS/汉拼
    def parse_phrase_trad_simp(phrase_str: str):
        """从 简[繁] 或 繁 解析出 trad, simp。"""
        pairs = re.findall(r"([^ \[]+)\[([^\]]+)\]", phrase_str)
        if pairs:
            return " or ".join(t.strip() for _, t in pairs if t.strip()), " or ".join(b.strip() for b, _ in pairs if b.strip())
        if "[" in phrase_str and "]" in phrase_str:
            left, right = phrase_str.find("["), phrase_str.rfind("]")
            base, inner = phrase_str[:left].strip(), phrase_str[left + 1 : right].strip()
            if base and inner:
                return inner, base
        return phrase_str, phrase_str

    while len(english_tokens) >= 4 and english_tokens[0].lower() == "or" and _CJK_RE.search(english_tokens[1]):
        phrase2 = english_tokens[1]
        if not looks_like_gps(english_tokens[2]):
            break
        gps2 = english_tokens[2]
        j = 3
        pinyin2_list = []
        while j < len(english_tokens) and _looks_like_pinyin_token(english_tokens[j]):
            pinyin2_list.append(english_tokens[j])
            j += 1
        if not pinyin2_list:
            break
        trad2, simp2 = parse_phrase_trad_simp(phrase2)
        trad = (trad + " or " + trad2) if trad else trad2
        simp = (simp + " or " + simp2) if simp else simp2
        gps = (gps + " or " + gps2) if gps else gps2
        pinyin = (pinyin + " or " + " ".join(pinyin2_list)) if pinyin else " ".join(pinyin2_list)
        english_tokens = english_tokens[j:]
        english = " ".join(english_tokens)

    return trad, simp, gps, pinyin, _norm_spaces(english), tag


def extract_mixed_rows(input_html: Path):
    """
    从主 HTML 中抽取“字头 + 词条”混合的行：
    - 先输出一个字头行 (RecordType=HEAD)
    - 紧接着输出该字头下的一系列词条行 (RecordType=PHRASE)
    """
    table = _get_main_table(input_html)
    rows = table.find_all("tr")
    if not rows:
        raise RuntimeError("No <tr> rows found in the main table.")

    header_tr = rows[0]
    data_trs = rows[1:]

    # 确认表头列顺序（号, 部, 画, 繁, 简, GPS, 汉拼, 英译与词句, gps#, Nos., Image）
    header_tds = header_tr.find_all("td")
    header_texts = [_norm_spaces(td.get_text(strip=True)) for td in header_tds]
    try:
        gloss_col_idx = header_texts.index("英译与词句")
    except ValueError:
        raise RuntimeError("Cannot find '英译与词句' column in header.")

    for tr in data_trs:
        tds = tr.find_all("td")
        if len(tds) <= gloss_col_idx:
            continue

        col = lambda idx: _norm_spaces(tds[idx].get_text(strip=True)) if idx < len(tds) else ""
        head_no = col(0)
        head_radical = col(1)
        head_strokes = col(2)
        head_trad = col(3)
        head_simp = col(4)
        head_gps = col(5)
        head_pinyin = col(6)
        head_gps_code = col(8)
        head_nos = col(9)

        gloss_td = tds[gloss_col_idx]
        lines = _split_cell_into_lines(gloss_td)
        if not lines:
            continue

        # 第 1 行：字头总释义；另外把 comp/composition/variant/(See ...) 追加进字头释义
        head_gloss_parts = [lines[0]]
        for line in lines[1:]:
            if _is_note_line(line) or line.startswith("(See ") or line.startswith("See "):
                head_gloss_parts.append(line)
        head_gloss_text = " ".join([p for p in head_gloss_parts if p])
        head_gloss_text = _norm_spaces(head_gloss_text)

        # 先输出字头行：列结构保持和主 CSV 一致，但增加 RecordType + Head linkage
        yield [
            "HEAD",
        "",  # DialectTag 留空
        head_no,
        head_radical,
        head_strokes,
        head_trad,
        head_simp,
        head_gps,
        head_pinyin,
        head_gloss_text,
        head_gps_code,
        head_nos,
        ]

        # 其余行视为词条/例句
        rest = lines[1:]
        i = 0
        while i < len(rest):
            line = rest[i]
            if _is_note_line(line):
                i += 1
                continue
            if _is_phrase_exclude_line(line):
                i += 1
                continue

            # 例句块合并（按行结构识别，减少单行解析歧义）

            # 块式 1：四行 = 简 / [繁] / GPS / 汉拼，可选多行英译
            if (
                i + 3 < len(rest)
                and _looks_like_cjk_sentence(rest[i])
                and _looks_like_bracketed_cjk_sentence(rest[i + 1])
                and _looks_like_gps_sentence(rest[i + 2])
                and _looks_like_pinyin_sentence(rest[i + 3])
            ):
                simp_sentence = _norm_spaces(rest[i])
                trad_sentence = _norm_spaces(rest[i + 1][1:-1])
                gps_sentence = _norm_spaces(rest[i + 2])
                pinyin_sentence = _norm_spaces(rest[i + 3])
                english_parts = []
                skip = 4
                while i + skip < len(rest) and _is_english_only_line(rest[i + skip]):
                    english_parts.append(_norm_spaces(rest[i + skip]))
                    skip += 1
                english_sentence = " ".join(english_parts)
                yield [
                    "PHRASE",
                    "",
                    head_nos,
                    "",
                    "",
                    "",
                    trad_sentence,
                    simp_sentence,
                    gps_sentence,
                    pinyin_sentence,
                    english_sentence,
                    head_gps_code,
                    head_nos,
                ]
                i += skip
                continue

            # 块式 2：四行 = 纯 CJK / GPS / 汉拼 / 英（无 [繁]），可选多行英译（如 晁采琬琰、魚在于沼 英译多行）
            if (
                i + 3 < len(rest)
                and _is_cjk_only_line(rest[i])
                and _looks_like_gps_sentence(rest[i + 1])
                and _looks_like_pinyin_sentence(rest[i + 2])
                and _is_english_only_line(rest[i + 3])
            ):
                phrase_ch = _norm_spaces(rest[i])
                trad_sentence = phrase_ch
                simp_sentence = phrase_ch
                if "[" in phrase_ch and "]" in phrase_ch:
                    pairs = re.findall(r"([^ \[]+)\[([^\]]+)\]", phrase_ch)
                    if pairs:
                        simp_sentence = " or ".join(b.strip() for b, _ in pairs if b.strip())
                        trad_sentence = " or ".join(t.strip() for _, t in pairs if t.strip())
                    else:
                        left, right = phrase_ch.find("["), phrase_ch.rfind("]")
                        base, inner = phrase_ch[:left].strip(), phrase_ch[left + 1 : right].strip()
                        if base and inner:
                            trad_sentence, simp_sentence = inner, base
                gps_sentence = _norm_spaces(rest[i + 1])
                pinyin_sentence = _norm_spaces(rest[i + 2])
                english_parts = [_norm_spaces(rest[i + 3])]
                skip = 4
                while i + skip < len(rest) and _is_english_only_line(rest[i + skip]):
                    english_parts.append(_norm_spaces(rest[i + skip]))
                    skip += 1
                english_sentence = " ".join(english_parts)
                yield [
                    "PHRASE",
                    "",
                    head_nos,
                    "",
                    "",
                    "",
                    trad_sentence,
                    simp_sentence,
                    gps_sentence,
                    pinyin_sentence,
                    english_sentence,
                    head_gps_code,
                    head_nos,
                ]
                i += skip
                continue

            trad, simp, gps, pinyin, english, tag = _try_parse_phrase_line(line)
            
            # 特殊处理：当前行只有繁/简（无GPS和汉拼）时，与后续行合并
            if (trad or simp) and not gps and not pinyin and i + 1 < len(rest):
                next_line = rest[i + 1]
                if not _is_note_line(next_line) and not _is_phrase_exclude_line(next_line):
                    next_trad, next_simp, next_gps, next_pinyin, next_english, next_tag = _try_parse_phrase_line(next_line)
                    # 情况 A：下一行有 GPS 和汉拼（如 "Hà-hèo-sì-däi-kĩ-ām Xià hòu shì jì qí àn"）
                    if next_gps and next_pinyin:
                        gps = next_gps
                        pinyin = next_pinyin
                        if i + 2 < len(rest):
                            third_line = rest[i + 2]
                            if not _is_note_line(third_line) and not _is_phrase_exclude_line(third_line):
                                third_trad, third_simp, third_gps, third_pinyin, third_english, third_tag = _try_parse_phrase_line(third_line)
                                if not third_trad and not third_simp and not third_gps and not third_pinyin and third_english:
                                    english = third_english
                                    i += 3
                                    yield ["PHRASE", tag, "", "", "", trad, simp, gps, pinyin, english, head_gps_code, head_nos]
                                    continue
                        if next_english:
                            english = next_english
                        i += 2
                        yield ["PHRASE", tag, "", "", "", trad, simp, gps, pinyin, english, head_gps_code, head_nos]
                        continue
                    # 情况 B：下一行只有 GPS，第三行是汉拼（如 佛肸召 → Bäi-dèik-jël... → Bì xī zhào...）
                    if next_gps and not next_pinyin and not (next_trad or next_simp) and i + 2 < len(rest):
                        third_line = rest[i + 2]
                        if not _is_note_line(third_line) and not _is_phrase_exclude_line(third_line):
                            third_trad, third_simp, third_gps, third_pinyin, third_english, third_tag = _try_parse_phrase_line(third_line)
                            if third_pinyin and not (third_trad or third_simp):
                                gps = next_gps
                                # 第三行可能把首字解析成 GPS（如 Bì），与 third_pinyin 拼成完整汉拼
                                pinyin = (_norm_spaces(third_gps + " " + third_pinyin) if third_gps else third_pinyin)
                                english = third_english or ""
                                skip = 3
                                if i + 3 < len(rest):
                                    fourth_line = rest[i + 3]
                                    if not _is_note_line(fourth_line) and not _is_phrase_exclude_line(fourth_line):
                                        ft, fs, fg, fp, fe, _ = _try_parse_phrase_line(fourth_line)
                                        if not ft and not fs and not fg and not fp and fe:
                                            english = fe
                                            skip = 4
                                i += skip
                                yield ["PHRASE", tag, "", "", "", trad, simp, gps, pinyin, english, head_gps_code, head_nos]
                                continue

            yield [
                "PHRASE",
                tag,
                "",  # 号（词条行留空）
                "",  # 部
                "",  # 画
                trad,
                simp,
                gps,
                pinyin,
                english,
                head_gps_code,
                head_nos,
            ]
            i += 1


def phrases_to_csv(input_html: Path, output_csv: Path) -> None:
    rows = list(extract_mixed_rows(input_html))

    header = [
        "RecordType",  # HEAD / PHRASE
        "DialectTag",  # 例如: 台 (台山话特色词句)
        "号",
        "部",
        "画",
        "繁",
        "简",
        "GPS",
        "汉拼",
        "英译与词句",
        "gps#",
        "Nos.",
    ]

    if output_csv.parent:
        output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="Extract phrase-level entries from HED HTML and link them to their head characters."
    )
    parser.add_argument(
        "input_html",
        type=Path,
        nargs="?",
        help="Path to the HED HTML file (default: auto-detect in current project).",
    )
    parser.add_argument(
        "output_csv",
        type=Path,
        nargs="?",
        help="Path to the output CSV file (default: same dir, '*_phrases.csv').",
    )

    args = parser.parse_args()

    if args.input_html is None:
        input_html = _resolve_default_html()
    else:
        input_html = args.input_html

    if args.output_csv is not None:
        output_csv = args.output_csv
    else:
        # 默认输出名：在主 HTML 同目录下，文件名加 _phrases
        base = input_html.with_suffix("")
        output_csv = base.with_name(base.name + "_phrases.csv").with_suffix(".csv")

    phrases_to_csv(input_html, output_csv)


if __name__ == "__main__":
    main()

