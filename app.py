"""FaultTrace Streamlit dashboard entry point."""

from __future__ import annotations

import html
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from faulttrace import LogEvent, parse_log_file, parse_log_lines  # noqa: E402
from faulttrace.analysis import (  # noqa: E402
    SYSTEM_PROMPT,
    build_analysis_prompt,
    build_incident_query,
)
from faulttrace.foundry import FoundryChatService, FoundryEmbeddingService  # noqa: E402
from faulttrace.document_ingestion import (  # noqa: E402
    extract_document_text,
    safe_source_name,
)
from faulttrace.evaluation import (  # noqa: E402
    available_evaluation_cases,
    evaluate_retrieval,
)
from faulttrace.incident_metrics import (  # noqa: E402
    build_failure_chain,
    calculate_incident_score,
)
from faulttrace.incident_repository import IncidentRepository  # noqa: E402
from faulttrace.knowledge_base import KnowledgeBase  # noqa: E402
from faulttrace.quick_analysis import build_quick_report, detect_cause  # noqa: E402
from faulttrace.privacy import redact_events  # noqa: E402
from faulttrace.qa import (  # noqa: E402
    QA_SYSTEM_PROMPT,
    audit_answer_citations,
    build_qa_prompt,
    retrieve_question_evidence,
)


LEVEL_ORDER = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LEVEL_COLORS = {
    "TRACE": "#64748b",
    "DEBUG": "#64748b",
    "INFO": "#38bdf8",
    "WARNING": "#f59e0b",
    "ERROR": "#f43f5e",
    "CRITICAL": "#a855f7",
}

DEMO_SCENARIOS = {
    "Database pool exhaustion": "sample_incident.log",
    "Authentication outage": "sample_auth_incident.log",
    "High CPU and timeouts": "sample_cpu_incident.log",
}


