# Project Structure

## Complete File Tree

```
precurement_experiments/
│
├── procurement_agent/                    # Main application package
│   ├── __init__.py                      # Package initialization
│   ├── config.py                        # System configuration
│   ├── workflow.py                      # LangGraph workflow builder
│   ├── mongodb_query.py                 # MongoDB query agent (from notebook)
│   │
│   ├── api/                             # FastAPI backend
│   │   ├── __init__.py
│   │   └── main.py                      # Server, WebSocket, REST endpoints
│   │
│   ├── graph/                           # LangGraph workflow nodes
│   │   ├── __init__.py
│   │   ├── guardrails.py                # Input/output validation
│   │   ├── memory_nodes.py              # Memory fetch/update nodes
│   │   └── procurement_agent_node.py    # Core agent logic
│   │
│   ├── memory/                          # Memory systems
│   │   ├── __init__.py
│   │   ├── short_term.py                # MongoDB recent messages
│   │   └── long_term.py                 # ChromaDB semantic search
│   │
│   └── static/                          # Frontend UI
│       ├── index.html                   # Chat interface
│       ├── style.css                    # Professional styling
│       └── app.js                       # WebSocket client
│
├── inspriation/                         # Reference implementations
│   ├── memory/
│   │   └── MEMORY.md                    # Memory system inspiration
│   └── workflow.py                      # Workflow pattern inspiration
│
├── experiment.ipynb                     # Original MongoDB query notebook
│
├── run_server.py                        # Server startup script
├── test_agent.py                        # Quick test script
│
├── requirements.txt                     # Python dependencies
├── .env.example                         # Environment template
│
├── README.md                            # Full documentation
├── QUICKSTART.md                        # Quick start guide
└── PROJECT_STRUCTURE.md                 # This file
```

## Component Descriptions

### Core Application (`procurement_agent/`)

#### `config.py`
- System-wide configuration
- MongoDB, memory, LLM settings
- Guardrails and agent restrictions
- FastAPI server configuration

#### `workflow.py`
- LangGraph StateGraph builder
- Orchestrates all nodes and edges
- Handles both async and sync processing
- Workflow: Guardrails → Memory → Agent → Guardrails → Memory

#### `mongodb_query.py`
- Reuses query system from experiment.ipynb
- Natural language → MongoDB query conversion
- Fast mode (simple formatting) & Explain mode (LLM explanation)
- Handles datetime parsing and safe query execution

### API Layer (`procurement_agent/api/`)

#### `main.py`
- FastAPI application
- WebSocket endpoint (`/ws/{session_id}`)
- REST endpoints (`/chat`, `/health`, `/sessions/...`)
- Static file serving
- Real-time bidirectional communication

### LangGraph Nodes (`procurement_agent/graph/`)

#### `guardrails.py`
- **Input validation**: Topic checking (procurement-related only)
- **Output validation**: Response safety checks
- **Conditional edge**: Route based on validation result
- Uses keyword matching + LLM verification

#### `memory_nodes.py`
- **memory_fetch_node**: Retrieves short-term + long-term context
- **memory_update_node**: Saves conversation to both memory systems
- Global memory instances (initialized once)

#### `procurement_agent_node.py`
- **Core agent logic**: Routes to MongoDB or general knowledge
- **Data queries**: Uses MongoDBQueryAgent for stats
- **General questions**: Uses LLM for procurement knowledge
- Smart keyword detection for query type

### Memory Systems (`procurement_agent/memory/`)

#### `short_term.py`
- MongoDB-based recent message storage
- Session-based conversation tracking
- Fast retrieval of last N messages
- Context summarization

#### `long_term.py`
- ChromaDB-based semantic search
- Sentence Transformers for local embeddings (no API costs)
- Finds relevant past conversations
- Distance-based similarity ranking

### Frontend UI (`procurement_agent/static/`)

#### `index.html`
- Clean, accessible chat interface
- Header with title and connection status
- Scrollable message area
- Auto-resizing textarea input

#### `style.css`
- Professional, calm color palette
- Eye-comfort design (soft blues, greens, neutrals)
- Responsive layout (mobile-friendly)
- Smooth animations and transitions

#### `app.js`
- WebSocket client with auto-reconnect
- Real-time message handling
- Typing indicators
- Session management
- Message formatting

## Data Flow

### User Sends Message

