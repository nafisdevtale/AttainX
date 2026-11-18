"""Vercel entry point for Smart CO PO AttainX."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import csv
import io
import re
import sys
import zipfile

from flask import has_request_context, request as flask_request

ROOT = Path(__file__).resolve().parent
BUNDLE_CANDIDATES = (ROOT / "obe-source.zip", ROOT / "obe-source (1).zip")
BUNDLE = next((path for path in BUNDLE_CANDIDATES if path.is_file()), None)

EXTRACT_ROOT = Path("/tmp/attainx-source")
APP_DIR = EXTRACT_ROOT / "obe-po-attainment-dashboard-github"
APP_FILE = APP_DIR / "app.py"

if not APP_FILE.is_file() or (BUNDLE is not None and BUNDLE.stat().st_mtime > APP_FILE.stat().st_mtime):
    if BUNDLE is None:
        expected = ", ".join(path.name for path in BUNDLE_CANDIDATES)
        raise FileNotFoundError(f"AttainX source archive not found. Expected one of: {expected}")
    EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BUNDLE) as archive:
        archive.extractall(EXTRACT_ROOT)

if not APP_FILE.is_file():
    raise RuntimeError("AttainX source bundle is missing its app.py entry point.")

sys.path.insert(0, str(APP_DIR))
_spec = spec_from_file_location("_attainx_application", APP_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Unable to load the AttainX Flask application.")

_module = module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

SUPPORTED_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")


def decode_csv_content(file_or_source, file_label=None):
    filename = file_label
    if not filename:
        filename = getattr(file_or_source, "filename", None)
    if not filename and hasattr(file_or_source, "name"):
        filename = getattr(file_or_source, "name")
    if not filename:
        filename = "uploaded CSV file"

    raw_bytes = None

    if hasattr(file_or_source, "stream"):
        stream = file_or_source.stream
        try:
            stream.seek(0)
        except Exception:
            pass
        raw_bytes = stream.read()
        try:
            stream.seek(0)
        except Exception:
            pass
        try:
            file_or_source.seek(0)
        except Exception:
            pass
    elif hasattr(file_or_source, "seek") and hasattr(file_or_source, "read"):
        if isinstance(file_or_source, io.StringIO):
            return file_or_source.getvalue()
        try:
            file_or_source.seek(0)
        except Exception:
            pass
        raw_bytes = file_or_source.read()
        try:
            file_or_source.seek(0)
        except Exception:
            pass
    elif isinstance(file_or_source, (bytes, bytearray)):
        raw_bytes = bytes(file_or_source)
    elif isinstance(file_or_source, str):
        if Path(file_or_source).is_file():
            filename = Path(file_or_source).name
            raw_bytes = Path(file_or_source).read_bytes()
        else:
            return file_or_source
    elif isinstance(file_or_source, Path) and file_or_source.is_file():
        filename = file_or_source.name
        raw_bytes = file_or_source.read_bytes()

    if raw_bytes is None:
        raise ValueError(f"Unable to read content from '{filename}': Unrecognized input type.")

    for encoding in SUPPORTED_CSV_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    raise ValueError(
        f"Unable to decode '{filename}': invalid encoding. Supported encodings are UTF-8, "
        f"UTF-8 with BOM, and Windows-1252 (CP1252). Please ensure the file is saved with a supported encoding."
    )


_orig_module_read_csv = getattr(_module.pd, "_orig_pd_read_csv", _module.pd.read_csv)


def safe_read_csv(file_or_source, *args, **kwargs):
    file_label = kwargs.pop("file_label", None)
    if "encoding" in kwargs:
        try:
            return _orig_module_read_csv(file_or_source, *args, **kwargs)
        except (UnicodeDecodeError, UnicodeError):
            kwargs.pop("encoding", None)

    decoded_text = decode_csv_content(file_or_source, file_label=file_label)
    return _orig_module_read_csv(io.StringIO(decoded_text), *args, **kwargs)


_module.SUPPORTED_CSV_ENCODINGS = SUPPORTED_CSV_ENCODINGS
_module.decode_csv_content = decode_csv_content
_module.safe_read_csv = safe_read_csv
_module.pd.read_csv = safe_read_csv


def _uncapped_target_attainment_percentage(final_score, target_score):
    if _module.pd.isna(target_score) or float(target_score) <= 0:
        return 0.0
    if _module.pd.isna(final_score):
        return 0.0
    return (float(final_score) / float(target_score)) * 100.0


_module.target_attainment_percentage = _uncapped_target_attainment_percentage
_original_new_pos = _module.calculate_dashboard_new_pos


METADATA_COLUMN_PATTERNS = [
    r'^(?:SR\.?\s*NO\.?|S\.?\s*NO\.?|SERIAL\s*NO\.?|SR_NO)$',
    r'^(?:NAME|STUDENT\s*NAME|CANDIDATE\s*NAME)$',
    r'^(?:ROLL\s*NO\.?|ROLL\s*NUMBER|REG\.?\s*NO\.?|PRN|UID|ID)$',
    r'^(?:TIMESTAMP|TIME|DATE)$',
    r'^(?:EMAIL|EMAIL\s*ADDRESS)$',
    r'^(?:FEEDBACK|COMMENT|COMMENTS|REMARK|REMARKS|SUGGESTION|SUGGESTIONS)$',
    r'^(?:CLASS|DIVISION|DIV|BRANCH|YEAR|SEMESTER|SEM)$',
]


def is_metadata_column(col_name):
    norm = str(col_name).strip().upper()
    return any(re.match(p, norm) for p in METADATA_COLUMN_PATTERNS)


def is_candidate_co_column(col_name):
    s = str(col_name).strip().upper()
    if not s or s.startswith("UNNAMED") or is_metadata_column(s):
        return False
    if re.search(r'\bCO\s*[-_.]?\s*\d+', s):
        return True
    if re.search(r'\bC\s*[-_.]?\s*\d+', s):
        return True
    if re.search(r'\bCOURSE\s*OUTCOME\s*[-_.]?\s*\d+', s):
        return True
    if re.match(r'^C[A-Z0-9_-]*[._-]?\d+$', s):
        return True
    return False


def normalize_co_key(s):
    return re.sub(r'[^A-Z0-9]', '', str(s).strip().upper())


def extract_co_index(s):
    s_clean = str(s).strip().upper()
    m = re.search(r'\b(?:CO|COURSE\s*OUTCOME)\s*[-_.]?\s*(\d+)', s_clean)
    if m:
        return int(m.group(1))
    m = re.search(r'\bC[A-Z0-9_-]*[._-](\d+)', s_clean)
    if m:
        return int(m.group(1))
    m = re.search(r'\bC\s*[-_.]?\s*(\d+)', s_clean)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*$', s_clean)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)', s_clean)
    if m:
        return int(m.group(1))
    return None


def find_survey_header_row(rows):
    candidates = []
    for idx, row in enumerate(rows):
        co_count = sum(1 for val in row if is_candidate_co_column(val))
        if co_count > 0:
            candidates.append((idx, co_count))
    if not candidates:
        raise ValueError(
            "The Survey Sheet must contain Course Outcome (CO) rating columns (e.g., C301.1, CO1, CO 1, etc.)."
        )
    return max(candidates, key=lambda x: (x[1], -x[0]))[0]


def align_survey_columns(survey_columns, mapped_cos):
    number_of_cos = len(mapped_cos)
    if number_of_cos == 0:
        raise ValueError("No CO statements were found in the mapping sheet.")

    candidate_cols = [c for c in survey_columns if is_candidate_co_column(c)]
    if not candidate_cols:
        non_meta = [
            c for c in survey_columns
            if not is_metadata_column(c) and not str(c).strip().upper().startswith("UNNAMED")
        ]
        if len(non_meta) == number_of_cos:
            candidate_cols = non_meta

    if len(candidate_cols) < number_of_cos:
        missing_co = mapped_cos[len(candidate_cols)] if len(candidate_cols) < len(mapped_cos) else mapped_cos[-1]
        cand_indices = {extract_co_index(c) for c in candidate_cols if extract_co_index(c) is not None}
        for co in mapped_cos:
            idx = extract_co_index(co)
            if idx is not None and idx not in cand_indices:
                missing_co = co
                break
        raise ValueError(
            f"The Survey Sheet contains {len(candidate_cols)} CO columns, but the mapping sheet has {number_of_cos} COs. "
            f"Missing survey column for mapped CO: {missing_co}."
        )

    # Strategy 1: Exact or Normalized Code Match
    norm_survey_map = {normalize_co_key(c): c for c in candidate_cols}
    exact_matches = []
    all_exact = True
    for co in mapped_cos:
        k = normalize_co_key(co)
        if k in norm_survey_map:
            exact_matches.append(norm_survey_map[k])
        else:
            all_exact = False
            break
    if all_exact and len(exact_matches) == number_of_cos:
        return exact_matches

    # Strategy 2: Match by CO index (handles different prefixes, e.g. C410A.1 vs C301.1 or CO1)
    col_by_index = {}
    for c in candidate_cols:
        idx = extract_co_index(c)
        if idx is not None and idx not in col_by_index:
            col_by_index[idx] = c

    index_matches = []
    all_indexed = True
    missing_co_by_index = None
    for co in mapped_cos:
        idx = extract_co_index(co)
        if idx is not None and idx in col_by_index:
            index_matches.append(col_by_index[idx])
        else:
            all_indexed = False
            missing_co_by_index = co
            break

    if all_indexed and len(index_matches) == number_of_cos:
        return index_matches

    # Strategy 3: Positional matching
    # Positional matching is permitted only when the survey and mapping contain exactly the same number of COs
    if len(candidate_cols) == number_of_cos:
        return list(candidate_cols)

    # If alignment failed
    if missing_co_by_index:
        raise ValueError(f"Survey column for mapped CO '{missing_co_by_index}' was not found in the Survey Sheet.")
    raise ValueError(
        f"Could not unambiguously match survey columns to mapped COs ({len(candidate_cols)} candidate columns for {number_of_cos} mapped COs)."
    )


def process_indirect_survey(indirect_file, mapped_cos, base_threshold):
    if indirect_file is None:
        raise ValueError("Survey Sheet (Indirect Ratings) is required.")

    survey_name = getattr(indirect_file, "filename", None)
    if not survey_name and hasattr(indirect_file, "name"):
        survey_name = getattr(indirect_file, "name")
    if not survey_name:
        survey_name = "Survey Sheet"

    content = decode_csv_content(indirect_file, file_label=survey_name)
    rows = list(csv.reader(io.StringIO(content)))
    if not rows or not any(any(str(c).strip() for c in r) for r in rows):
        raise ValueError("The uploaded Survey Sheet is empty.")

    header_idx = find_survey_header_row(rows)
    df_survey = _orig_module_read_csv(io.StringIO(content), header=header_idx)
    df_survey.columns = df_survey.columns.astype(str).str.strip().str.upper()
    df_survey = df_survey.loc[:, ~df_survey.columns.astype(str).str.contains("^UNNAMED", case=False, na=False)]

    aligned_columns = align_survey_columns(df_survey.columns, mapped_cos)

    for col in aligned_columns:
        df_survey[col] = _module.pd.to_numeric(df_survey[col], errors="coerce")

    df_survey_clean = df_survey.dropna(subset=aligned_columns, how="all")
    if df_survey_clean.empty:
        raise ValueError("The Survey Sheet contains no valid student responses.")

    d_high = float(base_threshold) / 100.0
    d_mid = (float(base_threshold) - 15.0) / 100.0
    d_low = (float(base_threshold) - 30.0) / 100.0
    s_high = d_high - 0.10
    s_mid = d_mid - 0.10
    s_low = d_low - 0.10

    indirect_values = [
        _module.compute_survey_attainment(df_survey_clean[col], s_low, s_mid, s_high)
        for col in aligned_columns
    ]

    return indirect_values, df_survey_clean


def extract_cos_from_mapping(mapping_source):
    content = decode_csv_content(mapping_source, file_label="mapping_file")
    rows = list(csv.reader(io.StringIO(content)))
    header_idx = None
    for idx, row in enumerate(rows):
        if any("CO CODE" in str(c).upper() for c in row):
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("Could not find 'CO Codes' column in the mapping sheet.")

    co_col_idx = next(i for i, c in enumerate(rows[header_idx]) if "CO" in str(c).upper())
    co_codes = []
    for row in rows[header_idx + 1:]:
        if row and len(row) > co_col_idx:
            val = str(row[co_col_idx]).strip()
            val_u = val.upper()
            if not val or val_u in ("-", "NAN", "NONE"):
                continue
            if any(kw in val_u for kw in ("TOTAL", "TARGET", "AVERAGE", "WEIGHT", "PRACTICAL", "STATEMENT")):
                continue
            if val_u.startswith("C") or re.match(r"^[A-Z0-9_-]+[._-]?\d+$", val_u):
                co_codes.append(val)
    if not co_codes:
        raise ValueError("No Course Outcomes found in the mapping sheet.")
    return co_codes


def generate_survey_template_csv(co_codes):
    if not co_codes:
        raise ValueError("At least one Course Outcome (CO) is required to generate a survey template.")
    pad = "," * len(co_codes)
    line1 = f",Survey for Indirect Attainment Only{pad}"
    line2 = "Sr. No.,Name ," + ",".join(co_codes)
    return f"\ufeff{line1}\r\n{line2}\r\n"


_module.extract_cos_from_mapping = extract_cos_from_mapping
_module.generate_survey_template_csv = generate_survey_template_csv


def _calculate_new_pos_with_survey(
    mapping_file, direct_file, base_threshold, has_practical, practical_only=False, indirect_file=None
):
    """Standard New-PO courses use 80:20; Only Practical uses 100:0."""
    results, df_map, df_direct, _empty_indirect, co_statements, practical_statements = (
        _original_new_pos(
            mapping_file,
            direct_file,
            base_threshold,
            has_practical,
            practical_only=practical_only,
        )
    )

    if practical_only:
        return (
            results, df_map, df_direct, _module.pd.DataFrame(),
            co_statements, practical_statements,
        )

    if indirect_file is None:
        if not has_request_context():
            raise RuntimeError(
                "A survey upload is required for Standard Theory / Practical New-PO courses."
            )
        indirect_file = flask_request.files.get("indirect_file")

    if indirect_file is None or not getattr(indirect_file, "filename", "file").strip():
        raise ValueError(
            "Survey Sheet (Indirect Ratings) is required for Standard Theory / Practical courses, including New POs."
        )

    number_of_cos = len(co_statements)
    if number_of_cos == 0:
        raise ValueError("No CO statements were found in the mapping sheet.")

    co_candidates = [column for column in df_map.columns if "CO" in str(column).upper()]
    if not co_candidates:
        raise ValueError("The mapping sheet must contain a CO Codes column.")
    co_column = co_candidates[0]
    theory_rows = df_map[
        df_map[co_column].astype(str).str.strip().str.upper().str.startswith("C", na=False)
    ].reset_index(drop=True)
    if len(theory_rows) != number_of_cos:
        raise ValueError(
            "The number of CO rows in the mapping sheet does not match the CO summary."
        )

    mapped_cos = theory_rows[co_column].astype(str).str.strip().tolist()

    indirect_values, df_survey = process_indirect_survey(
        indirect_file, mapped_cos, base_threshold
    )

    for index, statement in enumerate(co_statements):
        raw_direct = float(statement.get("direct", 0.0))
        raw_indirect = float(indirect_values[index])
        statement["indirect"] = f"{raw_indirect:.4f}"
        statement["final"] = f"{(0.80 * raw_direct + 0.20 * raw_indirect):.4f}"

    po_columns = [
        column for column in df_map.columns
        if re.match(r"^(PO\d+|PSO\d+)$", str(column).strip().upper())
    ]
    mapping_weights = {}
    for po_column in po_columns:
        weights = [_module.parse_mapping_value(value) for value in theory_rows[po_column].tolist()]
        numeric_weights = [
            0.0 if (value is None or float(value) <= 0) else float(value)
            for value in weights
        ]
        weight_total = float(sum(numeric_weights))
        if weight_total <= 0:
            mapping_weights[po_column] = (0.0, 0.0)
            continue
        indirect_po_raw = sum(
            indirect_values[index] * numeric_weights[index]
            for index in range(number_of_cos)
        ) / weight_total
        mapping_weights[po_column] = (weight_total, indirect_po_raw)

    for row in results:
        po_name = str(row.get("po", "")).strip().upper()
        match = next(
            (column for column in po_columns if str(column).strip().upper() == po_name),
            None,
        )
        if match is None:
            continue
        weight_total, indirect_po_raw = mapping_weights.get(match, (0.0, 0.0))
        if weight_total <= 0:
            row.update({
                "target": "0.00", "direct": "0.0000", "indirect": "0.0000",
                "final": "0.0000", "percentage": "0.00",
            })
            continue

        direct_po_raw = float(row.get("direct", 0.0))
        direct_contribution = 0.80 * direct_po_raw
        indirect_contribution = 0.20 * indirect_po_raw
        final_po = direct_contribution + indirect_contribution
        target = float(row.get("target", 0.0))
        percentage = (final_po / target) * 100.0 if target > 0 else 0.0

        row["direct"] = f"{direct_contribution:.4f}"
        row["indirect"] = f"{indirect_contribution:.4f}"
        row["final"] = f"{final_po:.4f}"
        row["percentage"] = f"{percentage:.2f}"

    return results, df_map, df_direct, df_survey, co_statements, practical_statements


_module.calculate_dashboard_new_pos = _calculate_new_pos_with_survey

_original_render_template = _module.render_template


def _render_template_with_evaluation_flags(template_name, *args, **kwargs):
    if template_name == "dashboard.html":
        course_type = str(kwargs.get("course_type", "theory")).strip().lower()
        is_project = bool(kwargs.get("is_project")) or course_type == "project"
        is_practical_only = course_type == "practical"
        kwargs["is_direct_only"] = is_project or is_practical_only
        kwargs["show_indirect"] = not (is_project or is_practical_only)
        kwargs["show_co_indirect"] = False
        if not (is_project or is_practical_only):
            kwargs["direct_formula_tooltip"] = (
                "Direct CO attainment is calculated from the selected assessment components; "
                "Final CO Attainment = (0.80 × Direct CO) + (0.20 × Indirect Survey CO)."
            )
    return _original_render_template(template_name, *args, **kwargs)


_module.render_template = _render_template_with_evaluation_flags

upload_template = APP_DIR / "templates" / "upload_form.html"
if upload_template.is_file():
    template_text = upload_template.read_text(encoding="utf-8")
    template_text = re.sub(
        r'\s*<small\s+id="practical_only_note"[\s\S]*?</small>',
        "",
        template_text,
        count=1,
    )
    template_text = re.sub(
        r'^\s*const practicalOnlyNote = document\.getElementById\("practical_only_note"\);\s*\n',
        "",
        template_text,
        flags=re.MULTILINE,
    )
    template_text = re.sub(
        r'^\s*practicalOnlyNote\.style\.display = isPracticalOnly \? "block" : "none";\s*\n',
        "",
        template_text,
        flags=re.MULTILINE,
    )
    template_text = template_text.replace(
        'const usesSurvey = !isProject && !isPracticalOnly && poFormat !== "new_pos";',
        'const usesSurvey = !isProject && !isPracticalOnly;',
    )
    template_text = template_text.replace(
        "3. Survey Sheet (Indirect Ratings — Old POs only)",
        "3. Survey Sheet (Indirect Ratings)",
    )

    existing_course = '                    "Sem IV | IC124PC404 — Digital Electronics Lab",\n'
    vocational_course = (
        '                    "Sem IV | IC124VC408 — Vocational and Skill Enhancement Course 3",\n'
    )
    if existing_course in template_text and vocational_course not in template_text:
        template_text = template_text.replace(
            existing_course, existing_course + vocational_course, 1
        )

    existing_teacher = '                <option value="Mrs. A. S. Nandangaon">Mrs. A. S. Nandangaon</option>\n'
    new_teachers = (
        '                <option value="Dr. Hnnie Williams">Dr. Hnnie Williams</option>\n'
        '                <option value="Dr. Yogita Talekar">Dr. Yogita Talekar</option>\n'
        '                <option value="Miss. Prachi Bhende">Miss. Prachi Bhende</option>\n'
    )
    if "Dr. Hniee Williams" in template_text:
        template_text = template_text.replace("Dr. Hniee Williams", "Dr. Hnnie Williams")
    elif existing_teacher in template_text and new_teachers not in template_text:
        template_text = template_text.replace(
            existing_teacher, existing_teacher + new_teachers, 1
        )

    old_class_select = (
        '            <select name="class_name" id="class_select" onchange="updateSubjects()" required>\n'
        '                <option value="" disabled selected>-- Select Class --</option>\n'
        '                <option value="SE">SE (Second Year)</option>\n'
        '                <option value="SY B Tech">SY B Tech</option>\n'
        '                <option value="TY B Tech">TY B Tech</option>\n'
        '                <option value="TE">TE (Third Year)</option>\n'
        '                <option value="BE">BE (Final Year)</option>\n'
        '            </select>'
    )
    new_class_select = (
        '            <select name="class_name" id="class_select" onchange="updateSubjects()" required>\n'
        '                <option value="" disabled selected>-- Select Class --</option>\n'
        '                <option value="FY B Tech">FY B Tech</option>\n'
        '                <option value="SE">SE (Second Year)</option>\n'
        '                <option value="SY B Tech">SY B Tech</option>\n'
        '                <option value="TY B Tech">TY B Tech</option>\n'
        '                <option value="TE">TE (Third Year)</option>\n'
        '                <option value="BE">BE (Final Year)</option>\n'
        '            </select>'
    )
    if old_class_select in template_text:
        template_text = template_text.replace(old_class_select, new_class_select, 1)

    old_theory_start = '        const subjectData = {\n            "theory": {\n                "SE": [\n'
    new_theory_start = (
        '        const subjectData = {\n'
        '            "theory": {\n'
        '                "FY B Tech": [\n'
        '                    "ET124ES103 \u2014 Electrical and Electronics engineering"\n'
        '                ],\n'
        '                "SE": [\n'
    )
    if old_theory_start in template_text:
        template_text = template_text.replace(old_theory_start, new_theory_start, 1)

    old_fy_theory_obj = (
        '                "FY B Tech": [\n'
        '                    { code: "ET124ES103", name: "Electrical and Electronics engineering", subject_code: "ET124ES103", subject_name: "Electrical and Electronics engineering" }\n'
        '                ],\n'
    )
    new_fy_theory_str = (
        '                "FY B Tech": [\n'
        '                    "ET124ES103 \u2014 Electrical and Electronics engineering"\n'
        '                ],\n'
    )
    if old_fy_theory_obj in template_text:
        template_text = template_text.replace(old_fy_theory_obj, new_fy_theory_str, 1)

    old_project_start = '            "project": {\n                "SE": [\n'
    new_project_start = '            "project": {\n                "FY B Tech": [],\n                "SE": [\n'
    if old_project_start in template_text:
        template_text = template_text.replace(old_project_start, new_project_start, 1)

    old_practical_start = '            "practical": {\n                "SY B Tech": [\n'
    new_practical_start = (
        '            "practical": {\n'
        '                "FY B Tech": [\n'
        '                    "ET124ES105 \u2014 Electrical and Electronics engineering"\n'
        '                ],\n'
        '                "SY B Tech": [\n'
    )
    if old_practical_start in template_text:
        template_text = template_text.replace(old_practical_start, new_practical_start, 1)

    old_fy_practical_obj = (
        '                "FY B Tech": [\n'
        '                    { code: "ET124ES105", name: "Electrical and Electronics engineering", subject_code: "ET124ES105", subject_name: "Electrical and Electronics engineering" }\n'
        '                ],\n'
    )
    new_fy_practical_str = (
        '                "FY B Tech": [\n'
        '                    "ET124ES105 \u2014 Electrical and Electronics engineering"\n'
        '                ],\n'
    )
    if old_fy_practical_obj in template_text:
        template_text = template_text.replace(old_fy_practical_obj, new_fy_practical_str, 1)

    old_update_loop = (
        '            if (subjectData[courseType] && subjectData[courseType][selectedClass]) {\n'
        '                subjectData[courseType][selectedClass].forEach(function(subject) {\n'
        '                    const option = document.createElement("option");\n'
        '                    option.value = subject;\n'
        '                    option.text = subject;\n'
        '                    subjectSelect.appendChild(option);\n'
        '                });\n'
        '            }'
    )
    new_update_loop = (
        '            if (subjectData[courseType] && subjectData[courseType][selectedClass]) {\n'
        '                subjectData[courseType][selectedClass].forEach(function(subject) {\n'
        '                    const option = document.createElement("option");\n'
        '                    if (typeof subject === "object" && subject !== null) {\n'
        '                        const label = subject.label || (subject.code && subject.name ? subject.code + " \u2014 " + subject.name : (subject.code || subject.name));\n'
        '                        option.value = label;\n'
        '                        option.text = label;\n'
        '                        if (subject.code || subject.subject_code) {\n'
        '                            option.setAttribute("data-code", subject.code || subject.subject_code);\n'
        '                        }\n'
        '                        if (subject.name || subject.subject_name) {\n'
        '                            option.setAttribute("data-name", subject.name || subject.subject_name);\n'
        '                        }\n'
        '                    } else {\n'
        '                        option.value = subject;\n'
        '                        option.text = subject;\n'
        '                        if (typeof subject === "string" && subject.includes(" \u2014 ")) {\n'
        '                            const parts = subject.split(" \u2014 ");\n'
        '                            option.setAttribute("data-code", parts[0].trim());\n'
        '                            option.setAttribute("data-name", parts[1].trim());\n'
        '                        }\n'
        '                    }\n'
        '                    subjectSelect.appendChild(option);\n'
        '                });\n'
        '            }'
    )
    if old_update_loop in template_text:
        template_text = template_text.replace(old_update_loop, new_update_loop, 1)

    template_text = template_text.replace(
        '            if (poFormatSelect === "new_pos") {\n                // New POs are direct-only; the survey upload is hidden and optional.\n',
        '            if (poFormatSelect === "new_pos") {\n'
        '                indirectLink.href = "/static/indirect_newpos_template.csv";\n'
        '                indirectLink.setAttribute("download", "indirect_newpos_template.csv");\n'
        '                indirectLink.innerHTML = "📥 New POs Survey Template";\n',
        1,
    )
    upload_template.write_text(template_text, encoding="utf-8")

dashboard_template = APP_DIR / "templates" / "dashboard.html"
if dashboard_template.is_file():
    template_text = dashboard_template.read_text(encoding="utf-8")
    template_text = template_text.replace(
        "Formula: min((Final PO / Target Mapping) × 100, 100%). Display is capped at 100%.",
        "Formula: (Final PO Attainment / PO Mapping) × 100. Values above 100% are valid when attainment exceeds the mapped target.",
    )
    template_text = template_text.replace(
        "Target achievement for {{ row.po }}; capped at 100%",
        "Final PO Attainment / PO Mapping × 100 for {{ row.po }}; not capped",
    )

    old_co_summary_tbody = (
        '            <tbody>\n'
        '                <tr>\n'
        '                    <td rowspan="2" style="font-weight: bold; background-color: #f8f9fa; font-size: 16px; text-align: center !important; vertical-align: middle;">{{ subject }}</td>\n'
        '                    \n'
        '                    <td style="color: #0056b3; text-align: left !important;"><strong data-tooltip="{{ direct_formula_tooltip }}">Direct {% if is_direct_only %}(100%){% else %}(80%){% endif %}</strong></td>\n'
        '                    {% for co in co_statements %}\n'
        '                        <td style="color: #0056b3; text-align: center !important;" data-tooltip="Direct Exam Score for {{ co.code }}">{{ co.direct }}</td>\n'
        '                    {% endfor %}\n'
        '                </tr>\n'
        '                \n'
        '                \n'
        '                <tr>\n'
        '                    <td style="background-color: #e9ecef; text-align: left !important;"><strong data-tooltip="Formula: {% if is_direct_only %}Direct CO (100%){% else %}(0.80 × Direct CO) + (0.20 × Indirect CO){% endif %}">Final CO Attainment</strong></td>\n'
        '                    {% for co in co_statements %}\n'
        '                        <td style="font-weight: bold; background-color: #e9ecef; font-size: 15px; text-align: center !important;" data-tooltip="Final blended score for {{ co.code }}">{{ co.final }}</td>\n'
        '                    {% endfor %}\n'
        '                </tr>\n'
        '            </tbody>'
    )
    new_co_summary_tbody = (
        '            <tbody>\n'
        '                <tr>\n'
        '                    <td style="font-weight: bold; background-color: #f8f9fa; font-size: 16px; text-align: center !important; vertical-align: middle;">{{ subject }}</td>\n'
        '                    <td style="background-color: #e9ecef; text-align: left !important;"><strong>Final CO Attainment</strong></td>\n'
        '                    {% for co in co_statements %}\n'
        '                        <td style="font-weight: bold; background-color: #e9ecef; color: #0056b3; font-size: 15px; text-align: center !important;" data-tooltip="Direct Exam Score for {{ co.code }}">{{ co.direct }}</td>\n'
        '                    {% endfor %}\n'
        '                </tr>\n'
        '            </tbody>'
    )
    if old_co_summary_tbody in template_text:
        template_text = template_text.replace(old_co_summary_tbody, new_co_summary_tbody, 1)

    # Keep the PO Indirect row and survey appendix, but hide the CO-summary
    # Indirect column as previously requested.
    co_summary_marker = "CO Attainment Summary"
    co_summary_start = template_text.find(co_summary_marker)
    if co_summary_start >= 0:
        co_table_end = template_text.find("</table>", co_summary_start)
        if co_table_end >= 0:
            co_section = template_text[co_summary_start:co_table_end]
            co_section = co_section.replace(
                "{% if show_indirect %}", "{% if show_co_indirect %}"
            )
            template_text = (
                template_text[:co_summary_start]
                + co_section
                + template_text[co_table_end:]
            )
    dashboard_template.write_text(template_text, encoding="utf-8")


# OLD POs (11), CO(6): generate dedicated 11-PO mapping templates and
# enforce the same 6-CO / 11-PO structure in processing and output.
def _write_old_pos_11_template(source_name, target_name):
    static_dir = APP_DIR / "public" / "static"
    source_path = static_dir / source_name
    target_path = static_dir / target_name
    content = decode_csv_content(source_path, file_label=source_name)
    rows = list(csv.reader(io.StringIO(content)))

    header_index = next(
        (
            index for index, row in enumerate(rows)
            if any(str(cell).strip().upper() == "PO12" for cell in row)
        ),
        None,
    )
    if header_index is None:
        raise RuntimeError(f"Cannot build {target_name}: PO12 header not found in {source_name}.")

    po12_index = next(
        index for index, cell in enumerate(rows[header_index])
        if str(cell).strip().upper() == "PO12"
    )
    trimmed_rows = [
        [cell for index, cell in enumerate(row) if index != po12_index]
        for row in rows
    ]

    headers = [str(cell).strip().upper() for cell in trimmed_rows[header_index]]
    expected_pos = [f"PO{number}" for number in range(1, 12)]
    missing_pos = [po for po in expected_pos if po not in headers]
    if missing_pos or "PO12" in headers:
        raise RuntimeError(
            f"Invalid generated template {target_name}: expected PO1-PO11 only; "
            f"missing={missing_pos}, contains_PO12={'PO12' in headers}."
        )

    co_rows = [
        row for row in trimmed_rows[header_index + 1:]
        if row and str(row[0]).strip().upper().startswith("C")
    ]
    if len(co_rows) != 6:
        raise RuntimeError(
            f"Invalid generated template {target_name}: expected exactly 6 CO rows, found {len(co_rows)}."
        )

    with target_path.open("w", newline="", encoding="utf-8") as target_file:
        csv.writer(target_file, lineterminator="\n").writerows(trimmed_rows)


static_dir = APP_DIR / "public" / "static"
_write_old_pos_11_template("mapping_template.csv", "mapping_11po_template.csv")
_write_old_pos_11_template(
    "mapping_practical_template.csv",
    "mapping_11po_practical_template.csv",
)

_original_old_pos_calculator = _module.calculate_dashboard_old_pos


def _calculate_old_pos_with_11po_guard(
    mapping_file, direct_file, indirect_file, base_threshold,
    has_practical, exclude_po12=False
):
    result = _original_old_pos_calculator(
        mapping_file, direct_file, indirect_file, base_threshold,
        has_practical, exclude_po12=exclude_po12
    )
    if not exclude_po12:
        return result

    results, df_map, df_direct, df_survey, co_statements, practical_statements = result
    co_columns = [column for column in df_map.columns if "CO" in str(column).upper()]
    if not co_columns:
        raise ValueError("The Old POs (11), CO(6) mapping sheet must contain a CO Codes column.")

    co_column = co_columns[0]
    co_mask = (
        df_map[co_column].astype(str).str.strip().str.upper().str.startswith("C", na=False)
    )
    co_count = int(co_mask.sum())
    if co_count != 6:
        raise ValueError(
            f"OLD POs (11), CO(6) requires exactly 6 Course Outcomes; "
            f"the uploaded mapping sheet contains {co_count}."
        )

    expected_pos = {f"PO{number}" for number in range(1, 12)}
    present_pos = {
        str(column).strip().upper()
        for column in df_map.columns
        if re.fullmatch(r"PO\d+", str(column).strip().upper())
    }
    missing_pos = sorted(
        expected_pos - present_pos,
        key=lambda value: int(value[2:])
    )
    if missing_pos:
        raise ValueError(
            "OLD POs (11), CO(6) requires mapping columns PO1 through PO11. "
            f"Missing columns: {', '.join(missing_pos)}."
        )

    columns_to_keep = [
        column for column in df_map.columns
        if not re.fullmatch(r"PO\d+", str(column).strip().upper())
        or str(column).strip().upper() in expected_pos
    ]
    df_map = df_map.loc[:, columns_to_keep].copy()
    results = [
        row for row in results
        if str(row.get("po", "")).strip().upper() in expected_pos
        or str(row.get("po", "")).strip().upper() in {"PSO1", "PSO2", "PSO3"}
    ]
    return results, df_map, df_direct, df_survey, co_statements, practical_statements


_module.calculate_dashboard_old_pos = _calculate_old_pos_with_11po_guard

if upload_template.is_file():
    template_text = upload_template.read_text(encoding="utf-8")
    template_text = template_text.replace(
        "OLD POs (11), CO(6) (Exclude PO12)",
        "OLD POs (11), CO(6)",
    )

    old_pos_11_template_branch = "\n".join([
        '            if (poFormatSelect === "old_pos_11") {',
        '                indirectLink.href = "/static/indirect_template.csv";',
        '                indirectLink.setAttribute("download", "indirect_template.csv");',
        '',
        '                if (practicalSelect === "yes") {',
        '                    mappingLink.href = "/static/mapping_11po_practical_template.csv";',
        '                    directLink.href = "/static/direct_practical_template.csv";',
        '                    mappingLink.setAttribute("download", "mapping_11po_practical_template.csv");',
        '                    directLink.setAttribute("download", "direct_practical_template.csv");',
        '                    mappingLink.innerHTML = "📥 Practical Mapping";',
        '                    directLink.innerHTML = "📥 Practical Marks";',
        '                } else {',
        '                    mappingLink.href = "/static/mapping_11po_template.csv";',
        '                    directLink.href = "/static/direct_template.csv";',
        '                    mappingLink.setAttribute("download", "mapping_11po_template.csv");',
        '                    directLink.setAttribute("download", "direct_template.csv");',
        '                    mappingLink.innerHTML = "📥 Blank Template";',
        '                    directLink.innerHTML = "📥 Blank Template";',
        '                }',
        '            } else if (poFormatSelect === "new_pos") {',
    ])

    new_pos_anchor = '            if (poFormatSelect === "new_pos") {'
    if 'if (poFormatSelect === "old_pos_11")' not in template_text:
        if new_pos_anchor not in template_text:
            raise RuntimeError("Could not find the template toggle insertion point for OLD POs (11), CO(6).")
        template_text = template_text.replace(new_pos_anchor, old_pos_11_template_branch, 1)

    upload_template.write_text(template_text, encoding="utf-8")

app = _module.app
calculate_dashboard_old_pos = _module.calculate_dashboard_old_pos
calculate_dashboard_new_pos = _module.calculate_dashboard_new_pos

