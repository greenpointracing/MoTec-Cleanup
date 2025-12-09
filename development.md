# Development Notes - Future Features

## Issue 14: Extract Single Lap from MoTeC Files

**Status:** Low priority - POC planned for later

**Goal:** Separate the fastest lap data from an .ld/.ldx file to create a new single-lap file.

### Current File Structure

**`.ldx` file (XML)** - Contains lap beacon timestamps in microseconds (cumulative times):
```xml
<Marker Name="0, id=99" Time="1.10018e+09" />  <!-- 1100.18 seconds -->
<Marker Name="1, id=99" Time="1.22553e+09" />  <!-- 1225.53 seconds -->
<!-- Lap time = 1225.53 - 1100.18 = ~125.35 seconds -->
```

**`.ld` file (Binary)** - Contains telemetry data as time-series channels:
- Throttle, brake, speed, steering, suspension, etc.
- Sampled at various frequencies (10Hz, 20Hz, 100Hz)
- Continuous data from session start to end

### Technical Approach

To extract a single lap:
1. Parse .ldx to get lap beacon timestamps
2. Identify the target lap (e.g., fastest)
3. Calculate sample index range for each channel based on:
   - Lap start/end timestamps
   - Channel sample frequency
4. Slice each channel's data array to just that range
5. Recalculate header pointers for new data layout
6. Write new .ld file with sliced data
7. Create matching .ldx with single lap marker (Time="0")

### Existing Resources

`ldparser.py` already has write capability:
- `ldData.write()` - Write complete .ld file
- `ldData.frompd()` - Create ldData from pandas DataFrame
- `ldHead.write()`, `ldChan.write()` - Component writers

### Challenges

- Different channels have different sample rates
- Need correct offset calculation per frequency
- Header pointers must be recalculated for sliced data
- Must handle edge cases (partial first/last laps)

### POC Plan

1. Select a test file with multiple laps
2. Read file structure and print channel info
3. Get lap timestamps from .ldx
4. Calculate sample indices for fastest lap
5. Slice channel data arrays
6. Write new .ld file
7. Create new .ldx with single marker
8. Test: Open in MoTeC i2 to verify

### Sample Code Skeleton

```python
def extract_lap(ld_path, ldx_path, lap_index, output_path):
    """Extract a single lap from a MoTeC session file.

    Args:
        ld_path: Path to source .ld file
        ldx_path: Path to source .ldx file
        lap_index: Which lap to extract (0-based, or -1 for fastest)
        output_path: Path for output .ld file (will create .ldx too)
    """
    # 1. Parse lap times from .ldx
    lap_times = get_lap_times_from_ldx(ldx_path)
    lap_timestamps = get_lap_timestamps_from_ldx(ldx_path)  # Need cumulative times

    # 2. Find target lap
    if lap_index == -1:
        lap_index = lap_times.index(min(lap_times))

    # 3. Get time boundaries
    start_time = lap_timestamps[lap_index]
    end_time = lap_timestamps[lap_index + 1]
    duration = end_time - start_time

    # 4. Load telemetry
    ld = ldData.fromfile(ld_path)

    # 5. Slice each channel
    new_channels = []
    for chan in ld.channs:
        start_sample = int(start_time * chan.freq)
        end_sample = int(end_time * chan.freq)
        sliced_data = chan.data[start_sample:end_sample]
        # Create new channel with sliced data...

    # 6. Write new files
    # ... build new ldData and write
    # ... create new .ldx with single marker
```

### Alternative Approach

If direct slicing proves difficult, could use `ldData.frompd()`:
1. Load all channels into pandas DataFrame
2. Calculate row indices for target lap
3. Slice DataFrame
4. Use `ldData.frompd(df)` to create new ldData
5. Write output file

This loses some metadata but may be simpler.