```
User Input (UI)
    ↓
WebSocket (app.js)
    ↓
FastAPI WebSocket Handler (api/main.py)
    ↓
Workflow.process() (workflow.py)
    ↓
LangGraph StateGraph Execution
    ↓
Input Guardrails (graph/guardrails.py)
    ↓ (if valid)
Memory Fetch (graph/memory_nodes.py)
    ├── Short-term (memory/short_term.py → MongoDB)
    └── Long-term (memory/long_term.py → ChromaDB)
    ↓
Procurement Agent (graph/procurement_agent_node.py)
    ├── Data query → MongoDB Query (mongodb_query.py)
    └── General question → LLM
    ↓
Output Guardrails (graph/guardrails.py)
    ↓
Memory Update (graph/memory_nodes.py)
    ├── Save to short-term (MongoDB)
    └── Save to long-term (ChromaDB)
    ↓
Response to WebSocket
    ↓
Display in UI
```

## Key Technologies

### Backend
- **LangGraph**: Workflow orchestration with StateGraph
- **FastAPI**: Modern async web framework
- **PyMongo**: MongoDB driver
- **OpenAI**: LLM for queries and responses

### Memory
- **MongoDB**: Short-term conversation storage
- **ChromaDB**: Vector database for semantic search
- **Sentence Transformers**: Local embedding generation

### Frontend
- **WebSocket**: Real-time bidirectional communication
- **Vanilla JavaScript**: No framework overhead
- **Modern CSS**: Custom properties, flexbox, animations

## Configuration Files

### `requirements.txt`
All Python dependencies with pinned versions

### `.env.example`
Template for environment variables:
- OPENAI_API_KEY (required)
- MongoDB settings (optional)
- Server configuration (optional)

## Utility Scripts

### `run_server.py`
- Checks for API key
- Loads environment variables
- Starts uvicorn server
- Pretty startup messages

### `test_agent.py`
- Quick verification script
- Tests guardrails, memory, queries
- Runs before starting server
- Useful for debugging

## Documentation

### `README.md`
- Complete system documentation
- Architecture overview
- Installation and setup
- API reference
- Configuration guide

### `QUICKSTART.md`
- 3-step getting started guide
- Sample queries
- Troubleshooting tips
- Quick reference

### `PROJECT_STRUCTURE.md`
- This file
- Complete file tree
- Component descriptions
- Data flow diagrams

## Inspiration Files

### `inspriation/memory/MEMORY.md`
- Three-tier memory architecture
- Short-term, long-term, structured facts
- ChromaDB + Sentence Transformers patterns

### `inspriation/workflow.py`
- LangGraph StateGraph examples
- Node and edge patterns
- Conditional routing
- Progress tracking

## Database Collections

### MongoDB (`procurement_db`)
- **purchase_orders**: Main data (from CSV)
  - Preprocessed dates (datetime objects)
  - Preprocessed prices (floats)
  - California purchases >$5000, 2012-2015

### MongoDB (`procurement_memory`)
- **conversations**: Short-term message storage
  - session_id, user_id, role, content
  - timestamp for ordering

### ChromaDB (`./chroma_db`)
- **procurement_memory**: Long-term semantic storage
  - Embeddings from Sentence Transformers
  - Conversation turn documents
  - Metadata with session info

## Environment Variables

### Required
- `OPENAI_API_KEY`: OpenAI API key for LLM

### Optional (with defaults)
- `MONGO_URI`: MongoDB connection string
- `MONGO_DB`: Database name
- `MONGO_COLLECTION`: Collection name
- `API_HOST`: Server host
- `API_PORT`: Server port

## Build and Run

```bash
# Install
pip install -r requirements.txt

# Configure
export OPENAI_API_KEY='your-key'

# Test (optional)
python test_agent.py

# Run
python run_server.py

# Access
open http://localhost:8000
```

## Customization Points

1. **Colors**: Edit CSS variables in `static/style.css`
2. **Guardrails**: Modify allowed topics in `config.py`
3. **Memory**: Adjust limits in `config.py`
4. **LLM**: Change model in `config.py`
5. **Workflow**: Add nodes in `graph/` and register in `workflow.py`
6. **UI**: Modify `static/index.html` and `static/app.js`

## File Counts

- Python files: 13
- Frontend files: 3
- Config files: 3
- Documentation: 3
- Total: 22 files

## Lines of Code (Approx)

- Backend: ~1,500 lines
- Frontend: ~500 lines
- Config/Docs: ~800 lines
- Total: ~2,800 lines
