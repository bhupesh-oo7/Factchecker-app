# 🔍 FactCheck AI - Automated Claim Verification

A Streamlit web application that automatically extracts factual claims from PDF documents, cross-references them against live web data, and flags inaccuracies.

## 🎯 Features

- **PDF Upload**: Extract text from uploaded PDF documents
- **Smart Claim Detection**: Automatically identifies statistics, financial figures, dates, and technical measurements
- **Live Web Verification**: Cross-references claims against DuckDuckGo search results
- **Detailed Reporting**: Flags claims as Verified ✅, Inaccurate ⚠️, or False ❌
- **Export**: Download JSON reports for further analysis

## 🚀 Deployment

### Option 1: Streamlit Cloud (Recommended)
1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Deploy!

### Option 2: Local Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 📋 How It Works

1. **Extract**: Upload a PDF → text is extracted using PyPDF2/pdfplumber
2. **Identify**: Regex patterns detect claims (stats, $, dates, technical figures)
3. **Verify**: Each claim is searched via DuckDuckGo API
4. **Report**: Results are categorized with confidence scores

## 🔧 Claim Types Detected

| Type | Examples |
|------|----------|
| Statistics | "80% of users", "1 in 5 people" |
| Financial | "$1.8 trillion", "€50M revenue" |
| Dates | "Founded in 2004", "Released in 2020" |
| Technical | "5GB storage", "2.4GHz processor" |

## 📊 Verification Status

- ✅ **Verified**: Claim matches online sources
- ⚠️ **Inaccurate**: Conflicting or outdated information found
- ❌ **False**: No supporting evidence found

## 📝 Notes

- Uses DuckDuckGo API for free web search (no API key required)
- Rate limiting is implemented to respect search APIs
- For best results, use documents with clear, specific claims

## 🎥 Demo

[Add demo video link here]

---
Built for CogDigital Product Management Assessment
