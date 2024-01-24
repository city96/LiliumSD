//
// Settings/inputs
//

function label_update(input) {
	let label = input.previousElementSibling
	if (!label.classList.contains("label")) {
		return
	}
	label.innerHTML = `[${input.value}]`
}

function dry_run_label_update(input){
	let div = document.getElementById("button-start")
	if (input.checked) {
		div.innerHTML = "Test"
	} else {
		div.innerHTML = "Start"
	}
}

function tiling_settings_update(input) {
	// todo: workspaces
	let div = document.getElementsByClassName("settings")[0]
	// div = div.getElementsByClassName("tiling-settings")[0]
	// get args
	let name = div.getElementsByClassName("tiling-name")[0]
	let size = div.getElementsByClassName("tiling-size")[0]
	let overlap = div.getElementsByClassName("tiling-overlap")[0]
	let feather = div.getElementsByClassName("mask-feather")[0]
	let padding = div.getElementsByClassName("mask-padding")[0]
	let autopad = div.getElementsByClassName("mask-autopad")[0]
	let autofhr = div.getElementsByClassName("mask-autofhr")[0]
	let autopaddiv = div.getElementsByClassName("mask-autopad-div")[0]
	let autofhrdiv = div.getElementsByClassName("mask-autofhr-div")[0]
	let source = div.getElementsByClassName("tiling-source")[0]
	let factor = div.getElementsByClassName("tiling-upscale-factor")[0]

	slicer = name.options[name.selectedIndex].value
	if (input == name) {
		if (slicer == "NyanTile") {
			overlap.disabled = true
			autofhr.disabled = false
			autofhrdiv.style.visibility = "visible"
			source.selectedIndex = 1
		} else {
			overlap.disabled = false
			autofhr.checked = false
			autofhr.disabled = true
			autofhrdiv.style.visibility = "hidden"
			source.selectedIndex = 0
		}
		size.dispatchEvent(new Event("input"));
		autopad.dispatchEvent(new Event("input"));
		autofhr.dispatchEvent(new Event("input"));
	}
	
	// tile size
	if (input == size) {
		if (slicer == "NyanTile") {
			overlap.value = Math.round(parseInt(size.value) / 2.0)
			overlap.dispatchEvent(new Event("input"));
		}
		factor.dispatchEvent(new Event("input"));
	}

	// tile overlap
	if (input == overlap) {
		autopad.dispatchEvent(new Event("input"));
		autofhr.dispatchEvent(new Event("input"));
	}

	// mask feather
	if (input == feather) {
		autopad.dispatchEvent(new Event("input"));
	}

	// mask auto feather
	if (input == autofhr) {
		if (autofhr.checked) {
			feather.disabled = true
			if (slicer == "NyanTile") {
				feather.value = Math.round(
					parseInt(size.value) * 0.1093750
				)
			}
		} else if (!autofhr.checked) {
			feather.disabled = false
		}
		feather.dispatchEvent(new Event("input"));
	}

	// mask auto padding
	if (input == autopad) {
		if (autopad.checked) {
			padding.disabled = true
			if (slicer == "NyanTile") {
				padding.value = Math.round(
					parseInt(size.value) * 0.0546875
				)
			} else if (slicer == "Simple") {
				padding.value = Math.round(
					parseInt(overlap.value) / 2.0 - parseInt(feather.value)
				)
			} else if (slicer == "USDUS") {
				padding.value = Math.round(
					parseInt(overlap.value) - parseInt(feather.value)
				)
			}
		} else if (!autopad.checked) {
			padding.disabled = false
		}
		padding.dispatchEvent(new Event("input"));
	}
	
	// tiling workflow scale
	if (input == factor) {
		let label = factor.previousElementSibling
		if (!label.classList.contains("label")) {
			return
		}
		let src_size = Math.round(
			parseInt(size.value) * (1/parseInt(factor.value))
		)
		label.innerHTML = `[${src_size}=>${size.value}]`
	}
}

function image_size_update(input) {
	let out = document.getElementById("out")
	let div = document.getElementsByClassName("settings")[0]
	let height = div.getElementsByClassName("image-height")[0]
	let image_height = parseInt(height.value)
	let width = div.getElementsByClassName("image-width")[0]
	let image_width = parseInt(width.value)
	let scale = div.getElementsByClassName("image-scale")[0]
	let image_scale = parseFloat(scale.value)
	
	// empty image, would result in division by zero.
	if (out.naturalHeight == 0 || out.naturalWidth == 0) {
		height.value = 0
		width.value = 0
		scale.value = 0
		return
	}
	// initialize to current image if no args
	if (!input || input == out) {
		height.value = out.naturalHeight
		width.value = out.naturalWidth
		scale.value = 1.0
		return
	}
	// verify inputs
	if (input == width) {
		height.value = Math.round(
			image_width/out.naturalWidth * out.naturalHeight
		)
		scale.value = image_width/out.naturalWidth
	}
	if (input == height) {
		width.value = Math.round(
			image_height/out.naturalHeight * out.naturalWidth
		)
		scale.value = image_height/out.naturalHeight
	}
	if (input == scale) {
		width.value = Math.round(
			out.naturalWidth * image_scale
		)
		height.value = Math.round(
			out.naturalHeight * image_scale
		)
	}
	// make sure we got a value
}

//
// main image drag and drop/etc
//
function set_main_display(data) {
	main_display = "input"
	input_image.name = data.name
	input_image.mode = data.mode
	input_image.meta = data.meta
	let out = document.getElementById("out")
	out.src = `/media/${input_image.mode}/${input_image.name}`
	out.style.visibility = "visible"
	setTimeout(function() { // wait for image to load?
		image_size_update(out)
	}, 500)
}

function clear_main_display() {
	setTimeout(function() { // stop click/etc immediately triggering
		main_display = "none"
		input_image.name = "none"
		input_image.mode = "none"
		let out = document.getElementById("out")
		out.style.visibility = "hidden"
		out.src = ""
		update_status()
		image_size_update(out)
	}, 100)
}

async function upload_image(file) {
	if (!["image/png","image/jpeg","image.webp"].includes(file.type)) {
		set_error_popup(`Invalid file type '${file.type}'!`)
		return
	}
	
	console.log("Uploading new file...", file)
	let formData = new FormData()
	formData.append("image", file)

	try {
		let data = await fetch("/api/upload", {
			method: "POST",
			body: formData
		})
		data = await data.json()
		console.log("Upload ok", data)
		if (!data.name) {
			set_error_popup(`Failed to upload image. (${data})`)
			return
		}
		set_main_display(data)
		update_status()
	} catch (error) {
		console.log(error)
		document.getElementById("button-start").disabled = true
		document.getElementById("button-abort").disabled = true
		set_error_popup("Failed to upload image.")
	}
}

function main_image_drop(e) {
	e.preventDefault()
	e.stopPropagation()
	
	if (main_display != "none") {
		return
	}

	if (e.dataTransfer.files.length != 1) {
		set_error_popup("Only single-file inputs are allowed!")
		return
	}
	upload_image(e.dataTransfer.files[0])
}

function main_image_select() {
	if (main_display != "none") {
		return
	}

	let input = document.createElement('input')
	input.type = 'file'
	input.onchange = e => { 
		upload_image(e.target.files[0])
	}
	input.click()
}
