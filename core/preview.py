#
# Main logic for live preview during processing
#
import time
import torch
from PIL import Image, ImageDraw, ImageFont
from threading import Thread, Lock

from .utils import sanitize, get_text

OVERLAY = get_text("Preview", scale=4)

class TiledUpscalePreviewer:
	"""
	Previewer with separate thread and polling updates.
	"""
	def __init__(self, slicer, image, scale=None):
		"""
		slicer: slicer object being used
		image: scaled image that the output will be pasted onto
		polling: how often to check for changes (seconds)
		"""
		if not scale:
			if image.shape[2] > 2048:
				scale = 0.25
			elif image.shape[2] > 1024:
				scale = 0.5
			else:
				scale = 1.0

		self.slicer = slicer
		self.scale = scale
		self.image = torch.nn.functional.interpolate(
				image,
				scale_factor = self.scale,
				mode = "nearest",
		)
		self.preview = self.image.clone()
		self.changed = time.time()
		self.updated = 0
		self.lock = Lock()

	def mark_change(self):
		"""
		Mark preview as changed.
		"""
		with self.lock:
			self.changed = time.time()

	def get_preview(self):
		"""
		Get preview of the full image.
		"""
		with self.lock:
			done = self.slicer.done()
			proc = [x for x in self.slicer.tiles if x.proc]
		if self.changed != self.updated and not done:
			if len(proc) > 0: # looks stupid without any tiles
				self.preview = self.draw_overlay()
				self.updated = self.changed
		elif self.changed != self.updated and done:
			self.preview = self.draw_overlay()
			self.updated = self.changed
		return self.preview

	def draw_overlay(self, image=None, scale=None):
		"""
		Paste map of tiles being processed over provided or final image
		"""
		image = image or self.image.clone()
		scale = scale or self.scale
		overlay = self.get_overlay()
		mask = overlay>0.0
		prev = (image*overlay)
		image[mask] *= 0.25
		image += prev
		return torch.clamp(image, 0.0, 1.0)

	def get_overlay(self, scale=None):
		"""
		Get an overlay with the current tiles being processed outlined
		"""
		scale = scale or self.scale
		overlay = torch.zeros_like(self.image)
		for tile in [x for x in self.slicer.tiles if x.proc]:
			if not tile.proc:
				continue
			h_start = round(tile.h_start*scale)
			h_end   = round(tile.h_end*scale)
			w_start = round(tile.w_start*scale)
			w_end   = round(tile.w_end*scale)
			pad = 14

			overlay[:, :, h_start:h_end,w_start:w_end] = 0.2
			overlay[:, :, h_start+pad:h_end-pad,w_start+pad:w_end-pad] = 0.0

			text = get_text(tile.worker.name, scale=2)*4.0+0.2
			text = text[:h_end-h_start, :w_end-w_start]
			overlay[:, :, h_end-text.shape[0]:h_end, w_start:w_start+text.shape[1]] = text

		overlay[:, :, :OVERLAY.shape[0], :OVERLAY.shape[1]] = (OVERLAY*4.0+0.2)
		return overlay

class TiledUpscaleDebugPreviewer(TiledUpscalePreviewer):
	"""
	Allows displaying tile logic as a popup cv2 preview. Only works locally.
	"""
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.im_thread = Thread(
			target = self.imshow_loop,
			daemon = True,
		)
		self.im_thread.start()

	def imshow_loop(self):
		import cv2
		import numpy as np
		res = 1080
		while not self.slicer.done():
			if self.changed == self.updated:
				time.sleep(0.25)
				continue
			img = self.get_preview()
			# This is the worst line of code in this entire repo. I am proud of it.
			cv2.imshow("preview", cv2.resize(img[0].permute((1, 2, 0)).numpy()[:, :, ::-1], (int(res/img.shape[2]*img.shape[3]),res)))
			cv2.waitKey(16)
			time.sleep(0.25)
