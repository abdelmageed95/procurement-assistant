# Agent Workflow System

## Overview

The procurement assistant implements a multi-agent workflow system using LangGraph, enabling intelligent routing between specialized agents for data queries and general conversation.

## Architecture

### Multi-Agent Design

The system uses three specialized agents:

1. **Router Agent** - Classifies user intent
2. **Data Query Agent** - Handles procurement data queries
3. **Chat Agent** - Handles general conversation

Each agent is optimized for its specific task, providing better performance than a single general-purpose agent.

## LangGraph Workflow

### State Graph Structure

```python
from langgraph.graph import StateGraph, END

# Define workflow state
class State(TypedDict):
    user_message: str
    session_id: str
    user_id: str
    route: str
    response: str
    query_results: List[Dict]
    metadata: Dict
    validation_failed: bool
    recent_messages: List[Dict]
    relevant_context: List[Dict]

# Build workflow graph
workflow = StateGraph(State)

# Add nodes
workflow.add_node("input_guardrails", input_guardrails_node)
workflow.add_node("router", router_node)
workflow.add_node("data_agent", procurement_agent_node)
workflow.add_node("chat_agent", chat_agent_node)
workflow.add_node("memory_fetch", memory_fetch_node)
workflow.add_node("memory_update", memory_update_node)
workflow.add_node("output_guardrails", output_guardrails_node)

# Define edges and conditions
workflow.set_entry_point("input_guardrails")
workflow.add_conditional_edges("input_guardrails", validation_check)
workflow.add_edge("memory_fetch", "router")
workflow.add_conditional_edges("router", routing_decision)
workflow.add_edge("data_agent", "memory_update")
workflow.add_edge("chat_agent", "memory_update")
workflow.add_edge("memory_update", "output_guardrails")
workflow.add_edge("output_guardrails", END)
```

### Visual Flow

```
User Input
    |
    v
[Input Guardrails]
    |
    +-- Fail --> Rejection --> END
    |
    +-- Pass
        |
        v
[Memory Fetch] (Retrieve context)
        |
        v
[Router Agent] (Classify intent)
        |
        +-- data_query --> [Data Agent]
        |                      |
        |                      v
        |                  Execute MongoDB Query
        |                      |
        +-- general_chat --> [Chat Agent]
                               |
                               v
                           Generate Response
                               |
                               v
                        [Memory Update]
                               |
                               v
                        [Output Guardrails]
                               |
                               v
                           User Response
```

## Router Agent

### Purpose

Classifies user messages into two categories:
- **data_query**: Questions about procurement data
- **general_chat**: Greetings, help, clarifications

### Implementation

**Location**: `procurement_agent/graph/router_node.py`

```python
def router_node(state: Dict) -> Dict:
    """
    Analyzes user intent and routes to appropriate agent
    """
    user_message = state.get("user_message", "")
    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": ROUTER_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        max_completion_tokens=10
    )

    route = response.choices[0].message.content.strip().lower()

    # Validate and default
    if route not in ["data_query", "general_chat"]:
        route = "data_query"

    state["route"] = route
    print(f"Router: '{user_message[:50]}...' -> {route}")

    return state
```

### Router System Prompt

```
You are a routing assistant for a California Procurement Data system.

Your job is to classify user messages into two categories:

1. data_query: Questions about California state procurement data
   - Examples: "What's the average order value?", "Top suppliers by spending"
   - Keywords: how many, what is, show me, find, average, total, count

2. general_chat: Everything else
   - Examples: "Hello", "Thanks", "What can you do?"
   - Keywords: hello, thanks, help, what can you

CRITICAL RULES:
- Simple greetings -> general_chat
- Questions about capabilities -> general_chat
- Thank you messages -> general_chat
- Help requests -> general_chat
- Data questions -> data_query
- When in doubt -> general_chat

Respond with ONLY ONE WORD: "data_query" or "general_chat"
```

### Routing Decision

Conditional edge function:

```python
def should_route_to_data_agent(state: Dict) -> str:
    """Determine which agent to use"""
    route = state.get("route", "data_query")

    if route == "data_query":
        return "data_agent"
    else:
        return "chat_agent"
```

### Routing Examples

| User Message | Classification | Rationale |
|-------------|----------------|-----------|
| "Hello!" | general_chat | Greeting |
| "What is total spending?" | data_query | Data question |
| "Thanks for the help" | general_chat | Acknowledgment |
| "Show me top 5 suppliers" | data_query | Data query |
| "What can you do?" | general_chat | Capability question |
| "How many purchases in 2014?" | data_query | Statistical query |

