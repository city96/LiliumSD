#
# Extra/misc functions
#
import torch
import torchvision.transforms.functional as F
from tqdm import tqdm

### Image related functions ###

def sanitize(t, channels=None):
	"""
	Force image/tensor to be in the correct [B,C,H,W] format.
	"""
	if not torch.is_tensor(t):
		t = F.to_tensor(t)

	dims = len(t.shape)
	if dims == 2: # [H,W]
		assert channels,"[H,W] image requires target channel count!"
		t = t.unsqueeze(0).repeat(channels, 1, 1).unsqueeze(0)
	elif dims == 3: # [C,H,W]
		t = t.unsqueeze(0)
	elif dims == 4: # [B,C,H,W] - expected
		pass
	else:
		raise ValueError(f"Invalid image shape '{t.shape}'!")
	return t

def channel_fix(t, channels=3):
	"""
	Try and fix image channel count
	"""
	# Fix channel count
	ch = t.shape[1]
	if ch == 1: # Single channel BW
		t = t.repeat(1, channels, 1, 1)
	elif ch == channels or channels > 4: # Correct/unknown channel count
		pass
	elif ch == 3 and channels == 4: # Missing alpha channel
		# t = torch.cat([t, t[:, :1], dim=1)
		t = torch.cat([t, torch.ones(t.shape[0], 1, t.shape[2],t.shape[3])], dim=1)
	elif ch == 4 and channels == 3: # Extra alpha channel
		t = t[:, :3]
	else:
		raise ValueError(f"Invalid mask channel count '{t.shape}'!")
	return t


### Log related functions ###
LOGLEVELS = {
	"debug":   0,
	"info":    1,
	"warning": 2,
	"error":   3,
}

def get_available_loglevels():
	"""
	return a list of available loglevel names
	"""
	return list(LOGLEVELS.keys())

MAX_LOGLEVEL = 0
def set_max_loglevel(name):
	"""
	Set verbosity (max. severity) for global logging
	"""
	global LOGLEVELS
	global MAX_LOGLEVEL
	assert name in LOGLEVELS, f"invalid loglevel '{name}'"
	MAX_LOGLEVEL = LOGLEVELS[name]
	log(f"Set max. log serverity to '{name}' ({MAX_LOGLEVEL})", "debug")

def log(msg, name="info"):
	"""
	Very simple logging function as to not break tqdm
	"""
	global LOGLEVELS
	global MAX_LOGLEVEL
	# check against current loglevel
	level = LOGLEVELS.get(name.lower(), 1)
	if level < MAX_LOGLEVEL:
		return
	# log to console
	tqdm.write(f"{name.upper()}: {str(msg)}")


