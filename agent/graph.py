"""LangGraph StateGraph wiring for the Job Application Agent."""

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes import (
    parse_resume, analyze_jd, gap_analysis, tailor_resume,
    generate_cover_letter, generate_interview_qs, route_after_gap_analysis,
)

graph_builder = StateGraph(AgentState)

graph_builder.add_node("parse_resume", parse_resume)
graph_builder.add_node("analyze_jd", analyze_jd)
graph_builder.add_node("gap_analysis", gap_analysis)
graph_builder.add_node("tailor_resume", tailor_resume)
graph_builder.add_node("generate_cover_letter", generate_cover_letter)
graph_builder.add_node("generate_interview_qs", generate_interview_qs)

# Parallel: parse_resume and analyze_jd run simultaneously (independent inputs)
graph_builder.add_edge(START, "parse_resume")
graph_builder.add_edge(START, "analyze_jd")
graph_builder.add_edge("parse_resume", "gap_analysis")
graph_builder.add_edge("analyze_jd", "gap_analysis")

graph_builder.add_conditional_edges(
    "gap_analysis",
    route_after_gap_analysis,
    {"has_gaps": "tailor_resume", "no_gaps": "generate_cover_letter"},
)
graph_builder.add_edge("tailor_resume", "generate_cover_letter")
graph_builder.add_edge("generate_cover_letter", "generate_interview_qs")
graph_builder.add_edge("generate_interview_qs", END)

graph = graph_builder.compile()