## Data Query Agent

### Purpose

Handles all questions related to California procurement data:
- Generates MongoDB queries from natural language
- Executes queries against the database
- Provides natural language explanations

### Implementation

**Location**: `procurement_agent/graph/procurement_agent_node.py`

```python
def procurement_agent_node(state: Dict) -> Dict:
    """
    Data-only agent - answers using procurement database
    """
    user_message = state.get("user_message", "")

    print(f"Processing: {user_message}...")

    try:
        # Initialize MongoDB query agent
        query_agent = MongoDBQueryAgent(
            mongo_uri=Config.MONGO_URI,
            db_name=Config.MONGO_DB,
            collection_name=Config.MONGO_COLLECTION
        )

        # Generate and execute query
        result = query_agent.process_query(user_message)

        state["response"] = result["response"]
        state["query_results"] = result.get("query_results", [])
        state["metadata"] = {
            "query": result.get("query", {}),
            "success": True,
            "result_count": len(result.get("query_results", [])),
            "total_count": result.get("total_count", 0)
        }

        print(f"Query successful: {len(result.get('query_results', []))} results")

    except Exception as e:
        print(f"Query error: {e}")

        # Generate error explanation
        error_explanation = generate_error_explanation(user_message, str(e))

        state["response"] = error_explanation
        state["metadata"] = {
            "success": False,
            "error": str(e)
        }

    return state
```

### MongoDB Query Generation

The data agent uses OpenAI function calling to generate structured MongoDB queries:

```python
def generate_mongodb_query(user_query: str) -> Dict:
    """Generate MongoDB query from natural language"""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "generate_mongodb_query",
                "description": "Generate MongoDB query for procurement data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["find", "aggregate", "count"]
                        },
                        "filter": {"type": "object"},
                        "pipeline": {"type": "array"},
                        "sort": {"type": "object"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["operation"]
                }
            }
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        tools=tools,
        tool_choice="required"
    )

    return parse_function_call(response)
```

### Two-Tier Query Execution

For comprehensive data access:

```python
# Tier 1: Limited query (fast summary)
limited_results = collection.aggregate(pipeline + [{"$limit": 100}])

# Tier 2: Complete query (downloads)
complete_results = collection.aggregate(pipeline + [{"$limit": 10000}])

# Tier 3: Total count
total_count = collection.count_documents(filter)
```

### Natural Language Response Generation

```python
def generate_natural_response(query_results: List[Dict], user_query: str) -> str:
    """Generate conversational explanation"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Generate a natural, engaging explanation..."
            },
            {
                "role": "user",
                "content": f"Query: {user_query}\n\nResults: {query_results}"
            }
        ],
        temperature=0.7
    )

    return response.choices[0].message.content
```

## Chat Agent

### Purpose

Handles non-data interactions:
- Greetings and farewells
- Help requests
- General questions about capabilities
- Clarifications

### Implementation

**Location**: `procurement_agent/graph/chat_agent_node.py`

```python
def chat_agent_node(state: Dict) -> Dict:
    """
    General Chat Agent - Handles non-data queries
    """
    user_message = state.get("user_message", "")
    recent_messages = state.get("recent_messages", [])

    # Build context from recent conversation
    context = "\n".join([
        f"{msg['role']}: {msg['message']}"
        for msg in recent_messages[-5:]
    ])

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": CHAT_SYSTEM_PROMPT + f"\n\nRecent context:\n{context}"
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.7,
        max_completion_tokens=200
    )

    state["response"] = response.choices[0].message.content
    state["metadata"] = {
        "agent": "chat",
        "context_used": bool(context)
    }

    return state
```

### Chat System Prompt

```
You are a friendly assistant for a California procurement data system.

You help users with:
- Greetings and general conversation
- Explaining what data is available
- Guiding users on how to ask questions
- Clarifying capabilities and limitations

Guidelines:
- Be warm and professional
- Keep responses concise (2-3 sentences)
- Encourage users to ask data questions
- Don't make up data or statistics
- Redirect data questions to "asking about the data"

Examples:
- "Hello!" -> "Hi! I can help you explore California's procurement data..."
- "What can you do?" -> "I can answer questions about California state..."
- "Thanks!" -> "You're welcome! Let me know if you need anything else."
```

## Workflow Execution

### Synchronous Execution

For immediate responses:

