#
# Workflow parsing/formatting.
#
import os
import json
from PIL import Image

from .utils import log
from .path import get_base_path, get_absolute_path, get_relative_path, verify_extension

def load_json(path):
	"""
	Load the content of the json file at the provided path
	"""
	with open(path, encoding="UTF-8") as f:
		data = json.load(f)
	return data

def load_image_meta(source):
	"""
	Load the metadata/workflow from the input image
	"""
	# todo: check if it's actually a PIL image
	if type(source) == str:
		img = Image.open(source)
	else:
		img = source

	info = {}
	if len(img.info.keys()) == 0:
		return info
	# this is the API format one
	if "prompt" in img.info:
		# yes the prompt is called workflow. I'm not rewriting all of this.
		info["workflow"] = json.loads(img.info["prompt"])
	# this is the one from the UI
	if "workflow" in img.info:
		info["workflow_raw"] = img.info["workflow"]
	# this is for lilium
	if "lilium" in img.info:
		info["lilium"] = json.loads(img.info["lilium"])
	return info

def get_nodes_by_class(workflow, class_type):
	"""
	Get nodes by one or more class types.
	"""
	class_types = [class_type] if type(class_type) == str else class_type
	nodes = []
	for node_id, node in workflow.items():
		if node.get("class_type") in class_types:
			nodes.append(node_id)
	return nodes

def get_nodes_by_title(workflow, title, nodes=None):
	"""
	Filter a list of nodes by their title(s)
	"""
	titles = [title] if type(title) == str else title
	nodes = nodes or workflow.keys()
	# iterate over our nodes
	found = []
	for node_id in nodes:
		title = workflow[node_id].get("_meta",{}).get("title", "Unknown")
		if any(x in title.lower() for x in title):
			found.append(node_id)
	return found

def find_output_image_id(wf):
	"""
	Try and find the node we'll be using as output.
	"""
	img_nodes = get_nodes_by_class(wf, ["SaveImage", "PreviewImage"])
	if len(img_nodes) == 0:
		log("Could not find any output images in workflow", "warning")
		return None
	if len(img_nodes) == 1:
		log("Found single output image in workflow", "debug")
		return img_nodes[0]
	# try and find the right node based on the title
	named_nodes = get_nodes_by_title(wf, ["output"], img_nodes)
	if len(named_nodes) == 0:
		log("Could not find any named output in workflow, picking first", "warning")
		return img_nodes[0]
	if len(named_nodes) == 1:
		log("Found single output image in workflow by title", "debug")
		return named_nodes[0]
	# more than 1 named output
	log("Found more than one named output in workflow, picking first", "warning")
	return named_nodes[0]

def find_input_image_id(wf):
	"""
	Get the input image for the workflow (for the tile)
	"""
	img_nodes = get_nodes_by_class(wf, "LoadImage")
	# missing input image
	if len(img_nodes) == 0:
		log("Workflow doesn't have any input images!", "warning")
		return None
	# single input image - most likely the tile
	if len(img_nodes) == 1:
		log("Found single input image for workflow", "debug")
		return img_nodes[0]
	# try and find the right node based on the title
	named_nodes = get_nodes_by_title(wf, ["input", "tile"], img_nodes)
	if len(named_nodes) == 1:
		log("Found input image for workflow by title", "debug")
		return(named_nodes[0])
	# try and find the image connected to the VAEEncode
	vae_nodes = get_nodes_by_class(wf, ["VAEEncode", "VAEDecodeTiled"])
	if len(vae_nodes) == 1:
		input_node = wf[vae_nodes[0]]["inputs"]["pixels"][0]
		if input_node in img_nodes:
			log("Found input image for workflow based on VAEEncode", "debug")
			return input_node
	# return randomly from the tile ones if we have them
	if len(named_nodes) > 1:
		log("Found multiple input images for workflow by title, picking first", "warning")
		return named_nodes[0]
	# todo: try harder
	log("Couldn't determine workflow input image!", "warning")
	return None

def set_input_image(wf, name):
	"""
	Set workflow input to [name]
	"""
	input_id = find_input_image_id(wf)
	if input_id and name:
		wf[input_id]["inputs"]["image"] = name
		log(f"Set workflow input to '{name}'", "debug")
	return wf

