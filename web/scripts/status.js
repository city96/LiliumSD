function set_status(data) {
	let out = document.getElementById("out")
	let pbar = document.getElementById("main-pbar")
	let label = document.getElementById("main-pbar-label")
	
	let start = document.getElementById("button-start")
	let abort = document.getElementById("button-abort")
	let clear = document.getElementById("out-clear")
	
	if (data.status == "idle") {
		label_text = "[idle]"
		pbar.value = 0;
		pbar.max = 100;
		abort.disabled = true
		start.disabled = main_display == "none"
		if (main_display == "none") {
			clear.style.visibility = "hidden"
		} else {
			clear.style.visibility = "visible"
		}
	} else if (data.status == "proc") {
		label_text = data.progress.label
		pbar.value = data.progress.current;
		pbar.max = data.progress.total;
		start.disabled = true
		abort.disabled = false
		clear.style.visibility = "hidden"
		// show preview as main image
		if (main_display == "input") {
			main_display = "preview"
		}
	} else {
		label_text = `[${data.status}]`
		pbar.value = 0;
		pbar.max = 100;
	}
	// status/pbar label if changed
	if (label.innerHTML != label_text) {
		label.innerHTML = label_text
	}

	// update preview
	if (data.preview_changed && main_display == "preview") {
		let src = `/api/exec/preview?t=${data.preview_changed}`
		if (out.src != src) {
			out.src = src
		}
		main_display = "preview"
	}

	// switch to output if previous image was a preview
	if (data.output && main_display == "preview") {
		let img = data.output[0]
		let src = ""
		if (img.mode == "preview" && data.preview_changed) {
			src = `/api/exec/preview?t=${data.preview_changed}`
			main_display = "preview"
		} else {
			src = `/media/${img.mode}/${img.name}`
			main_display = "output"
		}
		if (out.src != src) {
			out.src = src
		}
	}
}

async function update_status() {
	let data = await fetch("/api/exec/status")
	data = await data.json()
	set_status(data)
}

var status_fail_count = 1
async function update_status_loop() {
	try {
		let data = await fetch("/api/exec/status")
		if (!data.ok) {
			throw new Error(`${data.statusText}`)
		}
		data = await data.json()
		set_status(data)
		status_fail_count = 0
		// not sure when it's best to poll this
		update_worker_list()
	} catch (error) {
		console.log(error)
		document.getElementById("button-start").disabled = true
		document.getElementById("button-abort").disabled = true
		// nevermind, this doesn't work
		// await new Promise(resolve => setTimeout(resolve, status_fail_count*1000))
		status_fail_count++
		if (status_fail_count < 180) {
			set_error_popup(`Failed to update status (x${status_fail_count})`)
		} else {
			set_error_popup("Failed to update status. Refresh page to reload UI.")
			clearInterval(update_status_timer)
		}
	}
}

function set_error_popup(message, timeout=5000) {
	// add error and show popup
	let popup = document.getElementById("error")
	popup.innerHTML = message
	popup.classList.remove("hidden")
	// leave indefinitely
	if (timeout <= 0) {
		return
	}
	// clear unless msg changed
	setTimeout(function() {
		if (popup.innerHTML == message) {
			dismiss_error_popup()
		}
	}, timeout)
}

function dismiss_error_popup() {
	document.getElementById("error").classList.add("hidden")
}
