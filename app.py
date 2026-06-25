import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

from document_processor import ClauseExtractor, get_document_summary
from clause_matcher import LegalClauseMatcher
from utils import format_report, save_report

# Page configuration
st.set_page_config(
    page_title="Legal Document Comparator",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
    }
    .clause-box {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #3B82F6;
    }
    .diff-box {
        background-color: #FEF2F2;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #EF4444;
    }
    .match-box {
        background-color: #F0FDF4;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #22C55E;
    }
    .stButton > button {
        width: 100%;
        background-color: #1E3A8A;
        color: white;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #1E40AF;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize session state variables"""
    if 'comparison_results' not in st.session_state:
        st.session_state.comparison_results = None
    if 'doc1_clauses' not in st.session_state:
        st.session_state.doc1_clauses = None
    if 'doc2_clauses' not in st.session_state:
        st.session_state.doc2_clauses = None
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'reports_generated' not in st.session_state:
        st.session_state.reports_generated = []

def main():
    st.markdown('<h1 class="main-header">⚖️ Legal Document Comparator</h1>', unsafe_allow_html=True)
    st.markdown("Compare two legal documents and identify differences in clauses")
    
    initialize_session_state()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        st.subheader("Comparison Settings")
        similarity_threshold = st.slider(
            "Similarity Threshold",
            min_value=0.1,
            max_value=0.9,
            value=0.3,
            step=0.05,
            help="Lower values will find more potential matches but may include false positives"
        )
        
        st.subheader("LLM Settings")
        st.info("Using Qwen2.5:7b (Local)")
        st.caption("✅ No data leaves your machine")
        
        st.subheader("Advanced Options")
        use_llm = st.checkbox("Use LLM Verification", value=True)
        use_embedding_cache = st.checkbox("Use Embedding Cache", value=True)
        
        st.divider()
        
        # Document summary (shown after processing)
        if st.session_state.doc1_clauses and st.session_state.doc2_clauses:
            st.subheader("📊 Document Summary")
            
            summary1 = get_document_summary(st.session_state.doc1_clauses)
            summary2 = get_document_summary(st.session_state.doc2_clauses)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Doc 1 Clauses", summary1['total'])
                st.metric("Avg Length", summary1['avg_length'], "words")
            with col2:
                st.metric("Doc 2 Clauses", summary2['total'])
                st.metric("Avg Length", summary2['avg_length'], "words")
    
    # Main content - two columns for document upload
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 Document 1")
        doc1_file = st.file_uploader(
            "Upload Document 1 (PDF or DOCX)",
            type=['pdf', 'docx'],
            key="doc1"
        )
        
        if doc1_file:
            if st.button("Process Document 1", key="process1"):
                with st.spinner("Extracting clauses..."):
                    extractor = ClauseExtractor()
                    try:
                        file_bytes = doc1_file.read()
                        if doc1_file.type == 'application/pdf':
                            clauses = extractor.extract_from_pdf(file_bytes)
                        else:
                            clauses = extractor.extract_from_docx(file_bytes)
                        
                        st.session_state.doc1_clauses = clauses
                        st.success(f"✅ Extracted {len(clauses)} clauses")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
            
            if st.session_state.doc1_clauses:
                with st.expander(f"📋 View Clauses ({len(st.session_state.doc1_clauses)})"):
                    for idx, clause in enumerate(st.session_state.doc1_clauses[:5]):
                        st.markdown(f"""
                            <div class="clause-box">
                                <strong>Clause {clause.get('number', idx+1)}</strong><br>
                                {clause['text'][:200]}...
                            </div>
                        """, unsafe_allow_html=True)
                    if len(st.session_state.doc1_clauses) > 5:
                        st.caption(f"... and {len(st.session_state.doc1_clauses) - 5} more clauses")
    
    with col2:
        st.subheader("📄 Document 2")
        doc2_file = st.file_uploader(
            "Upload Document 2 (PDF or DOCX)",
            type=['pdf', 'docx'],
            key="doc2"
        )
        
        if doc2_file:
            if st.button("Process Document 2", key="process2"):
                with st.spinner("Extracting clauses..."):
                    extractor = ClauseExtractor()
                    try:
                        file_bytes = doc2_file.read()
                        if doc2_file.type == 'application/pdf':
                            clauses = extractor.extract_from_pdf(file_bytes)
                        else:
                            clauses = extractor.extract_from_docx(file_bytes)
                        
                        st.session_state.doc2_clauses = clauses
                        st.success(f"✅ Extracted {len(clauses)} clauses")
                    except Exception as e:
                        st.error(f"Error processing document: {str(e)}")
            
            if st.session_state.doc2_clauses:
                with st.expander(f"📋 View Clauses ({len(st.session_state.doc2_clauses)})"):
                    for idx, clause in enumerate(st.session_state.doc2_clauses[:5]):
                        st.markdown(f"""
                            <div class="clause-box">
                                <strong>Clause {clause.get('number', idx+1)}</strong><br>
                                {clause['text'][:200]}...
                            </div>
                        """, unsafe_allow_html=True)
                    if len(st.session_state.doc2_clauses) > 5:
                        st.caption(f"... and {len(st.session_state.doc2_clauses) - 5} more clauses")
    
    # Compare button (center aligned)
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        compare_btn = st.button(
            "🔄 Compare Documents",
            use_container_width=True,
            disabled=not (st.session_state.doc1_clauses and st.session_state.doc2_clauses)
        )
    
    # Run comparison
    if compare_btn and st.session_state.doc1_clauses and st.session_state.doc2_clauses:
        with st.spinner("Comparing documents... This may take a few minutes."):
            st.session_state.processing = True
            
            try:
                matcher = LegalClauseMatcher()
                results = matcher.match_documents(
                    st.session_state.doc1_clauses,
                    st.session_state.doc2_clauses,
                    doc1_name="Document 1",
                    doc2_name="Document 2",
                    similarity_threshold=similarity_threshold
                )
                
                st.session_state.comparison_results = results
                st.session_state.processing = False
                
                # Auto-generate report
                report_text = format_report(results)
                report_file = save_report(results)
                st.session_state.reports_generated.append(report_file)
                
                st.success(f"✅ Comparison complete! Processed {results['total_doc1'] + results['total_doc2']} clauses in {results['processing_time']:.2f} seconds")
                
            except Exception as e:
                st.session_state.processing = False
                st.error(f"Error during comparison: {str(e)}")
                st.error("Make sure Ollama is running and qwen2.5:7b model is downloaded")
                st.info("To install and run Ollama:\n1. Download from https://ollama.ai\n2. Run: ollama pull qwen2.5:7b\n3. Run: ollama serve")
    
    # Display results
    if st.session_state.comparison_results and not st.session_state.processing:
        results = st.session_state.comparison_results
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Clauses", results['total_doc1'] + results['total_doc2'])
        with col2:
            st.metric("Matching Clauses", results['matching_count'])
        with col3:
            st.metric("Only in Doc 1", len(results['only_in_doc1']))
        with col4:
            st.metric("Only in Doc 2", len(results['only_in_doc2']))
        
        # Visualization
        st.subheader("📊 Visual Analysis")
        fig = go.Figure(data=[
            go.Bar(
                x=['Doc 1 Only', 'Doc 2 Only', 'Matching'],
                y=[len(results['only_in_doc1']), len(results['only_in_doc2']), results['matching_count']],
                marker_color=['#EF4444', '#3B82F6', '#22C55E'],
                text=[len(results['only_in_doc1']), len(results['only_in_doc2']), results['matching_count']],
                textposition='auto',
            )
        ])
        fig.update_layout(
            title='Clause Comparison Overview',
            xaxis_title='Category',
            yaxis_title='Number of Clauses',
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Results in tabs
        tab1, tab2, tab3 = st.tabs(["🔴 Only in Document 1", "🔵 Only in Document 2", "📋 Detailed Report"])
        
        with tab1:
            if results['only_in_doc1']:
                st.warning(f"⚠️ {len(results['only_in_doc1'])} clauses found only in Document 1")
                for idx, clause in enumerate(results['only_in_doc1']):
                    with st.expander(f"Clause {clause.get('number', idx+1)}"):
                        st.markdown(f"""
                            <div class="diff-box">
                                <strong>Text:</strong><br>
                                {clause['text']}
                                <br><br>
                                <strong>Closest match in Document 2:</strong><br>
                                {clause.get('closest_match', 'No similar clause found')}
                                <br><br>
                                <strong>Similarity Score:</strong> {clause.get('similarity', 0):.2f}
                                <br>
                                <strong>Word Count:</strong> {clause.get('metadata', {}).get('word_count', 0)}
                            </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✅ All clauses in Document 1 have matches in Document 2")
        
        with tab2:
            if results['only_in_doc2']:
                st.warning(f"⚠️ {len(results['only_in_doc2'])} clauses found only in Document 2")
                for idx, clause in enumerate(results['only_in_doc2']):
                    with st.expander(f"Clause {clause.get('number', idx+1)}"):
                        st.markdown(f"""
                            <div class="diff-box">
                                <strong>Text:</strong><br>
                                {clause['text']}
                                <br><br>
                                <strong>Closest match in Document 1:</strong><br>
                                {clause.get('closest_match', 'No similar clause found')}
                                <br><br>
                                <strong>Similarity Score:</strong> {clause.get('similarity', 0):.2f}
                                <br>
                                <strong>Word Count:</strong> {clause.get('metadata', {}).get('word_count', 0)}
                            </div>
                        """, unsafe_allow_html=True)
            else:
                st.success("✅ All clauses in Document 2 have matches in Document 1")
        
        with tab3:
            st.subheader("📋 Full Comparison Report")
            
            # Download options
            col1, col2 = st.columns(2)
            with col1:
                report_text = format_report(results)
                st.download_button(
                    label="📥 Download Report (TXT)",
                    data=report_text,
                    file_name=f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
            with col2:
                json_file = save_report(results)
                with open(json_file, 'r') as f:
                    json_data = f.read()
                st.download_button(
                    label="📥 Download Report (JSON)",
                    data=json_data,
                    file_name=f"comparison_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            st.text_area(
                "Report Preview",
                report_text[:2000] + ("..." if len(report_text) > 2000 else ""),
                height=300,
                disabled=True
            )

if __name__ == "__main__":
    # Check if Ollama is running
    try:
        import ollama
        # Test connection
        ollama.list()
    except Exception:
        st.warning("⚠️ Ollama not detected. Please ensure Ollama is running and qwen2.5:7b is downloaded.")
        st.info("""
        To install:
        1. Download Ollama from https://ollama.ai
        2. Run in terminal: `ollama pull qwen2.5:7b`
        3. Run in terminal: `ollama serve`
        """)
    
    main()