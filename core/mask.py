#
# Mask creation/editing logic
#
import torch
from .utils import sanitize

def get_mask(shape, feather, padding):
	"""
	Create a [B,C,H,W] mask with soft edges and optional padding around the borders.
	<get_center_mask(9) equiv is s=512|f=56|p=28>
	"""
	assert (shape[2]%2==0 and shape[3]%2==0),"Mask size must be divisible by 2!"
	mask = torch.ones((shape[2]//2,shape[3]//2), dtype=torch.float32)

	# zero out offset region
	for k in range(padding):
		mask[k] *= 0.0
		mask[:, k] *= 0.0

	# fade out overlap region
	for k in range(feather):
		perc = (k+1)/feather
		mask[padding+k] *= perc
		mask[:, padding+k] *= perc

	# Rebuild mask from single corner, then expand to channels/batch
	mask = torch.cat((mask, torch.flip(mask, dims=(0,)))) 
	mask = torch.cat((mask, torch.flip(mask, dims=(1,))),dim=1)
	mask = mask.unsqueeze(0).unsqueeze(0).repeat(shape[0], shape[1], 1, 1) 
	return mask

def fix_mask_edge(mask, tile, perc=0.5):
	"""
	Stretch mask to the edge of the image for edge/corner tiles.
	"""
	mask = sanitize(mask)

	# find center/template for fill
	h_com = mask.shape[2]//2
	w_com = mask.shape[3]//2
	h_lim = int(mask.shape[2]*perc)
	w_lim = int(mask.shape[3]*perc)

	if tile.is_edge("h_start"):
		for k in range(h_lim):
			mask[:, :, k] = mask[:, :, h_com]

	if tile.is_edge("w_start"):
		for k in range(w_lim):
			mask[:, :, :, k] = mask[:, :, :, w_com]

	if tile.is_edge("h_end"):
		for k in range(1,h_lim):
			mask[:, :, -k] = mask[:, :, h_com]

	if tile.is_edge("w_end"):
		for k in range(1,w_lim):
			mask[:, :, :, -k] = mask[:, :, :, w_com]

	return mask

class MaskBuilder:
	"""
	Class which can be used to dynamically generate required masks.
	"""
	def __init__(self, mode="default", **kwargs):
		if mode == "default":
			self.mask_func = get_mask
			self.mask_args = {
				"feather": kwargs.get("feather", 0),
				"padding": kwargs.get("padding", 0),
			}
		else:
			raise ValueError(f"Unknown mask type '{mode}'!")

	def from_shape(self, shape):
		"""
		Create [B,C,H,W] mask from shape w/ initial settings
		"""
		return self.mask_func(shape, **self.mask_args)
