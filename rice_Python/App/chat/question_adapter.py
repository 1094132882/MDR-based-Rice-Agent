import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from .llm import llm


LEXICON_PATH = Path(__file__).with_name("db_keyword_lexicon.json")
SV_NAME_PATTERN = r"[A-Za-z0-9_]+_[A-Za-z0-9_]+_(?:DEL|INS|TRA|INV|OTH)\d+(?:_\d+)?"
OGI_NAME_PATTERN = r"OGI:\d{6,10}"
MUTANT_NAME_PATTERN = r"22NB[A-Z]\d+"
GENE_NAME_PATTERNS = [
    r"LOC_Os\d{2}g\d+(?:\.\d+)?",
    r"Os[A-Za-z0-9_]+[Gg]\d+(?:\.\d+)?(?:\.T\d+)?",
    r"Os\d{2}g\d+(?:\.\d+)?",
    r"Oglab_\d+",
    r"TMG\d+",
    r"R\d+C\d+g\d+",
]


def normalize_question_for_agent(question: str) -> str:
    """
    Normalize multilingual user questions into the Chinese-style internal
    question format that the current agent/tool rules handle most reliably.

    Database identifiers and controlled vocabulary values are protected before
    translation so LLMs do not rewrite gene IDs, accessions, SV IDs, TE types,
    coordinates, or URLs.
    """
    if not question:
        return question

    text = question.strip()
    if not _is_likely_english_question(text):
        return text

    lexicon = _load_lexicon()
    deterministic = _deterministic_english_to_internal_query(text, lexicon)
    if deterministic:
        if os.getenv("QUESTION_ADAPTER_DEBUG", "").lower() == "true":
            print(f"[question_adapter] original={text}")
            print(f"[question_adapter] internal={deterministic}")
        return deterministic

    protected_text, replacements = _protect_database_terms(text, lexicon)
    translated = _translate_question_to_internal_chinese(protected_text, lexicon)

    if translated:
        normalized = _restore_database_terms(translated, replacements)
    else:
        normalized = _restore_database_terms(_append_rule_based_hints(protected_text), replacements)

    if os.getenv("QUESTION_ADAPTER_DEBUG", "").lower() == "true":
        print(f"[question_adapter] original={text}")
        print(f"[question_adapter] internal={normalized}")

    return normalized or text