### Pytorch font rendering ###
# (this is stupid don't use this)
LETTERS = {
	" " : torch.tensor([
		[0,0,0,0,0],
		[0,0,0,0,0],
		[0,0,0,0,0],
		[0,0,0,0,0],
		[0,0,0,0,0],
	]), "a" : torch.tensor([
		[0,0,1,0,0],
		[0,1,0,1,0],
		[1,0,0,0,1],
		[1,1,1,1,1],
		[1,0,0,0,1],
	]),"b" : torch.tensor([
		[1,1,1,1,0],
		[1,0,0,0,1],
		[1,1,1,1,0],
		[1,0,0,0,1],
		[1,1,1,1,1],
	]),"c" : torch.tensor([
		[0,0,1,1,1],
		[0,1,0,0,0],
		[1,0,0,0,0],
		[0,1,0,0,0],
		[0,0,1,1,1],
	]),"d" : torch.tensor([
		[1,1,1,1,0],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,1,1,1,0],
	]),"e" : torch.tensor([
		[1,1,1,1,1],
		[1,0,0,0,0],
		[1,1,1,1,0],
		[1,0,0,0,0],
		[1,1,1,1,1],
	]),"f" : torch.tensor([
		[1,1,1,1,1],
		[1,0,0,0,0],
		[1,1,1,1,0],
		[1,0,0,0,0],
		[1,0,0,0,0],
	]),"g" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,0,0],
		[1,0,1,1,1],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"h" : torch.tensor([
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,1,1,1,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
	]),"i" : torch.tensor([
		[1,1,1,1,1],
		[0,0,1,0,0],
		[0,0,1,0,0],
		[0,0,1,0,0],
		[1,1,1,1,1],
	]),"j" : torch.tensor([
		[0,1,1,1,1],
		[0,0,0,0,1],
		[0,0,0,0,1],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"k" : torch.tensor([
		[1,0,0,0,1],
		[1,0,0,1,0],
		[1,1,1,0,0],
		[1,0,0,1,0],
		[1,0,0,0,1],
	]),"l" : torch.tensor([
		[1,0,0,0,0],
		[1,0,0,0,0],
		[1,0,0,0,0],
		[1,0,0,0,0],
		[1,1,1,1,1],
	]),"m" : torch.tensor([
		[1,1,0,1,1],
		[1,0,1,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
	]),"n" : torch.tensor([
		[1,0,0,0,1],
		[1,1,0,0,1],
		[1,0,1,0,1],
		[1,0,0,1,1],
		[1,0,0,0,1],
	]),"o" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"p" : torch.tensor([
		[1,1,1,1,1],
		[1,0,0,0,1],
		[1,1,1,1,1],
		[1,0,0,0,0],
		[1,0,0,0,0],
	]),"q" : torch.tensor([
		[1,1,1,1,1],
		[1,0,0,0,1],
		[1,1,1,1,1],
		[0,0,0,0,1],
		[0,0,0,1,1],
	]),"r" : torch.tensor([
		[1,1,1,1,1],
		[1,0,0,0,1],
		[1,1,1,1,1],
		[1,0,0,1,0],
		[1,0,0,0,1],
	]),"s" : torch.tensor([
		[0,1,1,1,1],
		[1,0,0,0,0],
		[0,1,1,1,0],
		[0,0,0,0,1],
		[1,1,1,1,0],
	]),"t" : torch.tensor([
		[1,1,1,1,1],
		[0,0,1,0,0],
		[0,0,1,0,0],
		[0,0,1,0,0],
		[0,0,1,0,0],
	]),"u" : torch.tensor([
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"v" : torch.tensor([
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[0,1,0,1,0],
		[0,0,1,0,0],
	]),"w" : torch.tensor([
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,0,0,1],
		[1,0,1,0,1],
		[0,1,0,1,0],
	]),"x" : torch.tensor([
		[1,0,0,0,1],
		[0,1,0,1,0],
		[0,0,1,0,0],
		[0,1,0,1,0],
		[1,0,0,0,1],
	]),"y" : torch.tensor([
		[1,0,0,0,1],
		[0,1,0,1,0],
		[0,0,1,0,0],
		[0,1,0,0,0],
		[1,0,0,0,0],
	]),"z" : torch.tensor([
		[1,1,1,1,1],
		[0,0,0,1,0],
		[0,0,1,0,0],
		[0,1,0,0,0],
		[1,1,1,1,1],
	]),"0" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,1,1],
		[1,0,1,0,1],
		[1,1,0,0,1],
		[0,1,1,1,0],
	]),"1" : torch.tensor([
		[0,0,1,0,0],
		[0,1,1,0,0],
		[1,0,1,0,0],
		[0,0,1,0,0],
		[1,1,1,1,1],
	]),"2" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,0,1],
		[0,0,0,1,0],
		[0,0,1,0,0],
		[1,1,1,1,1],
	]),"3" : torch.tensor([
		[1,1,1,1,0],
		[0,0,0,0,1],
		[0,0,0,1,0],
		[0,0,0,0,1],
		[1,1,1,1,0],
	]),"4" : torch.tensor([
		[0,0,0,1,0],
		[0,0,1,0,0],
		[0,1,0,0,0],
		[1,1,1,1,1],
		[0,0,1,0,0],
	]),"5" : torch.tensor([
		[0,0,1,1,1],
		[0,1,0,0,0],
		[1,1,1,1,0],
		[0,0,0,0,1],
		[1,1,1,1,0],
	]),"6" : torch.tensor([
		[0,1,1,1,1],
		[1,0,0,0,0],
		[1,1,1,1,0],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"7" : torch.tensor([
		[1,1,1,1,1],
		[0,0,0,1,0],
		[0,1,1,1,0],
		[0,1,0,0,0],
		[1,0,0,0,0],
	]),"8" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,0,1],
		[0,1,1,1,0],
		[1,0,0,0,1],
		[0,1,1,1,0],
	]),"9" : torch.tensor([
		[0,1,1,1,0],
		[1,0,0,0,1],
		[0,1,1,1,0],
		[0,0,0,0,1],
		[0,1,1,1,0],
	]),
}

def get_text(text, scale=8):
	text = text.lower()
	out = torch.zeros(7, (len(text))*6+1)
	for k in range(len(text)):
		letter = LETTERS.get(text[k], LETTERS[" "])
		out[1:6, k*6+1:(k+1)*6] = letter
	out = out.float()
	out = torch.nn.functional.interpolate(
		out.unsqueeze(0).unsqueeze(0),
		scale_factor = scale,
		mode = "nearest",
	).squeeze(0).squeeze(0)
	return out
