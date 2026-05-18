# pip install pybliometrics
import os
import pandas as pd
from pybliometrics.utils import init
from pybliometrics.scopus import ScopusSearch, AbstractRetrieval


# =========================
# 1. API KEY
# =========================
# API obtained from: https://dev.elsevier.com/
API_KEY = ""


# =========================
# 2. Query builder
# =========================
def build_query(mode="econ_strict"):
    topic_query = '''
        TITLE-ABS-KEY(
            "gender wage gap" OR
            "gender pay gap" OR
            "gender earnings gap" OR
            ("wage gap" AND gender) OR
            ("pay gap" AND gender)
        )
    '''

    if mode == "econ_strict":
        subj_query = "SUBJAREA(ECON)"
    elif mode == "econ_plus":
        subj_query = "SUBJAREA(ECON OR SOCI OR BUSI OR PSYC)"
    elif mode == "social_sciences_all":
        subj_query = "SUBJAREA(ARTS OR BUSI OR DECI OR ECON OR PSYC OR SOCI)"
    else:
        raise ValueError(
            "mode 必须是 econ_strict, econ_plus, social_sciences_all 之一")

    doc_query = 'DOCTYPE(ar OR re)'

    full_query = f"{topic_query} AND {subj_query} AND {doc_query}"
    return " ".join(full_query.split())


# =========================
# 3. Search Scopus and return paper-level dataframe
# =========================
def search_scopus(query):
    rows = []
    results = ScopusSearch(query, refresh=False).results

    if results is None:
        return pd.DataFrame(rows)

    for r in results:
        eid = str(getattr(r, "eid", "") or "")

        title = str(getattr(r, "title", "") or "")
        authors = str(getattr(r, "author_names", "") or "")
        author_ids = str(getattr(r, "author_ids", "") or "")
        author_afids = str(getattr(r, "author_afids", "") or "")
        cover_date = str(getattr(r, "coverDate", "") or "")
        year = cover_date[:4] if cover_date else ""
        publication_name = str(getattr(r, "publicationName", "") or "")
        doi = str(getattr(r, "doi", "") or "")
        citedby_count = getattr(r, "citedby_count", None)
        keywords = str(getattr(r, "authkeywords", "") or "")
        affiliation_ids = str(getattr(r, "afid", "") or "")
        affiliation_names = str(getattr(r, "affilname", "") or "")
        affiliation_countries = str(
            getattr(r, "affiliation_country", "") or "")

        references = ""
        references_count = 0
        citing_eids = ""
        citing_titles = ""
        citing_count_from_search = 0

        try:
            ab = AbstractRetrieval(eid, view="FULL", refresh=False)

            if ab.references:
                ref_list = []
                for ref in ab.references:
                    ref_author = (
                        str(getattr(ref, "surname", "") or "")
                        or str(getattr(ref, "author", "") or "")
                        or str(getattr(ref, "authors", "") or "")
                    )

                    ref_year = (
                        str(getattr(ref, "publicationyear", "") or "")
                        or str(getattr(ref, "year", "") or "")
                        or str(getattr(ref, "coverDate", "") or "")[:4]
                    )

                    ref_title = str(getattr(ref, "title", "") or "")
                    ref_id = str(getattr(ref, "id", "") or "")
                    ref_doi = str(getattr(ref, "doi", "") or "")

                    if ref_author and ref_year:
                        ref_text = f"{ref_author} ({ref_year})"
                    elif ref_author:
                        ref_text = ref_author
                    elif ref_year and ref_title:
                        ref_text = f"{ref_year}; {ref_title[:80]}"
                    elif ref_doi:
                        ref_text = f"DOI:{ref_doi}"
                    elif ref_id:
                        ref_text = f"SCOPUS_ID:{ref_id}"
                    else:
                        ref_text = ref_title[:80]

                    if ref_text:
                        ref_list.append(ref_text)
                references = " | ".join(ref_list)
                references_count = len(ref_list)

        except Exception:
            references = ""
            references_count = 0

        try:
            cite_query = f'REFEID("{eid}")'
            citing_search = ScopusSearch(cite_query, refresh=False)

            if citing_search.results:
                citing_rows = []

                for x in citing_search.results:
                    ceid = str(getattr(x, "eid", "") or "")
                    ctitle = str(getattr(x, "title", "") or "")

                    if ceid or ctitle:
                        citing_rows.append((ceid, ctitle))

                citing_eids = " | ".join([x[0] for x in citing_rows if x[0]])
                citing_titles = " | ".join([x[1] for x in citing_rows if x[1]])
                citing_count_from_search = len(citing_rows)

        except Exception:
            citing_eids = ""
            citing_titles = ""
            citing_count_from_search = 0

        row = {
            "eid": eid,
            "title": title,
            "authors": authors,
            "author_ids": author_ids,
            "author_afids": author_afids,
            "year": year,
            "cover_date": cover_date,
            "publication_name": publication_name,
            "doi": doi,
            "citedby_count": citedby_count,
            "keywords": keywords,
            "affiliation_ids": affiliation_ids,
            "affiliation_names": affiliation_names,
            "affiliation_countries": affiliation_countries,
            "references": references,
            "references_count": references_count,
            "citing_eids": citing_eids,
            "citing_titles": citing_titles,
            "citing_count_from_search": citing_count_from_search,
        }

        rows.append(row)

    return pd.DataFrame(rows)


# =========================
# 4. Helpers
# =========================
def safe_split(value, sep=";"):
    """
    把字符串按 sep 拆开，去掉空白和空值
    """
    if pd.isna(value) or value is None:
        return []
    value = str(value).strip()
    if value == "":
        return []
    parts = [x.strip() for x in value.split(sep)]
    return [x for x in parts if x != ""]


