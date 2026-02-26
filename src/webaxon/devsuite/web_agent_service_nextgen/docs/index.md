# Web Agent Service NextGen - Documentation

Welcome to the Web Agent Service NextGen documentation. This is a modular, queue-based web agent service that provides a clean, maintainable architecture for interactive web automation.

## 📚 Documentation Structure

### Getting Started
- [Quick Start Guide](getting-started/quick-start.md) - Get up and running in minutes
- [Installation](../README.md#installation) - Installation instructions

### User Guides
- [Import Guide](guides/imports.md) - How to import and use the service components
- [Configuration Guide](guides/configuration.md) - Comprehensive configuration examples
- [Session Management](guides/session-management.md) - Understanding session lifecycle and management
- [Monitoring Guide](guides/monitoring.md) - Session monitoring and status tracking
- [Template Versioning](guides/template-versioning.md) - Managing and switching prompt templates

### Architecture
- [Main README](../README.md) - Architecture overview and design principles
- Component documentation embedded in main README

### Testing
- [Integration Tests](testing/integration-tests.md) - Running and understanding integration tests

### Reference
- [Task Summaries](archive/task-summaries/) - Development history and implementation notes

## 🚀 Quick Links

### For New Users
1. Start with the [Quick Start Guide](getting-started/quick-start.md)
2. Review [Configuration Examples](guides/configuration.md)
3. Read the [Import Guide](guides/imports.md) to understand the module structure

### For Developers
1. Read the [Main README](../README.md) for architecture overview
2. Check [Integration Tests](testing/integration-tests.md) for test examples
3. Review [Task Summaries](archive/task-summaries/) for implementation details

### Common Tasks
- **Configure the service**: See [Configuration Guide](guides/configuration.md)
- **Manage sessions**: See [Session Management](guides/session-management.md)
- **Monitor service**: See [Monitoring Guide](guides/monitoring.md)
- **Switch templates**: See [Template Versioning](guides/template-versioning.md)
- **Import modules**: See [Import Guide](guides/imports.md)

## 📖 Main Components

The service is organized into four main modules:

### Core Module (`core/`)
- **ServiceConfig**: Centralized configuration management
- **SessionManager**: Thread-safe session lifecycle management
- **AgentFactory**: Centralized agent creation

### Communication Module (`communication/`)
- **QueueManager**: Queue service lifecycle management
- **MessageHandlers**: Control message processing

### Agents Module (`agents/`)
- **AgentRunner**: Thread management for agent execution
- **TemplateManagerWrapper**: Template version management

### Session Module (`session/`)
- **SessionMonitor**: Session monitoring and cleanup
- **SessionLogManager**: Structured session logging and artifacts

## 💡 Key Features

- ✅ **Modular Architecture**: Clean separation of concerns
- ✅ **Queue-Based Communication**: Decoupled debugger and service
- ✅ **Thread-Safe**: Proper locking for concurrent access
- ✅ **Centralized Configuration**: Environment variable support
- ✅ **Session Management**: Automatic cleanup of idle sessions
- ✅ **Template Versioning**: Per-session template versions
- ✅ **Comprehensive Testing**: Unit, integration, and property-based tests

## 🔗 External Resources

- [Source Code](../) - Browse the source code
- [Test Suite](../../test/devsuite/web_agent_service_nextgen/) - Explore the tests
- [Verification Scripts](../verify_*.py) - Validation scripts

## 📝 Contributing

For development-related documentation, see:
- [Documentation Organization Report](DOCUMENTATION_ORGANIZATION_REPORT.md) - How the docs are organized
- [Task Summaries](archive/task-summaries/) - Detailed implementation notes
- Code docstrings in source files

## 🆘 Need Help?

- Check the [Quick Start](getting-started/quick-start.md) for common issues
- Review the relevant guide in the [User Guides](#user-guides) section
- Read the troubleshooting sections in the [Main README](../README.md)

---

*This documentation is organized for easy navigation. Start with the Quick Start guide if you're new, or jump directly to the relevant guide for your specific needs.*
