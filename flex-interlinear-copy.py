#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
os.environ["PATH"] += os.pathsep + "/usr/bin"

import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import re
import webbrowser
import csv
import io
import tkinter.simpledialog as simpledialog
import xml.etree.ElementTree as ET
import xml.dom.minidom
import xml.sax.saxutils
from xml.dom import minidom
import re

MORPHEME_MARKERS = {"-", "=", "_", "."} #Define morpheme break markers
#FLEx Row Labels (note: define these lower case to match input)
FLEX_ROW_LABELS = ["word", "morphemes", "lex. gloss", "lex. gram info", "word Gloss", "word cat.", "free"]

def clean_input(text):
    # Remove BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]
    # Remove non-breaking spaces and other invisible/control chars
    text = text.replace('\u00A0', ' ')  # non-breaking space to regular space
    text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t')
    return text

def process_labeled_rows(rows):
    print("Processing labeled rows with FLEx labels...")
    print("Initial rows:", rows)
    """
    Process rows with FLEx labels by removing the first column from non-Free rows
    and formatting the Free row with quotes.
    
    Args:
        rows: List of lists containing TSV row data
        open_quote: Opening quotation character (default: "'")
        close_quote: Closing quotation character (default: "'")
    
    Returns:
        Modified rows list
    """
    if not rows:
        return rows
    
    # Define the labels to look for
    labels = FLEX_ROW_LABELS
    
    # Check if we have at least two labels including "Free"
    found_labels = set()
    free_row_index = None
    
    for i, row in enumerate(rows):
        if row:  # Make sure row is not empty
            for j, cell in enumerate(row):
                cell_stripped = cell.strip().lower()  # Normalize to lowercase for matching
                # Check for exact matches or "Free " prefix
                if cell_stripped in labels:
                    found_labels.add(cell_stripped)
                elif cell_stripped.startswith("free "):
                    found_labels.add("free")
                    free_row_index = i
    
    # Check if we have at least 2 labels including "Free"
    if len(found_labels) < 2 or "free" not in found_labels:
        return rows  # Don't modify if criteria not met
    
    # Process the rows
    for i, row in enumerate(rows):
        if i == free_row_index:
            # This is the Free row - remove "Free " prefix and add quotes
            for j, cell in enumerate(row):
                if cell.strip().lower().startswith("free "):
                    # Remove "Free " and add quotes around the remaining text
                    free_text = cell.strip()[5:]  # Remove "Free " (5 characters)
                    row[j] = f"'{free_text}'"
                    break
        else:
            # This is not the Free row - delete the first column
            if row:  # Make sure row is not empty
                del row[0]
    
    return rows

def is_free_row(cell):
    stripped = cell.strip()
    return (
        stripped.lower().startswith("free ") or
        (stripped.startswith("'") and stripped.endswith("'"))
    )

def convert_clipboard_for_mit(rows, latex_formatting=True, exType="single"):
    print("Rows before LaTeX conversion:", rows)

    if latex_formatting:
        ex_title = r"%\extitle{Example Caption}\\ %Caption/title with \extitle{} style"
        ex_subtitle = r"%\exsubtitle{Sub-caption}\\ %Sub-caption/subtitle using \exsubtitle style."
        txt_ref = r"%\txtref{TxtRf\_\#} %Reference source text abbreviation (predefined style)"
    else:
        ex_title = r"%\textbf{\underline{Example Caption}}\\ %Caption/title with built-in formatting"
        ex_subtitle = r"%\textit{Sub-caption} \\ %Sub-caption/subtitle with built-in formatting"
        txt_ref = r"%\hfill\textit{TxtRf\_\#} %Reference source text abbreviation with built-in formatting"

    # Replace spaces with ~ except for "Free" row
    for i, row in enumerate(rows):
        if is_free_row(row[0]):
            continue
        rows[i] = [re.sub(r"\s+", "~", cell) for cell in row]

    # Insert BOM (~) in empty cells
    BOM = "~"
    rows = [[cell if cell else BOM for cell in row] for row in rows]

    # Determine if last row is Free
    is_free = is_free_row(rows[-1][0]) if rows else False

    # Add \glll or similar to first non-Free row
    num_non_free = len(rows) - 1 if is_free else len(rows)
    for row in rows:
        if not is_free_row(row[0]):
            row[0] = r"\g" + "l" * num_non_free + " " + row[0]
            break

    # Handle Free line formatting
    if is_free:
        cell = rows[-1][0].strip()
        if cell.lower().startswith("free "):
            rows[-1][0] = r"\glt \textbf{Free} " + cell[5:]
        elif cell.startswith("'") and cell.endswith("'"):
            rows[-1][0] = r"\glt `" + cell.strip("'") + "'"

    # Detect FLEx-style row labels
    has_labels = any(row[0].strip().lower() in FLEX_ROW_LABELS for row in rows)
    print(f"Has FLEx labels: {has_labels}")
    if has_labels:
        for row in rows:
            if not is_free_row(row[0]) and not row[0].startswith(r"\glt"):
                m = re.match(r"^(\\g[l]+)(.+)$", row[0])
                if m:
                    row[0] = f"{m.group(1)}\\textbf{{{m.group(2).lstrip()}}}"
                else:
                    row[0] = r"\textbf{" + row[0].strip() + "}"

    # Build LaTeX lines
    interlinear_lines = [
        " ".join(row) + (r"\\" if i != len(rows) - 1 else "")
        for i, row in enumerate(rows)
    ]

    if len(interlinear_lines) > 1:
        interlinear_lines.insert(-1, r"\vspace{14pt} %Add 14 pt vertical space between interlinear blocks.")

    interlinear_block = (
        "{%\n"
        "%Suggestion: Consider definining a global linespacing variable and then insert it in the \\lineskip and \\vspace commands below instead of 14pt.\n"
        "  \\setlength{\\lineskiplimit}{1pt} % Anytime there's less vertical space than 1pt, trigger the line immediately below.\n"
        "  \\setlength{\\lineskip}{6pt} % 6pt pt vertical space between interlinear blocks.\n"
        "  \\vspace{6pt} % Add 6 pt vertical space before interlinear blocks.\n"
        + "\n".join(interlinear_lines) + "\n"
        "}%"  # End of group
    )

    if exType == "newList":
        final_output = (
            r"%\vspace{12pt} %add 12pt vertical space" + "\n"
            r"\begin{exe}" + "\n"
            r"\ex%\label{name} %for referencing the list elsewhere" + "\n"
            + ex_title[1:] + "\n"
            + ex_subtitle + "\n"
            r"%\vspace{6pt} %Add 6 pt vertical space between title and blocks." + "\n"
            r"\begin{xlist}" + "\n"
            r"\begin{minipage}{\linewidth}" + "\n"
            r"\ex%\label{name} %for referencing this item elsewhere" + "\n"
            + interlinear_block + "\n"
            + txt_ref + "\n"
            r"\end{minipage}\\" + "\n\n"
            r"%Paste more items to this list example here..." + "\n\n"
            r"\end{xlist}" + "\n"
            r"\end{exe}" + "\n\n"
        )

    elif exType == "existingList":
        final_output = (
            r"%\vspace{6pt} %add 6pt vertical space" + "\n"
            r"\begin{minipage}{\linewidth}" + "\n"
            r"\ex%\label{name} %for referencing this item elsewhere" + "\n"
            r"%\vspace{6pt} %Add 6 pt vertical space between title and blocks." + "\n"
            + interlinear_block + "\n"
            + txt_ref + "\n"
            r"\end{minipage}\\" + "\n\n"
            r"%Paste more items to this list example here..." + "\n\n"
        )

    else: # Single example code
        final_output = (
            r"%\vspace{6pt} %add 8pt vertical space" + "\n"
            r"\begin{minipage}{\linewidth}\begin{exe}" + "\n"
            r"\ex%\label{name} %for referencing this elsewhere" + "\n"
            + ex_title + "\n"
            + ex_subtitle + "\n"
            r"%\vspace{6pt} %Add 6 pt vertical space between title and blocks." + "\n"
            + interlinear_block + "\n"
            + txt_ref + "\n"
            r"\end{exe}\end{minipage}\\" + "\n"
        )

    return final_output


