# Agent Coordination Workflow Template

Copy this for any multi-agent feature build. Adjust the phases, models, and task as needed.

---

## Agent Roles

| Role | Model | Count | Responsibility |
|------|-------|-------|---------------|
| **Coordinator** | `deepseek/deepseek-v4-pro` | 1 | Decompose features → assign tasks → track → iterate |
| **Build agents** | `deepseek/deepseek-chat` | 1-N | Implement individual features (one per file/unit) |
| **Review agent** | `deepseek/deepseek-chat` | 1 | Review built work for correctness, consistency, edge cases |
| **Audit agent** | `deepseek/deepseek-v4-pro` | 1 | Monitor coordinator: stay on task, no rabbit holes |
| **Research agent** | `deepseek/deepseek-chat` | 1 | Central research for all other agents (docs, APIs, patterns) |
| **Test agent** | `deepseek/deepseek-chat` | 1 | Write tests for built features |
| **Doc agent** | `deepseek/deepseek-chat` | 1 | Write/validate `.ai/` documentation, keep it AI-readable |

## Phases

### 0. Scaffolding (human or main agent)
- Install dependencies
- Create initial file structure
- Define schemas / interfaces
- Verify basic build passes

### 1. Coordinator Kickoff
```
spawn coordinator (deepseek-v4-pro, isolated, runTimeoutSeconds=1200)
  → reads codebase
  → decomposes into specific build tasks (one API route = one task, one page = one task)
  → spawns build agents in parallel
  → tracks completions
  → spawns review agent after each batch
  → iterates on review feedback
  → spawns test + doc agents
  → runs final build verification
  → reports status
```

### 2. Build Phase
```
for each task in parallel (max 4-5 concurrent):
  spawn build agent (deepseek-chat, isolated)
    → receives single clear task: "create file X with contents Y"
    → writes files directly
    → returns what was created
```

### 3. Review Phase
```
after each batch of builds:
  spawn review agent (deepseek-chat, isolated)
    → reads all built files
    → checks: correctness, consistency, edge cases, integration breakage
    → returns list of issues (critical / medium / low)
```

### 4. Iteration
```
coordinator reviews feedback:
  → fix critical issues (spawn build agents for fixes)
  → note medium/low issues for backlog
  → re-run review if significant changes
```

### 5. Integration Review
```
after all features built:
  spawn review agent (deepseek-chat, isolated)
    → checks cross-feature consistency (imports, types, API contracts)
    → runs npx nuxt build (or equivalent)
    → tests API endpoints
    → reports any integration breakage
```

### 6. Documentation
```
spawn doc agent (deepseek-chat, isolated):
  → write .ai/OVERVIEW.md (architecture, table relationships, data flow)
  → write .ai/API.md (endpoint reference, request/response examples)
  → keep it short — bullet points, AI-readable
```

### 7. Tests
```
spawn test agent (deepseek-chat, isolated):
  → write basic tests for critical paths
  → API route tests, validation tests, DB queries
```

---

## Coordinator Task Template

Copy and customize this when spawning the coordinator:

```
You are the Coordinator agent for building {FEATURE_NAME}.

## Project Location
{PROJECT_ROOT}

## Existing Codebase
- {KEY_FILE_1} — {description}
- {KEY_FILE_2} — {description}

## What To Build

### Phase 1: {PHASE_NAME}
1. {FILE_1} — {description}
2. {FILE_2} — {description}

### Phase 2: {PHASE_NAME}
3. {FILE_3} — {description}

... (as needed)

## Build Process
1. READ the existing files: {KEY_FILES}
2. Spawn build agents in parallel (use sessions_spawn with runtime="subagent", model="deepseek/deepseek-chat")
3. Build agents should WRITE actual files
4. Review all work for consistency (use sessions_spawn for review agents)
5. Run {BUILD_COMMAND} to verify
6. Spawn doc agent for .ai/ docs
7. Report final status

## Rules
- Get code WORKING. No stubs or TODOs.
- {TECH_STACK_SPECIFICS}
- {UI_LIBRARY_COMPONENTS}
- DB: {DB_IMPORT_PATTERN}
- Keep it practical, no over-engineering
- Documents in {DOCS_DIR} — short bullet points
```

---

## Sub-Agent Spawn Pattern

```typescript
// Coordinator spawns build agents like this:
sessions_spawn({
  label: "build-{feature-name}",
  runtime: "subagent",
  model: "deepseek/deepseek-chat",
  runTimeoutSeconds: 300,
  task: "Create {FILE_PATH} with {DESCRIPTION}. Follow these patterns: {EXAMPLES}"
})

// Coordinator spawns review agent like this:
sessions_spawn({
  label: "review-{phase}",
  runtime: "subagent",
  model: "deepseek/deepseek-chat",
  runTimeoutSeconds: 600,
  task: "Review all files in {DIRECTORY}. Check for: correctness, consistency, edge cases, integration breakage. Return list of issues with severity."
})

// Coordinator spawns audit agent like this:
sessions_spawn({
  label: "audit-coordinator",
  runtime: "subagent",
  model: "deepseek/deepseek-v4-pro",
  runTimeoutSeconds: 300,
  task: "Audit the coordinator's progress. Are we on track? Any rabbit holes? What's the next priority?"
})
```

---

## Anti-Patterns to Avoid

- ❌ Coordinator building features itself instead of delegating
- ❌ Build agents creating broken stubs / TODO comments
- ❌ Review agent being too nice — flag everything
- ❌ Skipping the integration review (imports break silently)
- ❌ Documentation written for humans instead of AI (long prose)
- ❌ Tests that test the framework instead of the feature logic
- ❌ Coordinator waiting for all agents sequentially instead of spawning in parallel

---

## Directory Convention

```
project/
├── .ai/                  # AI-readable docs (always)
│   ├── OVERVIEW.md
│   ├── API.md
│   └── AGENT-WORKFLOW.md
├── app/                  # Application source
│   ├── pages/            # Frontend pages
│   ├── server/           # Shared server code (DB, types)
│   └── app.vue           # Root layout
├── server/               # Nitro server routes + plugins
│   ├── api/              # API route handlers
│   └── plugins/          # Server plugins (DB init, middleware)
└── package.json
```
