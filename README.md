# amplifier-module-tool-memory

Persistent memory tool module for Amplifier - enables AI agents to remember facts, observations, and session context across sessions.

## Features

- **Persistent Storage**: SQLite database with automatic schema migrations
- **Observation Types**: bugfix, feature, refactor, change, discovery, decision
- **FTS5 Full-Text Search**: Fast search across all memory content
- **Session Tracking**: Track sessions with request/investigated/learned/completed summaries
- **Concept Classification**: how-it-works, why-it-exists, problem-solution, gotcha, pattern, trade-off
- **Importance Scoring**: Prioritize important memories (1-10 scale)
- **File Context**: Associate memories with files read/modified
- **Automatic Cleanup**: Old/unused memories removed when limit reached

## Tools Provided

| Tool | Description |
|------|-------------|
| `add_memory` | Store a new memory with observation type and metadata |
| `list_memories` | List memories with optional filtering by type/project |
| `search_memories` | Full-text search across memory content |
| `get_memory` | Get a specific memory by ID |
| `update_memory` | Update an existing memory |
| `delete_memory` | Delete a memory |
| `create_session` | Create a new session record |
| `update_session` | Update session with summary fields |
| `get_session` | Get session details |
| `list_sessions` | List recent sessions |
| `get_context_for_session` | Get relevant memories for session start |
| `add_file_context` | Associate a memory with a file |
| `get_file_context` | Get memories related to a file |
| `get_stats` | Get memory store statistics |
| `compact` | Remove old/low-importance memories |
| `export_memories` | Export memories to JSON |

## Installation

```yaml
# Via source in bundle.yaml
tools:
  - module: tool-memory
    source: git+https://github.com/michaeljabbour/amplifier-module-tool-memory@v0.1.0
    config:
      storage_path: ~/.amplifier/memories.db
      max_memories: 1000
      enable_fts: true
      enable_sessions: true
```

## Observation Types

- `bugfix` - Something broken, now fixed
- `feature` - New capability added
- `refactor` - Code restructured, behavior unchanged
- `change` - Generic modification
- `discovery` - Learning about existing system
- `decision` - Architectural choice with rationale

## Concept Types

- `how-it-works` - Mechanism or process explanation
- `why-it-exists` - Rationale for design choice
- `problem-solution` - Problem and its resolution
- `gotcha` - Non-obvious behavior or pitfall
- `pattern` - Recurring approach or structure
- `trade-off` - Competing concerns and balance

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `storage_path` | string | `~/.amplifier/memories.db` | SQLite database path |
| `max_memories` | int | 1000 | Maximum memories to store |
| `enable_fts` | bool | true | Enable FTS5 full-text search |
| `enable_sessions` | bool | true | Enable session tracking |

## Schema v2 Features

The v2 schema adds:
- `observation_type` field for classification
- `concept` field for knowledge categorization
- `title` and `subtitle` for progressive disclosure
- `facts` array for structured learnings
- `files_read` and `files_modified` for file context
- `session_id` for session association
- FTS5 virtual table for fast full-text search
- Sessions table with summary fields

## Example Usage

```
User: Remember that the config parser has a gotcha - it silently ignores invalid keys
AI: [calls add_memory with observation_type="discovery", concept="gotcha"]
    Memory stored successfully.

User: What gotchas have I discovered?
AI: [calls list_memories with observation_type="gotcha"]
    Found: "Config parser silently ignores invalid keys"
```

## Requirements

- Python 3.11+
- amplifier-core
- pydantic>=2.0

## License

MIT License - See LICENSE file