def import_FLEx_TSV(raw_text):
    if not raw_text:
        return []

    # Parse clipboard as TSV
    reader = csv.reader(io.StringIO(raw_text), delimiter="\t")
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    # REMOVE THIS SECTION - it's interfering:
    # # Remove the first column if it looks like a number
    # for i, row in enumerate(rows):
    #     if row and row[0].strip().isdigit():
    #         rows[i] = row[1:]

    # --- New period merge logic: ["", "X", ".X"] -> ["X.X", "", ""] ---
    for row in rows:
        i = 0
        while i < len(row) - 2:
            if row[i] == "" and row[i+1] and row[i+2].startswith("."):
                row[i] = row[i+1] + row[i+2]
                row[i+1] = ""
                row[i+2] = ""
                i += 3
            else:
                i += 1

    # --- Remove columns that are blank in ALL rows ---
    if rows:
        # Pad all rows to the same length first
        max_cols = max(len(row) for row in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")
        
        # Find indices of columns that are blank in ALL rows
        blank_col_indices = []
        for col in range(max_cols):
            if all(not row[col].strip() for row in rows):  # Empty in ALL rows
                blank_col_indices.append(col)
        
        # Remove these columns from all rows (right to left to keep indices valid)
        for col in reversed(blank_col_indices):
            for row in rows:
                del row[col]

    # 1. If there's a number in column 1, shift "Free" cell to col 2, then delete col 1 (all but last row)
    free_row = None
    other_rows = []
    for row in rows:
        if row and row[0].strip().startswith("Free"):
            free_row = row
        else:
            other_rows.append(row)
    rows = other_rows + ([free_row] if free_row else [])

    # Check if we need to delete col 1 (numbered)
    if rows and re.match(r"^\d+(\.\d+)?$", rows[0][0].strip()):
        # First row starts with a number, so delete column 0 from all non-Free rows
        for row in rows:
            # Skip the Free row
            if row and row[0].strip().startswith("Free"):
                continue
            
            # For all other rows, shift "Free" cell to col 2 if present
            for i, cell in enumerate(row):
                if cell.strip().startswith("Free"):
                    if len(row) > 1:
                        row[1] = cell
                        row[i] = ""
                    break
            
            # Now delete column 0 for this row
            del row[0]

    # 3. Trim whitespace from all cells
    rows = [[cell.strip() for cell in row] for row in rows]

    # --- New functionality: Copy morpheme break markers to Lex. Gloss row ---
    # Define morpheme break markers
    morpheme_markers = MORPHEME_MARKERS

    # Find the Morphemes and Lex. Gloss rows
    morphemes_row = None
    lex_gloss_row = None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "morphemes":
            morphemes_row = i
        elif row and row[0].strip().lower() == "lex. gloss":
            lex_gloss_row = i

    # If both rows are found, copy markers
    if morphemes_row is not None and lex_gloss_row is not None:
        morphemes = rows[morphemes_row]
        lex_gloss = rows[lex_gloss_row]
        for j in range(1, min(len(morphemes), len(lex_gloss))):  # Skip column 0 (label)
            morpheme_cell = morphemes[j].strip()
            lex_gloss_cell = lex_gloss[j].strip()
            # Check if the morpheme cell starts with a marker
            if morpheme_cell and morpheme_cell[0] in morpheme_markers:
                rows[lex_gloss_row][j] = morpheme_cell[0] + lex_gloss_cell

    return rows

def is_free_row(cell):
    stripped = cell.strip()
    return (
        stripped.lower().startswith("free ") or
        (stripped.startswith("'") and stripped.endswith("'"))
    )


def paste_from_clipboard():
    try:
        data = pyperclip.paste()
        if not data or not any(cell.strip() for cell in data.splitlines()):
            messagebox.showwarning("Clipboard Warning", "Clipboard empty or not correctly formatted.")
            return
        # Process clipboard data through import_FLEx_TSV
        rows = import_FLEx_TSV(data)
        # Convert rows back to TSV for display
        processed_tsv = "\n".join(["\t".join(row) for row in rows])
        output_text.config(state='normal')
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, processed_tsv)
        output_text.config(state='disabled')
    except Exception as e:
        messagebox.showerror("Clipboard Error", f"Could not paste from clipboard:\n{e}")

def export_rows_as_tsv(rows):
    BOM = "\uFEFF"
    def safe_cell(cell):
        if cell and cell[0] in "=+-@":
            return BOM + cell
        return cell
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return output.getvalue()

