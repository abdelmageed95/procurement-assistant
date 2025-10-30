# Memory Management System

## Overview

The procurement assistant implements a dual-memory architecture combining short-term and long-term memory storage to provide context-aware responses while maintaining conversation history.

## Architecture

### Dual Memory System

The system uses two complementary memory stores:

1. **Short-Term Memory (MongoDB)**
   - Recent conversation history
   - Fast access for current session context
   - Message-level granularity
   - Session-based organization

2. **Long-Term Memory (ChromaDB)**
   - Semantic search using embeddings
   - Stores meaningful Q&A pairs
   - Context retrieval for similar queries
   - Duplicate detection

## Short-Term Memory

### Implementation

**Storage**: MongoDB collection `conversation_history`

**Location**: `procurement_agent/memory/short_term.py`

**Data Structure**:
```python
{
    "session_id": str,      # Unique session identifier
    "user_id": str,         # User identifier
    "role": str,            # "user" or "assistant"
    "message": str,         # Message content
    "timestamp": datetime,  # Message timestamp
    "metadata": dict        # Additional context
}
```

### Key Functions

**Store Message**
```python
def store_message(
    session_id: str,
    user_id: str,
    role: str,
    message: str,
    metadata: dict = None
) -> None
```

Stores a single message with session context.

**Retrieve Recent Messages**
```python
def get_recent_messages(
    session_id: str,
    limit: int = 10
) -> List[Dict]
```

Retrieves the N most recent messages for a session.

**Clear Session**
```python
def clear_session(session_id: str) -> None
```

Removes all messages for a specific session.

### Configuration

Default settings in `procurement_agent/config.py`:

```python
SHORT_TERM_LIMIT = 10  # Number of recent messages to retrieve
```

### Usage Pattern

1. **Store User Message**
   ```python
   short_term_memory.store_message(
       session_id="session_123",
       user_id="user_456",
       role="user",
       message="What is the total spending in 2014?"
   )
   ```

2. **Store Assistant Response**
   ```python
   short_term_memory.store_message(
       session_id="session_123",
       user_id="user_456",
       role="assistant",
       message="The total spending in 2014 was $156.7M"
   )
   ```

3. **Retrieve Context**
   ```python
   recent_messages = short_term_memory.get_recent_messages(
       session_id="session_123",
       limit=10
   )
   ```

## Long-Term Memory

### Implementation

**Storage**: ChromaDB vector database

**Location**: `procurement_agent/memory/long_term.py`

**Embedding Model**: `all-MiniLM-L6-v2` (384 dimensions)

**Data Structure**:
```python
{
    "query": str,           # User question
    "response": str,        # Assistant answer
    "metadata": {
        "session_id": str,
        "user_id": str,
        "timestamp": str,
        "query_type": str
    }
}
```

### Key Functions

**Store Q&A Pair**
```python
def store_interaction(
    query: str,
    response: str,
    session_id: str,
    user_id: str,
    metadata: dict = None
) -> None
```

Stores a question-answer pair with embeddings for semantic search.

**Retrieve Similar Queries**
```python
def get_relevant_context(
    query: str,
    top_k: int = 3
) -> List[Dict]
```

Finds semantically similar past interactions using vector similarity.

**Check for Duplicates**
```python
def is_duplicate(
    query: str,
    recent_queries: List[str],
    threshold: float = 0.9
) -> bool
```

Detects if a query is very similar to recent queries.

### Configuration

Default settings in `procurement_agent/config.py`:

```python
LONG_TERM_TOP_K = 3  # Number of similar queries to retrieve
CHROMA_PERSIST_DIR = "./chroma_db"  # ChromaDB storage location
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Sentence transformer model
```

### Semantic Search

ChromaDB uses cosine similarity on embeddings to find related queries:

1. **Query Embedding**: Convert user query to 384-dim vector
2. **Similarity Search**: Find top-k most similar vectors
3. **Context Retrieval**: Return corresponding Q&A pairs

### Duplicate Detection

Prevents storing redundant information:

```python
# Check last 5 messages for duplicates
if not long_term_memory.is_duplicate(
    query=user_message,
    recent_queries=last_5_queries,
    threshold=0.9  # 90% similarity
):
    long_term_memory.store_interaction(query, response, ...)
```

## Workflow Integration

### Memory Nodes in LangGraph

The workflow includes dedicated memory nodes:

