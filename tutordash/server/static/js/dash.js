document.getElementById("search-input").addEventListener("input", function () {
	let filter = this.value.toLowerCase();
	let plugins = document.querySelectorAll(".installed-plugin");

	plugins.forEach((plugin) => {
		let name = plugin.querySelector(".name a").textContent.toLowerCase();
		if (name.includes(filter)) {
			plugin.style.display = "";
		} else {
			plugin.style.display = "none";
		}
	});
});

let open = document.querySelectorAll(".open-modal-button");
const modal_container = document.getElementById("modal_container");
let close = document.querySelectorAll(".close-modal-button");

open.forEach((button) => {
	button.addEventListener("click", () => {
		modal_container.classList.add("show");
	});
});

close.forEach((button) => {
	button.addEventListener("click", () => {
		modal_container.classList.remove("show");
	});
});
