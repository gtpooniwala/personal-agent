# 📚 Personal Agent Documentation

Comprehensive documentation for the Personal Agent MVP - an intelligent AI assistant powered by LangGraph orchestrator architecture.

## Documentation Index

### 🏗️ **Core Architecture**
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - System architecture and design patterns
- [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md) - Async run model migration contract and sequencing
- [`SYSTEM_FLOW.md`](SYSTEM_FLOW.md) - Detailed system flow, logic, and decision-making processes
- [`FEATURES_OVERVIEW.md`](FEATURES_OVERVIEW.md) - Comprehensive overview of all implemented features

### 🚀 **Setup & Development**
- [`SETUP.md`](SETUP.md) - Installation and setup instructions
- [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) - Development workflow and guidelines
- [`../AGENT.md`](../AGENT.md) - AI coding agent workflow contract
- [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md) - Branch/worktree/PR/merge policy for Codex + Claude
- [`API.md`](API.md) - API reference and endpoint documentation
- [`TESTING.md`](TESTING.md) - Testing framework and guidelines

### 🗂️ **Execution Tracking**
- [`WORKBOARD.md`](WORKBOARD.md) - AI execution board (`Now` / `Next` / `Later` / `Done`)
- [`ROADMAP.md`](ROADMAP.md) - Sequenced improvement and feature roadmap
- GitHub issue tracker: [Repository Issues](https://github.com/gtpooniwala/personal-agent/issues)

### 🔧 **Features & Tools**
- [`features/`](features/) - Detailed documentation for each system feature
  - [Conversation Summarization](features/CONVERSATION_SUMMARISATION.md)
  - [Document Q&A System](features/DOCUMENT_UPLOAD_SYSTEM.md)
  - [User Profile System](features/USER_PROFILE_SYSTEM.md)
  - [Gmail Integration](features/GMAIL_TOOL.md)
  - [Internet Search Tool](features/INTERNET_SEARCH_TOOL.md)
  - [Response Agent System](features/RESPONSE_AGENT_SYSTEM.md)
  - [Time Formatting](features/TIME_FORMATTING_IMPROVEMENT.md)
  - [Title Generation](features/TITLE_GENERATION_SYSTEM.md)
  - [Selective RAG](features/SELECTIVE_RAG_VALIDATION.md)

### 📊 **Quality & Testing**
- [`TESTING.md`](TESTING.md) - Comprehensive testing framework
- Test Results - See main [test validation](../tests/)

### 🐛 **Debugging & Troubleshooting**
- [`debugging/`](debugging/) - Debugging guides and session dumps
- [`FEATURE_TEMPLATE.md`](FEATURE_TEMPLATE.md) - Template for new feature documentation

## 🎯 **Quick Navigation**

### For Developers
- **Getting Started**: [`SETUP.md`](SETUP.md) → [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md)
- **Architecture Deep Dive**: [`ARCHITECTURE.md`](ARCHITECTURE.md) → [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md)
- **Adding Features**: [`FEATURE_TEMPLATE.md`](FEATURE_TEMPLATE.md) → [`features/`](features/)

### For Users
- **Installation**: [`SETUP.md`](SETUP.md)
- **Feature Overview**: Main [`README.md`](../README.md)
- **API Usage**: [`API.md`](API.md)

### For Contributors
- **Development Setup**: [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md)
- **Testing**: [`TESTING.md`](TESTING.md)
- **Code Quality**: [Test suite](../tests/)

## 📖 **Documentation Standards**

All documentation follows these principles:
- **Clear Structure**: Consistent formatting and organization
- **Code Examples**: Working examples for all features
- **Up-to-Date**: Synchronized with current implementation
- **Comprehensive**: Covers architecture, usage, and troubleshooting

### Documentation Guidelines

When adding new feature documentation:

1. **Location**: Create new feature docs in `docs/features/`
2. **Naming**: Use descriptive, UPPERCASE file names (e.g., `FEATURE_NAME_SYSTEM.md`)
3. **Structure**: Include:
   - Overview and purpose
   - Features implemented
   - Technical implementation details
   - User experience examples
   - Configuration options
   - Testing instructions
   - Files modified

4. **Format**: Use clear markdown with:
   - Emojis for visual organization (🎯 🔧 📊 etc.)
   - Code blocks for technical details
   - Bulleted lists for features
   - Examples and use cases

## 🔄 **Maintenance**

This documentation is actively maintained to reflect the current state of the system:
- All major features are documented before implementation
- Architecture changes are reflected in relevant docs
- Test coverage and validation results are kept current
- Outdated documentation is archived in appropriate subfolders

---

**This documentation structure supports the growing complexity of the Personal Agent while maintaining clear organization and easy navigation for developers, users, and contributors.**
