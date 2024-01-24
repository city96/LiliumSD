#
# Path/filename variables & manipulation
#
import os
import re

# init global path variables (last init at bottom of file)
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PATH_DICT = {}

# set default fname format options
DIGITS = 5                # For zero padding, e.g. 5=>00005
PREFIX = "LiliumSD_"      # Prefix for saved outputs
PREFIX_TMP = "LiliumTMP_" # Prefix for temp outputs
IMAGE_EXTS = ["png", "jpg", "jpeg", "webp"]

def get_root_dir():
	"""
	returns the root folder (by default, where main.py is)
	"""
	return ROOT

def get_base_path(mode):
	"""
	Returns requested input or output path.
	"""
	global PATH_DICT
	assert mode in PATH_DICT,f"Invalid path type '{mode}'!"
	return PATH_DICT[mode]

def set_base_path(mode, path, create=False, initial=False):
	"""
	Changes specified input/output path globally.
	create: create directory if it doesn't exist
	initial: add new mode/base path.
	"""
	path = os.path.realpath(os.path.normpath(path))
	if create and not os.path.isdir(path):
		os.mkdir(path)
	assert os.path.isdir(path),f"Path does not exist '{path}'"

	global PATH_DICT
	if initial:
		assert mode not in PATH_DICT,f"Path type already exists '{mode}'!"
		PATH_DICT[mode] = path
	else:
		assert mode in PATH_DICT,f"Invalid path type '{mode}'!"
		PATH_DICT[mode] = path

def set_default_base_paths():
	"""
	Initialize all required base paths to the default values.
	"""
	for mode in ["temp", "input", "output", "prompt"]:
		set_base_path(mode, os.path.join(get_root_dir(), mode), create=True, initial=True)

def find_max_id(folder, prefix=PREFIX, strict=True):
	"""
	Attempts to find the largest ID already in use in a folder of files
		prefix: See above. Defaults to global prefix.
		strict: Only look for images starting with the provided prefix
	"""
	if strict:
		assert type(prefix) == str and len(prefix)>0, f"Invalid prefix '{repr(prefix)}'"
		prefix = prefix.lower()

	pat = re.compile(r"[0-9]+")
	file_ids = [0]
	for file in os.listdir(folder):
		name = os.path.splitext(file)[0].lower()
		if strict:
			if not name.startswith(prefix):
				continue
			# only allow exact match
			try:
				file_id = int(name[len(prefix):])
			except ValueError:
				continue
			else:
				file_ids.append(file_id)
		else:
			if name.startswith(prefix):
				name = name[len(prefix):]
			# find any number in filename
			file_ids += [int(x) for x in re.findall(pat,name)]

	return max(file_ids)

def get_new_path_iter(mode, ext="png", prefix="", append=True, zeropad=DIGITS):
	"""
	Get an iterator that will keep returning the next available output path.
		mode: one of ['temp','input','output']
		ext: file extension
		prefix: prefix for type/group sorting. separate from global prefix.
		append: keep local prefix when generating filename
		zeropad: how many zeros to append to the front
	"""
	if mode == "temp":
		# temp files - always the same prefix
		prefix = PREFIX_TMP # randomize?
	elif append:
		# append local prefix to global prefix
		prefix = f"{PREFIX}{prefix}"

	# iterate available filenames
	base_path = get_base_path(mode)
	current_id = find_max_id(base_path, prefix=prefix) + 1
	while True:
		fname = f"{prefix}{current_id:>0{zeropad}}.{ext}"
		path = os.path.join(base_path, fname)
		if os.path.isfile(path):
			continue
		yield path
		current_id += 1

def get_new_path(*args, **kwargs):
	"""
	Get full output path for the next available name
		mode: one of ['temp','input','output']
		ext: file extension
		prefix: prefix for type/group sorting. separate from global prefix.
		append: keep local prefix when generating filename
		zeropad: how many zeros to append to the front
	"""
	gen = get_new_path_iter(*args, **kwargs)
	return next(gen)

def clean_path(mode, path, existing=True):
	"""
	Make sure path isn't outside the base dir and that the mode exists.
	Optionally raise exception if file is missing
	"""
	# verify mode exists
	try:
		base = get_base_path(mode)
	except:
		raise ValueError(f"Invalid mode! {mode}")
	# normalize both
	base = os.path.realpath(os.path.normpath(base))
	path = os.path.realpath(os.path.normpath(os.path.join(base,path)))
	# verify that it's in the local folder
	if not path.startswith(base):
		raise ValueError(f"Path outside base folder! {path}")
	if not os.path.isfile(path) and existing:
		raise FileNotFoundError(f"File does not exist! {path}")

	return base, path

def get_relative_path(mode, path, existing=True):
	"""
	Convert full path to relative compared to the mode base path
	"""
	base, path = clean_path(mode, path, existing)
	return path[len(base)+len(os.sep):]

def get_absolute_path(mode, path, existing=True):
	"""
	Convert relative path to absolute path
	"""
	base, path = clean_path(mode, path, existing)
	return path

def verify_extension(path, exts=IMAGE_EXTS, exception=False):
	"""
	Make sure file extension matches provided list.
	Defaults to image extensions.
	"""
	ext = os.path.splitext(path)[1]
	if not ext:
		if exception:
			raise ValueError(f"Missing extension! ({path})")
		return False
	if type(exts) == list and ext[1:] not in exts:
		if exception:
			raise ValueError(f"Invalid extension {ext}! Must be one of {exts}")
		return False
	if type(exts) == str and ext[1:] != exts:
		if exception:
			raise ValueError(f"Invalid extension {ext}! Must be [{exts}]")
		return False
	return True
