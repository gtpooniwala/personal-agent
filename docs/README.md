# Personal Agent Documentation

## 📚 Documentation Structure

This folder contains comprehensive documentation for the Personal Agent project, organized by category for easy navigation.

## 🗂️ Folder Organization

### `/features/`
Detailed documentation for specific features and implementations:

- **[Time Formatting Improvement](features/TIME_FORMATTING_IMPROVEMENT.md)** - Smart time formatting with unit selection and pluralization
- **[Title Generation System](features/TITLE_GENERATION_SYSTEM.md)** - Intelligent conversation title generation with multiple triggers
- **[Selective RAG Validation](features/SELECTIVE_RAG_VALIDATION.md)** - Document-based Q&A system validation
- **[Document Q&A Context](features/DOCUMENT_QA_CONTEXT.txt)** - Context and examples for document question answering

### Main Project Files
- **[AGENT.md](../AGENT.md)** - Core agent technical documentation and status
- **[README.md](../README.md)** - Project overview and setup instructions

### Development Resources
- **[Development Guide](DEVELOPMENT_GUIDE.md)** - Quick reference for adding new features
- **[Feature Template](FEATURE_TEMPLATE.md)** - Template for documenting new features

## 📝 Documentation Standards

When adding new feature documentation:

1. **Location**: Create new feature docs in `docs/features/`
2. **Naming**: Use descriptive, UPPERCASE file names (e.g., `FEATURE_NAME_SYSTEM.md`)
3. **Structure**: Include:
   - Overview
   - Features implemented
   - Technical implementation
   - User experience
   - Configuration
   - Testing instructions
   - Files modified

4. **Format**: Use clear markdown with:
   - Emojis for visual organization
   - Code blocks for technical details
   - Bulleted lists for features
   - Examples where helpful

## 🔄 Maintenance

- Update this index when adding new feature documentation
- Keep feature docs focused on specific implementations
- Cross-reference related features when applicable
- Archive outdated documentation in `/archive/` subfolder

## 🚀 Quick Navigation

For developers looking for specific information:

- **Setup & Installation** → [Main README](../README.md)
- **Agent Architecture** → [AGENT.md](../AGENT.md)
- **Feature Details** → Individual files in [features/](features/)
- **Testing** → Each feature doc includes testing instructions

---

This documentation structure supports the growing complexity of the Personal Agent while maintaining clear organization and easy navigation.
