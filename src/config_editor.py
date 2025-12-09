"""
MoTeC Cleanup Tool - Configuration Editor

Interactive editor for:
- Benchmark lap times (dry/wet per category)
- Car categories

Uses keyboard navigation with arrow keys.
"""

import json
import os
import platform
from pathlib import Path


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
ERROR_COLOR = BRIGHT_RED

# Branding
BRAND_TEXT = "GreenPoint Racing"


# Path to config directory
CONFIG_DIR = Path(__file__).parent.parent / "config"

# Valid car categories
VALID_CATEGORIES = ["gt3", "gt4", "gt2", "cup", "tc"]

# Category display names
CATEGORY_NAMES = {
    "gt3": "GT3",
    "gt4": "GT4",
    "gt2": "GT2",
    "cup": "Cup/GTC",
    "tc": "Touring Car"
}


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls')


def print_header(title):
    """Print the application header with colours."""
    clear_screen()
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print(f"  {TITLE_COLOR}{BOLD}{title}{RESET}")
    print(f"{ACCENT_COLOR}{'=' * 60}{RESET}")
    print()


def print_footer():
    """Print the subtle branding footer."""
    print()
    print(f"  {BRAND_COLOR}{BRAND_TEXT}{RESET}")


def get_key():
    """Get a single keypress from the user."""
    import msvcrt

    key = msvcrt.getch()

    # Handle special keys (arrows, etc.)
    if key == b'\xe0':  # Special key prefix
        key = msvcrt.getch()
        if key == b'H':  # Up arrow
            return 'UP'
        elif key == b'P':  # Down arrow
            return 'DOWN'
        elif key == b'K':  # Left arrow
            return 'LEFT'
        elif key == b'M':  # Right arrow
            return 'RIGHT'
    elif key == b'\r':  # Enter
        return 'ENTER'
    elif key == b'\x1b':  # Escape
        return 'ESC'
    elif key == b'q' or key == b'Q':
        return 'Q'
    elif key == b't' or key == b'T':
        return 'T'
    elif key == b'a' or key == b'A':
        return 'A'
    elif key == b'd' or key == b'D':
        return 'D'

    return key.decode('utf-8', errors='ignore') if isinstance(key, bytes) else key


def prettify_name(name):
    """Convert internal name to display name (capitalize, replace underscores)."""
    return name.replace("_", " ").title()


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


def format_lap_time(seconds):
    """Format lap time as M:SS.mmm for display."""
    if seconds is None:
        return "--:--"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}:{secs:06.3f}"


def check_threshold_overlap(dry_time, wet_time, tolerance):
    """Check if wet threshold overlaps with dry threshold.

    Returns: (overlaps, gap_start, gap_end)
    - overlaps: True if thresholds overlap
    - gap_start: dry_max (end of dry range)
    - gap_end: wet_min (start of wet range)

    If gap_end < gap_start, they overlap.
    """
    if dry_time is None or wet_time is None:
        return False, None, None

    dry_max = dry_time * (1 + tolerance)
    wet_min = wet_time * (1 - tolerance)

    overlaps = wet_min <= dry_max
    return overlaps, dry_max, wet_min


def calculate_max_safe_tolerance(dry_time, wet_time):
    """Calculate the maximum tolerance that won't cause overlap.

    For no overlap, we need: dry_max < wet_min
    dry * (1 + tol) < wet * (1 - tol)
    dry + dry*tol < wet - wet*tol
    dry*tol + wet*tol < wet - dry
    tol * (dry + wet) < wet - dry
    tol < (wet - dry) / (wet + dry)

    Returns the max safe tolerance as a decimal (e.g., 0.10 for 10%).
    Returns None if dry_time >= wet_time (invalid configuration).
    """
    if dry_time is None or wet_time is None:
        return None
    if dry_time >= wet_time:
        return None

    max_tol = (wet_time - dry_time) / (wet_time + dry_time)
    return max_tol