**Memory Fetch Node**
```python
def memory_fetch_node(state: Dict) -> Dict:
    """Retrieve relevant context from both memory systems"""
    session_id = state.get("session_id")
    user_message = state.get("user_message")

    # Short-term: Recent conversation
    recent_messages = short_term_memory.get_recent_messages(
        session_id=session_id,
        limit=10
    )

    # Long-term: Similar past queries
    relevant_context = long_term_memory.get_relevant_context(
        query=user_message,
        top_k=3
    )

    state["recent_messages"] = recent_messages
    state["relevant_context"] = relevant_context

    return state
```

**Memory Update Node**
```python
def memory_update_node(state: Dict) -> Dict:
    """Store current interaction in both memory systems"""
    session_id = state.get("session_id")
    user_id = state.get("user_id")
    user_message = state.get("user_message")
    response = state.get("response")

    # Store in short-term memory
    short_term_memory.store_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        message=user_message
    )

    short_term_memory.store_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        message=response
    )

    # Store in long-term memory (if not duplicate)
    if not is_duplicate(user_message):
        long_term_memory.store_interaction(
            query=user_message,
            response=response,
            session_id=session_id,
            user_id=user_id
        )

    return state
```

### Execution Flow

```
User Query
    |
    v
Memory Fetch Node
    |
    +-- Short-term: Last 10 messages
    +-- Long-term: 3 similar queries
    |
    v
Agent Processing (with context)
    |
    v
Generate Response
    |
    v
Memory Update Node
    |
    +-- Store in short-term
    +-- Store in long-term (if unique)
    |
    v
Return Response
```

## Session Management

### Session Lifecycle

1. **Session Creation**
   - Generate unique session_id
   - Initialize empty conversation history
   - No pre-loading required

2. **Active Session**
   - Messages stored incrementally
   - Context retrieved on each query
   - Session persists across page refreshes

3. **Session Cleanup**
   - Optional: Clear session on user request
   - Automatic: Old sessions can be archived

### Session Persistence

Frontend stores session_id in localStorage:

```javascript
// Create new session
const sessionId = `session_${Date.now()}_${Math.random()}`;
localStorage.setItem('currentSession', sessionId);

// Restore session
const sessionId = localStorage.getItem('currentSession');
```

Backend retrieves full history on reconnection.

## Context Building

### Context Window Construction

When processing a query, context is built from:

1. **Recent Messages** (Short-term)
   ```python
   recent_context = "\n".join([
       f"{msg['role']}: {msg['message']}"
       for msg in recent_messages[-5:]  # Last 5 exchanges
   ])
   ```

2. **Similar Queries** (Long-term)
   ```python
   similar_context = "\n".join([
       f"Q: {ctx['query']}\nA: {ctx['response']}"
       for ctx in relevant_context
   ])
   ```

3. **Combined Context**
   ```python
   full_context = f"""
   Recent Conversation:
   {recent_context}

   Related Past Queries:
   {similar_context}
   """
   ```

### LLM Integration

Context is prepended to the system prompt:

```python
messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT + "\n\n" + full_context
    },
    {
        "role": "user",
        "content": current_query
    }
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)
```

## Performance Considerations

### Short-Term Memory

**Query Performance**:
- MongoDB indexed on session_id
- Fast retrieval: < 10ms for 10 messages
- No embedding overhead

**Storage**:
- Lightweight: ~1KB per message
- Scalable: Millions of messages

### Long-Term Memory

**Query Performance**:
- ChromaDB optimized for vector search
- Embedding generation: ~50ms
- Similarity search: ~20ms for 1000 vectors

**Storage**:
- Vector size: 384 floats (1.5KB per entry)
- Includes metadata and original text
- Efficient for 100K+ entries

### Memory Limits

**Short-term**:
- Configurable limit (default: 10 messages)
- Prevents context window overflow
- Keeps prompts under token limits

**Long-term**:
- Unlimited storage capacity
- Semantic search scales to millions
- Automatic duplicate filtering

## Configuration Options

### Environment Variables

```env
# MongoDB Short-term Memory
MONGO_URI=mongodb://localhost:27017
MONGO_DB=procurement_db
MONGO_HISTORY_COLLECTION=conversation_history

# ChromaDB Long-term Memory
CHROMA_PERSIST_DIR=./chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Memory Limits
SHORT_TERM_LIMIT=10
LONG_TERM_TOP_K=3
DUPLICATE_THRESHOLD=0.9
```

### Tuning Parameters

**Short-term Limit**:
- Lower (5-10): Faster, less context
- Higher (15-20): More context, slower

