function parse_tiled_upscale_args() {
	let args = {}
	// todo: workspaces
	let div = document.getElementsByClassName("settings")[0]
	// div = mdiv.getElementsByClassName("tiling-settings")[0]

	// slicer settings
	args["slicer"] = {}
	//   name
	let name = div.getElementsByClassName("tiling-name")[0]
	args["slicer"]["name"] = name.options[name.selectedIndex].value
	//   size
	let size = div.getElementsByClassName("tiling-size")[0]
	args["slicer"]["size"] = parseInt(size.value)
	//   overlap
	let overlap = div.getElementsByClassName("tiling-overlap")[0]
	args["slicer"]["overlap"] = parseInt(overlap.value)
	//   uniform or not
	let uniform = div.getElementsByClassName("tiling-uniform")[0]
	args["slicer"]["uniform"] = uniform.checked

	// Mask settings
	args["mask"] = {}
	//   size
	args["mask"]["size"] = parseInt(size.value)
	//   feather
	let feather = div.getElementsByClassName("mask-feather")[0]
	args["mask"]["feather"] = parseInt(feather.value)
	//   paddings
	let padding = div.getElementsByClassName("mask-padding")[0]
	args["mask"]["padding"] = parseInt(padding.value)

	// Job settings
	args["job"] = {}
	args["job"]["type"] = "TiledUpscale"
	//   test run
	let dryrun = div.getElementsByClassName("tiling-dryrun")[0]
	args["job"]["dry_run"] = dryrun.checked
	//   tile image source
	let source = div.getElementsByClassName("tiling-source")[0]
	args["job"]["tile_source"] = source.options[source.selectedIndex].value
	//   noise source
	let noise = div.getElementsByClassName("tiling-noise")[0]
	args["job"]["tile_noise"] = noise.options[noise.selectedIndex].value

	// Image info
	args["job"]["image_name"] = input_image.name
	args["job"]["image_mode"] = input_image.mode
	//   image width
	let width = div.getElementsByClassName("image-width")[0]
	args["job"]["image_width"] = parseInt(width.value)
	//   image height
	let height = div.getElementsByClassName("image-height")[0]
	args["job"]["image_height"] = parseInt(height.value)
	//   workflow scale
	let factor = div.getElementsByClassName("tiling-upscale-factor")[0]
	args["job"]["upscale_factor"] = parseFloat(factor.value)

	// Workflow settings
	args["workflow"] = {}
	args["workflow"]["workflow"] = workflow_info.workflow
	//   positive prompt
	let positive = div.getElementsByClassName("workflow-positive-prompt")[0]
	if (positive.value.length > 0) {
		args["workflow"]["positive_prompt"] = positive.value
	}
	//   negative prompt
	let negative = div.getElementsByClassName("workflow-negative-prompt")[0]
	if (negative.value.length > 0) {
		args["workflow"]["negative_prompt"] = negative.value
	}
	return args
}

async function start_tiled_upscale_job() {
	let conf = parse_tiled_upscale_args()

	if (!conf.job.image_name) {
		set_error_popup("No input image!")
		return
	}
	if (conf.job.tile_noise != "local") {
		set_error_popup("Tile noise source must be 'Local' (Feature TBA)")
		return
	}

	console.log("Starting tiled upscale job.")
	console.log(conf)
	try {
		let data = await fetch("/api/exec/start", {
			method: "POST",
			headers: {"Content-Type": "application/json; charset=UTF-8"},
			body: JSON.stringify(conf)
		})
		console.log("Started", data)
	} catch (error) {
		console.log(error)
		set_error_popup(`Failed to start workflow - ${error}`)
	}
}

async function start_job() {
	start_tiled_upscale_job()
	document.getElementById("button-start").disabled = true
	document.getElementById("button-abort").disabled = false
	// reset if already has input
	document.getElementById("out").src = `/media/${input_image.mode}/${input_image.name}`
	main_display = "input"
	update_status()
}

async function abort_job() {
	document.getElementById("button-start").disabled = false
	document.getElementById("button-abort").disabled = true
	await fetch("/api/exec/abort", { method: "POST" })
	update_status()
	// wait for job to fully cancel before displaying input again
	setTimeout(function() {
		document.getElementById("out").src = `/media/${input_image.mode}/${input_image.name}`
		main_display = "input"
	}, 500)
}
