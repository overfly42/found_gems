import os
import glob
import numpy as np
import matplotlib

# Choose an interactive backend when a display is available; otherwise use Agg
if os.environ.get("DISPLAY"):
    try:
        matplotlib.use("TkAgg")
    except Exception:
        try:
            matplotlib.use("Qt5Agg")
        except Exception:
            pass
else:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# ---------------------------------------------------------
# Load all CSV files in the current directory
# ---------------------------------------------------------
csv_files = sorted(glob.glob("data/*.csv"))

if len(csv_files) == 0:
    raise RuntimeError("No CSV files found in this folder.")

print(f"Loaded {len(csv_files)} files")

data = []
for f in csv_files:
    grid = np.loadtxt(f)
    data.append(grid)

# Convert to numpy array for easier handling
data = np.array(data)

# ---------------------------------------------------------
# Global color scaling (important for time consistency)
# ---------------------------------------------------------
vmin = data.min()
vmax = data.max()

# ---------------------------------------------------------
# Create the figure
# ---------------------------------------------------------
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.25)

img = ax.imshow(data[0], cmap="coolwarm", vmin=vmin, vmax=vmax)
cbar = plt.colorbar(img, ax=ax)
cbar.set_label("Signal probability / intensity")

title = ax.set_title(f"Frame 0 — {csv_files[0]}")

# ---------------------------------------------------------
# Slider
# ---------------------------------------------------------
ax_slider = plt.axes([0.2, 0.1, 0.6, 0.03])
slider = Slider(
    ax=ax_slider,
    label="Frame",
    valmin=0,
    valmax=len(data) - 1,
    valinit=0,
    valstep=1
)

# ---------------------------------------------------------
# Update function
# ---------------------------------------------------------
def update(val):
    idx = int(slider.val)
    img.set_data(data[idx])
    title.set_text(f"Frame {idx} — {csv_files[idx]}")
    fig.canvas.draw_idle()

slider.on_changed(update)

# ---------------------------------------------------------
# Show viewer or save frames in headless environments
# ---------------------------------------------------------
backend = matplotlib.get_backend().lower()
if backend in ("agg", "cairo"):
    out_dir = "frames_out"
    os.makedirs(out_dir, exist_ok=True)
    for i in range(len(data)):
        img.set_data(data[i])
        title.set_text(f"Frame {i} — {csv_files[i]}")
        fig.savefig(os.path.join(out_dir, f"frame_{i:04d}.png"))
    print(f"No interactive backend ({matplotlib.get_backend()}). Saved {len(data)} frames to '{out_dir}'.")
else:
    plt.show()
