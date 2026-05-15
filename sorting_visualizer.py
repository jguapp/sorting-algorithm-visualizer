import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
import threading

# bar colors - each state gets its own color so you can see what's happening
BAR_COLOR       = "#4a90d9"   # blue  = normal/unsorted
COMPARING_COLOR = "#ff6b6b"   # red   = currently being compared
SORTED_COLOR    = "#6bcb77"   # green = in its final sorted position
PIVOT_COLOR     = "#ffd93d"   # yellow = pivot element (quick sort only)


class SortingVisualizer:

    def __init__(self, root):
        self.root = root
        self.root.title("Sorting Algorithm Visualizer")
        self.root.geometry("1200x750")
        self.root.configure(bg="#1e1e2e")

        # the list of numbers we're sorting
        self.array = []

        # flags to track what the app is doing right now
        self.is_sorting = False
        self.is_paused  = False

        # how long to sleep between each animation step (in seconds)
        # 0.05s = 50ms is the default (1x speed)
        self.speed = 0.05

        # at high speeds, drawing every single step makes the canvas lag behind.
        # draw_skip controls how many steps we skip between redraws.
        # 0 = draw every step, 1 = draw every other step, 3 = draw every 4th, etc.
        self.draw_skip    = 0
        self.skip_counter = 0   # counts up to draw_skip, resets when we actually draw

        # we save the original unsorted array before each sort so the Compare
        # feature can re-run the same data with a different algorithm
        self.original_array  = []
        self.last_run        = None   # dict holding results from the last finished sort
        self.anim_start_time = 0.0    # wall-clock time recorded when animation started
        self.comparing_mode  = False  # True when Compare button triggered the current sort

        # canvas item IDs for the bars and their number labels.
        # we create these once and just move/recolor them each frame instead of
        # deleting and recreating everything - this prevents flickering
        self.bar_items  = []
        self.bar_labels = []

        # threading.Event is used to pause the background sort thread.
        # calling pause_event.set()   lets the thread keep running
        # calling pause_event.clear() makes the thread block until set() is called again
        self.pause_event = threading.Event()
        self.pause_event.set()  # start unpaused

        self.setup_ui()
        self.generate_array()

    # -----------------------------------------------------------------------
    # UI SETUP
    # -----------------------------------------------------------------------

    def setup_ui(self):
        # reusable style dicts so I don't have to repeat bg/fg/font everywhere
        lbl_style = {"bg": "#2a2a3e", "fg": "white", "font": ("Arial", 10)}
        btn_style = {"font": ("Arial", 10, "bold"), "relief": "flat",
                     "padx": 10, "pady": 4, "cursor": "hand2"}

        # ---- top control bar ----
        control_frame = tk.Frame(self.root, bg="#2a2a3e", pady=6)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        col = 0  # track column position so adding/removing controls is easy

        # algorithm dropdown
        tk.Label(control_frame, text="Algorithm:", **lbl_style).grid(row=0, column=col, padx=(10, 2))
        col += 1
        self.algorithm_var = tk.StringVar(value="Bubble Sort")
        self.algo_menu = ttk.Combobox(
            control_frame, textvariable=self.algorithm_var,
            values=["Bubble Sort", "Selection Sort", "Insertion Sort",
                    "Merge Sort", "Quick Sort", "Heap Sort"],
            state="readonly", width=13
        )
        self.algo_menu.grid(row=0, column=col, padx=(0, 8))
        self.algo_menu.bind("<<ComboboxSelected>>", self.on_algorithm_change)
        col += 1

        # array size slider (10 - 75 elements)
        tk.Label(control_frame, text="Size:", **lbl_style).grid(row=0, column=col, padx=(4, 2))
        col += 1
        self.size_var = tk.IntVar(value=50)
        tk.Scale(
            control_frame, from_=10, to=75, orient=tk.HORIZONTAL,
            variable=self.size_var, bg="#2a2a3e", fg="white",
            highlightthickness=0, length=85, font=("Arial", 8)
        ).grid(row=0, column=col, padx=(0, 8))
        col += 1

        # speed multiplier dropdown
        # 1x = 50ms per step (default). higher = faster animation
        tk.Label(control_frame, text="Speed:", **lbl_style).grid(row=0, column=col, padx=(4, 2))
        col += 1
        self.speed_var = tk.StringVar(value="1x")
        speed_menu = ttk.Combobox(
            control_frame, textvariable=self.speed_var,
            values=["0.25x", "0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x", "3x", "4x"],
            state="readonly", width=6
        )
        speed_menu.grid(row=0, column=col, padx=(0, 8))
        speed_menu.bind("<<ComboboxSelected>>", self.update_speed)
        col += 1

        # action buttons
        tk.Button(control_frame, text="Generate",
                  command=self.generate_array, bg="#4a90d9", fg="white",
                  **btn_style).grid(row=0, column=col, padx=3)
        col += 1
        tk.Button(control_frame, text="Sort!",
                  command=self.start_sorting, bg="#4a90d9", fg="white",
                  **btn_style).grid(row=0, column=col, padx=3)
        col += 1
        self.pause_btn = tk.Button(control_frame, text="Pause",
                                   command=self.toggle_pause,
                                   bg="#ffd93d", fg="black", **btn_style)
        self.pause_btn.grid(row=0, column=col, padx=3)
        col += 1
        tk.Button(control_frame, text="Reset",
                  command=self.reset, bg="#ff6b6b", fg="white",
                  **btn_style).grid(row=0, column=col, padx=3)
        col += 1

        # Compare button - stays grayed out until a sort finishes.
        # after a sort, pick a different algorithm and click this to run it
        # on the same array and see a side-by-side stats comparison.
        self.compare_btn = tk.Button(
            control_frame, text="Compare", command=self.start_compare,
            bg="#6bcb77", fg="#1e1e2e", state=tk.DISABLED, **btn_style
        )
        self.compare_btn.grid(row=0, column=col, padx=3)
        col += 1

        # divider between buttons and custom input
        tk.Label(control_frame, text="|", bg="#2a2a3e", fg="#444466",
                 font=("Arial", 18)).grid(row=0, column=col, padx=6)
        col += 1

        # text box where the user can type their own array
        self.custom_entry = tk.Entry(
            control_frame, font=("Arial", 10), width=24,
            bg="#12121f", fg="#888899", insertbackground="white", relief="flat"
        )
        self.custom_entry.grid(row=0, column=col, padx=(0, 4))
        self.custom_entry.insert(0, "e.g. 5, 3, 8, 1, 9, 2")
        self.custom_entry.bind("<FocusIn>", self.clear_placeholder)
        col += 1
        tk.Button(control_frame, text="Load",
                  command=self.load_custom_array, bg="#c678dd", fg="white",
                  **btn_style).grid(row=0, column=col, padx=3)

        # ---- main area: canvas on the left, info panel on the right ----
        main_frame = tk.Frame(self.root, bg="#1e1e2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # the canvas is where the bars get drawn
        self.canvas = tk.Canvas(main_frame, bg="#12121f", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # right side panel shows info about the selected algorithm
        info_frame = tk.Frame(main_frame, bg="#2a2a3e", width=280)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        info_frame.pack_propagate(False)  # don't shrink to fit content

        tk.Label(info_frame, text="Algorithm Info", bg="#2a2a3e", fg="white",
                 font=("Arial", 14, "bold")).pack(pady=10)
        self.info_text = tk.Text(
            info_frame, bg="#1e1e2e", fg="#cccccc",
            font=("Arial", 10), wrap=tk.WORD, relief="flat", padx=10, pady=10
        )
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ---- bottom stats bar ----
        stats_frame = tk.Frame(self.root, bg="#2a2a3e")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # swap count (red)
        self.swaps_label = tk.Label(stats_frame, text="Swaps: 0",
                                    bg="#2a2a3e", fg="#ff6b6b",
                                    font=("Arial", 12, "bold"))
        self.swaps_label.pack(side=tk.LEFT, padx=20)

        # pure algorithm time - how fast the sort runs without any animation delays (green)
        self.algo_time_label = tk.Label(stats_frame, text="Algo Time: --",
                                        bg="#2a2a3e", fg="#6bcb77",
                                        font=("Arial", 12, "bold"))
        self.algo_time_label.pack(side=tk.LEFT, padx=20)

        # animation time - actual wall-clock time the animation took on screen (purple)
        self.anim_time_label = tk.Label(stats_frame, text="Anim Time: --",
                                        bg="#2a2a3e", fg="#c678dd",
                                        font=("Arial", 12, "bold"))
        self.anim_time_label.pack(side=tk.LEFT, padx=20)

        self.status_label = tk.Label(stats_frame, text="Status: Ready",
                                     bg="#2a2a3e", fg="#ffd93d",
                                     font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.RIGHT, padx=20)

        self.update_info()

    # -----------------------------------------------------------------------
    # ALGORITHM INFO PANEL
    # -----------------------------------------------------------------------

    def on_algorithm_change(self, event=None):
        self.update_info()

    def update_info(self):
        # descriptions and complexity data for each algorithm
        info = {
            "Bubble Sort": {
                "time":   "Best: O(n)   Average: O(n²)   Worst: O(n²)",
                "space":  "O(1)",
                "stable": "Yes",
                "desc": (
                    "Bubble sort goes through the list over and over, comparing "
                    "adjacent elements and swapping them if they're out of order. "
                    "Big numbers 'bubble up' to the top each pass.\n\n"
                    "It's really simple to understand but super slow on big arrays. "
                    "You basically wouldn't use this in real life unless the array "
                    "is tiny or already almost sorted."
                )
            },
            "Selection Sort": {
                "time":   "Best: O(n²)   Average: O(n²)   Worst: O(n²)",
                "space":  "O(1)",
                "stable": "No",
                "desc": (
                    "Selection sort finds the smallest element in the unsorted part "
                    "and swaps it to the front. Then finds the next smallest, and so "
                    "on until everything is sorted.\n\n"
                    "It does fewer swaps than bubble sort which is nice, but it still "
                    "has to compare everything so it ends up being the same O(n²). "
                    "Not great but easy to understand."
                )
            },
            "Insertion Sort": {
                "time":   "Best: O(n)   Average: O(n²)   Worst: O(n²)",
                "space":  "O(1)",
                "stable": "Yes",
                "desc": (
                    "Insertion sort works just like sorting cards in your hand. "
                    "You take one element at a time and insert it into its correct "
                    "position among the already-sorted elements.\n\n"
                    "It's actually pretty efficient for small arrays or arrays that "
                    "are almost sorted. That's why a lot of libraries use it for "
                    "small sub-arrays inside faster algorithms."
                )
            },
            "Merge Sort": {
                "time":   "Best: O(n log n)   Average: O(n log n)   Worst: O(n log n)",
                "space":  "O(n)",
                "stable": "Yes",
                "desc": (
                    "Merge sort uses divide and conquer - it keeps splitting the array "
                    "in half until each piece has one element, then merges them back "
                    "together in sorted order.\n\n"
                    "It's guaranteed O(n log n) which is way better than the O(n²) "
                    "algorithms. The downside is it needs extra memory for the temp "
                    "arrays while merging. Good for large datasets though."
                )
            },
            "Quick Sort": {
                "time":   "Best: O(n log n)   Average: O(n log n)   Worst: O(n²)",
                "space":  "O(log n)",
                "stable": "No",
                "desc": (
                    "Quick sort picks a 'pivot' element, then rearranges everything "
                    "so smaller elements go left of the pivot and bigger ones go right. "
                    "Then it recursively does the same for both sides.\n\n"
                    "In practice this is usually the fastest sorting algorithm. "
                    "The worst case is O(n²) but it almost never happens with good "
                    "pivot selection. Most programming languages use this or a "
                    "variation of it."
                )
            },
            "Heap Sort": {
                "time":   "Best: O(n log n)   Average: O(n log n)   Worst: O(n log n)",
                "space":  "O(1)",
                "stable": "No",
                "desc": (
                    "Heap sort builds a max-heap from the array (a tree where every "
                    "parent is bigger than its children), then repeatedly pulls the "
                    "biggest element off the top and puts it at the end.\n\n"
                    "It's O(n log n) guaranteed like merge sort, but doesn't need "
                    "extra memory. The downside is it's usually slower than quicksort "
                    "in practice because of how it jumps around in memory."
                )
            }
        }

        algo = self.algorithm_var.get()
        if algo in info:
            d = info[algo]
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(tk.END, f"{algo}\n\n")
            self.info_text.insert(tk.END, f"Time Complexity:\n{d['time']}\n\n")
            self.info_text.insert(tk.END, f"Space Complexity: {d['space']}\n")
            self.info_text.insert(tk.END, f"Stable Sort: {d['stable']}\n\n")
            self.info_text.insert(tk.END, "How it works:\n\n")
            self.info_text.insert(tk.END, d['desc'])
            self.info_text.config(state=tk.DISABLED)

    # -----------------------------------------------------------------------
    # ARRAY MANAGEMENT
    # -----------------------------------------------------------------------

    def generate_array(self):
        if self.is_sorting:
            return  # don't interrupt a running sort

        size = self.size_var.get()
        self.array = [random.randint(10, 400) for _ in range(size)]

        # new array means old comparison data is no longer valid
        self.last_run = None
        self.compare_btn.config(state=tk.DISABLED)
        self.update_stats(0, 0, 0)

        # clear old bars so draw_array will rebuild them
        self.bar_items  = []
        self.bar_labels = []
        self.canvas.delete("all")

        # prime skip_counter so the very first draw_array call always renders.
        # without this, high-speed settings can skip the first draw and leave
        # a blank canvas after generating
        self.skip_counter = self.draw_skip
        self.draw_array(self.array, [], [])

    def clear_placeholder(self, event):
        # wipe the hint text when the user clicks into the input box
        if self.custom_entry.get().startswith("e.g."):
            self.custom_entry.delete(0, tk.END)

    def load_custom_array(self):
        if self.is_sorting:
            return

        raw = self.custom_entry.get().strip()

        if not raw or raw.startswith("e.g."):
            messagebox.showwarning("No Input", "Type some numbers separated by commas first.")
            return

        try:
            # parse comma-separated input; using float() first lets "3.7" become 3
            nums = [int(float(x.strip())) for x in raw.split(",") if x.strip()]
        except ValueError:
            messagebox.showerror("Bad Input",
                "Please enter only numbers separated by commas.\nExample: 5, 3, 8, 1, 9")
            return

        if len(nums) < 2:
            messagebox.showwarning("Too Short", "Enter at least 2 numbers.")
            return
        if len(nums) > 200:
            messagebox.showwarning("Too Many", "Please enter 200 numbers or fewer.")
            return

        # force everything to be positive so bars always have visible height
        nums = [max(1, abs(n)) for n in nums]

        self.array      = nums
        self.bar_items  = []
        self.bar_labels = []
        self.canvas.delete("all")
        self.update_stats(0, 0, 0)
        self.skip_counter = self.draw_skip  # same blank-canvas fix as generate_array
        self.draw_array(self.array, [], [])
        self.status_label.config(text=f"Status: Loaded {len(nums)} numbers")

    # -----------------------------------------------------------------------
    # SPEED AND STATS
    # -----------------------------------------------------------------------

    def update_speed(self, event=None):
        # each entry maps to (sleep delay in seconds, frame skip level)
        # at 2x and above the canvas can't keep up with every step, so we skip
        # some frames to make the speed difference actually noticeable
        speed_table = {
            "0.25x": (0.20,  0),
            "0.5x":  (0.10,  0),
            "0.75x": (0.067, 0),
            "1x":    (0.05,  0),   # default - 50ms per step
            "1.25x": (0.035, 0),
            "1.5x":  (0.022, 0),
            "2x":    (0.008, 1),   # draw every 2nd step
            "3x":    (0.003, 3),   # draw every 4th step
            "4x":    (0.001, 7),   # draw every 8th step
        }
        self.speed, self.draw_skip = speed_table[self.speed_var.get()]

    def update_stats(self, comparisons, swaps, pure_time, anim_time=None):
        self.swaps_label.config(text=f"Swaps: {swaps}")

        if pure_time == 0:
            self.algo_time_label.config(text="Algo Time: --")
        else:
            self.algo_time_label.config(text=f"Algo Time: {self.format_time(pure_time)}")

        if anim_time is None:
            self.anim_time_label.config(text="Anim Time: --")
        else:
            self.anim_time_label.config(text=f"Anim Time: {self.format_time(anim_time)}")

    def format_time(self, seconds):
        # pick the right unit depending on how big the number is
        ms = seconds * 1000
        if ms < 1:
            return f"{ms:.4f}ms"    # very fast - show 4 decimal places
        if seconds >= 1:
            return f"{seconds:.3f}s"  # over a second
        return f"{ms:.2f}ms"

    # -----------------------------------------------------------------------
    # DRAWING
    # -----------------------------------------------------------------------

    def draw_array(self, arr, comparing=[], sorted_indices=[], pivot_index=None):
        # frame skipping - at 2x+ we can't redraw fast enough to match the speed,
        # so we only redraw every (draw_skip + 1) steps instead of every single one.
        # the final "all green" frame is always drawn regardless (the len check handles that)
        if self.draw_skip > 0 and len(sorted_indices) < len(arr):
            self.skip_counter = (self.skip_counter + 1) % (self.draw_skip + 1)
            if self.skip_counter != 0:
                return  # skip this frame

        canvas_width  = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # the canvas might not be fully drawn yet when the app first opens
        if canvas_width  <= 1: canvas_width  = 900
        if canvas_height <= 1: canvas_height = 500

        n = len(arr)
        if n == 0:
            return

        bar_width = canvas_width / n
        max_val   = max(arr)

        # using sets here because checking "x in set" is O(1) lookup,
        # vs "x in list" which scans the whole list and is O(n)
        comparing_set = set(comparing)
        sorted_set    = set(sorted_indices)

        # if this is a fresh array (or different size), build new canvas objects
        if len(self.bar_items) != n:
            self.canvas.delete("all")
            self.bar_items  = []
            self.bar_labels = []
            for i in range(n):
                rect  = self.canvas.create_rectangle(0, 0, 1, 1, fill=BAR_COLOR, outline="")
                label = self.canvas.create_text(0, 0, text="", fill="white",
                                                font=("Arial", 7), anchor="s")
                self.bar_items.append(rect)
                self.bar_labels.append(label)

        # move and recolor each bar in place (no delete/recreate = no flicker)
        for i in range(n):
            val = arr[i]

            if i in sorted_set:
                color = SORTED_COLOR
            elif i == pivot_index:
                color = PIVOT_COLOR
            elif i in comparing_set:
                color = COMPARING_COLOR
            else:
                color = BAR_COLOR

            bar_height = (val / max_val) * (canvas_height - 25)
            x1 = i * bar_width
            y1 = canvas_height - bar_height
            x2 = x1 + bar_width - 1
            y2 = canvas_height

            self.canvas.coords(self.bar_items[i], x1, y1, x2, y2)
            self.canvas.itemconfig(self.bar_items[i], fill=color)

            # show the value above the bar; shrink font when bars are narrow
            cx        = x1 + bar_width / 2
            font_size = 9 if bar_width >= 28 else 7
            text_y    = max(y1 - 3, 10)
            self.canvas.coords(self.bar_labels[i], cx, text_y)
            self.canvas.itemconfig(self.bar_labels[i], text=str(val),
                                   font=("Arial", font_size), state="normal")

        # tell tkinter to actually push the changes to screen right now
        self.root.update_idletasks()

    # -----------------------------------------------------------------------
    # SORTING CONTROL
    # -----------------------------------------------------------------------

    def check_paused(self):
        # if the user hit Pause, wait here until they hit Resume.
        # returns False if sorting was cancelled so the thread knows to stop.
        self.pause_event.wait()
        return self.is_sorting

    def start_sorting(self):
        if self.is_sorting:
            return
        if not self.array:
            self.generate_array()

        # save a copy of the unsorted array so Compare can reuse it later
        self.original_array  = self.array.copy()
        self.anim_start_time = time.time()

        self.is_sorting   = True
        self.is_paused    = False
        self.skip_counter = 0
        self.compare_btn.config(state=tk.DISABLED)
        self.pause_event.set()
        self.status_label.config(text="Status: Sorting...")

        # run in a background thread so the window stays responsive while sorting
        # daemon=True means the thread automatically stops when the app closes
        sort_thread = threading.Thread(target=self.run_sort, daemon=True)
        sort_thread.start()

    def run_sort(self):
        algo = self.algorithm_var.get()
        arr  = self.array.copy()

        # --- measure pure algorithm speed ---
        # the animation adds sleep() calls that inflate the time, so we run
        # a separate no-sleep version just to get an accurate timing number
        timing_funcs = {
            "Bubble Sort":    self._time_bubble_sort,
            "Selection Sort": self._time_selection_sort,
            "Insertion Sort": self._time_insertion_sort,
            "Merge Sort":     self._time_merge_sort,
            "Quick Sort":     self._time_quick_sort,
            "Heap Sort":      self._time_heap_sort,
        }
        timing_copy = self.array.copy()
        t0        = time.time()
        timing_funcs[algo](timing_copy)
        pure_time = time.time() - t0

        # --- run the animated version ---
        # using single-item lists for counters because Python doesn't let a method
        # directly modify a plain int variable from an outer scope
        comparisons = [0]
        swaps       = [0]

        if algo == "Bubble Sort":
            self.bubble_sort(arr, comparisons, swaps)
        elif algo == "Selection Sort":
            self.selection_sort(arr, comparisons, swaps)
        elif algo == "Insertion Sort":
            self.insertion_sort(arr, comparisons, swaps)
        elif algo == "Merge Sort":
            self.merge_sort(arr, 0, len(arr) - 1, comparisons, swaps)
        elif algo == "Quick Sort":
            self.quick_sort(arr, 0, len(arr) - 1, comparisons, swaps)
        elif algo == "Heap Sort":
            self.heap_sort(arr, comparisons, swaps)

        # only update the screen if the sort finished (wasn't cancelled by Reset)
        if self.is_sorting:
            anim_time  = time.time() - self.anim_start_time
            self.array = arr

            # turn all bars green to signal completion
            self.draw_array(arr, [], list(range(len(arr))))
            self.update_stats(comparisons[0], swaps[0], pure_time, anim_time)
            self.status_label.config(text="Status: Done!")
            self.is_sorting = False

            # package up the results so Compare can use them
            run_result = {
                "algo":      algo,
                "swaps":     swaps[0],
                "pure_time": pure_time,
                "anim_time": anim_time,
                "size":      len(arr),
            }

            if self.comparing_mode and self.last_run is not None:
                # this was a compare run - open the results popup
                prev_run = self.last_run
                self.last_run       = run_result
                self.comparing_mode = False
                # root.after runs on the main thread, which is required for new windows
                self.root.after(0, lambda a=prev_run, b=run_result: self.show_comparison_window(a, b))
            else:
                self.last_run       = run_result
                self.comparing_mode = False

            self.compare_btn.config(state=tk.NORMAL)

    def toggle_pause(self):
        if not self.is_sorting:
            return

        if self.is_paused:
            # resume - signal the sort thread to keep going
            self.is_paused = False
            self.pause_event.set()
            self.pause_btn.config(text="Pause")
            self.status_label.config(text="Status: Sorting...")
        else:
            # pause - the sort thread will block at the next check_paused() call
            self.is_paused = True
            self.pause_event.clear()
            self.pause_btn.config(text="Resume")
            self.status_label.config(text="Status: Paused")

    def reset(self):
        self.is_sorting = False
        self.is_paused  = False
        self.pause_event.set()  # unblock the thread so it can exit cleanly
        self.pause_btn.config(text="Pause")
        self.status_label.config(text="Status: Ready")
        self.generate_array()

    # -----------------------------------------------------------------------
    # COMPARE FEATURE
    # -----------------------------------------------------------------------

    def start_compare(self):
        if self.is_sorting or self.last_run is None:
            return

        algo = self.algorithm_var.get()

        # make sure they actually picked a different algorithm
        if algo == self.last_run["algo"]:
            messagebox.showinfo(
                "Same Algorithm",
                f"The current algorithm is already {algo}.\n"
                "Pick a different one from the dropdown to compare."
            )
            return

        # restore the original unsorted array, then kick off the new sort
        self.comparing_mode = True
        self.array      = self.original_array.copy()
        self.bar_items  = []
        self.bar_labels = []
        self.canvas.delete("all")
        self.skip_counter = self.draw_skip
        self.draw_array(self.array, [], [])
        self.start_sorting()

    def show_comparison_window(self, run_a, run_b):
        win = tk.Toplevel(self.root)
        win.title("Algorithm Comparison")
        win.configure(bg="#1e1e2e")
        win.resizable(False, False)

        tk.Label(win, text="Algorithm Comparison", bg="#1e1e2e", fg="white",
                 font=("Arial", 16, "bold")).grid(
                     row=0, column=0, columnspan=3, pady=(18, 10), padx=30)

        # algorithm name headers
        tk.Label(win, text=run_a["algo"], bg="#2a2a3e", fg="#4a90d9",
                 font=("Arial", 11, "bold"), width=18, pady=8
                 ).grid(row=1, column=1, padx=6, sticky="ew")
        tk.Label(win, text=run_b["algo"], bg="#2a2a3e", fg="#4a90d9",
                 font=("Arial", 11, "bold"), width=18, pady=8
                 ).grid(row=1, column=2, padx=6, sticky="ew")

        # figure out which side wins a given stat (lower is better for all of these)
        def winner(val_a, val_b):
            if val_a < val_b:   return "a"
            elif val_b < val_a: return "b"
            else:               return None  # tie

        # each row: (label, value for A, value for B, which side won)
        rows = [
            ("Array Size",
                str(run_a["size"]),
                str(run_b["size"]),
                None),
            ("Swaps",
                f"{run_a['swaps']:,}",
                f"{run_b['swaps']:,}",
                winner(run_a["swaps"], run_b["swaps"])),
            ("Algorithm Time",
                self.format_time(run_a["pure_time"]),
                self.format_time(run_b["pure_time"]),
                winner(run_a["pure_time"], run_b["pure_time"])),
            ("Animation Time",
                self.format_time(run_a["anim_time"]),
                self.format_time(run_b["anim_time"]),
                winner(run_a["anim_time"], run_b["anim_time"])),
        ]

        for row_num, (label, val_a, val_b, wins) in enumerate(rows, start=2):
            row_bg = "#1e1e2e" if row_num % 2 == 0 else "#252535"  # alternating rows

            tk.Label(win, text=label, bg=row_bg, fg="#aaaacc",
                     font=("Arial", 10), width=16, anchor="w",
                     padx=12, pady=7).grid(row=row_num, column=0, sticky="ew")

            # green = winner, red = loser, white = tie or not comparable
            if wins == "a":
                color_a, color_b = "#6bcb77", "#ff6b6b"
            elif wins == "b":
                color_a, color_b = "#ff6b6b", "#6bcb77"
            else:
                color_a = color_b = "white"

            tk.Label(win, text=val_a, bg=row_bg, fg=color_a,
                     font=("Arial", 10, "bold"), width=18, pady=7
                     ).grid(row=row_num, column=1)
            tk.Label(win, text=val_b, bg=row_bg, fg=color_b,
                     font=("Arial", 10, "bold"), width=18, pady=7
                     ).grid(row=row_num, column=2)

        tk.Button(win, text="Close", command=win.destroy,
                  bg="#4a90d9", fg="white", font=("Arial", 10, "bold"),
                  relief="flat", padx=14, pady=5
                  ).grid(row=len(rows) + 2, column=0, columnspan=3, pady=16)

    # -----------------------------------------------------------------------
    # SORTING ALGORITHMS  (animated - include draw and sleep calls)
    # -----------------------------------------------------------------------

    def bubble_sort(self, arr, comparisons, swaps):
        n = len(arr)
        for i in range(n):
            swapped = False
            # after each full pass the largest unsorted element ends up at the back,
            # so we shrink the range by 1 each time
            for j in range(0, n - i - 1):
                if not self.check_paused():
                    return

                comparisons[0] += 1
                self.draw_array(arr, [j, j + 1], list(range(n - i, n)))
                time.sleep(self.speed)

                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    swaps[0] += 1
                    swapped = True

                self.update_stats(comparisons[0], swaps[0], 0)

            # if nothing swapped this pass, the array is already sorted
            if not swapped:
                break

    def selection_sort(self, arr, comparisons, swaps):
        n = len(arr)
        sorted_indices = []

        for i in range(n):
            min_idx = i  # assume the current position holds the minimum
            for j in range(i + 1, n):
                if not self.check_paused():
                    return

                comparisons[0] += 1
                self.draw_array(arr, [j, min_idx], sorted_indices)
                time.sleep(self.speed)

                if arr[j] < arr[min_idx]:
                    min_idx = j  # found something smaller

                self.update_stats(comparisons[0], swaps[0], 0)

            if min_idx != i:
                arr[i], arr[min_idx] = arr[min_idx], arr[i]
                swaps[0] += 1

            sorted_indices.append(i)

    def insertion_sort(self, arr, comparisons, swaps):
        # like sorting playing cards - pick one up and slide it left until it fits
        for i in range(1, len(arr)):
            key   = arr[i]   # the element we're inserting
            j     = i - 1
            moved = False

            # shift everything bigger than key one spot to the right
            while j >= 0 and arr[j] > key:
                if not self.check_paused():
                    return

                comparisons[0] += 1
                arr[j + 1] = arr[j]
                moved = True

                self.draw_array(arr, [j, j + 1], list(range(i)))
                time.sleep(self.speed)
                self.update_stats(comparisons[0], swaps[0], 0)

                j -= 1

            arr[j + 1] = key  # place the element in its correct spot
            comparisons[0] += 1
            if moved:
                swaps[0] += 1  # one swap per element placed, not per shift

    def merge_sort(self, arr, left, right, comparisons, swaps):
        if left < right:
            mid = (left + right) // 2
            # keep splitting in half until we have single elements
            self.merge_sort(arr, left, mid, comparisons, swaps)
            self.merge_sort(arr, mid + 1, right, comparisons, swaps)
            self.merge(arr, left, mid, right, comparisons, swaps)

    def merge(self, arr, left, mid, right, comparisons, swaps):
        # copy both halves into temp arrays so we don't overwrite data we still need
        left_arr  = arr[left : mid + 1]
        right_arr = arr[mid + 1 : right + 1]

        i = 0       # pointer for left_arr
        j = 0       # pointer for right_arr
        k = left    # pointer for where we're writing back to arr

        # compare the front of each half and place the smaller one
        while i < len(left_arr) and j < len(right_arr):
            if not self.check_paused():
                return

            comparisons[0] += 1
            if left_arr[i] <= right_arr[j]:
                arr[k] = left_arr[i]
                i += 1
            else:
                arr[k] = right_arr[j]
                j += 1
                swaps[0] += 1  # right-side element jumped ahead of left-side elements

            self.draw_array(arr, [k], [])
            time.sleep(self.speed)
            self.update_stats(comparisons[0], swaps[0], 0)
            k += 1

        # copy whatever is left over in either half
        while i < len(left_arr):
            arr[k] = left_arr[i]
            i += 1
            k += 1

        while j < len(right_arr):
            arr[k] = right_arr[j]
            j += 1
            k += 1

    def quick_sort(self, arr, low, high, comparisons, swaps):
        if low < high:
            # partition puts the pivot in its correct spot and returns that index
            pivot_idx = self.partition(arr, low, high, comparisons, swaps)
            # sort everything to the left and right of the pivot
            self.quick_sort(arr, low, pivot_idx - 1, comparisons, swaps)
            self.quick_sort(arr, pivot_idx + 1, high, comparisons, swaps)

    def partition(self, arr, low, high, comparisons, swaps):
        pivot = arr[high]  # always use the last element as pivot
        i = low - 1        # i is the boundary between "smaller" and "bigger" sections

        for j in range(low, high):
            if not self.check_paused():
                return low

            comparisons[0] += 1
            self.draw_array(arr, [j], [], pivot_index=high)
            time.sleep(self.speed)

            # if this element is smaller than the pivot it belongs on the left
            if arr[j] <= pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]
                swaps[0] += 1

            self.update_stats(comparisons[0], swaps[0], 0)

        # move the pivot to its final sorted position
        arr[i + 1], arr[high] = arr[high], arr[i + 1]
        swaps[0] += 1
        return i + 1

    def heap_sort(self, arr, comparisons, swaps):
        n = len(arr)

        # phase 1: build a max-heap (parent is always bigger than its children)
        # start from the last non-leaf node and sift everything down
        for i in range(n // 2 - 1, -1, -1):
            self.heapify(arr, n, i, comparisons, swaps)

        # phase 2: pull the max (root) off the heap and place it at the end,
        # then fix the heap again - repeat until sorted
        for i in range(n - 1, 0, -1):
            if not self.check_paused():
                return

            arr[0], arr[i] = arr[i], arr[0]  # root is the largest, send it to back
            swaps[0] += 1

            self.draw_array(arr, [0, i], list(range(i, n)))
            time.sleep(self.speed)

            self.heapify(arr, i, 0, comparisons, swaps)  # restore heap property

    def heapify(self, arr, n, i, comparisons, swaps):
        # makes sure the subtree rooted at index i satisfies the max-heap property.
        # if a child is bigger than the parent, swap them, then recurse down.
        largest = i
        left    = 2 * i + 1   # left child is at 2i+1 in a 0-indexed array
        right   = 2 * i + 2   # right child is at 2i+2

        if left < n:
            comparisons[0] += 1
            if arr[left] > arr[largest]:
                largest = left

        if right < n:
            comparisons[0] += 1
            if arr[right] > arr[largest]:
                largest = right

        if largest != i:
            arr[i], arr[largest] = arr[largest], arr[i]
            swaps[0] += 1

            if self.is_sorting:
                self.draw_array(arr, [i, largest], [])
                time.sleep(self.speed / 2)
                self.update_stats(comparisons[0], swaps[0], 0)

            self.heapify(arr, n, largest, comparisons, swaps)

    # -----------------------------------------------------------------------
    # TIMING VERSIONS  (no animation - just raw speed measurement)
    # -----------------------------------------------------------------------
    # these are the same algorithms as above but with all draw_array() and
    # time.sleep() calls removed so we can time the pure algorithm performance

    def _time_bubble_sort(self, arr):
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]

    def _time_selection_sort(self, arr):
        n = len(arr)
        for i in range(n):
            min_idx = i
            for j in range(i + 1, n):
                if arr[j] < arr[min_idx]:
                    min_idx = j
            arr[i], arr[min_idx] = arr[min_idx], arr[i]

    def _time_insertion_sort(self, arr):
        for i in range(1, len(arr)):
            key = arr[i]
            j   = i - 1
            while j >= 0 and arr[j] > key:
                arr[j + 1] = arr[j]
                j -= 1
            arr[j + 1] = key

    def _time_merge_sort(self, arr):
        if len(arr) <= 1:
            return
        mid   = len(arr) // 2
        left  = arr[:mid]
        right = arr[mid:]
        self._time_merge_sort(left)
        self._time_merge_sort(right)
        i = j = k = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                arr[k] = left[i]
                i += 1
            else:
                arr[k] = right[j]
                j += 1
            k += 1
        while i < len(left):
            arr[k] = left[i]
            i += 1
            k += 1
        while j < len(right):
            arr[k] = right[j]
            j += 1
            k += 1

    def _time_quick_sort(self, arr):
        if len(arr) <= 1:
            return
        pivot = arr[len(arr) // 2]
        left  = [x for x in arr if x < pivot]
        mid   = [x for x in arr if x == pivot]
        right = [x for x in arr if x > pivot]
        self._time_quick_sort(left)
        self._time_quick_sort(right)
        arr[:] = left + mid + right

    def _time_heap_sort(self, arr):
        n = len(arr)
        for i in range(n // 2 - 1, -1, -1):
            self._heapify_simple(arr, n, i)
        for i in range(n - 1, 0, -1):
            arr[0], arr[i] = arr[i], arr[0]
            self._heapify_simple(arr, i, 0)

    def _heapify_simple(self, arr, n, i):
        largest = i
        left    = 2 * i + 1
        right   = 2 * i + 2
        if left  < n and arr[left]  > arr[largest]: largest = left
        if right < n and arr[right] > arr[largest]: largest = right
        if largest != i:
            arr[i], arr[largest] = arr[largest], arr[i]
            self._heapify_simple(arr, n, largest)


# start the app
if __name__ == "__main__":
    root = tk.Tk()
    app  = SortingVisualizer(root)
    root.mainloop()
