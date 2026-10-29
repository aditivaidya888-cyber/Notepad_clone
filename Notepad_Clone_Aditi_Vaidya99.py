import json
import os
import re
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from pathlib import Path


APP_NAME = "Aditi's Notepad clone"
AUTOSAVE_SECONDS = 30
AUTOSAVE_DIR = Path.home() / ".aditis_notepad_autosaves"
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 40


class Document:
    """State and widgets belonging to one open document tab."""

    def __init__(self, app, initial_text="", file_path=None):
        self.app = app
        self.file_path = file_path
        self.saved_content = initial_text
        self.font_size = 12
        self.word_wrap = True

        self.frame = ttk.Frame(app.notebook)
        self.text = tk.Text(
            self.frame,
            undo=True,
            autoseparators=True,
            maxundo=-1,
            wrap="word",
            font=("Consolas", self.font_size),
            padx=8,
            pady=8,
            tabs=("4c",),
        )
        self.v_scroll = ttk.Scrollbar(
            self.frame, orient="vertical", command=self.text.yview
        )
        self.h_scroll = ttk.Scrollbar(
            self.frame, orient="horizontal", command=self.text.xview
        )
        self.text.configure(
            yscrollcommand=self.v_scroll.set,
            xscrollcommand=self.h_scroll.set,
        )

        self.text.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        # Formatting tags apply to selected text.
        self.text.tag_configure("bold", font=("Consolas", self.font_size, "bold"))
        self.text.tag_configure("italic", font=("Consolas", self.font_size, "italic"))
        self.text.tag_configure(
            "bold_italic", font=("Consolas", self.font_size, "bold italic")
        )
        self.text.tag_configure("underline", underline=True)
        self.text.tag_configure("strike", overstrike=True)
        self.text.tag_configure(
            "search_match", background="#ffe082", foreground="black"
        )

        if initial_text:
            self.text.insert("1.0", initial_text)
        self.text.edit_modified(False)

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_cursor_change)
        self.text.bind("<ButtonRelease-1>", self._on_cursor_change)
        self.text.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.text.bind("<Control-MouseWheel>", self._on_zoom, add="+")
        self.text.bind("<Control-Button-4>", lambda e: self.change_font_size(1), add="+")
        self.text.bind("<Control-Button-5>", lambda e: self.change_font_size(-1), add="+")
        self.text.bind("<<Paste>>", lambda e: self.app.root.after_idle(self.refresh_status))
        self.text.bind("<<Cut>>", lambda e: self.app.root.after_idle(self.refresh_status))

        # Bind formatting shortcuts directly to the Text widget. Tk maps Ctrl+I
        # to a key event that can be consumed by the Text class bindings before
        # a toplevel binding sees it, so widget-level bindings are more reliable.
        self.text.bind("<Control-b>", lambda e: self._shortcut(self.app.bold))
        self.text.bind("<Control-i>", lambda e: self._shortcut(self.app.italic))
        self.text.bind("<Control-u>", lambda e: self._shortcut(self.app.underline))
        self.text.bind("<Control-Shift-X>", lambda e: self._shortcut(self.app.strike))

        if initial_text:
            self.text.edit_reset()
            self.saved_content = initial_text

    @staticmethod
    def _shortcut(callback):
        callback()
        return "break"

    def content(self):
        return self.text.get("1.0", "end-1c")

    def changed(self):
        return self.content() != self.saved_content

    def display_name(self):
        return os.path.basename(self.file_path) if self.file_path else "Untitled"

    def _on_modified(self, _event=None):
        # Tkinter's modified flag must be reset after handling the event.
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.app.update_tab_title(self)
            self.app.refresh_status()

    def _on_cursor_change(self, _event=None):
        self.app.refresh_status()

    def _on_mousewheel(self, event):
        # Keep normal scrolling. Ctrl+wheel is handled separately.
        return None

    def _on_zoom(self, event):
        self.change_font_size(1 if event.delta > 0 else -1)
        return "break"

    def change_font_size(self, amount):
        self.font_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self.font_size + amount))
        self.text.configure(font=("Consolas", self.font_size))
        # Refresh formatting tag fonts so the base size remains consistent.
        self.text.tag_configure("bold", font=("Consolas", self.font_size, "bold"))
        self.text.tag_configure("italic", font=("Consolas", self.font_size, "italic"))
        self.text.tag_configure(
            "bold_italic", font=("Consolas", self.font_size, "bold italic")
        )
        self.app.refresh_status()

    def toggle_wrap(self):
        self.word_wrap = not self.word_wrap
        self.text.configure(wrap="word" if self.word_wrap else "none")
        if self.word_wrap:
            self.h_scroll.grid_remove()
        else:
            self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.app.refresh_status()

    def apply_tag_to_selection(self, tag_name):
        try:
            start, end = self.text.index("sel.first"), self.text.index("sel.last")
        except tk.TclError:
            messagebox.showinfo(
                "Formatting", "Select some text first.", parent=self.app.window
            )
            return

        # Toggle the selected tag off if all selected characters already have it.
        ranges = self.text.tag_ranges(tag_name)
        fully_applied = False
        if ranges:
            fully_applied = True
            pos = self.text.index(start)
            while self.text.compare(pos, "<", end):
                if tag_name not in self.text.tag_names(pos):
                    fully_applied = False
                    break
                next_pos = self.text.index(f"{pos}+1c")
                if self.text.compare(next_pos, "<=", pos):
                    break
                pos = next_pos

        if fully_applied:
            self.text.tag_remove(tag_name, start, end)
        else:
            self.text.tag_add(tag_name, start, end)
        self.text.focus_set()
        self.app.refresh_status()

    def toggle_bold(self):
        self.apply_tag_to_selection("bold")

    def toggle_italic(self):
        self.apply_tag_to_selection("italic")

    def toggle_underline(self):
        self.apply_tag_to_selection("underline")

    def toggle_strike(self):
        self.apply_tag_to_selection("strike")