def recommend_tolerance(dry_time, wet_time, margin=0.02):
    """Recommend a safe tolerance with a safety margin.

    Args:
        dry_time: Dry benchmark time in seconds
        wet_time: Wet benchmark time in seconds
        margin: Safety margin to subtract from max (default 2%)

    Returns:
        Recommended tolerance, or None if calculation not possible.
    """
    max_tol = calculate_max_safe_tolerance(dry_time, wet_time)
    if max_tol is None:
        return None

    # Apply safety margin and round to nearest 1%
    recommended = max_tol - margin
    if recommended < 0.05:  # Minimum 5%
        return 0.05
    if recommended > 0.30:  # Cap at 30%
        return 0.30

    # Round to nearest 1%
    return round(recommended * 100) / 100


def parse_lap_time_input(time_str):
    """Parse user input for lap time. Accepts M:SS, M:SS.mmm, or seconds."""
    time_str = time_str.strip()

    if not time_str:
        return None

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


# =============================================================================
# Benchmark Times Editor
# =============================================================================

def benchmark_editor():
    """Main entry point for benchmark times editor."""
    while True:
        category = select_category()
        if category is None:
            return
        edit_category_benchmarks(category)


def select_category():
    """Display category selection menu."""
    selected = 0

    while True:
        print_header("Edit Benchmark Times - Select Category")

        for i, cat in enumerate(VALID_CATEGORIES):
            if i == selected:
                print(f"  {SELECTED_COLOR}>{RESET} {BRIGHT_WHITE}{CATEGORY_NAMES[cat]}{RESET}")
            else:
                print(f"    {WHITE}{CATEGORY_NAMES[cat]}{RESET}")

        print()
        print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] Select  [Esc] Back{RESET}")
        print_footer()

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(VALID_CATEGORIES)
        elif key == 'DOWN':
            selected = (selected + 1) % len(VALID_CATEGORIES)
        elif key == 'ENTER':
            return VALID_CATEGORIES[selected]
        elif key == 'ESC':
            return None


def edit_category_benchmarks(category):
    """Edit benchmark times for a specific category."""
    selected = 0

    while True:
        # Load both dry and wet configs
        dry_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json")
        wet_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json")

        # Get all tracks (union of dry and wet)
        tracks = set()
        for key in dry_config:
            if not key.startswith('_'):
                tracks.add(key)
        for key in wet_config:
            if not key.startswith('_'):
                tracks.add(key)
        tracks = sorted(tracks)

        # Get tolerance
        tolerance = dry_config.get('_tolerance', 0.20)

        # Build menu items
        items = []
        for track in tracks:
            dry_time = dry_config.get(track)
            wet_time = wet_config.get(track)
            items.append({
                'track': track,
                'dry': dry_time,
                'wet': wet_time
            })
        items.append({'action': 'add_track'})

        # Ensure selected is valid
        if selected >= len(items):
            selected = len(items) - 1
        if selected < 0:
            selected = 0

        # Display
        print_header(f"Edit Benchmark Times - {CATEGORY_NAMES[category]}")
        print(f"  {CYAN}Tolerance:{RESET} +/- {tolerance * 100:.0f}%")
        print()

        # Check for any overlap warnings
        has_warnings = False
        for item in items:
            if 'track' in item:
                overlaps, _, _ = check_threshold_overlap(item['dry'], item['wet'], tolerance)
                if overlaps:
                    has_warnings = True
                    break

        for i, item in enumerate(items):
            if i == selected:
                prefix = f"  {SELECTED_COLOR}>{RESET} "
                text_color = BRIGHT_WHITE
            else:
                prefix = "    "
                text_color = WHITE

            if 'action' in item:
                print(f"{prefix}{CYAN}[+ Add Track]{RESET}")
            else:
                track_display = prettify_name(item['track'])
                dry_display = format_lap_time(item['dry'])
                wet_display = format_lap_time(item['wet'])

                # Check for overlap
                overlaps, dry_max, wet_min = check_threshold_overlap(item['dry'], item['wet'], tolerance)
                warning = f" {WARNING_COLOR}[!OVERLAP]{RESET}" if overlaps else ""

                print(f"{prefix}{text_color}{track_display:<20}{RESET} {GREEN}Dry:{RESET} {dry_display}  {CYAN}Wet:{RESET} {wet_display}{warning}")

        if has_warnings:
            print()
            print(f"  {WARNING_COLOR}WARNING:{RESET} [!OVERLAP] = wet threshold overlaps dry threshold.")
            print(f"  {DIM}Laps may be misclassified. Consider adjusting times or tolerance.{RESET}")

        print()
        print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] Edit  [T] Tolerance  [D] Delete  [Esc] Back{RESET}")
        print_footer()

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(items)
        elif key == 'DOWN':
            selected = (selected + 1) % len(items)
        elif key == 'ENTER':
            item = items[selected]
            if 'action' in item and item['action'] == 'add_track':
                add_track(category)
            elif 'track' in item:
                edit_track_times(category, item['track'])
        elif key == 'T':
            edit_tolerance(category)
        elif key == 'D':
            if selected < len(items) - 1:  # Not the "Add Track" item
                item = items[selected]
                if 'track' in item:
                    delete_track(category, item['track'])
        elif key == 'ESC':
            return


