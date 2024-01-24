#
# Static file / media handling
#
import os
import hashlib
import asyncio
import aiohttp
from io import BytesIO
from PIL import Image
from aiohttp import web

from ..utils import log
from ..path import get_base_path, get_new_path, get_absolute_path, get_relative_path, verify_extension
from ..workflow import load_image_meta, get_prompt_text

async def static_api(request):
	"""
	Handle static files from the web folder
	"""
	# special - index
	if str(request.url.relative()) in ["/", "/index.html"]:
		return web.FileResponse(f"{get_base_path('web')}/index.html")
	# verify path
	name = str(request.url.relative())[1:] # leading '/'
	try:
		path = get_absolute_path("web", name)
	except ValueError as e:
		return web.Response(status=403, text=f"403\n{e}")
	except FileNotFoundError as e:
		return web.Response(status=404, text=f"404\n{e}")
	# verify extension
	if verify_extension(path, ["html","css","png","ico"]):
		return web.FileResponse(path)
	elif verify_extension(path, "js"):
		return web.FileResponse(path, headers={"Content-Type" : "application/javascript"})
	else:
		return web.Response(status=403, text="403")

async def media_api(request):
	"""
	Handle dynamic files from input/output/temp folder
	"""
	mode = request.match_info.get("mode")
	name = request.match_info.get("name")
	# verify path
	try:
		path = get_absolute_path(mode, name)
	except ValueError as e:
		return web.Response(status=403, text=f"403\n{e}")
	except FileNotFoundError as e:
		return web.Response(status=404, text=f"404\n{e}")
	# verify extension
	if not verify_extension(path):
		return web.Response(status=403, text="403")
	# return file
	return web.FileResponse(path)


async def upload_api(request):
	"""
	Handle file uploads
	"""
	data = await request.post()
	image = data["image"]
	meta = {}
	raw = image.file.read()

	# Verify that it's a real image
	try:
		img = Image.open(image.file.raw) # todo: move to load.py or something
		try: 
			# load optional metadata
			meta = load_image_meta(img)
			# also parse the prompts
			meta["positive_prompt"] = get_prompt_text(meta["workflow"], "positive")
			meta["negative_prompt"] = get_prompt_text(meta["workflow"], "negative")
		except Exception as e:
			log(f"Failed to parse metadata for uploaded image {e}", "warning")
			pass
	except:
		return web.Response(status=400, text="Invalid/corrupt image!")

	# Check path/extension/etc
	fname = image.filename
	try:
		path = get_absolute_path("input", fname, False)
	except:
		return web.Response(status=400, text="Invalid filename!")
	if not verify_extension(path):
		return web.Response(status=400, text="Invalid extension!")

	# Avoid duplicates if it's the exact same file that's already on the disk
	if os.path.isfile(path):
		with open(path, "rb") as f:
			raw_disk = f.read()
		disk_hash = hashlib.sha256(raw_disk).hexdigest()
		file_hash = hashlib.sha256(raw).hexdigest()
		if disk_hash == file_hash:
			return web.json_response({
				"mode": "input",
				"name": get_relative_path("input", path),
				"meta": meta,
			})

	# Get a filename to save to
	if os.path.isfile(path):
		name, ext = os.path.splitext(fname)
		path = get_new_path(
			ext = ext[1:].lower(),
			mode = "input",
			prefix = name,
			append = False,
			zeropad = 0
		)

	# dump image to disk
	with open(path, "wb") as f:
		f.write(raw)

	# return path to saved file
	return web.json_response({
		"mode": "input",
		"name": get_relative_path("input", path),
		"meta": meta,
	})
