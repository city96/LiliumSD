#
# Saving / metadata logic
#
import os
import json
import torch
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from torchvision.transforms.functional import to_pil_image

from .utils import sanitize, log
from .path import get_new_path_iter, get_relative_path

META_VER = "LiliumSD-1.0"

def format_metadata(meta):
	"""
	Reformat metadata to keep comfy compatibility
	"""
	metadata = PngInfo()
	if not meta:
		return metadata
	meta["version"] = META_VER
	# "prompt"
	if "workflow" in meta:
		metadata.add_text(
			"prompt",
			json.dumps(meta.pop("workflow"))
		)
	# "workflow"
	if "workflow_raw" in meta:
		metadata.add_text(
			"workflow",
			json.dumps(meta.pop("workflow_raw"))
		)
	# custom
	metadata.add_text(
		"lilium",
		json.dumps(meta)
	)
	return metadata

def save_to_disk(mode, images, ext="png", meta=None):
	"""
	Save image to disk with added metadata
	"""

	# construct metadata
	try:
		# check if it can be serialized
		json.dumps(meta)
		info = format_metadata(meta)
	except Exception as e:
		meta = {}
		info = PngInfo()
		log(f"Failed to add output metadata: {e}", "warning")

	# iterate batches (should be 1)
	outputs = []
	gen = get_new_path_iter(mode, ext=ext)
	for img in sanitize(images):
		path = next(gen)
		if os.path.isfile(path):
			raise OSError(f"File exists! {path}")
		# save to disk and track outputs
		to_pil_image(img).save(path, pnginfo=info)
		outputs.append({
			"name": get_relative_path(mode, path),
			"mode": mode,
			"path": path,
			"meta": meta,
		})
	return outputs

def save_temp_image(*args, **kwargs):
	"""
	Save temp image, returns info about saved file(s)
	"""
	return save_to_disk("temp", *args, **kwargs)

def save_output_image(*args, **kwargs):
	"""
	Save image(s) to output directory, returns info about saved file(s)
	"""
	return save_to_disk("output", *args, **kwargs)