def open_manual_entry_dialog(parent):
    # Step 1: Prompt for source sentence
    src_line = simpledialog.askstring(
        "Manual Entry",
        "Type or paste a source-language sentence (no glosses or translation):",
        parent=parent
    )
    if not src_line:
        return

    # Step 2: Split into cells, add "Word" at start
    cells = re.split(r'[ \t]+', src_line.strip())
    tsv_row = ["Word"] + cells

    # Step 3: Create the data sheet dialog
    ManualEntrySheet(parent, tsv_row)

class ManualEntrySheet(tk.Toplevel):
    def __init__(self, parent, first_row):
        super().__init__(parent)
        self.title("Manual Interlinear Entry")
        self.grab_set()
        self.resizable(True, True)

        self.rows = [
            first_row,
            ["Morphemes"] + [""] * (len(first_row) - 1),
            ["Lex. Gloss"] + [""] * (len(first_row) - 1),
            ["Word Gloss"] + [""] * (len(first_row) - 1)
        ]
        self.entries = []
        self.sheet_widgets = []
        self.controls_widgets = []
        self.build_sheet()
        self.build_controls()

    def build_sheet(self):
        # Only called once at init, or if you ever want to fully redraw the grid
        for widget in getattr(self, 'sheet_widgets', []):
            widget.destroy()
        self.sheet_widgets = []
        self.entries = []

        for r, row in enumerate(self.rows):
            row_entries = []
            for c, val in enumerate(row):
                e = tk.Entry(self, width=12)
                e.grid(row=r, column=c, padx=1, pady=1)
                e.insert(0, val)
                row_entries.append(e)
                self.sheet_widgets.append(e)
            self.entries.append(row_entries)

    def build_controls(self):
        # Preserve Free Translation value
        free_val = ""
        if hasattr(self, "free_entry"):
            free_val = self.free_entry.get()

        # Remove previous controls if they exist
        if hasattr(self, 'controls_widgets'):
            for widget in self.controls_widgets:
                widget.destroy()
        self.controls_widgets = []

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(self.rows), column=0, columnspan=len(self.rows[0]), pady=5)
        self.controls_widgets.append(btn_frame)
        tk.Button(btn_frame, text="Add Row", command=self.add_row).pack(side="left")
        tk.Button(btn_frame, text="Delete Row", command=self.delete_row_and_cleanup).pack(side="left")
        tk.Button(btn_frame, text="Split Cell", command=self.split_cell_and_cleanup).pack(side="left")

        # Free Translation
        ft_frame = tk.Frame(self)
        ft_frame.grid(row=len(self.rows)+1, column=0, columnspan=len(self.rows[0]), pady=5)
        self.controls_widgets.append(ft_frame)
        tk.Label(ft_frame, text="Free Translation:").pack(side="left")
        self.free_entry = tk.Entry(ft_frame, width=40)
        self.free_entry.pack(side="left")
        self.free_entry.insert(0, free_val)  # Restore previous value

        # Done/Cancel
        action_frame = tk.Frame(self)
        action_frame.grid(row=len(self.rows)+2, column=0, columnspan=len(self.rows[0]), pady=10)
        self.controls_widgets.append(action_frame)
        tk.Button(action_frame, text="Done", command=self.on_done).pack(side="left", padx=10)
        tk.Button(action_frame, text="Cancel", command=self.destroy).pack(side="left", padx=10)

    def sync_entries_to_rows(self):
        # Sync Entry values to self.rows
        for r, row_entries in enumerate(self.entries):
            for c, entry in enumerate(row_entries):
                if r < len(self.rows) and c < len(self.rows[r]):
                    self.rows[r][c] = entry.get()

    def add_row(self):
        self.sync_entries_to_rows()
        new_row = [""] * len(self.rows[0])
        self.rows.append(new_row)
        # Add Entry widgets for the new row only
        r = len(self.rows) - 1
        row_entries = []
        for c, val in enumerate(new_row):
            e = tk.Entry(self, width=12)
            e.grid(row=r, column=c, padx=1, pady=1)
            row_entries.append(e)
            self.sheet_widgets.append(e)
        self.entries.append(row_entries)
        self.build_controls()

    def delete_row_and_cleanup(self):
        self.sync_entries_to_rows()
        # Find the currently focused entry and its row
        for r, row in enumerate(self.entries):
            for entry in row:
                if entry == self.focus_get():
                    # Don't allow deleting if only one row left or if it's the first row ("Word")
                    if len(self.rows) > 1 and r != 0:
                        # Destroy Entry widgets for this row
                        for e in self.entries[r]:
                            e.destroy()
                        del self.entries[r]
                        del self.rows[r]
                    self.cleanup_empty()
                    self.build_controls()
                    return

    def split_cell(self):
        # Find focused entry
        for r, row in enumerate(self.entries):
            for c, entry in enumerate(row):
                if entry == self.focus_get():
                    val = entry.get()
                    idx = entry.index(tk.INSERT)
                    left, right = val[:idx], val[idx:]
                    # Ensure right column exists
                    if c+1 >= len(row):
                        # Add a new column to all rows
                        for row_entries, row_data in zip(self.entries, self.rows):
                            e = tk.Entry(self, width=12)
                            e.grid(row=self.entries.index(row_entries), column=len(row_entries), padx=1, pady=1)
                            row_entries.append(e)
                            self.sheet_widgets.append(e)
                            row_data.append("")
                    # Now split the cell
                    if not row[c+1].get():
                        row[c].delete(0, tk.END)
                        row[c].insert(0, left)
                        row[c+1].delete(0, tk.END)
                        row[c+1].insert(0, right)
                    else:
                        # Add a new column to all rows
                        for row_entries, row_data in zip(self.entries, self.rows):
                            e = tk.Entry(self, width=12)
                            e.grid(row=self.entries.index(row_entries), column=len(row_entries), padx=1, pady=1)
                            row_entries.append(e)
                            self.sheet_widgets.append(e)
                            row_data.append("")
                        row = self.entries[r]
                        row[c+1].delete(0, tk.END)
                        row[c+1].insert(0, right)
                        row[c].delete(0, tk.END)
                        row[c].insert(0, left)
                    return

    def split_cell_and_cleanup(self):
        self.sync_entries_to_rows()
        self.split_cell()
        self.cleanup_empty()
        self.build_controls()

    def cleanup_empty(self):
        # Remove empty rows (except the last, which is the Free Translation row)
        self.sync_entries_to_rows()
        self.rows = [row for row in self.rows if any(cell.strip() for cell in row)]
        # Remove empty columns
        if self.rows:
            num_cols = max(len(row) for row in self.rows)
            blank_col_indices = []
            for col in range(num_cols):
                if all((len(row) <= col or not row[col].strip()) for row in self.rows):
                    blank_col_indices.append(col)
            for col in reversed(blank_col_indices):
                for row in self.rows:
                    if len(row) > col:
                        del row[col]
                for row_entries in self.entries:
                    if len(row_entries) > col:
                        row_entries[col].destroy()
                        del row_entries[col]

    def on_done(self):
        self.cleanup_empty()
        # Gather data
        data = []
        for row in self.entries:
            data.append([e.get() for e in row])

        # Add Free Translation row
        free_val = ""
        if hasattr(self, "free_entry"):
            free_val = self.free_entry.get()
        free_row = ["Free " + free_val]
        data.append(free_row)

        # --- Remove empty rows ---
        data = [row for row in data if any(cell.strip() for cell in row)]

        # --- Remove empty columns ---
        if data:
            num_cols = max(len(row) for row in data)
            blank_col_indices = []
            for col in range(num_cols):
                if all((len(row) <= col or not row[col].strip()) for row in data):
                    blank_col_indices.append(col)
            for col in reversed(blank_col_indices):
                for row in data:
                    if len(row) > col:
                        del row[col]

        # Convert to TSV and save to main window textbox
        tsv = "\n".join(["\t".join(row) for row in data])
        output_text.config(state='normal')
        output_text.delete("1.0", tk.END)
        output_text.insert(tk.END, tsv)
        output_text.config(state='disabled')
        self.destroy()

