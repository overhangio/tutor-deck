function setCookie(name, value, days) {
	var expires = "";
	if (days) {
		var date = new Date();
		date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = name + "=" + (value || "") + expires + "; path=/";
}
function getCookie(name) {
	var nameEQ = name + "=";
	var ca = document.cookie.split(";");
	for (var i = 0; i < ca.length; i++) {
		var c = ca[i];
		while (c.charAt(0) == " ") c = c.substring(1, c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
	}
	return null;
}
function eraseCookie(name) {
	document.cookie =
		name + "=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;";
}

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

// Define logs element
const logsElement = document.getElementById("tutor-logs");
