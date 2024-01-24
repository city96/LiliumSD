#
# Main backend
#
import os
import time
import json
import torch
import requests
import traceback
from io import BytesIO
from PIL import Image
from copy import deepcopy
from threading import Lock
from urllib.parse import urlparse
from urllib.error import URLError
from torchvision.transforms.functional import to_pil_image

from .utils import sanitize, log
from .workflow import format_workflow_path, set_input_image, set_prompt_text, find_output_image_id

TIMEOUT = 8
MAX_FAILURES = 1000

### Comfy UI backend ###
class ComfyUIWorker:
	"""
	Main class for ComfyUI backend
	"""
	def __init__(self, url, priority=1.0, name=None):
		url = urlparse(url)
		self.url = f"{url.scheme}://{url.netloc}"
		self.host = url.hostname
		self.port = url.port
		self.worker_id = url.netloc # should be unique enough
		self.priority = priority
		self.priority_init = priority
		# Can be "idle", "proc", "fail", "lock"
		self.state = "init"
		self.state_old = "init"
		self.fails = 0
		self.lock = Lock()

		try:
			self.parse()
			self.name = name or f"{self.gpu}"
			self.state = "idle"
		except Exception as e:
			self.name = "Unknown"
			self.state = "fail"
			log(f"Worker init. failed for {self.worker_id}", "warning")

	def request(self, endpoint, timeout=TIMEOUT):
		"""
		Simple abstraction for get request w/ default timeout
		"""
		url = f"{self.url}/{endpoint}"
		r = requests.get(url, timeout=timeout)
		r.raise_for_status()
		return r.json()

	def parse_system_info(self):
		"""
		Try to load all relevant (static) info about remote worker.
		"""
		data = self.request("system_stats")
		self.os = data["system"]["os"]
		self.gpu  = data["devices"][0]["name"].split(' : ')[0].split(' ', 1)[-1].strip()
		self.vram = round(data["devices"][0]["vram_total"] / 1024**3, 2)

		# Shorten GPU name
		# for prefix in ["NVIDIA GeForce ", "Tesla ", "AMD Radeon "]:
			# if self.gpu.startswith(prefix):
				# self.gpu = self.gpu[len(prefix):]

	def parse_status(self):
		"""
		Try to load/update dynamic info about remote worker.
		"""
		# don't try to check client we know is failed/locked
		if self.state in ["fail", "lock"]:
			return
		# don't poll remote if state hasn't changed
		if self.state == self.state_old:
			return
		else:
			self.state_old = self.state
		# handle remote info
		data = self.request("system_stats")
		self.vram_free = round(data["devices"][0]["vram_free"] / 1024**3, 2)
		self.vram_perc = round(1.0 - data["devices"][0]["vram_free"] / data["devices"][0]["vram_total"], 2)

	def parse_models(self):
		"""
		Get list of available models/LoRAs/etc.
		"""
		data = self.request("object_info")
		self.models = {
			"checkpoint": data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0],
			"loras": data["LoraLoader"]["input"]["required"]["lora_name"][0],
			"vae": data["VAELoader"]["input"]["required"]["vae_name"][0],
			"controlnet": data["ControlNetLoader"]["input"]["required"]["control_net_name"][0],
			"upscale_models": data["UpscaleModelLoader"]["input"]["required"]["model_name"][0],
		}
		# replace windows os.sep with linux version to allow comparison
		for key,val in self.models.items():
			out = []
			for name in val:
				if "/" in name and "\\" in name:
					log(f"Model name contains both `\\\\` and `/` '{name}'!", "warning")
				name = name.replace('\\','/')
				out.append(name)
			self.models[key] = out
		# save the object info for workflow parsing
		self.object_info = data

	def parse(self):
		"""
		Load/refresh all stored info about client.
		"""
		self.parse_system_info()
		self.parse_status()
		self.parse_models()

	def fail(self):
		"""
		Logic for logging failures
		"""
		self.fails += 1
		self.priority -= 0.001 # lower priority a small bit for each failure
		if MAX_FAILURES and self.fails >= MAX_FAILURES:
			with self.lock:
				self.state = "fail"

	def reset(self):
		"""
		Cleanup between runs
		"""
		with self.lock:
			assert self.state == "idle","Can't reset busy/failed worker!"
		self.fails = 0
		self.priority = self.priority_init

	def abort(self):
		"""
		Abort current process immediately
		"""
		if self.state in ["fail", "lock"]:
			return
		try:
			self.clear_queue()
		except Exception as e:
			log(f"Failed to clear queue for {self.worker_id}! [{e}]", "warning")
		with self.lock:
			self.state = "idle"

	def get_info(self):
		"""
		Return dict containing all relevant data about worker
		"""
		info = {
			"id"  : self.worker_id,
			"url" : self.url,
			"name": self.name,
			"host": self.host,
			"port": self.port,
			"state": self.state,
			"priority": self.priority,
		}
		if self.state != "fail":
			info.update({
				"system_stats": {
					"gpu" : self.gpu,
					"vram": self.vram,
					"vram_free": self.vram_free,
					"vram_perc": self.vram_perc,
				},
				"models": self.models,
			})
		return info

	def upload_image(self, image, name=None):
		"""
		Upload passed image to the remote worker
		"""
		img = to_pil_image(image[0])
		tmp = BytesIO()
		img.save(tmp, 'png')
		tmp.seek(0)

		name = name or f"LiliumSD-{self.port}.png"

		ul_start = time.time()
		r = requests.post(
			f"{self.url}/upload/image",
			files = {"image": (name, tmp)},
			data  = {"overwrite" : "true"},
			timeout = TIMEOUT,
		)
		r.raise_for_status()
		log(f"Upload done {time.time()-ul_start:.2f}", "debug")

	def run_workflow(self, workflow):
		"""
		Dispatch workflow to remote worker
		"""
		job_id = f"LiliumSD-{int(time.time())}"
		data = {
			"prompt": workflow,
			"client_id": "LiliumSD",
			"extra_data": {
				"job_id": job_id,
			}
		}
		r = requests.post(f"{self.url}/prompt", json=data, timeout=TIMEOUT)
		r.raise_for_status()
		return job_id

	def download_image(self, job_id, output_id=None):
		"""
		Retrieve final processed image from worker
		"""
		out = None
		tc = 0
		while not out:
			data = self.request("history")
			if not data:
				time.sleep(0.3)
				continue
			for i,d in data.items():
				if d["prompt"][3].get("job_id") == job_id:
					if output_id in d["outputs"]:
						out = d["outputs"][output_id]["images"]
					else:
						out = d["outputs"][list(d["outputs"].keys())[-1]]["images"]
			time.sleep(0.3)
			tc += 1
			if tc >= 180/0.3:
				raise Exception("Shard timed out!")
			if self.state != "proc":
				raise Exception("Shard interrupted!")

		dl_start = time.time()
		img = None
		for i in out:
			img_url = f"{self.url}/view?filename={i['filename']}&subfolder={i['subfolder']}&type={i['type']}"
			r = requests.get(img_url, timeout=TIMEOUT)
			r.raise_for_status()
			img = Image.open(BytesIO(r.content))
			break
		log(f"Download done {time.time()-dl_start:.2f}", "debug")
		if not img:
			raise Exception("Shard never returned image!")
		return sanitize(img)

	def clear_queue(self, client_id="LiliumSD"):
		"""
		Stop all running workflows on remote instance.
		"""
		queue = self.request("queue")
		# in queue
		to_cancel = []
		for k in queue.get("queue_pending", []):
			if k[3].get("client_id") == client_id:
				to_cancel.append(k[1]) # job UUID
		r = requests.post(
			f"{self.url}/queue",
			json = {"delete" : to_cancel},
			timeout = TIMEOUT,
		)
		r.raise_for_status()

		# currently running
		for k in queue.get("queue_running", []):
			if k[3].get("client_id") == client_id:
				r = requests.post(
					f"{self.url}/interrupt",
					json    = {},
					timeout = 4,
				)
				r.raise_for_status()
				break

	def process(self, image, settings):
		"""
		Process one single image using the provided settings
		"""
		assert "workflow" in settings,"Missing workflow!"
		with self.lock:
			assert self.state == "idle",f"Incorrect worker state for processing '{self.state}'"
			self.state = "proc"

		# format workflow
		wf = deepcopy(settings.pop("workflow"))
		wf = format_workflow_path(wf, self.os)
		wf = set_input_image(wf, f"LiliumSD-{self.port}.png")

		# upload image if it exists
		if torch.is_tensor(image):
			# scale as required
			if "upscale_factor" in settings and settings["upscale_factor"] != 1.0:
				image  = torch.nn.functional.interpolate(
					image,
					scale_factor = (1.0 / settings["upscale_factor"]),
					mode = "bilinear",
				)
				log(f"Downscaled tile input image to {image.shape}", "debug")
			# actual upload:
			try:
				self.upload_image(image)
			except Exception as e:
				self.state = "idle"
				self.fail()
				raise Exception("Worker processing failed") from e
		else:
			log(f"Starting tile processing without input", "debug")

		# execute workflow and get result
		try:
			job_id = self.run_workflow(wf)
			out = self.download_image(job_id, find_output_image_id(wf))
		except Exception as e:
			self.state = "idle"
			self.fail()
			raise Exception("Worker processing (image upload) failed") from e

		# set to idle and return result
		with self.lock:
			self.state = "idle"
		return out

	def __str__(self):
		return self.name

	def __repr__(self):
		return self.name

	def __lt__(self, other):
		return self.priority > other.priority


### FAKE WORKER FOR TILE LOGIC TESTING ###
import random
class DebugWorker(ComfyUIWorker):
	"""
	Simple (fake) demo worker that implements all the same attributes as the main class
	Darkens output image instead of processing it.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def process(self, image, settings):
		with self.lock:
			assert self.state == "idle",f"Incorrect worker state for processing '{self.state}'"
			self.state = "proc"
		image *= 0.6
		time.sleep(random.random()*0.5+2.0)
		with self.lock:
			self.state = "idle"
		return image
	def parse(self):
		"""
		set everything to to placeholder values.
		"""
		self.os = "nt"
		self.gpu = "Demo"
		self.vram = 1.0
		self.vram_free = 0.5
		self.vram_perc = 0.5
		self.object_info = {}
		self.models = {
			"checkpoints": ["Demo"],
			"loras": ["Demo"],
			"vae": ["Demo"],
			"controlnet": ["Demo"],
			"upscale_models": ["Demo"],
		}
	def clear_queue(self):
		pass
	def parse_status(self):
		pass
	def reset(self):
		pass
	def abort(self):
		pass