def _is_likely_english_question(text: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", text):
        return False
    letters = len(re.findall(r"[A-Za-z]", text))
    return letters >= 3


def _deterministic_english_to_internal_query(text: str, lexicon: Dict) -> str:
    """
    Convert high-frequency English questions to the exact Chinese-style
    questions already covered by the existing tool prompts.

    This avoids relying on a second LLM call for common database queries.
    """
    q = text.lower()
    sv_name = _extract_first(SV_NAME_PATTERN, text)
    gene_name = _extract_gene_name(text)
    ogi_name = _extract_first(OGI_NAME_PATTERN, text)
    mutant_name = _extract_first(MUTANT_NAME_PATTERN, text)

    if sv_name:
        if _mentions_te_query(q):
            return f"{sv_name}有没有转座元件注释？"
        sv_type = _extract_sv_type_cn(q)
        if sv_type and _has_any(q, ["structural variation", "variant", "sv "]):
            return f"{sv_name}是什么{sv_type}类型的结构变异？"
        if _has_any(q, ["structural variation", "variant", "sv ", "location", "coordinate"]):
            return f"{sv_name}的结构变异信息是什么？"

    if mutant_name and _has_any(q, ["gene", "genes", "associated", "related", "linked"]):
        return f"{mutant_name}关联哪些基因？"

    if ogi_name:
        if _has_any(q, ["how many", "count", "number", "total"]):
            return f"{ogi_name}这个分类里共有多少个水稻基因？"
        return f"{ogi_name}这个分类里有哪些水稻基因？"

    if gene_name:
        if _has_any(q, ["strand", "plus strand", "minus strand", "forward", "reverse"]):
            return f"{gene_name}基因所在的DNA链是正链还是负链？"
        if _has_any(q, ["coordinate", "coordinates", "location", "position", "located", "chromosome"]):
            return f"{gene_name}在基因组中的具体物理坐标是多少？"
        if _has_any(q, ["mrna", "transcript", "transcripts"]):
            return f"{gene_name}基因注释中记录的mRNA转录本有哪些？"
        if _has_any(q, ["dna sequence", "genomic sequence"]):
            return f"{gene_name}基因的完整DNA序列是什么？"
        if _has_any(q, ["cds", "coding sequence"]):
            return f"{gene_name}基因的编码区全序列？"
        if _has_any(q, ["protein sequence", "amino acid"]):
            return f"{gene_name}基因编码的蛋白质完整氨基酸序列是什么？"
        if _has_any(q, ["mutant", "mutants"]):
            return f"{gene_name}这个基因有没有突变体？"
        if _has_any(q, ["ogi", "ortholog gene index", "ortholog"]):
            if _has_any(q, ["how many", "count", "number", "total"]):
                return f"{gene_name}所属的OGI分组有多少个成员基因？"
            return f"{gene_name}对应的OGI编号是多少？"
        if _has_any(q, ["expression", "leaf", "root", "young ear", "panicle", "stem"]):
            return f"{gene_name}的表达信息是什么？"

        neighbor_query = _build_neighbor_query(gene_name, q)
        if neighbor_query:
            return neighbor_query

        if _has_any(q, ["function", "annotation"]):
            return f"{gene_name}的功能或注释是什么？"

    region_query = _build_region_query(text, q, lexicon)
    if region_query:
        return region_query

    return ""


def _translate_question_to_internal_chinese(text: str, lexicon: Dict) -> str:
    if llm is None:
        return ""

    glossary = _format_glossary(lexicon)
    prompt = f"""Convert the user question into a concise Chinese internal query for a rice genomics database agent.

Rules:
- Return only the converted Chinese question.
- Keep every placeholder such as __KEEP_0__ exactly unchanged.
- Do not answer the question.
- Do not add facts or database values.
- Preserve numbers, units, chromosome coordinates, and query intent.
- Use the database vocabulary below when relevant.

Database vocabulary:
{glossary}

Examples:
English: What are the chromosome coordinates of __KEEP_0__?
Chinese: __KEEP_0__在基因组中的具体物理坐标是多少？

English: Which strand is __KEEP_0__ located on?
Chinese: __KEEP_0__位于正链还是负链？

English: Which TE types are associated with __KEEP_0__?
Chinese: __KEEP_0__关联了哪些转座元件？

English: What are the upstream genes within 50kb of __KEEP_0__?
Chinese: __KEEP_0__上游50kb范围内有哪些基因？

English: What is the longest deletion-type structural variation in __KEEP_0__ on __KEEP_1__ between 300kb and 500kb?
Chinese: __KEEP_0__的__KEEP_1__在300kb-500kb范围内最长的缺失类型结构变异是什么？

User question:
{text}

/no_think"""

    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", response)
        content = _strip_code_fence(str(content).strip())
        if content:
            placeholders = re.findall(r"__KEEP_\d+__", text)
            if placeholders and not all(placeholder in content for placeholder in placeholders):
                return ""
            return content
    except Exception:
        return ""
    return ""


def _load_lexicon() -> Dict:
    try:
        return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "accessions": [],
            "primary_chromosomes": [f"Chr{i:02d}" for i in range(1, 13)],
            "sv_types": ["DEL", "INS", "INV", "OTH", "TRA"],
            "te_types": [],
            "mdr_terms": [],
            "english_to_internal_terms": {},
        }


def _format_glossary(lexicon: Dict) -> str:
    terms = lexicon.get("english_to_internal_terms", {})
    lines = []
    for source, target in sorted(terms.items(), key=lambda item: item[0].lower()):
        lines.append(f"- {source}: {target}")
    return "\n".join(lines[:80])


