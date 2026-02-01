# aco: Agentic Sequencing Quality Control

Automate sequencing quality control with LLM-driven experiment understanding. aco uses Google Gemini to analyze your sequencing data manifests and provide intelligent QC recommendations.

## Features

- **File Scanner**: Automatically discovers FASTQ, BAM, CellRanger outputs, and other sequencing files
- **Manifest Builder**: Combines user descriptions with discovered file metadata
- **LLM Understanding**: Uses Gemini to infer experiment type, assay details, and quality concerns
- **Human-in-the-Loop**: Interactive UI for reviewing and approving LLM-generated insights
- **QC Recommendations**: Get tailored quality control check suggestions

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Google AI API key ([get one here](https://aistudio.google.com/apikey))

### Installation

```bash
# Install from source
git clone https://github.com/seqmachines/aco
cd aco
uv sync
```

### Usage

```bash
# Navigate to your sequencing data directory
cd /path/to/your/sequencing/data

# Run aco (will prompt for API key on first run)
uv run aco init
```

That's it! aco will:
1. Prompt for your Google API key (saved for future use)
2. Scan the current directory for sequencing files
3. Start the local server at http://localhost:7878
4. Open the web UI in your browser

### CLI Commands

```bash
# Initialize aco in current directory and start server
uv run aco init

# Use a different port
uv run aco init --port 9000

# Don't auto-open browser
uv run aco init --no-browser

# Quick scan without starting server
uv run aco scan /path/to/data

# Show version
uv run aco version
```

## Workflow

1. **Install aco** - Clone and `uv sync`
2. **Navigate to data** - `cd /path/to/sequencing/data`
3. **Run aco** - `uv run aco init`
4. **Use the web UI** - Describe your experiment, review files, get LLM analysis

## Architecture

```
aco/
├── aco/                    # Python backend
│   ├── cli.py             # CLI commands (aco init, scan, etc.)
│   ├── static/            # Built frontend (included in package)
│   ├── api/               # FastAPI routes
│   │   ├── main.py        # App entry point
│   │   └── routes/        # API endpoints
│   ├── engine/            # LLM integration
│   │   ├── gemini.py      # Gemini API client
│   │   ├── understanding.py  # Prompt templates
│   │   └── models.py      # Understanding schemas
│   └── manifest/          # Data handling
│       ├── scanner.py     # File discovery
│       ├── builder.py     # Manifest creation
│       └── models.py      # Data schemas
├── frontend/              # React UI source
│   └── src/
│       ├── components/    # UI components
│       ├── hooks/         # API hooks
│       └── types/         # TypeScript types
└── pyproject.toml         # Python dependencies
```

## Configuration

Your API key is saved to `~/.aco/config` after first run.

| Setting | Description |
|---------|-------------|
| Google API Key | Prompted on first run, saved to ~/.aco/config |
| Storage | Project data saved to `.aco/` in working directory |

## Supported File Types

- **FASTQ**: `.fastq`, `.fastq.gz`, `.fq`, `.fq.gz`
- **Alignments**: `.bam`, `.sam`, `.cram`
- **Variants**: `.vcf`, `.vcf.gz`, `.bcf`
- **Annotations**: `.bed`, `.gtf`, `.gff`
- **CellRanger**: Automatic detection of `outs/` directories

## Development

### Rebuild Frontend

```bash
cd frontend
npm install
npm run build
cp -r dist ../aco/static
```

### Run in Development Mode

```bash
# Terminal 1: Backend
uv run uvicorn aco.api.main:app --reload --port 7878

# Terminal 2: Frontend (with hot reload)
cd frontend
npm run dev
```

## License

MIT
