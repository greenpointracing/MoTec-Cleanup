"""
MoTeC Cleanup Tool - Main Entry Point

Interactive CLI menu for:
- Scanning and organising telemetry files
- Editing benchmark lap times
- Editing car categories
- Settings

Requires Windows PowerShell - will exit with warning if run on Linux/WSL.
"""

import sys
import platform
import os


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
MAGENTA = "\033[35m"

# Theme colours
TITLE_COLOR = BRIGHT_GREEN
ACCENT_COLOR = BRIGHT_CYAN
SELECTED_COLOR = BRIGHT_YELLOW
HINT_COLOR = DIM + WHITE
BRAND_COLOR = DIM + GREEN

# Branding
BRAND_TEXT = "GreenPoint Racing"


def check_platform():
    """Check if running on Windows. Exit with warning if on Linux/WSL."""
    if platform.system() != "Windows":
        print()
        print("=" * 60)
        print("  ERROR: Unsupported Platform")
        print("=" * 60)
        print()
        print("  This tool must be run in Windows PowerShell, not Linux/WSL.")
        print()
        print("  OneDrive integration and Windows file paths require")
        print("  native Windows execution.")
        print()
        print("  To run this tool:")
        print("    1. Open Windows PowerShell")
        print("    2. cd C:\\Users\\alasd\\Projects\\MoTeC_Cleanup")
        print("    3. .\\venv\\Scripts\\Activate.ps1")
        print("    4. python src\\main.py")
        print()
        input("  Press Enter to exit...")
        sys.exit(1)


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls')


def print_header(title="MoTeC Cleanup Tool"):
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


def print_menu(options, selected_index):
    """Print menu options with selection indicator and colours."""
    for i, option in enumerate(options):
        if i == selected_index:
            print(f"  {SELECTED_COLOR}>{RESET} {BRIGHT_WHITE}{option}{RESET}")
        else:
            print(f"    {WHITE}{option}{RESET}")
    print()
    print(f"  {HINT_COLOR}[Up/Down] Navigate  [Enter] Select  [Esc] Exit{RESET}")
    print_footer()


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
        return 'ESC'

    return key.decode('utf-8', errors='ignore') if isinstance(key, bytes) else key


def main_menu():
    """Display and handle the main menu."""
    options = [
        "Scan & Organise Telemetry",
        "Undo Last Scan",
        "Clean Up Old Files",
        "Edit Benchmark Times",
        "Edit Car Categories",
        "Settings",
        "Exit"
    ]
    selected = 0

    while True:
        print_header()
        print_menu(options, selected)

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(options)
        elif key == 'DOWN':
            selected = (selected + 1) % len(options)
        elif key == 'ENTER':
            if selected == 0:  # Scan & Organise
                run_scan()
            elif selected == 1:  # Undo Last Scan
                undo_scan()
            elif selected == 2:  # Clean Up Old Files
                cleanup_old_files_menu()
            elif selected == 3:  # Edit Benchmark Times
                edit_benchmark_times()
            elif selected == 4:  # Edit Car Categories
                edit_car_categories()
            elif selected == 5:  # Settings
                show_settings()
            elif selected == 6:  # Exit
                return
        elif key == 'ESC':
            return


def run_scan():
    """Run the telemetry scan and organisation process."""
    clear_screen()

    options = [
        "Full Scan (copy PBs)",
        "Dry Run (preview only)"
    ]
    selected = 0

    while True:
        print_header("Scan & Organise Telemetry")
        print("  This will scan your MoTeC telemetry folder,")
        print("  identify top 3 dry AND top 3 wet laps per track/car combo,")
        print("  and copy PBs to a timestamped folder.")
        print()
        print("  Original files are NEVER modified or moved.")
        print()

        for i, option in enumerate(options):
            if i == selected:
                print(f"  > {option}")
            else:
                print(f"    {option}")

        print()
        print("  [Up/Down] Navigate  [Enter] Select  [Esc] Back")

        key = get_key()

        if key == 'UP':
            selected = (selected - 1) % len(options)
        elif key == 'DOWN':
            selected = (selected + 1) % len(options)
        elif key == 'ENTER':
            if selected == 0:  # Full Scan
                clear_screen()
                try:
                    from scan import scan_telemetry, results_browser
                    result = scan_telemetry(dry_run=False)
                    if result and result.get('comparison_data'):
                        print("  Would you like to browse the results? (y/n)")
                        browse_key = get_key()
                        if browse_key.lower() == 'y':
                            results_browser(result['comparison_data'])
                except ImportError as e:
                    print(f"  Error: Could not import scan module: {e}")
                except Exception as e:
                    print(f"  Error during scan: {e}")
                    import traceback
                    traceback.print_exc()
                input("\n  Press Enter to return to menu...")
                return
            elif selected == 1:  # Dry Run
                clear_screen()
                try:
                    from scan import scan_telemetry, results_browser
                    result = scan_telemetry(dry_run=True)
                    if result and result.get('comparison_data'):
                        print("  Would you like to browse the results? (y/n)")
                        browse_key = get_key()
                        if browse_key.lower() == 'y':
                            results_browser(result['comparison_data'])
                except ImportError as e:
                    print(f"  Error: Could not import scan module: {e}")
                except Exception as e:
                    print(f"  Error during scan: {e}")
                    import traceback
                    traceback.print_exc()
                input("\n  Press Enter to return to menu...")
                return
        elif key == 'ESC':
            return


