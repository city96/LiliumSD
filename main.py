#
# Contains most API/server code. [Might be moved to dedicated file later.]
#
import os
import yaml
import asyncio
import aiohttp
import argparse
from aiohttp import web

from core.path import get_root_dir, set_base_path, set_default_base_paths
from core.utils import log, get_available_loglevels, set_max_loglevel

from core.server.meta import meta_api
from core.server.files import static_api, media_api, upload_api
from core.server.workers import worker_api, set_worker_class, init_workers, get_workers
from core.server.control import exec_api

def parse_args():
	"""
	Parse provided cli args
	"""
	parser = argparse.ArgumentParser(description="LiliumSD")
	parser.add_argument("--config", default="config.yaml", help="Config file to use")
	parser.add_argument("--listen", action=argparse.BooleanOptionalAction, help="Allow network access from other PCs")
	parser.add_argument("-p", "--port", type=int, default=7777, help="Port to listen on")
	parser.add_argument("--loglevel", choices=get_available_loglevels(), default="debug", help="Max severity to log to the console.")
	parser.add_argument("--backend", choices=["comfy", "debug"], default="comfy",  help="Backend type")
	args = parser.parse_args()
	return args

if __name__ == "__main__":
	# Parse CLI args
	args = parse_args()

	# set loglevel
	set_max_loglevel(args.loglevel)

	# parse config file
	with open(args.config, encoding="UTF-8") as f:
		conf = yaml.safe_load(f)

	# Initialize folders
	set_default_base_paths()
	set_base_path("web", os.path.join(get_root_dir(), "web"), create=False, initial=True)

	# Initialize workers
	set_worker_class(args.backend)
	init_workers(conf["workers"])

	# Setup args
	app = web.Application(client_max_size=150*1024*1024)
	app.add_routes([
		web.get("/media/{mode}/{name:.*}", media_api),
		web.get("/api/workers/{command}", worker_api),
		web.get("/api/meta/{command}", meta_api),
		web.get("/api/exec/{command}", exec_api),
		web.post("/api/exec/{command}", exec_api),
		web.post("/api/upload", upload_api),
		web.get("/", static_api),
		web.get("/{name:.*}", static_api), # default
	])
	# Launch main server
	web.run_app(
		app,
		host = "0.0.0.0" if args.listen else "127.0.0.1",
		port = args.port
	)
