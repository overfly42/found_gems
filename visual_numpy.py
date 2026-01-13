import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import glob
import os

# ---------------------------------------------------------
# Load all CSV files in the current directory
# ---------------------------------------------------------
csv_files = sorted(glob.glob("data2/*.csv"))

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
# Show viewer
# ---------------------------------------------------------
plt.show()
