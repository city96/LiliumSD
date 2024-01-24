workflow_info = {
	"workflow": {}
}

async function update_available_workflows() {
	console.log("Updating list of available workflows")
	let data = await fetch("/api/meta/workflow_list")
	data = await data.json()
	
	// save info about currently selected
	let old_val = null
	let old_select = document.getElementsByClassName("workflow-name")[0]
	if (old_select.options.length > 0) {
		old_val = old_select.options[old_select.selectedIndex].value
	}
	
	// create new list
	let new_val_id = 0
	let new_select = document.createElement("select")
	for (const name of data) {
		let opt = document.createElement("option")
		opt.innerHTML = name
		opt.value = name
		new_select.appendChild(opt)
		if (opt.value == old_val) {
			new_val_id = new_select.options.length - 1
		}
	}
	// write back info and select previously selected
	old_select.innerHTML = new_select.innerHTML
	old_select.selectedIndex = new_val_id
	
	// propagate
	update_current_workflow()
}

function set_prompt(prompt_type, text, if_empty=false) {
	let input = document.getElementsByClassName(`workflow-${prompt_type}-prompt`)[0]
	if (if_empty && input.value.length > 0) {
		return
	}
	if (text && text.length > 0) {
		input.value = text
	} else {
		input.value = ""
	}
}

function set_prompt_from_info(prompt_type, if_empty=false) {
	set_prompt(prompt_type, workflow_info[`${prompt_type}_prompt`], if_empty)
}

function set_prompt_from_input(prompt_type, if_empty=false) {
	set_prompt(prompt_type, input_image.meta[`${prompt_type}_prompt`], if_empty)
}

async function update_current_workflow() {
	let select = document.getElementsByClassName("workflow-name")[0]
	let name = select.options[select.selectedIndex].value
	console.log(`Fetching info for workflow '${name}'`)

	let data = await fetch(`/api/meta/workflow?name=${name}`)
	data = await data.json()
	workflow_info = data
}
