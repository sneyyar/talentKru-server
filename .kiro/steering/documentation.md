# Documentation Standards

**Last Updated:** June 6, 2026

## Overview

All AI-generated documentation and detailed technical guides should be organized in the `ai_docs/` directory with appropriate subdirectory structure. This keeps the root directory clean and improves documentation discoverability.

## Directory Structure

```
ai_docs/
├── README.md (navigation and index)
├── test-architecture/         # Test framework documentation
│   ├── README.md
│   ├── ARCHITECTURE_FIXED.md
│   ├── FIX_SUMMARY.md
│   ├── IMPLEMENTATION_GUIDE.md
│   └── COMPLETION_REPORT.md
├── infrastructure/            # Infrastructure and deployment docs
├── feature-name/              # Feature-specific documentation
└── tools/                      # Development tools and utilities
```

## Documentation Categories

### Test Architecture (`ai_docs/test-architecture/`)
- Test framework design and implementation
- Testing patterns and best practices
- Test infrastructure updates
- Test coverage reports
- Test troubleshooting guides

**Example files**:
- `ARCHITECTURE_FIXED.md` - Design rationale and technical details
- `IMPLEMENTATION_GUIDE.md` - How-to guide with examples
- `FIX_SUMMARY.md` - Quick reference
- `COMPLETION_REPORT.md` - Formal completion documentation

### Infrastructure (`ai_docs/infrastructure/`)
- Database setup and migration
- Deployment procedures
- Container configuration
- Environment setup
- Infrastructure troubleshooting

**Example files**:
- Database setup guides
- Docker configuration
- CI/CD pipeline documentation
- Environment variables

### Feature Documentation (`ai_docs/{feature-name}/`)
- Feature specifications and design
- Implementation guides
- API documentation
- Data models
- Feature-specific troubleshooting

**Example files**:
- Feature design documents
- Migration guides
- Integration guides
- API references

### Tools (`ai_docs/tools/`)
- Development tool documentation
- Build system guides
- Task automation documentation
- CLI tool references

**Example files**:
- Task runner guides (invoke tasks)
- Build system documentation
- Testing tool configuration

## File Naming Conventions

### Descriptive Naming
- Use descriptive names that indicate content
- Format: `SUBJECT_ASPECT.md` (e.g., `ARCHITECTURE_FIXED.md`, `IMPLEMENTATION_GUIDE.md`)
- Avoid vague names like `DOCUMENT1.md` or `INFO.md`

### Capitalization
- Directory names: lowercase with hyphens (e.g., `test-architecture`, `feature-name`)
- File names: UPPERCASE_WITH_UNDERSCORES.md (e.g., `ARCHITECTURE_FIXED.md`)

## When to Create AI Documentation

Create AI documentation (in `ai_docs/`) for:
- ✅ Complex technical implementations
- ✅ Comprehensive design documentation
- ✅ Detailed troubleshooting guides
- ✅ Multi-step implementation guides
- ✅ Architecture overviews
- ✅ Completion reports

Avoid AI documentation for:
- ❌ Quick code comments (use inline comments)
- ❌ API docs (use docstrings)
- ❌ Standard setup (use steering files)
- ❌ One-off notes (use team communication)

## Steering Files vs AI Documentation

### Steering Files (`.kiro/steering/`)
- **Purpose**: Context for all developer tasks in specific area
- **Scope**: Essential patterns and guidelines
- **Size**: Concise (typically 200-500 lines)
- **Audience**: All developers on the feature/area
- **Format**: Markdown with actionable examples

**Files**:
- `test.md` - Testing guidelines
- `tech.md` - Tech stack and build system
- `structure.md` - Project structure
- `product.md` - Product overview

### AI Documentation (`.ai_docs/`)
- **Purpose**: Detailed technical reference and deep dives
- **Scope**: Comprehensive technical details
- **Size**: Larger documents (500+ lines)
- **Audience**: Developers needing deep understanding
- **Format**: Markdown with sections, references, and examples

**Examples**:
- Test architecture implementation guide
- Feature design documents
- Migration guides
- Completion reports

## Creating New AI Documentation

### Directory Setup
1. Create subdirectory: `mkdir ai_docs/{subdirectory}/`
2. Create README: `ai_docs/{subdirectory}/README.md`
3. Add files: `ai_docs/{subdirectory}/{SUBJECT}.md`

### File Structure
Each documentation file should include:
- Title heading
- Last updated date
- Executive summary or quick navigation
- Detailed content organized by sections
- References and links to related docs

### Example Header
```markdown
# Feature Name - Component Documentation

**Last Updated:** June 6, 2026

## Overview
Brief description of content and audience.

## Quick Navigation
Links to key sections for different use cases.

## Key Sections
### Section 1: ...
### Section 2: ...
...
```

## Documentation Maintenance

### Version Control
- Commit documentation changes with related code
- Use descriptive commit messages: "docs: Update test architecture guide"
- Include documentation updates in PR descriptions

### Updates
- Update timestamps when documentation changes
- Link related documents together
- Maintain README.md in directories

### Cleanup
- Remove outdated documentation
- Consolidate related documents into directories
- Archive completed task documentation

## References

Existing documentation structure:
- `ai_docs/identity-and-access/` - Identity and access implementation docs
- `ai_docs/interview-workflow/` - Interview workflow documentation
- `ai_docs/test-architecture/` - Test framework documentation

## Best Practices

✅ **DO**
- Use descriptive file names
- Include table of contents or quick navigation
- Add internal links between related docs
- Include dates (Last Updated)
- Organize by subdirectories (one concept per directory)
- Reference steering files for quick guidelines

❌ **DON'T**
- Put detailed technical docs in root directory
- Create vague file names
- Duplicate content between files
- Leave documentation without dates
- Mix different topics in one document
- Create files without directory organization
