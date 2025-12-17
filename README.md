# amplifier-module-tool-memory

Persistent memory tool module for Amplifier - enables AI agents to remember facts across sessions.

## Features

- **Persistent Storage**: Memories stored in SQLite, survive restarts
- **Categories**: Organize memories by type (learning, decision, preference, etc.)
- **Importance Scoring**: Prioritize important memories
- **Keyword Search**: Find relevant memories by searching
- **Automatic Cleanup**: Old/unused memories removed when limit reached

## Tools Provided

| Tool | Description |
|------|-------------|
| `add_memory` | Store a new memory |
| `list_memories` | List memories with optional filtering |
| `search_memories` | Search memories by keyword |
| `get_memory` | Get a specific memory by ID |
| `update_memory` | Update an existing memory |
| `delete_memory` | Delete a memory |

## Installation

### In a Bundle

```yaml
tools:
  - module: tool-memory
    source: git+https://github.com/yourusername/amplifier-module-tool-memory@main
    config:
      storage_path: ~/.amplifier/memories.db
      max_memories: 1000
```

### Local Development

```bash
export AMPLIFIER_MODULE_TOOL_MEMORY=$(pwd)
amplifier run "remember that I prefer TypeScript over JavaScript"
```

## Memory Categories

- `learning` - Knowledge acquired (facts, concepts)
- `decision` - Decisions made (architecture, design choices)
- `issue_solved` - Problems and their solutions
- `preference` - User preferences (style, formatting)
- `pattern` - Recurring behaviors observed
- `recipe` - Reusable workflows
- `coding_style` - Code style preferences
- `tech_stack` - Technology preferences
- `project_context` - Project-specific knowledge
- `communication` - Communication preferences
- `general` - Default category

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `storage_path` | string | `~/.amplifier/memories.db` | SQLite database path |
| `max_memories` | int | 1000 | Maximum memories to store |

## Example Usage

```
User: Remember that I always use 4-space indentation in Python
AI: [calls add_memory with category="coding_style"]
    Memory stored successfully.

User: What are my coding preferences?
AI: [calls search_memories with query="coding preferences"]
    Found: "I always use 4-space indentation in Python"
```

## License

MIT
