# FLEx Interlinear Copy Assistant

A cross-platform application streamlines the process of converting linguistic interlinear glossed text (IGT) data, typically copied as Tab-Separated Values (TSV) from **FieldWorks Language Explorer (FLEx)** ( or spreadsheets, into common publication formats.

The tool cleans the raw TSV data and provides one-click conversion to **LaTeX**, **XML**, and **HTML** formats.

## 🌟 Features

* **Clipboard-to-Format:** Directly pastes and processes TSV data copied from the clipboard.
* **Format Conversion:** Output interlinear text in multiple reliable formats:
    * **LaTeX (XeTeX):** Formats for packages like `ling-example` or `gb4e` (using `\glll` and similar commands).
    * **xlingpaper XML:** Outputs XLingPaper XML code for interlinear examples (and list interlinear examples) that can be pasted into the source code view.
    * **HTML:** Generates clean HTML markup, suitable for pasting into wikis or web content.
* **Data Pre-processing:** Automatically cleans the TSV data, removes entirely blank columns, attempts to handle numbered examples, and copies morpheme break markers (e.g., `-`, `=`, `.`) from the *Morphemes* row to the *Lex. Gloss* row.
* **Manual Entry/Editor:** Includes a built-in spreadsheet-like editor for manual creation or fine-tuning of interlinear examples.

## 💻 Installation and Running

### Option 1: Portable Executable (Windows x64)

For Windows users, the tool is distributed as a single, portable executable file (built with PyInstaller's `--onefile --windowed` options). **No installation is required—just download and run.**

* **Download:** [Portable FLEx Converter EXE (x64)](https://drive.google.com/file/d/1Ah1oBeynWNVLF5ytAvpsTJwSWM2jyuPh/view?usp=sharing)
* **Usage:** Download the file and double-click to run.

### Option 2: Running from Source (macOS, Linux, and Windows)

This tool is written in Python 3. To run it directly from the source code, you must have Python 3 and the `pyperclip` dependency installed.

1.  **Download:** Clone this repository or download the `simple-flex_il_clipboard_convert.py` file.
2.  **Install Dependency:**
    ```bash
    pip install pyperclip
    ```
3.  **Run the script:**
    ```bash
    python simple-flex_il_clipboard_convert.py
    ```

## ⚠️ Major Development Targets

We are actively seeking contributors to implement the following high-priority features and fixes:

1.  **Multi-Example Clipboard Support:**
    * **Goal:** Allow users to copy and paste **multiple** interlinear examples from a source (e.g., FLEx or spreadsheet) at once.
    * **Current State:** The application currently only processes a single interlinear example (one sentence) per clipboard paste.
2.  **Automatic Text Reference Capture:**
    * **Goal:** Implement logic to automatically detect and parse the text source abbreviation and line number (e.g., `TXT:12a`) from the input data.
    * **Benefit:** This would eliminate the need for users to manually add this reference to the output formats (LaTeX, XML).
3.  **Manual Editor Overhaul:**
    * **Goal:** Fix critical bugs and improve the usability of the manual interlinear editor.
    * **Current State:** The editor is known to be buggy and requires significant work to make it a reliable feature for creating or editing examples within the GUI.
4.  **MS Word MathML Implementation:**
    * **Goal:** Research and implement a robust method for outputting the data as **Microsoft Word MathML** for clean interlinear display in Word documents.
    * **Constraint:** This feature is currently disabled in the GUI and will probably always be **inaccessible on macOS**. Implementation must focus on platform-specific methods for **Windows** that can correctly place the complex MathML data onto the clipboard, potentially requiring system APIs beyond standard Python libraries. MathML also turns out to be very difficult to work with outside of Word.
5.  **macOS/Linux Standalone Packaging:**
    * **Goal:** Create single-file, portable application bundles for macOS (`.app`) and Linux (e.g., AppImage).
    * **Constraint:** The goal is a simple, lightweight bundle (under 25MB) that runs without manual dependency installation. This will be very complicated as it will need to include logic to download and install dependences inside the app bundle on the first run.
6. **Windows Bootstrapper/Network Installer (probably using an NSIS or similar installer script):**
    * **Goal:** Create an easy to use Windows installer that is under 25MB that works by downloading and installing python and dependencies to the app install directory and then creating a start menu shortcut that will run the app.
    * **Constraint:** The goal is a simple, lightweight bundle (under 25MB) that can be hosted directly in the GitHub repository, which looks a lot less sketchy and is also a more user friendly experience.

## 🤝 Contributing

We welcome contributions! If you have a bug fix or feature suggestion, please open an Issue or submit a Pull Request. Specific contributions are needed for the [Major Development Targets](#-major-development-targets) listed above.

## ⚖️ Licensing

**Copyright © 2025 Seth Johnston**

This software is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.**

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