def _protect_database_terms(text: str, lexicon: Dict) -> Tuple[str, List[Tuple[str, str]]]:
    replacements: List[Tuple[str, str]] = []
    protected = text

    patterns = [
        r"https?://[^\s\])]+",
        OGI_NAME_PATTERN,
        SV_NAME_PATTERN,
        MUTANT_NAME_PATTERN,
        *GENE_NAME_PATTERNS,
        r"Chr[A-Za-z0-9%_.-]+",
    ]

    exact_terms = []
    for key in ("accessions", "primary_chromosomes", "sv_types", "te_types"):
        exact_terms.extend(lexicon.get(key, []))
    exact_terms = sorted(set(exact_terms), key=len, reverse=True)

    for pattern in patterns:
        protected = _replace_matches(protected, pattern, replacements)

    for term in exact_terms:
        if not term:
            continue
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])"
        protected = _replace_matches(protected, pattern, replacements)

    return protected, replacements


def _replace_matches(text: str, pattern: str, replacements: List[Tuple[str, str]]) -> str:
    def repl(match):
        original = match.group(0)
        for placeholder, existing in replacements:
            if existing == original:
                return placeholder
        placeholder = f"__KEEP_{len(replacements)}__"
        replacements.append((placeholder, original))
        return placeholder

    return re.sub(pattern, repl, text, flags=re.IGNORECASE)


def _restore_database_terms(text: str, replacements: List[Tuple[str, str]]) -> str:
    restored = text
    for placeholder, original in replacements:
        restored = restored.replace(placeholder, original)
    return restored.strip()


def _extract_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_gene_name(text: str) -> str:
    for pattern in GENE_NAME_PATTERNS:
        gene_name = _extract_first(pattern, text)
        if gene_name:
            return gene_name
    return ""


def _has_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _mentions_te_query(text: str) -> bool:
    return (
        "transposable element" in text
        or "transposon" in text
        or "te annotation" in text
        or "te type" in text
        or re.search(r"\bte\b", text) is not None
    )


def _extract_sv_type_cn(text: str) -> str:
    sv_type_map = [
        (["deletion", " del ", "del-type"], "缺失"),
        (["insertion", " ins ", "ins-type"], "插入"),
        (["translocation", " tra ", "tra-type"], "易位"),
        (["inversion", " inv ", "inv-type"], "倒位"),
        (["other", " oth ", "oth-type"], "其他"),
    ]
    padded = f" {text} "
    for keywords, cn_name in sv_type_map:
        if any(keyword in padded for keyword in keywords):
            return cn_name
    return ""


def _build_neighbor_query(gene_name: str, text: str) -> str:
    is_upstream = "upstream" in text or "before" in text
    is_downstream = "downstream" in text or "after" in text
    if not is_upstream and not is_downstream:
        return ""

    direction = "上游" if is_upstream else "下游"
    distance = _extract_distance(text)
    count = _extract_count(text)
    if distance:
        return f"{gene_name}{direction}{distance}范围内有哪些基因？"
    if count:
        return f"{gene_name}的{direction}最近{count}个基因。"
    return f"{gene_name}的{direction}最近的基因。"


def _build_region_query(text: str, lowered_text: str, lexicon: Dict) -> str:
    accession = _extract_accession(text, lexicon)
    chromosome = _extract_chromosome(text)
    position_range = _extract_range(text)
    if not accession or not chromosome or not position_range:
        return ""

    if _has_any(lowered_text, ["structural variation", "variant", " sv ", "svs"]):
        sv_type = _extract_sv_type_cn(lowered_text)
        if _has_any(lowered_text, ["longest", "largest", "maximum", "max"]):
            if sv_type:
                return f"{accession}的{chromosome}在{position_range}范围内最长的{sv_type}类型结构变异是什么？"
            return f"{accession}的{chromosome}在{position_range}范围内最长的结构变异是什么？"
        if _has_any(lowered_text, ["how many", "count", "number", "statistics", "statistic"]):
            if sv_type:
                return f"{accession}的{chromosome}在{position_range}区域内{sv_type}类型结构变异的数量？"
            return f"{accession}的{chromosome}在{position_range}区域的结构变异分类统计结果？"
        if sv_type:
            return f"{accession}的{chromosome}在{position_range}范围内有哪些{sv_type}类型结构变异？"
        return f"{accession}的{chromosome}在{position_range}范围内有哪些结构变异？"

    if _has_any(lowered_text, ["gene", "genes"]):
        return f"{accession}的{chromosome}在{position_range}范围内有哪些基因？"

    return ""


