// Handle modal
const modal_container = document.getElementById("modal_container");
let open_modal_button = document.querySelector(".open-modal-button");
let close_modal_button = document.querySelector(".close-modal-button");
if (open_modal_button !== null) {
	open_modal_button.addEventListener("click", () => {
		modal_container.classList.add("show");
	});
}
if (close_modal_button !== null) {
	close_modal_button.addEventListener("click", () => {
		modal_container.classList.remove("show");
	});
}

// Handle toast
const toast = document.querySelector(".toast");
let closeToastButtons = document.querySelectorAll(".close-toast-button");

closeToastButtons.forEach((button) => {
	button.addEventListener("click", () => {
		hideToast(toast);
	});
});
function showToast() {
	if (toast !== null) {
		toast.style.display = "flex";
		setTimeout(() => {
			void toast.offsetHeight;
			toast.classList.add("active");
		}, 1);
	}
}
function hideToast() {
	if (toast !== null) {
		toast.classList.remove("active");
		setTimeout(() => {
			toast.style.display = "none";
		}, 500);
	}
}
