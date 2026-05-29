#!/usr/bin/env python3
"""Real-time Star Trek script search TUI."""

import curses
import json
import glob
import os
import re
import sys
import tempfile
import subprocess

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "json_transcripts")

SERIES_MAP = {"tng": "TNG", "ds9": "DS9", "voy": "VOY", "ent": "ENT", "tos": "TOS", "tas": "TAS", "movies": "Movies"}

MOVIE_ABBREVS = {
    "movie01": "ST:TMP",
    "movie02": "ST:TWOK",
    "movie03": "ST:TSFS",
    "movie04": "ST:TVH",
    "movie05": "ST:TFF",
    "movie06": "ST:TUC",
    "movie07": "ST:GEN",
    "movie08": "ST:FC",
    "movie09": "ST:INS",
    "movie10": "ST:NEM",
}


def load_all_lines():
    """Load every dialogue line into a flat list for searching."""
    lines = []
    for series_dir in SERIES_MAP:
        series_label = SERIES_MAP[series_dir]
        pattern = os.path.join(DATA_DIR, series_dir, "*.json")
        for filepath in sorted(glob.glob(pattern)):
            basename = os.path.basename(filepath)  # e.g. "s01e01 - Title.json"
            ep_code = basename.split(" - ")[0] if " - " in basename else basename.replace(".json", "")
            with open(filepath) as f:
                ep = json.load(f)
            title = ep.get("title", "")
            line_num = 0
            for scene in ep["scenes"]:
                for dial in scene["dialogue"]:
                    display_series = MOVIE_ABBREVS.get(ep_code, series_label) if series_dir == "movies" else series_label
                    lines.append(
                        {
                            "character": dial["character"],
                            "line": dial["line"],
                            "series": display_series,
                            "ep_code": ep_code,
                            "title": title,
                            "filepath": filepath,
                            "line_num": line_num,
                        }
                    )
                    line_num += 1
    return lines


def search(all_lines, query):
    """Return lines matching query (case-insensitive)."""
    if not query.strip():
        return []
    q = query.lower()
    results = []
    for entry in all_lines:
        if q in entry["line"].lower():
            results.append(entry)
    return results


def dump_episode_and_open(entry, query):
    """Dump full episode transcript to a temp file; open vim at the matched line."""
    with open(entry["filepath"]) as f:
        ep = json.load(f)

    transcript_lines = []
    target_line = 0
    current = 0
    found = False
    q = query.lower()

    for scene in ep["scenes"]:
        for dial in scene["dialogue"]:
            transcript_lines.append(f"{dial['character']}: {dial['line']}")
            if not found and q in dial["line"].lower() and dial["character"] == entry["character"] and dial["line"] == entry["line"]:
                target_line = current
                found = True
            current += 1

    title_safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", ep.get("title", "episode"))
    filename = f"{entry['series']}_{entry['ep_code']}_{title_safe}.txt"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)

    with open(tmp_path, "w") as f:
        f.write("\n".join(transcript_lines) + "\n")

    # vim line numbers are 1-indexed
    subprocess.call(["vim", f"+{target_line + 1}", tmp_path])


