# gogdl — GRINDER fork

A fork of [heroic-gogdl](https://github.com/Heroic-Games-Launcher/heroic-gogdl) maintained for **[GRINDER](https://github.com/FromChaosComesClarity/GRINDER)** — the Cafe Neurotico GOG/Epic launcher.

## Changes from upstream

| File | Change |
|---|---|
| `gogdl/constants.py` | Default config dir renamed `heroic_gogdl` → `gogdl`; `GOGDL_CONFIG_PATH` isolates manifests per launcher |
| `gogdl/dl/managers/linux.py` | Null check before subscripting `game_installer` — fixes crash when no Linux installer matches |
| `gogdl/dl/progressbar.py` | Progress line rewritten to `Progress: X.XX% (...) Speed: X.XX MiB/s ETA: HH:MM:SS` |
| `gogdl/dl/workers/task_executor.py` | `gogdl_xdelta3` import made optional so the binary builds without the C extension |
| `gogdl/auth.py` | User-Agent changed to `GRINDER by Cafe Neurotico` |
| `grinder_entry.py` | PyInstaller entry point with `freeze_support()` + `set_start_method('spawn')` |

## Building

```bash
pip install pyinstaller requests
pyinstaller --onefile --name gogdl grinder_entry.py
# Output: dist/gogdl
```

## License

GPL v3 — same as upstream. See [LICENSE](LICENSE).

Original work copyright © imLinguin and the Heroic Games Launcher contributors.