def get_working_data():
    return output_text.get("1.0", tk.END).strip()

def is_morphemic_version(row, ref_row):
    # Collapse ref_row cells into a single reference string
    ref_string = "".join(cell.strip() for cell in ref_row if cell.strip())
    candidate_string = "".join(cell.strip() for cell in row if cell.strip())

    # Remove morpheme boundaries from candidate
    morpheme_stripped = re.sub(r"[=.\-]", "", candidate_string)

    # Compare character overlap
    match_count = sum(1 for c in ref_string if c in morpheme_stripped)
    match_ratio = match_count / max(len(ref_string), 1)

    return match_ratio > 0.6  # Tune threshold as needed

def rows_to_xlingpaper_interlinear_dom(rows):
    if not rows:
        return ET.Element("interlinear")

    # Split into lineGroup rows and free row
    if rows[-1] and (rows[-1][0].startswith("Free ") or (rows[-1][0].startswith("'") and rows[-1][0].endswith("'"))):
        line_rows = rows[:-1]
        free_row = rows[-1]
    else:
        line_rows = rows
        free_row = None

    interlinear_elem = ET.Element("interlinear")
    lineGroup_elem = ET.SubElement(interlinear_elem, "lineGroup")

    first_row = None  # To store the first langData row

    for row in line_rows:
        if not row or all(not cell.strip() for cell in row):
            continue  # Skip empty rows

        # Determine row type
        if first_row is None:
            use_langData = True
            first_row = row
        else:
            use_langData = False # is_morphemic_version(row, first_row) # Fix this function later for a more precise check

        line_elem = ET.SubElement(lineGroup_elem, "line")
        remove_labels = remove_labels_var.get()

        for i, cell in enumerate(row):
            wrd_elem = ET.SubElement(line_elem, "wrd")
            if use_langData:
                langData_elem = ET.SubElement(wrd_elem, "langData", {"lang": "lVernacular"})
                if i == 0 and not remove_labels:
                    obj_elem = ET.Element("object", {"type": "tBold"})
                    obj_elem.text = xml.sax.saxutils.escape(cell)
                    langData_elem.append(obj_elem)
                else:
                    langData_elem.text = xml.sax.saxutils.escape(cell)
            else:
                gloss_elem = ET.SubElement(wrd_elem, "gloss", {"lang": "lGloss"})
                if i == 0 and not remove_labels:
                    obj_elem = ET.Element("object", {"type": "tBold"})
                    obj_elem.text = xml.sax.saxutils.escape(cell)
                    gloss_elem.append(obj_elem)
                else:
                    gloss_elem.text = xml.sax.saxutils.escape(cell)

    # Add <free> element if needed
    if free_row:
        free_text = ' '.join(free_row)
        free_elem = ET.SubElement(interlinear_elem, "free", {"lang": "en-free"})
        if free_text.startswith("Free "):
            obj = ET.Element("object", {"type": "tBold"})
            obj.text = "Free"
            rest = free_text[4:].strip()
            free_elem.append(obj)
            obj.tail = " " + rest if rest else ""
        else:
            free_elem.text = xml.sax.saxutils.escape(free_text.strip())

    return interlinear_elem

def pretty_print_xml(elem):
    """Pretty-print from an ElementTree.Element."""
    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = xml.dom.minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent="  ")
    # Remove XML declaration if present
    pretty = pretty.replace('<?xml version="1.0" ?>\n', '')
    return pretty

def pretty_xml(xml_string, indent="  "):
    """Pretty-print from an XML string."""
    # Pretty-print using minidom
    pretty = minidom.parseString(xml_string).toprettyxml(indent=indent) # Use 6 spaces for indentation
    # Remove the XML declaration at the top, if present
    pretty = re.sub(r'^<\?xml[^>]*\?>\s*', '', pretty)
    return pretty

def xlingpaper_single_example(rows):
    interlinear_elem = rows_to_xlingpaper_interlinear_dom(rows)
    example_elem = ET.Element("example")
    example_elem.append(interlinear_elem)
    return pretty_print_xml(example_elem)

def xlingpaper_new_list(rows):
    interlinear_elem = rows_to_xlingpaper_interlinear_dom(rows)
    interlinear_elem.tag = "listInterlinear"
    example_elem = ET.Element("example")
    example_elem.append(interlinear_elem)
    return pretty_print_xml(example_elem)

def xlingpaper_existing_list(rows):
    elem = rows_to_xlingpaper_interlinear_dom(rows)
    elem.tag = "listInterlinear"
    return pretty_print_xml(elem)