def main(stdscr):
    curses.curs_set(1)
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_YELLOW, -1)   # search prompt
    curses.init_pair(2, curses.COLOR_CYAN, -1)      # character name
    curses.init_pair(3, curses.COLOR_GREEN, -1)     # episode info
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)  # selected row
    curses.init_pair(5, curses.COLOR_RED, -1)       # bold match text
    curses.init_pair(6, curses.COLOR_WHITE, -1)     # normal quote text

    stdscr.timeout(50)  # non-blocking getch with 50ms timeout

    # Loading screen
    stdscr.clear()
    stdscr.addstr(0, 0, "Loading Star Trek scripts...", curses.A_BOLD)
    stdscr.refresh()

    all_lines = load_all_lines()

    query = ""
    cursor_pos = 0       # cursor position in query string
    selected = -1        # -1 = in search bar, 0+ = result index
    scroll_offset = 0    # first visible result index
    results = []
    last_query = None

    while True:
        height, width = stdscr.getmaxyx()
        max_results_visible = height - 3  # 1 for prompt, 1 for status, 1 for border

        # Recompute results if query changed
        if query != last_query:
            results = search(all_lines, query)
            last_query = query
            selected = -1
            scroll_offset = 0

        stdscr.erase()

        # Draw search bar
        prompt = " Search: "
        stdscr.addstr(0, 0, prompt, curses.color_pair(1) | curses.A_BOLD)
        # Draw query text, truncated to fit
        max_q_width = width - len(prompt) - 1
        display_q = query[:max_q_width] if len(query) > max_q_width else query
        stdscr.addstr(0, len(prompt), display_q)

        # Draw separator
        stdscr.addstr(1, 0, "─" * min(width - 1, 200), curses.A_DIM)

        # Draw results
        if not query.strip():
            msg = "Type to search across all Star Trek scripts..."
            stdscr.addstr(2, 1, msg[:width - 2], curses.A_DIM)
        elif not results:
            stdscr.addstr(2, 1, "No results found.", curses.A_DIM)
        else:
            visible_count = min(max_results_visible, len(results) - scroll_offset)
            for i in range(visible_count):
                idx = scroll_offset + i
                if idx >= len(results):
                    break
                entry = results[idx]
                row = 2 + i
                if row >= height:
                    break

                is_selected = idx == selected

                # Build the display string piece by piece
                if entry['ep_code'].startswith('movie'):
                    prefix = f"{entry['character']}, {entry['series']}: '"
                else:
                    prefix = f"{entry['character']}, {entry['series']} {entry['ep_code']} {entry['title']}: '"
                suffix = "'"

                # Find match span in the line for highlighting
                line_text = entry["line"]

                # Truncate line to fit
                avail = width - len(prefix) - len(suffix) - 2
                if avail < 10:
                    avail = 10

                # Find the match position
                q_lower = query.lower()
                match_start = line_text.lower().find(q_lower)

                # If line is long, center the window around the match
                if len(line_text) > avail:
                    if match_start >= 0:
                        # Center the match in the available space
                        window_start = max(0, match_start - avail // 3)
                        window_end = window_start + avail
                        if window_end > len(line_text):
                            window_end = len(line_text)
                            window_start = max(0, window_end - avail)
                        display_line = line_text[window_start:window_end]
                        # Adjust match_start relative to display window
                        match_start = match_start - window_start
                        if window_start > 0:
                            display_line = "…" + display_line[1:]
                        if window_end < len(line_text):
                            display_line = display_line[:-1] + "…"
                    else:
                        display_line = line_text[:avail]
                else:
                    display_line = line_text

                col = 1
                if is_selected:
                    # Fill entire row with selection background
                    try:
                        stdscr.addstr(row, 0, " " * (width - 1), curses.color_pair(4))
                    except curses.error:
                        pass

                base_attr = curses.color_pair(4) if is_selected else 0

                # Draw prefix (character, episode info)
                try:
                    if is_selected:
                        stdscr.addstr(row, col, prefix, base_attr | curses.A_BOLD)
                    else:
                        # character part
                        char_part = entry["character"] + ", "
                        stdscr.addstr(row, col, char_part, curses.color_pair(2) | curses.A_BOLD)
                        if entry['ep_code'].startswith('movie'):
                            ep_part = f"{entry['series']}: '"
                        else:
                            ep_part = f"{entry['series']} {entry['ep_code']} {entry['title']}: '"
                        stdscr.addstr(row, col + len(char_part), ep_part, curses.color_pair(3))
                except curses.error:
                    continue

                col += len(prefix)

                # Draw the line text with match highlighting
                if match_start >= 0 and match_start < len(display_line):
                    match_end = match_start + len(query)
                    # Before match
                    before = display_line[:match_start]
                    matched = display_line[match_start:match_end]
                    after = display_line[match_end:]

                    try:
                        if before:
                            stdscr.addstr(row, col, before, base_attr)
                        col += len(before)
                        if matched:
                            stdscr.addstr(
                                row,
                                col,
                                matched,
                                base_attr | curses.A_BOLD | (curses.color_pair(5) if not is_selected else 0),
                            )
                        col += len(matched)
                        if after:
                            remaining_width = width - col - len(suffix) - 1
                            stdscr.addstr(row, col, after[:max(0, remaining_width)], base_attr)
                            col += min(len(after), max(0, remaining_width))
                    except curses.error:
                        pass
                else:
                    try:
                        stdscr.addstr(row, col, display_line, base_attr)
                        col += len(display_line)
                    except curses.error:
                        pass

                # Closing quote
                try:
                    stdscr.addstr(row, col, suffix, base_attr | (curses.color_pair(3) if not is_selected else 0))
                except curses.error:
                    pass

        # Status bar at the bottom
        status = f" {len(results)} results" if query.strip() else " Ready"
        if results and selected >= 0:
            status += f" | [{selected + 1}/{len(results)}]"
        status += " | ↑↓ navigate | Enter: open in vim | Esc: quit"
        try:
            stdscr.addstr(height - 1, 0, status[:width - 1], curses.A_DIM | curses.A_REVERSE)
        except curses.error:
            pass

        # Position cursor in search bar
        if selected == -1:
            cursor_screen_x = len(prompt) + cursor_pos
            if cursor_screen_x < width:
                try:
                    stdscr.move(0, cursor_screen_x)
                except curses.error:
                    pass

        stdscr.refresh()

        # Input handling
        try:
            ch = stdscr.get_wch()
        except curses.error:
            continue

        if isinstance(ch, str):
            if ch == "\x1b":  # Escape
                break
            elif ch == "\n" or ch == "\r":
                if selected >= 0 and selected < len(results):
                    curses.endwin()
                    dump_episode_and_open(results[selected], query)
                    stdscr = curses.initscr()
                    curses.noecho()
                    curses.cbreak()
                    stdscr.keypad(True)
                    curses.start_color()
                    curses.use_default_colors()
                    curses.init_pair(1, curses.COLOR_YELLOW, -1)
                    curses.init_pair(2, curses.COLOR_CYAN, -1)
                    curses.init_pair(3, curses.COLOR_GREEN, -1)
                    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
                    curses.init_pair(5, curses.COLOR_RED, -1)
                    curses.init_pair(6, curses.COLOR_WHITE, -1)
                    curses.curs_set(1)
                    stdscr.timeout(50)
            elif ch == "\x7f" or ch == "\b":  # Backspace
                if selected == -1 and cursor_pos > 0:
                    query = query[: cursor_pos - 1] + query[cursor_pos:]
                    cursor_pos -= 1
            elif ch == "\t":  # Tab to enter results
                if results:
                    selected = 0
                    scroll_offset = 0
            else:
                if selected == -1:
                    # Regular character input
                    query = query[:cursor_pos] + ch + query[cursor_pos:]
                    cursor_pos += 1
        elif isinstance(ch, int):
            if ch == curses.KEY_BACKSPACE:
                if selected == -1 and cursor_pos > 0:
                    query = query[: cursor_pos - 1] + query[cursor_pos:]
                    cursor_pos -= 1
            elif ch == curses.KEY_DC:  # Delete
                if selected == -1 and cursor_pos < len(query):
                    query = query[:cursor_pos] + query[cursor_pos + 1 :]
            elif ch == curses.KEY_LEFT:
                if selected == -1 and cursor_pos > 0:
                    cursor_pos -= 1
            elif ch == curses.KEY_RIGHT:
                if selected == -1 and cursor_pos < len(query):
                    cursor_pos += 1
            elif ch == curses.KEY_HOME:
                cursor_pos = 0
            elif ch == curses.KEY_END:
                cursor_pos = len(query)
            elif ch == curses.KEY_DOWN:
                if results:
                    if selected < len(results) - 1:
                        selected += 1
                    # Scroll if selection goes below visible area
                    if selected >= scroll_offset + max_results_visible:
                        scroll_offset = selected - max_results_visible + 1
            elif ch == curses.KEY_UP:
                if selected > 0:
                    selected -= 1
                    if selected < scroll_offset:
                        scroll_offset = selected
                elif selected == 0:
                    selected = -1  # back to search bar
            elif ch == curses.KEY_NPAGE:  # Page Down
                if results:
                    selected = min(selected + max_results_visible, len(results) - 1)
                    if selected >= scroll_offset + max_results_visible:
                        scroll_offset = selected - max_results_visible + 1
            elif ch == curses.KEY_PPAGE:  # Page Up
                if results:
                    selected = max(selected - max_results_visible, 0)
                    if selected < scroll_offset:
                        scroll_offset = selected
            elif ch == curses.KEY_RESIZE:
                pass  # will be handled on next loop iteration


if __name__ == "__main__":
    curses.wrapper(main)
