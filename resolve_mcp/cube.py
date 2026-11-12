"""Read, write, apply and combine 3D .cube LUTs (needs numpy; use the project's .venv).

A LUT is held as an array `t` of shape (N, N, N, 3) indexed t[r, g, b] -> (R, G, B),
with inputs and outputs in 0-1.
"""

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722])   # Rec.709, what Resolve's YRGB math uses


def read_cube(path):
    size, rows = None, []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("LUT_3D_SIZE"):
                size = int(s.split()[1])
            elif s[0].isdigit() or s[0] in "-.":
                rows.append(s.split()[:3])
    if not size or len(rows) != size ** 3:
        raise ValueError(f"{path}: not a 3D .cube LUT (size {size}, {len(rows)} rows)")
    data = np.array(rows, dtype=np.float64).reshape(size, size, size, 3)   # file order: b, g, r (r fastest)
    return np.ascontiguousarray(data.transpose(2, 1, 0, 3))                # -> t[r, g, b]


def write_cube(path, t, title="latest avenue resolve"):
    size = t.shape[0]
    data = t.transpose(2, 1, 0, 3).reshape(-1, 3)
    with open(path, "w") as f:
        f.write(f'TITLE "{title}"\nLUT_3D_SIZE {size}\n\n')
        f.write("\n".join(f"{r:.7g} {g:.7g} {b:.7g}" for r, g, b in data))
        f.write("\n")


def apply_lut(t, rgb):
    """Trilinear lookup. rgb: (..., 3) array in 0-1. Returns the same shape."""
    n = t.shape[0]
    x = np.clip(np.asarray(rgb, dtype=np.float64), 0, 1) * (n - 1)
    i0 = np.minimum(np.floor(x).astype(int), n - 2)
    f = x - i0
    out = np.zeros(x.shape)
    for dr in (0, 1):
        for dg in (0, 1):
            for db in (0, 1):
                w = (np.where(dr, f[..., 0], 1 - f[..., 0]) * np.where(dg, f[..., 1], 1 - f[..., 1])
                     * np.where(db, f[..., 2], 1 - f[..., 2]))
                out += w[..., None] * t[i0[..., 0] + dr, i0[..., 1] + dg, i0[..., 2] + db]
    return out


def identity(size):
    a = np.linspace(0, 1, size)
    r, g, b = np.meshgrid(a, a, a, indexing="ij")
    return np.stack([r, g, b], axis=-1)


def neutral_axis(t):
    """What the LUT does to greys: (levels, rgb_out) for r=g=b at each grid step."""
    n = t.shape[0]
    idx = np.arange(n)
    return np.linspace(0, 1, n), t[idx, idx, idx]


def layer(first, second, size=65):
    """One LUT that does `first` and then `second` (like two LUT nodes in a row), as a size^3 table."""
    return apply_lut(second, apply_lut(first, identity(size)))