```python
async def process(
    user_message: str,
    session_id: str,
    user_id: str
) -> Dict:
    """Process user message through workflow"""

    initial_state = {
        "user_message": user_message,
        "session_id": session_id,
        "user_id": user_id,
        "response": "",
        "metadata": {}
    }

    # Execute workflow
    final_state = await self.workflow.ainvoke(initial_state)

    return final_state
```

### Streaming Execution

For progressive output:

```python
async def process_with_streaming(
    user_message: str,
    session_id: str,
    user_id: str
):
    """Stream workflow execution step-by-step"""

    initial_state = {
        "user_message": user_message,
        "session_id": session_id,
        "user_id": user_id
    }

    async for event in self.workflow.astream(initial_state):
        node_name = list(event.keys())[0]
        node_output = event[node_name]

        yield {
            "node": node_name,
            "output": node_output,
            "timestamp": datetime.now().isoformat()
        }
```

## State Management

### State Schema

```python
class State(TypedDict):
    # Input
    user_message: str         # User's question
    session_id: str           # Session identifier
    user_id: str              # User identifier

    # Routing
    route: str                # "data_query" or "general_chat"

    # Memory
    recent_messages: List[Dict]   # Recent conversation
    relevant_context: List[Dict]  # Similar past queries

    # Validation
    validation_failed: bool       # Guardrails result
    failed_checks: List[str]      # Failed validation checks

    # Processing
    query_results: List[Dict]     # MongoDB query results
    complete_results: List[Dict]  # Full dataset for downloads
    total_count: int              # Actual count in database

    # Output
    response: str                 # Final response text
    metadata: Dict                # Additional information
```

### State Transitions

Each node receives state, processes it, and returns modified state:

```python
# Node 1: Input Guardrails
state = {"user_message": "Hello"}

# Node 2: Router adds route
state = {"user_message": "Hello", "route": "general_chat"}

# Node 3: Chat agent adds response
state = {
    "user_message": "Hello",
    "route": "general_chat",
    "response": "Hi! How can I help you?"
}

# Node 4: Output guardrails sanitizes
state = {
    "user_message": "Hello",
    "route": "general_chat",
    "response": "Hi! How can I help you?"
}
```

## Node Implementation Patterns

### Standard Node Pattern

```python
def node_name(state: Dict) -> Dict:
    """
    Node description

    Args:
        state: Current workflow state

    Returns:
        Modified state
    """
    # 1. Extract inputs from state
    input_data = state.get("key", default_value)

    # 2. Process data
    result = process(input_data)

    # 3. Update state
    state["output_key"] = result

    # 4. Return modified state
    return state
```

### Error Handling Pattern

```python
def node_with_error_handling(state: Dict) -> Dict:
    """Node with comprehensive error handling"""
    try:
        # Normal processing
        result = risky_operation(state)
        state["result"] = result
        state["error"] = None

    except SpecificException as e:
        # Handle specific errors
        print(f"Specific error: {e}")
        state["result"] = fallback_value
        state["error"] = str(e)

    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error: {e}")
        state["result"] = None
        state["error"] = str(e)

    return state
```

### Conditional Edge Pattern

```python
def conditional_function(state: Dict) -> str:
    """
    Determine next node based on state

    Returns:
        Next node name
    """
    if state.get("validation_failed"):
        return "end"
    elif state.get("route") == "data_query":
        return "data_agent"
    else:
        return "chat_agent"
```

## Workflow Composition

### Modular Design

Each component is independently testable:

```python
# Test router in isolation
def test_router():
    state = {"user_message": "What is total spending?"}
    result = router_node(state)
    assert result["route"] == "data_query"

# Test data agent in isolation
def test_data_agent():
    state = {"user_message": "Total spending in 2014?"}
    result = procurement_agent_node(state)
    assert "response" in result
    assert result["metadata"]["success"] == True
```

### Extension Points

Add new agents easily:

```python
# 1. Define new node
def analytics_agent_node(state: Dict) -> Dict:
    """Provides advanced analytics"""
    # ... implementation
    return state

# 2. Add to workflow
workflow.add_node("analytics_agent", analytics_agent_node)

# 3. Update routing
def extended_routing(state: Dict) -> str:
    route = state.get("route")
    if route == "analytics":
        return "analytics_agent"
    elif route == "data_query":
        return "data_agent"
    else:
        return "chat_agent"

workflow.add_conditional_edges("router", extended_routing)
```

## Performance Considerations

### Node Execution Time

Typical node latencies:

