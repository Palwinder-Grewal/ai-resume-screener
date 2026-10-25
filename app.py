"""
app.py — Streamlit dashboard for AI Resume Screener.

Run with:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import time

from core import parse_resume, score_candidate, RESUME_SCHEMA

# ─────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Resume Screener",
    page_icon="🎯",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────
# Minimal custom CSS
# ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .rec-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
    }
    .rec-strong   { background: #d1fae5; color: #065f46; }
    .rec-interview{ background: #dbeafe; color: #1e40af; }
    .rec-maybe    { background: #fef3c7; color: #92400e; }
    .rec-no       { background: #fee2e2; color: #991b1b; }
    .score-ring   { font-size: 2.2rem; font-weight: 700; }
    .skill-tag {
        display: inline-block;
        background: #f1f5f9;
        border-radius: 6px;
        padding: 2px 10px;
        margin: 2px;
        font-size: 0.82rem;
        color: #334155;
    }
    .skill-tag.matched { background: #d1fae5; color: #065f46; }
    .skill-tag.missing { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────
# Sidebar — Job requirements config
# ─────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Job requirements")
    st.caption("Configure the position you're hiring for.")

    job_title = st.text_input("Job title", value="Senior Data Scientist")
    min_exp   = st.slider("Minimum years of experience", 0, 20, 4)

    st.markdown("**Required skills** (one per line)")
    req_skills_raw = st.text_area(
        label="required_skills",
        value="Python\nSQL\nMachine Learning",
        height=100,
        label_visibility="collapsed",
    )

    st.markdown("**Preferred skills** (one per line)")
    pref_skills_raw = st.text_area(
        label="preferred_skills",
        value="PyTorch\nTensorFlow\nMLflow\nSpark",
        height=100,
        label_visibility="collapsed",
    )

    min_edu = st.selectbox(
        "Minimum education",
        options=["high_school", "bachelor", "master", "phd"],
        index=1,
    )

    st.divider()
    st.caption("Scoring weights: Experience 30 · Required skills 40 · Preferred 20 · Education 10")

# Build job requirements dict from sidebar
JOB_REQUIREMENTS = {
    "title":           job_title,
    "min_experience":  min_exp,
    "required_skills": [s.strip() for s in req_skills_raw.splitlines() if s.strip()],
    "preferred_skills":[s.strip() for s in pref_skills_raw.splitlines() if s.strip()],
    "min_education":   min_edu,
}

# ─────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────
st.title("🎯 AI Resume Screener")
st.markdown(f"Screening candidates for **{job_title}** · powered by GPT-4o mini")
st.divider()

# ─────────────────────────────────────────────────────────────────────────
# Input — paste resumes
# ─────────────────────────────────────────────────────────────────────────
st.subheader("📋 Paste resumes")
st.caption("Separate multiple resumes with a line containing only `---`")

DEFAULT_RESUMES = """\
Meera Iyer | meera.iyer@email.com
Senior Data Scientist at FinEdge Analytics — 6 years total experience.
M.Sc. Computer Science, IIT Bombay.
Skills: Python, SQL, TensorFlow, PyTorch, MLflow, Spark, scikit-learn, Tableau.
Languages: English, Hindi, Tamil.
Previous: Infosys (2 years), Wipro (1.5 years).
---
Arjun Sharma | arjun.s@mail.com
Junior Developer, 1.5 years experience.
B.E. IT, VIT Vellore.
Skills: HTML, CSS, JavaScript, React.
Previous company: WebCraft Solutions.
Languages: English, Telugu.
---
Dr. Sunita Rao
Lead ML Engineer at DeepTech Labs — 9 years experience.
Ph.D. in Machine Learning, IISc Bangalore.
Skills: Python, SQL, PyTorch, TensorFlow, Spark, MLflow, Kubernetes, R, Scala.
Former researcher at Microsoft Research and Google Brain.
Languages: English, Kannada."""

raw_input = st.text_area(
    label="Resumes",
    value=DEFAULT_RESUMES,
    height=200,
    label_visibility="collapsed",
)

run_btn = st.button("▶ Screen candidates", type="primary", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────
# Processing
# ─────────────────────────────────────────────────────────────────────────
if run_btn:
    resumes = [r.strip() for r in raw_input.split("---") if r.strip()]
    if not resumes:
        st.warning("Paste at least one resume above.")
        st.stop()

    results = []
    progress = st.progress(0, text="Starting…")
    status   = st.empty()

    for i, resume_text in enumerate(resumes):
        status.info(f"Parsing candidate {i+1} of {len(resumes)}…")
        progress.progress((i) / len(resumes))

        candidate = parse_resume(resume_text)

        if candidate is None or "_error" in candidate:
            err = candidate.get("_error", "Unknown error") if candidate else "Returned None"
            results.append({"_raw": resume_text, "_error": err})
            continue

        scores = score_candidate(candidate, JOB_REQUIREMENTS)
        results.append({**candidate, **scores, "_raw": resume_text})

        time.sleep(0.3)   # slight pause to avoid rate limits on free-tier

    progress.progress(1.0, text="Done!")
    status.empty()

    # ── Store results in session state so they survive reruns ─────────────
    st.session_state["results"]       = results
    st.session_state["job_reqs_used"] = dict(JOB_REQUIREMENTS)

# ─────────────────────────────────────────────────────────────────────────
# Results display
# ─────────────────────────────────────────────────────────────────────────
if "results" in st.session_state:
    results  = st.session_state["results"]
    job_used = st.session_state["job_reqs_used"]

    valid = [r for r in results if "_error" not in r]
    failed= [r for r in results if "_error" in r]

    # ── Summary bar ──────────────────────────────────────────────────────
    st.subheader("📊 Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total screened", len(results))
    col2.metric("🟢 Strong hire",  sum(1 for r in valid if r.get("recommendation") == "STRONG HIRE"))
    col3.metric("🔵 Interview",    sum(1 for r in valid if r.get("recommendation") == "PROCEED TO INTERVIEW"))
    col4.metric("🟡 Maybe",        sum(1 for r in valid if r.get("recommendation") == "MAYBE — NEEDS REVIEW"))
    col5.metric("🔴 Not suitable", sum(1 for r in valid if r.get("recommendation") == "NOT SUITABLE"))

    st.divider()

    # ── Sort + filter controls ────────────────────────────────────────────
    if valid:
        sort_col, filter_col = st.columns([1, 2])
        with sort_col:
            sort_by = st.selectbox("Sort by", ["Score (high→low)", "Score (low→high)", "Name A→Z"])
        with filter_col:
            show_only = st.multiselect(
                "Filter by decision",
                ["STRONG HIRE", "PROCEED TO INTERVIEW", "MAYBE — NEEDS REVIEW", "NOT SUITABLE"],
                default=["STRONG HIRE", "PROCEED TO INTERVIEW", "MAYBE — NEEDS REVIEW", "NOT SUITABLE"],
            )

        filtered = [r for r in valid if r.get("recommendation") in show_only]

        if sort_by == "Score (high→low)":
            filtered.sort(key=lambda r: r.get("total", 0), reverse=True)
        elif sort_by == "Score (low→high)":
            filtered.sort(key=lambda r: r.get("total", 0))
        else:
            filtered.sort(key=lambda r: r.get("full_name", ""))

        # ── Candidate cards ───────────────────────────────────────────────
        st.subheader(f"👥 Candidates ({len(filtered)} shown)")

        REC_CLASS = {
            "STRONG HIRE":          "rec-strong",
            "PROCEED TO INTERVIEW": "rec-interview",
            "MAYBE — NEEDS REVIEW": "rec-maybe",
            "NOT SUITABLE":         "rec-no",
        }
        REC_ICON = {
            "STRONG HIRE":          "🟢",
            "PROCEED TO INTERVIEW": "🔵",
            "MAYBE — NEEDS REVIEW": "🟡",
            "NOT SUITABLE":         "🔴",
        }

        for r in filtered:
            rec   = r.get("recommendation", "")
            total = r.get("total", 0)
            icon  = REC_ICON.get(rec, "❓")

            with st.expander(
                f"{icon} {r.get('full_name', 'Unknown')} — {total}/100 · {rec}",
                expanded=(rec in ["STRONG HIRE", "PROCEED TO INTERVIEW"]),
            ):
                left, right = st.columns([2, 1])

                with left:
                    st.markdown(f"**Role:** {r.get('current_role', '—')}")
                    st.markdown(f"**Experience:** {r.get('years_experience', '—')} years")
                    st.markdown(f"**Education:** {r.get('education_level', '—').replace('_', ' ').title()}")
                    if r.get("email"):
                        st.markdown(f"**Email:** {r['email']}")
                    if r.get("previous_companies"):
                        st.markdown(f"**Previous companies:** {', '.join(r['previous_companies'])}")
                    if r.get("languages"):
                        st.markdown(f"**Languages:** {', '.join(r['languages'])}")

                    # Skills tags
                    st.markdown("**Skills:**")
                    matched_r = [s.lower() for s in r.get("matched_required", [])]
                    matched_p = [s.lower() for s in r.get("matched_preferred", [])]
                    tags_html = ""
                    for skill in r.get("technical_skills", []):
                        sl = skill.lower()
                        css = "matched" if sl in matched_r or sl in matched_p else ""
                        tags_html += f'<span class="skill-tag {css}">{skill}</span>'
                    st.markdown(tags_html, unsafe_allow_html=True)

                    # Missing required skills
                    missing = r.get("missing_required", [])
                    if missing:
                        miss_html = "".join(f'<span class="skill-tag missing">✗ {s}</span>' for s in missing)
                        st.markdown(f"**Missing required:** {miss_html}", unsafe_allow_html=True)

                with right:
                    badge_class = REC_CLASS.get(rec, "")
                    st.markdown(
                        f'<div class="score-ring">{total}<span style="font-size:1rem;font-weight:400">/100</span></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<span class="rec-badge {badge_class}">{rec}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("")

                    # Score breakdown
                    st.caption("Score breakdown")
                    st.progress(r.get("experience_score", 0) / 30,
                                text=f"Experience: {r.get('experience_score',0)}/30")
                    st.progress(r.get("required_skills", 0) / 40,
                                text=f"Required skills: {r.get('required_skills',0)}/40")
                    st.progress(r.get("preferred_skills", 0) / 20,
                                text=f"Preferred skills: {r.get('preferred_skills',0)}/20")
                    st.progress(r.get("education", 0) / 10,
                                text=f"Education: {r.get('education',0)}/10")

        # ── Export table ──────────────────────────────────────────────────
        st.divider()
        st.subheader("📥 Export results")
        export_rows = []
        for r in valid:
            export_rows.append({
                "Name":              r.get("full_name", ""),
                "Email":             r.get("email", ""),
                "Role":              r.get("current_role", ""),
                "Experience (yrs)":  r.get("years_experience", ""),
                "Education":         r.get("education_level", ""),
                "Score":             r.get("total", 0),
                "Recommendation":    r.get("recommendation", ""),
                "Matched Required":  ", ".join(r.get("matched_required", [])),
                "Matched Preferred": ", ".join(r.get("matched_preferred", [])),
                "Missing Required":  ", ".join(r.get("missing_required", [])),
            })
        df = pd.DataFrame(export_rows).sort_values("Score", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode()
        st.download_button("⬇ Download CSV", csv, "screened_candidates.csv", "text/csv")

    # ── Failed parses ─────────────────────────────────────────────────────
    if failed:
        st.divider()
        with st.expander(f"⚠️ {len(failed)} resume(s) failed to parse"):
            for r in failed:
                st.error(f"**Error:** {r['_error']}")
                st.code(r["_raw"][:300] + "…" if len(r["_raw"]) > 300 else r["_raw"])