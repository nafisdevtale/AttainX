"""Vercel entry point for Smart CO PO AttainX."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
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

if not APP_FILE.is_file():
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


def _uncapped_target_attainment_percentage(final_score, target_score):
    if _module.pd.isna(target_score) or float(target_score) <= 0:
        return 0.0
    if _module.pd.isna(final_score):
        return 0.0
    return (float(final_score) / float(target_score)) * 100.0


_module.target_attainment_percentage = _uncapped_target_attainment_percentage
_original_new_pos = _module.calculate_dashboard_new_pos


def _find_survey_header_row(raw_frame):
    candidates = []
    for index, row in raw_frame.iterrows():
        values = [str(value).strip().upper() for value in row.tolist()]
        co_columns = [
            value for value in values
            if re.match(r"^C[A-Z0-9_-]*[._-]?\d+$", value)
        ]
        if co_columns:
            candidates.append((index, len(co_columns)))
    if not candidates:
        raise ValueError(
            "The New-PO Survey Sheet must contain CO columns (for example, C401.1, C401.2, etc.)."
        )
    return max(candidates, key=lambda item: (item[1], -item[0]))[0]


def _calculate_new_pos_with_survey(
    mapping_file, direct_file, base_threshold, has_practical, practical_only=False
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

    if not has_request_context():
        raise RuntimeError(
            "A survey upload is required for Standard Theory / Practical New-PO courses."
        )
    indirect_file = flask_request.files.get("indirect_file")
    if indirect_file is None or not getattr(indirect_file, "filename", "").strip():
        raise ValueError(
            "Survey Sheet (Indirect Ratings) is required for Standard Theory / Practical courses, including New POs."
        )

    survey_bytes = indirect_file.stream.read()
    indirect_file.stream.seek(0)
    if not survey_bytes:
        raise ValueError("The uploaded Survey Sheet is empty.")

    raw_survey = _module.pd.read_csv(io.BytesIO(survey_bytes), header=None, dtype=object)
    number_of_cos = len(co_statements)
    if number_of_cos == 0:
        raise ValueError("No CO statements were found in the mapping sheet.")

    survey_header = _find_survey_header_row(raw_survey)
    df_survey = _module.pd.read_csv(io.BytesIO(survey_bytes), header=survey_header)
    df_survey.columns = df_survey.columns.astype(str).str.strip().str.upper()
    df_survey = df_survey.loc[
        :, ~df_survey.columns.astype(str).str.contains("^UNNAMED", case=False, na=False)
    ]

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

    survey_columns = [
        column for column in df_survey.columns
        if re.match(r"^C[A-Z0-9_-]*[._-]?\d+$", str(column).strip().upper())
    ]
    if len(survey_columns) < number_of_cos:
        raise ValueError(
            f"The Survey Sheet contains {len(survey_columns)} CO columns, but the mapping sheet has {number_of_cos} COs."
        )

    normalized_survey_columns = {
        re.sub(r"\s+", "", str(column).strip().upper()): column
        for column in survey_columns
    }
    aligned_columns = []
    for index, co_row in theory_rows.iterrows():
        co_code = re.sub(r"\s+", "", str(co_row[co_column]).strip().upper())
        if co_code in normalized_survey_columns:
            aligned_columns.append(normalized_survey_columns[co_code])
        else:
            if len(survey_columns) < number_of_cos:
                raise ValueError(
                    f"Survey column for {co_code} was not found. Add one survey column for each mapped CO."
                )
            aligned_columns.append(survey_columns[index])

    if len(df_survey.columns) > 0:
        df_survey = df_survey.dropna(subset=[df_survey.columns[0]])
    for column in aligned_columns:
        df_survey[column] = _module.pd.to_numeric(df_survey[column], errors="coerce")

    direct_high = float(base_threshold) / 100.0
    direct_mid = (float(base_threshold) - 15.0) / 100.0
    direct_low = (float(base_threshold) - 30.0) / 100.0
    survey_high = direct_high - 0.10
    survey_mid = direct_mid - 0.10
    survey_low = direct_low - 0.10

    indirect_values = [
        _module.compute_survey_attainment(
            df_survey[column], survey_low, survey_mid, survey_high
        )
        for column in aligned_columns
    ]

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
        numeric_weights = [0.0 if value is None else float(value) for value in weights]
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
                "direct": "0.0000", "indirect": "0.0000",
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

app = _module.app