**Long-term Top-K**:
- Lower (1-3): Focused context
- Higher (5-10): Broader context

**Duplicate Threshold**:
- Lower (0.7-0.8): More storage, less filtering
- Higher (0.9-0.95): Less storage, aggressive filtering

## Advanced Features

### Smart Duplicate Detection

Compares new queries against recent history:

```python
def is_duplicate(query: str, recent_queries: List[str]) -> bool:
    """Check if query is similar to recent queries"""
    query_embedding = embed(query)

    for recent in recent_queries[-5:]:  # Last 5 only
        recent_embedding = embed(recent)
        similarity = cosine_similarity(query_embedding, recent_embedding)

        if similarity > 0.9:  # 90% threshold
            return True

    return False
```

Benefits:
- Prevents storage bloat
- Reduces redundant embeddings
- Maintains data quality

### Context Ranking

Long-term memory results are ranked by relevance:

```python
relevant_context = long_term_memory.get_relevant_context(
    query=user_message,
    top_k=3
)

# Results are pre-sorted by similarity score
# Most relevant query appears first
```

### Session Analytics

Track memory usage per session:

```python
def get_session_stats(session_id: str) -> Dict:
    """Get statistics for a session"""
    messages = short_term_memory.get_all_messages(session_id)

    return {
        "message_count": len(messages),
        "duration": messages[-1]["timestamp"] - messages[0]["timestamp"],
        "avg_response_length": mean([len(m["message"]) for m in messages]),
        "query_types": count_by_type(messages)
    }
```

## Best Practices

### When to Use Short-term Memory

- Tracking current conversation flow
- Maintaining question/answer pairs
- Handling clarification questions
- Session-specific context

### When to Use Long-term Memory

- Learning from past interactions
- Finding similar query patterns
- Providing examples from history
- Building knowledge base

### Memory Hygiene

1. **Regular Cleanup**: Archive old sessions
2. **Duplicate Prevention**: Enable threshold checking
3. **Context Limits**: Don't exceed LLM token limits
4. **Quality Control**: Store only meaningful interactions

## Troubleshooting

### Issue: Context Not Retrieved

**Symptoms**: Agent doesn't remember past conversation

**Solutions**:
- Check session_id consistency
- Verify MongoDB connection
- Confirm SHORT_TERM_LIMIT > 0

### Issue: Slow Response Times

**Symptoms**: Queries take too long

**Solutions**:
- Reduce SHORT_TERM_LIMIT
- Reduce LONG_TERM_TOP_K
- Check MongoDB indexes
- Monitor ChromaDB performance

### Issue: Duplicate Storage

**Symptoms**: Same queries stored repeatedly

**Solutions**:
- Enable duplicate detection
- Adjust DUPLICATE_THRESHOLD
- Check recent query buffer size

## API Reference

### Short-Term Memory

```python
class ShortTermMemory:
    def store_message(session_id, user_id, role, message, metadata)
    def get_recent_messages(session_id, limit)
    def clear_session(session_id)
    def get_all_messages(session_id)
    def count_messages(session_id)
```

### Long-Term Memory

```python
class LongTermMemory:
    def store_interaction(query, response, session_id, user_id, metadata)
    def get_relevant_context(query, top_k)
    def is_duplicate(query, recent_queries, threshold)
    def clear_all()
    def count_interactions()
```

## Testing

### Unit Tests

```bash
# Test short-term memory
pytest tests/test_short_term_memory.py

# Test long-term memory
pytest tests/test_long_term_memory.py

# Test memory integration
pytest tests/test_memory_integration.py
```

### Manual Testing

```python
# Test short-term storage
from procurement_agent.memory.short_term import ShortTermMemory

memory = ShortTermMemory()
memory.store_message("test_session", "user1", "user", "Hello")
messages = memory.get_recent_messages("test_session")
assert len(messages) == 1

# Test long-term semantic search
from procurement_agent.memory.long_term import LongTermMemory

memory = LongTermMemory()
memory.store_interaction("What is total spending?", "Answer", "session1", "user1")
results = memory.get_relevant_context("What was the spending?", top_k=1)
assert len(results) > 0
```

## References

- MongoDB Documentation: https://docs.mongodb.com/
- ChromaDB Documentation: https://docs.trychroma.com/
- Sentence Transformers: https://www.sbert.net/
- Vector Search Best Practices: https://www.pinecone.io/learn/vector-similarity/
