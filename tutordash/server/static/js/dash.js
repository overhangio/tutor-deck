const modal_container = document.getElementById("modal_container");
let open_modal_button = document.querySelector(".open-modal-button");
let close_modal_button = document.querySelector(".close-modal-button");

open_modal_button.addEventListener("click", () => {
	modal_container.classList.add("show");
});
close_modal_button.addEventListener("click", () => {
	modal_container.classList.remove("show");
});

let closeToastButtons = document.querySelectorAll(".close-toast-button");
const toast = document.querySelector(".toast");

closeToastButtons.forEach((button) => {
	button.addEventListener("click", () => {
		hideToast(toast);
	});
});

function showToast(type = "success") {
	if (toast !== null) {
		toast.style.display = "flex"; // Show the toast
		setTimeout(() => {
			void toast.offsetHeight;
			toast.classList.add("active");
		}, 1);
	}
}

function hideToast() {
	if (toast !== null) {
		toast.classList.remove("active");

		// Wait for transition to complete before removing container
		setTimeout(() => {
			toast.style.display = "none";
		}, 500); // Match this to the CSS transition duration
	}
}