def inject_faulttrace_theme() -> None:
    """Apply the local FaultTrace visual system to Streamlit components."""

    st.markdown(
        """
        <style>
        :root {
            --ft-bg: #070b12;
            --ft-panel: #0d1420;
            --ft-panel-raised: #121c2b;
            --ft-border: #243247;
            --ft-muted: #8fa1b8;
            --ft-text: #e8eef7;
            --ft-accent: #ff6b35;
            --ft-accent-soft: rgba(255, 107, 53, 0.14);
            --ft-success: #42d392;
        }

        .stApp {
            background:
                radial-gradient(circle at 82% -10%, rgba(255,107,53,.11), transparent 28rem),
                linear-gradient(180deg, #080d16 0%, var(--ft-bg) 55%);
            color: var(--ft-text);
        }

        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"], [data-testid="stDecoration"],
        #MainMenu, footer { display: none; }

        .block-container {
            max-width: 1480px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            background: #090f19;
            border-right: 1px solid var(--ft-border);
        }
        [data-testid="stSidebar"] h2 {
            color: #fff;
            letter-spacing: -0.02em;
        }

        .faulttrace-hero {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 2rem;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1rem;
            border: 1px solid var(--ft-border);
            border-radius: 18px;
            background: linear-gradient(115deg, rgba(18,28,43,.96), rgba(10,16,26,.92));
            box-shadow: 0 20px 55px rgba(0,0,0,.28);
        }
        .faulttrace-eyebrow {
            color: var(--ft-accent);
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .18em;
            text-transform: uppercase;
            margin-bottom: .35rem;
        }
        .faulttrace-title {
            color: #f8fbff;
            font-size: clamp(2rem, 4vw, 3.35rem);
            line-height: .98;
            letter-spacing: -.055em;
            font-weight: 820;
            margin: 0;
        }
        .faulttrace-title span { color: var(--ft-accent); }
        .faulttrace-subtitle {
            color: var(--ft-muted);
            margin: .65rem 0 0;
            max-width: 760px;
            font-size: .98rem;
        }
        .faulttrace-status {
            flex: 0 0 auto;
            display: inline-flex;
            align-items: center;
            gap: .55rem;
            color: #b9f6d7;
            background: rgba(66,211,146,.08);
            border: 1px solid rgba(66,211,146,.3);
            border-radius: 999px;
            padding: .55rem .8rem;
            font-size: .72rem;
            font-weight: 750;
            letter-spacing: .09em;
        }
        .faulttrace-status::before {
            content: "";
            width: .48rem;
            height: .48rem;
            border-radius: 50%;
            background: var(--ft-success);
            box-shadow: 0 0 12px rgba(66,211,146,.8);
        }
        .incident-strip {
            display: flex;
            align-items: center;
            gap: .65rem;
            color: var(--ft-muted);
            margin: .8rem 0 1rem;
            font-size: .83rem;
        }
        .incident-strip strong { color: #dce7f5; }
        .incident-strip code {
            color: #ffd2c2;
            background: var(--ft-accent-soft);
            border: 1px solid rgba(255,107,53,.24);
            padding: .25rem .5rem;
            border-radius: 7px;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(160deg, var(--ft-panel-raised), var(--ft-panel));
            border: 1px solid var(--ft-border);
            border-radius: 14px;
            padding: 1rem 1.05rem;
            min-height: 112px;
        }
        [data-testid="stMetricLabel"] { color: var(--ft-muted); }
        [data-testid="stMetricValue"] { color: #f7faff; letter-spacing: -.035em; }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(150deg, rgba(18,28,43,.88), rgba(11,17,27,.86));
            border-color: var(--ft-border) !important;
            border-radius: 14px !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
            background: #0a111c;
            border: 1px solid var(--ft-border);
            border-radius: 13px;
            padding: .35rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9px;
            color: var(--ft-muted);
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .stTabs [aria-selected="true"] {
            color: white !important;
            background: var(--ft-accent-soft);
        }
        .stTabs [data-baseweb="tab-highlight"] { background: var(--ft-accent); }

        .stButton > button, .stDownloadButton > button {
            border-radius: 9px;
            border-color: #34455e;
            font-weight: 680;
        }
        .stButton > button[kind="primary"] {
            background: var(--ft-accent);
            border-color: var(--ft-accent);
            color: #10141b;
        }
        .stButton > button[kind="primary"]:hover {
            background: #ff8256;
            border-color: #ff8256;
        }

        [data-testid="stFileUploaderDropzone"] {
            background: rgba(18,28,43,.7);
            border-color: #34455e;
            border-radius: 12px;
        }
        [data-testid="stExpander"] {
            background: rgba(13,20,32,.7);
            border-color: var(--ft-border);
            border-radius: 11px;
        }
        hr { border-color: var(--ft-border) !important; opacity: .7; }
        h1, h2, h3 { letter-spacing: -.025em; }

        @media (max-width: 760px) {
            .faulttrace-hero { align-items: flex-start; flex-direction: column; }
            .faulttrace-status { align-self: flex-start; }
            .block-container { padding-top: 1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def style_figure(figure: object) -> object:
    """Match Plotly charts to the FaultTrace dark operations theme."""

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,13,22,0.35)",
        font=dict(color="#aebed1", family="Arial, sans-serif"),
        hoverlabel=dict(bgcolor="#121c2b", font_color="#f7faff"),
        xaxis=dict(gridcolor="rgba(143,161,184,.12)", zerolinecolor="rgba(143,161,184,.16)"),
        yaxis=dict(gridcolor="rgba(143,161,184,.12)", zerolinecolor="rgba(143,161,184,.16)"),
    )
    return figure


def events_to_frame(events: list[LogEvent]) -> pd.DataFrame:
    """Convert normalized events into a dashboard-friendly dataframe."""

    return pd.DataFrame(
        [
            {
                "Time": event.timestamp,
                "Level": event.level,
                "Service": event.service,
                "Message": event.message,
                "Line": event.line_number,
            }
            for event in events
        ]
    )


def read_uploaded_log(uploaded_file: object) -> tuple[list[LogEvent], list[str]]:
    """Decode an uploaded Streamlit file and parse its lines."""

    content = uploaded_file.getvalue().decode("utf-8-sig", errors="replace")
    return parse_log_lines(content.splitlines())


def render_sidebar() -> tuple[list[LogEvent], list[str], str]:
    """Render input controls and return the selected incident data."""

    with st.sidebar:
        st.header("Incident workspace")
        uploaded = st.file_uploader(
            "Upload a log file",
            type=["log", "txt", "jsonl", "json"],
            help="Supported: plain text logs and one JSON object per line.",
        )
        redact_sensitive = st.toggle(
            "Redact sensitive values",
            value=True,
            help="Masks emails, IP addresses, tokens, API keys and passwords before analysis.",
        )
        st.caption("Processing stays on this device. No log data is uploaded.")
        st.divider()
        selected_demo = st.selectbox(
            "Built-in demo scenario",
            options=list(DEMO_SCENARIOS),
            help="Used when no custom log file is uploaded.",
        )

    if uploaded is not None:
        events, rejected = read_uploaded_log(uploaded)
        if redact_sensitive:
            events, redaction_count = redact_events(events)
            st.session_state["redaction_count"] = redaction_count
        else:
            st.session_state["redaction_count"] = 0
        return events, rejected, uploaded.name

    demo_file = DEMO_SCENARIOS[selected_demo]
    events, rejected = parse_log_file(PROJECT_ROOT / "data" / demo_file)
    if redact_sensitive:
        events, redaction_count = redact_events(events)
        st.session_state["redaction_count"] = redaction_count
    else:
        st.session_state["redaction_count"] = 0
    return events, rejected, demo_file


def render_metrics(events: list[LogEvent]) -> None:
    counts = Counter(event.level for event in events)
    services = {event.service for event in events}
    duration = events[-1].timestamp - events[0].timestamp

    incident_score = calculate_incident_score(events)
    columns = st.columns(6)
    columns[0].metric("Events", len(events))
    columns[1].metric("Errors", counts["ERROR"])
    columns[2].metric("Critical", counts["CRITICAL"])
    columns[3].metric("Services", len(services))
    columns[4].metric("Duration", f"{int(duration.total_seconds())} sec")
    columns[5].metric("Impact score", f"{incident_score.value}/100", incident_score.label)
    st.caption(f"Impact score: {incident_score.explanation}")


def render_failure_chain(events: list[LogEvent]) -> None:
    """Render a deterministic, chronological chain of serious events."""

    st.subheader("Failure chain")
    st.caption(
        "This sequence is extracted directly from WARNING, ERROR and CRITICAL logs; "
        "it is not generated by the language model."
    )
    chain = build_failure_chain(events)
    for index, event in enumerate(chain, start=1):
        marker = "->" if index < len(chain) else "END"
        st.markdown(
            f"**{index}. {event.timestamp.strftime('%H:%M:%S')} | "
            f"{event.service} | {event.level}**  \n"
            f"{event.message} `{marker}`"
        )


def render_charts(frame: pd.DataFrame) -> None:
    left, right = st.columns((1.15, 1))

    with left:
        st.subheader("Severity distribution")
        severity = (
            frame.groupby("Level", as_index=False)
            .size()
            .rename(columns={"size": "Count"})
        )
        severity["Level"] = pd.Categorical(
            severity["Level"], categories=LEVEL_ORDER, ordered=True
        )
        severity = severity.sort_values("Level")
        figure = px.bar(
            severity,
            x="Level",
            y="Count",
            color="Level",
            color_discrete_map=LEVEL_COLORS,
        )
        figure.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(style_figure(figure), width="stretch")

    with right:
        st.subheader("Events by service")
        services = (
            frame.groupby("Service", as_index=False)
            .size()
            .rename(columns={"size": "Events"})
            .sort_values("Events", ascending=True)
        )
        figure = px.bar(
            services,
            x="Events",
            y="Service",
            orientation="h",
            color="Events",
            color_continuous_scale=["#172554", "#38bdf8"],
        )
        figure.update_layout(
            coloraxis_showscale=False, margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(style_figure(figure), width="stretch")


def render_timeline(frame: pd.DataFrame) -> None:
    st.subheader("Incident timeline")
    severity_filter = st.multiselect(
        "Filter severity",
        options=[level for level in LEVEL_ORDER if level in set(frame["Level"])],
        default=[level for level in LEVEL_ORDER if level in set(frame["Level"])],
    )
    visible = frame[frame["Level"].isin(severity_filter)].copy()
    visible["Time"] = (
        visible["Time"]
        .dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        .str.rstrip("0")
        .str.rstrip(".")
    )
    st.dataframe(
        visible[["Time", "Level", "Service", "Message", "Line"]],
        width="stretch",
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn(width="medium"),
            "Level": st.column_config.TextColumn(width="small"),
            "Service": st.column_config.TextColumn(width="medium"),
            "Message": st.column_config.TextColumn(width="large"),
            "Line": st.column_config.NumberColumn(width="small"),
        },
    )


def render_runbook_search(events: list[LogEvent]) -> None:
    """Retrieve runbook evidence for the incident's serious log messages."""

    st.subheader("Runbook evidence")
    st.write(
        "Search the local technical knowledge base for guidance related to this "
        "incident. This uses embeddings, not the chat model."
    )
    knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")

    if knowledge_base.count() == 0:
        st.info("The local knowledge base has not been indexed yet.")
        return

    if st.button("Find relevant runbook", type="primary"):
        query = build_incident_query(events)
        with st.spinner("Searching local runbooks..."):
            with FoundryEmbeddingService() as embeddings:
                st.session_state["runbook_results"] = knowledge_base.search(
                    query, embeddings.embed, limit=3
                )

    results = st.session_state.get("runbook_results", [])
    for rank, result in enumerate(results, start=1):
        with st.expander(
            f"{rank}. {result.source} | {result.heading} | score {result.score:.3f}",
            expanded=rank == 1,
        ):
            st.write(result.content)
            st.caption(f"Local source: {result.source} - {result.heading}")


def render_knowledge_base_management() -> None:
    """Upload, index, list and remove custom local knowledge documents."""

    st.subheader("Knowledge base management")
    st.write(
        "Add local TXT, Markdown or text-based PDF runbooks. Documents are "
        "embedded and stored in SQLite on this device."
    )
    knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")

    upload_column, inventory_column = st.columns((1, 1.1))
    with upload_column:
        documents = st.file_uploader(
            "Upload knowledge documents",
            type=["txt", "md", "pdf"],
            accept_multiple_files=True,
            key="knowledge-documents",
            help="Maximum 10 MB per document. Scanned PDFs require OCR and are not supported yet.",
        )
        if st.button("Index uploaded documents", disabled=not documents):
            try:
                prepared_documents = [
                    (
                        safe_source_name(document.name),
                        extract_document_text(document.name, document.getvalue()),
                    )
                    for document in documents
                ]
                indexed_summary: list[str] = []
                with st.spinner("Creating local document embeddings..."):
                    with FoundryEmbeddingService() as embeddings:
                        for source, text in prepared_documents:
                            count = knowledge_base.index_document(
                                source, text, embeddings.embed
                            )
                            indexed_summary.append(f"{source}: {count} chunks")
                st.session_state["knowledge_status"] = (
                    "Indexed " + ", ".join(indexed_summary)
                )
                st.rerun()
            except Exception as error:
                st.error(f"Document indexing failed: {error}")

        knowledge_status = st.session_state.pop("knowledge_status", None)
        if knowledge_status:
            st.success(knowledge_status)

    with inventory_column:
        sources = knowledge_base.list_sources()
        st.markdown(f"**Indexed sources: {len(sources)}**")
        for source in sources:
            is_custom = source.source.startswith("custom/")
            label = "Custom" if is_custom else "Built-in"
            source_row, action_row = st.columns((4, 1))
            source_row.write(
                f"`{source.source}`  \n{label} | {source.chunk_count} chunks"
            )
            if is_custom and action_row.button(
                "Delete", key=f"delete-source-{source.source}"
            ):
                removed = knowledge_base.delete_source(source.source)
                st.session_state["knowledge_status"] = (
                    f"Deleted {source.source} ({removed} chunks)."
                )
                st.rerun()


def render_ai_analysis(events: list[LogEvent], source_name: str) -> None:
    """Generate and display a source-grounded local LLM analysis."""

    st.subheader("AI root-cause analysis")
    st.write("Choose instant rule-based analysis or a detailed local LLM report.")
    quick_column, deep_column = st.columns(2)

    if quick_column.button("Quick analysis (instant)", type="primary"):
        rule, _ = detect_cause(events)
        knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
        runbooks = knowledge_base.get_source_chunks(rule.source) if rule else []
        analysis = build_quick_report(events, runbooks)
        st.session_state["incident_analysis"] = analysis
        st.session_state["analysis_mode"] = "Quick"
        repository = IncidentRepository(PROJECT_ROOT / "data" / "faulttrace.db")
        st.session_state["saved_report_id"] = repository.save(
            source_name, events, analysis
        )

    if deep_column.button("Deep AI analysis (~1 min)"):
        try:
            total_started = time.perf_counter()
            retrieval_seconds = 0.0
            runbooks = st.session_state.get("runbook_results", [])
            if not runbooks:
                knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
                retrieval_started = time.perf_counter()
                with st.spinner("Retrieving local runbook evidence..."):
                    with FoundryEmbeddingService() as embeddings:
                        runbooks = knowledge_base.search(
                            build_incident_query(events), embeddings.embed, limit=3
                        )
                retrieval_seconds = time.perf_counter() - retrieval_started
                st.session_state["runbook_results"] = runbooks

            prompt = build_analysis_prompt(events, runbooks)
            generation_started = time.perf_counter()
            with st.spinner("Local model is analyzing the incident..."):
                with FoundryChatService() as chat:
                    analysis = chat.complete(
                        SYSTEM_PROMPT, prompt
                    )
                generation_seconds = time.perf_counter() - generation_started
                st.session_state["incident_analysis"] = analysis
                st.session_state["analysis_mode"] = "Deep AI"
                st.session_state["analysis_performance"] = {
                    "retrieval": retrieval_seconds,
                    "generation": generation_seconds,
                    "total": time.perf_counter() - total_started,
                }
                repository = IncidentRepository(PROJECT_ROOT / "data" / "faulttrace.db")
                report_id = repository.save(source_name, events, analysis)
                st.session_state["saved_report_id"] = report_id
        except Exception as error:
            st.error(f"Local analysis failed: {error}")

    analysis = st.session_state.get("incident_analysis")
    if not analysis:
        return

    report_id = st.session_state.get("saved_report_id")
    if report_id:
        mode = st.session_state.get("analysis_mode", "Analysis")
        st.success(f"{mode} report saved locally as incident report #{report_id}.")
    st.markdown(analysis)
    performance = st.session_state.get("analysis_performance")
    if performance and st.session_state.get("analysis_mode") == "Deep AI":
        st.caption(
            f"Measured locally — retrieval: {performance['retrieval']:.2f}s | "
            f"LLM generation: {performance['generation']:.2f}s | "
            f"end-to-end: {performance['total']:.2f}s"
        )
    st.download_button(
        "Download analysis as Markdown",
        data=analysis,
        file_name="faulttrace-incident-analysis.md",
        mime="text/markdown",
    )

    with st.expander("Verified log evidence", expanded=False):
        evidence = [
            {
                "Evidence": f"L{event.line_number}",
                "Time": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Level": event.level,
                "Service": event.service,
                "Message": event.message,
            }
            for event in events
            if event.level in {"WARNING", "ERROR", "CRITICAL"}
        ]
        st.dataframe(pd.DataFrame(evidence), width="stretch", hide_index=True)


def render_incident_qa(events: list[LogEvent]) -> None:
    """Answer free-form incident questions using only accepted local evidence."""

    st.subheader("Ask FaultTrace")
    st.write(
        "Ask about the active incident, its likely cause, or safe recovery steps. "
        "FaultTrace answers only when the local knowledge base contains relevant evidence."
    )
    st.caption(
        "Retrieval runs first. The local chat model starts only if the evidence passes "
        "the relevance check; a generated answer may take about one minute on this PC."
    )

    question = st.text_input(
        "Question",
        placeholder="Why are requests returning HTTP 503, and what should we check first?",
        key="incident_question",
    )
    if st.button("Ask local model", type="primary", disabled=not question.strip()):
        knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
        if knowledge_base.count() == 0:
            st.session_state["qa_result"] = {
                "status": "empty",
                "answer": "The knowledge base is empty. Index a runbook before asking a question.",
                "chunks": [],
            }
        else:
            try:
                total_started = time.perf_counter()
                retrieval_started = time.perf_counter()
                with st.spinner("Checking local evidence relevance..."):
                    with FoundryEmbeddingService() as embeddings:
                        decision = retrieve_question_evidence(
                            question, knowledge_base, embeddings.embed
                        )
                retrieval_seconds = time.perf_counter() - retrieval_started

                if not decision.accepted:
                    st.session_state["qa_result"] = {
                        "status": "rejected",
                        "answer": (
                            "I don't have enough relevant local evidence to answer this "
                            "question safely. Add a related runbook or ask a question about "
                            "the active software incident."
                        ),
                        "chunks": list(decision.chunks),
                        "score": decision.best_score,
                        "threshold": decision.threshold,
                        "retrieval_seconds": retrieval_seconds,
                    }
                else:
                    prompt = build_qa_prompt(question, events, decision.chunks)
                    generation_started = time.perf_counter()
                    with st.spinner("The local model is preparing a grounded answer..."):
                        with FoundryChatService(max_tokens=260) as chat:
                            answer = chat.complete(QA_SYSTEM_PROMPT, prompt)
                    generation_seconds = time.perf_counter() - generation_started
                    citation_audit = audit_answer_citations(
                        answer, events, decision.chunks
                    )
                    st.session_state["qa_result"] = {
                        "status": "answered",
                        "answer": answer,
                        "chunks": list(decision.chunks),
                        "score": decision.best_score,
                        "threshold": decision.threshold,
                        "retrieval_seconds": retrieval_seconds,
                        "generation_seconds": generation_seconds,
                        "total_seconds": time.perf_counter() - total_started,
                        "citation_audit": citation_audit,
                    }
            except Exception as error:
                st.session_state["qa_result"] = {
                    "status": "error",
                    "answer": f"Local question answering failed: {error}",
                    "chunks": [],
                }

    result = st.session_state.get("qa_result")
    if not result:
        return

    status = result["status"]
    if status == "rejected":
        st.warning(result["answer"])
        st.caption(
            f"Best similarity: {result['score']:.3f} | Required: "
            f"{result['threshold']:.3f}"
        )
    elif status in {"empty", "error"}:
        st.error(result["answer"])
    else:
        st.markdown(result["answer"])
        st.success(
            f"Evidence check passed ({result['score']:.3f} >= "
            f"{result['threshold']:.3f}). Answer generated entirely on-device."
        )
        citation_audit = result.get("citation_audit")
        if citation_audit and citation_audit.passed:
            st.caption(
                "Citation audit passed: " + ", ".join(citation_audit.cited_labels)
            )
        elif citation_audit:
            detail = (
                ", ".join(citation_audit.invalid_labels)
                if citation_audit.invalid_labels
                else "no evidence labels were cited"
            )
            st.warning(f"Citation audit needs review: {detail}.")
        st.caption(
            f"Measured locally — retrieval: {result['retrieval_seconds']:.2f}s | "
            f"LLM generation: {result['generation_seconds']:.2f}s | "
            f"end-to-end: {result['total_seconds']:.2f}s"
        )

    chunks = result.get("chunks", [])
    if chunks:
        with st.expander("Retrieved runbook evidence", expanded=status == "rejected"):
            for index, chunk in enumerate(chunks, start=1):
                st.markdown(
                    f"**[R{index}] {chunk.source} — {chunk.heading}** "
                    f"(similarity {chunk.score:.3f})"
                )
                st.write(chunk.content)


def render_report_history() -> None:
    """Show recent locally saved analyses without loading an AI model."""

    st.subheader("Saved reports")
    repository = IncidentRepository(PROJECT_ROOT / "data" / "faulttrace.db")
    reports = repository.list_recent(limit=5)
    if not reports:
        st.caption("No reports saved yet. Generate an analysis to create one.")
        return

    for report in reports:
        label = (
            f"Report #{report.id} | {report.source_name} | "
            f"{report.event_count} events"
        )
        with st.expander(label):
            st.caption(
                f"Created: {report.created_at} | Incident window: "
                f"{report.started_at} - {report.ended_at}"
            )
            st.markdown(report.analysis_markdown)
            st.download_button(
                "Download saved report",
                data=report.analysis_markdown,
                file_name=f"faulttrace-report-{report.id}.md",
                mime="text/markdown",
                key=f"download-report-{report.id}",
            )


def render_evaluation() -> None:
    """Run and display a reproducible top-1 RAG retrieval evaluation."""

    st.subheader("RAG evaluation")
    st.write(
        "Measure whether semantic search retrieves the expected runbook for a "
        "small set of known incident queries. No chat model is used."
    )
    knowledge_base = KnowledgeBase(PROJECT_ROOT / "data" / "faulttrace.db")
    cases = available_evaluation_cases(knowledge_base)

    if st.button("Run retrieval evaluation"):
        with st.spinner("Evaluating local semantic retrieval..."):
            with FoundryEmbeddingService() as embeddings:
                st.session_state["evaluation_results"] = evaluate_retrieval(
                    knowledge_base, embeddings.embed, cases
                )

    results = st.session_state.get("evaluation_results", [])
    if not results:
        st.caption(f"Ready to run {len(cases)} evaluation cases.")
        return

    passed = sum(result.passed for result in results)
    accuracy = passed / len(results) * 100
    average_latency = sum(result.latency_seconds for result in results) / len(results)
    metric_columns = st.columns(3)
    metric_columns[0].metric("Top-1 accuracy", f"{accuracy:.0f}%")
    metric_columns[1].metric("Passed cases", f"{passed}/{len(results)}")
    metric_columns[2].metric("Average latency", f"{average_latency:.2f} sec")

    evaluation_frame = pd.DataFrame(
        [
            {
                "Result": "PASS" if result.passed else "FAIL",
                "Case": result.name,
                "Expected behavior": "Answer" if result.answerable else "Reject",
                "Expected": result.expected_source,
                "Retrieved": result.retrieved_source,
                "Section": result.retrieved_heading,
                "Similarity": round(result.score, 3),
                "Latency (sec)": round(result.latency_seconds, 2),
            }
            for result in results
        ]
    )
    st.dataframe(evaluation_frame, width="stretch", hide_index=True)


def main() -> None:
    st.set_page_config(
        page_title="FaultTrace",
        page_icon="FT",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_faulttrace_theme()
    st.markdown(
        """
        <section class="faulttrace-hero">
          <div>
            <div class="faulttrace-eyebrow">Local incident intelligence</div>
            <h1 class="faulttrace-title">FAULT<span>TRACE</span></h1>
            <p class="faulttrace-subtitle">
              Trace failures across services, retrieve operational evidence,
              and generate source-grounded postmortems without sending data off-device.
            </p>
          </div>
          <div class="faulttrace-status">LOCAL / OFFLINE</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    events, rejected, source_name = render_sidebar()

    if st.session_state.get("active_source") != source_name:
        st.session_state["active_source"] = source_name
        st.session_state.pop("runbook_results", None)
        st.session_state.pop("incident_analysis", None)
        st.session_state.pop("saved_report_id", None)
        st.session_state.pop("qa_result", None)
        st.session_state.pop("analysis_performance", None)
    st.markdown(
        f'<div class="incident-strip"><strong>ACTIVE INCIDENT</strong>'
        f'<code>{html.escape(source_name)}</code></div>',
        unsafe_allow_html=True,
    )
    redaction_count = st.session_state.get("redaction_count", 0)
    if redaction_count:
        st.info(f"Privacy filter masked {redaction_count} sensitive value(s) locally.")

    if rejected:
        st.warning(f"{len(rejected)} non-empty line(s) could not be parsed.")
        with st.expander("Show unparsed lines"):
            st.code("\n".join(rejected), language="text")

    if not events:
        st.error("No supported log events were found in this file.")
        st.stop()

    frame = events_to_frame(events)
    step_columns = st.columns(3)
    with step_columns[0].container(border=True):
        st.markdown("**1. Select incident**")
        st.caption("Choose a demo or upload your own log file.")
    with step_columns[1].container(border=True):
        st.markdown("**2. Retrieve evidence**")
        st.caption("Find the most relevant local runbook sections.")
    with step_columns[2].container(border=True):
        st.markdown("**3. Generate report**")
        st.caption("Create an instant or deep AI postmortem.")

    (
        overview_tab,
        knowledge_tab,
        analysis_tab,
        qa_tab,
        evaluation_tab,
        reports_tab,
    ) = st.tabs(
        [
            "1. Overview",
            "2. Knowledge Base",
            "3. Analysis",
            "4. Ask FaultTrace",
            "5. Evaluation",
            "6. Saved Reports",
        ]
    )

    with overview_tab:
        render_metrics(events)
        st.divider()
        render_charts(frame)
        st.divider()
        render_failure_chain(events)
        st.divider()
        render_timeline(frame)

    with knowledge_tab:
        render_knowledge_base_management()
        st.divider()
        render_runbook_search(events)

    with analysis_tab:
        render_ai_analysis(events, source_name)

    with qa_tab:
        render_incident_qa(events)

    with evaluation_tab:
        render_evaluation()

    with reports_tab:
        render_report_history()


if __name__ == "__main__":
    main()
