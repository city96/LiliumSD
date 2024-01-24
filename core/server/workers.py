#
# Worker handling
#
import asyncio
import aiohttp
from aiohttp import web

from ..worker import ComfyUIWorker, DebugWorker

workers = [] # list of workers for server
worker_class = ComfyUIWorker

def set_worker_class(mode):
	"""
	Allow setting 
	"""
	global worker_class
	if mode == "debug":
		worker_class = DebugWorker
	elif mode == "comfy":
		worker_class = ComfyUIWorker
	else:
		raise ValueError(f"Unknown worker type '{mode}'")

def init_workers(config):
	"""
	Initialize workers from config file (on startup)
	"""
	global workers
	workers = [worker_class(**x) for x in config]

def get_workers(excluse_failed=True):
	"""
	Return list of available workers
	"""
	if excluse_failed:
		return [x for x in workers if x.state not in ["fail","lock"]]
	else:
		return workers

async def worker_api(request):
	"""
	Handle worker related ops
	"""
	global workers
	cmd = request.match_info.get("command")
	if cmd == "info":
		"""
		Get info about all active workers
		"""
		info = []
		sort = sorted([x for x in workers if x.state not in ["fail","lock"]])
		for worker in sorted(workers):
			worker.parse_status()
			nfo = {}
			if worker in sort:
				nfo["order"] = sort.index(worker)+1 # no 1, no 2 etc..
			nfo.update(worker.get_info())
			info.append(nfo)
		return web.json_response(info)
	elif cmd == "add":
		"""
		Add worker (if doesn't exist)
		"""
		data = await request.json()
		# URL is required
		if url not in data.keys():
			return web.Response(status=400)

		# setup args
		worker_args = {}
		for key in ["url", "name", "priority"]:
			if key in data.keys():
				worker_args["key"] = data["key"]

		# create & append worker
		worker = worker_class(**worker_args)
		# todo: duplicates
		workers.append(worker)
		return web.Response(status=200)
	elif cmd == "del":
		"""
		Remove worker if exists
		"""
		data = await data.json()
		# URL used as ID
		if url not in data.keys():
			return web.Response(status=400)
		worker_id = urlparse(data["url"]).netloc

		# Find index of target worker
		worker_index = None
		for k in range(len(workers)):
			if workers[k].worker_id == worker_id:
				worker_index = k
				break
		if not worker_index:
			return web.Response(status=400)

		# Remove worker from pool
		deleted = workers.pop(worker_id) # todo: cleanup?
		return web.Response(status=200)
	else:
		return web.Response(status=404)
