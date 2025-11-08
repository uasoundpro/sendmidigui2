import difflib
import csv
import os
import shutil

def create_ordered_setlist_csv(setlist_path, base_csv_path, output_csv_path):
    """
    Creates an ordered CSV from a setlist file and a base CSV.
    Songs not found in the base CSV will be marked as '# MISSING'.
    """
    try:
        # Try reading with utf-8 first, then fall back to latin-1
        try:
            with open(setlist_path, "r", encoding="utf-8") as f:
                song_names = [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            with open(setlist_path, "r", encoding="latin-1") as f:
                song_names = [line.strip() for line in f if line.strip()]

        try:
            with open(base_csv_path, "r", encoding="utf-8") as f:
                all_rows = [row for row in csv.reader(f.read().splitlines()) if row]
        except UnicodeDecodeError:
            with open(base_csv_path, "r", encoding="latin-1") as f:
                all_rows = [row for row in csv.reader(f.read().splitlines()) if row]

        label_lookup = {row[0].strip(): row for row in all_rows}
        lower_keys = {k.lower(): k for k in label_lookup}

        pinned_top = ["MUTE", "DEFAULT (JCM800)", "DEFAULT (RVerb)"]
        all_requested = pinned_top + song_names + ["TEST 123"] # Always add test at bottom

        output_rows = []
        for name in all_requested:
            match_key = lower_keys.get(name.lower())
            if match_key:
                output_rows.append(label_lookup[match_key])
            else:
                close_matches = difflib.get_close_matches(name.lower(), lower_keys.keys(), n=1, cutoff=0.7)
                if close_matches:
                    best_match = lower_keys[close_matches[0]]
                    output_rows.append(label_lookup[best_match])
                else:
                    output_rows.append([name, "", "", "# MISSING"])

        with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(output_rows)

    except Exception as e:
        print("Error generating setlist CSV:", e)
        # Fallback to base_csv_path if setlist creation fails
        shutil.copyfile(base_csv_path, output_csv_path)