def _extract_accession(text: str, lexicon: Dict) -> str:
    accessions = sorted(set(lexicon.get("accessions", [])), key=len, reverse=True)
    for accession in accessions:
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(accession)}(?![A-Za-z0-9_])", text, flags=re.IGNORECASE):
            return accession
    return ""


def _extract_chromosome(text: str) -> str:
    chr_match = re.search(r"Chr(?:omosome)?[\s:_-]*(\d{1,2})", text, flags=re.IGNORECASE)
    if chr_match:
        return f"Chr{int(chr_match.group(1)):02d}"

    chromosome_match = re.search(r"chromosome\s+(\d{1,2})", text, flags=re.IGNORECASE)
    if chromosome_match:
        return f"Chr{int(chromosome_match.group(1)):02d}"

    return ""


def _extract_range(text: str) -> str:
    range_patterns = [
        r"(\d+(?:\.\d+)?\s*(?:kb|bp)?)\s*[-:]\s*(\d+(?:\.\d+)?\s*(?:kb|bp)?)",
        r"between\s+(\d+(?:\.\d+)?\s*(?:kb|bp)?)\s+and\s+(\d+(?:\.\d+)?\s*(?:kb|bp)?)",
        r"from\s+(\d+(?:\.\d+)?\s*(?:kb|bp)?)\s+to\s+(\d+(?:\.\d+)?\s*(?:kb|bp)?)",
    ]
    for pattern in range_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"{_compact_unit(match.group(1))}-{_compact_unit(match.group(2))}"
    return ""


def _extract_distance(text: str) -> str:
    match = re.search(r"within\s+(\d+(?:\.\d+)?\s*(?:kb|bp))", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"(\d+(?:\.\d+)?\s*(?:kb|bp))", text, flags=re.IGNORECASE)
    return _compact_unit(match.group(1)) if match else ""


def _extract_count(text: str) -> str:
    match = re.search(r"(?:nearest|closest|next|previous)\s+(\d+)", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _compact_unit(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _append_rule_based_hints(text: str) -> str:
    q = text.lower()
    hints = []
    phrase_hints = [
        (["coordinate", "coordinates", "location", "position"], "位置 坐标"),
        (["strand", "forward", "reverse", "plus strand", "minus strand"], "链方向 正链 负链"),
        (["transcript", "mrna"], "转录本"),
        (["dna sequence"], "DNA序列"),
        (["cds"], "CDS序列"),
        (["protein"], "蛋白质序列"),
        (["mutant"], "突变体"),
        (["ogi", "ortholog gene index"], "OGI 同源基因索引"),
        (["function"], "功能"),
        (["annotation"], "注释"),
        (["expression", "leaf", "root", "young ear", "panicle", "stem"], "表达量 叶 根 幼穗 茎"),
        (["upstream"], "上游"),
        (["downstream"], "下游"),
        (["neighbor", "neighboring", "adjacent", "nearest"], "邻近 最近 基因"),
        (["region", "range", "between", "from"], "区域 范围内 之间"),
        (["structural variation", " sv ", "variant"], "结构变异"),
        (["deletion", "del"], "缺失"),
        (["insertion", "ins"], "插入"),
        (["translocation", "tra"], "易位"),
        (["inversion", "inv"], "倒位"),
        (["longest", "largest", "maximum"], "最长 最大"),
        (["count", "number", "how many", "statistics"], "数量 多少 统计"),
        (["transposable element", " te ", "te type"], "转座元件"),
        (["associated with", "linked to", "contain", "contains"], "关联 包含"),
    ]
    for keywords, hint in phrase_hints:
        if any(keyword in q for keyword in keywords):
            hints.append(hint)

    if not hints:
        return text
    return f"{text}\n\n中文关键词提示：{'；'.join(dict.fromkeys(hints))}"


def _strip_code_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
    return text.strip()
