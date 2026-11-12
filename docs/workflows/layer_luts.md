# Workflow: layer two LUTs into one

Builds one `.cube` file that applies a first LUT and then a second LUT on top. The app uses it so a clip's color choice and look choice, made separately, end up as a single LUT on the clip.

**File:** `resolve_mcp/workflows/layer_luts.py` (uses `resolve_mcp/cube.py`; needs numpy, so run it with the project's `.venv`)
**Resolve API used:** none. This is pure Python.

## Command line

```bash
.venv/bin/python -m resolve_mcp.workflows.layer_luts luts/NIGHT_COLOR_2_33Pt.cube luts/NIGHT_5_33Pt.cube
```

The first file is applied first and the second on top. It prints the path of the layered file. Options: `--out-dir`, `--size` (default 65) and `--overwrite`.

## From Python

```python
from resolve_mcp.workflows.layer_luts import layered_lut, split_name

path = layered_lut("luts/NIGHT_COLOR_2_33Pt.cube", "luts/NIGHT_5_33Pt.cube")
split_name(path)    # ('NIGHT_5_33Pt', 'NIGHT_COLOR_2_33Pt')
```

## Behaviour notes

- **Name:** `<second>__<first>.cube`, e.g. `NIGHT_5_33Pt__NIGHT_COLOR_2_33Pt.cube` (look, then the color underneath it). `split_name` reads the two parts back, which is how the app knows what a clip has.
- **Where:** a `combined/` folder beside the second LUT (`luts/combined/`), unless `--out-dir` is given. An existing file is reused.
- **Size:** 65 points, finer than the 33-point sources, so little is lost. Each file is about 5–6 MB and takes about a second to build.
- **Accuracy:** against applying the two LUTs one after the other, the average difference is 0.013%. The largest, 3.9%, is at hard clipping edges. In Resolve, a clip with the layered LUT matched the app's two-step preview at 48.9 dB PSNR, which is visually identical.
- Files are built only when a combination is actually applied, so `luts/combined/` holds just the combinations in use. It's safe to delete; files are rebuilt when needed.