def edit_track_times(category, track):
    """Edit dry and/or wet times for a specific track."""
    # First, show menu to select what to edit
    options = ["Edit Dry Time Only", "Edit Wet Time Only", "Edit Both Times"]
    selected = 0

    dry_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json")
    wet_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json")
    current_dry = dry_config.get(track)
    current_wet = wet_config.get(track)

    while True:
        print_header(f"Edit: {prettify_name(track)} ({CATEGORY_NAMES[category]})")
        print(f"  Current Dry: {format_lap_time(current_dry)}")
        print(f"  Current Wet: {format_lap_time(current_wet)}")
        print()

        for i, option in enumerate(options):
            prefix = "  > " if i == selected else "    "
            print(f"{prefix}{option}")

        print()
        print("  [Up/Down] Navigate  [Enter] Select  [Esc] Back")

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(options)
        elif key == 'DOWN':
            selected = (selected + 1) % len(options)
        elif key == 'ENTER':
            if selected == 0:  # Dry only
                _edit_single_time(category, track, 'dry', dry_config, current_dry)
            elif selected == 1:  # Wet only
                _edit_single_time(category, track, 'wet', wet_config, current_wet)
            elif selected == 2:  # Both
                _edit_both_times(category, track, dry_config, wet_config, current_dry, current_wet)
            return
        elif key == 'ESC':
            return


def _edit_single_time(category, track, condition, config, current_time):
    """Edit a single time (dry or wet) for a track."""
    condition_display = condition.upper()

    print_header(f"Edit {condition_display} Time: {prettify_name(track)}")
    print(f"  Current {condition_display}: {format_lap_time(current_time)}")
    print()
    print("  Enter time as M:SS (e.g., 1:44) or seconds (e.g., 104)")
    print("  Press Enter to keep current value, or type 'x' to clear")
    print()

    time_input = input(f"  New {condition_display} Time [{format_lap_time(current_time)}]: ").strip()

    if time_input.lower() == 'x':
        if track in config:
            del config[track]
    elif time_input:
        new_time = parse_lap_time_input(time_input)
        if new_time and 30 < new_time < 600:
            config[track] = int(new_time) if float(new_time).is_integer() else new_time

    save_json_config(CONFIG_DIR / f"lap_times_{category}_{condition}.json", config)

    print()
    print("  Saved!")
    import time
    time.sleep(0.5)