def edit_benchmark_times():
    """Launch the benchmark times editor."""
    try:
        from config_editor import benchmark_editor
        benchmark_editor()
    except ImportError:
        print_header("Edit Benchmark Times")
        print("  [Config editor module not found]")
        print()
        input("  Press Enter to return to menu...")


def edit_car_categories():
    """Launch the car categories editor."""
    try:
        from config_editor import category_editor
        category_editor()
    except ImportError:
        print_header("Edit Car Categories")
        print("  [Config editor module not found]")
        print()
        input("  Press Enter to return to menu...")


def show_settings():
    """Launch the settings editor."""
    try:
        from config_editor import settings_editor
        settings_editor()
    except ImportError:
        print_header("Settings")
        print("  [Config editor module not found]")
        print()
        input("  Press Enter to return to menu...")


def cleanup_old_files_menu():
    """Clean up old telemetry files with safety confirmations."""
    try:
        from scan import get_cleanup_candidates, cleanup_old_files, get_default_motec_path
        from pathlib import Path
    except ImportError as e:
        print_header("Clean Up Old Files")
        print(f"  {RED}Error: Could not import scan module: {e}{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    print_header("Clean Up Old Files")

    # Warning banner
    print(f"  {RED}{BOLD}WARNING: This will permanently delete telemetry files!{RESET}")
    print()
    print(f"  {WHITE}This operation will delete .ld and .ldx files from the{RESET}")
    print(f"  {WHITE}selected directory. PB folders will NOT be affected.{RESET}")
    print()

    # Step 1: Prompt for directory path
    default_path = get_default_motec_path()
    print(f"  {ACCENT_COLOR}Step 1: Select Directory{RESET}")
    print()
    print(f"  Default: {WHITE}{default_path}{RESET}")
    print(f"  {HINT_COLOR}(Press Enter to use default, or type a new path){RESET}")
    print()

    while True:
        user_input = input("  Path: ").strip()

        # Handle quoted paths
        user_input = user_input.strip('"').strip("'")

        # Use default if empty
        if not user_input:
            motec_path = default_path
            break

        path = Path(user_input)

        if not path.exists():
            print(f"  {RED}ERROR: Path does not exist: {path}{RESET}")
            continue

        if not path.is_dir():
            print(f"  {RED}ERROR: Path is not a directory: {path}{RESET}")
            continue

        motec_path = path
        break

    print()
    print(f"  {WHITE}Scanning: {motec_path}{RESET}")
    print()

    # Step 2: Show what will be deleted
    candidates = get_cleanup_candidates(motec_path)

    if candidates['count'] == 0:
        print(f"  {YELLOW}No .ld or .ldx files found to clean up.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    print(f"  {ACCENT_COLOR}Step 2: Review Files to Delete{RESET}")
    print()
    print(f"  {BRIGHT_WHITE}Files found: {candidates['count']}{RESET}")
    print(f"  {BRIGHT_WHITE}Total size:  {candidates['total_size_mb']} MB{RESET}")
    print()

    # Show a sample of files (first 10)
    sample_files = candidates['files'][:10]
    print(f"  {WHITE}Sample of files to delete:{RESET}")
    for f in sample_files:
        print(f"    {DIM}{f.name}{RESET}")
    if candidates['count'] > 10:
        print(f"    {DIM}... and {candidates['count'] - 10} more files{RESET}")
    print()

    # Step 3: First confirmation
    print(f"  {ACCENT_COLOR}Step 3: Confirm Deletion{RESET}")
    print()
    print(f"  {RED}This will permanently delete {candidates['count']} files ({candidates['total_size_mb']} MB){RESET}")
    print(f"  {WHITE}from: {motec_path}{RESET}")
    print()
    print(f"  {YELLOW}PB folders (PBs_*) will NOT be affected.{RESET}")
    print()
    print(f"  Continue? {HINT_COLOR}(y/n){RESET}")

    key = get_key()

    if key.lower() != 'y':
        print()
        print(f"  {YELLOW}Cleanup cancelled.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    # Step 4: Type "delete" confirmation
    print()
    print(f"  {ACCENT_COLOR}Step 4: Final Confirmation{RESET}")
    print()
    print(f"  {RED}{BOLD}To confirm deletion, type 'delete' and press Enter:{RESET}")
    print()

    confirmation = input("  > ").strip().lower()

    if confirmation != 'delete':
        print()
        print(f"  {YELLOW}Cleanup cancelled. You typed '{confirmation}' instead of 'delete'.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    # Perform deletion
    print()
    print(f"  {WHITE}Deleting files...{RESET}")

    success, errors, error_list = cleanup_old_files(motec_path)

    print()
    if success > 0:
        print(f"  {GREEN}Successfully deleted {success} files.{RESET}")
    if errors > 0:
        print(f"  {RED}Failed to delete {errors} files:{RESET}")
        for err in error_list[:5]:
            print(f"    {DIM}{err}{RESET}")
        if len(error_list) > 5:
            print(f"    {DIM}... and {len(error_list) - 5} more errors{RESET}")

    print()
    input("  Press Enter to return to menu...")


def undo_scan():
    """Undo the last scan by deleting the most recent PB folder."""
    try:
        from scan import get_undo_candidates, undo_last_scan, get_default_motec_path
        from pathlib import Path
    except ImportError as e:
        print_header("Undo Last Scan")
        print(f"  {RED}Error: Could not import scan module: {e}{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    print_header("Undo Last Scan")

    # Step 1: Prompt for directory path
    default_path = get_default_motec_path()
    print(f"  {ACCENT_COLOR}Step 1: Select Directory{RESET}")
    print()
    print(f"  Default: {WHITE}{default_path}{RESET}")
    print(f"  {HINT_COLOR}(Press Enter to use default, or type a new path){RESET}")
    print()

    while True:
        user_input = input("  Path: ").strip()

        # Handle quoted paths
        user_input = user_input.strip('"').strip("'")

        # Use default if empty
        if not user_input:
            motec_path = default_path
            break

        path = Path(user_input)

        if not path.exists():
            print(f"  {RED}ERROR: Path does not exist: {path}{RESET}")
            continue

        if not path.is_dir():
            print(f"  {RED}ERROR: Path is not a directory: {path}{RESET}")
            continue

        motec_path = path
        break

    print()
    print(f"  {WHITE}Looking in: {motec_path}{RESET}")
    print()

    # Show available PB folders
    candidates = get_undo_candidates(motec_path)

    if not candidates:
        print(f"  {YELLOW}No PB folders found to undo.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    # Show the most recent folder
    folder, timestamp, file_count = candidates[0]

    print(f"  {ACCENT_COLOR}Most recent PB folder:{RESET}")
    print()
    print(f"    {BRIGHT_WHITE}{folder.name}{RESET}")
    print(f"    Created: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Files:   {file_count} PB files")
    print()

    # Show older folders if any
    if len(candidates) > 1:
        print(f"  {HINT_COLOR}({len(candidates) - 1} older PB folder(s) will be preserved){RESET}")
        print()

    # Step 2: First confirmation
    print(f"  {ACCENT_COLOR}Step 2: Confirm Deletion{RESET}")
    print()
    print(f"  {RED}This will PERMANENTLY DELETE this folder and all its contents.{RESET}")
    print()
    print(f"  Continue? {HINT_COLOR}(y/n){RESET}")

    key = get_key()

    if key.lower() != 'y':
        print()
        print(f"  {YELLOW}Undo cancelled.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    # Step 3: Type "delete" confirmation
    print()
    print(f"  {ACCENT_COLOR}Step 3: Final Confirmation{RESET}")
    print()
    print(f"  {RED}{BOLD}To confirm deletion, type 'delete' and press Enter:{RESET}")
    print()

    confirmation = input("  > ").strip().lower()

    if confirmation != 'delete':
        print()
        print(f"  {YELLOW}Undo cancelled. You typed '{confirmation}' instead of 'delete'.{RESET}")
        print()
        input("  Press Enter to return to menu...")
        return

    # Perform deletion
    result, message = undo_last_scan(motec_path)
    print()
    if result:
        print(f"  {GREEN}{message}{RESET}")
    else:
        print(f"  {RED}Error: {message}{RESET}")

    print()
    input("  Press Enter to return to menu...")


def main():
    """Main entry point."""
    # Check platform first
    check_platform()

    try:
        main_menu()
    except KeyboardInterrupt:
        pass
    finally:
        clear_screen()
        print("MoTeC Cleanup Tool - Goodbye!")


if __name__ == "__main__":
    main()