def tsv_to_html_table(tsv_rows, copy_to_clipboard=False):
    def escape_html(text):
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))

    # Prepare regex pattern to find all labels (case-insensitive)
    pattern = re.compile(
        "(" + "|".join(re.escape(label) for label in FLEX_ROW_LABELS) + ")",
        re.IGNORECASE
    )

    def bold_labels_in_text(text):
        escaped_text = escape_html(text)

        def repl(m):
            return f"<b>{m.group(0)}</b>"

        return pattern.sub(repl, escaped_text)

    # Separate the special "free" or single-quoted row(s) to move it/them last
    normal_rows = []
    special_rows = []
    for row in tsv_rows:
        if not row:
            normal_rows.append(row)
            continue

        first_cell = str(row[0]).strip()
        first_cell_lower = first_cell.lower()

        # Check conditions:
        contains_free = "free" in first_cell_lower
        is_single_quoted = bool(re.match(r"^'.*'$", first_cell))

        if contains_free or is_single_quoted:
            special_rows.append(row)
        else:
            normal_rows.append(row)

    # Determine max columns count from normal rows (fallback to 1)
    max_cols = max((len(row) for row in normal_rows if row), default=1)

    html = [
        '<table border="0" cellspacing="0" cellpadding="10" style="border-collapse:collapse;">'
    ]

    # Render normal rows
    for row in normal_rows:
        html.append('<tr>')
        for cell in row:
            cell_text = str(cell)
            cell_with_bold = bold_labels_in_text(cell_text)
            html.append(f'<td>{cell_with_bold}</td>')
        html.append('</tr>')

    # Render special rows last, each as one cell with colspan=max_cols
    for row in special_rows:
        first_cell_text = str(row[0])
        cell_with_bold = bold_labels_in_text(first_cell_text)
        html.append(f'<tr><td colspan="{max_cols}">{cell_with_bold}</td></tr>')

    html.append('</table>')
    html_string = "\n".join(html)

    if copy_to_clipboard:
        copy_html_to_clipboard(html_string)  # You provide this

    return html_string


def copy_html_to_clipboard(html):
    copy_to_clipboard(html, mime_type='text/html')

def copy_to_clipboard(data, mime_type='text/plain'):
    """
    Copy data to the clipboard in the specified MIME type.
    This function is a placeholder for platform-specific implementations.
    """
    try:
        pyperclip.copy(data)
        #print(f"Copied data to clipboard as {mime_type}")
    except Exception as e:
        print(f"Failed to copy data to clipboard: {e}")
#    platform = sys.platform
#
#    if platform.startswith('win'):
#        copy_windows(data, mime_type)
#    elif platform == 'darwin':
#        copy_macos(data, mime_type)
#    elif platform.startswith('linux'):
#        copy_linux(data, mime_type)
#    else:
#        raise NotImplementedError(f"Unsupported platform: {platform}")

#def copy_windows(data, mime_type):
#    try:
#        import win32clipboard
#
#        win32clipboard.OpenClipboard()
#        win32clipboard.EmptyClipboard()
#
#        if mime_type == 'text/html':
#            CF_HTML = win32clipboard.RegisterClipboardFormat("HTML Format")
#            clipboard_data = create_cf_html(data).encode('utf-8')
#            win32clipboard.SetClipboardData(CF_HTML, clipboard_data)
#        else:
#            # default to plain text
#            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, data)
#        win32clipboard.CloseClipboard()
#
#    except ImportError:
#        print("pywin32 is required on Windows for this operation.")
#    except Exception as e:
#        print(f"Failed to copy data to clipboard on Windows: {e}")

def create_cf_html(html):
    # Minimal HTML clipboard wrapper per MSDN spec
    start_html = 0
    end_html = len(html)
    start_fragment = html.find("<body>")
    if start_fragment == -1:
        start_fragment = 0
    else:
        start_fragment += len("<body>")
    end_fragment = html.find("</body>")
    if end_fragment == -1:
        end_fragment = len(html)

    header = (
        "Version:0.9\r\n"
        f"StartHTML:{start_html:09d}\r\n"
        f"EndHTML:{end_html:09d}\r\n"
        f"StartFragment:{start_fragment:09d}\r\n"
        f"EndFragment:{end_fragment:09d}\r\n"
    )
    return header + html

#def copy_macos(data, mime_type):
#    if mime_type == 'text/html':
#        try:
#            p = subprocess.Popen(['pbcopy-html'], stdin=subprocess.PIPE)
#            p.communicate(input=data.encode('utf-8'))
#        except Exception as e:
#            print(f"Failed to copy HTML clipboard on macOS: {e}")
#    else:
#        try:
#            pyperclip.copy(data)
#        except Exception as e:
#            print(f"Failed to copy to clipboard on macOS: {e}")

#def copy_linux(data, mime_type):
    # Linux is tricky; many distros don't handle html mime on clipboard out of the box.
    # You could try xclip or xsel with appropriate args, but here we fallback to plain text.
#    try:
#        subprocess.run(['xclip', '-selection', 'clipboard'], input=data.encode('utf-8'))
#    except Exception as e:
#        print(f"Failed to copy clipboard data on Linux: {e}")

def convert_rows_to_column_equations(rows):
    """
    Convert rows (list of lists) to Word MathML where each COLUMN is an
    equation stacking all its rows vertically,
    except the last row if it starts with "Free ",
    which is output as a separate plain text line after the equations.

    Adds:
    - Left-align all cells in arrays.
    - Font "Charis SIL" for all cells.
    - Bold font for the first equation only.
    """

    NS_MATH = 'http://schemas.openxmlformats.org/officeDocument/2006/math'

    def esc(text):
        return xml.sax.saxutils.escape(text)

    if not rows:
        return ""

    # Check if last row starts with "Free "
    free_row = None
    if rows[-1] and rows[-1][0].startswith("Free "):
        free_row = rows[-1]
        rows = rows[:-1]

    num_cols = max(len(row) for row in rows) if rows else 0
    num_rows = len(rows)

    column_equations = []

    for col_idx in range(num_cols):
        array_rows_xml = ""
        for row_idx in range(num_rows):
            cell_text = rows[row_idx][col_idx] if col_idx < len(rows[row_idx]) else ""
            cell_text_escaped = xml.sax.saxutils.escape(cell_text)

            # Build <m:rPr> with font "Charis SIL"
            # Add <m:b/> if this is the FIRST equation (col_idx == 0)
            rpr_bold = '<m:b/>' if col_idx == 0 else ''
            rpr_xml = (
                f"<m:rPr>"
                f"{rpr_bold}"
                f'<m:latin m:val="Charis SIL"/>'
                f'<m:ea m:val="Charis SIL"/>'
                f'<m:cs m:val="Charis SIL"/>'
                f"</m:rPr>"
            )

            array_rows_xml += (
                f"<m:arrayRow>"
                f"<m:r>{rpr_xml}<m:t>{cell_text_escaped}</m:t></m:r>"
                f"</m:arrayRow>"
            )

        array_xml = (
            f'<m:array>'
            f'<m:arrayPr>'
            f'<m:baseJc m:val="left"/>'  # Left align instead of center
            f'<m:colBandSz m:val="1"/>'
            f'<m:rowBandSz m:val="1"/>'
            f'</m:arrayPr>'
            f'<m:tblStyleRowBandSize m:val="1"/>'
            f'<m:tblStyleColBandSize m:val="1"/>'
            f'{array_rows_xml}'
            f'</m:array>'
        )

        equation_xml = (
            f'<w:r>'
            f'<m:oMath>'
            f'{array_xml}'
            f'</m:oMath>'
            f'</w:r>'
        )
        column_equations.append(equation_xml)

    # Join column equations with two spaces
    equations_line = ("  ").join(column_equations)

    # Prepare free line as plain text if exists
    free_line = ""
    if free_row:
        free_line = " ".join(xml.sax.saxutils.escape(cell.strip()) for cell in free_row).strip()

    return [equations_line, free_line]

