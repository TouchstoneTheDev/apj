# apj

A collection of analysis tools and utilities.

## Intent Expansion Pipeline

A Python-based pipeline for analyzing customer messages and identifying missing intents.

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` with your actual API keys (never commit this file)
4. Install dependencies (optional, for LLM support):
   ```bash
   pip install -r requirements.txt
   ```

### API Key Security

⚠️ **Important Security Notes:**

- **Never commit API keys** to the repository
- Store API keys in environment variables or a `.env` file
- The `.env` file is gitignored and will not be tracked
- Use `.env.example` as a template for required environment variables
- Rotate any keys that were accidentally exposed

### Usage

```bash
# Basic usage (keyword analysis only)
python intent_expansion_pipeline.py inputs_for_assignment.json

# With LLM enhancement (requires API key in .env)
python intent_expansion_pipeline.py inputs_for_assignment.json --use-llm --llm-provider openai
```

### Available LLM Providers

- `openai` - GPT models (requires `OPENAI_API_KEY`)
- `anthropic` - Claude models (requires `ANTHROPIC_API_KEY`)
- `google` - Gemini models (requires `GOOGLE_API_KEY`)

## License

See [LICENSE](LICENSE) file.