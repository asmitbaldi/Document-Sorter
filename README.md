# DocumentSorter

DocumentSorter watches a macOS Downloads folder and safely sorts newly completed `.pdf`, `.docx`, `.pptx`, and `.txt` documents into a fixed Semester V layout. It first uses conservative filename matching; ambiguous files are classified by Gemini `gemini-3.5-flash-lite` with JSON structured output.

Only these paths can ever receive a file:

- `ROOT/ML` for `ML`
- `ROOT/Sem_V/AI`, `OS`, `IVP`, `SWE`, `SET`, `MAD`, `LTLS`, or `Other`

`Downloads` is an explicit no-move decision. Personal/unsupported/hidden/temp files and AI responses below the configured confidence threshold remain in Downloads.

## Setup

```zsh
cd /Users/asmitbaldi/vibecoded/DocumentSorter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
```

Review `config.json` before use. It defaults to dry-run mode, so no document moves until you deliberately set `"dry_run": false`. If you clone this project elsewhere, copy and edit `config.json.example`.

Create the expected folders once (the sorter also creates individual safe targets when needed):

```zsh
mkdir -p ~/ML ~/Sem_V/{AI,OS,IVP,SWE,SET,MAD,LTLS,Other}
```

Run the watcher:

```zsh
python -m smartsort.main --config config.json
```

Process the currently present documents once instead:

```zsh
python -m smartsort.main --config config.json --once
```

Undo the last actual move (not available for dry runs):

```zsh
python -m smartsort.main --config config.json --undo-last
```

## Behaviour and safety

- Browser partial downloads (`.download`, `.crdownload`) and common temporary files are ignored.
- The watcher requires two stable size observations and a best-effort macOS advisory-lock check before processing.
- Files never overwrite an existing destination; a timestamped name is selected instead.
- Failed extraction/API requests and low-confidence results leave the source untouched.
- The Gemini API retries transient failures three times with exponential backoff.
- Each real move is written to `ROOT/.smartsort-undo.jsonl` for a one-step undo.
- Logs are written to `logs/smartsort.log` and rotated.

The API key is only read from `GEMINI_API_KEY`; do not put it in `config.json` or commit it.

## Tests

```zsh
python -m unittest discover -s tests -v
```

## Launch at login

1. Copy `config.json.example` to `config.json` and update its two folder paths.
2. Copy `scripts/run_documentsorter.sh.example` to `scripts/run_documentsorter.sh`, then make it executable with `chmod 700 scripts/run_documentsorter.sh`.
3. Store the API key in Keychain without adding it to a file:

   ```zsh
   read -s "GEMINI_KEY?Paste your Gemini API key: "
   echo
   security add-generic-password -U -a "$USER" -s DocumentSorter.GeminiAPIKey -w "$GEMINI_KEY"
   unset GEMINI_KEY
   ```

4. Copy `launchagent/com.asmitbaldi.documentsorter.plist.example` to `~/Library/LaunchAgents/com.asmitbaldi.documentsorter.plist`, then replace every `YOUR_USERNAME`.
5. Load it with:

   ```zsh
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.asmitbaldi.documentsorter.plist
   ```

Use `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.asmitbaldi.documentsorter.plist` to stop it. Local runtime files (`config.json`, the runner script, logs, and the installed plist) are intentionally ignored by Git.

## Extending classifiers

`BaseClassifier` is the provider boundary. Add an `OllamaClassifier` or `OpenAIClassifier` that implements `classify(document) -> Classification`, then inject it in `main.py`; the processing, safety, and mover layers stay unchanged.
