# LiliumSD
## Experimental network-distributed frontend for ComfyUI

![LiliumSD_00072](https://github.com/city96/LiliumSD/assets/125218114/b3dd72f2-29b1-406c-840e-3ec9b5eca8a8)

https://github.com/city96/LiliumSD/assets/125218114/536d5c56-1ca0-447d-b171-a84150dd3159

This is the early-alpha version of *LiliumSD*, a ComfyUI frontend for using multiple networked machines for rendering.

The motivation behind creating this was the fact that all my [5K+](https://imgsli.com/MjMwMzg2) and [8K+](https://imgsli.com/MjMxMTgw) upscales were taking 30+ minutes on Ultimate SD Upscale. *Now they only take 15.*

Tiled upscaling is done with a full workflow for each tile, meaning it's possible to apply ESRGAN/ControlNet/IP adapter/CLIP vision/etc to each part of the image separately, allowing (in theory) greater control.

#### What works:
- Network distributed tiled upscaling
- Metadata saving
- Basic checks/error reporting

#### What needs work:
- Tile processing errors (will infinitely retry sometimes)
- Image preview (currently doesn't always update)
- Sanity checks (postponed due to lack of sanity)
- Frontend error reporting
- Metadata loading

#### What is planned:
- Regular workflows (i.e. initial image search)
- Model/LoRA changing in the UI (verify that they're present on all workers as well)
- Better noise source for coherence (needs custom node or changes to ComfyUI)
- tooltips (probably)

## How to use:

Install requirements using `pip install -r requirements.txt`

Launch via `python main.py`

### Workers

Edit `config.yaml` to match your configuration.

Each worker take two arguments:

- url: The URL for the ComfyUI instance, make sure it is accessible from the PC running LiliumSD
- priority: Determines which GPU should be picked first when dispatching tiles. Slower GPUs should have lower values. 

### Prompt/workflow

Create your workflow for a single tile:

- It should take one input image (you can change the title to "Tile Input" to make sure the right one is selected)
- It should have one output image (Use a PreviewImage node, set the title to "Output Image" if you have more than one)
- Your positive/negative prompt can be named as such, or can have the text "`<POSITIVE>`" or "`<NEGATIVE>`" in the field you wish to insert the prompt from the UI into.
- The workflow should assume that the input is *already upscaled* (input/output are the same size). You'll have to set "Workflow upscale factor" if this isn't the case (see: tiled sampling settings)
- **The models used should be present on all workers**

After you're done, save the image for your single tile (with the embedded metadata) or export it in the API format as a json. You should place this in the "prompts" folder (created on first run), then click "refresh" next to the workflow dropdown.

A simple example workflow you can edit is provided [here](https://github.com/city96/LiliumSD/assets/125218114/a9b4f4f3-113c-4b92-a455-5258205a0f0f) (remember to save either the **image** or the **API JSON**, and **not** the regular workflow json using the save button).

### Tiled sampling settings:

- Upscale input image: The size of the *final* output image. The image is upscaled to this resolution using bicubic first.
- Slicing method: 
  - Nyan Tile: Custom algo using half-tile overlaps and generous padding to sample in a grid/matrix pattern.
  - USDUS: Default tiling logic from ultimate SD Upscale (mode:linear)
  - Simple: Simple algo for maximum concurrency. Will probably look awful.
- Tile size: The size of each tile, based on the size of the output image.
- Tile overlap: What amount of pixels a tile should overlap with the previous one. Needs to be larger than Tile size
- Mask feather: Blur mask edges to hide seams
- Mask padding: how far in the mask should start. Recommended to leave on auto.
- Tile image source: the image the tile workflow receives. It'll either be from the source image, or from the output/final image (i.e. the parts that have been sampled already are passed to the workflow)
- Tile noise source: whether each tile should use it's own noise, or if it should generate the noise based on the entire image, then crop to the target region.
- Force Uniform tile size: All tiles will be size by size, even on the edges of the image.
- Test upscale settings: Verify your settings are correct by running a demo where the tiles are simply darkened one by one.

- Workflow file: the workflow to be used for the tiled upscaling.
- Workflow upscale factor: Change this if your workflow doesn't produce 1:1 images. e.g. takes 512 but upscales it to 1024.

## FAQ

#### Q: Slider input is annoying for precise values
Use the scrollwheel after clicking the slider.

#### Q: Console info too verbose
Add `--loglevel warning` to the launch arguments. Default is debug, but will be lower in the final iterations.

#### Q: Better/more user friendly setup/instructions
Most likely after the UI is at a point where it isn't just a tech demo.

#### Q: Mobile support?
Definitely not.
