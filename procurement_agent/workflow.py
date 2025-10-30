"""
LangGraph Multi-Agent Workflow for Procurement System
"""
import os
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any
from .config import Config
from .graph import (
    input_guardrails_node,
    output_guardrails_node,
    should_continue_after_validation,
    memory_fetch_node,
    memory_update_node,
    procurement_agent_node,
    router_node,
    should_route_to_data_agent,
    chat_agent_node
)


# Disable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "false"


class ProcurementWorkflow:
    """LangGraph workflow for procurement agent system"""

    def __init__(self):
        self.workflow = self._build_workflow()

    def _build_workflow(self):
        """Build the LangGraph workflow with router"""
        workflow = StateGraph(dict)

        # Add nodes
        if Config.ENABLE_GUARDRAILS:
            workflow.add_node("input_guardrails", input_guardrails_node)
            workflow.add_node("output_guardrails", output_guardrails_node)

        workflow.add_node("memory_fetch", memory_fetch_node)
        workflow.add_node("router", router_node)
        workflow.add_node("data_agent", procurement_agent_node)  # Renamed for clarity
        workflow.add_node("chat_agent", chat_agent_node)
        workflow.add_node("memory_update", memory_update_node)

        # Build edges
        if Config.ENABLE_GUARDRAILS:
            # Start with input validation
            workflow.add_edge(START, "input_guardrails")

            # Conditional edge after validation
            workflow.add_conditional_edges(
                "input_guardrails",
                should_continue_after_validation,
                {
                    "continue": "memory_fetch",
                    "end": "output_guardrails"
                }
            )

            # Memory -> Router -> [Data Agent OR Chat Agent]
            workflow.add_edge("memory_fetch", "router")

            # Router decides which agent to use
            workflow.add_conditional_edges(
                "router",
                should_route_to_data_agent,
                {
                    "data_agent": "data_agent",
                    "chat_agent": "chat_agent"
                }
            )

            # Both agents go to output guardrails
            workflow.add_edge("data_agent", "output_guardrails")
            workflow.add_edge("chat_agent", "output_guardrails")
            workflow.add_edge("output_guardrails", "memory_update")
        else:
            # No guardrails - direct flow with router
            workflow.add_edge(START, "memory_fetch")
            workflow.add_edge("memory_fetch", "router")

            # Router decides which agent to use
            workflow.add_conditional_edges(
                "router",
                should_route_to_data_agent,
                {
                    "data_agent": "data_agent",
                    "chat_agent": "chat_agent"
                }
            )

            # Both agents go to memory update
            workflow.add_edge("data_agent", "memory_update")
            workflow.add_edge("chat_agent", "memory_update")

        workflow.add_edge("memory_update", END)

        return workflow.compile()

    async def process(
        self,
        user_message: str,
        session_id: str,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Process a user message through the workflow

        Args:
            user_message: User's input message
            session_id: Session ID for tracking
            user_id: User ID

        Returns:
            Dict with response and metadata
        """
        print(f"\nProcessing: {user_message[:60]}...")

        # Initial state
        initial_state = {
            "user_message": user_message,
            "session_id": session_id,
            "user_id": user_id,
            "memory_context": {},
            "agent_response": "",
            "metadata": {},
            "input_validation": {},
            "output_validation": {},
            "query_results": [],
            "complete_results": [],  # For complete data downloads
            "route": ""  # Will be set by router
        }

        try:
            # Run workflow
            final_state = await self.workflow.ainvoke(initial_state)

            print("Workflow completed")

            return {
                "response": final_state["agent_response"],
                "metadata": final_state["metadata"],
                "memory_context": final_state["memory_context"].get("context_summary", ""),
                "query_results": final_state.get("query_results", []),
                "complete_results": final_state.get("complete_results", []),  # Complete results for downloads
                "success": True
            }

        except Exception as e:
            print(f"Workflow error: {e}")
            return {
                "response": (
                    "I encountered an error processing your request. "
                    "Please try again."
                ),
                "metadata": {"error": str(e)},
                "memory_context": "",
                "query_results": [],
                "complete_results": [],
                "success": False
            }

    def process_sync(
        self,
        user_message: str,
        session_id: str,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Synchronous version of process"""
        print(f"\nProcessing (sync): {user_message[:60]}...")

        initial_state = {
            "user_message": user_message,
            "session_id": session_id,
            "user_id": user_id,
            "memory_context": {},
            "agent_response": "",
            "metadata": {},
            "input_validation": {},
            "output_validation": {},
            "query_results": [],
            "route": ""  # Will be set by router
        }

        try:
            final_state = self.workflow.invoke(initial_state)

            print("Workflow completed (sync)")

            return {
                "response": final_state["agent_response"],
                "metadata": final_state["metadata"],
                "memory_context": final_state["memory_context"].get("context_summary", ""),
                "query_results": final_state.get("query_results", []),
                "success": True
            }

        except Exception as e:
            print(f"Workflow error (sync): {e}")
            return {
                "response": (
                    "I encountered an error processing your request. "
                    "Please try again."
                ),
                "metadata": {"error": str(e)},
                "memory_context": "",
                "query_results": [],
                "success": False
            }


def create_workflow() -> ProcurementWorkflow:
    """Create a new procurement workflow instance"""
    return ProcurementWorkflow()
