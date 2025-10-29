#!/usr/bin/env python3
"""
Quick test script for the procurement agent
Run this to verify the system is working before starting the server
"""
import asyncio
from dotenv import load_dotenv
from procurement_agent.workflow import create_workflow

load_dotenv()


async def test_agent():
    """Test the procurement agent with sample queries"""
    print("=" * 80)
    print("Testing Procurement Agent")
    print("=" * 80)
    print()

    # Create workflow
    workflow = create_workflow()

    # Test queries
    test_queries = [
        "What is procurement?",  # General question
        "How many orders were placed?",  # Data query
        "What's the weather today?",  # Should be rejected by guardrails
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n[Test {i}] User: {query}")
        print("-" * 80)

        result = await workflow.process(
            user_message=query,
            session_id="test_session",
            user_id="test_user"
        )

        print(f"Assistant: {result['response']}")
        print(f"Success: {result['success']}")
        print(f"Metadata: {result['metadata']}")
        print()

    print("=" * 80)
    print("Test completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_agent())