def build_affiliation_mapping(affiliation_ids, affiliation_names, affiliation_countries):
    """
    为每篇论文建立:
    affiliation_id -> {name, country}
    """
    ids = safe_split(affiliation_ids, sep=";")
    names = safe_split(affiliation_names, sep=";")
    countries = safe_split(affiliation_countries, sep=";")

    max_len = max(len(ids), len(names), len(countries), 0)

    ids += [None] * (max_len - len(ids))
    names += [None] * (max_len - len(names))
    countries += [None] * (max_len - len(countries))

    mapping = {}
    for aff_id, aff_name, aff_country in zip(ids, names, countries):
        if aff_id is None or aff_id == "":
            continue
        mapping[str(aff_id)] = {
            "affiliation_name": aff_name,
            "affiliation_country": aff_country
        }
    return mapping


def paper_to_author_affiliation_rows(row):
    """
    把一篇论文展开成多行：
    一行 = 一个作者 × 一个机构

    关键逻辑：
    - authors: 作者之间用 ;
    - author_ids: 作者之间用 ;
    - author_afids: 作者之间用 ;，同一作者多个机构用 -
    """
    authors = safe_split(row["authors"], sep=";")
    author_ids = safe_split(row["author_ids"], sep=";")
    author_afids = safe_split(row["author_afids"], sep=";")

    n = max(len(authors), len(author_ids), len(author_afids), 0)

    authors += [None] * (n - len(authors))
    author_ids += [None] * (n - len(author_ids))
    author_afids += [None] * (n - len(author_afids))

    aff_map = build_affiliation_mapping(
        row["affiliation_ids"],
        row["affiliation_names"],
        row["affiliation_countries"]
    )

    out_rows = []

    for author_name, author_id, author_aff_str in zip(authors, author_ids, author_afids):
        # 某个作者可能没有机构
        if author_aff_str is None or str(author_aff_str).strip() == "":
            out_rows.append({
                "eid": row["eid"],
                "title": row["title"],
                "year": row["year"],
                "cover_date": row["cover_date"],
                "publication_name": row["publication_name"],
                "doi": row["doi"],
                "citedby_count": row["citedby_count"],
                "keywords": row["keywords"],
                "parsed_author_name": author_name,
                "parsed_author_id": str(author_id) if author_id is not None else None,
                "parsed_author_affiliation_id": None,
                "parsed_author_affiliation_name": None,
                "parsed_author_affiliation_country": None
            })
            continue

        # 同一作者多个机构，用 -
        aff_ids_for_author = safe_split(author_aff_str, sep="-")

        # 如果一个作者没有有效机构ID，也保留一行
        if len(aff_ids_for_author) == 0:
            out_rows.append({
                "eid": row["eid"],
                "title": row["title"],
                "year": row["year"],
                "cover_date": row["cover_date"],
                "publication_name": row["publication_name"],
                "doi": row["doi"],
                "citedby_count": row["citedby_count"],
                "keywords": row["keywords"],
                "parsed_author_name": author_name,
                "parsed_author_id": str(author_id) if author_id is not None else None,
                "parsed_author_affiliation_id": None,
                "parsed_author_affiliation_name": None,
                "parsed_author_affiliation_country": None
            })
            continue

        # 一位作者对应多个机构 -> 多行
        for aff_id in aff_ids_for_author:
            aff_id = str(aff_id).strip()
            aff_info = aff_map.get(aff_id, {})

            out_rows.append({
                "eid": row["eid"],
                "title": row["title"],
                "year": row["year"],
                "cover_date": row["cover_date"],
                "publication_name": row["publication_name"],
                "doi": row["doi"],
                "citedby_count": row["citedby_count"],
                "keywords": row["keywords"],
                "parsed_author_name": author_name,
                "parsed_author_id": str(author_id) if author_id is not None else None,
                "parsed_author_affiliation_id": aff_id,
                "parsed_author_affiliation_name": aff_info.get("affiliation_name"),
                "parsed_author_affiliation_country": aff_info.get("affiliation_country")
            })

    return out_rows


def build_author_long(df_paper):
    """
    从 paper-level dataframe 构造 author-affiliation long dataframe
    """
    all_rows = []

    for _, row in df_paper.iterrows():
        expanded_rows = paper_to_author_affiliation_rows(row)
        all_rows.extend(expanded_rows)

    df_long = pd.DataFrame(all_rows)

    # 防止 Excel 把 author_id 变成科学计数法，尽量保留字符串
    for col in ["parsed_author_id", "parsed_author_affiliation_id", "eid", "doi"]:
        if col in df_long.columns:
            df_long[col] = df_long[col].astype("string")

    return df_long


# =========================
# 5. Main
# =========================
if __name__ == "__main__":
    init(keys=[API_KEY])

    configs = [
        ("econ_strict", "gender_gap_econ_strict"),
        ("econ_plus", "gender_gap_econ_plus"),
        ("social_sciences_all", "gender_gap_social_sciences_all"),
    ]

    for mode, base_filename in configs:
        print(f"Running mode: {mode}")

        query = build_query(mode=mode)

        # paper-level
        df_paper = search_scopus(query)

        # 保存 paper-level
        paper_file = f"{base_filename}_paper.csv"
        df_paper.to_csv(paper_file, index=False, encoding="utf-8-sig")

        # author-affiliation long
        df_author_long = build_author_long(df_paper)

        # 保存 long-level
        long_file = f"{base_filename}_author_long.csv"
        df_author_long.to_csv(long_file, index=False, encoding="utf-8-sig")

        print(f"{paper_file}: {len(df_paper)} rows")
        print(f"{long_file}: {len(df_author_long)} rows")
        print("-" * 50)
