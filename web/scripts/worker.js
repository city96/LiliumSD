function create_worker_card(data) {
	let div = document.createElement("div")
	div.innerHTML = ""
	div.classList.add("worker")

	let name = document.createElement("a")
	name.classList.add("name")
	div.appendChild(name)

	let state = document.createElement("a")
	state.classList.add("state")
	div.appendChild(state)
	
	let id = document.createElement("a")
	id.classList.add("id")
	div.appendChild(id)
	
	let info = document.createElement("a")
	info.classList.add("info")
	info.innerHTML = "[info]"
	div.appendChild(info)

	return div
}

function update_worker_card(div, data) {
	let name = div.getElementsByClassName("name")[0]
	name.innerHTML = data.name

	let state = div.getElementsByClassName("state")[0]
	// pretty print
	let state_str = "unknown"
	let priority_str = data.priority.toFixed(2)
	let order_str = `#${data.order}`
	if (data.state == "proc") {
		state_str = "processing"
	} else if (data.state == "fail") {
		state_str = "failed"
		order_str = '--'
	} else if (data.state == "lock") {
		state_str = "disabled"
		order_str = '--'
	} else {
		state_str = data.state
	}
	div.classList.remove(["status_idle", "status_proc", "status_fail", "status_lock"])
	div.classList.add(`status_${data.state}`)
	state.innerHTML = `${order_str} | ${priority_str} | ${state_str}`
	
	let id = div.getElementsByClassName("id")[0]
	id.innerHTML = data.id
}

workers_info_old = {}
async function update_worker_list() {
	let workers = await fetch("/api/workers/info")
	workers = await workers.json()

	// probably a more elegant way of doing this.
	// e.g. checking which ones exist already
	if (workers_info_old == workers) {
		return
	}
	
	let old_list = document.getElementById("worker-list")
	let new_list = document.createElement("div")
	for(const wdata of workers) {
		let wdiv = create_worker_card(wdata)
		update_worker_card(wdiv, wdata)
		new_list.appendChild(wdiv)
	}
	old_list.innerHTML = new_list.innerHTML
	workers_info_old = workers
}
