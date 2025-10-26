# Coding Standards

Coding standards, principles, and best practices for the USDXFixGap project.

---

## Core Principles

### **KISS (Keep It Simple, Stupid)**
- Favor simple, straightforward solutions over clever or complex ones
- Early returns reduce nesting depth
- Avoid unnecessary abstraction layers

### **DRY (Don't Repeat Yourself)**
- Extract common functionality into reusable components
- Use generic methods instead of operation-specific variants
- Create shared utility services for repeated operations
- Avoid copy-paste code - refactor into shared functions

### **SOLID Principles**

**Single Responsibility Principle (SRP):**
- Each class has one reason to change
- Models handle data, services handle business logic, actions orchestrate

**Open/Closed Principle (OCP):**
- Classes open for extension, closed for modification
- Generic error handling extends without code changes

**Liskov Substitution Principle (LSP):**
- Subclasses must be substitutable for base classes
- Maintain contracts and behavior expectations

**Interface Segregation Principle (ISP):**
- Small, focused interfaces rather than large general ones
- Clients shouldn't depend on methods they don't use

**Dependency Inversion Principle (DIP):**
- Depend on abstractions, not concretions
- Inject dependencies via AppData (preferred) or use static service methods (acceptable)

---

## Code Style

### **PEP 8 Compliance**
- **Line Length**: 120 characters (configured in Black)
- **Indentation**: 4 spaces
- **Naming Conventions**:
  - `snake_case` for functions, variables, modules
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Imports**: Grouped (standard library, third-party, local), sorted alphabetically
- **Blank Lines**: 2 between top-level definitions, 1 between methods

### **Type Hints**
- Add type hints to all function signatures
- Use `Optional[]` for nullable parameters
- Use `Union[]` for multiple types
- Improves IDE support, documentation, and catches bugs early

### **Code Formatting**
- **Black formatter**: Automatic formatting (line-length=120)
- Run `run.bat cleanup` before committing
- CI enforces Black formatting

---

## Error Handling

### **Model Error State**
- Models manage error states via `set_error()` and `clear_error()` methods
- `set_error(message)` sets status to ERROR with message
- `clear_error()` resets to NOT_PROCESSED (neutral ready state)

### **Status Mapping**
- **GapInfo is single source of truth** for MATCH/MISMATCH/UPDATED/SOLVED/ERROR
- Update `gap_info.status`, `Song.status` updates automatically via owner hook
- **QUEUED/PROCESSING**: Set directly by actions (transient workflow states)
- **MATCH/MISMATCH/UPDATED/SOLVED/ERROR**: Set via `gap_info.status` mapping

### **Service Error Communication**
- Services return results or raise exceptions
- Actions handle results and update model state
- Never set model state inside services

### **Exception Handling**
- Use specific exception types
- Always log exceptions with context
- No silent `except:` without logging
- Re-raise unknown exceptions after logging

---

## Testing Guidelines

### **Test Organization**
- **Unit Tests**: Test individual components in isolation (models, services, single functions)
- **Integration Tests**: Test component interactions (actions + services + workers)
- **File Naming**: `test_*.py` in `tests/` directory
- **Test Naming**: `test_<function_name>_<scenario>` (e.g., `test_delete_song_success`)

### **When to Use Unit vs Integration Tests**
- **Unit Tests**: Parsing/validation, formatting logic, selection/routing, pure services
- **Integration Tests**: External process piping (Demucs/ffmpeg), worker queue behavior, signals/UI sync, real file I/O

### **Mocking Strategy**
- Mock external dependencies (file system, network, external processes)
- Use `patch()` for mocking services in actions
- Mock worker signals for testing action handlers
- Never mock the system under test

### **Test Coverage**
- Aim for >80% coverage for critical paths
- Test both success and error paths
- Include edge cases and boundary conditions

---

## Performance Considerations

### **Avoid Repeated Heavy Operations**
- Cache results where safe
- Reuse computed values
- Batch operations when possible

### **Worker Queue Pattern**
- All long-running operations MUST be queued via `worker_queue.add_task()`
- Never execute workers inline (blocks UI, bypasses status tracking)
- Use `start_now=True` for user-initiated actions, `start_now=False` for chained tasks

