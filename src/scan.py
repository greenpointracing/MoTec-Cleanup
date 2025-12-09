"""
MoTeC Cleanup Tool - Telemetry Scanner

Scans MoTeC telemetry files and organises them:
- Identifies top 3 dry AND top 3 wet laps per track/car combo
- Copies PBs to PB's folder with new naming convention
- Moves non-PBs to ToDelete folder
- Generates CSV report
"""

import csv
import json
import os
import platform
import re
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Import ldparser from same directory
from ldparser import ldData


# =============================================================================
# Colour Constants (ANSI escape codes)
# =============================================================================

# Enable ANSI escape codes on Windows
if platform.system() == "Windows":
    os.system('')  # Enables ANSI escape sequences in Windows terminal

# Colours
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground colours
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
YELLOW = "\033[33m"
BRIGHT_YELLOW = "\033[93m"
CYAN = "\033[36m"
BRIGHT_CYAN = "\033[96m"
WHITE = "\033[37m"
BRIGHT_WHITE = "\033[97m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"

# Theme colours
TITLE_COLOR = BRIGHT_GREEN
ACCENT_COLOR = BRIGHT_CYAN
SELECTED_COLOR = BRIGHT_YELLOW
HINT_COLOR = DIM + WHITE
BRAND_COLOR = DIM + GREEN
WARNING_COLOR = BRIGHT_YELLOW
SUCCESS_COLOR = BRIGHT_GREEN
ERROR_COLOR = BRIGHT_RED

# Branding
BRAND_TEXT = "GreenPoint Racing"


# =============================================================================
# Configuration
# =============================================================================

# Path to config directory
CONFIG_DIR = Path(__file__).parent.parent / "config"

# Valid car categories
VALID_CATEGORIES = ["gt3", "gt4", "gt2", "cup", "tc"]


def get_settings():
    """Load application settings."""
    settings_file = CONFIG_DIR / "settings.json"
    if settings_file.exists():
        with open(settings_file, 'r') as f:
            return json.load(f)
    return {}


def get_default_motec_path():
    """Get default MoTeC path from settings."""
    settings = get_settings()
    path_str = settings.get('default_motec_path',
                            r"C:\Users\alasd\OneDrive\Documents\Assetto Corsa Competizione\MoTeC")
    return Path(path_str)


def get_default_report_path():
    """Get default report output path from settings."""
    settings = get_settings()
    path_str = settings.get('report_output_path', r"C:\Temp")
    return Path(path_str)


def get_pb_count():
    """Get number of PBs to keep per condition from settings."""
    settings = get_settings()
    return settings.get('pb_count', 3)


def get_default_tolerance():
    """Get default tolerance from settings."""
    settings = get_settings()
    return settings.get('default_tolerance', 0.05)


# =============================================================================
# Config Loading
# =============================================================================

