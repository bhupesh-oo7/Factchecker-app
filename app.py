
"""
Fact-Checking Web App
Automated claim verification system that reads PDFs, cross-references claims against live web data,
and flags inaccuracies.

Built with Streamlit for deployment on Streamlit Cloud.
"""

import streamlit as st
import re
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
import requests
from io import BytesIO

# PDF extraction
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

# --- CONFIGURATION ---
st.set_page_config(
    page_title="FactCheck AI - Automated Claim Verification",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f2937;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6b7280;
        text-align: center;
        margin-bottom: 2rem;
    }
    .claim-card {
        background-color: #f9fafb;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #e5e7eb;
    }
    .claim-card.verified {
        border-left-color: #10b981;
        background-color: #ecfdf5;
    }
    .claim-card.inaccurate {
        border-left-color: #f59e0b;
        background-color: #fffbeb;
    }
    .claim-card.false {
        border-left-color: #ef4444;
        background-color: #fef2f2;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
    }
    .badge-verified { background-color: #10b981; color: white; }
    .badge-inaccurate { background-color: #f59e0b; color: white; }
    .badge-false { background-color: #ef4444; color: white; }
    .stat-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .stat-label {
        font-size: 0.875rem;
        opacity: 0.9;
    }
    .source-link {
        color: #3b82f6;
        text-decoration: none;
        font-size: 0.875rem;
    }
    .source-link:hover {
        text-decoration: underline;
    }
    .extraction-info {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(uploaded_file) -> str:
    """Extract text from uploaded PDF file."""
    text = ""

    # Try pdfplumber first (better extraction)
    if pdfplumber is not None:
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
            if text.strip():
                return text
        except Exception:
            pass

    # Fallback to PyPDF2
    if PyPDF2 is not None:
        try:
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        except Exception as e:
            st.error(f"Error reading PDF: {e}")

    return text


def identify_claims(text: str) -> List[Dict[str, Any]]:
    """
    Identify specific claims from text:
    - Statistics (percentages, numbers with %)
    - Dates and years
    - Financial figures ($, €, £, etc.)
    - Technical figures (speeds, sizes, counts)
    - Specific named facts with numbers
    """
    claims = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue

        claim = None

        # Pattern 1: Percentages
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', sentence)
        if pct_match:
            claim = {
                "type": "statistic",
                "subtype": "percentage",
                "value": pct_match.group(0),
                "text": sentence,
                "context": get_context(sentences, i)
            }

        # Pattern 2: Financial figures
        elif re.search(r'[\$€£¥]\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|M|B|T)?', sentence, re.IGNORECASE):
            match = re.search(r'[\$€£¥]\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|trillion|M|B|T)?', sentence, re.IGNORECASE)
            claim = {
                "type": "financial",
                "subtype": "monetary",
                "value": match.group(0),
                "text": sentence,
                "context": get_context(sentences, i)
            }

        # Pattern 3: Specific years with claims
        elif re.search(r'\b(19|20)\d{2}\b', sentence) and re.search(r'\d+', sentence):
            year_match = re.search(r'\b(19|20)\d{2}\b', sentence)
            # Only flag if the sentence makes a factual claim about the year
            if any(word in sentence.lower() for word in ['launched', 'founded', 'established', 'released', 'started', 'began', 'introduced', 'created', 'in', 'by', 'since', 'as of', 'reported', 'recorded', 'grew', 'increased', 'decreased', 'reached']):
                claim = {
                    "type": "date",
                    "subtype": "year_claim",
                    "value": year_match.group(0),
                    "text": sentence,
                    "context": get_context(sentences, i)
                }

        # Pattern 4: Numbers with units (technical figures)
        elif re.search(r'\d+(?:,\d{3})*(?:\.\d+)?\s*(?:GB|TB|MB|mph|km/h|GHz|MHz|users|customers|downloads|employees|people)', sentence, re.IGNORECASE):
            match = re.search(r'\d+(?:,\d{3})*(?:\.\d+)?\s*(?:GB|TB|MB|mph|km/h|GHz|MHz|users|customers|downloads|employees|people)', sentence, re.IGNORECASE)
            claim = {
                "type": "technical",
                "subtype": "measurement",
                "value": match.group(0),
                "text": sentence,
                "context": get_context(sentences, i)
            }

        # Pattern 5: Large round numbers that look like statistics
        elif re.search(r'\b\d{1,3}(?:,\d{3})+\b', sentence):
            match = re.search(r'\b\d{1,3}(?:,\d{3})+\b', sentence)
            # Check if it's a standalone stat
            if any(word in sentence.lower() for word in ['has', 'have', 'there are', 'total', 'over', 'more than', 'approximately', 'about', 'around', 'estimated', 'reported']):
                claim = {
                    "type": "statistic",
                    "subtype": "count",
                    "value": match.group(0),
                    "text": sentence,
                    "context": get_context(sentences, i)
                }

        # Pattern 6: "X out of Y" or "X in Y" statistics
        elif re.search(r'\d+\s*(?:out of|in|per)\s*\d+', sentence, re.IGNORECASE):
            match = re.search(r'\d+\s*(?:out of|in|per)\s*\d+', sentence, re.IGNORECASE)
            claim = {
                "type": "statistic",
                "subtype": "ratio",
                "value": match.group(0),
                "text": sentence,
                "context": get_context(sentences, i)
            }

        if claim:
            claim["id"] = len(claims) + 1
            claims.append(claim)

    return claims


def get_context(sentences: List[str], index: int, window: int = 1) -> str:
    """Get surrounding context for a claim."""
    start = max(0, index - window)
    end = min(len(sentences), index + window + 1)
    return " ".join(sentences[start:end])


def search_web(query: str, api_key: str = None) -> List[Dict[str, Any]]:
    """
    Search the web for verification.
    Uses DuckDuckGo API (free, no key needed) or falls back to simulated search.
    """
    results = []

    # Try DuckDuckGo instant answer API
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1&skip_disambig=1"
        headers = {"User-Agent": "FactCheckAI/1.0"}
        response = requests.get(ddg_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Abstract/Definition
            if data.get("AbstractText"):
                results.append({
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                    "title": data.get("Heading", "Definition"),
                    "snippet": data.get("AbstractText", ""),
                    "url": data.get("AbstractURL", ""),
                    "type": "definition"
                })

            # Related topics
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "source": "DuckDuckGo",
                        "title": topic.get("Text", "")[:60],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", ""),
                        "type": "related"
                    })
    except Exception as e:
        st.warning(f"Web search encountered an issue: {e}")

    return results


def verify_claim(claim: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify a claim against web data.
    Returns verification result with status and evidence.
    """
    # Build search query from claim
    query = claim["text"][:150]  # Use the claim text as query

    # Clean up query for better search
    query = re.sub(r'[^\w\s$%€£.,-]', '', query)

    # Search web
    search_results = search_web(query)

    # Analyze results
    verification = {
        "claim_id": claim["id"],
        "claim_text": claim["text"],
        "claim_type": claim["type"],
        "claim_value": claim["value"],
        "status": "unverified",  # verified, inaccurate, false
        "confidence": 0.0,
        "evidence": [],
        "explanation": "",
        "sources": []
    }

    if not search_results:
        verification["status"] = "false"
        verification["confidence"] = 0.3
        verification["explanation"] = "No evidence found online to support this claim."
        return verification

    # Extract the key value from claim for comparison
    claim_value = claim["value"].lower().replace(",", "").replace("$", "").replace("%", "").strip()

    # Analyze search results
    matches = 0
    contradictions = 0
    total_checked = 0

    for result in search_results:
        snippet = result.get("snippet", "").lower()
        if not snippet:
            continue

        total_checked += 1

        # Check if claim value appears in results
        if claim["value"].lower() in snippet or claim_value in snippet:
            matches += 1
            verification["sources"].append(result)
        # Check for contradictions (opposite numbers, different years, etc.)
        elif claim["type"] == "date":
            # Look for different years mentioned
            years_in_snippet = re.findall(r'\b(19|20)\d{2}\b', snippet)
            claim_year = re.search(r'\b(19|20)\d{2}\b', claim["value"])
            if claim_year and years_in_snippet:
                if claim_year.group(0) not in years_in_snippet:
                    contradictions += 1
        elif claim["type"] == "statistic":
            # Look for percentage or number contradictions
            nums_in_snippet = re.findall(r'\d+(?:\.\d+)?', snippet)
            claim_num = re.search(r'\d+(?:\.\d+)?', claim["value"])
            if claim_num and nums_in_snippet:
                # If numbers are very different, might be contradiction
                try:
                    c_num = float(claim_num.group(0))
                    for n in nums_in_snippet[:3]:
                        s_num = float(n)
                        if abs(c_num - s_num) > max(c_num * 0.5, 5):  # >50% difference
                            contradictions += 1
                            break
                except ValueError:
                    pass

    # Determine status based on analysis
    if matches > 0 and contradictions == 0:
        verification["status"] = "verified"
        verification["confidence"] = min(0.7 + (matches * 0.1), 0.95)
        verification["explanation"] = f"Found {matches} source(s) corroborating this claim."
    elif matches > 0 and contradictions > 0:
        verification["status"] = "inaccurate"
        verification["confidence"] = 0.6
        verification["explanation"] = "Some sources support this, but conflicting information was found. The claim may be outdated or partially incorrect."
    elif matches == 0 and contradictions > 0:
        verification["status"] = "false"
        verification["confidence"] = 0.7
        verification["explanation"] = "Evidence contradicts this claim. The stated value appears to be incorrect."
    else:
        # No direct match, but results exist
        if total_checked > 0:
            # Check semantic similarity
            verification["status"] = "inaccurate"
            verification["confidence"] = 0.4
            verification["explanation"] = "Could not directly verify this claim. The specific value was not found in available sources."
        else:
            verification["status"] = "false"
            verification["confidence"] = 0.3
            verification["explanation"] = "No supporting evidence found for this claim."

    verification["evidence"] = search_results[:3]

    return verification


def generate_summary_report(verifications: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary statistics for the report."""
    total = len(verifications)
    verified = sum(1 for v in verifications if v["status"] == "verified")
    inaccurate = sum(1 for v in verifications if v["status"] == "inaccurate")
    false_count = sum(1 for v in verifications if v["status"] == "false")

    avg_confidence = sum(v["confidence"] for v in verifications) / total if total > 0 else 0

    return {
        "total_claims": total,
        "verified": verified,
        "inaccurate": inaccurate,
        "false": false_count,
        "accuracy_score": round((verified / total * 100), 1) if total > 0 else 0,
        "avg_confidence": round(avg_confidence * 100, 1),
        "risk_level": "High" if false_count > total * 0.3 else "Medium" if inaccurate > total * 0.3 else "Low"
    }


# --- MAIN APP ---

def main():
    # Header
    st.markdown('<div class="main-header">🔍 FactCheck AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated Claim Verification for Marketing Content</div>', unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/fact-checking.png", width=80)
        st.title("Settings")

        st.markdown("---")
        st.subheader("About")
        st.markdown("""
        **FactCheck AI** automatically extracts claims from PDF documents,
        cross-references them against live web data, and flags:

        - ✅ **Verified** - Claim matches online sources
        - ⚠️ **Inaccurate** - Claim may be outdated or partially wrong
        - ❌ **False** - No evidence supports this claim

        **Supported claim types:**
        - Statistics & percentages
        - Financial figures
        - Dates & years
        - Technical measurements
        """)

        st.markdown("---")
        st.subheader("How it works")
        st.markdown("""
        1. 📄 Upload your PDF
        2. 🔍 Claims are auto-extracted
        3. 🌐 Each claim is verified online
        4. 📊 Get a detailed report
        """)

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📄 Upload Document")
        uploaded_file = st.file_uploader(
            "Upload a PDF document to fact-check",
            type=["pdf"],
            help="Upload marketing content, reports, or any document with statistical claims"
        )

    with col2:
        st.subheader("⚙️ Options")
        max_claims = st.slider("Max claims to verify", 5, 50, 20)
        show_context = st.checkbox("Show context", value=True)

    if uploaded_file is not None:
        # Extract text
        with st.spinner("📖 Extracting text from PDF..."):
            text = extract_text_from_pdf(uploaded_file)

        if not text.strip():
            st.error("❌ Could not extract text from this PDF. Please try a different file.")
            return

        # Show extracted text preview
        with st.expander("📄 Extracted Text Preview", expanded=False):
            st.text_area("Content", text[:3000] + ("..." if len(text) > 3000 else ""), height=200)

        # Identify claims
        with st.spinner("🔍 Identifying claims..."):
            claims = identify_claims(text)

        if not claims:
            st.info("ℹ️ No verifiable claims found in this document. Try a document with statistics, dates, or financial figures.")
            return

        # Limit claims
        claims = claims[:max_claims]

        st.markdown(f"""
        <div class="extraction-info">
            <strong>✅ Found {len(claims)} verifiable claim(s)</strong> in your document.
            <br>Types detected: {', '.join(set(c['type'] for c in claims))}
        </div>
        """, unsafe_allow_html=True)

        # Verify button
        if st.button("🚀 Start Verification", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            verifications = []

            for i, claim in enumerate(claims):
                status_text.text(f"Verifying claim {i+1}/{len(claims)}: {claim['value'][:50]}...")

                # Verify claim
                result = verify_claim(claim)
                verifications.append(result)

                # Update progress
                progress = (i + 1) / len(claims)
                progress_bar.progress(progress)
                time.sleep(0.5)  # Rate limiting

            status_text.empty()
            progress_bar.empty()

            # Generate summary
            summary = generate_summary_report(verifications)

            # Display Summary Dashboard
            st.markdown("---")
            st.subheader("📊 Verification Summary")

            cols = st.columns(4)
            with cols[0]:
                st.markdown(f"""
                <div class="stat-box">
                    <div class="stat-number">{summary['total_claims']}</div>
                    <div class="stat-label">Total Claims</div>
                </div>
                """, unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"""
                <div class="stat-box" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                    <div class="stat-number">{summary['verified']}</div>
                    <div class="stat-label">Verified ✅</div>
                </div>
                """, unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f"""
                <div class="stat-box" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
                    <div class="stat-number">{summary['inaccurate']}</div>
                    <div class="stat-label">Inaccurate ⚠️</div>
                </div>
                """, unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"""
                <div class="stat-box" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
                    <div class="stat-number">{summary['false']}</div>
                    <div class="stat-label">False ❌</div>
                </div>
                """, unsafe_allow_html=True)

            # Accuracy score
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Accuracy Score", f"{summary['accuracy_score']}%")
            with col2:
                st.metric("Avg Confidence", f"{summary['avg_confidence']}%")
            with col3:
                st.metric("Risk Level", summary['risk_level'], 
                         delta="⚠️ Review needed" if summary['risk_level'] != "Low" else "✅ Clean")

            # Detailed Results
            st.markdown("---")
            st.subheader("📋 Detailed Verification Results")

            for v in verifications:
                status_class = v["status"]
                badge_class = f"badge-{v['status']}"

                with st.container():
                    st.markdown(f"""
                    <div class="claim-card {status_class}">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <span class="badge {badge_class}">{v['status'].upper()}</span>
                            <span style="color: #6b7280; font-size: 0.875rem;">Confidence: {v['confidence']*100:.0f}%</span>
                        </div>
                        <p style="font-weight: 600; margin: 0.5rem 0;">{v['claim_text']}</p>
                        <p style="color: #6b7280; font-size: 0.875rem; margin: 0.5rem 0;">
                            <strong>Type:</strong> {v['claim_type'].title()} | <strong>Value:</strong> {v['claim_value']}
                        </p>
                        <p style="margin: 0.5rem 0; padding: 0.5rem; background: rgba(255,255,255,0.5); border-radius: 6px;">
                            {v['explanation']}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Show evidence
                    if v["evidence"]:
                        with st.expander("🔍 View Sources & Evidence"):
                            for ev in v["evidence"][:3]:
                                st.markdown(f"""
                                **{ev.get('title', 'Source')}** ({ev.get('source', 'Web')})
                                > {ev.get('snippet', 'No snippet available')[:300]}
                                """)
                                if ev.get('url'):
                                    st.markdown(f'<a href="{ev["url"]}" target="_blank" class="source-link">🔗 View Source</a>',unsafe_allow_html=True)
                                st.markdown("---")

            # Export option
            st.markdown("---")
            st.subheader("📥 Export Report")

            report_data = {
                "generated_at": datetime.now().isoformat(),
                "document_name": uploaded_file.name,
                "summary": summary,
                "verifications": verifications
            }

            report_json = json.dumps(report_data, indent=2, default=str)
            st.download_button(
                label="📥 Download JSON Report",
                data=report_json,
                file_name=f"factcheck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    else:
        # Show sample/demo
        st.markdown("---")
        st.subheader("🎯 Try with a Sample")
        st.info("Upload a PDF above, or check out how FactCheck AI works with these example claims:")

        sample_claims = [
            {"text": "The global AI market is expected to reach $1.8 trillion by 2030.", "type": "financial", "value": "$1.8 trillion"},
            {"text": "Over 80% of all Google searches now end without a click.", "type": "statistic", "value": "80%"},
            {"text": "Tesla was founded in 2004 by Elon Musk.", "type": "date", "value": "2004"},
            {"text": "The iPhone was first released in 2007.", "type": "date", "value": "2007"},
        ]

        for sc in sample_claims:
            st.markdown(f'- **{sc["type"].title()}**: "{sc["text"]}" → *Value to verify: {sc["value"]}*')

        st.markdown("---")
        st.subheader("📋 Supported Claim Types")

        types_col1, types_col2, types_col3 = st.columns(3)
        with types_col1:
            st.markdown("""
            **📊 Statistics**
            - Percentages (e.g., 75%)
            - Ratios (e.g., 1 in 5)
            - Large counts (e.g., 10,000 users)
            """)
        with types_col2:
            st.markdown("""
            **💰 Financial**
            - Dollar amounts ($1M, $5B)
            - Revenue figures
            - Market size estimates
            """)
        with types_col3:
            st.markdown("""
            **📅 Dates & Technical**
            - Years with claims
            - Technical specs
            - Performance metrics
            """)


if __name__ == "__main__":
    main()
