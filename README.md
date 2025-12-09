# MoTeC Cleanup

A Python tool to analyse Assetto Corsa Competizione MoTeC telemetry files, identify your fastest dry and wet laps per track/car combination, and organise them into a personal bests folder with standardised naming.

## Features

- **Automatic PB Detection**: Scans your MoTeC telemetry folder and identifies the top 3 fastest laps for both dry and wet conditions
- **Weather Classification**: Uses configurable benchmark times to classify laps as dry or wet (ACC telemetry doesn't include weather data)
- **Non-Destructive**: Original files are never moved, renamed, or modified - only copies are created
- **PB History**: Timestamped PB folders preserve your progression over time
- **Progress Tracking**: Compare current PBs against previous scans to see your improvement
- **Interactive UI**: Keyboard-navigable menus for easy operation
- **Self-Configuring**: Automatically prompts for benchmark times when encountering new track/car/condition combinations
- **OneDrive Support**: Detects cloud-only files and warns you to sync before processing

## Supported Car Categories

- GT3
- GT4
- GT2
- Cup/GTC (Challenge series)
- TC (Touring Cars)

## Requirements

- **Windows** (PowerShell) - required for OneDrive integration and Windows file paths
- Python 3.x
- Dependencies: `pandas`, `numpy`, `windows-curses`

## Installation

```powershell
# Clone the repository
git clone https://github.com/yourusername/MoTeC_Cleanup.git
cd MoTeC_Cleanup

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Usage

```powershell
.\venv\Scripts\Activate.ps1
python src\main.py
```

### Main Menu

```
════════════════════════════════════════════════════════════
  MoTeC Cleanup Tool
════════════════════════════════════════════════════════════

  > Scan & Organise Telemetry
    Undo Last Scan
    Edit Benchmark Times
    Edit Car Categories
    Settings
    Exit

  [↑/↓] Navigate  [Enter] Select  [Esc] Exit
```

### Workflow

1. **Scan & Organise Telemetry** - Point the tool at your ACC MoTeC folder
2. The tool parses all `.ld` and `.ldx` files to extract lap times
3. Laps are classified as dry or wet based on benchmark times (±tolerance)
4. Top 3 laps for each condition per track/car combo are copied to a timestamped PB folder
5. Browse results interactively to see your improvements

### Output Structure

```
MoTeC/
├── PBs_2024-01-15_143052/
│   ├── Barcelona_amr_v8_vantage_gt3_dry_1st_1m43.521s_2024-01-15.ld
│   ├── Barcelona_amr_v8_vantage_gt3_dry_1st_1m43.521s_2024-01-15.ldx
│   ├── Barcelona_amr_v8_vantage_gt3_wet_1st_2m05.234s_2024-01-16.ld
│   ├── Barcelona_amr_v8_vantage_gt3_wet_1st_2m05.234s_2024-01-16.ldx
│   ├── operation_log.txt
│   └── ...
└── [original telemetry files unchanged]
```

## Configuration

Configuration files are stored in the `config/` folder and are self-populating:

- **settings.json** - Application settings (paths, defaults)
- **car_categories.json** - Maps car names to categories (GT3, GT4, etc.)
- **lap_times_{category}_{condition}.json** - Benchmark times per track

### Benchmark Times

Benchmark times define what constitutes a "valid" lap. The tool uses these to:

- Filter out partial laps, pit laps, and outliers
- Classify laps as dry or wet based on which benchmark range they fall into

Edit benchmarks via the interactive menu or directly in the JSON files.

### Tolerance

Each category has a configurable tolerance (default ±5%) that defines the acceptable range around benchmark times. The config editor includes:

- Auto-calculated tolerance recommendations
- Overlap warnings (when wet threshold might overlap with dry)
- Option to apply tolerance changes globally or per-category

## How It Works

### Data Sources

| Data | Source |
|------|--------|
| Track name | `.ld` file header |
| Car name | Filename |
| Lap times | `.ldx` companion file (beacon timestamps) |
| Session date | Filename or `.ld` header |
| Weather | Inferred from lap time vs benchmarks |

### Lap Classification

1. Extract beacon markers from `.ldx` file
2. Calculate individual lap times from cumulative timestamps
3. Check each lap against dry benchmark ± tolerance
4. Check each lap against wet benchmark ± tolerance
5. Classify as dry, wet, or invalid
6. Track top 3 for each condition

## Credits

- MoTeC `.ld` file parser based on [ldparser](https://github.com/gotzl/ldparser) by gotzl

## License

MIT License - See LICENSE file for details.