def load_json_config(filepath):
    """Load a JSON config file, returning empty dict if not found."""
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def save_json_config(filepath, data):
    """Save data to a JSON config file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)


def get_car_categories():
    """Load car categories mapping."""
    return load_json_config(CONFIG_DIR / "car_categories.json")


def save_car_categories(categories):
    """Save car categories mapping."""
    save_json_config(CONFIG_DIR / "car_categories.json", categories)


def get_lap_times_config(category, condition):
    """Load lap times config for a category and condition (dry/wet)."""
    return load_json_config(CONFIG_DIR / f"lap_times_{category}_{condition}.json")


def save_lap_times_config(category, condition, config):
    """Save lap times config for a category and condition."""
    save_json_config(CONFIG_DIR / f"lap_times_{category}_{condition}.json", config)


# =============================================================================
# Car Category Inference
# =============================================================================

def infer_category_from_name(car_name):
    """Try to infer car category from its name."""
    car_lower = car_name.lower()

    if "_gt3" in car_lower or car_lower.endswith("gt3"):
        return "gt3"
    elif "_gt4" in car_lower or car_lower.endswith("gt4"):
        return "gt4"
    elif "_gt2" in car_lower or car_lower.endswith("gt2"):
        return "gt2"
    elif "cup" in car_lower or "challenge" in car_lower:
        return "cup"
    elif "_tc" in car_lower or "touring" in car_lower:
        return "tc"

    return None


def prompt_for_category(car_name):
    """Prompt user to select category for unknown car."""
    inferred = infer_category_from_name(car_name)

    print(f"\n  Unknown car: '{car_name}'")
    if inferred:
        print(f"  (Suggested category based on name: {inferred.upper()})")

    print(f"  Available categories: {', '.join(c.upper() for c in VALID_CATEGORIES)}")

    while True:
        prompt = f"  Enter category [{inferred.upper() if inferred else ''}]: "
        choice = input(prompt).strip().lower()

        if not choice and inferred:
            return inferred

        if choice in VALID_CATEGORIES:
            return choice

        print(f"  Invalid category. Choose from: {', '.join(c.upper() for c in VALID_CATEGORIES)}")


def get_car_category(car_name, auto_save=True):
    """Get category for a car, prompting if unknown."""
    categories = get_car_categories()

    # Remove comment keys
    categories_clean = {k: v for k, v in categories.items() if not k.startswith('_')}

    if car_name in categories_clean:
        return categories_clean[car_name]

    # Unknown car - prompt user
    category = prompt_for_category(car_name)

    if auto_save:
        categories[car_name] = category
        save_car_categories(categories)

    return category


# =============================================================================
# Lap Time Benchmarks
# =============================================================================

def parse_lap_time_input(time_str):
    """Parse user input for lap time. Accepts M:SS, M:SS.mmm, or seconds."""
    time_str = time_str.strip()

    # Try MM:SS or MM:SS.mmm format
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            try:
                minutes = int(parts[0])
                seconds = float(parts[1])
                return minutes * 60 + seconds
            except ValueError:
                pass

    # Try plain seconds
    try:
        return float(time_str)
    except ValueError:
        pass

    return None


def prompt_for_benchmark_times(track, category):
    """Prompt user for benchmark lap times (both dry and wet)."""
    print(f"\n  No benchmark times for '{track}' in {category.upper()} category.")
    print("  Enter typical fast lap times for this track/category combo.")
    print("  Format: M:SS (e.g., 1:44) or seconds (e.g., 104)")
    print()

    dry_time = None
    while dry_time is None:
        time_str = input("  DRY benchmark time: ").strip()
        dry_time = parse_lap_time_input(time_str)
        if dry_time is None or not (30 < dry_time < 600):
            print("  Invalid time. Please enter a valid lap time (e.g., 1:44 or 104)")
            dry_time = None

    wet_time = None
    while wet_time is None:
        time_str = input("  WET benchmark time: ").strip()
        wet_time = parse_lap_time_input(time_str)
        if wet_time is None or not (30 < wet_time < 600):
            print("  Invalid time. Please enter a valid lap time (e.g., 2:05 or 125)")
            wet_time = None

    return dry_time, wet_time


def get_benchmark_times(track, category, auto_save=True):
    """Get benchmark lap times for track/category (both dry and wet), prompting if unknown."""
    dry_config = get_lap_times_config(category, "dry")
    wet_config = get_lap_times_config(category, "wet")

    # Normalize track name
    track_lower = track.lower().replace(" ", "_")

    # Check for existing benchmarks
    dry_time = None
    wet_time = None

    for key in dry_config:
        if key.startswith('_'):
            continue
        if key.lower() == track_lower:
            dry_time = dry_config[key]
            break

    for key in wet_config:
        if key.startswith('_'):
            continue
        if key.lower() == track_lower:
            wet_time = wet_config[key]
            break

    # If either is missing, prompt for both
    if dry_time is None or wet_time is None:
        dry_time, wet_time = prompt_for_benchmark_times(track, category)

        if auto_save:
            dry_config[track_lower] = int(dry_time) if float(dry_time).is_integer() else dry_time
            wet_config[track_lower] = int(wet_time) if float(wet_time).is_integer() else wet_time
            save_lap_times_config(category, "dry", dry_config)
            save_lap_times_config(category, "wet", wet_config)

    return dry_time, wet_time


def get_tolerance(category, condition):
    """Get lap time tolerance for a category/condition."""
    config = get_lap_times_config(category, condition)
    return config.get('_tolerance', get_default_tolerance())


# =============================================================================
# Lap Time Extraction
# =============================================================================

def get_lap_times_from_ldx(ldx_path):
    """Extract lap times from the .ldx companion XML file.

    ACC stores lap timing data in the .ldx file, not in the .ld telemetry channels.
    The .ldx file is XML with lap timestamps in microseconds.

    Returns a list of individual lap times in seconds.
    """
    if not ldx_path.exists():
        return []

    try:
        tree = ET.parse(ldx_path)
        root = tree.getroot()

        lap_timestamps = []

        # Try to find the lap markers in the XML structure
        for marker_groups in root.findall('.//Markers'):
            for marker in marker_groups.findall('Marker'):
                time_attr = marker.get('Time')
                if time_attr is not None:
                    lap_timestamps.append(float(time_attr) * 1e-6)

        # If that didn't work, try the indexed approach
        if not lap_timestamps:
            try:
                for lap in root[0][0][0][0]:
                    time_attr = lap.get('Time')
                    if time_attr is not None:
                        lap_timestamps.append(float(time_attr) * 1e-6)
            except (IndexError, TypeError):
                pass

        if not lap_timestamps:
            return []

        # Convert cumulative timestamps to individual lap times
        lap_times = []
        if len(lap_timestamps) > 0:
            if lap_timestamps[0] != 0:
                lap_times.append(lap_timestamps[0])

            for i in range(1, len(lap_timestamps)):
                lap_time = lap_timestamps[i] - lap_timestamps[i - 1]
                lap_times.append(lap_time)

        return lap_times

    except ET.ParseError:
        return []
    except Exception:
        return []


# =============================================================================
# Lap Classification
# =============================================================================

def check_threshold_overlap(dry_benchmark, wet_benchmark, tolerance):
    """Check if wet threshold overlaps with dry threshold.

    Returns: (overlaps, dry_max, wet_min)
    """
    dry_max = dry_benchmark * (1 + tolerance)
    wet_min = wet_benchmark * (1 - tolerance)
    overlaps = wet_min <= dry_max
    return overlaps, dry_max, wet_min


def classify_lap(lap_time, dry_benchmark, wet_benchmark, tolerance):
    """Classify a lap as dry, wet, gap, or invalid based on benchmarks.

    Returns: 'dry', 'wet', 'gap', or None (invalid - too short/long)
    - 'gap' means the lap falls between dry max and wet min
    """
    dry_min = dry_benchmark * (1 - tolerance)
    dry_max = dry_benchmark * (1 + tolerance)
    wet_min = wet_benchmark * (1 - tolerance)
    wet_max = wet_benchmark * (1 + tolerance)

    # Check dry range first (faster times)
    if dry_min <= lap_time <= dry_max:
        return 'dry'

    # Check wet range
    if wet_min <= lap_time <= wet_max:
        return 'wet'

    # Check if in the gap between dry and wet (if no overlap)
    if dry_max < wet_min and dry_max < lap_time < wet_min:
        return 'gap'

    return None


def classify_laps(lap_times, dry_benchmark, wet_benchmark, tolerance):
    """Classify all laps and return best lap for each condition plus gap laps.

    Returns: (best_dry_lap, best_wet_lap, gap_laps)
    - best_dry_lap: fastest dry lap or None
    - best_wet_lap: fastest wet lap or None
    - gap_laps: list of lap times that fell in the gap
    """
    dry_laps = []
    wet_laps = []
    gap_laps = []

    for lap_time in lap_times:
        condition = classify_lap(lap_time, dry_benchmark, wet_benchmark, tolerance)
        if condition == 'dry':
            dry_laps.append(lap_time)
        elif condition == 'wet':
            wet_laps.append(lap_time)
        elif condition == 'gap':
            gap_laps.append(lap_time)

    best_dry = min(dry_laps) if dry_laps else None
    best_wet = min(wet_laps) if wet_laps else None

    return best_dry, best_wet, gap_laps


# =============================================================================
# Filename Parsing and Generation
# =============================================================================

def parse_original_filename(filename):
    """Parse the original filename to extract car name and date.

    Format: {Track}-{car_name}-{number}-{YYYY.MM.DD}-{HH.MM.SS}.ld
    Returns: (car_name, date_str) or (None, None) if parsing fails
    """
    name = filename.rsplit('.', 1)[0]

    # Look for the date pattern
    date_pattern = r'(\d{4}\.\d{2}\.\d{2})'
    date_match = re.search(date_pattern, name)
    date_str = date_match.group(1) if date_match else None

    # Extract car name
    parts = name.split('-')
    if len(parts) >= 4:
        car_name = parts[1] if len(parts) > 1 else None
    else:
        car_name = None

    return car_name, date_str


def format_lap_time_filename(seconds):
    """Format lap time for filename: {minutes}m{seconds.milliseconds}s"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m{secs:.3f}s"