class NotepadWindow:
    """One application window; each window has its own set of tabs."""

    def __init__(self, app, window=None):
        self.app = app
        self.window = window or app.root
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True)
        self.documents = []
        self.notebook.bind("<<NotebookTabChanged>>", lambda _e: self.refresh_status())
        self._build_menus()
        self._build_status_bar()
        self.new_tab()
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)

    def _build_menus(self):
        self.menu_bar = tk.Menu(self.window)
        self.window.config(menu=self.menu_bar)

        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Tab", command=self.new_tab, accelerator="Ctrl+N")
        file_menu.add_command(label="New Window", command=self.app.new_window, accelerator="Ctrl+Shift+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_as_file, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab", command=self.close_tab, accelerator="Ctrl+W")
        file_menu.add_command(label="Exit Window", command=self.close_window)

        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=self.copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_separator()
        edit_menu.add_command(label="Find / Replace", command=self.open_find_replace, accelerator="Ctrl+F")
        edit_menu.add_command(label="Bold", command=self.bold, accelerator="Ctrl+B")
        edit_menu.add_command(label="Italic", command=self.italic, accelerator="Ctrl+I")
        edit_menu.add_command(label="Underline", command=self.underline, accelerator="Ctrl+U")
        edit_menu.add_command(label="Strikethrough", command=self.strike, accelerator="Ctrl+Shift+X")
        edit_menu.add_command(label="Insert Date and Time", command=self.insert_date_time)

        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Word Wrap", command=self.toggle_wrap)
        view_menu.add_command(label="Zoom In", command=lambda: self.zoom(1), accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=lambda: self.zoom(-1), accelerator="Ctrl+-")
        view_menu.add_command(label="Reset Zoom", command=self.reset_zoom, accelerator="Ctrl+0")

        # Standard Windows shortcuts.
        bindings = {
            "<Control-n>": lambda e: self.new_tab(),
            "<Control-Shift-N>": lambda e: self.app.new_window(),
            "<Control-o>": lambda e: self.open_file(),
            "<Control-s>": lambda e: self.save_file(),
            "<Control-Shift-S>": lambda e: self.save_as_file(),
            "<Control-w>": lambda e: self.close_tab(),
            "<Control-f>": lambda e: self.open_find_replace(),
            "<Control-b>": lambda e: self.bold(),
            "<Control-i>": lambda e: self.italic(),
            "<Control-u>": lambda e: self.underline(),
            "<Control-Shift-X>": lambda e: self.strike(),
            "<Control-plus>": lambda e: self.zoom(1),
            "<Control-equal>": lambda e: self.zoom(1),
            "<Control-minus>": lambda e: self.zoom(-1),
            "<Control-0>": lambda e: self.reset_zoom(),
            "<Control-a>": lambda e: self.select_all(),
            "<Control-z>": lambda e: self.undo(),
            "<Control-y>": lambda e: self.redo(),
        }
        for sequence, callback in bindings.items():
            self.window.bind(sequence, callback)

    def _build_status_bar(self):
        self.status = tk.Label(
            self.window, text="", anchor="w", relief="sunken", padx=6, pady=4
        )
        self.status.pack(side="bottom", fill="x")

    def current_doc(self):
        selected = self.notebook.select()
        if not selected:
            return None
        for doc in self.documents:
            if str(doc.frame) == selected:
                return doc
        return None

    def new_tab(self, initial_text="", file_path=None):
        doc = Document(self, initial_text=initial_text, file_path=file_path)
        self.documents.append(doc)
        self.notebook.add(doc.frame, text=doc.display_name())
        self.notebook.select(doc.frame)
        doc.text.focus_set()
        self.update_tab_title(doc)
        self.refresh_status()
        return doc

    def update_tab_title(self, doc):
        if doc not in self.documents:
            return
        marker = "*" if doc.changed() else ""
        try:
            self.notebook.tab(doc.frame, text=f"{doc.display_name()}{marker}")
        except tk.TclError:
            pass
        if self.current_doc() is doc:
            self.window.title(f"{APP_NAME} - {doc.display_name()}{marker}")

    def refresh_status(self):
        doc = self.current_doc()
        if not doc:
            self.status.config(text="")
            return
        content = doc.content()
        line, column = doc.text.index("insert").split(".")
        words = len(content.split())
        chars = len(content)
        lines = len(content.splitlines()) or 1
        self.status.config(
            text=(
                f"Line: {int(line)}  |  Column: {int(column) + 1}  |  "
                f"Words: {words}  |  Characters: {chars}  |  Lines: {lines}  |  "
                f"Zoom: {doc.font_size}px"
            )
        )
        self.update_tab_title(doc)

    def ask_to_save(self, doc):
        if not doc.changed():
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"Save changes to {doc.display_name()} before continuing?",
            parent=self.window,
        )
        if answer is None:
            return False
        if answer:
            return self.save_file(doc)
        return True

    def new_tab_command(self):
        self.new_tab()

    def open_file(self):
        if not self.ask_to_save(self.current_doc()):
            return
        path = filedialog.askopenfilename(
            parent=self.window,
            title="Open File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return
        # If the same file is already open in this window, switch to its tab.
        for doc in self.documents:
            if doc.file_path and os.path.abspath(doc.file_path) == os.path.abspath(path):
                self.notebook.select(doc.frame)
                return
        try:
            with open(path, "r", encoding="utf-8-sig", newline=None) as handle:
                content = handle.read()
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Open Error", f"Could not open the file.\n\n{error}", parent=self.window)
            return
        self.new_tab(content, path)

    def save_file(self, doc=None):
        doc = doc or self.current_doc()
        if not doc:
            return False
        if not doc.file_path:
            return self.save_as_file(doc)
        return self._write_file(doc, doc.file_path)

    def save_as_file(self, doc=None):
        doc = doc or self.current_doc()
        if not doc:
            return False
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save As",
            defaultextension=".txt",
            initialfile=doc.display_name() if doc.file_path else "Untitled.txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return False
        return self._write_file(doc, path)

    def _write_file(self, doc, path):
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(doc.content())
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Save Error", f"Could not save the file.\n\n{error}", parent=self.window)
            return False
        doc.file_path = path
        doc.saved_content = doc.content()
        doc.text.edit_modified(False)
        self.update_tab_title(doc)
        self.refresh_status()
        self.app.remove_recovery(doc)
        return True

    def close_tab(self):
        doc = self.current_doc()
        if not doc:
            return
        if not self.ask_to_save(doc):
            return
        self.app.remove_recovery(doc)
        self.notebook.forget(doc.frame)
        self.documents.remove(doc)
        doc.frame.destroy()
        if not self.documents:
            self.new_tab()
        self.refresh_status()

    def close_window(self):
        for doc in list(self.documents):
            if not self.ask_to_save(doc):
                return
        for doc in list(self.documents):
            self.app.remove_recovery(doc)
        self.app.remove_window(self)
        if self.window is self.app.root:
            if self.app.windows:
                # Hide the original root window while other editor windows remain.
                self.app.root.withdraw()
                self.app.windows[0].window.lift()
            else:
                self.app.root.destroy()
        else:
            self.window.destroy()
            if not self.app.windows:
                self.app.root.destroy()

    def cut(self):
        doc = self.current_doc()
        if doc:
            doc.text.event_generate("<<Cut>>")
            self.refresh_status()

    def copy(self):
        doc = self.current_doc()
        if doc:
            doc.text.event_generate("<<Copy>>")

    def paste(self):
        doc = self.current_doc()
        if doc:
            doc.text.event_generate("<<Paste>>")
            self.window.after_idle(self.refresh_status)

    def select_all(self):
        doc = self.current_doc()
        if doc:
            doc.text.tag_add("sel", "1.0", "end-1c")
            doc.text.mark_set("insert", "1.0")
            doc.text.see("insert")
            doc.text.focus_set()
        return "break"

    def undo(self):
        doc = self.current_doc()
        if doc:
            try:
                doc.text.edit_undo()
            except tk.TclError:
                pass
            self.refresh_status()

    def redo(self):
        doc = self.current_doc()
        if doc:
            try:
                doc.text.edit_redo()
            except tk.TclError:
                pass
            self.refresh_status()

    def bold(self):
        doc = self.current_doc()
        if doc:
            doc.toggle_bold()

    def italic(self):
        doc = self.current_doc()
        if doc:
            doc.toggle_italic()

    def underline(self):
        doc = self.current_doc()
        if doc:
            doc.toggle_underline()

    def strike(self):
        doc = self.current_doc()
        if doc:
            doc.toggle_strike()

    def zoom(self, amount):
        doc = self.current_doc()
        if doc:
            doc.change_font_size(amount)

    def reset_zoom(self):
        doc = self.current_doc()
        if doc:
            doc.change_font_size(12 - doc.font_size)

    def toggle_wrap(self):
        doc = self.current_doc()
        if doc:
            doc.toggle_wrap()

    def insert_date_time(self):
        doc = self.current_doc()
        if doc:
            doc.text.insert("insert", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.refresh_status()

    def open_find_replace(self):
        doc = self.current_doc()
        if not doc:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title("Find and Replace")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Find:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        find_entry = ttk.Entry(dialog, width=32)
        find_entry.grid(row=0, column=1, padx=8, pady=8)
        ttk.Label(dialog, text="Replace with:").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        replace_entry = ttk.Entry(dialog, width=32)
        replace_entry.grid(row=1, column=1, padx=8, pady=8)

        def find_next():
            query = find_entry.get()
            if not query:
                messagebox.showinfo("Find", "Enter a word or phrase to find.", parent=dialog)
                return
            doc.text.tag_remove("search_match", "1.0", tk.END)
            start = doc.text.index("insert")
            match = doc.text.search(query, start, stopindex=tk.END, nocase=True)
            if not match:
                match = doc.text.search(query, "1.0", stopindex=tk.END, nocase=True)
            if match:
                end = f"{match}+{len(query)}c"
                doc.text.tag_add("search_match", match, end)
                doc.text.tag_remove("sel", "1.0", tk.END)
                doc.text.tag_add("sel", match, end)
                doc.text.mark_set("insert", end)
                doc.text.see(match)
                doc.text.focus_set()
            else:
                messagebox.showinfo("Find", "No matching text was found.", parent=dialog)

        def replace_one():
            query, replacement = find_entry.get(), replace_entry.get()
            if not query:
                messagebox.showinfo("Replace", "Enter text to find.", parent=dialog)
                return
            try:
                start, end = doc.text.index("sel.first"), doc.text.index("sel.last")
                selected = doc.text.get(start, end)
            except tk.TclError:
                selected = ""
            if selected.casefold() == query.casefold():
                doc.text.delete(start, end)
                doc.text.insert(start, replacement)
            find_next()
            self.refresh_status()

        def replace_all():
            query, replacement = find_entry.get(), replace_entry.get()
            if not query:
                messagebox.showinfo("Replace All", "Enter text to find.", parent=dialog)
                return
            content = doc.content()
            count = content.casefold().count(query.casefold())
            if not count:
                messagebox.showinfo("Replace All", "No matching text was found.", parent=dialog)
                return
            updated = re.sub(re.escape(query), lambda _m: replacement, content, flags=re.IGNORECASE)
            doc.text.delete("1.0", tk.END)
            doc.text.insert("1.0", updated)
            self.refresh_status()
            messagebox.showinfo("Replace All", f"Replaced {count} occurrence(s).", parent=dialog)

        ttk.Button(dialog, text="Find Next", command=find_next).grid(row=2, column=0, padx=8, pady=8, sticky="ew")
        ttk.Button(dialog, text="Replace", command=replace_one).grid(row=2, column=1, padx=8, pady=8, sticky="w")
        ttk.Button(dialog, text="Replace All", command=replace_all).grid(row=3, column=0, padx=8, pady=4, sticky="ew")
        ttk.Button(dialog, text="Close", command=dialog.destroy).grid(row=3, column=1, padx=8, pady=4, sticky="e")
        find_entry.focus_set()


class NotepadApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("1000x650")
        self.root.minsize(650, 420)
        self.windows = []
        self.root_window = NotepadWindow(self, self.root)
        self.windows.append(self.root_window)
        self.root.after(AUTOSAVE_SECONDS * 1000, self.autosave_all)
        self.root.after(500, self.offer_recovery)
        self.root.mainloop()

    def new_window(self):
        window = tk.Toplevel(self.root)
        window.geometry("900x600")
        window.minsize(600, 400)
        editor_window = NotepadWindow(self, window)
        self.windows.append(editor_window)
        window.lift()
        return editor_window

    def remove_window(self, editor_window):
        if editor_window in self.windows:
            self.windows.remove(editor_window)

    def recovery_path(self, doc):
        AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        # A stable unique key for a tab, retained for this running session.
        if not hasattr(doc, "_recovery_id"):
            doc._recovery_id = f"{os.getpid()}_{id(doc)}"
        return AUTOSAVE_DIR / f"{doc._recovery_id}.json"

    def autosave_all(self):
        try:
            AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
            for window in list(self.windows):
                for doc in list(window.documents):
                    if doc.changed():
                        payload = {
                            "app": APP_NAME,
                            "saved_at": datetime.now().isoformat(timespec="seconds"),
                            "file_path": doc.file_path,
                            "content": doc.content(),
                        }
                        path = self.recovery_path(doc)
                        temp_path = path.with_suffix(".tmp")
                        with open(temp_path, "w", encoding="utf-8") as handle:
                            json.dump(payload, handle, ensure_ascii=False, indent=2)
                        os.replace(temp_path, path)
        except OSError:
            # Recovery should never interrupt editing if the disk is unavailable.
            pass
        finally:
            if self.root.winfo_exists():
                self.root.after(AUTOSAVE_SECONDS * 1000, self.autosave_all)

    def remove_recovery(self, doc):
        try:
            path = self.recovery_path(doc)
            if path.exists():
                path.unlink()
        except OSError:
            pass

    def offer_recovery(self):
        if not AUTOSAVE_DIR.exists():
            return
        try:
            files = sorted(AUTOSAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return
        if not files:
            return
        if not messagebox.askyesno(
            "Recover Unsaved Work",
            f"Recovery copies were found ({len(files)} file(s)). Would you like to open them?",
            parent=self.root,
        ):
            return
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                content = payload.get("content", "")
                original = payload.get("file_path")
                title = Path(original).name if original else "Recovered document"
                if messagebox.askyesno(
                    "Recovery Copy",
                    f"Open recovery copy for '{title}'?\n\nAutosaved: {payload.get('saved_at', 'unknown')}",
                    parent=self.root,
                ):
                    doc = self.root_window.new_tab(content)
                    doc.saved_content = ""
                    doc._recovery_id = path.stem
                    self.root_window.update_tab_title(doc)
            except (OSError, ValueError, TypeError):
                continue


if __name__ == "__main__":
    NotepadApp()
