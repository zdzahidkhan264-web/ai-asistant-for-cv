import streamlit as st
import pandas as pd
import json
import io

# Safe imports to prevent crashes on startup
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Page Setup
st.set_page_config(page_title="AI CV Screener", page_icon="📄", layout="wide")
st.title("📄 AI-Powered CV Screening App")
st.caption("Screen multiple candidate CVs against job criteria with Google Gemini AI")

# Check missing packages
missing_pkgs = []
if PdfReader is None:
    missing_pkgs.append("pypdf")
if docx is None:
    missing_pkgs.append("python-docx")
if genai is None:
    missing_pkgs.append("google-generativeai")

if missing_pkgs:
    st.error(f"⚠️ **Missing Dependencies on Streamlit Cloud:** `{', '.join(missing_pkgs)}`")
    st.info("Make sure `requirements.txt` is in your repository root, then click **Manage app** ➔ **Reboot app**.")

# Sidebar - API Key
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input(
        "Google Gemini API Key",
        value=st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else "",
        type="password",
        help="Get a free key from https://aistudio.google.com"
    )
    st.markdown("---")
    st.markdown("**Strict Evaluation Rule:**\nIf any information is unavailable in the CV, the AI will display **'Not Found'** without inventing data.")

# Step 1: Job Criteria
st.subheader("1. Enter Job Requirements & Criteria")
col1, col2 = st.columns([3, 1])
with col1:
    req_education = st.text_input("Required Education", "Bachelor's or Master's in Computer Science")
with col2:
    min_experience = st.number_input("Minimum Years of Experience", min_value=0, max_value=30, value=3, step=1)

relevant_experience = st.text_area("Relevant Experience", "React, Node.js, Python, REST APIs, SQL")
col3, col4 = st.columns(2)
with col3:
    pref_qualifications = st.text_input("Preferred Qualifications", "AWS Certification, Docker")
with col4:
    other_preferences = st.text_input("Other Job-Related Preferences", "Immediate joiner, Hybrid availability")

# Step 2: Upload Multiple CVs
st.subheader("2. Upload Candidate CVs")
uploaded_files = st.file_uploader(
    "Upload CVs in PDF, Word (DOCX), or TXT format",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True
)

# Text Extractor for PDF, DOCX, and TXT
def extract_text(file) -> str:
    name = file.name.lower()
    bytes_data = file.read()
    if name.endswith(".pdf"):
        if PdfReader is None:
            return "Error: pypdf not installed. Please check requirements.txt."
        reader = PdfReader(io.BytesIO(bytes_data))
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif name.endswith(".docx"):
        if docx is None:
            return "Error: python-docx not installed. Please check requirements.txt."
        doc = docx.Document(io.BytesIO(bytes_data))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    else:
        return bytes_data.decode("utf-8", errors="ignore")

# AI Analysis Function
def screen_cv_with_ai(cv_text: str, file_name: str) -> dict:
    prompt = f"""
You are an expert HR Talent Acquisition AI.
Analyze the candidate's CV against the specified Job Criteria.

CRITICAL INSTRUCTIONS:
1. Do not assume or invent missing information. If any information is unavailable in the CV, output "Not Found".
2. Candidate Name: Extract candidate's full name. If not found, output "Not Found".
3. Education: Compare with Required Education. Output "Matched", "Not Matched", or "Not Found".
4. Total Experience: Extract total number of years of experience from history/dates. Output as "X Years" (e.g. "5 Years", "2.5 Years"). If no dates or duration exist, output "Not Found".
5. Relevant Experience: Compare with Relevant Experience. Output "Matched", "Not Matched", or "Not Found".
6. Preferences: Compare with Preferred Qualifications & Other Preferences. Output "Matched", "Not Matched", or "Not Found".
7. Overall Criteria Matching: Output "Yes" only if Education = "Matched", Total Experience >= {min_experience} years, and Relevant Experience = "Matched". Otherwise output "No".

JOB CRITERIA:
- Required Education: {req_education}
- Minimum Years of Experience: {min_experience}
- Relevant Experience: {relevant_experience}
- Preferred Qualifications: {pref_qualifications}
- Other Preferences: {other_preferences}

CANDIDATE CV:
\"\"\"
{cv_text[:7000]}
\"\"\"

Return ONLY a valid JSON object matching this schema:
{{
  "Candidate Name": "string or 'Not Found'",
  "Education": "Matched" | "Not Matched" | "Not Found",
  "Total Experience": "X Years" or "Not Found",
  "Relevant Experience": "Matched" | "Not Matched" | "Not Found",
  "Preferences": "Matched" | "Not Matched" | "Not Found",
  "Overall Criteria Matching": "Yes" | "No"
}}
"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    data = json.loads(response.text)
    data["File Name"] = file_name
    return data

# Step 3: Run Evaluation
st.markdown("---")
if st.button("🚀 Run AI Screening", type="primary", use_container_width=True):
    if not api_key:
        st.error("Please enter your Google Gemini API Key in the sidebar.")
    elif not uploaded_files:
        st.warning("Please upload at least one CV file.")
    elif missing_pkgs:
        st.error(f"Cannot run screening: Missing dependencies ({', '.join(missing_pkgs)}).")
    else:
        results = []
        progress = st.progress(0)
        
        for idx, file in enumerate(uploaded_files):
            text = extract_text(file)
            try:
                res = screen_cv_with_ai(text, file.name)
            except Exception as e:
                res = {
                    "Candidate Name": file.name,
                    "Education": "Not Found",
                    "Total Experience": "Not Found",
                    "Relevant Experience": "Not Found",
                    "Preferences": "Not Found",
                    "Overall Criteria Matching": "No",
                    "File Name": file.name
                }
            results.append(res)
            progress.progress((idx + 1) / len(uploaded_files))
        
        st.success(f"Screening complete for {len(results)} candidate(s)!")
        
        # Results Table
        df = pd.DataFrame(results)
        cols = [
            "Candidate Name",
            "Education",
            "Total Experience",
            "Relevant Experience",
            "Preferences",
            "Overall Criteria Matching",
            "File Name"
        ]
        df = df[[c for c in cols if c in df.columns]]
        
        st.subheader("📊 Candidate Evaluation Results")
        
        def highlight_overall(val):
            if val == "Yes":
                return "background-color: #dcfce7; color: #15803d; font-weight: bold;"
            elif val == "No":
                return "background-color: #fee2e2; color: #b91c1c; font-weight: bold;"
            elif val == "Not Found":
                return "background-color: #fef3c7; color: #b45309;"
            return ""

        styled_df = df.style.map(highlight_overall, subset=["Overall Criteria Matching", "Education", "Relevant Experience", "Preferences"])
        st.dataframe(styled_df, use_container_width=True)
        
        # Summary counts
        yes_count = sum(df["Overall Criteria Matching"] == "Yes")
        no_count = sum(df["Overall Criteria Matching"] == "No")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Candidates", len(df))
        c2.metric("Criteria Met (YES)", yes_count)
        c3.metric("Criteria Not Met (NO)", no_count)
        
        # CSV Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name="cv_screening_results.csv",
            mime="text/csv"
        )