def _edit_both_times(category, track, dry_config, wet_config, current_dry, current_wet):
    """Edit both dry and wet times for a track."""
    print_header(f"Edit Both Times: {prettify_name(track)}")
    print(f"  Current Dry: {format_lap_time(current_dry)}")
    print(f"  Current Wet: {format_lap_time(current_wet)}")
    print()
    print("  Enter time as M:SS (e.g., 1:44) or seconds (e.g., 104)")
    print("  Press Enter to keep current value, or type 'x' to clear")
    print()

    # Edit dry time
    dry_input = input(f"  New Dry Time [{format_lap_time(current_dry)}]: ").strip()
    if dry_input.lower() == 'x':
        if track in dry_config:
            del dry_config[track]
    elif dry_input:
        new_dry = parse_lap_time_input(dry_input)
        if new_dry and 30 < new_dry < 600:
            dry_config[track] = int(new_dry) if float(new_dry).is_integer() else new_dry

    # Edit wet time
    wet_input = input(f"  New Wet Time [{format_lap_time(current_wet)}]: ").strip()
    if wet_input.lower() == 'x':
        if track in wet_config:
            del wet_config[track]
    elif wet_input:
        new_wet = parse_lap_time_input(wet_input)
        if new_wet and 30 < new_wet < 600:
            wet_config[track] = int(new_wet) if float(new_wet).is_integer() else new_wet

    # Save both
    save_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json", dry_config)
    save_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json", wet_config)

    print()
    print("  Saved!")
    import time
    time.sleep(0.5)


def add_track(category):
    """Add a new track to the category."""
    dry_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json")
    wet_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json")

    print_header(f"Add Track - {CATEGORY_NAMES[category]}")
    print("  Enter track name (use underscores for spaces, e.g., watkins_glen)")
    print()

    track = input("  Track name: ").strip().lower().replace(" ", "_")

    if not track:
        return

    # Check if already exists
    if track in dry_config or track in wet_config:
        print(f"  Track '{track}' already exists!")
        import time
        time.sleep(1)
        return

    print()
    print("  Enter benchmark times (M:SS or seconds)")
    print()

    # Get dry time
    dry_input = input("  Dry Time: ").strip()
    dry_time = parse_lap_time_input(dry_input)
    if dry_time and 30 < dry_time < 600:
        dry_config[track] = int(dry_time) if float(dry_time).is_integer() else dry_time

    # Get wet time
    wet_input = input("  Wet Time: ").strip()
    wet_time = parse_lap_time_input(wet_input)
    if wet_time and 30 < wet_time < 600:
        wet_config[track] = int(wet_time) if float(wet_time).is_integer() else wet_time

    # Save
    save_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json", dry_config)
    save_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json", wet_config)

    print()
    print(f"  Added {prettify_name(track)}!")
    import time
    time.sleep(0.5)


def delete_track(category, track):
    """Delete a track from the category."""
    print_header(f"Delete Track: {prettify_name(track)}")
    print("  Are you sure you want to delete this track? (y/n)")

    key = get_key()
    if key.lower() != 'y':
        return

    dry_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json")
    wet_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json")

    if track in dry_config:
        del dry_config[track]
    if track in wet_config:
        del wet_config[track]

    save_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json", dry_config)
    save_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json", wet_config)

    print()
    print("  Deleted!")
    import time
    time.sleep(0.5)


