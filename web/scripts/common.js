// main global variables
main_display = "none" // none | input | preview | output
input_image = {
	"mode": null,
	"name": null,
}

// on page load
document.addEventListener("DOMContentLoaded", function() {
	// init UI
	update_status()
	update_worker_list()
	update_available_workflows()
	image_size_update()
	tiling_settings_update(document.getElementsByClassName("tiling-name")[0])
	update_status_timer = setInterval(update_status_loop, 1000);

	// drag and drop listener
	function prevent_default(e) {
		e.preventDefault()
		e.stopPropagation()
	}
	let main_div = document.getElementById("main")
	for (const e of ["dragenter", "dragover", "dragleave", "drop"]) {
		window.addEventListener(e, prevent_default, false)
		main_div.addEventListener(e, prevent_default, false)		
	}
	main_div.addEventListener("drop", main_image_drop, false)
});