def format_lap_time_display(seconds):
    """Format lap time for display: M:SS.mmm"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}:{secs:06.3f}"


def generate_pb_filename(track, car, condition, rank, lap_time, date_str):
    """Generate the new filename format for PB files.

    Format: {Track}_{car_name}_{condition}_{rank}_{lap_time}_{date}.ld
    """
    rank_suffix = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
    lap_time_str = format_lap_time_filename(lap_time)
    date_formatted = date_str.replace(".", "-")

    return f"{track}_{car}_{condition}_{rank_suffix}_{lap_time_str}_{date_formatted}.ld"


def parse_pb_filename(filename):
    """Parse a PB filename to extract metadata.

    Format: {Track}_{car_name}_{condition}_{rank}_{lap_time}_{date}.ld
    Returns: dict with track, car, condition, rank, lap_time (seconds), date or None if invalid
    """
    name = filename.rsplit('.', 1)[0]  # Remove extension
    parts = name.split('_')

    if len(parts) < 6:
        return None

    try:
        # Track is first part
        track = parts[0]

        # Find condition (dry/wet) - it's after car name
        condition_idx = None
        for i, part in enumerate(parts):
            if part.lower() in ['dry', 'wet']:
                condition_idx = i
                break

        if condition_idx is None:
            return None

        # Car name is between track and condition
        car = '_'.join(parts[1:condition_idx])
        condition = parts[condition_idx].lower()

        # Rank is after condition
        rank_str = parts[condition_idx + 1]
        rank = int(rank_str[0])  # "1st" -> 1, "2nd" -> 2, etc.

        # Lap time is after rank (format: 1m43.521s)
        lap_time_str = parts[condition_idx + 2]
        lap_match = re.match(r'(\d+)m([\d.]+)s', lap_time_str)
        if lap_match:
            minutes = int(lap_match.group(1))
            seconds = float(lap_match.group(2))
            lap_time = minutes * 60 + seconds
        else:
            return None

        # Date is last part
        date_str = parts[-1]

        return {
            'track': track,
            'car': car,
            'condition': condition,
            'rank': rank,
            'lap_time': lap_time,
            'date': date_str
        }
    except (ValueError, IndexError):
        return None


# =============================================================================
# Previous PB Detection
# =============================================================================

def find_previous_pb_folders(source_dir):
    """Find all timestamped PB folders in the source directory.

    Returns: list of (folder_path, timestamp) sorted by timestamp (newest first)
    """
    pb_folders = []
    pb_pattern = re.compile(r'^PBs_(\d{4}-\d{2}-\d{2}_\d{6})$')

    for item in source_dir.iterdir():
        if item.is_dir():
            match = pb_pattern.match(item.name)
            if match:
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
                    pb_folders.append((item, timestamp))
                except ValueError:
                    pass

    # Sort by timestamp, newest first
    pb_folders.sort(key=lambda x: x[1], reverse=True)
    return pb_folders


def load_previous_pbs(pb_folder):
    """Load PB data from a previous PB folder.

    Returns: dict of {(track, car, condition): [(rank, lap_time, filename), ...]}
    """
    pbs = defaultdict(list)

    for ld_file in pb_folder.glob("*.ld"):
        parsed = parse_pb_filename(ld_file.name)
        if parsed:
            key = (parsed['track'], parsed['car'], parsed['condition'])
            pbs[key].append((parsed['rank'], parsed['lap_time'], ld_file.name))

    # Sort each list by rank
    for key in pbs:
        pbs[key].sort(key=lambda x: x[0])

    return pbs


# =============================================================================
# Undo Feature
# =============================================================================

def get_undo_candidates(source_dir=None):
    """Find PB folders that can be undone (deleted).

    Args:
        source_dir: Directory to search for PB folders. If None, uses default MoTeC path.

    Returns: list of (folder_path, timestamp, file_count) sorted by timestamp (newest first)
    """
    if source_dir is None:
        source_dir = get_default_motec_path()

    if not source_dir.exists():
        return []

    candidates = []
    pb_pattern = re.compile(r'^PBs_(\d{4}-\d{2}-\d{2}_\d{6})$')

    for item in source_dir.iterdir():
        if item.is_dir():
            match = pb_pattern.match(item.name)
            if match:
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H%M%S")
                    # Count files in folder
                    file_count = len(list(item.glob("*.ld")))
                    candidates.append((item, timestamp, file_count))
                except ValueError:
                    pass

    # Sort by timestamp, newest first
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def undo_last_scan(source_dir=None):
    """Delete the most recent PB folder (undo last scan).

    Args:
        source_dir: Directory to search for PB folders. If None, uses default MoTeC path.

    Returns: (folder, message) tuple - folder if successful, None otherwise.
    """
    candidates = get_undo_candidates(source_dir)

    if not candidates:
        return None, "No PB folders found to undo."

    # Get the most recent folder
    folder, timestamp, file_count = candidates[0]

    # Delete the folder and its contents
    try:
        for item in folder.iterdir():
            item.unlink()
        folder.rmdir()
        return folder, f"Deleted {folder.name} ({file_count} PB files)"
    except Exception as e:
        return None, f"Error deleting folder: {e}"


# =============================================================================
# Cleanup Old Files
# =============================================================================

def get_cleanup_candidates(source_dir=None):
    """Find .ld and .ldx files that can be cleaned up (deleted).

    Excludes files in PB folders (PBs_* directories).

    Args:
        source_dir: Directory to search. If None, uses default MoTeC path.

    Returns: dict with 'files' (list of paths), 'count', 'total_size_mb'
    """
    if source_dir is None:
        source_dir = get_default_motec_path()

    if not source_dir.exists():
        return {'files': [], 'count': 0, 'total_size_mb': 0}

    files_to_delete = []
    total_size = 0

    # Find all .ld and .ldx files in the root directory (not in PB folders)
    for ext in ['*.ld', '*.ldx']:
        for file_path in source_dir.glob(ext):
            # Only include files directly in source_dir, not in subdirectories
            if file_path.parent == source_dir:
                files_to_delete.append(file_path)
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass

    return {
        'files': files_to_delete,
        'count': len(files_to_delete),
        'total_size_mb': round(total_size / (1024 * 1024), 2)
    }


def cleanup_old_files(source_dir=None):
    """Delete old .ld and .ldx files from the source directory.

    Only deletes files in the root directory, NOT in PB folders.

    Args:
        source_dir: Directory to clean. If None, uses default MoTeC path.

    Returns: (success_count, error_count, errors_list)
    """
    candidates = get_cleanup_candidates(source_dir)

    if not candidates['files']:
        return 0, 0, []

    success_count = 0
    error_count = 0
    errors = []

    for file_path in candidates['files']:
        try:
            file_path.unlink()
            success_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"{file_path.name}: {e}")

    return success_count, error_count, errors


# =============================================================================
# OneDrive Check
# =============================================================================

def check_onedrive_files(directory):
    """Check for cloud-only OneDrive files and warn user.

    Returns: list of cloud-only file paths
    """
    cloud_only = []

    try:
        import ctypes
        from ctypes import wintypes

        # File attribute for pinned/unpinned OneDrive files
        FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000

        for ld_file in directory.glob("*.ld"):
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(ld_file))
            if attrs != -1 and (attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS):
                cloud_only.append(ld_file)
    except Exception:
        # If we can't check, assume all files are available
        pass

    return cloud_only


# =============================================================================
# Path Input
# =============================================================================

def prompt_for_path(prompt_text, default_path=None):
    """Prompt user for a directory path with optional default."""
    print(f"  {ACCENT_COLOR}{prompt_text}{RESET}")
    print()
    if default_path:
        print(f"  Default: {WHITE}{default_path}{RESET}")
        print(f"  {HINT_COLOR}(Press Enter to use default, or type a new path){RESET}")
    print()

    while True:
        user_input = input("  Path: ").strip()

        # Handle quoted paths
        user_input = user_input.strip('"').strip("'")

        # Use default if empty and default exists
        if not user_input and default_path:
            return Path(default_path)

        if not user_input:
            print(f"  {WARNING_COLOR}Please enter a valid path.{RESET}")
            continue

        path = Path(user_input)

        if not path.exists():
            print(f"  {ERROR_COLOR}ERROR: Path does not exist: {path}{RESET}")
            print(f"  {WARNING_COLOR}Please enter a valid path.{RESET}")
            continue

        if not path.is_dir():
            print(f"  {ERROR_COLOR}ERROR: Path is not a directory: {path}{RESET}")
            print(f"  {WARNING_COLOR}Please enter a valid path.{RESET}")
            continue

        return path


# =============================================================================
# Main Scanner
# =============================================================================

def scan_telemetry(source_dir=None, report_dir=None, dry_run=False):
    """Scan telemetry directory and organise files.

    Args:
        source_dir: Path to MoTeC telemetry directory (prompts if None)
        report_dir: Path for CSV report output (default: C:\Temp)
        dry_run: If True, only report what would be done without copying files

    Returns:
        dict with scan results
    """
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print(f"  {TITLE_COLOR}{BOLD}MoTeC Telemetry Scanner{RESET}")
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print()

    # Prompt for source directory if not provided
    if source_dir is None:
        default_path = get_default_motec_path()
        source_dir = prompt_for_path(
            "Step 1: Select Telemetry Directory",
            default_path=default_path
        )
    else:
        source_dir = Path(source_dir)

    report_dir = Path(report_dir) if report_dir else get_default_report_path()

    print()
    print(f"  {CYAN}Source:{RESET} {source_dir}")
    print(f"  {CYAN}Report:{RESET} {report_dir}")
    if dry_run:
        print(f"  {WARNING_COLOR}Mode:   DRY RUN (no files will be copied){RESET}")
    print()

    # Check for OneDrive cloud-only files
    cloud_files = check_onedrive_files(source_dir)
    if cloud_files:
        print(f"  {WARNING_COLOR}WARNING:{RESET} {len(cloud_files)} files are cloud-only (not downloaded).")
        print(f"  {DIM}Please sync these files in OneDrive before scanning.")
        print(f"  Cloud-only files will be skipped.{RESET}")
        print()

    # Find all .ld files
    ld_files = list(source_dir.glob("*.ld"))
    print(f"  {CYAN}Found{RESET} {BRIGHT_WHITE}{len(ld_files)}{RESET} telemetry files")
    print()

    if not ld_files:
        return None

    # Data structure: {(track, car): {'dry': [(lap_time, file_path, date)], 'wet': [...], 'gap': [...]}}
    track_car_data = defaultdict(lambda: {'dry': [], 'wet': [], 'gap': []})

    # Track overlap warnings per track/category
    overlap_warnings = set()

    # Process each file
    skipped = 0
    processed = 0

    for ld_file in ld_files:
        # Skip cloud-only files
        if ld_file in cloud_files:
            skipped += 1
            continue

        ldx_file = ld_file.with_suffix('.ldx')
        if not ldx_file.exists():
            print(f"  Skipping {ld_file.name} (no .ldx file)")
            skipped += 1
            continue

        try:
            # Parse metadata
            ld_data = ldData.fromfile(str(ld_file))
            track = ld_data.head.venue

            # Get car and date from filename
            car_from_filename, date_from_filename = parse_original_filename(ld_file.name)
            car = car_from_filename or ld_data.head.vehicleid or "unknown"

            if not date_from_filename:
                date_from_filename = ld_data.head.datetime.strftime("%Y.%m.%d")

            # Get car category
            category = get_car_category(car)

            # Get benchmark times
            dry_benchmark, wet_benchmark = get_benchmark_times(track, category)
            tolerance = get_tolerance(category, "dry")  # Same tolerance for both

            # Check for threshold overlap (warn once per track/category)
            overlaps, dry_max, wet_min = check_threshold_overlap(dry_benchmark, wet_benchmark, tolerance)
            if overlaps and (track, category) not in overlap_warnings:
                overlap_warnings.add((track, category))
                print(f"  WARNING: {track}/{category.upper()} - threshold overlap detected!")
                print(f"           Dry max: {format_lap_time_display(dry_max)} >= Wet min: {format_lap_time_display(wet_min)}")

            # Get lap times from .ldx
            lap_times = get_lap_times_from_ldx(ldx_file)

            if not lap_times:
                skipped += 1
                continue

            # Classify and get best lap for each condition
            best_dry, best_wet, gap_laps = classify_laps(lap_times, dry_benchmark, wet_benchmark, tolerance)

            key = (track, car)

            if best_dry:
                track_car_data[key]['dry'].append((best_dry, ld_file, date_from_filename))

            if best_wet:
                track_car_data[key]['wet'].append((best_wet, ld_file, date_from_filename))

            # Track gap laps for reporting
            for gap_lap in gap_laps:
                track_car_data[key]['gap'].append((gap_lap, ld_file, date_from_filename))

            processed += 1

        except Exception as e:
            print(f"  Error processing {ld_file.name}: {e}")
            skipped += 1

    print()
    print(f"  Processed: {processed} files")
    print(f"  Skipped:   {skipped} files")
    print()

    # Find previous PB folder for comparison
    previous_pb_folders = find_previous_pb_folders(source_dir)
    previous_pbs = {}
    if previous_pb_folders:
        latest_pb_folder, latest_timestamp = previous_pb_folders[0]
        print(f"  Found previous PBs: {latest_pb_folder.name}")
        previous_pbs = load_previous_pbs(latest_pb_folder)
    else:
        print("  No previous PB folders found.")
    print()

    # Create timestamped output directory
    scan_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pbs_dir = source_dir / f"PBs_{scan_timestamp}"

    if not dry_run:
        pbs_dir.mkdir(exist_ok=True)

    # Process results and identify PBs
    report_rows = []
    files_to_pb = []
    gap_lap_count = 0

    # Track comparison data for results browser
    comparison_data = {}  # {(track, car): {'dry': {...}, 'wet': {...}}}

    for (track, car), conditions in track_car_data.items():
        comparison_data[(track, car)] = {'dry': {'current': [], 'previous': []},
                                          'wet': {'current': [], 'previous': []}}

        for condition in ['dry', 'wet']:
            laps = conditions[condition]
            if not laps:
                continue

            # Sort by lap time (fastest first)
            laps.sort(key=lambda x: x[0])

            # Top N are PBs (N from settings)
            pb_count = get_pb_count()
            for rank, (lap_time, file_path, date_str) in enumerate(laps[:pb_count], 1):
                new_filename = generate_pb_filename(track, car, condition, rank, lap_time, date_str)
                files_to_pb.append((file_path, new_filename, track, car, condition, rank, lap_time))

                # Get previous time for this rank if available
                prev_key = (track, car, condition)
                prev_time = None
                if prev_key in previous_pbs:
                    for prev_rank, prev_lap, _ in previous_pbs[prev_key]:
                        if prev_rank == rank:
                            prev_time = prev_lap
                            break

                # Calculate delta
                delta = None
                if prev_time is not None:
                    delta = lap_time - prev_time

                comparison_data[(track, car)][condition]['current'].append({
                    'rank': rank,
                    'lap_time': lap_time,
                    'previous_time': prev_time,
                    'delta': delta,
                    'is_new_pb': prev_time is None or lap_time < prev_time
                })

                report_rows.append({
                    'track': track,
                    'car': car,
                    'condition': condition,
                    'rank': rank,
                    'lap_time': format_lap_time_display(lap_time),
                    'previous_time': format_lap_time_display(prev_time) if prev_time else '-',
                    'delta': f"{delta:+.3f}s" if delta is not None else '-',
                    'original_file': file_path.name,
                    'new_file': new_filename,
                    'action': 'PB'
                })

            # Load previous PBs for this track/car/condition
            prev_key = (track, car, condition)
            if prev_key in previous_pbs:
                for prev_rank, prev_lap, prev_file in previous_pbs[prev_key]:
                    comparison_data[(track, car)][condition]['previous'].append({
                        'rank': prev_rank,
                        'lap_time': prev_lap
                    })

        # Report gap laps (laps that fell between thresholds)
        gap_laps = conditions['gap']
        if gap_laps:
            gap_lap_count += len(gap_laps)
            for lap_time, file_path, date_str in gap_laps:
                report_rows.append({
                    'track': track,
                    'car': car,
                    'condition': 'GAP',
                    'rank': '-',
                    'lap_time': format_lap_time_display(lap_time),
                    'previous_time': '-',
                    'delta': '-',
                    'original_file': file_path.name,
                    'new_file': '-',
                    'action': 'GAP_WARNING'
                })

    # Display gap lap warning if any
    if gap_lap_count > 0:
        print(f"  WARNING: {gap_lap_count} lap(s) fell between dry/wet thresholds!")
        print("  These laps were not classified. Consider adjusting benchmark times.")
        print("  See CSV report for details (action='GAP_WARNING').")
        print()

    # Copy PB files (COPY ONLY - never move or modify originals)
    # Deduplicate: if one file contains multiple PBs, copy once with 1st place name
    operation_log = []
    copied_files = {}  # Maps source path to (dest_filename, list of ranks/times)

    if not dry_run:
        print("  Copying PB files...")
        print()

        for file_path, new_filename, track, car, condition, rank, lap_time in files_to_pb:
            source_key = str(file_path)

            if source_key in copied_files:
                # This file was already copied - just note the additional PB
                copied_files[source_key]['additional_pbs'].append({
                    'condition': condition,
                    'rank': rank,
                    'lap_time': lap_time,
                    'filename': new_filename
                })
            else:
                # First time seeing this file - copy it with 1st place name
                dest_ld = pbs_dir / new_filename
                dest_ldx = pbs_dir / new_filename.replace('.ld', '.ldx')

                shutil.copy2(file_path, dest_ld)
                ldx_file = file_path.with_suffix('.ldx')
                if ldx_file.exists():
                    shutil.copy2(ldx_file, dest_ldx)

                copied_files[source_key] = {
                    'dest_ld': str(dest_ld),
                    'dest_ldx': str(dest_ldx) if ldx_file.exists() else None,
                    'track': track,
                    'car': car,
                    'primary_condition': condition,
                    'primary_rank': rank,
                    'primary_lap_time': lap_time,
                    'primary_filename': new_filename,
                    'additional_pbs': []
                }

                print(f"    PB: {new_filename}")

        # Build operation log with deduplication info
        for source_path, info in copied_files.items():
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'source': source_path,
                'dest_ld': info['dest_ld'],
                'dest_ldx': info['dest_ldx'],
                'track': info['track'],
                'car': info['car'],
                'condition': info['primary_condition'],
                'rank': info['primary_rank'],
                'lap_time': info['primary_lap_time'],
                'additional_pbs': info['additional_pbs']
            }
            operation_log.append(log_entry)

            # Print additional PBs contained in same file
            if info['additional_pbs']:
                for extra in info['additional_pbs']:
                    print(f"      (also contains {extra['condition'].upper()} #{extra['rank']}: {format_lap_time_display(extra['lap_time'])})")

        print()

        # Write operation log to PB folder
        log_file = pbs_dir / "operation_log.txt"
        files_copied_count = len(copied_files)
        total_pbs_count = len(files_to_pb)

        with open(log_file, 'w') as f:
            f.write(f"MoTeC PB Scan - {scan_timestamp}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Source directory: {source_dir}\n")
            f.write(f"Files processed: {processed}\n")
            f.write(f"Total PBs identified: {total_pbs_count}\n")
            f.write(f"Files copied: {files_copied_count}\n")
            if total_pbs_count != files_copied_count:
                f.write(f"  (Some files contain multiple PBs)\n")
            f.write("\nOperations:\n")
            f.write("-" * 60 + "\n")
            for op in operation_log:
                f.write(f"\n[{op['timestamp']}]\n")
                f.write(f"  Source: {op['source']}\n")
                f.write(f"  Dest:   {op['dest_ld']}\n")
                f.write(f"  Track:  {op['track']} | Car: {op['car']}\n")
                f.write(f"  {op['condition'].upper()} #{op['rank']}: {format_lap_time_display(op['lap_time'])}\n")

                # Log additional PBs in the same file
                if op.get('additional_pbs'):
                    f.write("  ** File also contains:\n")
                    for extra in op['additional_pbs']:
                        f.write(f"     {extra['condition'].upper()} #{extra['rank']}: {format_lap_time_display(extra['lap_time'])}\n")

    # Generate CSV report
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"motec_scan_{scan_timestamp.replace('-', '').replace('_', '_')}.csv"

    with open(report_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'track', 'car', 'condition', 'rank', 'lap_time',
            'previous_time', 'delta', 'original_file', 'new_file', 'action'
        ])
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"  {DIM}Report saved: {report_file}{RESET}")
    if not dry_run:
        print(f"  {DIM}Operation log: {pbs_dir / 'operation_log.txt'}{RESET}")
    print()
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print(f"  {SUCCESS_COLOR}{BOLD}Scan Complete!{RESET}")
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print()

    # Calculate file counts
    total_pbs = len(files_to_pb)
    files_copied = len(copied_files) if not dry_run else total_pbs

    print(f"  {CYAN}PBs identified:{RESET} {BRIGHT_WHITE}{total_pbs}{RESET}")
    if not dry_run and files_copied != total_pbs:
        print(f"  {CYAN}Files copied:{RESET}   {files_copied} {DIM}(some files contain multiple PBs){RESET}")
    if not dry_run:
        print(f"  {CYAN}PB folder:{RESET}      {pbs_dir}")
    print()

    if dry_run:
        print(f"  {WARNING_COLOR}This was a DRY RUN - no files were copied.{RESET}")
        print()

    print(f"  {BRAND_COLOR}{BRAND_TEXT}{RESET}")
    print()

    return {
        'processed': processed,
        'skipped': skipped,
        'pbs': total_pbs,
        'files_copied': files_copied,
        'pbs_dir': pbs_dir,
        'report_file': report_file,
        'comparison_data': comparison_data,
        'track_car_data': track_car_data
    }


# =============================================================================
# Results Browser
# =============================================================================

def get_key():
    """Get a single keypress from the user."""
    import msvcrt

    key = msvcrt.getch()

    if key == b'\xe0':  # Special key prefix
        key = msvcrt.getch()
        if key == b'H':  # Up arrow
            return 'UP'
        elif key == b'P':  # Down arrow
            return 'DOWN'
    elif key == b'\r':  # Enter
        return 'ENTER'
    elif key == b'\x1b':  # Escape
        return 'ESC'

    return key.decode('utf-8', errors='ignore') if isinstance(key, bytes) else key


def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('cls')


def prettify_name(name):
    """Convert internal name to display name."""
    return name.replace("_", " ").title()


def results_browser(comparison_data):
    """Interactive browser for scan results.

    Args:
        comparison_data: dict of {(track, car): {'dry': {...}, 'wet': {...}}}
    """
    if not comparison_data:
        print("  No results to display.")
        input("  Press Enter to continue...")
        return

    # Build list of unique cars
    cars = sorted(set(car for (track, car) in comparison_data.keys()))

    if not cars:
        print("  No cars found in results.")
        input("  Press Enter to continue...")
        return

    # Car selection
    selected_car_idx = 0

    while True:
        clear_screen()
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print(f"  {TITLE_COLOR}{BOLD}Scan Results - Select Car{RESET}")
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print()

        for i, car in enumerate(cars):
            if i == selected_car_idx:
                print(f"  {SELECTED_COLOR}>{RESET} {BRIGHT_WHITE}{prettify_name(car)}{RESET}")
            else:
                print(f"    {WHITE}{prettify_name(car)}{RESET}")

        print()
        print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] Select  [Esc] Exit{RESET}")
        print()
        print(f"  {BRAND_COLOR}{BRAND_TEXT}{RESET}")

        key = get_key()

        if key == 'UP':
            selected_car_idx = (selected_car_idx - 1) % len(cars)
        elif key == 'DOWN':
            selected_car_idx = (selected_car_idx + 1) % len(cars)
        elif key == 'ENTER':
            selected_car = cars[selected_car_idx]
            browse_car_tracks(comparison_data, selected_car)
        elif key == 'ESC':
            return


def browse_car_tracks(comparison_data, car):
    """Browse tracks for a specific car."""
    # Get tracks for this car
    tracks = sorted(set(track for (track, c) in comparison_data.keys() if c == car))

    if not tracks:
        return

    selected_track_idx = 0

    while True:
        clear_screen()
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print(f"  {TITLE_COLOR}{BOLD}{prettify_name(car)} - Select Track{RESET}")
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print()

        for i, track in enumerate(tracks):
            # Show summary of PBs for this track
            data = comparison_data.get((track, car), {})
            dry_count = len(data.get('dry', {}).get('current', []))
            wet_count = len(data.get('wet', {}).get('current', []))

            summary = []
            if dry_count:
                summary.append(f"{GREEN}{dry_count} dry{RESET}")
            if wet_count:
                summary.append(f"{CYAN}{wet_count} wet{RESET}")
            summary_str = f" ({', '.join(summary)})" if summary else ""

            if i == selected_track_idx:
                print(f"  {SELECTED_COLOR}>{RESET} {BRIGHT_WHITE}{prettify_name(track)}{RESET}{summary_str}")
            else:
                print(f"    {WHITE}{prettify_name(track)}{RESET}{summary_str}")

        print()
        print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] View Details  [Esc] Back{RESET}")
        print()
        print(f"  {BRAND_COLOR}{BRAND_TEXT}{RESET}")

        key = get_key()

        if key == 'UP':
            selected_track_idx = (selected_track_idx - 1) % len(tracks)
        elif key == 'DOWN':
            selected_track_idx = (selected_track_idx + 1) % len(tracks)
        elif key == 'ENTER':
            selected_track = tracks[selected_track_idx]
            show_track_details(comparison_data, car, selected_track)
        elif key == 'ESC':
            return


def show_track_details(comparison_data, car, track):
    """Show detailed PB comparison for a car/track combo."""
    data = comparison_data.get((track, car), {})

    while True:
        clear_screen()
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print(f"  {TITLE_COLOR}{BOLD}{prettify_name(car)} - {prettify_name(track)}{RESET}")
        print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
        print()

        for condition in ['dry', 'wet']:
            condition_data = data.get(condition, {})
            current = condition_data.get('current', [])
            previous = condition_data.get('previous', [])

            condition_color = GREEN if condition == 'dry' else CYAN
            print(f"  {condition_color}{BOLD}{condition.upper()} Condition:{RESET}")

            if not current:
                print(f"    {DIM}No PBs recorded{RESET}")
            else:
                for pb in current:
                    rank = pb['rank']
                    lap_time = pb['lap_time']
                    prev_time = pb.get('previous_time')
                    delta = pb.get('delta')
                    is_new_pb = pb.get('is_new_pb', False)

                    # Format current time
                    current_str = format_lap_time_display(lap_time)

                    # Format comparison
                    if prev_time is not None:
                        prev_str = format_lap_time_display(prev_time)
                        if delta is not None:
                            delta_str = f"{delta:+.3f}"
                            if delta < 0:
                                status = f"  {SUCCESS_COLOR}NEW PB!{RESET}"
                            elif delta == 0:
                                status = f"  {DIM}(same){RESET}"
                            else:
                                status = f"  {WARNING_COLOR}(slower){RESET}"
                        else:
                            delta_str = "-"
                            status = ""
                        comparison = f"{DIM}(Previous: {prev_str}  Δ {delta_str}){RESET}{status}"
                    else:
                        comparison = f"{SUCCESS_COLOR}NEW!{RESET}"

                    rank_str = {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th")
                    print(f"    {BRIGHT_WHITE}{rank_str}:{RESET} {current_str}  {comparison}")

            print()

        print(f"  {HINT_COLOR}[Esc] Back{RESET}")
        print()
        print(f"  {BRAND_COLOR}{BRAND_TEXT}{RESET}")

        key = get_key()
        if key == 'ESC':
            return


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run scanner directly for testing
    scan_telemetry(dry_run=True)
