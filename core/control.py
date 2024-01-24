#
# Main logic for threaded processing
#
import time
import torch
import traceback
from tqdm import tqdm
from queue import Queue
from threading import Thread, Lock

from .utils import sanitize, log
from .save import save_output_image
from .mask import MaskBuilder, fix_mask_edge
from .preview import TiledUpscalePreviewer, TiledUpscaleDebugPreviewer

class TiledUpscaleJob:
	def __init__(self, slicer, image, mask, workers, settings={}, preview=True, save=True):
		"""
		Iterate all tiles using the provided processing function.
		slicer: pre-initialized slicer object
		image: full image that the output will be pasted onto
		mask: Mask instance used to mask/recombine tiles
		workers: list of workers to dispatch jobs to
		settings: dict passed to worker for processing
		save: save final output to disk
		"""
		self.slicer = slicer
		self.image = sanitize(image)
		self.mask = mask # MaskBuilder instance or tensor, so no sanitize
		self.workers = workers

		self.lock = Lock()
		self.pbar = tqdm(total=len(self.slicer.tiles), unit="tile")

		self.save = save
		self.output = None # final image
		self.outputs = None # same but saved to disk

		# Not always used/required.
		self.settings = settings.copy()
		if "image_scale" not in settings:
			self.settings.update({
				"image_scale": 1.0,
				"image_height": self.image.shape[2],
				"image_width": self.image.shape[3],
				"image_shape": self.image.shape,
			})

		tile_src = settings.get("tile_source", "raw")
		if tile_src == "raw":
			self.source = image.clone()
		elif tile_src == "out":
			self.source = image
		else:
			raise ValueError(f"Unknown tile/image source '{tile_src}'! [raw|out]")

		# debug preview only works locally.
		if preview == "debug":
			self.previewer = TiledUpscaleDebugPreviewer(self.slicer, image.clone())
		elif preview:
			self.previewer = TiledUpscalePreviewer(self.slicer, image.clone())
		else:
			self.previewer = None

	def run(self):
		"""
		Run job to completion. Blocking.
		"""
		# set up queue for format (tile[Tile], tile_out[Tensor]) + start thread
		self.queue = Queue()
		self.assembler = Thread(target=self.assemble, daemon=True)
		self.assembler.start()

		while not self.slicer.done():
			# get tiles available for processing
			to_proc = self.slicer.get_tiles()
			if len(to_proc) == 0:
				time.sleep(0.3)
				continue
			# get free workers
			available = sorted([x for x in self.workers if x.state == "idle"])
			for tile in to_proc:
				if len(available) == 0:
					time.sleep(0.3)
					break
				worker = available.pop(0)
				# mark tile as busy
				with self.lock:
					log(f"Dispatching tile {tile} to worker {worker}", "info")
					tile.proc = True
					tile.worker = worker
				# dispatch worker
				Thread(
					target = self.process,
					args   = (tile, worker),
					daemon = True
				).start()
			time.sleep(0.15) # just to be safe
			# mark change on previewer
			if self.previewer:
				self.previewer.mark_change()
		# wait for assembler
		self.queue.join()
		self.assembler.join()
		# save output if required
		self.output = self.image
		if self.save:
			self.outputs = save_output_image(self.output, meta=self.settings)
		# update final preview
		if self.previewer:
			self.previewer.mark_change()
		#cleanup
		self.pbar.close()
		time.sleep(0.3)
		[x.reset() for x in self.workers]
		self.slicer.tiles = [] # free up RAM & speed up .done()

	def start(self):
		"""
		Run job to completion. Separate thread.
		"""
		self.runner = Thread(target=self.run, daemon=True)
		self.runner.start()

	def process(self, tile, worker):
		"""
		Process a single tile, add tile to queue when ready. Separate thread.
		"""
		# get actual image that'll be processed
		image = tile.get(self.source)

		# Not sure which one of these is useful, better include all.
		# (can't pass the entire tile since worker.process() is generic)
		settings = self.settings.copy()
		settings.update ({
			"tiling": True,
			"tile_w_id": tile.w,
			"tile_h_id": tile.h,
			"tile_h_start": tile.h_start,
			"tile_w_start": tile.w_start,
			"tile_h_end": tile.h_end,
			"tile_w_end": tile.w_end,
			"tile_width": tile.w_end-tile.w_start,
			"tile_height": tile.h_end-tile.h_start,
		})

		try:
			out = worker.process(image, settings)
		except Exception as e:
			log(f"Tile {tile} failed! ({e})", "error")
			log(f"Tile {tile} traceback:\n{traceback.format_exc()}", "debug")
			tile.proc = False
		else:
			self.queue.put((tile, out))

	def assemble(self):
		"""
		Receive tiles and paste them onto the output.
		"""
		# define function to prepare mask
		if torch.is_tensor(self.mask):
			get_mask = lambda shape: self.mask.clone()
		elif type(self.mask) == MaskBuilder:
			get_mask = self.mask.from_shape
		else:
			raise ValueError("Mask must be one of [Mask,Tensor]!")

		while not self.slicer.done():
			# get finished tile and paste onto output image
			tile, tile_image = self.queue.get() # FIFO, blocking
			tile_mask = get_mask(tile_image.shape)
			tile_mask = fix_mask_edge(tile_mask, tile)
			self.image = tile.put(self.image, tile_image, tile_mask)
			# mark tile as done
			with self.lock:
				tile.done = True
				tile.worker = None
				tile.proc = False
			# apply change to previewer
			if self.previewer:
				self.previewer.image = tile.put(
					image = self.previewer.image,
					scale = self.previewer.scale,
					mask  = tile_mask,
					tile  = torch.nn.functional.interpolate(
						tile_image,
						scale_factor = self.previewer.scale,
						mode = "nearest",
					)
				)
				self.previewer.mark_change()
			# end queue job
			self.queue.task_done()
			self.pbar.update()

	def abort(self):
		"""
		Abort job immediately.
		"""
		log("Job aborted.", "warning")
		self.save = False
		# todo: this definitely needs to be less medieval than this
		[x.abort() for x in self.workers]
		self.slicer.tiles = []

	def done(self):
		"""
		Check if job is finished.
		"""
		return self.slicer.done()
