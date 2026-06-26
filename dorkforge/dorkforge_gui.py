#!/usr/bin/env python3
"""
DorkForge v1.0 GUI — Tkinter dark hacker theme.
Single-file, no external deps beyond stdlib + dorkforge engine.
"""

import os
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

# Make dorkforge.py importable
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from dorkforge import (
        Client, Scraper, extract_urls, filter_excluded, is_blocked,
        ENGINE_URLS, ENGINE_RESULTS_PER_PAGE, EXCLUDED_DOMAINS
    )
    DORKFORGE_OK = True
    DORKFORGE_ERROR = None
except Exception as e:
    DORKFORGE_OK = False
    DORKFORGE_ERROR = str(e)

# ---- Theme ----
BG = "#0a0e14"
BG2 = "#11151c"
FG = "#d8e1ec"
FG2 = "#7f8a9e"
ACCENT = "#39ff14"
ACCENT2 = "#ff3860"
WARN = "#ffb86c"
ENTRY_BG = "#1a1f29"  # Fixed: was #0d1117 (invisible against BG)
ENTRY_FG = "#39ff14"
BTN_BG = "#1a1f29"
BTN_HOVER = "#262c3a"

FONT_MONO = ("Courier New", 10)
FONT_MONO_BIG = ("Courier New", 11, "bold")
FONT_TITLE = ("Courier New", 14, "bold")
FONT_SMALL = ("Courier New", 9)


class DorkForgeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DorkForge v1.0 — URL Harvester for SQLiDumper")
        self.root.geometry("1100x720")
        self.root.configure(bg=BG)
        self.root.minsize(900, 600)

        # State
        self.running = False
        self.worker_thread = None
        self.event_queue = queue.Queue()
        self.stats = {"dorks_done": 0, "urls": 0, "errors": 0, "current": ""}

        self._build_ui()
        self._poll_events()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Title bar
        title = tk.Frame(self.root, bg=BG, height=50)
        title.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(
            title, text="⚡ DORKFORGE v1.0 ⚡", font=FONT_TITLE,
            fg=ACCENT, bg=BG, anchor="w"
        ).pack(side="left")
        tk.Label(
            title, text="multi-engine dork executor",
            font=FONT_MONO, fg=FG2, bg=BG, anchor="w"
        ).pack(side="left", padx=10)
        if not DORKFORGE_OK:
            tk.Label(
                title, text=f"⚠ dorkforge.py import failed: {DORKFORGE_ERROR}",
                font=FONT_SMALL, fg=WARN, bg=BG, anchor="e"
            ).pack(side="right")

        # Main paned window: left (controls), right (log)
        main = tk.PanedWindow(self.root, orient="horizontal", bg=BG, sashwidth=4)
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # ---- LEFT: controls ----
        left = tk.Frame(main, bg=BG, width=420)
        main.add(left, minsize=380)

        # Dork source
        self._section(left, "DORK SOURCE")
        dork_frame = tk.Frame(left, bg=BG)
        dork_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.dork_file_var = tk.StringVar()
        tk.Entry(
            dork_frame, textvariable=self.dork_file_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=BTN_HOVER, highlightcolor=ACCENT,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            dork_frame, text="📂", font=FONT_MONO, bg=BTN_BG, fg=ACCENT,
            relief="flat", activebackground=BTN_HOVER, activeforeground=ACCENT,
            command=self._browse_dorks, width=3, cursor="hand2",
        ).pack(side="left", padx=(4, 0))

        # Preset dorks quick-pick
        preset_frame = tk.Frame(left, bg=BG)
        preset_frame.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(preset_frame, text="⚡ QUICK DORKS:", font=FONT_MONO, fg=FG2, bg=BG).pack(side="left")
        for label, gen in [
            ("🎯 TARGETED", "targeted"),
            ("SQLi Params", "sqli"),
            ("CMS", "cms"),
            ("eCommerce", "ecom"),
            ("Forum", "forum"),
            ("All Parametric", "all"),
            ("⭐ CURATED", "curated"),
        ]:
            tk.Button(
                preset_frame, text=label, font=FONT_SMALL, bg=BTN_BG, fg=ACCENT,
                relief="flat", cursor="hand2", padx=4, pady=2,
                activebackground=BTN_HOVER, activeforeground=ACCENT,
                command=lambda g=gen: self._gen_preset_dorks(g),
            ).pack(side="left", padx=2)

        # Single dork input
        self._section(left, "OR SINGLE DORK (optional)")
        dork_single = tk.Frame(left, bg=BG)
        dork_single.pack(fill="x", padx=10, pady=(0, 8))
        self.dork_single_var = tk.StringVar()
        tk.Entry(
            dork_single, textvariable=self.dork_single_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, insertbackground=ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=BTN_HOVER, highlightcolor=ACCENT,
        ).pack(fill="x")

        # Engines
        self._section(left, "ENGINES")
        engine_frame = tk.Frame(left, bg=BG)
        engine_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.engine_vars = {}
        for eng in ["ddg", "bing", "brave", "yandex"]:
            var = tk.BooleanVar(value=(eng == "bing"))
            self.engine_vars[eng] = var
            tk.Checkbutton(
                engine_frame, text=eng.upper(), variable=var,
                font=FONT_MONO, bg=BG, fg=FG, selectcolor=BTN_BG,
                activebackground=BG, activeforeground=ACCENT,
                cursor="hand2",
            ).pack(side="left", padx=(0, 12))
        # All toggle
        tk.Button(
            engine_frame, text="ALL", font=FONT_MONO_BIG,
            bg=BTN_BG, fg=ACCENT2, relief="flat", cursor="hand2",
            activebackground=BTN_HOVER, activeforeground=ACCENT2,
            command=self._toggle_all_engines,
        ).pack(side="right")

        # Settings: pages, workers
        self._section(left, "SETTINGS")
        settings = tk.Frame(left, bg=BG)
        settings.pack(fill="x", padx=10, pady=(0, 8))
        # Pages
        tk.Label(settings, text="Pages/dork:", font=FONT_MONO, fg=FG, bg=BG).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.pages_var = tk.IntVar(value=2)
        tk.Spinbox(
            settings, from_=1, to=20, textvariable=self.pages_var,
            font=FONT_MONO, bg=ENTRY_BG, fg=ENTRY_FG, buttonbackground=BTN_BG,
            width=5, relief="flat",
        ).grid(row=0, column=1, sticky="w", padx=(0, 20))
        # Workers
        tk.Label(settings, text="Workers:", font=FONT_MONO, fg=FG, bg=BG).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.workers_var = tk.IntVar(value=5)
        tk.Spinbox(
            settings, from_=1, to=50, textvariable=self.workers_var,
            font=FONT_MONO, bg=ENTRY_BG, fg=ENTRY_FG, buttonbackground=BTN_BG,
            width=5, relief="flat",
        ).grid(row=0, column=3, sticky="w")

        # Delay min/max
        tk.Label(settings, text="Delay (s):", font=FONT_MONO, fg=FG, bg=BG).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.delay_min_var = tk.DoubleVar(value=0.4)
        self.delay_max_var = tk.DoubleVar(value=1.2)
        delay_box = tk.Frame(settings, bg=BG)
        delay_box.grid(row=1, column=1, sticky="w", pady=(8, 0))
        tk.Entry(
            delay_box, textvariable=self.delay_min_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, width=5, relief="flat",
        ).pack(side="left")
        tk.Label(delay_box, text="–", font=FONT_MONO, fg=FG2, bg=BG).pack(side="left", padx=2)
        tk.Entry(
            delay_box, textvariable=self.delay_max_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, width=5, relief="flat",
        ).pack(side="left")

        # Output
        self._section(left, "OUTPUT")
        out_frame = tk.Frame(left, bg=BG)
        out_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.output_var = tk.StringVar(value="dorkforge_hits.txt")
        tk.Entry(
            out_frame, textvariable=self.output_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, relief="flat", highlightthickness=1,
            highlightbackground=BTN_HOVER, highlightcolor=ACCENT,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            out_frame, text="📂", font=FONT_MONO, bg=BTN_BG, fg=ACCENT,
            relief="flat", cursor="hand2",
            command=self._browse_output, width=3,
        ).pack(side="left", padx=(4, 0))

        # Format for SQLiDumper
        fmt_frame = tk.Frame(left, bg=BG)
        fmt_frame.pack(fill="x", padx=10, pady=(4, 4))
        tk.Button(
            fmt_frame, text="🎯 FORMAT FOR SQLiDUMPER", font=FONT_MONO_BIG,
            bg=BTN_BG, fg=ACCENT2, relief="flat", cursor="hand2",
            activebackground=BTN_HOVER, activeforeground=ACCENT2,
            command=self._format_for_sqldumper,
        ).pack(fill="x")

        # Analyze yield (v3)
        yield_frame = tk.Frame(fmt_frame, bg=BG)
        yield_frame.pack(fill="x", pady=(4, 0))
        tk.Button(
            yield_frame, text="📊 ANALYZE YIELD", font=FONT_MONO,
            bg=BTN_BG, fg=ACCENT, relief="flat", cursor="hand2",
            activebackground=BTN_HOVER, activeforeground=ACCENT,
            command=self._analyze_yield,
        ).pack(side="left", fill="x", expand=True)

        # SQLite
        sqlite_frame = tk.Frame(left, bg=BG)
        sqlite_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.use_sqlite_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            sqlite_frame, text="SQLite sink:", variable=self.use_sqlite_var,
            font=FONT_MONO, bg=BG, fg=FG, selectcolor=BTN_BG,
            activebackground=BG, activeforeground=ACCENT,
        ).pack(side="left")
        self.sqlite_var = tk.StringVar(value="dorkforge_hits.db")
        tk.Entry(
            sqlite_frame, textvariable=self.sqlite_var, font=FONT_MONO,
            bg=ENTRY_BG, fg=ENTRY_FG, relief="flat", highlightthickness=1,
            highlightbackground=BTN_HOVER, highlightcolor=ACCENT,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Button(
            sqlite_frame, text="📂", font=FONT_MONO, bg=BTN_BG, fg=ACCENT,
            relief="flat", cursor="hand2", width=3,
            command=self._browse_sqlite,
        ).pack(side="left", padx=(4, 0))

        # Action buttons
        btn_frame = tk.Frame(left, bg=BG)
        btn_frame.pack(fill="x", padx=10, pady=(10, 5))
        self.start_btn = tk.Button(
            btn_frame, text="⚡ START", font=FONT_MONO_BIG,
            bg=BTN_BG, fg=ACCENT, activebackground=BG, activeforeground=ACCENT,
            relief="flat", cursor="hand2", height=2,
            command=self._start,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.stop_btn = tk.Button(
            btn_frame, text="■ STOP", font=FONT_MONO_BIG,
            bg=BTN_BG, fg=ACCENT2, activebackground=BG, activeforeground=ACCENT2,
            relief="flat", cursor="hand2", height=2,
            command=self._stop, state="disabled",
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Stats bar
        stats = tk.Frame(left, bg=BG2, height=60)
        stats.pack(fill="x", padx=10, pady=(10, 0))
        self.stat_labels = {}
        for i, (key, label) in enumerate([
            ("dorks_done", "Dorks"),
            ("urls", "URLs"),
            ("errors", "Errors"),
            ("current", "Current"),
        ]):
            f = tk.Frame(stats, bg=BG2)
            f.grid(row=0, column=i, sticky="nsew", padx=4, pady=6)
            stats.grid_columnconfigure(i, weight=1)
            tk.Label(f, text=label, font=FONT_SMALL, fg=FG2, bg=BG2).pack()
            lbl = tk.Label(f, text="0" if key != "current" else "—",
                          font=FONT_MONO_BIG, fg=ACCENT, bg=BG2)
            lbl.pack()
            self.stat_labels[key] = lbl

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            left, variable=self.progress_var, maximum=100, mode="determinate",
        ).pack(fill="x", padx=10, pady=(4, 10))

        # ---- RIGHT: log ----
        right = tk.Frame(main, bg=BG)
        main.add(right, minsize=400)
        self._section(right, "LIVE LOG")
        log_frame = tk.Frame(right, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = scrolledtext.ScrolledText(
            log_frame, font=FONT_MONO, bg=ENTRY_BG, fg=FG,
            insertbackground=ACCENT, relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BTN_HOVER,
        )
        self.log.pack(fill="both", expand=True)
        # Log tags
        self.log.tag_config("info", foreground=FG)
        self.log.tag_config("ok", foreground=ACCENT)
        self.log.tag_config("warn", foreground=WARN)
        self.log.tag_config("err", foreground=ACCENT2)
        self.log.tag_config("url", foreground="#5af")
        self.log.tag_config("dim", foreground=FG2)
        self._log("DorkForge GUI ready.", "ok")
        self._log("Engine import: " + ("OK" if DORKFORGE_OK else f"FAIL ({DORKFORGE_ERROR})"),
                  "ok" if DORKFORGE_OK else "err")
        self._log("Working dir: " + str(SCRIPT_DIR), "dim")

    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(f, text="▸ " + text, font=FONT_MONO_BIG,
                 fg=ACCENT, bg=BG, anchor="w").pack(side="left")
        tk.Frame(f, bg=BTN_HOVER, height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=8)

    # ----------------------------------------------------------- File pickers
    def _browse_dorks(self):
        path = filedialog.askopenfilename(
            title="Select dork file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=str(SCRIPT_DIR),
        )
        if path:
            self.dork_file_var.set(path)

    def _gen_preset_dorks(self, preset):
        """Generate a preset dork file for one-shot URL harvest."""
        # 'targeted' = load the pre-made high-yield dorks file directly
        if preset == "targeted":
            targeted = SCRIPT_DIR / "dorks_bing_targeted.txt"
            if targeted.exists():
                count = sum(1 for _ in targeted.open(encoding="utf-8"))
                self.dork_file_var.set(str(targeted))
                self._log(f"[preset] Loaded {count} TARGETED dorks → {targeted.name}")
                return
            else:
                # Generate on the fly if file is missing
                try:
                    sys.path.insert(0, str(SCRIPT_DIR))
                    import gen_bing_targeted as gbt
                    targeted_dorks = gbt.generate_high_yield()
                    targeted.write_text("\n".join(targeted_dorks) + "\n", encoding="utf-8")
                    self.dork_file_var.set(str(targeted))
                    self._log(f"[preset] Generated {len(targeted_dorks)} TARGETED dorks → {targeted.name}")
                    return
                except Exception as e:
                    messagebox.showerror("TARGETED Error", f"Cannot load/generate targeted dorks: {e}")
                    return

        # Import the generator (lazy load)
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            import gen_parametric_dorks as gpd
        except Exception as e:
            messagebox.showerror("Generator Error", f"Cannot load gen_parametric_dorks: {e}")
            return

        # Build the dorks for the preset
        all_dorks = set()
        all_dorks.update(gpd.gen_classic_dorks())

        if preset == "sqli":
            # Param-only dorks (no vertical restriction)
            all_dorks.update(gpd.gen_basic_params())
        elif preset == "cms":
            all_dorks.update(gpd.gen_cms_specific())
        elif preset == "ecom":
            all_dorks.update(gpd.gen_shop_specific())
        elif preset == "forum":
            all_dorks.update(gpd.gen_classic_dorks())
            all_dorks.update(gpd.gen_cms_specific())
        elif preset == "all":
            all_dorks.update(gpd.gen_basic_params())
            all_dorks.update(gpd.gen_cms_specific())
            all_dorks.update(gpd.gen_shop_specific())
            all_dorks.update(gpd.gen_param_combos())
            # Add a couple verticals
            for v in ["hotel", "shop", "news", "forum"]:
                if v in gpd.VERTICALS:
                    for p in gpd.PARAMS[:15]:
                        for ext in ("php", "asp", "aspx"):
                            for kw in gpd.VERTICALS[v][:3]:
                                all_dorks.add(f'inurl:"{kw}" inurl:"?{p}=" inurl:.{ext}')
        elif preset == "curated":
            # Load pre-validated HIGH-YIELD dorks from dork_yield_analyzer output
            curated = SCRIPT_DIR / "high_yield_dorks.txt"
            if curated.exists():
                lines = curated.read_text(encoding="utf-8").strip().splitlines()
                all_dorks.update(lines)
                self._log(f"[curated] Loaded {len(lines)} PRE-VALIDATED high-yield dorks from {curated.name}")
            else:
                # Fall back to TOP-yield patterns (proven winners from data)
                self._log("[curated] No high_yield_dorks.txt found - using TOP-YIELD set", tag="warn")
                top_patterns = [
                    'contains:asp inurl:"?id="',
                    'contains:asp inurl:"?cat="',
                    'contains:asp inurl:"?page="',
                    'contains:php inurl:"?cat="',
                    'contains:php inurl:"?id="',
                    'contains:aspx inurl:"?cat="',
                    'contains:aspx inurl:"?id="',
                    'contains:aspx inurl:"?page="',
                    'inurl:"?products="',
                    'inurl:"?prof="',
                    'inbody:"?category_id="',
                    'inbody:"?cmd="',
                    'inbody:"?cb="',
                ]
                all_dorks.update(top_patterns)

        # Save to file
        out_path = SCRIPT_DIR / f"dorks_preset_{preset}.txt"
        out_path.write_text("\n".join(sorted(all_dorks)) + "\n", encoding="utf-8")
        self.dork_file_var.set(str(out_path))
        self._log(f"[preset] Generated {len(all_dorks)} {preset.upper()} dorks → {out_path.name}")

    def _format_for_sqldumper(self):
        """Run the v3.0 multi-pass formatter on the current output.
        Uses format_final.py: smart filter + dork-pollution + diversity + tier classification.
        Output: harvest_final.txt + harvest_final_unique.txt + harvest_final_grouped.txt
                + harvest_scripted.txt (the money file - 48 SCRIPTED targets)
        """
        out_path = self.output_var.get().strip()
        if not out_path or not Path(out_path).exists():
            messagebox.showwarning("No Output", f"Output file not found: {out_path}\nRun a harvest first.")
            return
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            import format_final as ff
            # Use the same base stem for all outputs
            base_stem = Path(out_path).stem
            out_dir = Path(out_path).parent
            fmt_out = out_dir / f"{base_stem}_final.txt"
            sys.argv = ["format_final", "-i", str(out_path), "-o", str(fmt_out)]
            ff.main()
            # Also list all generated files
            generated = sorted(out_dir.glob(f"{base_stem}_final*"))
            msg_lines = [f"Formatted URL list saved to:\n{fmt_out}", ""]
            msg_lines.append("Also generated:")
            for f in generated:
                if f != fmt_out:
                    size = f.stat().st_size
                    msg_lines.append(f"  {f.name} ({size:,} bytes)")
            self._log(f"[fmt] Multi-pass format done → {fmt_out.name}")
            messagebox.showinfo("Format v3 Done", "\n".join(msg_lines))
        except SystemExit:
            pass  # argparse calls sys.exit on --help
        except Exception as e:
            self._log(f"[!] v3 format error: {e}", tag="err")
            # Fallback to v2 (smart filter only)
            try:
                self._log("[*] Falling back to format_v2...", tag="warn")
                import format_v2 as fv2
                fmt_out = Path(out_path).with_name(Path(out_path).stem + "_v2.txt")
                sys.argv = ["format_v2", "-i", str(out_path), "-o", str(fmt_out)]
                fv2.main()
                self._log(f"[fmt] v2 fallback → {fmt_out.name}")
                messagebox.showinfo("Format v2 Fallback", f"Saved to:\n{fmt_out}")
            except Exception as e2:
                self._log(f"[!] v2 fallback also failed: {e2}", tag="err")
                messagebox.showerror("Format Error", f"v3 error: {e}\nv2 error: {e2}")

    def _analyze_yield(self):
        """Analyze dork yield from a harvest to identify best/worst dorks.
        Generates:
          - high_yield_dorks.txt (top tier, re-run these)
          - low_yield_dorks.txt (drop these)
          - yield_report.txt (full per-dork stats)
          - dork_recommendations.txt (actionable steps)
        """
        out_path = self.output_var.get().strip()
        if not out_path or not Path(out_path).exists():
            messagebox.showwarning("No Output", f"Output file not found: {out_path}\nRun a harvest first.")
            return
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            import dork_yield_analyzer as dya
            # Set up to output in same dir as harvest
            out_dir = Path(out_path).parent
            sys.argv = ["dork_yield_analyzer", "-i", str(out_path)]
            dya.main()
            high_path = out_dir / "high_yield_dorks.txt"
            rec_path = out_dir / "dork_recommendations.txt"
            msg = f"Yield analysis complete!\n\n"
            msg += f"Generated files in:\n{out_dir}\n\n"
            if high_path.exists():
                n = sum(1 for _ in high_path.open(encoding="utf-8"))
                msg += f"  • high_yield_dorks.txt ({n} dorks to KEEP)\n"
            msg += f"  • low_yield_dorks.txt (drop these)\n"
            msg += f"  • yield_report.txt (full stats)\n"
            msg += f"  • dork_recommendations.txt (next steps)\n\n"
            msg += "Load 'high_yield_dorks.txt' in this GUI for the next harvest!"
            self._log(f"[yield] Analysis complete → {out_dir}/")
            messagebox.showinfo("Yield Analysis Done", msg)
        except SystemExit:
            pass
        except Exception as e:
            self._log(f"[!] yield analysis error: {e}", tag="err")
            messagebox.showerror("Yield Error", str(e))

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Save output as",
            defaultextension=".txt",
            initialfile="dorkforge_hits.txt",
            initialdir=str(SCRIPT_DIR),
        )
        if path:
            self.output_var.set(path)

    def _browse_sqlite(self):
        path = filedialog.asksaveasfilename(
            title="Save SQLite as",
            defaultextension=".db",
            initialfile="dorkforge_hits.db",
            initialdir=str(SCRIPT_DIR),
        )
        if path:
            self.sqlite_var.set(path)

    def _toggle_all_engines(self):
        all_on = all(v.get() for v in self.engine_vars.values())
        for v in self.engine_vars.values():
            v.set(not all_on)

    # -------------------------------------------------------------- Logging
    def _log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {msg}\n", tag)
        self.log.see("end")

    # ----------------------------------------------------------- Run engine
    def _get_inputs(self):
        dorks = []
        # From file
        if self.dork_file_var.get().strip():
            p = Path(self.dork_file_var.get())
            if p.exists():
                dorks.extend([line.strip() for line in p.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])
            else:
                messagebox.showerror("Error", f"Dork file not found:\n{p}")
                return None
        # From single
        if self.dork_single_var.get().strip():
            dorks.append(self.dork_single_var.get().strip())
        if not dorks:
            messagebox.showerror("Error", "No dorks provided.\nLoad a file or enter a single dork.")
            return None
        engines = [e for e, v in self.engine_vars.items() if v.get()]
        if not engines:
            messagebox.showerror("Error", "No engines selected.")
            return None
        return {
            "dorks": dorks,
            "engines": engines,
            "pages": self.pages_var.get(),
            "workers": self.workers_var.get(),
            "delay_min": self.delay_min_var.get(),
            "delay_max": self.delay_max_var.get(),
            "output": self.output_var.get().strip(),
            "sqlite": self.sqlite_var.get().strip() if self.use_sqlite_var.get() else None,
        }

    def _start(self):
        if self.running:
            return
        if not DORKFORGE_OK:
            messagebox.showerror("Engine import failed",
                                f"Cannot start: {DORKFORGE_ERROR}\n\nMake sure dorkforge.py is in the same folder.")
            return
        cfg = self._get_inputs()
        if not cfg:
            return
        # Reset
        self.stats = {"dorks_done": 0, "urls": 0, "errors": 0, "current": ""}
        self._update_stats()
        self.progress_var.set(0)
        self.running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.worker_thread = threading.Thread(target=self._run_engine, args=(cfg,), daemon=True)
        self.worker_thread.start()
        self._log(f"START: {len(cfg['dorks'])} dorks × {len(cfg['engines'])} engines × {cfg['pages']} pages", "ok")
        self._log(f"Workers: {cfg['workers']} | Delay: {cfg['delay_min']}–{cfg['delay_max']}s", "dim")

    def _stop(self):
        self.running = False
        self._log("STOP requested (will finish current batch)", "warn")

    def _run_engine(self, cfg):
        # Setup
        try:
            Path(cfg["output"]).parent.mkdir(parents=True, exist_ok=True)
            # Truncate
            Path(cfg["output"]).write_text(
                f"# DorkForge GUI | engines={','.join(cfg['engines'])} | "
                f"dorks={len(cfg['dorks'])} | pages/dork={cfg['pages']}\n\n",
                encoding="utf-8",
            )
        except Exception as e:
            self.event_queue.put(("log", f"Output file error: {e}", "err"))
            self.event_queue.put(("done", None))
            return

        # SQLite setup
        sqlite_conn = None
        if cfg["sqlite"]:
            try:
                import sqlite3
                sqlite_conn = sqlite3.connect(cfg["sqlite"])
                sqlite_conn.execute("""
                    CREATE TABLE IF NOT EXISTS hits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT DEFAULT CURRENT_TIMESTAMP,
                        engine TEXT NOT NULL,
                        dork TEXT NOT NULL,
                        url TEXT NOT NULL,
                        UNIQUE(engine, url)
                    )
                """)
                sqlite_conn.commit()
            except Exception as e:
                self.event_queue.put(("log", f"SQLite error: {e}", "err"))
                sqlite_conn = None

        c = Client(use_cffi=True, timeout=25)
        total_jobs = len(cfg["dorks"]) * len(cfg["engines"])
        job_idx = 0

        def process_job(engine, dork, page):
            scraper = Scraper(c, engine, cfg["pages"])
            scraper.delay_min = cfg["delay_min"]
            scraper.delay_max = cfg["delay_max"]
            # Mimic scraper's per-page loop but only fetch one page
            import random
            time.sleep(random.uniform(scraper.delay_min, scraper.delay_max))
            params = scraper._params(dork, page)
            status, html = c.get(scraper.base_url, params)
            if is_blocked(html, status):
                return []
            urls = extract_urls(html, engine)
            return filter_excluded(urls)

        for engine in cfg["engines"]:
            for dork in cfg["dorks"]:
                if not self.running:
                    break
                job_idx += 1
                pct = (job_idx - 1) / total_jobs * 100
                self.event_queue.put(("progress", pct))
                self.event_queue.put(("current", f"{engine}: {dork[:40]}"))
                self.event_queue.put(("log", f"[{engine}] {dork}", "info"))

                all_urls = []
                err = False
                for page in range(1, cfg["pages"] + 1):
                    if not self.running:
                        break
                    import random
                    time.sleep(random.uniform(cfg["delay_min"], cfg["delay_max"]))
                    try:
                        urls = process_job(engine, dork, page)
                        all_urls.extend(urls)
                    except Exception as e:
                        self.event_queue.put(("log", f"  page {page} err: {e}", "err"))
                        err = True

                # Dedup
                seen = set()
                unique = []
                for u in all_urls:
                    if u not in seen:
                        seen.add(u)
                        unique.append(u)

                # Write to TXT
                try:
                    with open(cfg["output"], "a", encoding="utf-8") as f:
                        f.write(f"## dork: {dork} | engine: {engine}\n")
                        for u in unique:
                            f.write(u + "\n")
                        f.write("\n")
                except Exception as e:
                    self.event_queue.put(("log", f"Write error: {e}", "err"))

                # Write to SQLite
                if sqlite_conn and unique:
                    try:
                        sqlite_conn.executemany(
                            "INSERT OR IGNORE INTO hits (engine, dork, url) VALUES (?, ?, ?)",
                            [(engine, dork, u) for u in unique],
                        )
                        sqlite_conn.commit()
                    except Exception as e:
                        self.event_queue.put(("log", f"SQLite insert error: {e}", "err"))

                # Update stats
                self.event_queue.put(("dork_done", len(unique), err))
                for u in unique[:5]:
                    self.event_queue.put(("log", f"  → {u[:120]}", "url"))
                if len(unique) > 5:
                    self.event_queue.put(("log", f"  … and {len(unique) - 5} more", "dim"))

                if not self.running:
                    self.event_queue.put(("log", "Stopped by user.", "warn"))
                    break
            if not self.running:
                break

        if sqlite_conn:
            sqlite_conn.close()
        self.event_queue.put(("done", None))

    def _update_stats(self):
        self.stat_labels["dorks_done"].config(text=str(self.stats["dorks_done"]))
        self.stat_labels["urls"].config(text=str(self.stats["urls"]))
        self.stat_labels["errors"].config(text=str(self.stats["errors"]))
        self.stat_labels["current"].config(text=self.stats["current"] or "—")

    def _poll_events(self):
        try:
            while True:
                ev = self.event_queue.get_nowait()
                kind = ev[0]
                if kind == "log":
                    _, msg, tag = ev
                    self._log(msg, tag)
                elif kind == "progress":
                    _, pct = ev
                    self.progress_var.set(pct)
                elif kind == "current":
                    _, txt = ev
                    self.stats["current"] = txt
                    self._update_stats()
                elif kind == "dork_done":
                    _, n_urls, err = ev
                    self.stats["dorks_done"] += 1
                    self.stats["urls"] += n_urls
                    if err:
                        self.stats["errors"] += 1
                    self._update_stats()
                elif kind == "done":
                    self.running = False
                    self.start_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    self._log(f"DONE — {self.stats['urls']} URLs from {self.stats['dorks_done']} dorks, {self.stats['errors']} errors", "ok")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)


def main():
    root = tk.Tk()
    DorkForgeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