| Node | Average Time | Notes |
|------|--------------|-------|
| Input Guardrails | 1-5ms | Regex checks |
| Memory Fetch | 10-20ms | MongoDB + ChromaDB |
| Router | 200-500ms | LLM call |
| Data Agent | 1-3s | Query generation + execution |
| Chat Agent | 300-800ms | LLM call |
| Memory Update | 20-50ms | Storage operations |
| Output Guardrails | 1-2ms | String sanitization |

### Optimization Strategies

**1. Parallel Execution**

Execute independent nodes in parallel:

```python
# Execute guardrails and memory fetch in parallel
results = await asyncio.gather(
    input_guardrails_node(state),
    memory_fetch_node(state)
)
```

**2. Caching**

Cache frequent queries:

```python
@lru_cache(maxsize=100)
def cached_router_decision(user_message: str) -> str:
    """Cache routing decisions"""
    return route_classification(user_message)
```

**3. Early Returns**

Exit workflow early when possible:

```python
if state.get("validation_failed"):
    # Skip all processing
    return state
```

## Monitoring and Observability

### Logging

Each node logs its execution:

```python
def instrumented_node(state: Dict) -> Dict:
    """Node with comprehensive logging"""
    start_time = time.time()

    logger.info(f"Node started", extra={
        "node": "node_name",
        "session_id": state["session_id"],
        "user_id": state["user_id"]
    })

    result = process(state)

    duration = time.time() - start_time

    logger.info(f"Node completed", extra={
        "node": "node_name",
        "duration_ms": duration * 1000,
        "success": result.get("success", True)
    })

    return result
```

### MLflow Tracing

Automatic tracing with MLflow:

```python
@mlflow.trace(name="router", span_type="AGENT")
def router_node(state: Dict) -> Dict:
    """Router with automatic MLflow tracing"""
    # ... implementation
    return state
```

Traces capture:
- Node execution time
- Input/output state
- Nested LLM calls
- Error information

### Metrics Collection

Track workflow metrics:

```python
WORKFLOW_METRICS = {
    "total_executions": 0,
    "successful_routes": 0,
    "failed_validations": 0,
    "avg_execution_time": 0,
    "routes_by_type": {
        "data_query": 0,
        "general_chat": 0
    }
}
```

## Testing

### Unit Tests

Test individual nodes:

```bash
pytest tests/test_router_node.py
pytest tests/test_data_agent_node.py
pytest tests/test_chat_agent_node.py
```

### Integration Tests

Test full workflow:

```python
async def test_data_query_workflow():
    """Test complete data query flow"""
    workflow = ProcurementWorkflow()

    result = await workflow.process(
        user_message="What is total spending?",
        session_id="test_session",
        user_id="test_user"
    )

    assert "response" in result
    assert result["metadata"]["success"] == True
    assert len(result.get("query_results", [])) > 0

async def test_chat_workflow():
    """Test chat flow"""
    workflow = ProcurementWorkflow()

    result = await workflow.process(
        user_message="Hello!",
        session_id="test_session",
        user_id="test_user"
    )

    assert "response" in result
    assert "help" in result["response"].lower()
```

### Load Testing

Test workflow under load:

```python
async def load_test():
    """Simulate concurrent users"""
    workflow = ProcurementWorkflow()

    tasks = [
        workflow.process(f"Query {i}", f"session_{i}", f"user_{i}")
        for i in range(100)
    ]

    results = await asyncio.gather(*tasks)

    print(f"Completed {len(results)} requests")
    print(f"Success rate: {sum(r['success'] for r in results) / len(results)}")
```

## Best Practices

### Node Design

1. **Single Responsibility**: Each node does one thing well
2. **Stateless**: Nodes don't maintain internal state
3. **Idempotent**: Same input produces same output
4. **Error Handling**: Always handle exceptions gracefully

### State Management

1. **Immutable Updates**: Don't modify nested state directly
2. **Type Safety**: Use TypedDict for state schema
3. **Clear Naming**: Use descriptive state keys
4. **Minimal State**: Only store what's necessary

### Workflow Design

1. **Linear Flow**: Avoid complex branching when possible
2. **Clear Entry/Exit**: Single entry point, single exit point
3. **Testability**: Design for easy testing
4. **Observability**: Add logging and tracing

## References

- LangGraph Documentation: https://python.langchain.com/docs/langgraph
- Multi-Agent Systems: https://www.langchain.com/multi-agent
- Workflow Patterns: https://www.workflowpatterns.com/
- State Machines: https://en.wikipedia.org/wiki/Finite-state_machine