### **Large Dataset Handling**
- Use batch loading for UI updates (50 items at a time)
- Defer heavy processing until after load completes
- Emit batch signals instead of per-item signals

---

## Documentation Standards

### **Docstrings**
- Use docstrings for all public classes, methods, and functions
- Format: Google style (summary line, Args, Returns, Raises)
- Include parameter types and return types in docstring if not using type hints

### **Comments**
- Explain **why**, not **what**
- Comment complex algorithms, non-obvious logic, workarounds
- Keep comments up-to-date with code changes

### **TODOs**
- Format: `# TODO: Description` or `# FIXME: Description`
- Include context and rationale
- Create issues for non-trivial TODOs

---

## Code Quality Gates

Before committing, ensure:
- ✅ All tests pass (`run.bat test`)
- ✅ Code formatted with Black (`run.bat cleanup`)
- ✅ No functions with CCN > 15 (`run.bat analyze`)
- ✅ No functions with NLOC > 100 (`run.bat analyze`)
- ✅ No flake8 style violations (`run.bat analyze`)
- ✅ No mypy type errors (`run.bat analyze`)

**CI will reject PRs that fail these checks.**

---

## Architecture Patterns

### **Layer Responsibilities**
- **Models**: Data structures, state management, validation
- **Services**: Business logic, stateless operations, no signals
- **Actions**: Orchestration, connect workers/services, signal via data models
- **Workers**: Background tasks, emit `started`/`finished`/`error` signals
- **UI**: User interaction, display updates, connect to data model signals

### **Signal Usage**
- Models emit signals when data changes (e.g., `songs.updated.emit(song)`)
- Actions update models, then emit via data model aggregators
- Workers emit task-specific signals
- Services never emit signals
- See [Architecture](architecture.md) for detailed signal patterns

### **Dependency Injection**
- Use `AppData` container for dependency injection
- Services can be injected instances (testable) or static methods (simpler)
- Prefer injection for complex services with dependencies

---

## Common Anti-Patterns to Avoid

- ❌ Actions emitting signals directly (update models instead)
- ❌ Models calling services (services operate on models)
- ❌ Services emitting signals (return results/exceptions)
- ❌ Duplicate error handling methods (use generic `set_error()`)
- ❌ Inline worker execution (use worker queue)
- ❌ Silent exception handling without logging
- ❌ Duplicate status writes (GapInfo status → Song status mapping)
- ❌ Discarding worker error signal payloads

---

## File Organization

### **Naming Conventions**
- Filenames reflect content and responsibility
- If purpose changes, **rename** the file
- If mixed concerns, **split** into focused files

### **Size Triggers**
- File > ~500 lines → consider refactoring
- Function > ~80-100 lines → consider splitting
- Class with > 10 methods → consider splitting responsibilities

### **Import Organization**
- Standard library imports first
- Third-party imports second
- Local imports last
- Within each group: alphabetically sorted
- No unused imports (autoflake removes them)

---

## Version Control

### **Commit Messages**
- Use imperative mood ("Add feature", not "Added feature")
- Format: `<type>: <subject>` (e.g., `fix: Handle edge case in gap detection`)
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Keep subject line < 72 characters
- Add body for complex changes

### **Branch Strategy**
- `main`: Stable releases
- `develop`: Active development
- Feature branches: `feature/<description>`
- Hotfix branches: `hotfix/<description>`

---

## References

- [Architecture](architecture.md) - System design, layers, signal patterns
- [Development Guide](DEVELOPMENT.md) - Setup, testing, CI/CD workflows
- [GitHub Copilot Instructions](../.github/copilot-instructions.md) - AI assistance guidelines

---

## Summary Checklist

**Before Committing:**
- [ ] Tests pass
- [ ] Code formatted (Black)
- [ ] Quality checks pass (CCN ≤ 15, NLOC ≤ 100)
- [ ] No unused imports
- [ ] Type hints added
- [ ] Docstrings updated
- [ ] Followed layer responsibilities
- [ ] No anti-patterns used

**Before PR:**
- [ ] All commits follow message format
- [ ] Breaking changes documented
- [ ] README updated if needed
- [ ] CI passes