def open_word_with_mathml(equations, free_line=None):
    # Allow passing a list [equations, free_line]
    if isinstance(equations, list) and free_line is None:
        equations, free_line = equations

    instruction = '''
    <w:p>
      <w:r>
        <w:rPr><w:b/></w:rPr>
        <w:t>Copy the following into your document.</w:t>
      </w:r>
    </w:p>
    '''

    equations_paragraph = f'''
    <w:p>
      {equations}
    </w:p>
    '''

    free_paragraph = f'''
    <w:p>
      <w:r>
        <w:t>{xml.sax.saxutils.escape(free_line)}</w:t>
      </w:r>
    </w:p>
    ''' if free_line else ''

    word_xml = f'''<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:ve="http://schemas.openxmlformats.org/markup-compatibility/2006"
  xmlns:o="urn:schemas-microsoft-com:office:office"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
  xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
  xmlns:w10="urn:schemas-microsoft-com:office:word"
  xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml">
  <w:body>
    {instruction}
    {equations_paragraph}
    {free_paragraph}
    <w:sectPr/>
  </w:body>
</w:document>
'''
    word_xml = minify_xml(wrap_flat_opc(word_xml))

    import tempfile, sys, os, subprocess
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8-sig", newline="\r\n") as tmp:
        tmp.write(word_xml)
        tmp_path = tmp.name

    print(f"Word XML file saved at: {tmp_path}")  # <-- This will print the file path

    if sys.platform.startswith("win"):
        os.startfile(tmp_path)
    elif sys.platform == "darwin":
        subprocess.run(['open', '-a', 'Microsoft Word', tmp_path])
    else:
        print("Automatic opening is not supported on this OS.")
        print(f"File saved at: {tmp_path}")

def wrap_flat_opc(document_xml):
    # Pretty-print the document XML
    document_xml = pretty_xml(document_xml)
    # Minimal styles and rels (expand as needed)
    styles_xml = '''
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rsid w:val="00000000"/>
  </w:style>
</w:styles>
'''.strip()

    rels_xml = '''
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
'''.strip()

    doc_rels_xml = '''
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
'''.strip()

    flat_opc = f'''<?xml version="1.0" encoding="utf-8"?>
<?mso-application  progid="Word.Document"?>
<pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage"
             xmlns="http://www.w3.org/1999/XSL/Format"
             xmlns:v="urn:schemas-microsoft-com:vml">
  <pkg:part pkg:name="/_rels/.rels" pkg:contentType="application/vnd.openxmlformats-package.relationships+xml" pkg:padding="512">
    <pkg:xmlData>
      {pretty_xml(rels_xml)}
    </pkg:xmlData>
  </pkg:part>
  <pkg:part pkg:name="/word/_rels/document.xml.rels" pkg:contentType="application/vnd.openxmlformats-package.relationships+xml" pkg:padding="256">
    <pkg:xmlData>
      {pretty_xml(doc_rels_xml)}
    </pkg:xmlData>
  </pkg:part>
  <pkg:part pkg:name="/word/document.xml" pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml">
    <pkg:xmlData>
{document_xml}
    </pkg:xmlData>
  </pkg:part>
  <pkg:part pkg:name="/word/styles.xml" pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml">
    <pkg:xmlData>
      {pretty_xml(styles_xml)}
    </pkg:xmlData>
  </pkg:part>
</pkg:package>
'''
    return flat_opc

# --- New function to remove extra XML declarations ---

def remove_extra_xml_declarations(xml_string):
    # Keep only the first <?xml ...?> declaration
    matches = list(re.finditer(r'<\?xml[^>]*\?>', xml_string))
    if not matches:
        return xml_string
    first = matches[0]
    # Remove all others
    xml_string = xml_string[:first.end()] + re.sub(r'<\?xml[^>]*\?>', '', xml_string[first.end():])
    return xml_string

def minify_xml(xml_string):
    """
    Minify XML by removing all unnecessary whitespace, newlines, and indentation between tags.
    """
    # Remove spaces between tags
    xml_string = re.sub(r'>\s+<', '><', xml_string)
    # Remove leading/trailing whitespace
    xml_string = xml_string.strip()
    return xml_string

# --- Collapse morpheme breaks function ---

def collapse_morpheme_breaks(rows):
    """
    Collapse morpheme break markers into preceding cells and delete blank cells in identified columns.
    
    Args:
        rows: List of lists containing TSV row data.
    
    Returns:
        Modified rows list with collapsed morpheme breaks.
    """
    if not rows:
        return rows

    # Step 1: Identify columns with morpheme break markers
    columns_with_markers = set()
    for row in rows:
        for col_idx, cell in enumerate(row):
            if cell.strip() and cell.strip()[0] in MORPHEME_MARKERS:
                columns_with_markers.add(col_idx)

    # Step 2: Collapse morpheme breaks
    for row in rows:
        for col_idx in sorted(columns_with_markers, reverse=True):  # Process columns right to left
            if col_idx > 0 and col_idx < len(row):  # Ensure valid indices
                current_cell = row[col_idx].strip()
                preceding_cell = row[col_idx - 1].strip() if col_idx - 1 < len(row) else ""

                if current_cell.startswith(tuple(MORPHEME_MARKERS)):
                    # Move marker to the end of the preceding cell
                    row[col_idx - 1] = preceding_cell + current_cell
                    row[col_idx] = ""  # Clear the current cell

    # Step 3: Remove blank cells in identified columns
    for row in rows:
        row[:] = [cell for idx, cell in enumerate(row) if cell.strip() or idx not in columns_with_markers]

    return rows

