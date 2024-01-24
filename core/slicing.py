#
# Main tiling/slicing logic
#
import torch
import torchvision.transforms.functional as F

from .utils import sanitize

class Tile:
	"""
	Single tile with slicing logic
	"""
	def __init__(self, h_pair, w_pair, h_id, w_id, h_max, w_max):
		"""
		h_pair: start/end pair for height (vertical) dimension
		w_pair: start/end pair for width (horizontal) dimension
		w_id/h_id: tile coordinates
		h_max/w_max: max. tile coordinates
		"""
		self.done = False
		self.proc = False
		self.worker = None
		self.h_start, self.h_end = h_pair
		self.w_start, self.w_end = w_pair
		self.h, self.w = h_id, w_id
		self.h_max, self.w_max = h_max, w_max
		assert h_id <= h_max and w_id <= w_max, f"Invalid tile coordinates [{h_id},{w_id}]!"

	def is_edge(self, edge):
		"""
		Check if the tile is on the edge of the image
		"""
		assert edge in ["h_start", "h_end", "w_start", "w_end"], f"Invalid edge '{edge}'"
		if edge == "h_start" and self.h == 0:
			return True
		if edge == "h_end" and self.h == self.h_max:
			return True
		if edge == "w_start" and self.w == 0:
			return True
		if edge == "w_end" and self.w == self.w_max:
			return True
		return False

	def crop(self, t, scale=1.0):
		"""
		Crop any tensor to the tile coordinates w/ scaling
		"""
		h_start = round(self.h_start*scale)
		h_end   = round(self.h_end*scale)
		w_start = round(self.w_start*scale)
		w_end   = round(self.w_end*scale)

		dims = len(t.shape)
		if dims == 3:
			return t[:, h_start:h_end, w_start:w_end].clone()
		elif dims == 4:
			return t[:, :, h_start:h_end, w_start:w_end].clone()
		else:
			raise ValueError(f"Can't crop this shape '{t.shape}'")

	def get(self, image, scale=1.0):
		"""
		Crop tile from image
		"""
		return self.crop(sanitize(image), scale)

	def put(self, image, tile, mask=None, blend=1.0, scale=1.0):
		"""
		image: image to paste finished tile onto
		tile: finished tile
		mask: mask for recombine: 0.0=image|1.0=tile
		blend: mix in parts of original image
		scale: scale coordinates when pasting. NOT the image.
		"""
		image = sanitize(image)
		tile = sanitize(tile)

		if torch.is_tensor(mask):
			mask = sanitize(mask).to(tile.dtype)
			raw = self.crop(image, scale)
			# match mask shape to tile shape
			if mask.shape != tile.shape:
				mask = F.resize(mask, tile.shape[2:], antialias=True)
			# match original to new tile shape
			if raw.shape != tile.shape:
				raw = F.resize(raw, tile.shape[2:], antialias=True)	
			# combine original with processed using mask
			pos_mask = mask * blend
			neg_mask = torch.ones_like(pos_mask) - pos_mask
			tile = tile * pos_mask + raw * neg_mask

		# scale coordinates as required
		h_start = round(self.h_start*scale)
		h_end   = round(self.h_end*scale)
		w_start = round(self.w_start*scale)
		w_end   = round(self.w_end*scale)

		# padding - doesn't work as tile is center-cropped by backend, resulting in misalignment
		# full = torch.zeros((tile.shape[0], tile.shape[1], h_end-h_start, w_end-w_start))
		# full[:, :, :tile.shape[2], :tile.shape[3]] = tile
		# tile = full

		# paste tile back onto full image
		image[:, :, h_start:h_end,w_start:w_end] = tile
		return image

	def __str__(self):
		return f"[{self.h};{self.w}]"

	def __repr__(self):
		return f"[{self.h};{self.w}]"

class TileSlicerTemplate:
	"""
	Abstract class for other slicers to inherit from.
	"""
	def __init__(self, *args, **kwargs):
		raise NotImplementedError("Trying to use abstract class!")

	def get_tiles(self):
		"""
		Get a list of tiles that can be processed
		"""
		raise NotImplementedError("Trying to use abstract class!")

	def build_dim_segs(self, dim):
		"""
		Create list of start/end coordinate pairs for a single dimension
		"""
		raise NotImplementedError("Trying to use abstract class!")

	def build_tile_list(self, image):
		"""
		Create a list of tiles based on the input image
		"""
		self.tiles = []

		h_segs = self.build_dim_segs(image.shape[2])
		w_segs = self.build_dim_segs(image.shape[3])
		# Iterate height [vertical] segments
		for h in range(len(h_segs)):
			# Iterate width [horizontal] segments
			for w in range(len(w_segs)):
				# Initialize individual tile
				self.tiles.append(Tile(
					h_id = h,
					w_id = w,
					h_pair = h_segs[h],
					w_pair = w_segs[w],
					h_max = len(h_segs)-1,
					w_max = len(w_segs)-1,
				))

	def get_tile_at(self, h, w):
		"""
		Find tile by [h,w] coordinates
		"""
		tile = None
		for k in self.tiles:
			if k.h == h and k.w == w:
				tile = k
				break
		return tile

	def done(self):
		"""
		True if all tiles have been processed.
		"""
		return all([x.done for x in self.tiles])