def edit_tolerance(category):
    """Edit the tolerance for a category with recommendation and global/local option."""
    dry_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json")
    wet_config = load_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json")

    current = dry_config.get('_tolerance', 0.20)

    # Calculate recommended tolerance based on tightest dry/wet gap
    tracks_dry = {k: v for k, v in dry_config.items() if not k.startswith('_')}
    tracks_wet = {k: v for k, v in wet_config.items() if not k.startswith('_')}

    min_recommended = None
    tightest_track = None

    for track, dry_time in tracks_dry.items():
        wet_time = tracks_wet.get(track)
        if dry_time and wet_time:
            rec = recommend_tolerance(dry_time, wet_time)
            if rec is not None:
                if min_recommended is None or rec < min_recommended:
                    min_recommended = rec
                    tightest_track = track

    print_header(f"Edit Tolerance - {CATEGORY_NAMES[category]}")
    print(f"  Current tolerance: +/- {current * 100:.0f}%")
    print()

    if min_recommended is not None:
        max_safe = calculate_max_safe_tolerance(
            tracks_dry[tightest_track], tracks_wet[tightest_track]
        )
        print(f"  Recommended: +/- {min_recommended * 100:.0f}% (max safe: {max_safe * 100:.0f}%)")
        print(f"  Based on tightest gap: {prettify_name(tightest_track)}")
        print()

    print("  Enter new tolerance as percentage (e.g., 20 for +/- 20%)")
    print()

    tol_input = input(f"  New Tolerance [{current * 100:.0f}%]: ").strip()

    if tol_input:
        try:
            new_tol = float(tol_input.replace('%', '')) / 100
            if 0.05 <= new_tol <= 0.50:  # 5% to 50%
                # Ask global or local
                print()
                print("  Apply to:")
                print("    [1] This category only")
                print("    [2] All categories")
                print()
                scope = input("  Choice [1]: ").strip()

                if scope == '2':
                    # Apply to all categories
                    for cat in VALID_CATEGORIES:
                        cat_dry = load_json_config(CONFIG_DIR / f"lap_times_{cat}_dry.json")
                        cat_wet = load_json_config(CONFIG_DIR / f"lap_times_{cat}_wet.json")
                        cat_dry['_tolerance'] = new_tol
                        cat_wet['_tolerance'] = new_tol
                        save_json_config(CONFIG_DIR / f"lap_times_{cat}_dry.json", cat_dry)
                        save_json_config(CONFIG_DIR / f"lap_times_{cat}_wet.json", cat_wet)
                    print()
                    print("  Saved to all categories!")
                else:
                    # Apply to this category only
                    dry_config['_tolerance'] = new_tol
                    wet_config['_tolerance'] = new_tol
                    save_json_config(CONFIG_DIR / f"lap_times_{category}_dry.json", dry_config)
                    save_json_config(CONFIG_DIR / f"lap_times_{category}_wet.json", wet_config)
                    print()
                    print("  Saved!")
            else:
                print()
                print("  Invalid tolerance. Must be between 5% and 50%.")
        except ValueError:
            print()
            print("  Invalid input.")

    import time
    time.sleep(0.5)


# =============================================================================
# Car Categories Editor
# =============================================================================

def category_editor():
    """Main entry point for car categories editor."""
    selected = 0

    while True:
        # Load car categories
        config = load_json_config(CONFIG_DIR / "car_categories.json")

        # Filter out comments
        cars = {k: v for k, v in config.items() if not k.startswith('_')}
        car_list = sorted(cars.keys())

        # Build menu items
        items = []
        for car in car_list:
            items.append({'car': car, 'category': cars[car]})
        items.append({'action': 'add_car'})

        # Ensure selected is valid
        if selected >= len(items):
            selected = len(items) - 1
        if selected < 0:
            selected = 0

        # Display
        print_header("Edit Car Categories")

        for i, item in enumerate(items):
            prefix = "  > " if i == selected else "    "
            if 'action' in item:
                print(f"{prefix}[+ Add Car]")
            else:
                car_display = prettify_name(item['car'])
                cat_display = CATEGORY_NAMES.get(item['category'], item['category'].upper())
                print(f"{prefix}{car_display:<40} {cat_display}")

        print()
        print("  [Up/Down] Navigate  [Enter] Edit  [D] Delete  [Esc] Back")

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(items)
        elif key == 'DOWN':
            selected = (selected + 1) % len(items)
        elif key == 'ENTER':
            item = items[selected]
            if 'action' in item and item['action'] == 'add_car':
                add_car()
            elif 'car' in item:
                edit_car_category(item['car'])
        elif key == 'D':
            if selected < len(items) - 1:  # Not the "Add Car" item
                item = items[selected]
                if 'car' in item:
                    delete_car(item['car'])
        elif key == 'ESC':
            return


def edit_car_category(car):
    """Edit the category for a specific car."""
    config = load_json_config(CONFIG_DIR / "car_categories.json")
    current = config.get(car, "unknown")

    selected = VALID_CATEGORIES.index(current) if current in VALID_CATEGORIES else 0

    while True:
        print_header(f"Edit Category: {prettify_name(car)}")

        for i, cat in enumerate(VALID_CATEGORIES):
            prefix = "  > " if i == selected else "    "
            print(f"{prefix}{CATEGORY_NAMES[cat]}")

        print()
        print("  [Up/Down] Navigate  [Enter] Select  [Esc] Cancel")

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(VALID_CATEGORIES)
        elif key == 'DOWN':
            selected = (selected + 1) % len(VALID_CATEGORIES)
        elif key == 'ENTER':
            config[car] = VALID_CATEGORIES[selected]
            save_json_config(CONFIG_DIR / "car_categories.json", config)
            print()
            print("  Saved!")
            import time
            time.sleep(0.5)
            return
        elif key == 'ESC':
            return


