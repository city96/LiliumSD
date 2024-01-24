#
# Workflow/metadata handling
#
import os
import asyncio
import aiohttp
from aiohttp import web

from ..utils import log
from ..path import get_base_path, get_absolute_path, get_relative_path, verify_extension
from ..workflow import load_json, load_image_meta, sanitize_workflow, set_input_image, find_output_image_id, get_prompt_text, verify_nodes

from .workers import get_workers

def get_workflow_info(path, workers=[]):
	"""
	Get info about workflow based on path
	"""
	# load the workflow that was provided
	if verify_extension(path, "png"):
		info = load_image_meta(path)
		wf = info["workflow"]
	elif verify_extension(path, "json"):
		wf = load_json(path)
		info = {}
	else:
		raise ValueError("Invalid File extension.")
	assert wf, "Empty workflow!"

	# todo: possibly figure out how to convert the normal one to the api format.
	assert "nodes" not in wf, "Workflow not in API format!"

	# apply initial cleanup (see workflow.py)
	wf = sanitize_workflow(wf)

	# verify that the workflow can accept an input image.
	# change it here so it won't run with a random image from the original wf.
	wf = set_input_image(wf, "LiliumSD.png")

	# try and find the output image
	out_id = find_output_image_id(wf)

	# verify that we can change the prompt
	positive_prompt = get_prompt_text(wf, "positive")
	negative_prompt = get_prompt_text(wf, "negative")

	# Verify that none of the changes caused incompatibilities (ignore debug/failed)
	workers = [x for x in workers if x.state not in ["fail","lock"]]
	if len(workers) > 0 and all(["Debug" not in str(type(x)) for x in workers]):
		verify_nodes(wf, workers)

	# build settings dict to return
	return {
		"workflow": wf,
		"workflow_raw": info.get("workflow_raw", None),
		"output_image_id": out_id,
		"positive_prompt": positive_prompt,
		"negative_prompt": negative_prompt,
	}

def list_all_workflows():
	"""
	List all available workflows in folder
	"""
	wf_dir = get_base_path("prompt")
	wf_list = []
	for name in sorted(os.listdir(wf_dir)):
		path = os.path.join(wf_dir, name)
		try:
			verify_extension(path, ["json", "png"], exception=True)
			path = get_relative_path("prompt", name)
			wf_list.append(path)
		except:
			log(f"Ignoring file '{name}' in workflow dir.", "debug")
	return wf_list

async def meta_api(request):
	cmd = request.match_info.get("command")
	if cmd == "workflow_list":
		return web.json_response(list_all_workflows())
	elif cmd in ["workflow", "image"]:
		# check args/input
		if "name" not in request.rel_url.query:
			return web.Response(status=400, text=f"400\nNo workflow name provided!")
		mode = request.rel_url.query.get("mode", "prompt")
		name = request.rel_url.query.get("name")
		try:
			path = get_absolute_path(mode, name)
		except Exception as e:
			log(f"Failed to load workflow for {name}: {e}", "error")
			return web.Response(status=400, text=f"400\n{e}")

		# formatted workflow
		if cmd == "workflow":
			try:
				data = get_workflow_info(path, workers=get_workers())
				return web.json_response(data)
			except Exception as e:
				log(f"Failed to load workflow for {name}: {e}", "error")
				return web.Response(status=400, text=f"400\n{e}")

		# raw metadata
		if cmd == "image":
			try:
				data = load_image_meta(path)
				return web.json_response(data)
			except Exception as e:
				log(f"Failed to load metadata for {name}: {e}", "error")
				return web.Response(status=400, text=f"400\n{e}")

		return web.Response(status=404)
	else:
		return web.Response(status=404)