class SimpleTileSlicer(TileSlicerTemplate):
	"""
	Basic tiling logic with fixed tile size & overlap.
	"""
	def __init__(self, image, size, overlap, uniform=False, *args, **kwargs):
		"""
		image: starting image to use
		size: length of tile edges
		overlap: overlap on either side (does not change size)
		uniform: force all tiles to be size*size
		"""
		self.size = size
		self.overlap = overlap
		self.uniform = uniform
		self.build_tile_list(sanitize(image))

	def build_dim_segs(self, dim):
		"""
		Create list of start/end coordinate pairs for a single dimension
		"""
		segs = [(0, min(self.size,dim))]
		while segs[-1][1] < dim:
			start = segs[-1][1] - self.overlap
			end   = segs[-1][1] + self.size - self.overlap
			if not self.uniform and end + self.size*0.3 > dim:
				end = dim # expand to end of segment
			if self.uniform and end >= dim:
				start = dim-self.size
			segs.append((max(start,0), min(end,dim)))
		return segs

	def get_tiles(self):
		"""
		Get list of tiles that can be processed
		! high concurrency version. probably suboptimal and non-deterministic
		"""
		to_proc = []
		for tile in self.tiles:
			if tile.done or tile.proc:
				continue
			dep_coords = []
			for h in [-1,0,1]:
				if h == -1 and tile.is_edge("h_start"): continue
				if h ==  1 and tile.is_edge("h_end"): continue
				for w in [-1,0,1]:
					if w == -1 and tile.is_edge("w_start"): continue
					if w ==  1 and tile.is_edge("w_end"): continue
					if h == 0 and w == 0: continue
					dep_coords.append((tile.h+h, tile.w+w))
			# check list of tiles
			valid = True
			for k in dep_coords:
				dep = self.get_tile_at(*k)
				if dep in to_proc or dep.proc:
					valid = False
					break
			if valid:
				to_proc.append(tile)
		return to_proc

class USDUSTileSlicer(TileSlicerTemplate):
	"""
	Bootleg ultimate SD upscale
	"""
	def __init__(self, image, size, overlap, uniform=False, *args, **kwargs):
		"""
		image: starting image to use
		size: length of tile edges
		overlap: total overlap on both sides (does not change size)
		uniform: force all tiles to be size*size (todo: mask??)
		"""
		self.size = size
		self.overlap = overlap
		self.uniform = uniform
		self.build_tile_list(sanitize(image))

	def build_dim_segs(self, dim):
		"""
		Create list of start/end coordinate pairs for a single dimension
		"""
		if not self.uniform:
			# this is mostly verified (1:1 with the comfy node)
			segs = [(0, min((self.size+self.overlap), dim))]
			while segs[-1][1] < dim:
				start = segs[-1][1] - (self.overlap * 2)
				end   = segs[-1][1] + (self.size)
				segs.append((max(start,0), min(end,dim)))
		else:
			# this is completely different. the real one just forces square tiles.
			segs = [(0, min(self.size+self.overlap, dim))]
			while segs[-1][1] < dim:
				start = segs[-1][1] - (self.overlap * 2)
				end   = segs[-1][1] + (self.size - self.overlap)
				if end >= dim:
					start = dim-(self.size+self.overlap)
				segs.append((max(start,0), min(end,dim)))
		return segs

	def get_tiles(self):
		"""
		Get a list of tiles that can be processed
		"""
		to_proc = []
		for tile in self.tiles:
			if tile.done:
				continue
			if tile.proc:
				to_proc = []
				break
			to_proc = [tile]
			break
		return to_proc

class NyanTileSlicer(TileSlicerTemplate):
	"""
	Custom tiling logic with half-tile overlap.
	> City96 || Lilium Project Committee
	"""
	def __init__(self, image, size, uniform=False, *args, **kwargs):
		"""
		image: starting image to use
		size: length of tile edges
		"""
		self.size = size
		self.uniform = uniform
		self.build_tile_list(sanitize(image))

	def build_dim_segs(self, dim):
		"""
		Create list of start/end coordinate pairs for a single dimension
		"""
		segs = [(0, min(self.size, dim))]
		while segs[-1][1] < dim:
			start = segs[-1][1] - self.size//2
			end   = segs[-1][1] + self.size//2
			if not self.uniform:
				if segs[-1][1] + self.size*0.75 > dim:
					end = dim # expand to end of segment
			else:
				if segs[-1][1] + self.size*0.5 > dim:
					start = dim - self.size
			segs.append((max(start,0), min(end,dim)))
		return segs

	def get_tiles(self):
		"""
		Get a list of tiles that can be processed
		"""
		to_proc = []
		for tile in self.tiles:
			if tile.done or tile.proc:
				continue

			# [0,0] is the only valid starting tile [special case]
			if tile.h == 0 and tile.w == 0:
				to_proc.append(tile)
				break

			# check tile above [height]
			if tile.h >= 1:
				dep = self.get_tile_at(tile.h-1, tile.w)
				if dep in to_proc or not dep.done:
					continue

			# check tile to the left [width]
			if tile.w >= 1:
				dep = self.get_tile_at(tile.h, tile.w-1)
				if dep in to_proc or not dep.done:
					continue

			# check tile diagonally up [cross]
			if tile.h >= 1 and not tile.is_edge("w_end"):
				dep = self.get_tile_at(tile.h-1, tile.w+1)
				if dep in to_proc or not dep.done:
					continue

			to_proc.append(tile)
		return to_proc

# List of all available slicing algos
SLICER_DICT = {
	"USDUS": USDUSTileSlicer,
	"Simple": SimpleTileSlicer,
	"NyanTile": NyanTileSlicer,
}

def get_slicer(name, *args, **kwargs):
	"""
	Return initialized tile slicer from name
	"""
	global SLICER_DICT
	assert name in SLICER_DICT,f"Invalid slicer type '{mode}'!"
	slicer_class = SLICER_DICT[name]
	return slicer_class(*args, **kwargs)