def find_prompt_info(wf, prompt_type):
	"""
	Try to find the id for the positive or negative prompt
	"""
	assert prompt_type in ["positive", "negative"], f"unknown prompt type '{prompt_type}'"

	# just iterate all nodes and hope the user read the readme.
	for node_id, node in wf.items():
		for k,v in node.get("inputs", {}).items():
			if v == f"<{prompt_type.upper()}>":
				log(f"Found {prompt_type} prompt by input text", "debug")
				return {
					"node_id": node_id,
					"input": k,
					"text": "",
				}

	# Find the first sampler we can find
	sampler_nodes = get_nodes_by_class(wf, [
		"KSampler", "KSamplerAdvanced", "SamplerCustom",
		"BNK_TiledKSampler", "BNK_TiledKSamplerAdvanced",
		"UltimateSDUpscale", "UltimateSDUpscaleNoUpscale",
	])
	# we don't have a prompt. maybe using tiled ESRGAN?
	if len(sampler_nodes) == 0:
		log(f"Could not find {prompt_type} prompt", "warning")
		return {}
	# we have more than one prompt. more logic required.
	if len(sampler_nodes) > 1:
		log(f"More than one sampler in workflow, {prompt_type} prompt might be wrong", "warning")

	# trace input of sampler back to text node
	def find_text_cond_node(node_id):
		"""
		recursively search for node with text attribute
		"""
		# check for text
		if "text" in wf[node_id].get("inputs", {}):
			return node_id
		# check for conditioning
		cond_names = [
			"conditioning", # e.g. controlnet
			"conditioning_1", "conditioning_2", # combine
			"conditioning_to", "conditioning_from", # average
		]
		for k in cond_names:
			if k in wf[node_id].get("inputs", {}):
				input_id = find_text_cond_node(wf[node_id]["inputs"][k][0])
				if input_id: return input_id
		# probably not the right node class
		return None

	for node in sampler_nodes:
		input_id = wf[node]["inputs"].get(prompt_type, [None])[0]
		text_node_id = find_text_cond_node(input_id)
		if text_node_id:
			log(f"Found {prompt_type} prompt by tracing sampler input", "debug")
			return {
				"node_id": text_node_id,
				"input": "text",
				"text": wf[text_node_id]["inputs"]["text"]
			}

	# give up
	log(f"Could not find {prompt_type} prompt", "warning")
	return {}

def set_prompt_text(wf, prompt_type, text):
	"""
	Set workflow positive/negative prompt to the passed text
	"""
	info = find_prompt_info(wf, prompt_type)
	if info and text:
		wf[info["node_id"]]["inputs"][info["input"]] = text
		log(f"Set workflow {prompt_type} prompt (id:{info['node_id']}|len:{len(text)})", "debug")
	return wf

def get_prompt_text(wf, prompt_type):
	"""
	Get positive/negative prompt from workflow
	"""
	info = find_prompt_info(wf, prompt_type)
	return info.get("text", "")

def increment_seed(wf, amount):
	"""
	Increment all seeds in the workflow by N
	"""
	return wf

def verify_nodes(wf, workers):
	"""
	Verify all nodes actually exist on all workers.
	"""
	# get a list of the nodes that are present on all workers.
	nodes = set(sum([list(getattr(x, "object_info", {}).keys()) for x in workers], []))
	# iterate all nodes and make sure they're available
	for node in wf.values():
		if not node.get("class_type") in nodes:
			raise ValueError(f"Node '{node.get('class_type')}' missing on one or more workers!")
	log("All nodes present on all workers", "debug")
	return

# nodes that have a path attribute
NODES_WITH_PATH = {
	"CheckpointLoaderSimple" : "ckpt_name",
	"CheckpointLoader"       : "ckpt_name",
	"UpscaleModelLoader"     : "model_name",
	"ControlNetLoader"       : "control_net_name",
	"LoraLoader"             : "lora_name",
	"VAELoader"              : "vae_name",
}

def normalize_workflow_path(wf):
	"""
	Try and replace all '\\' characters with '/'.
	This is only really needed for cross-OS compatibility
	"""
	# get target nodes
	targets = get_nodes_by_class(wf, NODES_WITH_PATH.keys())
	log(f"Normalizing path for {len(targets)} nodes", "debug")
	for k in targets:
		# get the value to replace
		s = NODES_WITH_PATH[wf[k]["class_type"]]
		# if required, change the path separator
		if "\\" in wf[k]["inputs"][s]:
			if "/" in wf[k]["inputs"][s]:
				log(f"Both '\\' and '/' found in model name '{wf[k]['inputs'][s]}'", "warning")
			wf[k]["inputs"][s] = wf[k]["inputs"][s].replace("\\", "/")
	return wf

def format_workflow_path(wf, os):
	"""
	Add windows \\ path separators as required.
	"""
	# already normalized
	if os != "nt":
		return wf
	# needs replacement for windows
	targets = get_nodes_by_class(wf, NODES_WITH_PATH.keys())
	for k in targets:
		# get the value to replace
		s = NODES_WITH_PATH[wf[k]["class_type"]]
		# if required, change the path separator
		if "/" in wf[k]["inputs"][s]:
			wf[k]["inputs"][s] = wf[k]["inputs"][s].replace("/", "\\")
	return wf

def remove_node_attribute(wf, name):
	"""
	Rest all "is_changed" node attributes
	"""
	c = 0
	for node_id, node in wf.items():
		if name in node:
			wf[node_id].pop(name)
			c += 1
	if c > 0:
		log(f"Removed attribute '{name}' from {c} nodes", "debug")
	return wf

def sanitize_workflow(wf):
	"""
	Try and get the workflow in a state where it can be further formatted
	"""
	# normalize all path separators to be '/' instead of '\\'
	wf = normalize_workflow_path(wf)

	# reset "is_changed" attribute since we can't verify it
	wf = remove_node_attribute(wf, "is_changed")

	return wf
