# Contributing to TraderAI

Thank you for your interest in contributing to TraderAI!

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/traderai.git
   cd traderai
   ```

3. Set up development environment:
   ```bash
   # Using Docker (recommended)
   docker-compose up -d

   # Or local setup
   poetry install
   cd apps/web && npm install
   ```

4. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Code Style

**Python:**
- Use [Black](https://black.readthedocs.io/) for formatting
- Use [Ruff](https://beta.ruff.rs/docs/) for linting
- Follow PEP 8 guidelines
- Max line length: 100 characters

```bash
# Format code
poetry run black apps/ tests/

# Lint code
poetry run ruff check apps/ tests/
```

**TypeScript/JavaScript:**
- Use ESLint configuration
- Follow Airbnb style guide

```bash
cd apps/web
npm run lint
```

## Testing

All new features must include tests:

```bash
# Run all tests
docker-compose exec api pytest tests/ -v

# Run specific test
docker-compose exec api pytest tests/test_signal_profit_filter.py -v

# Check coverage
docker-compose exec api pytest tests/ --cov=apps --cov-report=html
```

**Critical tests to maintain:**
- ✅ Minimum 2% profit filter
- ✅ Backfill resume functionality
- ✅ Walk-forward validation (no leakage)
- ✅ Hit rate calculation (≥55% target)

## Commit Messages

Use conventional commits format:

```
feat: add sentiment analysis plugin
fix: correct SL calculation for short positions
docs: update API documentation
test: add tests for drift detection
refactor: simplify feature engineering pipeline
```

## Pull Request Process

1. Update tests for your changes
2. Update documentation (README.md, ARCHITECTURE.md) if needed
3. Ensure all tests pass:
   ```bash
   docker-compose exec api pytest tests/ -v
   ```

4. Create pull request with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots (if UI changes)

5. Wait for CI checks to pass
6. Request review from maintainers

## Code Review Guidelines

Reviewers will check for:
- Code quality and style
- Test coverage
- Documentation updates
- Performance implications
- Security considerations
- Backward compatibility

## Feature Requests

Submit feature requests via GitHub Issues with:
- Clear use case
- Expected behavior
- Impact on existing functionality

## Bug Reports

Submit bugs via GitHub Issues with:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Docker version, etc.)
- Logs/screenshots

## Questions?

- Open a Discussion on GitHub
- Check existing Issues and Discussions

Thank you for contributing! 🚀