def add_car():
    """Add a new car to the categories."""
    config = load_json_config(CONFIG_DIR / "car_categories.json")

    print_header("Add Car")
    print("  Enter car name (as it appears in filenames)")
    print()

    car = input("  Car name: ").strip()

    if not car:
        return

    # Check if already exists
    if car in config:
        print(f"  Car '{car}' already exists!")
        import time
        time.sleep(1)
        return

    # Select category
    selected = 0

    while True:
        print_header(f"Select Category for: {prettify_name(car)}")

        for i, cat in enumerate(VALID_CATEGORIES):
            prefix = "  > " if i == selected else "    "
            print(f"{prefix}{CATEGORY_NAMES[cat]}")

        print()
        print("  [Up/Down] Navigate  [Enter] Select  [Esc] Cancel")

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(VALID_CATEGORIES)
        elif key == 'DOWN':
            selected = (selected + 1) % len(VALID_CATEGORIES)
        elif key == 'ENTER':
            config[car] = VALID_CATEGORIES[selected]
            save_json_config(CONFIG_DIR / "car_categories.json", config)
            print()
            print(f"  Added {prettify_name(car)} as {CATEGORY_NAMES[VALID_CATEGORIES[selected]]}!")
            import time
            time.sleep(0.5)
            return
        elif key == 'ESC':
            return


def delete_car(car):
    """Delete a car from the categories."""
    print_header(f"Delete Car: {prettify_name(car)}")
    print("  Are you sure you want to delete this car? (y/n)")

    key = get_key()
    if key.lower() != 'y':
        return

    config = load_json_config(CONFIG_DIR / "car_categories.json")

    if car in config:
        del config[car]

    save_json_config(CONFIG_DIR / "car_categories.json", config)

    print()
    print("  Deleted!")
    import time
    time.sleep(0.5)


# =============================================================================
# Settings Editor
# =============================================================================

def settings_editor():
    """Main entry point for settings editor."""
    settings_file = CONFIG_DIR / "settings.json"
    settings = load_json_config(settings_file)

    # Default values if not present
    if 'default_motec_path' not in settings:
        settings['default_motec_path'] = r"C:\Users\alasd\OneDrive\Documents\Assetto Corsa Competizione\MoTeC"
    if 'report_output_path' not in settings:
        settings['report_output_path'] = r"C:\Temp"
    if 'pb_count' not in settings:
        settings['pb_count'] = 3
    if 'default_tolerance' not in settings:
        settings['default_tolerance'] = 0.05

    options = [
        "Default MoTeC Path",
        "Report Output Path",
        "PBs Per Condition",
        "Default Tolerance",
        "Apply Tolerance to All Categories"
    ]
    selected = 0

    while True:
        print_header("Settings")

        # Display current values
        print(f"  {CYAN}Default MoTeC Path:{RESET}")
        print(f"    {DIM}{settings.get('default_motec_path', 'Not set')}{RESET}")
        print()
        print(f"  {CYAN}Report Output Path:{RESET}")
        print(f"    {DIM}{settings.get('report_output_path', 'Not set')}{RESET}")
        print()
        print(f"  {CYAN}PBs Per Condition:{RESET} {settings.get('pb_count', 3)}")
        print(f"  {CYAN}Default Tolerance:{RESET} +/- {settings.get('default_tolerance', 0.05) * 100:.0f}%")
        print()
        print(f"  {DIM}{'-' * 40}{RESET}")
        print()

        for i, option in enumerate(options):
            if i == selected:
                print(f"  {SELECTED_COLOR}>{RESET} {BRIGHT_WHITE}{option}{RESET}")
            else:
                print(f"    {WHITE}{option}{RESET}")

        print()
        print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] Edit  [Esc] Back{RESET}")
        print_footer()

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(options)
        elif key == 'DOWN':
            selected = (selected + 1) % len(options)
        elif key == 'ENTER':
            if selected == 0:  # MoTeC Path
                edit_path_setting(settings, 'default_motec_path', "Default MoTeC Path")
                save_json_config(settings_file, settings)
            elif selected == 1:  # Report Path
                edit_path_setting(settings, 'report_output_path', "Report Output Path")
                save_json_config(settings_file, settings)
            elif selected == 2:  # PB Count
                edit_pb_count(settings)
                save_json_config(settings_file, settings)
            elif selected == 3:  # Default Tolerance
                edit_default_tolerance(settings)
                save_json_config(settings_file, settings)
            elif selected == 4:  # Apply to All
                apply_tolerance_to_all(settings.get('default_tolerance', 0.05))
        elif key == 'ESC':
            return


