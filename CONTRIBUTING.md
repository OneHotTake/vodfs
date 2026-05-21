# Contributing to VOD HTTP Filesystem Plugin

Thank you for your interest in contributing! This guide will help you get started.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Assume good intentions
- Help others learn

## Getting Started

### Prerequisites

- Python 3.10+
- Dispatcharr v0.20.0 or later
- Git
- Basic understanding of Django, FastAPI, and HTTP

### Development Setup

1. **Fork and clone**:
```bash
git clone https://github.com/YOUR_USERNAME/dispatcharr-vodfs.git
cd dispatcharr-vodfs
```

2. **Create a branch**:
```bash
git checkout -b feature/your-feature-name
```

3. **Make your changes**
4. **Test thoroughly**
5. **Submit a pull request**

## Development Workflow

### Making Changes

1. Edit code in `plugin/` directory
2. Update tests in `tests/` directory
3. Update documentation if needed
4. Run tests locally
5. Commit changes with clear messages

### Commit Messages

Follow conventional commits:

```
feat: add episode hydration cooldown
fix: resolve path traversal vulnerability
docs: update installation instructions
test: add integration tests for tree building
refactor: simplify directory listing logic
```

### Testing

Before submitting, ensure:

- [ ] All unit tests pass: `python -m pytest tests/`
- [ ] Manual testing with Dispatcharr completed
- [ ] No linting errors
- [ ] Documentation updated

## Pull Request Process

### PR Description

Include:
- Summary of changes
- Motivation for the change
- Testing performed
- Related issues
- Screenshots (if applicable)

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Commits are squashed/clean

### Review Process

1. Automated checks must pass
2. At least one maintainer approval required
3. Address feedback promptly
4. Request review when ready for merge

## Project Guidelines

### Code Style

- Follow PEP 8
- Use type hints
- Document public APIs
- Keep functions focused and small

### Architecture

- Keep components loosely coupled
- Use dependency injection where appropriate
- Separate business logic from I/O
- Design for testability

### Security

- Never expose credentials
- Validate all input
- Handle errors gracefully
- Use safe defaults

### Performance

- Avoid N+1 queries
- Cache expensive operations
- Use async I/O where beneficial
- Profile before optimizing

## Testing Guidelines

### Unit Tests

Test individual functions and classes in isolation.

```python
def test_path_resolution():
    tree = VirtualTree()
    tree.build()
    node = tree.resolve_path("/Movies/All/")
    assert node is not None
    assert node.name == "All"
```

### Integration Tests

Test components together with real Dispatcharr instance.

```python
@pytest.mark.live
def test_integration_with_dispatcharr():
    integrator = DispatcharrIntegrator()
    movies = integrator.get_all_movies()
    assert len(movies) > 0
```

### Manual Tests

- Plugin enable/disable
- HTTP server start/stop
- Directory browsing
- File access (HEAD/GET)
- rclone mount
- Plex scan
- Playback

## Documentation

### Update README.md for:
- New features
- Configuration changes
- Breaking changes

### Update Architecture Docs for:
- Design changes
- New components
- Performance optimizations

### Update Code Docs for:
- New functions/classes
- Changed behavior
- API changes

## Release Process

Releases are managed by maintainers:

1. Update `plugin.json` version
2. Update `CHANGELOG.md`
3. Run full test suite
4. Tag release: `git tag v1.0.0`
5. Push tag: `git push origin v1.0.0`
6. Create GitHub release
7. Submit to Dispatcharr plugin repository

## Issues and Bug Reports

When reporting issues, include:

- Dispatcharr version
- Plugin version
- Python version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Logs/error messages
- Screenshots (if applicable)

## Feature Requests

Before requesting features:

- Check existing issues
- Consider if it fits project scope
- Propose implementation approach
- Discuss with maintainers

## Questions?

- GitHub Issues: https://github.com/OneHotTake/dispatcharr-vodfs/issues
- Discord: https://discord.gg/dispatcharr

## License

By contributing, you agree that your contributions will be licensed under the MIT License.