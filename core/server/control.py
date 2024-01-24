#
# Execution / info handling
#
import torch
import asyncio
import aiohttp
from aiohttp import web

from ..mask import MaskBuilder
from ..path import get_absolute_path, verify_extension
from ..utils import sanitize, log
from ..worker import DebugWorker
from ..slicing import get_slicer
from ..control import TiledUpscaleJob
from ..workflow import set_prompt_text, increment_seed

from .workers import get_workers

current_job = None

def start_tiled_upscale_job(data):
	"""
	Setup & launch tiled upscale job
	"""
	slicer_args = data.pop("slicer", {})
	mask_args = data.pop("mask", {})
	job_args = data.pop("job", {})
	wf_args = data.pop("workflow", {})

	# Image
	if "image_data" in job_args:
		# Base 64
		raise NotImplementedError("Base64 image upload not implemented!")
	elif "image_name" in job_args:
		# verify/clean path
		mode = job_args.get("image_mode", "input")
		try:
			path = get_absolute_path(mode, job_args["image_name"])
		except ValueError as e:
			return web.Response(status=403, text=f"403\n{e}")
		except FileNotFoundError as e:
			return web.Response(status=404, text=f"404\n{e}")

		# verify extension
		try:
			verify_extension(path, exception=True)
		except Exception as e:
			return web.Response(status=403, text=f"403\n{e}")

		# todo: not this
		from PIL import Image
		from core.utils import sanitize, channel_fix
		image = channel_fix(sanitize(Image.open(path)))

		# resize - check args
		if not ("image_height" in job_args and "image_width" in job_args):
			if "image_scale" in job_args:
				job_args["image_height"] = int(image.shape[2]*job_args["image_scale"])
				job_args["image_width"] = int(image.shape[3]*job_args["image_scale"])
			else:
				job_args["image_scale"] = 1.0
				job_args["image_height"] = image.shape[2]
				job_args["image_width"] = image.shape[3]
		if "image_scale" not in job_args:
			job_args["image_scale"] = job_args["image_height"]/image.shape[2]

		# apply input resize - if required
		if job_args["image_scale"] != 1.0:
			image = torch.nn.functional.interpolate(
				image,
				size = (
					job_args["image_height"],
					job_args["image_width"],
				),
				mode = "bilinear"
			)
		
		# crop to align to multiples of 8
		image = image[:, :, :(image.shape[2] - image.shape[2]%8), :(image.shape[3] - image.shape[3]%8)]
		
	else:
		return web.Response(status=400, text=f"400\nMissing 'image_name' or 'image_data' in request!")

	# Workers
	if job_args.get("dry_run", False):
		job_workers = []
		for w in [x for x in get_workers() if x.state]:
			job_workers.append(
				DebugWorker(w.url, w.priority, w.name)
			)
		save = False
	else:
		job_workers = get_workers()
		save = True

	# Slicer
	if "name" not in slicer_args:
		return web.Response(status=400, text=f"400\nMissing slicer name!"),
	if slicer_args["name"] == "NyanTile" and job_args.get("tile_source", None) != "out":
		log("Using NyanTile with tile_source!=out.", "note")
	if "size" not in slicer_args:
		slicer_args["size"] = 768
		log("Falling back to default tile size of 768!", "warning")
	slicer = get_slicer(**slicer_args, image=image)

	# Mask
	mask = MaskBuilder(**mask_args)

	# Workflow
	if "workflow" not in wf_args:
		return web.Response(status=400, text=f"400\nNo workflow provided!"),
	wf = wf_args.pop("workflow")
	if "positive_prompt" in wf_args:
		wf = set_prompt_text(wf, "positive", wf_args["positive_prompt"])
	if "negative_prompt" in wf_args:
		wf = set_prompt_text(wf, "negative", wf_args["negative_prompt"])
	if "seed_increment" in wf_args:
		wf = increment_seed(wf, wf_args["seed_increment"])
	job_args["workflow"] = wf

	# Raw workflow for UI compatibility
	if "workflow_raw" in wf_args:
		wfr = wf_args.pop("workflow_raw")
		job_args["workflow_raw"] = wfr

	# Add other args as metadata
	job_args["slicer"] = slicer_args
	job_args["mask"] = mask_args

	# Actual job
	global current_job
	if current_job is not None and not current_job.done():
		return web.Response(status=400, text=f"400\nJob already running!")
	job = TiledUpscaleJob(slicer, image, mask, job_workers, job_args, save=save)
	current_job = job
	current_job.start()
	return web.Response(status=200)

async def exec_api(request):
	"""
	Switch for exec/abort logic
	"""
	global current_job
	cmd = request.match_info.get("command")
	if request.method == "POST" and cmd == "start":
		"""
		Start new job
		"""
		data = await request.json()
		return start_tiled_upscale_job(data)
	elif request.method == "POST" and cmd == "abort":
		"""
		Abort current job
		"""
		if current_job and not current_job.done():
			current_job.abort()
			return web.Response(status=200)
		return web.Response(status=400, text="No active job!")
	elif request.method == "GET" and cmd == "status":
		"""
		Get job status
		"""
		data = {}
		# Idle
		if current_job is None:
			data["status"] = "idle"
		elif current_job.done():
			data["status"] = "idle"
			if current_job.outputs:
				data["output"] = current_job.outputs
			elif current_job.previewer:
				data["output"] = [{"mode":"preview", "name":None},]
				data["preview_changed"] = int(current_job.previewer.changed)
		# Processing
		else:
			data["status"] = "proc"
			data["progress"] = {
				"current": current_job.pbar.n,
				"total": current_job.pbar.total,
				"perc": round(current_job.pbar.n/current_job.pbar.total,2),
			}
			data["progress"]["label"] = current_job.pbar.format_meter(
				current_job.pbar.n,
				current_job.pbar.total,
				current_job.pbar.format_dict.get("elapsed", 1),
				ascii = True,
				unit  = "Tile",
				bar_format = "[{n_fmt}/{total_fmt} | {elapsed}&lt{remaining} | {rate_fmt}{postfix}]",
			).replace("  "," ")
			if current_job.previewer:
				data["preview_changed"] = int(current_job.previewer.changed)
		return web.json_response(data)
	elif request.method == "GET" and cmd == "preview":
		"""
		Get preview image
		"""
		if not current_job:
			return web.Response(status=400, text=f"400\nNo active jobs")
		# todo: definitely not this
		from io import BytesIO
		from PIL import Image
		from torchvision.transforms.functional import to_pil_image
		img = current_job.previewer.get_preview()
		img = to_pil_image(img[0])
		tmp = BytesIO()
		img.save(tmp, "jpeg", subsampling=0, quality=99)
		tmp.seek(0)
		return web.Response(body=tmp.getvalue(), content_type='image/jpeg')
	else:
		return web.Response(status=400, text=f"400\ninvalid request{cmd}")