def on_convert_click():
    selected = app_var.get()
    latex_formatting = latex_option_var.get()
    print(f"Running on_convert_click()")
    print(f"latex_formatting: {latex_formatting} type: {type(latex_formatting)}")
    try:
        tsv_text = get_working_data()
        rows = [line.split('\t') for line in tsv_text.splitlines() if line.strip()]
        remove_labels = remove_labels_var.get()
        remove_column_breaks = remove_column_breaks_var.get()
        if remove_labels:
            rows = process_labeled_rows(rows)
            print("Removing labels...")
            print(f"Rows after processing labels: {rows}")
        if remove_column_breaks:
            print("Removing column breaks...")
            rows = collapse_morpheme_breaks(rows)
            print(f"Rows after processing column breaks: {rows}")
        xling_warning = (
            "Warning, XLingPaper does not allow you to paste code into the graphical editor. "
            "You will have to edit the source code. Click where you want to insert the text in the graphical viewer, "
            'and then go to "view" and "2 XML Source". Be very careful! If you do not understand XML well enough to put code in the correct place, '
            "you could mess up your document so that XLingPaper can no longer read it. Read a basic XML tutorial first before trying to use this tool if you're new to it. Also ctrl+x / Edit > Undo is your friend."
        )
        if "MIT interlinear package" in selected:
            reminder_label.config(
                text=r"Reminder: Remember to download the MIT interlinear package, include it in your LaTeX project folder, and include a \\usepackage{interlinear} statement in the preamble. You may also need to specify a font that can handle special IPA characters. Additionally, using predefined styles \extitle, \exsubtitle, and \txtref (checkbox above) can help with consistent formatting, but it will only work if you also define them in your document preamble.",
                fg='red',
                wraplength=600,
                justify="left",
                cursor="hand2"
            )
            reminder_label.pack(pady=5)
            reminder_label.bind(
                "<Button-1>",
                lambda e: webbrowser.open_new("https://ctan.math.washington.edu/tex-archive/macros/latex/contrib/interlinear/interlinear.sty")
            )
            exType = "existingList" if "Add to Existing List Example" in selected else "newList" if "New List Example" in selected else "single"
            result = convert_clipboard_for_mit(rows, latex_formatting, exType)
            mime_type = 'text/plain'
        elif "Spreadsheet App" in selected:
            reminder_label.pack_forget()
            result = export_rows_as_tsv(rows)
            mime_type = 'text/tab-separated-values'
        elif "XLingPaper Single Interlinear Example" in selected:
            reminder_label.config(
                text=xling_warning,
                fg='red',
                wraplength=600,
                justify="left"
            )
            reminder_label.pack(pady=5)
            result = xlingpaper_single_example(rows)
            mime_type = 'text/xml'
        elif "XLingPaper List Interlinear - Create New List" in selected:
            reminder_label.config(
                text=xling_warning,
                fg='red',
                wraplength=600,
                justify="left"
            )
            reminder_label.pack(pady=5)
            result = xlingpaper_new_list(rows)
            mime_type = 'text/xml'
        elif "XLingPaper List Interlinear - Add Item to Existing List" in selected:
            reminder_label.config(
                text=xling_warning,
                fg='red',
                wraplength=600,
                justify="left"
            )
            reminder_label.pack(pady=5)
            result = xlingpaper_existing_list(rows)
            mime_type = 'text/xml'
        elif "HTML Table (for web display)" in selected:
            reminder_label.pack_forget()
            result = tsv_to_html_table(rows)
            mime_type = 'text/html'
        
        #elif "Word MathML - Column Equations" in selected:
        #    reminder_label.config(
        #        text="This will open a new word document with your formatted interlinear example. You can copy it, close the new doc, and paste it in your paper.",
        #        fg='red',
        #        wraplength=600,
        #        justify="left"
        #    )
        #    reminder_label.pack(pady=5)
        #    result = ""
        #    equations, free_line = convert_rows_to_column_equations(rows)
        #    open_word_with_mathml(equations, free_line if free_line else "")
        #    mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.math'
        else:
            reminder_label.pack_forget()
            result = ""
            mime_type = 'text/plain'

        if result:
            output_text.config(state='disabled')
            #pyperclip.copy(result)
            copy_to_clipboard(result, mime_type)
        elif result == "":
            pass
        else:
            messagebox.showwarning("Empty Clipboard", "Clipboard is empty or contains invalid text.")
    except Exception as e:
        messagebox.showerror("Conversion Error", f"An error occurred during conversion:\n\n{e}")

# --- GUI setup ---
root = tk.Tk()
root.title("Clipboard Converter")
root.geometry("700x800")

# Reminder label (initially hidden)
reminder_label = tk.Label(root, text="", fg='red', justify="left")

# Manual button (positioned above the textbox)
manual_button = tk.Button(root, text="Manually Enter Interlinear Example...", command=lambda: open_manual_entry_dialog(root))
manual_button.pack(pady=5, anchor="ne")  # Positioned above the textbox

# Output textbox
output_text = tk.Text(root, wrap="word", height=15, width=80)
try:
    output_text.insert(tk.END, pyperclip.paste())
except Exception:
    pass
output_text.config(state='disabled')
output_text.pack(pady=10)

# Dropdown for target application
app_var = tk.StringVar()
dropdown = ttk.Combobox(root, textvariable=app_var, state="readonly", width=60)
dropdown['values'] = [
    "Spreadsheet App (Google Sheets, Excel, LibreOffice Calc)",
    "---------------------------------------------------",
    "LaTeX - MIT interlinear package - Single Example",
    "LaTeX - MIT interlinear package - New List Example",
    "LaTeX - MIT interlinear package - Add to Existing List Example",
    "---------------------------------------------------",
    #To do: troubleshoot and fix these options (since pasting and conversion logic has changed)
    "XLingPaper Single Interlinear Example",
    "XLingPaper List Interlinear - Create New List",
    "XLingPaper List Interlinear - Add Item to Existing List",
    "---------------------------------------------------",
    "HTML Table (for web display)"
    #"Word MathML - Column Equations"
]
dropdown.current(0)
dropdown.pack(pady=5)

