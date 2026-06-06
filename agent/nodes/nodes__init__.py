"""
agent/nodes/
────────────
All four LangGraph node functions, importable from one place.
"""
from agent.nodes.planner import planner_node
from agent.nodes.researcher import researcher_node
from agent.nodes.critic import critic_node, route_after_critic
from agent.nodes.synthesizer import synthesizer_node

__all__ = [
    "planner_node",
    "researcher_node",
    "critic_node",
    "route_after_critic",
    "synthesizer_node",
]