def edit_path_setting(settings, key, title):
    """Edit a path setting."""
    current = settings.get(key, '')

    print_header(f"Edit: {title}")
    print(f"  Current: {current}")
    print()
    print("  Enter new path (or press Enter to keep current):")
    print()

    new_path = input("  Path: ").strip()

    # Handle quoted paths
    new_path = new_path.strip('"').strip("'")

    if new_path:
        settings[key] = new_path
        print()
        print("  Saved!")
    else:
        print()
        print("  Kept current value.")

    import time
    time.sleep(0.5)


def edit_pb_count(settings):
    """Edit the number of PBs to keep per condition."""
    current = settings.get('pb_count', 3)

    print_header("Edit: PBs Per Condition")
    print(f"  Current: {current}")
    print()
    print("  How many PBs should be kept per track/car/condition?")
    print("  (Typically 3, range 1-10)")
    print()

    count_input = input(f"  PB Count [{current}]: ").strip()

    if count_input:
        try:
            count = int(count_input)
            if 1 <= count <= 10:
                settings['pb_count'] = count
                print()
                print("  Saved!")
            else:
                print()
                print("  Invalid. Must be between 1 and 10.")
        except ValueError:
            print()
            print("  Invalid number.")

    import time
    time.sleep(0.5)


def edit_default_tolerance(settings):
    """Edit the default tolerance setting."""
    current = settings.get('default_tolerance', 0.05)

    print_header("Edit: Default Tolerance")
    print(f"  Current: +/- {current * 100:.0f}%")
    print()
    print("  Enter new tolerance as percentage (e.g., 5 for +/- 5%)")
    print("  This is used when creating new category configs.")
    print()

    tol_input = input(f"  Tolerance [{current * 100:.0f}%]: ").strip()

    if tol_input:
        try:
            new_tol = float(tol_input.replace('%', '')) / 100
            if 0.01 <= new_tol <= 0.50:  # 1% to 50%
                settings['default_tolerance'] = new_tol
                print()
                print("  Saved!")
            else:
                print()
                print("  Invalid. Must be between 1% and 50%.")
        except ValueError:
            print()
            print("  Invalid input.")

    import time
    time.sleep(0.5)


def apply_tolerance_to_all(tolerance):
    """Apply the default tolerance to all category config files."""
    print_header("Apply Tolerance to All Categories")
    print(f"  This will set tolerance to +/- {tolerance * 100:.0f}% for ALL categories.")
    print()
    print("  Categories affected:")
    for cat in VALID_CATEGORIES:
        print(f"    - {CATEGORY_NAMES[cat]} (dry & wet)")
    print()
    print("  Are you sure? (y/n)")

    key = get_key()
    if key.lower() != 'y':
        print()
        print("  Cancelled.")
        import time
        time.sleep(0.5)
        return

    # Apply to all config files
    for cat in VALID_CATEGORIES:
        for condition in ['dry', 'wet']:
            config_file = CONFIG_DIR / f"lap_times_{cat}_{condition}.json"
            config = load_json_config(config_file)
            config['_tolerance'] = tolerance
            save_json_config(config_file, config)

    print()
    print(f"  Applied +/- {tolerance * 100:.0f}% tolerance to all categories!")
    import time
    time.sleep(1)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Run benchmark editor directly for testing
    benchmark_editor()
