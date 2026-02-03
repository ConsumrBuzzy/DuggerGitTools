# DuggerCore Git Tools (DGT)

A modular, language-agnostic CLI utility designed to automate the development lifecycle across diverse tech stacks.

## Features

- **Multi-language Support**: Python, Rust, Chrome Extensions with extensible provider architecture
- **Automated Workflows**: Pre-flight checks, testing, linting, and post-flight validation
- **Smart Detection**: Automatically detects project types and applies appropriate tooling
- **Beautiful CLI**: Rich terminal output with progress bars and structured information
- **Type Safety**: Full type hints with Pydantic validation
- **Observability**: Comprehensive logging with Loguru

## Quick Start

### Installation

```bash
# Install with uv (recommended)
uv install duggercore-git-tools

# Or with pip
pip install duggercore-git-tools
```

### Basic Usage

```bash
# Initialize DGT for your project
dgt init .

# Check project status
dgt status

# Commit with automated workflow
dgt commit -m "Add new feature"

# Dry run to see what would happen
dgt commit -m "Add new feature" --dry-run

# Get detailed project information
dgt info
```

## Architecture

### Provider System

DGT uses a modular provider architecture where each language ecosystem has its own provider:

- **PythonProvider**: Handles venv verification, pytest, ruff/black linting
- **RustProvider**: Manages cargo fmt, cargo check, cargo build
- **ChromeExtensionProvider**: Validates manifest.json and handles extension-specific checks

### Workflow

When you run `dgt commit`:

1. **Detection**: Identify project type and appropriate provider
2. **Environment Validation**: Ensure required tools are available
3. **Pre-flight Checks**: Run language-specific validation (linting, testing, building)
4. **Commit**: Create formatted commit with language tags
5. **Post-flight Checks**: Run additional validation after commit
6. **Push**: Automatically push to remote (if configured)

## Configuration

Create a `dgt.toml` file in your project root:

```toml
[logging]
level = "INFO"

[providers.python]
enabled = true

[providers.rust]
enabled = true

[providers.chrome_extension]
enabled = true
auto_bump_version = false
```

## Provider-specific Features

### Python Provider

- Virtual environment detection and validation
- Dependency installation (requirements.txt, pyproject.toml)
- Linting with ruff, black, or flake8
- Testing with pytest
- Type checking with mypy
- Security scanning with safety

### Rust Provider

- Code formatting with cargo fmt
- Compilation checking with cargo check
- Linting with cargo clippy
- Testing with cargo test
- Release builds with cargo build --release
- Benchmarking with cargo bench

### Chrome Extension Provider

- manifest.json validation against Chrome Extension schema
- Required file verification (icons, scripts, etc.)
- HTML and JavaScript syntax validation
- Build script execution (npm run build)
- Version bumping with semantic versioning
- Package size validation

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/duggercore/duggercore-git-tools.git
cd duggercore-git-tools

# Install in development mode
uv install -e .

# Install development dependencies
uv install --dev
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_orchestrator.py
```

### Code Quality

```bash
# Format code
black dgt/

# Lint code
ruff check dgt/

# Type check
mypy dgt/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite and ensure all checks pass
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/duggercore/duggercore-git-tools/issues
- Documentation: https://docs.duggercore.com/dgt