# Checkbox for LaTeX-specific option (hidden by default)
latex_option_var = tk.BooleanVar(value=False) # Unchecked by default
latex_option_checkbox = ttk.Checkbutton(root, text=r"Enable Predefined LaTeX Styles", variable=latex_option_var)
latex_option_checkbox.pack(pady=5)

# Checkbox for removing column breaks between morphemes
remove_column_breaks_var = tk.BooleanVar(value=True)  # Checked by default
remove_column_breaks_checkbox = ttk.Checkbutton(root, text="Remove Column breaks between Morphemes (Enforce Word Alignment instead of Morpheme Alignment)", variable=remove_column_breaks_var)
remove_column_breaks_checkbox.pack(pady=5)  # Positioned below the first checkbox

# Checkbox for removing FLEx row labels
remove_labels_var = tk.BooleanVar(value=True)
remove_labels_checkbox = ttk.Checkbutton(root, text="Remove FLEx row labels...", variable=remove_labels_var)
remove_labels_checkbox.pack(pady=5)  # Positioned between dropdown and buttons

# Convert button
convert_button = tk.Button(root, text="Convert and Re-Copy!", command=on_convert_click)
convert_button.pack(pady=10)

# Paste button
paste_button = tk.Button(root, text="Paste from Clipboard", command=lambda: paste_from_clipboard())
paste_button.pack(pady=5)
paste_from_clipboard()  # Initial paste from clipboard on startup


root.mainloop()

def convert_clipboard_for_mit_old(rows, latex_formatting=True):
    print("Rows before LaTeX conversion:", rows)
    
    if latex_formatting:
        ex_title = r"%\extitle{Example Caption}\\ %Caption/title with \extitle{} style"
        ex_subtitle = r"%\exsubtitle{Sub-caption}\\ %Sub-caption/subtitle using \exsubtitle style."
        txt_ref = r"%\txtref{TxtRf\_\#} %Reference source text abbreviation (predefined style)"
    else:
        ex_title = r"%\textbf{\underline{Example Caption}}\\ %Caption/title with built-in formatting"
        ex_subtitle = r"%\textit{Sub-caption} \\ %Sub-caption/subtitle with built-in formatting"
        txt_ref = r"%\hfill\textit{TxtRf\_\#} %Reference source text abbreviation with built-in formatting"


    # rows is now a list of lists (already processed TSV)
    # 4. Replace spaces within cells with "~", except for the final row that starts with "Free"
    for i, row in enumerate(rows):
        if is_free_row(row[0]):
            continue  # Skip replacement for the final "Free" row
        rows[i] = [re.sub(r"\s+", "~", cell) for cell in row]

    # 5. Insert BOM (~) in any empty cells
    BOM = "~"
    rows = [[cell if cell else BOM for cell in row] for row in rows]

    is_free = (
        rows[-1][0].strip().startswith("Free")
        or (rows[-1][0].strip().startswith("'") and rows[-1][0].strip().endswith("'"))
    )

    # --- Add LaTeX prefixes as the final step before output ---

    num_non_free = len(rows) - 1 if rows and is_free else len(rows)
    if rows:
    # Find the first row that is NOT a free translation
        for row in rows:
            label = row[0].strip().lower()
            if not is_free_row(row[0]):
                row[0] = r"\g" + "l" * num_non_free + " " + row[0]
                break
    if rows and rows[-1][0].strip().lower().startswith("free "):
        cell = rows[-1][0].strip()
        rows[-1][0] = r"\glt \textbf{Free} " + cell[5:]
    elif rows and rows[-1][0].lstrip().startswith("'") and rows[-1][0].lstrip().endswith("'"):
        # If the last row is a quoted Free translation, format it
        cell = rows[-1][0].lstrip().strip("'")
        rows[-1][0] = r"\glt `" + cell

    # Check if FLEx row labels are present
    has_labels = any(row[0].strip().lower() in FLEX_ROW_LABELS for row in rows)
    print(f"Has FLEx labels: {has_labels}")
    if has_labels:
        # 6. Wrap first cell of each row (except "Free" row) with \textbf{}
        for row in rows:
            label = row[0].strip()
            if not (label.lower() == "free" or (label.startswith("'") and label.endswith("'"))):
                m = re.match(r"^(\\g[l]+)(.+)$", row[0])
                if m:
                    row[0] = f"{m.group(1)}\\textbf{{{m.group(2).lstrip('~')}}}"
                else:
                    row[0] = r"\textbf{" + row[0].strip() + "}"


    # Build the interlinear block
    interlinear_lines = []
    for i, row in enumerate(rows):
        line = " ".join(row)
        interlinear_lines.append(line + (r"\\" if i != len(rows) - 1 else ""))

    # Insert \vspace{14pt} before the last line (the translation line)
    if len(interlinear_lines) > 1:
        interlinear_lines.insert(-1, r"\vspace{14pt} %Add 14 pt vertical space between interlinear blocks.")

    interlinear_block = (
        "{%\n"
        "%Suggestion: Consider definining a global linespacing variable and then insert it in the \\lineskip and \\vspace commands below instead of 14pt. \n"
        "  \\setlength{\\lineskiplimit}{1pt} % Anytime there's less vertical space than 1pt, trigger the line immediately below.\n"
        "  \\setlength{\\lineskip}{14pt} % 14 pt vertical space between interlinear blocks.\n"
        + "\n".join(interlinear_lines) + "\n"
        "}%"  # End of group
    )

    # Final output with LaTeX formatting
    final_output = (
        r"%\vspace{12pt} %add 12pt vertical space" + "\n"
        r"\begin{minipage}{\linewidth}\begin{exe}" + "\n"
        r"\ex%\label{name} %for referencing this elsewhere" + "\n"
        + ex_title + "\n"
        + ex_subtitle + "\n"
        r"%vspace{6pt} %Add 6 pt vertical space between title and blocks." + "\n"
        + interlinear_block + "\n"
        + txt_ref + "\n"
        r"\end{exe}\end{minipage}\\" + "\n"
    )
    return final_output

def tsv_to_html_table_old(tsv_rows):
    """
    Convert TSV rows (list of lists) to an HTML table string
    and copy it to the clipboard using copy_html_to_clipboard().
    """
    html = ['<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;">']
    for row in tsv_rows:
        html.append('<tr>')
        for cell in row:
            cell_escaped = (str(cell)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
            html.append(f'<td>{cell_escaped}</td>')
        html.append('</tr>')
    html.append('</table>')

    # Join HTML lines into a single string
    html_string = "\n".join(html)

    # Copy the HTML to clipboard (you need to implement this)
    return html_string
